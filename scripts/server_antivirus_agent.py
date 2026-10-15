# -*- coding: utf-8 -*-
"""Antivirus satu server hosting (dijalankan di server lewat `ssh ... python3 -`).

Dipakai halaman Server > Antivirus (installer_status.py → /api/servers/antivirus*). Pemanggil menambahkan
satu baris `jalankan(<perintah base64 JSON>)` di akhir kode ini. Mencetak satu objek JSON di baris
terakhir; aksi scan juga mencetak baris kemajuan `P {json}` selama berjalan.
Harus tetap jalan di Python 3.6 (CloudLinux 8 platform-python). Tidak memasang apa pun di server.

Aksi:
- ringkas (baca): deteksi cPGuard 30 hari dari /opt/cpguard/app/data/scanner.db (pembanding selama
  cPGuard masih jalan), daftar akun DirectAdmin, isi karantina Velocity.
- scan (baca): pindai berkas akun dengan tanda tangan VD.* di bawah (regex, Python murni). Hanya melapor.
- karantina: pindahkan satu berkas ke KARANTINA/<id>/ + meta.json (pemilik, izin, waktu, sha256).
- kembalikan: pulihkan berkas karantina ke lokasi asal (pemilik & izin semula); gagal bila lokasi terisi.
- hapus: hapus permanen satu entri karantina.
- baca (baca): isi satu berkas di /home (path) atau salinan karantina (id), maks MAKS_LIHAT byte + sha256 utuh.
- scan menerima 'aman' {path: sha256}: berkas yang ditandai aman dari dashboard dilewati selama isinya sama.
"""
import base64
import hashlib
import json
import os
import pwd
import re
import shutil
import sqlite3
import subprocess
import sys
import time

KARANTINA = '/root/velocity-karantina'
HOME = '/home'
CPG_DB = '/opt/cpguard/app/data/scanner.db'
MAKS_BACA = 3 * 1024 * 1024
MAKS_TEMUAN = 3000
EKSTENSI = {'php', 'php3', 'php4', 'php5', 'php7', 'php8', 'phtml', 'pht', 'phar', 'inc', 'suspected',
            'html', 'htm', 'js', 'txt', 'htaccess', 'ico', 'png', 'jpg', 'jpeg', 'gif'}
GAMBAR = {'ico', 'png', 'jpg', 'jpeg', 'gif'}
PHP = {'php', 'php3', 'php4', 'php5', 'php7', 'php8', 'phtml', 'pht', 'phar', 'inc', 'suspected'}
# Halaman judi untuk cloaking sering disimpan sebagai .txt lalu di-include/readfile
TEKS_JUDI = PHP | {'html', 'htm', 'txt'}
# Folder yang tidak dipindai (surat, cadangan, statistik, cache paket)
LEWATI = {'Maildir', 'imap', 'backups', '.trash', '.cagefs', '.cache', '.npm', '.composer', '.git', 'node_modules',
          'logs', 'stats', '.softaculous', 'awstats', '.cl.selector', 'lscache'}


def r(pola, bendera=re.I):
    return re.compile(pola.encode(), bendera)


# Tanda tangan: (id, nama, tingkat, ekstensi ('php'|'web'|'semua'|set), fungsi(teks, path) → potongan|None).
# tingkat 'virus' = keyakinan tinggi; 'curiga' = perlu dilihat manusia (bisa positif palsu).
RE_EVAL_DEKODE = r(r'\b(?:eval|assert)\s*\(\s*(?:@\s*)?(?:base64_decode|gzinflate|gzuncompress|gzdecode|str_rot13|strrev|hex2bin|rawurldecode|convert_uudecode)\s*\(')
RE_EVAL_INPUT = r(r'\b(?:eval|assert|system|passthru|shell_exec|popen|proc_open|create_function)\s*\(\s*(?:@\s*)?(?:stripslashes\s*\(\s*|base64_decode\s*\(\s*|urldecode\s*\(\s*|trim\s*\(\s*)?\$_(?:POST|GET|REQUEST|COOKIE|SERVER\s*\[\s*[\'"]HTTP_)')
RE_SHELL = r(r'FilesMan|b374k|c99shell|r57shell|IndoXploit|AnonymousFox|ALFA_DATA|\bWSOsetcookie\b|FoxAuto|0x1949|Mini\s*Shell\s*\d|BlackDragon|<title>\s*Gecko\s*\[', 0)
RE_EKSEKUSI = r(r'\b(?:system|shell_exec|passthru|proc_open|popen|exec|eval|move_uploaded_file)\s*\(')
RE_SUPERGLOBAL = r(r'\$_(?:POST|GET|REQUEST|FILES|COOKIE)\b')
RE_HACKED = r(r'<title>[^<]{0,60}hack(?:ed|3d)\s*by')
RE_LOCALE = r(r'wp-locale-perf|Locale Performance Cache|wp-cachepress|craft-harvester-jet|widget-compat-helper|wp_locale_cache_\w+|locale-cache-(?:db|oc)\b|Anti-DB-wipe MU loader')
# Botnet backlink "WP-LinkHelper" (folder wlh-*/class-wlh-*.php, panel cachelayer.top), dari karantina cPGuard Fahmi 14 Okt 2026
RE_WLH = r(r'\bclass\s+WLH_\w+|\bWLH_(?:REMOTE_URL|HANDSHAKE|OPT_LINKS)\b|WP-LinkHelper', 0)
# Payload dipecah jadi array potongan base64 pendek lalu di-eval (wp-config-sample.php sisipan)
RE_ARRAY_B64 = r(r'array\s*\(\s*(?:[\'"][A-Za-z0-9+/=]{16,64}[\'"]\s*,\s*){30,}')
RE_ROT13_URL = r(r'str_rot13\s*\(\s*[\'"]uggcf?://')
RE_CHR_RANTAI = r(r'(?:chr\s*\(\s*\d+\s*\)\s*\.\s*){24,}')
RE_EVAL_VAR = r(r'\b(?:eval|assert)\s*\(\s*(?:@\s*)?\$\w+\s*\)')
RE_AMBIL_URL = r(r'curl_exec\s*\(|file_get_contents\s*\(\s*[\'"]https?://|fsockopen\s*\(')
RE_GOTO = r(r'\bgoto\s+\w+\s*;')
RE_PANJANG = r(rb'[A-Za-z0-9+/=]{3000,}'.decode())
RE_DEKODE = r(r'base64_decode|gzinflate|gzuncompress|str_rot13|strrev\s*\(')
RE_FUNGSI_STR = r(r'\$\w+\s*=\s*[\'"](?:base64_decode|str_rot13|gzinflate|gzuncompress|create_function|shell_exec|passthru)[\'"]\s*;')
RE_HEX = r(r'\\x[0-9a-f]{2}')
RE_EVAL_APA = r(r'\b(?:eval|assert|create_function)\s*\(|\$GLOBALS\s*\[')
RE_PREPEND = r(r'^\s*php_value\s+auto_(?:prepend|append)_file\s+\S+', re.I | re.M)
RE_HANDLER = r(r'(?:AddType|AddHandler)\s+application/x-httpd-(?:php|ea-php|lsphp|alt-php)\S*\s+.*\.(?:jpe?g|png|gif|ico|txt|css)\b|SetHandler\s+application/x-httpd-php', re.I)
RE_UPLOAD = r(r'move_uploaded_file\s*\(\s*\$_FILES')
RE_JUDI = r(r'slot\s*gacor|situs\s*(?:slot|judi|toto|togel)|togel\s*(?:online|hari\s*ini)|judi\s*(?:online|slot|bola)|maxwin|scatter\s*hitam'
             r'|rtp\s*(?:live|slot)|bandar\s*(?:togel|slot|judi)|slot\s*(?:thailand|online|88|777|demo|dana|pulsa|zeus)'
             r'|toto\s*(?:togel|macau|slot)|sbobet|pragmatic\s*play|mahjong\s*ways|bocoran\s*(?:slot|rtp)|link\s*alternatif'
             r'|bonus\s*new\s*member|deposit\s*pulsa|depo\s*\d+\s*k\b|pola\s*gacor|agen\s*(?:slot|judi|togel)|daftar\s*slot'
             r'|[ck]asino\s*online|poker\s*online|sabung\s*ayam|pkv\s*games')
GERBANG_JUDI = (b'slot', b'togel', b'judi', b'maxwin', b'toto', b'rtp', b'sbobet', b'casino', b'kasino', b'scatter',
                b'pragmatic', b'mahjong', b'gacor', b'poker', b'sabung', b'pkv')
# Judi online: teks disembunyikan dari pengunjung (link backlink untuk Google)
RE_SEMBUNYI = r(r'display\s*:\s*none|visibility\s*:\s*hidden|(?:left|top|text-indent)\s*:\s*-\d{3,}\s*px|font-size\s*:\s*0(?:px)?\s*[;"\']')
RE_LINK = r(r'<a\s[^>]*href')
# Cloaking: Googlebot diberi halaman judi, pengunjung biasa halaman asli
RE_UA = r(r'HTTP_USER_AGENT')
RE_REFERER = r(r'HTTP_REFERER')
RE_BOT = r(r'googlebot|google-inspectiontool|bingbot|slurp|yandex|\bbot\b|crawl|spider')
RE_MESIN_CARI = r(r'\bgoogle\b|\bbing\b|yahoo|yandex')
RE_KELUARKAN = r(r'(?:echo|print)\s*\(?\s*(?:@\s*)?(?:file_get_contents|curl_exec)\s*\(|\breadfile\s*\('
                 r'|\b(?:include|require)(?:_once)?\s*\(?\s*[\'"][^\'"]+\.(?:txt|html?|jpe?g|png|gif|ico|css)[\'"]')
RE_ECHO_VAR = r(r'\b(?:echo|print)\s*\(?\s*\$\w+')
RE_ALIH = r(r'header\s*\(\s*[\'"]Location\s*:\s*https?://')
# .htaccess: RewriteCond UA/referer mesin pencari lalu RewriteRule (bukan blokir [F]/[G]/-)
RE_HT_CLOAK = r(r'RewriteCond\s+%\{HTTP_(?:USER_AGENT|REFERER)\}\s+[^!\s][^\n]*(?:google|bing|yahoo|bot)[^\n]*\n'
                r'(?:[ \t]*RewriteCond[^\n]*\n)*[ \t]*RewriteRule\s+\S+\s+(\S+)([^\n]*)')
RE_AUTH = r(r'wp_set_auth_cookie')
RE_ADMIN_PAKSA = r(r'wp_set_current_user')
RE_INPUT = r(r'\$_(?:GET|REQUEST|COOKIE)\s*\[')
RE_WPLOAD = r(r'wp-load\.php')
# Berkas gambar biner: hanya penanda panjang ("<?=" 3 byte bisa muncul acak di JPEG)
RE_PHP_TAG = r(r'<\?php\s|eval\s*\(\s*\$|base64_decode\s*\(|<script\s+language\s*=\s*[\'"]?php', re.I)
RE_JS_CHAR = r(r'String\.fromCharCode\(\s*(?:\d+\s*,\s*){40,}')
RE_JS_SUNTIK = r(r'document\.write|createElement\s*\(\s*[\'"]script|\.src\s*=')


def potong(teks, m, lebar=90):
    a = max(0, m.start() - 30)
    return teks[a:a + lebar].decode('utf-8', 'replace').replace('\n', ' ').replace('\r', ' ').strip()


def cari(pola):
    def f(teks, path):
        m = pola.search(teks)
        return potong(teks, m) if m else None
    return f


def webshell(teks, path):
    # Nama webshell juga muncul di daftar blokir plugin keamanan → wajib ada eksekusi + input pengunjung
    m = RE_SHELL.search(teks)
    return potong(teks, m) if m and RE_EKSEKUSI.search(teks) and RE_SUPERGLOBAL.search(teks) else None


def eval_ambil_url(teks, path):
    m = RE_EVAL_VAR.search(teks)
    return potong(teks, m) if m and RE_AMBIL_URL.search(teks) else None


def goto_samar(teks, path):
    n = len(RE_GOTO.findall(teks))
    return '%d pernyataan goto (kode disamarkan)' % n if n >= 60 else None


def kode_panjang(teks, path):
    if not (RE_EVAL_VAR.search(teks) or RE_FUNGSI_STR.search(teks) or b'eval' in teks):
        return None
    m = RE_PANJANG.search(teks)
    if m and RE_DEKODE.search(teks):
        return 'string terkode %d karakter + fungsi dekode' % (m.end() - m.start())
    return None


def hex_samar(teks, path):
    # Inti WP (SimplePie, html5 entities) penuh \x tapi tanpa eval/GLOBALS → bukan samaran
    if not (RE_EVAL_APA.search(teks) or RE_FUNGSI_STR.search(teks)):
        return None
    n = len(RE_HEX.findall(teks))
    return '%d escape \\x (kode disamarkan)' % n if n >= 400 and len(teks) < 400000 else None


def auth_paksa(teks, path):
    if RE_AUTH.search(teks) and RE_ADMIN_PAKSA.search(teks) and RE_INPUT.search(teks) and RE_WPLOAD.search(teks):
        m = RE_AUTH.search(teks)
        return potong(teks, m)
    return None


# PHP sah di uploads: AIOS firewall, log Wordfence, cache WP-Optimize, WPForms, Elementor
UPLOADS_SAH = ('/uploads/aios/', '/uploads/wflogs/', '/wp-content/wflogs/', '/uploads/wpo-cache/', '/uploads/wpforms/',
               '/uploads/elementor/', '/uploads/wpo/', '/uploads/sucuri/')


def php_di_uploads(teks, path):
    if '/wp-content/uploads/' not in path or any(x in path for x in UPLOADS_SAH):
        return None
    if len(teks) < 120 and (b'Silence is golden' in teks or not teks.strip(b'<?ph \n\r\t/')):
        return None
    return 'berkas PHP di wp-content/uploads'


def prepend(teks, path):
    m = RE_PREPEND.search(teks)
    if m and b'wordfence-waf' not in m.group(0) and b'.user.ini' not in m.group(0):
        return potong(teks, m)
    return None


def php_dalam_gambar(teks, path):
    m = RE_PHP_TAG.search(teks)
    return potong(teks, m) if m else None


def uploader(teks, path):
    if len(teks) < 4000 and RE_UPLOAD.search(teks) and b'wp_' not in teks:
        return potong(teks, RE_UPLOAD.search(teks))
    return None


def array_b64(teks, path):
    m = RE_ARRAY_B64.search(teks)
    return potong(teks, m) if m and RE_EVAL_APA.search(teks) else None


def kata_judi(teks):
    return {re.sub(r'\s+', ' ', t.decode('utf-8', 'replace').lower()) for t in RE_JUDI.findall(teks)}


def judi(teks, path):
    # Berita boleh menyebut "judi online"; spam SEO memakai banyak istilah berbeda (6+ = halaman judi → judi_berat)
    jenis = kata_judi(teks)
    return 'kata judi: ' + ', '.join(sorted(jenis)[:5]) if 3 <= len(jenis) < 6 else None


def judi_berat(teks, path):
    jenis = kata_judi(teks)
    return '%d kata judi: %s' % (len(jenis), ', '.join(sorted(jenis)[:6])) if len(jenis) >= 6 else None


def link_judi_sembunyi(teks, path):
    for i, m in enumerate(RE_SEMBUNYI.finditer(teks)):
        if i >= 300:
            break
        jendela = teks[m.start():m.start() + 3000]
        if RE_LINK.search(jendela) and RE_JUDI.search(jendela):
            return potong(teks, m, 160)
    return None


def cloaking(teks, path):
    # Pemuat kecil: cek UA mesin pencari lalu cetak isi unduhan / berkas .txt/.html (halaman judi untuk Googlebot)
    if len(teks) > 40000 or not RE_UA.search(teks) or not RE_BOT.search(teks):
        return None
    m = RE_KELUARKAN.search(teks)
    if not m and RE_AMBIL_URL.search(teks) and RE_ECHO_VAR.search(teks):
        m = RE_AMBIL_URL.search(teks)
    return potong(teks, m) if m else None


def alih_referer(teks, path):
    # Pengunjung dari Google dialihkan ke situs lain (pola judi untuk HP/klik hasil pencarian)
    if len(teks) > 40000 or not RE_REFERER.search(teks) or not RE_MESIN_CARI.search(teks):
        return None
    m = RE_ALIH.search(teks)
    return potong(teks, m) if m else None


def htaccess_cloak(teks, path):
    for m in RE_HT_CLOAK.finditer(teks):
        tujuan, bendera = m.group(1), m.group(2).upper()
        if tujuan == b'-' or b'[F' in bendera or b',F' in bendera or b'[G' in bendera or b',G' in bendera:
            continue
        return potong(teks, m, 200)
    return None


def index_wp(teks, path):
    if os.path.basename(path) != 'index.php':
        return None
    folder = os.path.dirname(path)
    if not os.path.exists(os.path.join(folder, 'wp-blog-header.php')):
        return None
    if b'wp-blog-header.php' in teks and len(teks) < 1500:
        return None
    return 'index.php WordPress tidak standar (%d byte)' % len(teks)


def js_suntik(teks, path):
    m = RE_JS_CHAR.search(teks)
    return potong(teks, m) if m and RE_JS_SUNTIK.search(teks) else None


# Gerbang = potongan huruf kecil yang WAJIB ada sebelum regex dijalankan (regex re.I mahal di ribuan berkas)
TANDA = [
    ('VD.PHP.EvalDekode', 'eval/assert atas hasil dekode', 'virus', 'php', cari(RE_EVAL_DEKODE), (b'eval', b'assert')),
    ('VD.PHP.EvalInput', 'Eksekusi input pengunjung', 'virus', 'php', cari(RE_EVAL_INPUT), (b'$_',)),
    ('VD.Webshell.Nama', 'Webshell dikenal', 'virus', 'php', webshell, (b'filesman', b'b374k', b'c99shell', b'r57shell', b'indoxploit', b'anonymousfox', b'alfa_data', b'wsosetcookie', b'foxauto', b'0x1949', b'mini', b'blackdragon', b'gecko')),
    ('VD.Deface.HackedBy', 'Halaman deface "hacked by"', 'virus', 'web', cari(RE_HACKED), (b'hacked', b'hack3d')),
    ('VD.WP.PluginPalsu', 'Plugin samaran (Locale Perf / cachepress dkk.)', 'virus', 'php', cari(RE_LOCALE), (b'locale', b'cachepress', b'craft-harvester', b'widget-compat', b'anti-db-wipe')),
    ('VD.WP.LinkHelper', 'Botnet backlink WP-LinkHelper (wlh)', 'virus', 'php', cari(RE_WLH), (b'wlh_', b'wp-linkhelper')),
    ('VD.PHP.ArrayBase64', 'Payload base64 dipecah dalam array + eval', 'virus', 'php', array_b64, (b'eval', b'assert', b'create_function')),
    ('VD.Backlink.Rot13', 'Backlink tersembunyi str_rot13', 'virus', 'php', cari(RE_ROT13_URL), (b'str_rot13',)),
    ('VD.PHP.RantaiChr', 'Rantai chr() (webshell disamarkan)', 'virus', 'php', cari(RE_CHR_RANTAI), (b'chr(',)),
    ('VD.WP.LoginPaksa', 'Login admin paksa via wp-load', 'virus', 'php', auth_paksa, (b'wp_set_auth_cookie',)),
    ('VD.Htaccess.Handler', 'Gambar/teks dieksekusi sebagai PHP', 'virus', {'htaccess'}, cari(RE_HANDLER), (b'php',)),
    ('VD.PHP.DalamGambar', 'Kode PHP di berkas gambar', 'virus', GAMBAR, php_dalam_gambar, (b'<?php', b'eval', b'base64_decode', b'<script')),
    ('VD.WP.IndexTakStandar', 'index.php WordPress diubah', 'virus', {'php'}, index_wp, None),
    ('VD.SEO.JudiHalaman', 'Halaman/teks judi online (6+ istilah)', 'virus', TEKS_JUDI, judi_berat, GERBANG_JUDI),
    ('VD.SEO.JudiTersembunyi', 'Link judi tersembunyi (display:none dkk.)', 'virus', TEKS_JUDI | {'js'}, link_judi_sembunyi, GERBANG_JUDI),
    ('VD.SEO.Cloaking', 'Cloaking: Googlebot diberi halaman lain', 'virus', 'php', cloaking, (b'http_user_agent',)),
    ('VD.Htaccess.Cloaking', 'Cloaking/alih mesin pencari di .htaccess', 'virus', {'htaccess'}, htaccess_cloak, (b'rewritecond',)),
    ('VD.SEO.AlihReferer', 'Pengunjung dari Google dialihkan ke situs lain', 'curiga', 'php', alih_referer, (b'http_referer',)),
    ('VD.PHP.EvalUnduh', 'eval kode yang diunduh', 'curiga', 'php', eval_ambil_url, (b'eval', b'assert')),
    ('VD.PHP.Goto', 'Kode disamarkan goto', 'curiga', 'php', goto_samar, (b'goto',)),
    ('VD.PHP.KodePanjang', 'String terkode panjang + dekode', 'curiga', 'php', kode_panjang, (b'base64_decode', b'gzinflate', b'gzuncompress', b'str_rot13', b'strrev')),
    ('VD.PHP.Hex', 'Kode disamarkan \\x', 'curiga', 'php', hex_samar, (b'\\x',)),
    ('VD.PHP.FungsiString', 'Nama fungsi berbahaya dalam string', 'curiga', 'php', cari(RE_FUNGSI_STR), (b'base64_decode', b'str_rot13', b'gzinflate', b'gzuncompress', b'create_function', b'shell_exec', b'passthru')),
    ('VD.PHP.Uploader', 'Pengunggah berkas kecil', 'curiga', 'php', uploader, (b'move_uploaded_file',)),
    ('VD.PHP.DiUploads', 'PHP di folder uploads', 'curiga', 'php', php_di_uploads, None),
    ('VD.Htaccess.Prepend', 'auto_prepend_file di .htaccess', 'curiga', {'htaccess'}, prepend, (b'auto_',)),
    ('VD.SEO.Judi', 'Spam SEO judi', 'curiga', TEKS_JUDI, judi, GERBANG_JUDI),
    ('VD.JS.Suntik', 'JavaScript tersuntik (fromCharCode)', 'curiga', {'js'}, js_suntik, (b'fromcharcode',)),
]


def ekstensi(nama):
    if nama == '.htaccess':
        return 'htaccess'
    return nama.rsplit('.', 1)[-1].lower() if '.' in nama else ''


def cocok_ekst(kelompok, ext):
    if kelompok == 'php':
        return ext in PHP
    if kelompok == 'web':
        return ext in PHP or ext in ('html', 'htm')
    if kelompok == 'semua':
        return True
    return ext in kelompok


def periksa(path, ext, teks):
    hasil = []
    kecil = teks.lower()
    for tid, nama, tingkat, kel, fn, gerbang in TANDA:
        if not cocok_ekst(kel, ext) or (gerbang and not any(g in kecil for g in gerbang)):
            continue
        try:
            bukti = fn(teks, path)
        except Exception:
            bukti = None
        if bukti:
            hasil.append({'id': tid, 'nama': nama, 'tingkat': tingkat, 'bukti': bukti[:160]})
    return hasil


def akun_da():
    out = []
    try:
        nama = sorted(os.listdir('/usr/local/directadmin/data/users'))
    except OSError:
        nama = sorted(d for d in os.listdir(HOME) if os.path.isdir(os.path.join(HOME, d, 'domains')))
    for n in nama:
        if os.path.isdir(os.path.join(HOME, n, 'domains')):
            try:
                dom = sorted(d for d in os.listdir(os.path.join(HOME, n, 'domains')) if not d.startswith('.'))
            except OSError:
                dom = []
            out.append({'user': n, 'domain': dom[:20]})
    return out


def akar_akun(user):
    return os.path.join(HOME, user, 'domains')


# Database WordPress: konten/opsi berisi judi (postingan spam, widget/kode header berisi link tersembunyi).
# Kredensial dari wp-config.php situs itu sendiri; hanya SELECT.
RE_DEF = re.compile(rb"define\s*\(\s*['\"](DB_NAME|DB_USER|DB_PASSWORD|DB_HOST)['\"]\s*,\s*(['\"])(.*?)(?<!\\)\2\s*\)", re.S)
RE_PREFIX = re.compile(rb"\$table_prefix\s*=\s*['\"]([A-Za-z0-9_]{1,40})['\"]")
POLA_SQL = ('slot[[:space:]]*(gacor|online|88|777|thailand|demo|dana|pulsa)|togel|judi[[:space:]]*(online|slot|bola)|maxwin|sbobet'
            '|scatter[[:space:]]*hitam|rtp[[:space:]]*(live|slot)|situs[[:space:]]*(slot|judi|toto)|mahjong[[:space:]]*ways|toto[[:space:]]*macau')
TANDA_DB = [('VD.DB.JudiTersembunyi', 'Database: link judi tersembunyi', 'virus', link_judi_sembunyi),
            ('VD.DB.JudiHalaman', 'Database: konten judi online (6+ istilah)', 'virus', judi_berat),
            ('VD.DB.Judi', 'Database: spam judi', 'curiga', judi)]


def wp_kredensial(path):
    try:
        with open(path, 'rb') as f:
            teks = f.read(200000)
    except OSError:
        return None
    d = {k.decode(): re.sub(rb'\\(.)', rb'\1', v).decode('utf-8', 'replace') for k, _, v in RE_DEF.findall(teks)}
    m = RE_PREFIX.search(teks)
    if not m or not d.get('DB_NAME') or not d.get('DB_USER'):
        return None
    d['prefix'] = m.group(1).decode()
    return d


def mysql_baris(k, sql):
    host, _, port = (k.get('DB_HOST') or 'localhost').partition(':')
    cmd = ['mysql', '-B', '-N', '--connect-timeout=10', '-u', k['DB_USER'], '-h', host or 'localhost']
    if port.isdigit():
        cmd += ['-P', port]
    env = dict(os.environ, MYSQL_PWD=k.get('DB_PASSWORD', ''))
    r = subprocess.run(cmd + [k['DB_NAME'], '-e', sql], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr.decode('utf-8', 'replace')[:200])
    # Mode batch meng-escape \t \n \\ \0 di nilai kolom
    pulih = {b'n': b'\n', b't': b'\t', b'0': b'\0', b'\\': b'\\'}
    return [[re.sub(rb'\\(.)', lambda m: pulih.get(m.group(1), m.group(1)), x) for x in b.split(b'\t')]
            for b in r.stdout.split(b'\n') if b]


def periksa_db(teks):
    hasil = []
    for tid, nama, tingkat, fn in TANDA_DB:
        bukti = fn(teks, '')
        if bukti:
            hasil.append({'id': tid, 'nama': nama, 'tingkat': tingkat, 'bukti': bukti[:160]})
            break  # satu tanda per baris cukup (urut dari terberat)
    return hasil


def scan_db(user, wpconfig, hari, aman, hit):
    temuan = []
    sejak = ' AND post_modified >= NOW() - INTERVAL %d DAY' % (hari + 1) if hari > 0 else ''
    for path in wpconfig:
        k = wp_kredensial(path)
        if not k:
            continue
        akar, p = os.path.dirname(path), k['prefix']
        kueri = (('posts', "SELECT ID, UNIX_TIMESTAMP(post_modified), CONCAT(post_type, ' ', post_status), post_title, LEFT(post_content, 300000) "
                           "FROM `%sposts` WHERE post_status NOT IN ('trash','auto-draft','inherit') AND post_type NOT IN ('revision','attachment') "
                           "AND LOWER(CONCAT(post_title, ' ', post_content)) REGEXP '%s'%s LIMIT 300" % (p, POLA_SQL, sejak)),
                 ('options', "SELECT option_name, 0, 'option', option_name, LEFT(option_value, 300000) FROM `%soptions` "
                             "WHERE option_name NOT LIKE '%%transient%%' AND LOWER(option_value) REGEXP '%s' LIMIT 100" % (p, POLA_SQL)))
        hit['db'] += 1
        for tabel, sql in kueri:
            try:
                baris = mysql_baris(k, sql)
            except Exception:
                hit['db_gagal'] += 1
                break
            for b in baris:
                if len(b) < 5:
                    continue
                kid, waktu, jenis, judul, isi = b[0].decode('utf-8', 'replace'), b[1], b[2].decode(), b[3], b[4]
                tanda = periksa_db(judul + b'\n' + isi)
                if not tanda:
                    continue
                lokasi = '%s#db:%s%s:%s' % (akar, p, tabel, kid)
                sha = hashlib.sha256(isi).hexdigest()
                if aman.get(lokasi) == sha:
                    hit['aman'] += 1
                    continue
                w = int(waktu) if waktu.isdigit() else 0
                temuan.append({'path': lokasi, 'user': user, 'ukuran': len(isi), 'mtime': w, 'ctime': w, 'sha256': sha, 'izin': '-',
                               'tingkat': tanda[0]['tingkat'], 'tanda': tanda,
                               'db': {'nama': k['DB_NAME'], 'tabel': p + tabel, 'id': kid, 'jenis': jenis,
                                      'judul': judul.decode('utf-8', 'replace')[:120]}})
    return temuan


# Cloaking dari luar: beranda tiap domain diambil lewat IP situs sendiri sebagai browser, Googlebot, dan HP dari
# hasil Google. Halaman judi yang hanya muncul untuk Googlebot / alih ke situs lain = situs disusupi.
UA_BROWSER = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'
UA_GOOGLEBOT = 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
UA_HP = ('Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) '
         'Chrome/141.0 Mobile Safari/537.36')
TANDA_WEB = [('VD.Web.Cloaking', 'Situs: Googlebot diberi halaman judi', 'virus'),
             ('VD.Web.AlihGoogle', 'Situs: pengunjung dari Google dialihkan', 'virus'),
             ('VD.Web.HalamanJudi', 'Situs: beranda berisi judi', 'virus'),
             ('VD.Web.Judi', 'Situs: istilah judi di beranda', 'curiga')]
NAMA_WEB = {t[0]: t for t in TANDA_WEB}


def ip_domain(user, domain):
    try:
        with open('/usr/local/directadmin/data/users/%s/domains/%s.conf' % (user, domain), errors='replace') as f:
            for b in f:
                if b.startswith('ip='):
                    return b.strip()[3:]
    except OSError:
        pass
    return '127.0.0.1'


def ambil(domain, ip, ua, referer=None):
    """(kode, alih, isi) beranda; query unik → tidak dijawab dari LSCache. Tanpa ikut redirect."""
    for skema, port in (('https', 443), ('http', 80)):
        cmd = ['curl', '-sk', '--compressed', '--max-time', '20', '--max-filesize', '3000000', '-A', ua,
               '--resolve', '%s:%d:%s' % (domain, port, ip), '-o', '-', '-w', '\nVCEK %{http_code} %{redirect_url}',
               '%s://%s/?vcek=%d' % (skema, domain, time.time())]
        if referer:
            cmd[-1:-1] = ['-e', referer]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
        except subprocess.TimeoutExpired:
            continue
        isi, _, ekor = r.stdout.rpartition(b'\nVCEK ')
        kode, _, alih = ekor.decode('utf-8', 'replace').strip().partition(' ')
        if kode not in ('', '000'):
            return kode, alih.strip(), isi
    return '000', '', b''


def host_url(url):
    m = re.match(r'^[a-z]+://([^/:?#]+)', url or '', re.I)
    return m.group(1).lower() if m else ''


def domain_sama(a, b):
    a, b = a.lower(), b.lower()
    return a == b or a.endswith('.' + b) or b.endswith('.' + a) or a.replace('www.', '', 1) == b.replace('www.', '', 1)


def cek_web(user, domain):
    ip = ip_domain(user, domain)
    kb, ab, ib = ambil(domain, ip, UA_BROWSER)
    kg, ag, ig = ambil(domain, ip, UA_GOOGLEBOT)
    kh, ah, _ = ambil(domain, ip, UA_HP, 'https://www.google.com/')
    jb, jg = kata_judi(ib), kata_judi(ig)
    tanda = []

    def tambah(tid, bukti):
        tanda.append({'id': tid, 'nama': NAMA_WEB[tid][1], 'tingkat': NAMA_WEB[tid][2], 'bukti': bukti[:160]})
    luar_g = ag and not domain_sama(host_url(ag), domain) and host_url(ag) != host_url(ab)
    if (len(jg) >= 3 and len(jg - jb) >= 2) or luar_g:
        tambah('VD.Web.Cloaking', 'Googlebot: %s · browser: %s' % (', '.join(sorted(jg)[:4]) or 'alih ' + ag, ', '.join(sorted(jb)[:3]) or 'tanpa judi'))
    luar_h = ah and not domain_sama(host_url(ah), domain) and host_url(ah) != host_url(ab)
    if luar_h:
        tambah('VD.Web.AlihGoogle', 'HP dari Google → %s (browser langsung: %s)' % (ah, ab or kb))
    if not tanda:
        semua = ib + b'\n' + ig
        bukti = link_judi_sembunyi(semua, '') or judi_berat(semua, '')
        if bukti:
            tambah('VD.Web.HalamanJudi', bukti)
        elif judi(semua, ''):
            tambah('VD.Web.Judi', judi(semua, ''))
    return {'kode': kb, 'kode_bot': kg, 'kode_hp': kh, 'alih': ab, 'alih_bot': ag, 'alih_hp': ah,
            'sha256': hashlib.sha256(ig).hexdigest(), 'ukuran': len(ig), 'tanda': tanda}


def scan_web(user, aman, hit, sisa):
    try:
        daftar = sorted(d for d in os.listdir(akar_akun(user))
                        if not d.startswith('.') and os.path.isdir(os.path.join(akar_akun(user), d, 'public_html')))
    except OSError:
        return []
    temuan = []
    mulai = time.time()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4) as kolam:
        # Per 8 domain supaya batas waktu scan bisa dicek di antaranya (tiap domain maks 3 request × 30 dtk)
        for i in range(0, len(daftar), 8):
            if time.time() - mulai > sisa:
                break
            potongan = daftar[i:i + 8]
            for domain, h in zip(potongan, kolam.map(lambda d: cek_web(user, d), potongan)):
                hit['situs'] += 1
                if h['kode'] == '000':
                    hit['situs_gagal'] += 1
                if not h['tanda']:
                    continue
                lokasi = 'https://%s/#web' % domain
                if aman.get(lokasi) == h['sha256']:
                    hit['aman'] += 1
                    continue
                sekarang = int(time.time())
                temuan.append({'path': lokasi, 'user': user, 'ukuran': h['ukuran'], 'mtime': sekarang, 'ctime': sekarang,
                               'sha256': h['sha256'], 'izin': '-', 'tanda': h['tanda'],
                               'tingkat': 'virus' if any(t['tingkat'] == 'virus' for t in h['tanda']) else 'curiga',
                               'web': {'domain': domain, 'kode': h['kode'], 'kode_bot': h['kode_bot'], 'kode_hp': h['kode_hp'],
                                       'alih': h['alih'], 'alih_bot': h['alih_bot'], 'alih_hp': h['alih_hp']}})
    return temuan


INFO_TANDA = [{'id': t[0], 'nama': t[1], 'tingkat': t[2]} for t in TANDA + TANDA_DB + TANDA_WEB]


def kemajuan(data):
    sys.stdout.write('P ' + json.dumps(data) + '\n')
    sys.stdout.flush()


def scan(p):
    akun = p.get('akun') or 'semua'
    hari = int(p.get('hari') or 0)
    batas = int(p.get('batas') or 1500)
    semua = akun_da()
    if akun == 'semua':
        # Semua akun + semua berkas hanya untuk scan mingguan terjadwal (berjam-jam, nice/ionice)
        if hari <= 0 and not p.get('penuh'):
            return {'ok': False, 'error': 'semua_akun_perlu_batas_hari'}
        daftar = [a['user'] for a in semua]
    else:
        if akun not in [a['user'] for a in semua]:
            return {'ok': False, 'error': 'akun_tidak_dikenal'}
        daftar = [akun]
    sejak = time.time() - hari * 86400 if hari > 0 else 0
    mulai = time.time()
    aman = p.get('aman') or {}
    hit = {'berkas': 0, 'dibaca': 0, 'folder': 0, 'byte': 0, 'aman': 0, 'db': 0, 'db_gagal': 0, 'situs': 0, 'situs_gagal': 0}
    periksa_db_aktif = p.get('db', True)
    periksa_web_aktif = p.get('web', True)
    temuan = []
    terpotong = None
    lapor = 0
    for ia, user in enumerate(daftar):
        akar = akar_akun(user)
        wpconfig = []
        for folder, dirs, files in os.walk(akar):
            dirs[:] = [d for d in dirs if d not in LEWATI and not os.path.islink(os.path.join(folder, d))]
            hit['folder'] += 1
            # Folder cache (halaman statis, gambar optimasi) hanya diperiksa PHP & .htaccess-nya
            di_cache = '/cache' in folder
            for nama in files:
                hit['berkas'] += 1
                if nama == 'wp-config.php':
                    wpconfig.append(os.path.join(folder, nama))
                ext = ekstensi(nama)
                # Loader PHP tersembunyi tanpa ekstensi .php (mis. .c274a4e194190d4e) — dicek isinya di bawah
                tersembunyi = ext not in EKSTENSI and nama.startswith('.')
                if (ext not in EKSTENSI and not tersembunyi) or (di_cache and ext not in PHP and ext != 'htaccess'):
                    continue
                path = os.path.join(folder, nama)
                try:
                    st = os.lstat(path)
                except OSError:
                    continue
                if not (st.st_mode & 0o170000 == 0o100000) or st.st_size == 0 or st.st_size > MAKS_BACA:
                    continue
                # Sisipan PHP di gambar biasanya berkas kecil; gambar besar dilewati agar scan tak membaca GB foto
                if (ext in GAMBAR and st.st_size > 262144) or ((tersembunyi or ext in ('html', 'htm', 'js', 'txt')) and st.st_size > 1048576):
                    continue
                if sejak and max(st.st_mtime, st.st_ctime) < sejak:
                    continue
                try:
                    with open(path, 'rb') as f:
                        teks = f.read()
                except OSError:
                    continue
                if tersembunyi:
                    if b'<?php' not in teks[:256]:
                        continue
                    ext = 'php'
                hit['dibaca'] += 1
                hit['byte'] += len(teks)
                tanda = periksa(path, ext, teks)
                if tanda:
                    sha = hashlib.sha256(teks).hexdigest()
                    if aman.get(path) == sha:
                        hit['aman'] += 1
                        continue
                    temuan.append({'path': path, 'user': user, 'ukuran': st.st_size, 'mtime': int(st.st_mtime), 'sha256': sha,
                                   'ctime': int(st.st_ctime), 'izin': oct(st.st_mode & 0o777)[2:],
                                   'tingkat': 'virus' if any(t['tingkat'] == 'virus' for t in tanda) else 'curiga',
                                   'tanda': tanda})
                    if len(temuan) >= MAKS_TEMUAN:
                        terpotong = 'maks_temuan'
                        break
            sekarang = time.time()
            if sekarang - lapor >= 2:
                lapor = sekarang
                kemajuan({'akun': user, 'ke': ia + 1, 'dari': len(daftar), 'temuan': len(temuan), **hit})
            if terpotong:
                break
            if sekarang - mulai > batas:
                terpotong = 'waktu_habis'
                break
        if periksa_db_aktif and not terpotong and wpconfig:
            temuan.extend(scan_db(user, wpconfig, hari, aman, hit))
        if periksa_web_aktif and not terpotong:
            temuan.extend(scan_web(user, aman, hit, batas - (time.time() - mulai)))
            if len(temuan) >= MAKS_TEMUAN:
                terpotong = 'maks_temuan'
        if terpotong:
            break
    return {'ok': True, 'akun': akun, 'hari': hari, 'detik': round(time.time() - mulai, 1), 'terpotong': terpotong,
            'jumlah_akun': len(daftar), 'temuan': temuan, **hit}


def cpguard():
    if not os.path.exists(CPG_DB):
        return None
    out = {'deteksi': [], 'per_hari': {}, 'per_akun': []}
    try:
        con = sqlite3.connect('file:%s?mode=ro' % CPG_DB, uri=True, timeout=5)
        baris = con.execute("SELECT id, path, reason, definition, time, user, file_status, cleanup_status, file_size "
                            "FROM scanner_logs WHERE time >= datetime('now','-30 day','localtime') ORDER BY id DESC LIMIT 1000").fetchall()
        for (tgl, n) in con.execute("SELECT substr(time,1,10), count(*) FROM scanner_logs WHERE time >= datetime('now','-30 day','localtime') GROUP BY 1"):
            out['per_hari'][tgl] = n
        out['per_akun'] = con.execute("SELECT coalesce(user, '-'), count(*) FROM scanner_logs WHERE time >= datetime('now','-30 day','localtime') "
                                      "GROUP BY 1 ORDER BY 2 DESC LIMIT 10").fetchall()
        out['total'] = con.execute('SELECT count(*) FROM scanner_logs').fetchone()[0]
        con.close()
    except sqlite3.Error as e:
        out['error'] = str(e)[:200]
        return out
    for (i, path, alasan, defin, t, user, fs, cs, ukuran) in baris:
        out['deteksi'].append({'id': i, 'path': path, 'alasan': alasan, 'definisi': defin, 'waktu': t, 'user': user,
                               'file_status': fs, 'cleanup': cs, 'ukuran': ukuran,
                               'ada': os.path.exists(path)})
    return out


def daftar_karantina():
    out = []
    try:
        isi = sorted(os.listdir(KARANTINA), reverse=True)
    except OSError:
        return out
    for d in isi:
        try:
            with open(os.path.join(KARANTINA, d, 'meta.json')) as f:
                m = json.load(f)
        except (OSError, ValueError):
            continue
        m['id'] = d
        m['asal_terisi'] = os.path.exists(m.get('path', ''))
        out.append(m)
    return out


def ringkas(p):
    proses = set()
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            try:
                with open('/proc/%s/comm' % pid) as f:
                    proses.add(f.read().strip())
            except OSError:
                pass
    return {'ok': True, 'cpguard': cpguard(), 'cpguard_jalan': 'cpguard' in proses, 'akun': akun_da(),
            'karantina': daftar_karantina(), 'tanda': INFO_TANDA, 'waktu': int(time.time())}


def aman_path(path):
    """Hanya berkas biasa di /home/<akun>/domains/..., bukan symlink."""
    if not path or '\0' in path or not path.startswith(HOME + '/') or '/.' + './' in path + '/':
        return None, 'path_tidak_sah'
    asli = os.path.realpath(path)
    bagian = asli[len(HOME) + 1:].split('/')  # akun/domains/<domain>/...
    if asli != os.path.normpath(path) or not asli.startswith(HOME + '/') or len(bagian) < 4 or bagian[1] != 'domains':
        return None, 'path_tidak_sah'
    if os.path.islink(path) or not os.path.isfile(asli):
        return None, 'berkas_tidak_ada'
    return asli, None


def karantina(p):
    path, err = aman_path(p.get('path'))
    if err:
        return {'ok': False, 'error': err}
    st = os.lstat(path)
    with open(path, 'rb') as f:
        isi = f.read()
    kid = time.strftime('%Y%m%d-%H%M%S') + '-' + hashlib.sha1(path.encode()).hexdigest()[:8]
    tujuan = os.path.join(KARANTINA, kid)
    os.makedirs(tujuan, mode=0o700)
    os.chmod(KARANTINA, 0o700)
    with open(os.path.join(tujuan, 'berkas'), 'wb') as f:
        f.write(isi)
    os.chmod(os.path.join(tujuan, 'berkas'), 0o600)
    meta = {'path': path, 'uid': st.st_uid, 'gid': st.st_gid, 'mode': st.st_mode & 0o7777, 'mtime': int(st.st_mtime),
            'ukuran': len(isi), 'sha256': hashlib.sha256(isi).hexdigest(), 'waktu': int(time.time()),
            'oleh': str(p.get('oleh') or '')[:40], 'alasan': str(p.get('alasan') or '')[:200]}
    try:
        meta['user'] = pwd.getpwuid(st.st_uid).pw_name
    except KeyError:
        meta['user'] = str(st.st_uid)
    with open(os.path.join(tujuan, 'meta.json'), 'w') as f:
        json.dump(meta, f)
    # Salinan tertulis utuh dulu, baru berkas asli dihapus
    with open(os.path.join(tujuan, 'berkas'), 'rb') as f:
        if hashlib.sha256(f.read()).hexdigest() != meta['sha256']:
            shutil.rmtree(tujuan, ignore_errors=True)
            return {'ok': False, 'error': 'salin_gagal'}
    os.remove(path)
    return {'ok': True, 'id': kid, 'path': path}


def entri(kid):
    if not re.match(r'^\d{8}-\d{6}-[0-9a-f]{8}$', kid or ''):
        return None, None
    folder = os.path.join(KARANTINA, kid)
    try:
        with open(os.path.join(folder, 'meta.json')) as f:
            return folder, json.load(f)
    except (OSError, ValueError):
        return None, None


def kembalikan(p):
    folder, meta = entri(p.get('id'))
    if not meta:
        return {'ok': False, 'error': 'karantina_tidak_ada'}
    path = meta['path']
    if os.path.lexists(path):
        return {'ok': False, 'error': 'lokasi_asal_terisi'}
    induk = os.path.dirname(path)
    if not os.path.isdir(induk) or not induk.startswith(HOME + '/'):
        return {'ok': False, 'error': 'folder_asal_hilang'}
    sementara = path + '.velocity-pulih'
    shutil.copyfile(os.path.join(folder, 'berkas'), sementara)
    os.chown(sementara, meta['uid'], meta['gid'])
    os.chmod(sementara, meta['mode'])
    os.utime(sementara, (meta['mtime'], meta['mtime']))
    os.rename(sementara, path)
    shutil.rmtree(folder)
    return {'ok': True, 'path': path}


def hapus(p):
    folder, meta = entri(p.get('id'))
    if not meta:
        return {'ok': False, 'error': 'karantina_tidak_ada'}
    shutil.rmtree(folder)
    return {'ok': True, 'path': meta['path']}


MAKS_LIHAT = 512 * 1024


def baca(p):
    if p.get('id'):
        folder, meta = entri(p['id'])
        if not meta:
            return {'ok': False, 'error': 'karantina_tidak_ada'}
        path, asal = os.path.join(folder, 'berkas'), meta['path']
        sha = meta.get('sha256')
    else:
        # Lebih longgar dari aman_path: berkas biasa mana pun di /home (deteksi cPGuard bisa di luar domains/)
        asal = p.get('path') or ''
        path = os.path.realpath(asal)
        if '\0' in asal or not path.startswith(HOME + '/'):
            return {'ok': False, 'error': 'path_tidak_sah'}
        if os.path.islink(asal) or not os.path.isfile(path):
            return {'ok': False, 'error': 'berkas_tidak_ada'}
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for blok in iter(lambda: f.read(1 << 20), b''):
                h.update(blok)
        sha = h.hexdigest()
    st = os.stat(path)
    with open(path, 'rb') as f:
        isi = f.read(MAKS_LIHAT)
    return {'ok': True, 'path': asal, 'ukuran': st.st_size, 'mtime': int(st.st_mtime), 'terpotong': st.st_size > len(isi), 'sha256': sha,
            'biner': b'\0' in isi[:8192], 'isi': isi.decode('utf-8', 'replace')}


AKSI = {'baca': baca, 'ringkas': ringkas, 'scan': scan, 'karantina': karantina, 'kembalikan': kembalikan, 'hapus': hapus}


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
