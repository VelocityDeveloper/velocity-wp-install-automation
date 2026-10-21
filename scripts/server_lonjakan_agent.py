#!/usr/bin/env python3
"""Agen deteksi lonjakan request per domain (VelocityGuard) — dijalankan dashboard lewat `ssh … python3 -` tiap 5 menit.

HANYA BACA access log; satu-satunya yang ditulis = berkas keadaan STATE (offset log + baseline per domain).
Alur `periksa`:
1. Baca tiap /var/log/httpd/domains/<domain>.log sejak offset terakhir (maks BACA_MAKS per berkas per putaran).
2. Request dinamis (bukan aset statis) per menit dibanding baseline EWMA domain itu. Lonjakan = ≥ `kali` × baseline
   dan ≥ `min_per_menit`, sesudah baseline cukup putaran (PEMANASAN). Selama lonjakan baseline tidak ikut naik
   (agar serangan panjang tak menjadi "normal"), kecuali pelan sekali.
3. Domain yang melonjak: request dikelompokkan per template URL (/{n}/{n}/{n}/{slug}/page/{n}/) + ciri tiap template
   (IP unik, maks per IP, status, referer, UA, contoh URL) → dikirim balik untuk dinilai AI di dashboard.
Python 3.6 (CloudLinux 8/9 platform-python).
"""
import base64
import ipaddress
import json
import os
import re
import time
from collections import Counter, defaultdict

LOG_DIR = '/var/log/httpd/domains'
STATE = '/var/lib/velocity-lonjakan/state.json'
BACA_MAKS = 30 * 1024 * 1024
PEMANASAN = 6  # putaran (±30 mnt) sebelum domain boleh dinilai
EWMA_DETIK = 3 * 3600
TEMPLATE_MAKS = 5
RE_BARIS = re.compile(r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) \S+ "([^"]*)" "([^"]*)"')
RE_STATIS = re.compile(r'\.(?:css|js|mjs|map|png|jpe?g|gif|webp|avif|svg|ico|bmp|woff2?|ttf|otf|eot|mp4|webm|mp3|pdf|zip)$', re.I)
RE_BOT_SAH = re.compile(r'googlebot|bingbot|applebot|duckduckbot|yandexbot', re.I)
WAF_DIR = '/etc/velocity-waf'  # daftar resmi bot AI pencarian dari VelocityGuard WAF (aturan 7700104/7700106)


def _baris(nama):
    try:
        with open(os.path.join(WAF_DIR, nama)) as f:
            return [b.split('#', 1)[0].strip().lower() for b in f if b.split('#', 1)[0].strip()]
    except OSError:
        return []


AI_UA = _baris('bot-ai-pencarian.txt')
AI_NET = []
for _b in _baris('ip-ai-pencarian.txt'):
    try:
        AI_NET.append(ipaddress.ip_network(_b, strict=False))
    except ValueError:
        pass
_ip_resmi = {}


def bot_ai_resmi(ip, ua):
    """UA bot AI pencarian (PerplexityBot, OAI-SearchBot…) DAN IP di daftar resmi pemiliknya = crawler sah, bukan scraper."""
    ua = ua.lower()
    if not any(u in ua for u in AI_UA):
        return False
    if ip not in _ip_resmi:
        try:
            a = ipaddress.ip_address(ip)
            _ip_resmi[ip] = any(a in n for n in AI_NET)
        except ValueError:
            _ip_resmi[ip] = False
    return _ip_resmi[ip]


def template(url):
    """URL → pola: angka → {n}, slug panjang → {slug}, nilai query dibuang (nama parameter tetap)."""
    jalur, _, query = url.partition('?')
    bagian = []
    for s in jalur.split('/'):
        if len(s) > 30 or (len(s) > 15 and '-' in s):
            bagian.append('{slug}')
        elif re.fullmatch(r'[0-9a-f]{16,}', s):
            bagian.append('{id}')
        else:
            bagian.append(re.sub(r'\d+', '{n}', s))
    t = '/'.join(bagian)
    if query:
        t += '?' + '&'.join(sorted({k.split('=', 1)[0] for k in query.split('&') if k}))[:80]
    return t[:160]


def baca_baru(path, pos_lama):
    """Teks baru sejak offset; berkas dirotasi/terpotong → mulai dari awal. Hasil: (baris, offset_baru, terpotong)."""
    st = os.stat(path)
    ino, ukuran = st.st_ino, st.st_size
    pos = pos_lama[1] if pos_lama and pos_lama[0] == ino and pos_lama[1] <= ukuran else 0
    terpotong = ukuran - pos > BACA_MAKS
    if terpotong:
        pos = ukuran - BACA_MAKS
    with open(path, 'rb') as f:
        f.seek(pos)
        data = f.read(ukuran - pos)
    if terpotong:  # buang baris pertama yang terpotong
        data = data.split(b'\n', 1)[-1]
    return data.decode('utf-8', 'replace').splitlines(), [ino, ukuran], terpotong


def ciri(domain, req):
    """req: [(ip, metode, url, status, referer, ua)] satu domain → ringkasan + template teratas."""
    per_t = defaultdict(list)
    for r in req:
        per_t[template(r[2])].append(r)
    hasil = []
    for t, rs in sorted(per_t.items(), key=lambda x: -len(x[1]))[:TEMPLATE_MAKS]:
        ip = Counter(r[0] for r in rs)
        ref = Counter('kosong' if r[4] in ('', '-') else 'sendiri' if domain in r[4] else
                      'mesin_pencari' if re.search(r'google\.|bing\.|yahoo\.|duckduckgo', r[4]) else
                      'sosmed' if re.search(r'facebook|instagram|t\.co/|twitter|tiktok|whatsapp|telegram', r[4]) else 'luar'
                      for r in rs)
        # referer = URL itu sendiri → ciri bot (browser asli tak merujuk dirinya)
        ref_diri = sum(1 for r in rs if r[4].endswith(r[2]) and r[2] != '/')
        hasil.append({
            'template': t, 'hit': len(rs), 'porsi': round(len(rs) / len(req), 3),
            'ip_unik': len(ip), 'maks_per_ip': ip.most_common(1)[0][1], 'ip_teratas': ip.most_common(3),
            'status': dict(Counter(r[3] for r in rs).most_common(6)), 'metode': dict(Counter(r[1] for r in rs).most_common(3)),
            'referer': dict(ref), 'referer_diri': ref_diri, 'url_unik': len({r[2] for r in rs}),
            'ua_unik': len({r[5] for r in rs}), 'ua_teratas': [[u[:110], n] for u, n in Counter(r[5] for r in rs).most_common(4)],
            'bot_sah': sum(1 for r in rs if RE_BOT_SAH.search(r[5])),
            'bot_ai_resmi': sum(1 for r in rs if bot_ai_resmi(r[0], r[5])),
            'contoh': [u[:200] for u in list(dict.fromkeys(r[2] for r in rs))[:6]],
        })
    return hasil


def periksa(p):
    kali, minimum = float(p.get('kali') or 5), float(p.get('min_per_menit') or 30)
    try:
        with open(STATE) as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    kini = time.time()
    dt = kini - st.get('t', 0)
    pertama = not st.get('t') or dt > 3600  # keadaan basi (agen lama mati) → hanya pasang offset
    offset, base = st.get('offset', {}), st.get('base', {})
    offset_baru, lonjakan, terpotong = {}, [], []
    for nama in os.listdir(LOG_DIR):
        if not nama.endswith('.log') or nama.endswith(('.error.log', '.bytes.log')):
            continue
        path = os.path.join(LOG_DIR, nama)
        domain = nama[:-4]
        try:
            if pertama:
                s = os.stat(path)
                offset_baru[nama] = [s.st_ino, s.st_size]
                continue
            baris, offset_baru[nama], potong = baca_baru(path, offset.get(nama))
        except OSError:
            continue
        if potong:
            terpotong.append(domain)
        req = []
        for b in baris:
            m = RE_BARIS.match(b)
            if m and not RE_STATIS.search(m.group(3).split('?', 1)[0]):
                req.append((m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)))
        r = len(req) / (dt / 60)
        b = base.get(domain) or {'m': r, 'n': 0}
        melonjak = b['n'] >= PEMANASAN and r >= minimum and r >= kali * max(b['m'], 1)
        a = min(1.0, dt / EWMA_DETIK) * (0.05 if melonjak else 1)
        base[domain] = {'m': round(b['m'] + a * (r - b['m']), 3), 'n': b['n'] + 1}
        if melonjak:
            lonjakan.append({'domain': domain, 'per_menit': round(r, 1), 'baseline': round(b['m'], 1),
                             'kali': round(r / max(b['m'], 1), 1), 'total': len(req), 'detik': int(dt),
                             'ip_unik': len({x[0] for x in req}), 'template': ciri(domain, req)})
    # domain yang lognya hilang (akun dihapus) ikut dibuang dari keadaan
    base = {d: v for d, v in base.items() if d + '.log' in offset_baru}
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump({'t': kini, 'offset': offset_baru, 'base': base}, f)
    os.replace(tmp, STATE)
    return {'ok': True, 'pertama': pertama, 'domain': len(offset_baru), 'detik': int(dt),
            'lonjakan': sorted(lonjakan, key=lambda x: -x['per_menit']), 'terpotong': terpotong}


AKSI = {'periksa': periksa}


def jalankan(kode):
    p = json.loads(base64.b64decode(kode).decode())
    fungsi = AKSI.get(p.get('aksi'))
    if not fungsi:
        hasil = {'ok': False, 'error': 'aksi_tidak_dikenal'}
    else:
        try:
            hasil = fungsi(p)
        except Exception as e:
            hasil = {'ok': False, 'error': 'galat', 'pesan': str(e)[:300]}
    print(json.dumps(hasil))
