"""Pantauan Realtime VelocityGuard (halaman /server/pantau): email, spam, peretasan, DDoS, sistem dalam satu panel.

Thread `jalan` (installer_status) tiap INTERVAL detik menjalankan scripts/server_pantau_agent.py (aksi `periksa`,
jendela bergulir JENDELA detik) di semua server secara berurutan. Hasil dievaluasi terhadap ambang di SETELAN:
- `sinyal`  : {kat, tingkat waspada|bahaya, judul, nilai, ambang}
- `usulan`  : tindakan TERUKUR {id, aksi, target, dampak (angka dari snapshot terakhir), alasan, ukur}
Tindakan TIDAK otomatis: admin menekan tombol (POST /api/servers/pantau/aksi). Saat dijalankan, nilai metrik
`ukur` dicatat sebagai `sebelum`; pemeriksaan berikutnya (≥ UKUR_JEDA dtk kemudian) mengisi `sesudah` → riwayat
menunjukkan efek tiap tindakan. Blokir IP memakai firewall_aksi (pengaman IP kantor/server/whitelist + riwayat
firewall). Tindakan email (hapus frozen bercadangan, tahan/lepas pengirim, proses antrean) lewat agen.
Tidak ada notif Telegram di modul ini (lonjakan/WAF/BFM sudah punya notif sendiri).
"""
import base64
import ipaddress
import json
import subprocess
import threading
import time
import uuid
from collections import deque
from pathlib import Path

AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_pantau_agent.py'
DIR = Path('/var/lib/velocity/server-pantau')
SETELAN = DIR / 'setelan.json'
RIWAYAT = DIR / 'tindakan.jsonl'
TITIK = DIR / 'titik.json'
LONJAKAN_NOTIF = Path('/var/lib/velocity/server-lonjakan/notif.json')
INTERVAL = 30
JENDELA = 300
TITIK_MAKS = 120  # 120 × 30 dtk = 1 jam tren
UKUR_JEDA = 25
TTL_BLOKIR = 3600

AMBANG = {  # [waspada, bahaya]; nilai per JENDELA (5 menit) kecuali disebut lain
    'antrean': [300, 1000], 'frozen_hapus': 20, 'antrean_pengirim': 50, 'kirim_akun': [60, 150],
    'spam_ditolak': [200, 800], 'auth_gagal_ip': 15, 'auth_gagal': [100, 400],
    'lfd_blokir': [30, 100], 'waf_tolak': [1500, 5000], 'ssh_gagal_ip': 10,
    'syn_recv': [300, 1500], 'koneksi_ip': 80, 'conntrack_persen': [60, 85],
    'load_per_cpu': [1.0, 2.0], 'disk': [85, 95], 'ram': [90, 97],
}
# Jangan pernah diusulkan diblokir: IP kantor, Cloudflare (Wajar di balik CF), crawler mesin pencari/Meta resmi.
JANGAN_BLOKIR = [ipaddress.ip_network(n) for n in (
    '202.59.194.129/32', '125.163.212.93/32', '36.65.0.93/32',
    '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22', '141.101.64.0/18', '108.162.192.0/18',
    '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
    '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22', '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32',
    '2405:b500::/32', '2405:8100::/32', '2a06:98c0::/29', '2c0f:f248::/32',
    '66.249.64.0/19', '64.233.160.0/19', '157.55.0.0/16', '40.77.0.0/16', '207.46.0.0/16', '57.141.0.0/16',
    '173.252.64.0/18', '69.63.176.0/20', '66.220.144.0/20', '17.0.0.0/8')]
TINGKAT = {'normal': 0, 'waspada': 1, 'bahaya': 2}

_kunci = threading.Lock()
_kini = {}       # host → hasil periksa + evaluasi
_titik = {}      # host → deque titik tren
_tunggu = {}     # id tindakan → {host, ukur, sebelum, t}
_bangun = threading.Event()


def pasang(daftar_server, perintah_server, ssh_key_file, firewall_aksi):
    global _daftar_server, _perintah_server, _ssh_key_file, _firewall_aksi
    _daftar_server, _perintah_server, _ssh_key_file, _firewall_aksi = daftar_server, perintah_server, ssh_key_file, firewall_aksi
    try:
        for h, t in json.loads(TITIK.read_text()).items():
            _titik[h] = deque(t, maxlen=TITIK_MAKS)
    except (OSError, ValueError):
        pass


def setelan():
    try:
        s = json.loads(SETELAN.read_text())
    except (OSError, ValueError):
        s = {}
    return {**AMBANG, **(s.get('ambang') or {})}


def _agen(srv, key, perintah, batas=90):
    cmd = _perintah_server(srv, key, 'command -v python3 >/dev/null && exec nice -n 15 ionice -c3 python3 - || exec /usr/libexec/platform-python -')
    sandi = base64.b64encode(json.dumps(perintah).encode()).decode()
    try:
        r = subprocess.run(cmd, input=f"{AGEN.read_text()}\njalankan('{sandi}')\n", capture_output=True, text=True,
                           timeout=batas, check=False)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'timeout'}
    try:
        return json.loads((r.stdout or '').strip().splitlines()[-1])
    except (ValueError, IndexError):
        pesan = (r.stderr or '').strip().splitlines()
        return {'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}


def boleh_blokir(ip):
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.is_global and not any(a.version == n.version and a in n for n in JANGAN_BLOKIR)


def _tingkat(nilai, ambang):
    if nilai is None:
        return 'normal'
    return 'bahaya' if nilai >= ambang[1] else 'waspada' if nilai >= ambang[0] else 'normal'


def _ambil(d, jalur):
    for k in jalur:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def nilai_ukur(d, ukur):
    """Metrik tindakan: angka di jalur, atau n milik ukur['k'] di daftar {k,n} (0 bila sudah hilang)."""
    v = _ambil(d, ukur['jalur'])
    if 'k' in ukur:
        return next((x['n'] for x in v or [] if x.get('k') == ukur['k']), 0)
    return v


def evaluasi(d, a):
    sinyal, usulan = [], []

    def s(kat, nilai, ambang, judul):
        t = _tingkat(nilai, ambang)
        if t != 'normal':
            sinyal.append({'kat': kat, 'tingkat': t, 'judul': judul, 'nilai': nilai, 'ambang': ambang})

    def u(kat, aksi, target, dampak, alasan, ukur, tingkat='waspada', **ekstra):
        usulan.append({'id': f"{aksi}:{target}", 'kat': kat, 'aksi': aksi, 'target': target, 'dampak': dampak,
                       'alasan': alasan, 'ukur': ukur, 'tingkat': tingkat, **ekstra})

    em, q = d.get('email') or {}, (d.get('email') or {}).get('antrean') or {}
    if q.get('ada'):
        s('email', q.get('total'), a['antrean'], f"Antrean email {q.get('total')} pesan")
        if (q.get('frozen_24j') or 0) >= a['frozen_hapus']:
            u('email', 'hapus_frozen', '24 jam', f"{q['frozen_24j']} pesan frozen ≥24 jam dihapus (disalin dulu ke /root/velocity-cadangan)",
              f"{q['frozen']} frozen dari {q['total']} antrean; frozen = bounce/pesan gagal yang tak akan terkirim",
              {'jalur': ['email', 'antrean', 'frozen'], 'satuan': 'pesan frozen'})
        for p in q.get('pengirim') or []:
            if p['n'] >= a['antrean_pengirim'] and '@' in p['k']:
                u('email', 'tahan_pengirim', p['k'], f"{p['n']} pesan dari pengirim ini dibekukan (bisa dilepas lagi)",
                  f"Satu pengirim menguasai antrean — indikasi akun/skrip spam", {'jalur': ['email', 'antrean', 'pengirim'], 'k': p['k'], 'satuan': 'pesan antrean'},
                  'bahaya' if p['n'] >= 3 * a['antrean_pengirim'] else 'waspada')
    log = em.get('log') or {}
    if log:
        s('email', log.get('auth_gagal'), a['auth_gagal'], f"{log.get('auth_gagal')} login SMTP/IMAP gagal / 5 mnt")
        s('spam', (log.get('spam_ditolak') or 0) + (log.get('rbl_ditolak') or 0), a['spam_ditolak'],
          f"{(log.get('spam_ditolak') or 0) + (log.get('rbl_ditolak') or 0)} email spam/RBL ditolak / 5 mnt")
        for p in em.get('pengirim_akun') or []:
            s('spam', p['n'], a['kirim_akun'], f"Akun {p['k']} mengirim {p['n']} email / 5 mnt (cek akun dibobol / skrip)")
        for p in em.get('auth_ip') or []:
            if p['n'] >= a['auth_gagal_ip'] and boleh_blokir(p['k']):
                u('retas', 'blokir_ip', p['k'], f"IP diblokir 1 jam di server ini ({p['n']} login email gagal / 5 mnt hilang)",
                  'Tebak sandi email (brute force SMTP/IMAP)', {'jalur': ['email', 'auth_ip'], 'k': p['k'], 'satuan': 'login gagal'})
    r = d.get('retas') or {}
    s('retas', (r.get('lfd') or {}).get('blokir'), a['lfd_blokir'], f"{(r.get('lfd') or {}).get('blokir')} IP diblokir LFD / 5 mnt")
    s('retas', (r.get('waf') or {}).get('tolak'), a['waf_tolak'], f"{(r.get('waf') or {}).get('tolak')} request ditolak WAF / 5 mnt")
    for p in (r.get('ssh') or {}).get('ip') or []:
        if p['n'] >= a['ssh_gagal_ip'] and boleh_blokir(p['k']):
            u('retas', 'blokir_ip', p['k'], f"IP diblokir 1 jam ({p['n']} login SSH gagal / 5 mnt)", 'Tebak sandi SSH',
              {'jalur': ['retas', 'ssh', 'ip'], 'k': p['k'], 'satuan': 'login SSH gagal'}, 'bahaya')
    k = d.get('ddos') or {}
    s('ddos', k.get('syn_recv'), a['syn_recv'], f"{k.get('syn_recv')} koneksi SYN_RECV (setengah terbuka)")
    if k.get('conntrack') and k.get('conntrack_maks'):
        pc = round(100 * k['conntrack'] / k['conntrack_maks'])
        s('ddos', pc, a['conntrack_persen'], f"Tabel conntrack {pc}% penuh")
    for p in k.get('ip_web') or []:
        if p['n'] >= a['koneksi_ip'] and boleh_blokir(p['k']):
            u('ddos', 'blokir_ip', p['k'], f"IP diblokir 1 jam ({p['n']} koneksi web aktif dari 1 IP putus)",
              'Satu IP membuka koneksi web berlebihan (flood/scraper)', {'jalur': ['ddos', 'ip_web'], 'k': p['k'], 'satuan': 'koneksi'},
              'bahaya' if p['n'] >= 2 * a['koneksi_ip'] else 'waspada')
    si = d.get('sistem') or {}
    if si.get('load'):
        lpc = round(si['load'][0] / max(si.get('cpu') or 1, 1), 2)
        s('sistem', lpc, a['load_per_cpu'], f"Load {si['load'][0]} untuk {si.get('cpu')} CPU ({lpc}/CPU)")
    s('sistem', si.get('ram_persen'), a['ram'], f"RAM terpakai {si.get('ram_persen')}%")
    for m, v in (si.get('disk') or {}).items():
        s('sistem', v, a['disk'], f"Disk {m} {v}%")
    for nm, st in (si.get('layanan') or {}).items():
        if st != 'active':
            sinyal.append({'kat': 'sistem', 'tingkat': 'bahaya', 'judul': f"Layanan {nm} {st}", 'nilai': st, 'ambang': 'active'})
    if q.get('ada') and (q.get('total') or 0) >= a['antrean'][0] and (log.get('tunda') or 0) > (log.get('terkirim') or 0):
        u('email', 'jalankan_antrean', 'semua', f"Proses antrean sekali (exim -q); {q['total']} pesan dicoba kirim",
          'Antrean menumpuk & banyak pengiriman tertunda', {'jalur': ['email', 'antrean', 'total'], 'satuan': 'pesan antrean'})
    status = {kat: max([x['tingkat'] for x in sinyal if x['kat'] == kat], key=TINGKAT.get, default='normal')
              for kat in ('email', 'spam', 'retas', 'ddos', 'sistem')}
    for x in usulan:  # usulan menaikkan status kategorinya minimal ke tingkat usulan
        if TINGKAT[x['tingkat']] > TINGKAT[status[x['kat']]]:
            status[x['kat']] = x['tingkat']
    return sinyal, usulan, status


def _lonjakan_aktif(host):
    try:
        aktif = json.loads(LONJAKAN_NOTIF.read_text()).get('aktif') or {}
    except (OSError, ValueError):
        return []
    return [{'domain': k.split('|', 1)[1], 'mulai': int(v.get('mulai') or 0), 'puncak': v.get('puncak')}
            for k, v in aktif.items() if k.startswith(host + '|')]


def _titik_dari(d):
    em, r, k, si = d.get('email') or {}, d.get('retas') or {}, d.get('ddos') or {}, d.get('sistem') or {}
    log, q = em.get('log') or {}, em.get('antrean') or {}
    return [d['t'], q.get('total'), q.get('frozen'), log.get('auth_gagal'), (log.get('spam_ditolak') or 0) + (log.get('rbl_ditolak') or 0),
            (r.get('lfd') or {}).get('blokir'), (r.get('waf') or {}).get('tolak'), k.get('syn_recv'), k.get('web'),
            (si.get('load') or [None])[0]]


def periksa_server(srv, key):
    d = _agen(srv, key, {'aksi': 'periksa', 'jendela': JENDELA})
    kini = int(time.time())
    if not d.get('ok'):
        with _kunci:
            lama = _kini.get(srv['host']) or {}
            _kini[srv['host']] = {**lama, 'name': srv['name'], 'host': srv['host'], 'ok': False, 'error': d.get('error'), 't_gagal': kini}
        return
    sinyal, usulan, status = evaluasi(d, setelan())
    lonjakan = _lonjakan_aktif(srv['host'])
    if lonjakan:  # kejadian aktif dari modul Lonjakan (dinilai AI tidak wajar) = sinyal DDoS lapis aplikasi
        sinyal.append({'kat': 'ddos', 'tingkat': 'waspada', 'judul': f"Lonjakan request tidak wajar: {', '.join(x['domain'] for x in lonjakan[:3])}"
                       + (f" +{len(lonjakan) - 3}" if len(lonjakan) > 3 else ''), 'nilai': len(lonjakan), 'ambang': 1})
        if status['ddos'] == 'normal':
            status['ddos'] = 'waspada'
    with _kunci:
        _kini[srv['host']] = {'name': srv['name'], 'host': srv['host'], 'ok': True, 'data': d, 'sinyal': sinyal,
                              'usulan': usulan, 'status': status, 'lonjakan': lonjakan}
        _titik.setdefault(srv['host'], deque(maxlen=TITIK_MAKS)).append(_titik_dari(d))
        selesai = [i for i, w in _tunggu.items() if w['host'] == srv['host'] and kini - w['t'] >= UKUR_JEDA]
        ukur = {i: nilai_ukur(d, _tunggu.pop(i)['ukur']) for i in selesai}
    for i, v in ukur.items():
        _catat({'id': i, 'sesudah': v, 't_sesudah': kini})


def jalan():
    """Thread installer_status: periksa semua server tiap INTERVAL (lebih cepat bila ada tindakan baru)."""
    while True:
        mulai = time.time()
        try:
            key = _ssh_key_file()
            for srv in _daftar_server() if key else []:
                periksa_server(srv, key)
            DIR.mkdir(parents=True, exist_ok=True)
            with _kunci:
                isi = json.dumps({h: list(t) for h, t in _titik.items()})
            tmp = TITIK.with_suffix('.tmp')
            tmp.write_text(isi)
            tmp.replace(TITIK)
        except Exception as e:  # noqa: BLE001
            print(f'pantau: {e}')
        _bangun.wait(max(5, INTERVAL - (time.time() - mulai)))
        _bangun.clear()


def _catat(baris):
    DIR.mkdir(parents=True, exist_ok=True)
    with _kunci, RIWAYAT.open('a') as f:
        f.write(json.dumps(baris, ensure_ascii=False, separators=(',', ':')) + '\n')


def tindakan(batas=60):
    """Gabungkan baris awal + baris `sesudah` per id → daftar tindakan terbaru."""
    try:
        baris = RIWAYAT.read_text().splitlines()[-2000:]
    except OSError:
        return []
    per_id, urut = {}, []
    for b in baris:
        try:
            x = json.loads(b)
        except ValueError:
            continue
        if x['id'] not in per_id:
            per_id[x['id']] = {}
            urut.append(x['id'])
        per_id[x['id']].update(x)
    return [per_id[i] for i in reversed(urut[-batas:])]


def ringkasan():
    with _kunci:
        server = [{**v, 'titik': list(_titik.get(h, []))} for h, v in _kini.items()]
    urutan = {s['host']: i for i, s in enumerate(_daftar_server())}
    server.sort(key=lambda x: urutan.get(x['host'], 99))
    return {'interval': INTERVAL, 'jendela': JENDELA, 'ambang': setelan(), 't': int(time.time()), 'server': server,
            'tindakan': tindakan(), 'kolom_titik': ['t', 'antrean', 'frozen', 'auth_gagal', 'spam', 'lfd', 'waf', 'syn_recv', 'web', 'load']}


def aksi(payload):
    """Jalankan SATU usulan yang masih berlaku di snapshot terakhir (dampak dihitung ulang, bukan dari klien)."""
    oleh = str(payload.get('oleh') or '').strip()[:40]
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    host = payload.get('server')
    srv = next((s for s in _daftar_server() if s['host'] == host), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    if payload.get('aksi') == 'periksa':
        _bangun.set()
        return {'ok': True}, 200
    with _kunci:
        kini = _kini.get(host) or {}
        u = next((x for x in kini.get('usulan') or [] if x['id'] == payload.get('id')), None)
        data = kini.get('data') or {}
    if not u:
        return {'error': 'usulan_kedaluwarsa'}, 409
    key = _ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}, 500
    sebelum = nilai_ukur(data, u['ukur'])
    if u['aksi'] == 'blokir_ip':
        if not boleh_blokir(u['target']):
            return {'error': 'ip_dilindungi'}, 400
        obj, kode = _firewall_aksi({'aksi': 'blokir', 'server': host, 'ip': u['target'], 'ttl': TTL_BLOKIR, 'oleh': oleh,
                                    'ket': f"pantau {u['kat']}: {u['alasan']}"[:120]})
        hasil = (obj.get('servers') or [obj])[0] if kode == 200 else obj
        ok = kode == 200 and bool(hasil.get('ok'))
    else:
        perintah = {'aksi': u['aksi']}
        if u['aksi'] == 'tahan_pengirim':
            perintah['pengirim'] = u['target']
        elif u['aksi'] == 'hapus_frozen':
            perintah['umur'] = 86400
        hasil = _agen(srv, key, perintah, 300)
        ok = bool(hasil.get('ok'))
    tid = uuid.uuid4().hex[:12]
    _catat({'id': tid, 't': int(time.time()), 'oleh': oleh, 'server': srv['name'], 'host': host, 'kat': u['kat'],
            'aksi': u['aksi'], 'target': u['target'], 'alasan': u['alasan'], 'dampak': u['dampak'], 'satuan': u['ukur'].get('satuan'),
            'sebelum': sebelum, 'ok': ok, 'error': hasil.get('error'), 'jumlah': hasil.get('jumlah'), 'cadangan': hasil.get('cadangan')})
    if ok:
        with _kunci:
            _tunggu[tid] = {'host': host, 'ukur': u['ukur'], 't': int(time.time())}
            # usulan yang sudah dijalankan disingkirkan sampai pemeriksaan berikutnya
            kini['usulan'] = [x for x in kini.get('usulan') or [] if x['id'] != u['id']]
        _bangun.set()
    return ({'ok': ok, 'id': tid, 'hasil': hasil}, 200) if ok else ({'error': hasil.get('error') or 'gagal', 'hasil': hasil}, 500)


def lepas_pengirim(payload):
    """Balikkan tahan_pengirim (exim -Mt) dari riwayat tindakan."""
    oleh = str(payload.get('oleh') or '').strip()[:40]
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not oleh or not srv:
        return {'error': 'invalid_oleh' if not oleh else 'server_tidak_dikenal'}, 400
    key = _ssh_key_file()
    hasil = _agen(srv, key, {'aksi': 'lepas_pengirim', 'pengirim': str(payload.get('pengirim') or '')}, 120)
    _catat({'id': uuid.uuid4().hex[:12], 't': int(time.time()), 'oleh': oleh, 'server': srv['name'], 'host': srv['host'], 'kat': 'email',
            'aksi': 'lepas_pengirim', 'target': payload.get('pengirim'), 'ok': bool(hasil.get('ok')), 'jumlah': hasil.get('jumlah'),
            'error': hasil.get('error')})
    return ({'ok': True, 'hasil': hasil}, 200) if hasil.get('ok') else ({'error': hasil.get('error') or 'gagal'}, 500)
