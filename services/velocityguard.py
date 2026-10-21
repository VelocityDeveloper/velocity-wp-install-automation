"""VelocityGuard — sistem keamanan server buatan sendiri pengganti cPGuard (WAF, BFM, CSF, antivirus, CMS, Judi AI).

Modul ini menangani bagian "selalu membaik":
1. Laporan celah harian (JAM_LAPORAN WIB, server di setelan `celah_server`): scripts/server_celah_agent.py (HANYA BACA)
   mencari request yang LOLOS VelocityGuard 24 jam terakhir (probe rawan dijawab 2xx, POST ke .php tak wajar, pemindai
   404 yang tidak diblokir, bot bervolume tinggi di luar daftar WAF, berkas PHP baru di uploads/cache, catatan uji
   tanpa cPGuard). Hasil + usulan perbaikan → CELAH_DIR/<tanggal>.json + Telegram tim server.
2. Kandidat virtual patch: kerentanan CMS kritis/tinggi yang bisa dieksploitasi tanpa login (dari hasil scan CMS)
   dan jenisnya bisa ditahan WAF → masuk laporan, ditandai "baru" bila belum ada di laporan sebelumnya.
3. Catatan insiden (INSIDEN, jsonl): setiap problem/celah → penyebab, perbaikan, aturan VelocityGuard terkait.
Tidak ada perubahan apa pun di server — usulan dikerjakan manual (aturan WAF, ambang BFM, tanda antivirus).
"""
import base64
import html
import json
import re
import subprocess
import threading
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path

AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_celah_agent.py'
GUARD_DIR = Path('/var/lib/velocity/velocityguard')
CELAH_DIR = GUARD_DIR / 'celah'
SETELAN = GUARD_DIR / 'setelan.json'  # {celah_server: [host], terakhir: 'YYYY-MM-DD'}
INSIDEN = GUARD_DIR / 'insiden.jsonl'
CMS_HASIL = Path('/var/lib/velocity/server-cms/hasil')
JAM_LAPORAN = (7, 0)  # WIB, sesudah scan antivirus 01:30 & CMS 02:00
SERVER_BAWAAN = ['157.66.55.81', '103.103.175.182']  # Wulan & Farnaz: server uji tanpa cPGuard
BATAS_SSH = 900
# Jenis kerentanan tanpa login yang polanya bisa ditahan di WAF (virtual patch) sampai plugin diperbarui
POLA_PATCH = re.compile(r'(?i)(remote code|code execution|code injection|sql injection|file upload|file inclusion|'
                        r'path traversal|directory traversal|arbitrary file|privilege escalation|object injection|'
                        r'authentication bypass|account takeover|options? update)')
STATUS_INSIDEN = ('terbuka', 'dipantau', 'selesai')

_kunci = threading.Lock()
_job = {}
_daftar_server = None
_perintah_server = None
_ssh_key_file = None
_kirim_tg = None


def pasang(daftar_server, perintah_server, ssh_key_file, kirim_tg=None):
    """Dipanggil installer_status.py: daftar server hosting, pembuat perintah SSH (mux), kunci SSH, Telegram tim server."""
    global _daftar_server, _perintah_server, _ssh_key_file, _kirim_tg
    _daftar_server, _perintah_server, _ssh_key_file, _kirim_tg = daftar_server, perintah_server, ssh_key_file, kirim_tg


def kandidat_patch(judul):
    """Judul kerentanan → True bila tanpa login dan jenisnya bisa ditahan WAF. Dipakai juga notif CMS."""
    j = str(judul or '')
    return bool(re.search(r'(?i)unauthenticated|unauthorized|without authentication', j)) and bool(POLA_PATCH.search(j))


# ---------- Setelan ----------

def _json(path, bawaan):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return bawaan


def _tulis(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    tmp.replace(path)


def setelan():
    s = _json(SETELAN, {})
    s.setdefault('celah_server', SERVER_BAWAAN)
    return s


# ---------- Laporan celah ----------

def _celah_satu(srv, key, jam=24):
    cmd = _perintah_server(srv, key, 'command -v python3 >/dev/null && exec nice -n 15 ionice -c3 python3 - || exec /usr/libexec/platform-python -')
    sandi = base64.b64encode(json.dumps({'aksi': 'celah', 'jam': jam}).encode()).decode()
    mulai = time.time()
    try:
        r = subprocess.run(cmd, input=f"{AGEN.read_text()}\njalankan('{sandi}')\n", capture_output=True, text=True,
                           timeout=BATAS_SSH, check=False)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'timeout'}
    try:
        h = json.loads((r.stdout or '').strip().splitlines()[-1])
    except (ValueError, IndexError):
        pesan = (r.stderr or '').strip().splitlines()
        return {'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}
    h['detik'] = round(time.time() - mulai, 1)
    return h


def _usulan(h):
    """Hasil agen → daftar temuan berkelompok + usulan perbaikan VelocityGuard."""
    out = []
    # Probe rawan dijawab 2xx. Ukuran sama berulang di satu domain = halaman 404 palsu (soft-404), bukan bocor.
    per_dom = defaultdict(list)
    for t, dom, ip, met, uri, kode, ua, *uk in h.get('probe_lolos') or []:
        per_dom[dom].append({'t': t, 'ip': ip, 'uri': uri, 'kode': kode, 'ua': ua, 'ukuran': (uk or ['-'])[0]})
    for dom, xs in sorted(per_dom.items(), key=lambda x: -len(x[1])):
        ukuran = Counter(x['ukuran'] for x in xs)
        # Jawaban 0 byte juga bukan bocor (berkas tak ada / dijawab kosong)
        soft = all(x['ukuran'] in ('0', '-') for x in xs) or (len(xs) >= 3 and ukuran.most_common(1)[0][1] >= len(xs) * 0.6)
        out.append({'jenis': 'probe_lolos', 'tingkat': 'info' if soft else 'tinggi', 'judul': f'{dom}: {len(xs)} probe path rawan dijawab 2xx',
                    'detail': xs[:15],
                    'usulan': 'Kemungkinan halaman 404 palsu (ukuran sama) — tetap tambahkan pola path ke aturan probe WAF agar dijawab 403 dan IP masuk BFM.'
                    if soft else 'Cek isi URL (bocor konfigurasi/dump?). Hapus berkas dari server bila ada, lalu tambah pola path ke aturan probe WAF.'})
    # POST 2xx ke .php tak wajar
    per_path = defaultdict(list)
    for t, dom, ip, uri, kode, ua in h.get('post_php') or []:
        per_path[(dom, uri.split('?', 1)[0])].append({'t': t, 'ip': ip, 'kode': kode, 'ua': ua})
    for (dom, path), xs in sorted(per_path.items(), key=lambda x: -len(x[1]))[:20]:
        rawan = bool(re.search(r'(?i)/wp-content/(uploads|cache|upgrade)/|/wp-includes/.+\.php', path))
        out.append({'jenis': 'post_php', 'tingkat': 'tinggi' if rawan else 'sedang',
                    'judul': f'{dom}{path}: {len(xs)} POST 2xx dari {len(set(x["ip"] for x in xs))} IP', 'detail': xs[:10],
                    'usulan': 'Kemungkinan webshell — Lihat berkas di Antivirus, karantina bila asing.' if rawan else
                    'Pastikan endpoint plugin/tema sah. Bila sah, masukkan pengecualian di agen celah agar tak muncul lagi.'})
    for ip, n, ndom, contoh in h.get('pemindai') or []:
        out.append({'jenis': 'pemindai', 'tingkat': 'sedang', 'judul': f'{ip}: {n} path 404 berbeda di {ndom} domain tanpa diblokir',
                    'detail': [{'uri': u} for u in contoh],
                    'usulan': 'Pemindai yang lolos WAF: cari pola path baru → aturan probe WAF; berulang → blokir permanen di Proteksi.'})
    for ua, n in h.get('bot_baru') or []:
        out.append({'jenis': 'bot_baru', 'tingkat': 'sedang', 'judul': f'{n} request 2xx dari UA bot di luar daftar WAF', 'detail': [{'ua': ua}],
                    'usulan': 'Kenali botnya. Tak berguna untuk klien → tambahkan ke waf/bot-seo.txt / bot-ai.txt / bot-jahat.txt lalu pasang ulang WAF.'})
    per_dir = defaultdict(list)
    for p, mt, uk in h.get('php_baru') or []:
        per_dir[p.rsplit('/', 1)[0]].append({'path': p, 't': mt, 'ukuran': uk})
    for d, xs in sorted(per_dir.items(), key=lambda x: -len(x[1]))[:20]:
        out.append({'jenis': 'php_baru', 'tingkat': 'tinggi' if '/uploads/' in d else 'sedang',
                    'judul': f'{len(xs)} berkas PHP baru di {d.replace("/home/", "", 1)}', 'detail': xs[:10],
                    'usulan': 'PHP di uploads/cache tak wajar — Lihat di Antivirus; bila cache plugin sah, catat sebagai pengecualian agen celah.'})
    pulih = [b for b in h.get('uji') or [] if 'PULIH' in b or 'JAGA' in b]
    if pulih:
        out.append({'jenis': 'uji', 'tingkat': 'tinggi', 'judul': f'Uji tanpa cPGuard: {len(pulih)} kejadian pulih/penjaga',
                    'detail': [{'baris': b} for b in pulih[-10:]],
                    'usulan': 'Cari penyebab lonjakan (log WAF menit itu) → aturan WAF/BFM baru agar tak terulang, lalu catat di Insiden.'})
    return out


def _kandidat_cve(hosts):
    """Kerentanan kritis/tinggi tanpa login & bisa di-virtual-patch, dari hasil scan CMS terakhir: {kunci: {...}}."""
    out = {}
    for host in hosts:
        d = _json(CMS_HASIL / f'{host}.json', {})
        kamus = d.get('kerentanan') or {}
        for s in d.get('situs') or []:
            for t in s.get('temuan') or []:
                for i in t.get('id') or []:
                    v = kamus.get(i) or {}
                    if v.get('tingkat') in ('kritis', 'tinggi') and kandidat_patch(v.get('judul')):
                        k = f"{t['slug']}|{i}"
                        x = out.setdefault(k, {'slug': t['slug'], 'nama': t.get('nama'), 'judul': v.get('judul'), 'tingkat': v['tingkat'],
                                               'link': v.get('link'), 'perbaiki': v.get('perbaiki'), 'situs': 0, 'server': []})
                        x['situs'] += 1
                        if d.get('server') not in x['server']:
                            x['server'].append(d.get('server'))
    return out


def _laporan_lalu(sebelum):
    for f in sorted(CELAH_DIR.glob('*.json'), reverse=True):
        if f.stem < sebelum:
            return _json(f, {})
    return {}


def laporan_jalan(oleh='Jadwal harian', hosts=None):
    servers = [s for s in _daftar_server() if s['host'] in (hosts or setelan()['celah_server'])]
    key = _ssh_key_file()
    tanggal = time.strftime('%Y-%m-%d')
    hasil = []
    for srv in servers:
        h = _celah_satu(srv, key)
        hasil.append({'host': srv['host'], 'server': srv['name'], 'ok': bool(h.get('ok')), 'error': h.get('error') or h.get('pesan'),
                      'request': h.get('request'), 'detik': h.get('detik'), 'cpguard_waf_off': h.get('cpguard_waf_off'),
                      'temuan': _usulan(h) if h.get('ok') else []})
    lalu = {c['kunci'] for c in _laporan_lalu(tanggal).get('cve') or []}
    cve = [{'kunci': k, **v, 'baru': k not in lalu} for k, v in _kandidat_cve([s['host'] for s in servers]).items()]
    cve.sort(key=lambda x: (not x['baru'], x['tingkat'] != 'kritis', -x['situs']))
    data = {'tanggal': tanggal, 'dibuat': int(time.time()), 'oleh': oleh, 'server': hasil, 'cve': cve}
    _tulis(CELAH_DIR / f'{tanggal}.json', data)
    _notif(data)
    return data


def _notif(data):
    if not _kirim_tg:
        return
    baris = [f"🛡️ <b>VelocityGuard — laporan celah {data['tanggal']}</b>"]
    for s in data['server']:
        if not s['ok']:
            baris.append(f"\n⚠️ <b>{html.escape(s['server'])}</b>: gagal ({html.escape(str(s['error']))})")
            continue
        t = s['temuan']
        tinggi = [x for x in t if x['tingkat'] == 'tinggi']
        baris.append(f"\n<b>{html.escape(s['server'])}</b> · {s['request'] or 0:,} request · {len(t)} temuan ({len(tinggi)} tinggi)".replace(',', '.'))
        for x in (tinggi + [x for x in t if x['tingkat'] != 'tinggi'])[:6]:
            baris.append(f"• {'🔴' if x['tingkat'] == 'tinggi' else '🟡' if x['tingkat'] == 'sedang' else '⚪'} {html.escape(x['judul'][:140])}")
    baru = [c for c in data['cve'] if c['baru']]
    if data['cve']:
        baris.append(f"\n🧩 <b>Kandidat virtual patch WAF</b>: {len(data['cve'])} kerentanan tanpa login ({len(baru)} baru)")
        for c in (baru or data['cve'])[:5]:
            baris.append(f"• {'🆕 ' if c['baru'] else ''}{html.escape(c['slug'])} — {c['situs']} situs: {html.escape(str(c['judul'])[:100])}")
    baris += ['', 'https://dash.velocity.ai.id/server/velocityguard']
    _kirim_tg('\n'.join(baris)[:4000])


def celah(tanggal=None):
    daftar = sorted((f.stem for f in CELAH_DIR.glob('*.json')), reverse=True)
    pilih = tanggal if tanggal in daftar else (daftar[0] if daftar else None)
    return {'tanggal': daftar[:60], 'laporan': _json(CELAH_DIR / f'{pilih}.json', None) if pilih else None,
            'setelan': setelan(), 'job': [j for j in _job.values() if j['status'] == 'berjalan']}


def _bersih_oleh(x):
    return re.sub(r'[^\w .-]', '', str(x or ''))[:40].strip()


def celah_mulai(payload):
    oleh = _bersih_oleh(payload.get('oleh'))
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    job = {'id': time.strftime('%Y%m%d-%H%M%S'), 'mulai': int(time.time()), 'oleh': oleh, 'status': 'berjalan'}
    with _kunci:
        if any(j['status'] == 'berjalan' for j in _job.values()):
            return {'error': 'laporan_sedang_jalan'}, 409
        _job[job['id']] = job

    def kerja():
        try:
            laporan_jalan(oleh)
            job.update(status='selesai', selesai=int(time.time()))
        except Exception as e:  # noqa: BLE001
            job.update(status='gagal', selesai=int(time.time()), error=str(e)[:200])
    threading.Thread(target=kerja, daemon=True).start()
    return job, 200


def jadwal_jalan():
    """Thread installer_status: tiap menit, sesudah JAM_LAPORAN, buat laporan celah sekali sehari."""
    while True:
        try:
            kini = time.localtime()
            tanda = time.strftime('%Y-%m-%d', kini)
            s = setelan()
            if (kini.tm_hour, kini.tm_min) >= JAM_LAPORAN and s.get('terakhir') != tanda and _ssh_key_file():
                s['terakhir'] = tanda
                _tulis(SETELAN, s)
                laporan_jalan()
        except Exception as e:  # noqa: BLE001
            print(f'velocityguard jadwal: {e}')
        time.sleep(60)


# ---------- Catatan insiden ----------

def insiden():
    data = {}
    try:
        for b in INSIDEN.read_text().splitlines():
            try:
                x = json.loads(b)
            except ValueError:
                continue
            if x.get('hapus'):
                data.pop(x.get('id'), None)
            else:
                data[x['id']] = {**data.get(x['id'], {}), **x}
    except OSError:
        pass
    return {'insiden': sorted(data.values(), key=lambda x: x.get('tanggal') or '', reverse=True), 'status': STATUS_INSIDEN}


def insiden_simpan(payload):
    """Tambah/ubah (append-only jsonl: baris terakhir per id menang) atau hapus satu catatan."""
    oleh = _bersih_oleh(payload.get('oleh'))
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    iid = str(payload.get('id') or '')
    if payload.get('hapus'):
        if not iid:
            return {'error': 'id_kosong'}, 400
        baris = {'id': iid, 'hapus': True, 'oleh': oleh, 'diubah': int(time.time())}
    else:
        judul = str(payload.get('judul') or '').strip()[:200]
        tanggal = str(payload.get('tanggal') or '')
        if not judul or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', tanggal):
            return {'error': 'judul_dan_tanggal_wajib'}, 400
        status = payload.get('status') if payload.get('status') in STATUS_INSIDEN else 'terbuka'
        baris = {'id': iid or uuid.uuid4().hex[:10], 'tanggal': tanggal, 'judul': judul, 'status': status,
                 'server': str(payload.get('server') or '')[:60],
                 **{k: str(payload.get(k) or '').strip()[:3000] for k in ('penyebab', 'perbaikan', 'aturan')},
                 'oleh': oleh, 'diubah': int(time.time())}
    with _kunci:
        GUARD_DIR.mkdir(parents=True, exist_ok=True)
        with INSIDEN.open('a') as f:
            f.write(json.dumps(baris, ensure_ascii=False, separators=(',', ':')) + '\n')
    return {'ok': True, 'id': baris['id']}, 200


if __name__ == '__main__':
    # Self-check logika tanpa SSH
    assert kandidat_patch('Kirki <= 6.3.1 - Unauthenticated Remote Code Execution')
    assert not kandidat_patch('Kirki <= 6.3.1 - Unauthenticated Stored Cross-Site Scripting')
    assert not kandidat_patch('Authenticated (Contributor+) SQL Injection')
    u = _usulan({'probe_lolos': [[1, 'a.com', '1.1.1.1', 'GET', f'/x{i}.sql', '200', 'ua', '5120'] for i in range(4)],
                 'post_php': [[1, 'a.com', '2.2.2.2', '/wp-content/uploads/z.php?x=1', '200', 'ua']],
                 'php_baru': [['/home/u/domains/a.com/public_html/wp-content/uploads/2026/z.php', 1, 10]],
                 'uji': ['PULIH 10:00:00: CPU']})
    assert [x['jenis'] for x in u] == ['probe_lolos', 'post_php', 'php_baru', 'uji'], u
    assert u[0]['tingkat'] == 'info' and u[1]['tingkat'] == 'tinggi'
    print('ok')
