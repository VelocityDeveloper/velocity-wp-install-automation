"""Deteksi lonjakan request per domain (VelocityGuard) — MODE DETEKSI: dicatat + Telegram, tanpa tindakan di server.

Thread `jalan` (installer_status) tiap INTERVAL detik, untuk server di setelan `server.<host>.aktif`:
1. scripts/server_lonjakan_agent.py (aksi `periksa`) → domain yang request dinamisnya ≥ `kali` × baseline EWMA
   dan ≥ `min_per_menit`, beserta template URL teratas & cirinya (IP unik, maks per IP, status, referer, UA).
2. Tiap template yang porsinya ≥ PORSI_MIN dinilai AI (model fungsi 'judi' di /ai, gateway 9router): natural atau
   tidak + jenis + usulan tindakan. Pasangan domain+template yang sama tidak dinilai ulang selama JEDA_AI.
3. Hasil → RIWAYAT (jsonl); tidak natural & yakin ≥ YAKIN_NOTIF → Telegram tim server, SATU pesan per domain saat
   kejadian mulai + satu saat reda (tak ada lonjakan selama REDA). Template yang sudah ditolak WAF (≥ PORSI_DIBLOK
   status 403/406/410/429) atau ≥ PORSI_DIBLOK dari bot AI pencarian ber-IP resmi tidak dinilai/dinotifkan. Cache AI & kejadian aktif disimpan di NOTIF (tahan restart).
Tindakan (challenge/410 per template) belum dibuat: diputuskan sesudah masa uji deteksi (rencana 19 Okt 2026).
"""
import base64
import html
import json
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

import server_judi

AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_lonjakan_agent.py'
DIR = Path('/var/lib/velocity/server-lonjakan')
SETELAN = DIR / 'setelan.json'  # {server: {host: {aktif}}, kali, min_per_menit}
RIWAYAT = DIR / 'riwayat.jsonl'
NOTIF = DIR / 'notif.json'  # {ai: {host|domain|template: {t, ai}}, aktif: {host|domain: {mulai, terakhir, puncak, kali}}}
INTERVAL = 300
JEDA_AI = 3600
PORSI_MIN = 0.2
YAKIN_NOTIF = 70
REDA = 900
PORSI_DIBLOK = 0.9
STATUS_DIBLOK = ('403', '406', '410', '429')
JENIS = ('viral', 'crawler_sah', 'botnet', 'scraper', 'serangan', 'lainnya')
USULAN = ('tidak_ada', 'challenge', 'tolak_pola', 'aturan_waf', 'cek_manual')

SISTEM = """Anda analis trafik hosting WordPress Indonesia. Satu domain sedang mengalami lonjakan request.
Nilai apakah lonjakan pada SATU pola URL di bawah wajar (pengunjung asli: artikel viral, kampanye, crawler mesin pencari
resmi) atau tidak wajar (botnet, scraper, serangan, crawler liar).
Ciri tidak wajar: URL tidak masuk akal (mis. /artikel/page/1790/ — artikel tunggal tak punya halaman sebanyak itu),
ribuan IP masing-masing sedikit request, referer kosong atau sama dengan URL itu sendiri, UA browser berputar,
status 404/410 dominan, parameter acak. Ciri wajar: referer mesin pencari/sosmed, URL artikel nyata,
Googlebot/Bingbot resmi, sebaran sesuai jam.
Jawab HANYA JSON: {"natural": true|false, "yakin": 0-100, "jenis": "viral|crawler_sah|botnet|scraper|serangan|lainnya",
"usulan": "tidak_ada|challenge|tolak_pola|aturan_waf|cek_manual", "pola_regex": "regex REQUEST_FILENAME bila usulan tolak_pola/aturan_waf, selain itu kosong",
"alasan": "maks 2 kalimat bahasa Indonesia"}"""

_kunci = threading.Lock()
_keadaan = None  # isi NOTIF, dimuat sekali


def _muat():
    global _keadaan
    if _keadaan is None:
        try:
            _keadaan = json.loads(NOTIF.read_text())
        except (OSError, ValueError):
            _keadaan = {}
        _keadaan.setdefault('ai', {})
        _keadaan.setdefault('aktif', {})
    return _keadaan


def _simpan():
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = NOTIF.with_suffix('.tmp')
    tmp.write_text(json.dumps(_keadaan, ensure_ascii=False))
    tmp.replace(NOTIF)


def pasang(daftar_server, perintah_server, ssh_key_file, kirim_tg):
    global _daftar_server, _perintah_server, _ssh_key_file, _kirim_tg
    _daftar_server, _perintah_server, _ssh_key_file, _kirim_tg = daftar_server, perintah_server, ssh_key_file, kirim_tg


def setelan():
    try:
        s = json.loads(SETELAN.read_text())
    except (OSError, ValueError):
        s = {}
    return {'server': s.get('server') or {}, 'kali': float(s.get('kali') or 5), 'min_per_menit': float(s.get('min_per_menit') or 30)}


def _catat(baris):
    DIR.mkdir(parents=True, exist_ok=True)
    with _kunci, RIWAYAT.open('a') as f:
        f.write(json.dumps(baris, ensure_ascii=False, separators=(',', ':')) + '\n')


def _agen(srv, key, perintah):
    cmd = _perintah_server(srv, key, 'command -v python3 >/dev/null && exec nice -n 15 ionice -c3 python3 - || exec /usr/libexec/platform-python -')
    sandi = base64.b64encode(json.dumps(perintah).encode()).decode()
    try:
        r = subprocess.run(cmd, input=f"{AGEN.read_text()}\njalankan('{sandi}')\n", capture_output=True, text=True,
                           timeout=240, check=False)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'timeout'}
    try:
        return json.loads((r.stdout or '').strip().splitlines()[-1])
    except (ValueError, IndexError):
        pesan = (r.stderr or '').strip().splitlines()
        return {'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}


def nilai_ai(l, t):
    m = server_judi.model_ai()
    bukti = json.dumps({'domain': l['domain'], 'request_per_menit': l['per_menit'], 'baseline_per_menit': l['baseline'],
                        'kali_normal': l['kali'], 'ip_unik_domain': l['ip_unik'], 'pola': t}, ensure_ascii=False)
    badan = json.dumps({'model': m['model'], 'temperature': 0, 'max_tokens': 800,
                        'messages': [{'role': 'system', 'content': SISTEM}, {'role': 'user', 'content': bukti}]}).encode()
    req = urllib.request.Request(f"{m['endpoint']}/chat/completions", data=badan, headers={
        'Content-Type': 'application/json', 'Authorization': f"Bearer {m['api_key']}", 'User-Agent': 'Mozilla/5.0 VelocityDashboard/1.0'})
    with urllib.request.urlopen(req, timeout=120) as r:
        j = json.loads(r.read())
    d = server_judi._urai_json(j['choices'][0]['message'].get('content'))
    return {'natural': bool(d.get('natural')), 'yakin': max(0, min(100, int(d.get('yakin') or 0))),
            'jenis': d.get('jenis') if d.get('jenis') in JENIS else 'lainnya',
            'usulan': d.get('usulan') if d.get('usulan') in USULAN else 'cek_manual',
            'pola_regex': str(d.get('pola_regex') or '')[:200], 'alasan': str(d.get('alasan') or '')[:300], 'model': m['model']}


def _notif(srv, l, pola):
    """Satu pesan per domain: semua template tidak natural pada kejadian yang baru mulai."""
    e = html.escape
    teks = (f"🚨 <b>VelocityGuard · Lonjakan tidak natural</b> (pemantau lonjakan: tanpa tindakan otomatis, WAF tetap jalan)\n"
            f"Server: {e(srv['name'])} · <b>{e(l['domain'])}</b>\n"
            f"{l['per_menit']}/mnt (normal {l['baseline']}/mnt, {l['kali']}×) · {l['ip_unik']} IP")
    for t, ai in pola:
        teks += (f"\n\n• <code>{e(t['template'])}</code> — {t['hit']} hit, {t['ip_unik']} IP, maks {t['maks_per_ip']}/IP\n"
                 f"AI: {e(ai['jenis'])} (yakin {ai['yakin']}) → usulan <b>{e(ai['usulan'])}</b>\n{e(ai['alasan'])}"
                 + (f"\nRegex: <code>{e(ai['pola_regex'])}</code>" if ai['pola_regex'] else ''))
    _kirim_tg(teks + "\n\nNotif berikutnya untuk domain ini hanya saat reda.")


def _diblok(t):
    status = t.get('status') or {}
    return sum(status.get(k, 0) for k in STATUS_DIBLOK) >= PORSI_DIBLOK * max(sum(status.values()), 1)


def periksa_server(srv, key, s):
    h = _agen(srv, key, {'aksi': 'periksa', 'kali': s['kali'], 'min_per_menit': s['min_per_menit']})
    if not h.get('ok'):
        _catat({'t': int(time.time()), 'host': srv['host'], 'server': srv['name'], 'error': h.get('error'), 'pesan': h.get('pesan')})
        return h
    kini = time.time()
    k_ai, aktif = _muat()['ai'], _keadaan['aktif']
    for l in h.get('lonjakan') or []:
        pola = []
        for t in l['template']:
            # bot AI pencarian terverifikasi IP (PerplexityBot dsb.) = crawler sah; AI sempat menilainya scraper (menararakyat 21 Okt)
            if t['porsi'] < PORSI_MIN or _diblok(t) or t.get('bot_ai_resmi', 0) >= PORSI_DIBLOK * t['hit']:
                continue
            k = f"{srv['host']}|{l['domain']}|{t['template']}"
            ai, simpan = None, k_ai.get(k)
            if not simpan or kini - simpan['t'] >= JEDA_AI:
                try:
                    ai = nilai_ai(l, t)
                except Exception as e:  # noqa: BLE001
                    ai = {'error': str(e)[:200]}
                k_ai[k] = {'t': kini, 'ai': ai}
            _catat({'t': int(kini), 'host': srv['host'], 'server': srv['name'], 'domain': l['domain'], 'per_menit': l['per_menit'],
                    'baseline': l['baseline'], 'kali': l['kali'], 'ip_unik': l['ip_unik'], 'pola': t, 'ai': ai})
            ai = ai or simpan['ai']
            if ai and not ai.get('error') and not ai['natural'] and ai['yakin'] >= YAKIN_NOTIF:
                pola.append((t, ai))
        if not pola:
            continue
        kd = f"{srv['host']}|{l['domain']}"
        if kd not in aktif:
            _notif(srv, l, pola)
            aktif[kd] = {'mulai': kini, 'puncak': 0}
        aktif[kd]['terakhir'] = kini
        aktif[kd]['puncak'] = max(aktif[kd]['puncak'], l['per_menit'])
    for kd in [kd for kd in aktif if kd.startswith(srv['host'] + '|') and kini - aktif[kd]['terakhir'] >= REDA]:
        a = aktif.pop(kd)
        _kirim_tg(f"✅ <b>VelocityGuard · Lonjakan reda</b>\nServer: {html.escape(srv['name'])} · <b>{html.escape(kd.split('|', 1)[1])}</b>\n"
                  f"Berlangsung ±{round((a['terakhir'] - a['mulai']) / 60)} mnt, puncak {a['puncak']}/mnt.")
    for k in [k for k, v in k_ai.items() if kini - v['t'] >= JEDA_AI]:  # cache basi dibuang agar berkas tak membengkak
        del k_ai[k]
    _simpan()
    return h


def jalan():
    """Thread installer_status: tiap INTERVAL, periksa semua server yang aktif di setelan."""
    while True:
        mulai = time.time()
        try:
            s = setelan()
            key = _ssh_key_file()
            for srv in _daftar_server():
                if key and (s['server'].get(srv['host']) or {}).get('aktif'):
                    periksa_server(srv, key, s)
        except Exception as e:  # noqa: BLE001
            print(f'lonjakan: {e}')
        time.sleep(max(30, INTERVAL - (time.time() - mulai)))


def riwayat(host='', batas=200):
    try:
        baris = RIWAYAT.read_text().splitlines()[-5000:]
    except OSError:
        baris = []
    out = []
    for b in reversed(baris):
        try:
            x = json.loads(b)
        except ValueError:
            continue
        if not host or x.get('host') == host:
            out.append(x)
            if len(out) >= batas:
                break
    return {'setelan': setelan(), 'riwayat': out}
