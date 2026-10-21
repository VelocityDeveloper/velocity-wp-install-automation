# -*- coding: utf-8 -*-
"""VelocityGuard — pencari celah harian (dijalankan di server lewat `ssh ... python3 -`, HANYA BACA).

Mencari request yang LOLOS VelocityGuard dalam 24 jam terakhir, sebagai bahan aturan baru:
- probe_lolos: path rawan (.env, .git, cadangan wp-config, phpunit, shell terkenal, dump SQL…) dijawab 2xx;
- post_php: POST berstatus 2xx ke berkas .php di luar titik masuk WordPress normal (indikasi webshell/backdoor);
- pemindai: IP dengan banyak 404 berbeda di beberapa domain yang tidak diblokir WAF (scanner baru);
- bot_baru: UA bot/klien skrip bervolume tinggi yang lolos (tidak cocok daftar bot Velocity WAF);
- php_baru: berkas PHP baru/diubah di uploads & cache WordPress;
- uji: catatan unit uji tanpa cPGuard (/root/vwaf-uji2j/pantau.txt): CPU tinggi & pemulihan.
Sumber: /var/log/httpd/domains/<domain>.log (format combined DirectAdmin). Harus jalan di Python 3.6.
Pemanggil menambahkan `jalankan(<base64 JSON>)`, aksi: celah {jam: 24}.
"""
import base64
import glob
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime

LOG_DIR = '/var/log/httpd/domains'
WAF_DIR = '/etc/velocity-waf'
PANTAU = '/root/vwaf-uji2j/pantau.txt'
BARIS = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+)[^"]*" (\d{3}) (\S+) "[^"]*" "([^"]*)"')
PROBE = re.compile(r'(?i)(/\.env|/\.git/|/\.svn/|/\.aws/|/\.ssh/|wp-config\.(php)?[._~-]?(bak|old|orig|save|txt|swp|zip)|'
                   r'wp-config\.php~|/phpunit/|eval-stdin\.php|/vendor/.+\.php|/(alfa|wso|c99|r57|b374k|marijuana|leaf)[\w-]*\.php|'
                   r'\.(sql|sql\.gz|bak|tar\.gz|tgz|zip|rar|7z)$|/phpinfo\.php|/info\.php|/adminer[\w.-]*\.php|/debug\.log$|'
                   r'/server-status|/cgi-bin/.+|/_profiler|/actuator/|/\.DS_Store|/config\.json$|/sftp-config\.json)')
# Titik masuk PHP normal WordPress (POST 2xx ke sini wajar)
POST_WAJAR = re.compile(r'(?i)^(/[^?]*)?/(index\.php|wp-login\.php|xmlrpc\.php|wp-cron\.php|wp-comments-post\.php|wp-trackback\.php|'
                        r'wp-signup\.php|wp-activate\.php|wp-admin/.*|wp-content/plugins/litespeed-cache/guest\.vary\.php)$')


def _post_wajar(path):
    # Titik masuk WP di subfolder (/staging/wp-cron.php) wajar, tapi tidak bila di bawah wp-content (folder buatan penyerang)
    rendah = path.lower()
    return bool(POST_WAJAR.match(path)) and ('/wp-content/' not in rendah or rendah.endswith('/litespeed-cache/guest.vary.php'))


BOT_UA = re.compile(r'(?i)(bot|crawl|spider|scan|python|curl|wget|go-http|java/|okhttp|httpclient|libwww|scrapy|headless|axios|node-fetch|php/|ruby|perl)')
UA_BAIK = re.compile(r'(?i)(googlebot|google-|bingbot|applebot|duckduckbot|yandex|facebookexternalhit|facebookcatalog|twitterbot|'
                     r'meta-webindexer|whatsapp|telegrambot|linkedinbot|slackbot|discordbot|tiktok|pinterest|velocity|wp-fastest-cache|wordpress/|'
                     r'jetpack|uptimerobot|lighthouse|chrome-lighthouse|feedfetcher|mediapartners|adsbot)')


def _daftar_bot():
    pola = []
    for f in ('bot-jahat.txt', 'bot-seo.txt', 'bot-ai.txt', 'bot-ai-pencarian.txt', 'klien-skrip.txt'):
        try:
            with open(os.path.join(WAF_DIR, f), encoding='utf-8', errors='replace') as h:
                pola += [b.strip().lower() for b in h if b.strip() and not b.startswith('#')]
        except OSError:
            pass
    return pola


def _waktu(s):
    try:
        return datetime.strptime(s[:20], '%d/%b/%Y:%H:%M:%S').timestamp()
    except ValueError:
        return 0


def _baca_log(sejak):
    probe, post_php, n404, ua = [], [], defaultdict(lambda: [set(), set()]), Counter()
    ua_lolos = Counter()
    total = 0
    for f in glob.glob(os.path.join(LOG_DIR, '*.log')):
        if f.endswith('.error.log') or os.path.getmtime(f) < sejak:
            continue
        domain = os.path.basename(f)[:-4]
        try:
            h = open(f, encoding='utf-8', errors='replace')
        except OSError:
            continue
        with h:
            # Log domain bisa memuat beberapa hari: lompati awal berkas besar (baris diurutkan waktu)
            ukuran = os.path.getsize(f)
            if ukuran > 64 << 20:
                h.seek(ukuran - (64 << 20))
                h.readline()
            for b in h:
                m = BARIS.match(b)
                if not m:
                    continue
                ip, tw, metode, uri, kode, ukuran_b, agen = m.groups()
                t = _waktu(tw)
                if t < sejak:
                    continue
                total += 1
                path = uri.split('?', 1)[0]
                lolos = kode[0] == '2'
                if lolos and PROBE.search(path):
                    probe.append((t, domain, ip, metode, uri[:200], kode, agen[:150], ukuran_b))
                if lolos and metode == 'POST' and path.lower().endswith('.php') and not _post_wajar(path):
                    post_php.append((t, domain, ip, uri[:200], kode, agen[:150]))
                if kode == '404':
                    s = n404[ip]
                    if len(s[0]) < 500:
                        s[0].add(path[:120])
                    s[1].add(domain)
                if lolos and BOT_UA.search(agen) and not UA_BAIK.search(agen):
                    ua_lolos[agen[:200]] += 1
    return total, probe, post_php, n404, ua_lolos


def _cache_aman(p):
    # Berkas cache plugin (wonder-cache dll.) diawali "<?php exit; ?>" = data serial, bukan kode
    try:
        with open(p, 'rb') as h:
            return h.read(16).startswith(b'<?php exit; ?>')
    except OSError:
        return False


def _php_baru(sejak):
    out = []
    for akar in glob.glob('/home/*/domains/*/public_html/wp-content'):
        for sub in ('uploads', 'cache'):
            d = os.path.join(akar, sub)
            for dirpath, dirs, files in os.walk(d):
                if '/uploads/aios' in dirpath:
                    continue
                for n in files:
                    if not re.search(r'(?i)\.(php\d?|phtml|phar|pht)$', n):
                        continue
                    p = os.path.join(dirpath, n)
                    try:
                        st = os.lstat(p)
                    except OSError:
                        continue
                    if st.st_mtime >= sejak and not (n == 'index.php' and st.st_size <= 64) and not _cache_aman(p):
                        out.append((p, int(st.st_mtime), st.st_size))
                        if len(out) >= 200:
                            return out
    return out


def _pantau():  # baris pantau.txt hanya berjam (tanpa tanggal) → ambil 50 kejadian terakhir
    out = []
    try:
        with open(PANTAU, encoding='utf-8', errors='replace') as h:
            for b in h:
                if 'PULIH' in b or 'JAGA' in b or 'CPU tinggi' in b:
                    out.append(b.strip()[:300])
    except OSError:
        return None
    return out[-50:]


def celah(p):
    jam = int(p.get('jam') or 24)
    sejak = time.time() - jam * 3600
    try:
        os.nice(15)
    except OSError:
        pass
    total, probe, post_php, n404, ua_lolos = _baca_log(sejak)
    bot = _daftar_bot()
    pemindai = sorted(((ip, len(s[0]), len(s[1]), sorted(s[0])[:15]) for ip, s in n404.items()
                       if len(s[0]) >= 30 and len(s[1]) >= 2), key=lambda x: -x[1])[:20]
    bot_baru = [(u, n) for u, n in ua_lolos.most_common(60) if n >= 300 and not any(x in u.lower() for x in bot)][:15]
    return {
        'ok': True, 'jam': jam, 'request': total,
        'probe_lolos': sorted(probe, reverse=True)[:60], 'n_probe_lolos': len(probe),
        'post_php': sorted(post_php, reverse=True)[:60], 'n_post_php': len(post_php),
        'pemindai': pemindai, 'bot_baru': bot_baru,
        'php_baru': _php_baru(sejak), 'uji': _pantau(),
        'cpguard_waf_off': os.path.exists('/etc/modsecurity.d/cpguard_waf.conf.off'),
    }


AKSI = {'celah': celah}


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
