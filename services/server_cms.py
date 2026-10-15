"""Kerentanan CMS (WordPress) server hosting — halaman /server/cms dashboard.

Alur scan (POST /api/servers/cms/scan, thread latar):
1. scripts/server_cms_agent.py dikirim lewat stdin SSH (hanya baca) → daftar instalasi WP + versi inti,
   plugin, tema, dan hasil "CMS Threat" cPGuard (cms.db) sebagai pembanding.
2. Setiap (jenis, slug) dicocokkan dengan basis data publik wpvulnerability.net (gratis, tanpa kunci API;
   feed Wordfence v3 wajib API key). Jawaban di-cache di VULN_DIR 24 jam; gagal ambil → pakai cache lama.
3. Hasil per server disimpan di HASIL_DIR/<host>.json; GET hanya membaca berkas (tanpa SSH).
Tidak ada perubahan apa pun di server klien — memperbarui plugin tetap dikerjakan manual/oleh tim.
Scan otomatis harian per server (JADWAL, diatur di halaman CMS): kerentanan kritis/tinggi yang BARU dibanding
hasil sebelumnya → Telegram tim server.
"""
import base64
import hashlib
import html
import json
import re
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_cms_agent.py'
CMS_DIR = Path('/var/lib/velocity/server-cms')
HASIL_DIR = CMS_DIR / 'hasil'
VULN_DIR = CMS_DIR / 'vuln'
RIWAYAT = CMS_DIR / 'riwayat.jsonl'
VULN_TTL = 86400
API = 'https://www.wpvulnerability.net'
UA = 'Mozilla/5.0 (X11; Linux x86_64) VelocityDashboard/1.0 (+https://velocitydeveloper.com)'
BATAS_SSH = 900
PEKERJA_API = 6
JADWAL = CMS_DIR / 'jadwal.json'  # {host: {harian, terakhir}}
JAM_JADWAL = (2, 0)  # WIB, sesudah scan antivirus 01:30
TINGKAT_HURUF = {'c': 'kritis', 'h': 'tinggi', 'm': 'sedang', 'l': 'rendah', 'n': 'rendah'}

_job = {}
_kunci = threading.Lock()
_daftar_server = None
_ssh_key_file = None
_kirim_tg = None


def pasang(daftar_server, ssh_key_file, kirim_tg=None):
    """Dipanggil installer_status.py: sumber daftar server hosting, kunci SSH, dan pengirim Telegram tim server."""
    global _daftar_server, _ssh_key_file, _kirim_tg
    _daftar_server, _ssh_key_file, _kirim_tg = daftar_server, ssh_key_file, kirim_tg


# ---------- Versi ----------

def urai_versi(v):
    """'6.8.1' → (6, 8, 1); '2.11.1.2' → (2, 11, 1, 2); '1.0-beta' → (1, 0). Tak terbaca → None."""
    m = re.match(r'\s*v?(\d+(?:\.\d+)*)', str(v or ''))
    if not m:
        return None
    t = [int(x) for x in m.group(1).split('.')]
    while len(t) > 1 and t[-1] == 0:
        t.pop()
    return tuple(t)


def _banding(a, op, b):
    return {'lt': a < b, 'le': a <= b, 'gt': a > b, 'ge': a >= b, 'eq': a == b}.get(op, False)


def terkena(versi, op):
    """op = operator wpvulnerability: min/max_version + min/max_operator + unfixed."""
    v = urai_versi(versi)
    if v is None:
        return False
    if op.get('min_version'):
        mn = urai_versi(op['min_version'])
        if mn is not None and not _banding(v, op.get('min_operator') or 'ge', mn):
            return False
    if op.get('max_version'):
        mx = urai_versi(op['max_version'])
        if mx is not None and not _banding(v, op.get('max_operator') or 'le', mx):
            return False
    elif str(op.get('unfixed')) != '1':
        return False  # tanpa batas atas dan bukan "belum diperbaiki" → data tak lengkap, jangan ditebak
    return True


# ---------- Basis data kerentanan ----------

def _ambil_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def _normal(v):
    """Satu entri wpvulnerability → bentuk ringkas untuk dashboard."""
    sumber = v.get('source') or []
    cve = [s['id'] for s in sumber if str(s.get('id', '')).startswith('CVE-')]
    # Judul deskriptif dari Wordfence/WPScan/Patchstack, bukan sekadar nomor CVE
    judul = next((s.get('name') for s in sumber if s.get('name') and not str(s.get('name')).startswith('CVE-')), None)
    if not judul:
        # Hanya ada CVE (umum untuk inti WP) → kalimat pertama deskripsinya
        teks = next((s.get('description') for s in sumber if s.get('description')), '') or ''
        judul = re.split(r'(?<=\.)\s', re.sub(r'^\[\w+\]\s*', '', teks.strip()), maxsplit=1)[0] or None
    tautan = next((s.get('link') for s in sumber if 'wordfence.com' in str(s.get('link'))), None) \
        or next((s.get('link') for s in sumber if s.get('link')), None)
    tanggal = max((s.get('date') or '' for s in sumber), default='')
    impak = v.get('impact') if isinstance(v.get('impact'), dict) else {}
    cvss = impak.get('cvss') or impak.get('cvss3') or {}
    try:
        skor = float(cvss.get('score')) if cvss.get('score') not in (None, '') else None
    except (TypeError, ValueError):
        skor = None
    tingkat = TINGKAT_HURUF.get(str(cvss.get('severity') or '')[:1].lower())
    if not tingkat and skor is not None:
        tingkat = 'kritis' if skor >= 9 else 'tinggi' if skor >= 7 else 'sedang' if skor >= 4 else 'rendah'
    jenis_cwe = next((c.get('name') for c in impak.get('cwe') or [] if c.get('name')), None)
    op = v.get('operator') or {}
    perbaiki = None
    if op.get('max_version') and op.get('max_operator') == 'lt':
        perbaiki = op['max_version']
    elif op.get('max_version') and op.get('max_operator') == 'le':
        perbaiki = '> ' + op['max_version']
    ssvc = impak.get('ssvc') or {}
    # uuid entri inti WP sama untuk semua kerentanan satu versi → id dari uuid + sumber
    kid = hashlib.sha1('|'.join([str(v.get('uuid'))] + [str(x.get('id')) for x in sumber]).encode()).hexdigest()[:20]
    return {'id': kid, 'judul': html.unescape(judul or v.get('name') or '-')[:220], 'cve': cve[:4], 'link': tautan,
            'tanggal': tanggal, 'skor': skor, 'tingkat': tingkat or 'tidak_diketahui', 'cwe': jenis_cwe,
            'perbaiki': perbaiki, 'belum_diperbaiki': str(op.get('unfixed')) == '1',
            'dieksploitasi': bool(ssvc.get('kev')) or ssvc.get('exploitation') == 'active',
            'op': {k: op.get(k) for k in ('min_version', 'min_operator', 'max_version', 'max_operator', 'unfixed')}}


def vuln(jenis, slug):
    """(daftar kerentanan ternormalisasi, info) untuk plugin/theme slug atau core versi. Cache disk 24 jam."""
    slug = slug.strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,120}', slug):
        return [], {}
    berkas = VULN_DIR / jenis / f'{slug}.json'
    lama = None
    try:
        lama = json.loads(berkas.read_text())
        if time.time() - lama.get('t', 0) < VULN_TTL:
            return lama['v'], lama.get('info', {})
    except (OSError, ValueError):
        pass
    try:
        d = _ambil_json(f'{API}/{jenis}/{urllib.parse.quote(slug)}/')
    except Exception:
        if lama:
            return lama['v'], lama.get('info', {})
        raise
    data = d.get('data') or {}
    daftar = [_normal(v) for v in data.get('vulnerability') or [] if isinstance(v, dict)]
    info = {'nama': data.get('name'), 'ditutup': bool(data.get('closed')), 'alasan_tutup': data.get('closed_reason')}
    berkas.parent.mkdir(parents=True, exist_ok=True)
    tmp = berkas.with_suffix('.tmp')
    tmp.write_text(json.dumps({'t': int(time.time()), 'v': daftar, 'info': info}, separators=(',', ':')))
    tmp.replace(berkas)
    return daftar, info


def versi_wp_terbaru():
    berkas = VULN_DIR / 'core-terbaru.json'
    try:
        lama = json.loads(berkas.read_text())
        if time.time() - lama['t'] < 6 * 3600:
            return lama['versi']
    except (OSError, ValueError, KeyError):
        lama = None
    try:
        d = _ambil_json('https://api.wordpress.org/core/version-check/1.7/')
        versi = (d.get('offers') or [{}])[0].get('current')
    except Exception:
        return lama['versi'] if lama else None
    if versi:
        berkas.parent.mkdir(parents=True, exist_ok=True)
        berkas.write_text(json.dumps({'t': int(time.time()), 'versi': versi}))
    return versi


# ---------- Scan ----------

def _inventaris(srv, key):
    sandi = base64.b64encode(json.dumps({'aksi': 'inventaris'}).encode()).decode()
    cmd = ['ssh', '-i', str(key), '-p', str(srv['port']), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
           '-o', 'ServerAliveInterval=30', '-o', 'StrictHostKeyChecking=accept-new', f"{srv['user']}@{srv['host']}",
           'command -v python3 >/dev/null && exec nice -n 15 ionice -c3 python3 - || exec /usr/libexec/platform-python -']
    try:
        r = subprocess.run(cmd, input=f"{AGEN.read_text()}\njalankan('{sandi}')\n", capture_output=True, text=True,
                           timeout=BATAS_SSH, check=False)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'timeout'}
    try:
        return json.loads((r.stdout or '').strip().splitlines()[-1])
    except (ValueError, IndexError):
        pesan = (r.stderr or '').strip().splitlines()
        return {'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}


def _cocokkan(job, inv):
    """Tambahkan 'temuan' ke setiap situs + kamus kerentanan bersama. Kembalikan (situs, kerentanan, galat_api)."""
    situs = inv['situs']
    perlu = set()
    for s in situs:
        perlu.add(('core', s['versi']))
        perlu.update(('plugin', p['slug'].lower()) for p in s['plugin'])
        perlu.update(('theme', t['slug'].lower()) for t in s['tema'])
    perlu = sorted(perlu)
    hasil, galat = {}, []
    job['kemajuan'] = {'tahap': 'kerentanan', 'ke': 0, 'dari': len(perlu)}

    def satu(k):
        try:
            hasil[k] = vuln(*k)
        except Exception as e:  # noqa: BLE001
            galat.append(f'{k[0]}/{k[1]}: {e}'[:160])
        job['kemajuan']['ke'] += 1
    with ThreadPoolExecutor(PEKERJA_API) as ex:
        list(ex.map(satu, perlu))

    kamus = {}
    for s in situs:
        temuan = []
        komponen = [('core', s['versi'], 'WordPress', s['versi'])] \
            + [('plugin', p['slug'].lower(), p['nama'], p['versi']) for p in s['plugin']] \
            + [('theme', t['slug'].lower(), t['nama'], t['versi']) for t in s['tema']]
        for jenis, slug, nama, versi in komponen:
            daftar, info = hasil.get((jenis, slug), ([], {}))
            # Inti: endpoint per versi → semua entri berlaku; plugin/tema: cek rentang versi
            kena = daftar if jenis == 'core' else [v for v in daftar if terkena(versi, v['op'])]
            if not kena and not info.get('ditutup'):
                continue
            for v in kena:
                kamus[v['id']] = {k: x for k, x in v.items() if k != 'op'}
            temuan.append({'jenis': jenis, 'slug': slug, 'nama': nama, 'versi': versi, 'id': [v['id'] for v in kena],
                           'ditutup': info.get('ditutup') and jenis != 'core', 'alasan_tutup': info.get('alasan_tutup')})
        s['temuan'] = temuan
    return situs, kamus, galat


def _ringkas(data):
    kamus = data.get('kerentanan') or {}
    out = {'situs': 0, 'rentan': 0, 'kritis': 0, 'tinggi': 0, 'sedang': 0, 'rendah': 0, 'tidak_diketahui': 0,
           'kerentanan': 0, 'inti_usang': 0, 'ditutup': 0, 'cpg_rentan': 0}
    terbaru = urai_versi(data.get('wp_terbaru'))
    for s in data.get('situs') or []:
        out['situs'] += 1
        ids = [i for t in s.get('temuan', []) for i in t['id']]
        if ids:
            out['rentan'] += 1
            tk = [kamus.get(i, {}).get('tingkat', 'tidak_diketahui') for i in ids]
            for nama in ('kritis', 'tinggi', 'sedang', 'rendah', 'tidak_diketahui'):
                if nama in tk:
                    out[nama] += 1
                    break
        out['kerentanan'] += len(ids)
        out['ditutup'] += sum(1 for t in s.get('temuan', []) if t.get('ditutup'))
        if terbaru and (urai_versi(s['versi']) or ()) < terbaru:
            out['inti_usang'] += 1
    for c in (data.get('cpguard') or {}).get('situs') or []:
        if str(c.get('rating') or 'safe').lower() != 'safe':
            out['cpg_rentan'] += 1
    return out


def _catat(baris):
    CMS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RIWAYAT, 'a') as f:
        f.write(json.dumps(baris, separators=(',', ':')) + '\n')


def _kerja(job, servers, key):
    try:
        job['kemajuan'] = {'tahap': 'inventaris', 'ke': 0, 'dari': len(servers)}
        inv = {}

        def ambil(srv):
            inv[srv['host']] = _inventaris(srv, key)
            job['kemajuan']['ke'] += 1
        utas = [threading.Thread(target=ambil, args=(s,), daemon=True) for s in servers]
        for t in utas:
            t.start()
        for t in utas:
            t.join(BATAS_SSH + 30)
        wp_terbaru = versi_wp_terbaru()
        gabung = {'situs': [s for h in inv.values() if h.get('ok') for s in h['situs']]}
        situs, kamus, galat = _cocokkan(job, gabung) if gabung['situs'] else ([], {}, [])
        HASIL_DIR.mkdir(parents=True, exist_ok=True)
        hasil = []
        for srv in servers:
            h = inv.get(srv['host']) or {'ok': False, 'error': 'timeout'}
            if not h.get('ok'):
                hasil.append({'host': srv['host'], 'server': srv['name'], 'ok': False, 'error': h.get('error')})
                continue
            punya = h['situs']  # dict yang sama dengan di `situs`, sudah diberi 'temuan' oleh _cocokkan
            lama = _baca_hasil(srv['host'])
            dipakai = {i for s in punya for t in s['temuan'] for i in t['id']}
            data = {'host': srv['host'], 'server': srv['name'], 'diambil': int(time.time()), 'oleh': job['oleh'],
                    'detik_ssh': h.get('detik'), 'terpotong': h.get('terpotong'), 'wp_terbaru': wp_terbaru,
                    'situs': punya, 'kerentanan': {i: kamus[i] for i in dipakai}, 'cpguard': h.get('cpguard'),
                    'cpguard_jalan': h.get('cpguard_jalan'), 'galat_api': galat[:30]}
            data['ringkas'] = _ringkas(data)
            tmp = HASIL_DIR / f".{srv['host']}.tmp"
            tmp.write_text(json.dumps(data, separators=(',', ':')))
            tmp.replace(HASIL_DIR / f"{srv['host']}.json")
            hasil.append({'host': srv['host'], 'server': srv['name'], 'ok': True, **data['ringkas']})
            if job.get('jadwal'):
                _notif_baru(srv['name'], lama, data)
        job.update(status='selesai', selesai=int(time.time()), hasil=hasil, galat_api=len(galat))
    except Exception as e:  # noqa: BLE001
        job.update(status='gagal', selesai=int(time.time()), error=str(e)[:200])
    if job.get('jadwal'):
        gagal = [h['server'] for h in job.get('hasil') or [] if not h.get('ok')] or ([] if job['status'] == 'selesai' else job['server'])
        if gagal and _kirim_tg:
            _kirim_tg(f"⚠️ <b>Scan CMS terjadwal gagal</b>: {html.escape(', '.join(gagal))} ({html.escape(str(job.get('error') or 'SSH'))}).")
    _catat({k: job.get(k) for k in ('id', 'mulai', 'selesai', 'oleh', 'target', 'status', 'error', 'hasil', 'galat_api')})


def _kritis(data):
    """{(path, slug, id): (domain, nama, versi, tingkat, judul)} untuk kerentanan kritis/tinggi."""
    kamus = (data or {}).get('kerentanan') or {}
    out = {}
    for s in (data or {}).get('situs') or []:
        for t in s.get('temuan', []):
            for i in t['id']:
                v = kamus.get(i, {})
                if v.get('tingkat') in ('kritis', 'tinggi'):
                    out[(s['path'], t['slug'], i)] = (s.get('domain') or s['path'], t['nama'], t['versi'], v['tingkat'], v.get('judul') or i)
    return out


def _notif_baru(nama, lama, baru):
    if not _kirim_tg:
        return
    sebelum = _kritis(lama)
    tambah = [v for k, v in _kritis(baru).items() if k not in sebelum]
    if not tambah:
        return
    baris = [f"• {'🔴' if t == 'kritis' else '🟠'} {html.escape(d)} — {html.escape(n)} {html.escape(str(ver))}: {html.escape(str(j)[:90])}"
             for d, n, ver, t, j in tambah[:10]]
    if len(tambah) > 10:
        baris.append(f'… dan {len(tambah) - 10} lagi')
    _kirim_tg('\n'.join([f'🛡️ <b>Kerentanan CMS baru di {html.escape(nama)}</b>', f'{len(tambah)} kerentanan kritis/tinggi baru', ''] + baris
                         + ['', f'https://dash.velocity.ai.id/server/cms?s={urllib.parse.quote(nama)}', 'Perbarui plugin/tema terkait (manual).']))


def _mulai(servers, key, oleh, target, jadwal=False):
    job = {'id': time.strftime('%Y%m%d-%H%M%S'), 'mulai': int(time.time()), 'oleh': oleh, 'status': 'berjalan',
           'target': target, 'server': [s['name'] for s in servers]}
    if jadwal:
        job['jadwal'] = True
    with _kunci:
        if any(j['status'] == 'berjalan' for j in _job.values()):
            return None
        _job[job['id']] = job
    threading.Thread(target=_kerja, args=(job, servers, key), daemon=True).start()
    return job


def jadwal_baca():
    try:
        return json.loads(JADWAL.read_text())
    except (OSError, ValueError):
        return {}


def _jadwal_tulis(data):
    CMS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = JADWAL.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(JADWAL)


def jadwal_atur(payload):
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    if not any(s['host'] == payload.get('server') for s in _daftar_server()):
        return {'error': 'server_tidak_dikenal'}, 400
    with _kunci:
        data = jadwal_baca()
        j = data.setdefault(payload['server'], {})
        j.update(harian=bool(payload.get('harian')), oleh=oleh, diubah=int(time.time()))
        _jadwal_tulis(data)
    return {'ok': True, 'jadwal': data}, 200


def jadwal_jalan():
    """Thread installer_status: tiap menit, sesudah JAM_JADWAL, scan server berjadwal yang belum di-scan hari ini."""
    while True:
        try:
            kini = time.localtime()
            tanda = time.strftime('%Y-%m-%d', kini)
            data = jadwal_baca()
            servers = [s for s in _daftar_server() if (data.get(s['host']) or {}).get('harian')
                       and (data.get(s['host']) or {}).get('terakhir') != tanda]
            key = _ssh_key_file()
            if (kini.tm_hour, kini.tm_min) >= JAM_JADWAL and servers and key and \
                    _mulai(servers, key, 'Jadwal harian', servers[0]['host'] if len(servers) == 1 else 'semua', True):
                with _kunci:
                    data = jadwal_baca()
                    for s in servers:
                        data.setdefault(s['host'], {})['terakhir'] = tanda
                    _jadwal_tulis(data)
        except Exception as e:  # noqa: BLE001
            print(f'jadwal cms: {e}')
        time.sleep(60)


def scan_mulai(payload):
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    semua = _daftar_server()
    target = payload.get('server') or 'semua'
    servers = semua if target == 'semua' else [s for s in semua if s['host'] == target]
    if not servers:
        return {'error': 'server_tidak_dikenal'}, 400
    key = _ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}, 500
    job = _mulai(servers, key, oleh, target)
    if not job:
        return {'error': 'scan_sedang_jalan'}, 409
    return job, 200


def _baca_hasil(host):
    try:
        return json.loads((HASIL_DIR / f'{host}.json').read_text())
    except (OSError, ValueError):
        return None


def ringkasan():
    """GET /api/servers/cms: ringkas per server dari berkas hasil (tanpa SSH) + job berjalan."""
    out = []
    for s in _daftar_server():
        d = _baca_hasil(s['host'])
        item = {'host': s['host'], 'name': s['name']}
        if d:
            item.update(diambil=d['diambil'], oleh=d.get('oleh'), ringkas=d.get('ringkas'), cpguard_jalan=d.get('cpguard_jalan'),
                        wp_terbaru=d.get('wp_terbaru'))
        out.append(item)
    berjalan = next((j for j in _job.values() if j['status'] == 'berjalan'), None)
    terakhir = max(_job.values(), key=lambda j: j['mulai'], default=None)
    return {'servers': out, 'job': berjalan or terakhir, 'sumber': API, 'jadwal': jadwal_baca(), 'jam_jadwal': '%02d:%02d' % JAM_JADWAL}


def detail(host):
    if not any(s['host'] == host for s in _daftar_server()):
        return {'error': 'server_tidak_dikenal'}
    return _baca_hasil(host) or {'host': host, 'belum': True}


def riwayat(batas=100):
    try:
        baris = RIWAYAT.read_text().splitlines()[-batas:]
    except OSError:
        return {'riwayat': []}
    out = []
    for b in reversed(baris):
        try:
            out.append(json.loads(b))
        except ValueError:
            continue
    return {'riwayat': out}
