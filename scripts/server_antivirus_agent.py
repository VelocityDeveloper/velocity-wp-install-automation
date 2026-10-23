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
- karantina: pindahkan satu berkas ke KARANTINA/<id>/ + meta.json (pemilik, izin, waktu, sha256); sha256 ikut dijawab.
- kembalikan: pulihkan berkas karantina ke lokasi asal (pemilik & izin semula); gagal bila lokasi terisi.
- hapus: hapus permanen satu entri karantina.
- baca (baca): isi satu berkas di /home (path) atau salinan karantina (id), maks MAKS_LIHAT byte + sha256 utuh.
- scan menerima 'aman' {path: sha256}: berkas yang ditandai aman dari dashboard dilewati selama isinya sama.
- bukti_judi (baca): domain akun, status suspend, judul+teks beranda versi browser/Googlebot, potongan berkas temuan,
  dan bila beranda masih berisi judi: sumber kemungkinan (scan penuh wp-content, tanda tingkat virus).
- suspend / unsuspend: akun DirectAdmin (`directadmin suspend-user`), hanya dipanggil Judi AI / tombol dashboard.
"""
import base64
import binascii
import glob
import hashlib
import json
import os
import pwd
import html
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

KARANTINA = '/root/velocity-karantina'
HOME = '/home'
CPG_DB = '/opt/cpguard/app/data/scanner.db'
MAKS_BACA = 3 * 1024 * 1024
MAKS_TEMUAN = 3000
# Berkas besar yang hanya dibaca awal+akhir dan bersih tetap dicatat (bertag) supaya bisa dicek manual
MAKS_BESAR = 2000
MAKS_BESAR = 2000
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
RE_SHELL = r(r'FilesMan|b374k|c99shell|r57shell|IndoXploit|AnonymousFox|ALFA_DATA|\bWSOsetcookie\b|FoxAuto|0x1949|Mini\s*Shell\s*\d|BlackDragon|PHP\s+File\s+manager\s+ver\b|<title>\s*Gecko\s*\[', 0)
RE_EKSEKUSI = r(r'\b(?:system|shell_exec|passthru|proc_open|popen|exec|eval|move_uploaded_file)\s*\(')
RE_SUPERGLOBAL = r(r'\$_(?:POST|GET|REQUEST|FILES|COOKIE)\b')
RE_KOMENTAR_PHP = re.compile(rb'/\*.*?\*/|//[^\n]*|#[^\n]*|<\?php|\?>', re.S)
RE_JAGA_PHP = re.compile(rb"\s*if\s*\(\s*!\s*defined\s*\(\s*\\*['\"]\w+\\*['\"]\s*\)\s*\)\s*(?:exit|die)\s*(?:\(\s*\))?\s*;")
RE_LISENSI_TERLARANG = r(r'\b(?:assert|create_function|file_put_contents|fwrite|fputs|curl_exec|include|require)(?:_once)?\s*\(|\bgzinflate\b|\bstr_rot13\b')
RE_HACKED = r(r'<title>[^<]{0,60}hack(?:ed|3d)\s*by')
RE_LOCALE = r(r'wp-locale-perf|Locale Performance Cache|wp-cachepress|craft-harvester-jet|widget-compat-helper|wp_locale_cache_\w+|locale-cache-(?:db|oc)\b|Anti-DB-wipe MU loader')
# Botnet backlink "WP-LinkHelper" (folder wlh-*/class-wlh-*.php, panel cachelayer.top), dari karantina cPGuard Fahmi 14 Okt 2026
RE_WLH = r(r'\bclass\s+WLH_\w+|\bWLH_(?:REMOTE_URL|HANDSHAKE|OPT_LINKS)\b|WP-LinkHelper', 0)
# Kampanye wp2shell (CVE-2026-63030, khankimi & bayarlis 22 Okt 2026): penanda alat, plugin/mu-plugin samaran, pintu TDS
RE_SUFIKS_W2S = re.compile(r'__[0-9a-f]{7}$')
RE_W2S = r(r'2DUAN_START|WP2SHELL::|WPBWORM::|Plugin Name:\s*(?:wp2shell|wpbatchworm)\b|FM_CACHE_IDX_INJECT|FM_CACHE_INDEX_CUSTOM_CODE'
           r'|source:\s*b26_wp_mu|\bwfc_dp_(?:dynamic_payload_handler|decrypt_data|send_get_request)\b|\bll_autocreate\b'
           r'|\?api=%s&ac=%s&path=%s|\d*PJcpMFsD8B\.php', 0)
# Closure yang meng-eval argumennya: $f = function ($x) { EVAL ($x); };
RE_EVAL_CLOSURE = r(r'function\s*\(\s*\$(\w+)\s*\)\s*\{\s*(?:@\s*)?(?:eval|assert)\s*\(\s*\$\1\s*\)\s*;\s*\}')
# Tabel fungsi $GLOBALS[O0O0O0] = explode('|H|Z|8', 'ini_set|…|eval|…') (pemuat O00OO di index.php folder ganda)
RE_GLOBALS_EXPLODE = r(r'\$GLOBALS\s*\[\s*[O0]{4,}\s*\]\s*=\s*explode\s*\(', 0)
# Nama fungsi dibalik (plugin CoreStack): strrev('elif_dedaolpu_evom')
RE_STRREV_FUNGSI = r(r'strrev\s*\(\s*[\'"](?:elif_dedaolpu_evom|knilnu|stnetnoc_tup_elif|stnetnoc_teg_elif|ridnacs|cexe_llehs|metsys|lave)[\'"]')
# Nama fungsi dalam string hex ('7068705f756e616d65' = php_uname) → webshell ngji
HEX_FUNGSI = {binascii.hexlify(x) for x in (b'php_uname', b'file_get_contents', b'file_put_contents', b'base64_decode', b'unlink',
              b'chmod', b'mkdir', b'scandir', b'shell_exec', b'passthru', b'move_uploaded_file', b'fwrite', b'proc_open', b'popen')}
RE_HEX_STR = re.compile(rb'[\'"]([0-9a-fA-F]{8,40})[\'"]')
# .htaccess kunci: tolak semua PHP lalu izinkan index.php + nama shell (melindungi shell, menutup PHP lain)
RE_HT_KUNCI = r(r'<FilesMatch\s+"[^"\n]*\(py\|exe\|(?:phtml\|)?php\b|<FilesMatch\s+"\^\([^"\n]*(?:lock360|wp-l0gin|PJcpMFsD8B|juejiang|zt2)\\?\.php')
# Penyembunyi akun penyerang (login wp_*) dari Users/penulis
RE_SEMBUNYI_USER = r(r'esc_like\s*\(\s*[\'"]wp_[\'"]\s*\)')
# Pemuat O00OO: $O00OO_0_O_ = urldecode("%6E1%7A…") lalu fungsi dirakit per karakter
RE_VAR_O0 = r(r'\$(?=[O0_]*O)(?=[O0_]*0)[O0_]{8,}\s*=\s*(?:urldecode|base64_decode|str_rot13|gzinflate|rawurldecode)\s*\(', 0)
# Nama fungsi dirakit str_split/implode (file manager bergerbang $__h/$__k di plugin samaran wp-menu-helper)
RE_STR_SPLIT = r(r'str_split\s*\(\s*[\'"](?:file_put_contents|file_get_contents|move_uploaded_file|unlink|rename|chmod|shell_exec)[\'"]'
                 r'|implode\s*\(\s*[\'"][\'"]\s*,\s*str_split\s*\(\s*\$\w+\s*,\s*1\s*\)\s*\)\s*;\s*\}\s*,\s*\[\s*[\'"]move_uploaded_file')
# mu-plugin sisipan tautan "Home Text Permanent" (bayarlis) — bisa saja dipasang pemilik → curiga
RE_HOME_TEXT = r(r'\bhti_(?:permanent_settings|mu_installer_cleanup_pending)\b', 0)
# Pintu belakang mu-plugin gelombang 21 Okt (montessori, dewanpendidikan, miainulyaqiin): salin diri ke MU, pemulih dari GitHub
RE_MU_BELAKANG = r(r'\b(?:mu_protector_restore_file|lf_sync_mu_plugin_copy)\b|CURLOPT_LF_TEST|MU Guardian Plugin', 0)
# Gelombang montesso 23 Okt: pemuat index.php "Plugin Name: SecurePlugin<acak>" + class Loader<HURUF><angka>,
# shell kecil $key="ptr" yang menulis payload ke <tmp>/.elem lalu include, dan file manager mandiri FM_ROOT/.fm_key
RE_LOADER_SP = r(r'Plugin Name:\s*SecurePlugin[A-Za-z0-9]{6,}|\bclass\s+Loader[A-Z]{5}\d{3,}\b', 0)
RE_PTR_ELEM = r(r'\$key\s*=\s*[\'"]ptr[\'"]', 0)
RE_FM_ROOT = r(r'\bFM_ROOT\b', 0)
# Login sebagai admin mana saja: cari ID administrator lewat SQL lalu wp_set_auth_cookie
RE_ADMIN_SQL = r(r'meta_value\s+LIKE\s+[\'"]%administrator%[\'"]')
# Buat akun dari ?user=&pass= di URL
RE_PASS_GET = r(r'\$_(?:GET|REQUEST)\s*\[\s*[\'"](?:pass|password|pwd)[\'"]\s*\]')
RE_BUAT_USER = r(r'\bwp_(?:create|insert)_user\s*\(')
# Payload dipecah ke $__map["k0"]…$__map["kN"] lalu didekode berlapis dan di-eval
RE_PETA = r(r'\$__map\s*\[\s*[\'"]k\d+[\'"]\s*\]\s*=', 0)
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
# Pengalih TDS (pleasewaitcenter dkk.): <script>.src = atob('aHR0c…') + referrer/judul halaman
RE_SRC_ATOB = r(r'\.src\s*=\s*atob\s*\(\s*\\?[\'"]aHR0c')
# Plugin/tema mencetak isi .txt dari situs luar di wp_footer/wp_head (footer-injector-kmaa26 → link judi)
RE_HOOK_TAMPIL = r(r'add_action\s*\(\s*[\'"](?:wp_footer|wp_head)[\'"]')
RE_URL_TXT = r(r'[\'"]https?://[^\'"\s]+\.txt[\'"]')
RE_UNDUH = r(r'wp_remote_get|wp_safe_remote_get|file_get_contents|curl_exec')


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


def lisensi_gianmr(teks, path):
    """Modul lisensi tema GianMR (wpmedia/wpberita/bloggingpro-core lib/lcs.php) disamarkan goto oleh vendornya.
    Dianggap sah hanya bila header vendor ada dan sesudah string \\x/oktal dibuka tidak ada fungsi eksekusi/tulis."""
    if not path.endswith('-core/lib/lcs.php') or b'License from amember http api softsale module' not in teks[:600] \
            or b'Gian MR' not in teks[:600]:
        return False
    buka = re.sub(rb'\\x([0-9a-fA-F]{2})', lambda m: bytes([int(m.group(1), 16)]), teks)
    buka = re.sub(rb'\\([0-7]{3})', lambda m: bytes([int(m.group(1), 8) & 255]), buka)
    return not RE_EKSEKUSI.search(buka) and not RE_LISENSI_TERLARANG.search(buka)


def goto_samar(teks, path):
    if lisensi_gianmr(teks, path):
        return None
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


# Redux Framework menulis kelas kontrol Customizer kosong ke uploads/redux/ (positif palsu 19 Okt, sinarberita.id dkk.).
# Hanya bila SELURUH isi berkas persis pola ini — satu baris tambahan tetap terdeteksi.
RE_REDUX_KONTROL = re.compile(rb'\A<\?php\s*class\s+Redux_Customizer_Control_\w+\s+extends\s+Redux_Customizer_Control\s*\{'
                              rb'\s*public\s+\$type\s*=\s*["\']redux-[\w-]+["\']\s*;\s*\}\s*\Z')


RE_HTML_AKTIF = re.compile(rb'<\?|<%|<script|<iframe|<object|<embed|<form|http-equiv|\bon\w+\s*=|javascript:', re.I)


# Berkas inti WordPress besar (block-editor.js, vips/worker.min.js, …) tidak dibaca scan → dicocokkan md5-nya dengan
# checksum resmi api.wordpress.org per versi situs. Cocok = asli, tidak masuk daftar besar; gagal ambil = tetap dilaporkan.
RE_INTI_WP = re.compile(r'^(/home/[^/]+/domains/[^/]+/(?:[^/]+/)*?)(wp-(?:includes|admin)/.+)$')
_CHECKSUM_WP = {}
# Hasil cocok checksum disimpan {path: [ukuran, mtime, ctime]} → scan berikutnya tak menghitung md5 ulang berkas yang sama
INTI_CACHE = '/var/lib/velocity-av/inti-asli.json'
_INTI_OK = None
# Berkas di atas batas baca: hanya POTONG_BESAR awal + POTONG_BESAR akhir yang diperiksa (sisipan biasanya di ujung berkas)
POTONG_BESAR = 262144


def baca_sebagian(path, ukuran):
    with open(path, 'rb') as f:
        kepala = f.read(POTONG_BESAR)
        f.seek(max(ukuran - POTONG_BESAR, POTONG_BESAR))
        return kepala + b'\n' + f.read(POTONG_BESAR)


def hash_berkas(path, algo='sha256'):
    h = hashlib.new(algo)
    with open(path, 'rb') as f:
        for blok in iter(lambda: f.read(1048576), b''):
            h.update(blok)
    return h.hexdigest()


def _inti_cache():
    global _INTI_OK
    if _INTI_OK is None:
        try:
            with open(INTI_CACHE) as f:
                _INTI_OK = json.load(f)
        except (OSError, ValueError):
            _INTI_OK = {}
    return _INTI_OK


def simpan_inti_cache():
    if not _INTI_OK:
        return
    try:
        os.makedirs(os.path.dirname(INTI_CACHE), exist_ok=True)
        with open(INTI_CACHE + '.tmp', 'w') as f:
            json.dump(_INTI_OK, f, separators=(',', ':'))
        os.replace(INTI_CACHE + '.tmp', INTI_CACHE)
    except OSError:
        pass


def checksum_wp(akar):
    try:
        with open(akar + 'wp-includes/version.php', encoding='latin-1') as f:
            versi = re.search(r"\$wp_version\s*=\s*'([\w.-]+)'", f.read()).group(1)
    except (OSError, AttributeError):
        return {}
    if versi not in _CHECKSUM_WP:
        _CHECKSUM_WP[versi] = {}
        try:
            req = urllib.request.Request('https://api.wordpress.org/core/checksums/1.0/?version=%s&locale=en_US' % versi,
                                         headers={'User-Agent': 'VelocityGuard/1.0'})
            data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode()).get('checksums')
            if isinstance(data, dict):
                _CHECKSUM_WP[versi] = data
        except Exception:
            pass
    return _CHECKSUM_WP[versi]


# Plugin dari wordpress.org (kirki-editor.min.js 5,9 MB dkk.): dicocokkan dengan downloads.wordpress.org/plugin-checksums
# per slug + versi terpasang. Plugin premium/non-wp.org → 404 → tetap dilaporkan.
RE_PLUGIN_WP = re.compile(r'^(/home/[^/]+/domains/[^/]+/(?:[^/]+/)*?wp-content/plugins/([^/]+)/)(.+)$')
_CHECKSUM_PLUGIN = {}
_VERSI_PLUGIN = {}
RE_KEPALA_PLUGIN = re.compile(r'^[ \t/*#@]*Plugin Name\s*:', re.M | re.I)
RE_VERSI_PLUGIN = re.compile(r'^[ \t/*#@]*Version\s*:\s*([\w.-]+)', re.M | re.I)


def versi_plugin(folder):
    if folder not in _VERSI_PLUGIN:
        _VERSI_PLUGIN[folder] = None
        for berkas in sorted(glob.glob(folder + '*.php')):
            try:
                with open(berkas, encoding='latin-1') as f:
                    kepala = f.read(8192)
            except OSError:
                continue
            m = RE_VERSI_PLUGIN.search(kepala)
            if m and RE_KEPALA_PLUGIN.search(kepala):
                _VERSI_PLUGIN[folder] = m.group(1)
                break
    return _VERSI_PLUGIN[folder]


def checksum_plugin(folder, slug):
    versi = versi_plugin(folder)
    if not versi:
        return {}
    kunci = slug + '@' + versi
    if kunci not in _CHECKSUM_PLUGIN:
        _CHECKSUM_PLUGIN[kunci] = {}
        try:
            req = urllib.request.Request('https://downloads.wordpress.org/plugin-checksums/%s/%s.json' % (slug, versi),
                                         headers={'User-Agent': 'VelocityGuard/1.0'})
            data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode()).get('files')
            if isinstance(data, dict):
                _CHECKSUM_PLUGIN[kunci] = {k: v.get('md5') for k, v in data.items() if isinstance(v, dict)}
        except Exception:
            pass
    return _CHECKSUM_PLUGIN[kunci]


# Berkas besar premium (bb-plugin dkk., tanpa API checksum) yang sudah dicek manual: daftar putih sha256 dari dashboard
# {sha256: ukuran}. Hanya berkas berukuran persis sama yang di-hash, jadi murah. Tidak di-cache: hash dibuang = muncul lagi.
def hash_asli(path, st, asli):
    if not asli or st.st_size not in asli.values():
        return False
    try:
        return asli.get(hash_berkas(path)) == st.st_size
    except OSError:
        return False


def inti_wp_asli(path, st):
    m = RE_INTI_WP.match(path)
    mp = None if m else RE_PLUGIN_WP.match(path)
    if not m and not mp:
        return False
    kunci = [st.st_size, int(st.st_mtime), int(st.st_ctime)]
    cache = _inti_cache()
    if cache.get(path) == kunci:
        return True
    md5 = checksum_wp(m.group(1)).get(m.group(2)) if m else checksum_plugin(mp.group(1), mp.group(2)).get(mp.group(3))
    try:
        if not md5 or hash_berkas(path, 'md5') != md5:
            return False
    except OSError:
        return False
    cache[path] = kunci
    return True


def php_di_uploads(teks, path):
    if '/wp-content/uploads/' not in path or any(x in path for x in UPLOADS_SAH):
        return None
    if '/uploads/redux/' in path and RE_REDUX_KONTROL.match(teks):
        return None
    # Penjaga folder / template kosong (silence is golden, BWS Custom Code): hanya komentar + `if (!defined(..)) exit;`.
    # Isi dinilai sebagai kode walau tanpa tag <? atau berbentuk &lt;?php: berkas lain bisa eval(file_get_contents(..)).
    isi = html.unescape(teks.decode('latin-1')).encode('latin-1', 'replace')
    if not RE_JAGA_PHP.sub(b'', RE_KOMENTAR_PHP.sub(b'', isi)).strip():
        return None
    # Penjaga folder ber-HTML (WP Content Copy Protection: komentar PHP, `?>`, lalu pesan "not authorized"):
    # sah hanya bila blok PHP cuma komentar dan HTML sesudahnya statis — tanpa <? lagi, skrip, iframe, atau meta refresh.
    kepala, tutup, ekor = isi.partition(b'?>')
    if tutup and len(isi) < 4096 and not RE_KOMENTAR_PHP.sub(b'', kepala).strip() and not RE_HTML_AKTIF.search(ekor):
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


# Kasus kalandra 18 Okt (plugin palsu "semrush", lolos semua VD.*): eval('?>' . $hasil_unduhan) dan
# include berkas sementara berisi unduhan (Gecko loader)
RE_EVAL_TAG = r(r'\b(?:eval|assert)\s*\(\s*(?:@\s*)?[\'"]\?>[\'"]\s*\.\s*\$\w+')
RE_INCLUDE_TMP = r(r'\b(?:include|require)(?:_once)?\s*\(?\s*stream_get_meta_data\s*\(')
RE_UNDUH_APA = r(r'curl_exec\s*\(|file_get_contents\s*\(|stream_get_contents\s*\(|fopen\s*\(\s*[\'"]?https?:|\\x68\\x74\\x74\\x70|\\150\\164\\164\\160')
RE_FM_OPS = [r(x) for x in (r'move_uploaded_file\s*\(', r'\bunlink\s*\(', r'\brename\s*\(', r'file_put_contents\s*\(',
                             r'\b(?:scandir|opendir|readdir)\s*\(', r'\brmdir\s*\(|\bchmod\s*\(')]
RE_WP_KONTEKS = r(r'\bwp_\w+\s*\(|\bABSPATH\b|\bdefined\s*\(\s*[\'"]WPINC|namespace\s+\w|\bclass\s+\w+\s+(?:extends|implements)\b')


def rantai_chr(teks, path):
    # Pustaka ber-namespace (doctrine/inflector: tabel aksen ISO-8859-1 chr(128) . chr(131) …) bukan webshell
    m = RE_CHR_RANTAI.search(teks)
    return potong(teks, m) if m and not re.search(rb'^\s*namespace\s+[\w\\]+\s*;', teks, re.M) else None


def eval_tag_unduh(teks, path):
    m = RE_EVAL_TAG.search(teks)
    return potong(teks, m) if m and RE_UNDUH_APA.search(teks) else None


def include_tmp_unduh(teks, path):
    m = RE_INCLUDE_TMP.search(teks)
    return potong(teks, m) if m and b'tmpfile' in teks.lower() and RE_UNDUH_APA.search(teks) else None


def file_manager(teks, path):
    # Webshell file manager mandiri: unggah + hapus/ganti nama + daftar folder dari input pengunjung, tanpa konteks WP/pustaka
    if not RE_SUPERGLOBAL.search(teks) or RE_WP_KONTEKS.search(teks) or len(teks) > 400000:
        return None
    n = sum(1 for x in RE_FM_OPS if x.search(teks))
    return '%d operasi berkas + input pengunjung (file manager mandiri)' % n if n >= 5 and RE_FM_OPS[0].search(teks) else None


def uploader(teks, path):
    if len(teks) < 4000 and RE_UPLOAD.search(teks) and b'wp_' not in teks:
        return potong(teks, RE_UPLOAD.search(teks))
    return None


def array_b64(teks, path):
    m = RE_ARRAY_B64.search(teks)
    return potong(teks, m) if m and RE_EVAL_APA.search(teks) else None


def kata_judi(teks):
    return {re.sub(r'\s+', ' ', t.decode('utf-8', 'replace').lower()) for t in RE_JUDI.findall(teks)}


# Daftar kata anti-spam (formidable/denylist/splorp-wp-comment.txt: 66 rb istilah per baris, termasuk "<a>" dan
# "http://") bukan halaman judi — halaman/sisipan judi berupa paragraf/HTML panjang dengan tautan href
RE_HREF = r(r'href\s*=')


def daftar_kata(teks):
    baris = teks.count(b'\n')
    return baris >= 500 and len(teks) / baris <= 40 and len(RE_HREF.findall(teks)) <= 2


RE_LLMS_KEPALA = re.compile(rb'Generated by (?:All in One SEO|Yoast SEO|Rank Math)[^\n]{0,80}llms\.txt', re.I)
RE_LLMS_HOST = re.compile(rb'\]\(https?://([^/)\s]+)')


def llms_seo(teks, path):
    """llms.txt buatan plugin SEO = daftar judul pos situs sendiri (situs berita memuat judul berita judi).
    Sah hanya bila header plugin ada dan SEMUA tautan menuju domain situs itu sendiri."""
    if os.path.basename(path) not in ('llms.txt', 'llms-full.txt') or not RE_LLMS_KEPALA.search(teks[:400]):
        return False
    host = {h.lower().split(b':')[0] for h in RE_LLMS_HOST.findall(teks)}
    return len({h[4:] if h.startswith(b'www.') else h for h in host}) == 1


def judi(teks, path):
    # Berita boleh menyebut "judi online"; spam SEO memakai banyak istilah berbeda (6+ = halaman judi → judi_berat)
    if daftar_kata(teks) or llms_seo(teks, path):
        return None
    jenis = kata_judi(teks)
    return 'kata judi: ' + ', '.join(sorted(jenis)[:5]) if 3 <= len(jenis) < 6 else None


def judi_berat(teks, path):
    if daftar_kata(teks) or llms_seo(teks, path):
        return None
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
    # Keluaran harus tepat sesudah cek UA bot (≤800 byte); readfile unduhan biasa di plugin (LSCache debug2) tidak
    kandidat = list(RE_KELUARKAN.finditer(teks))
    if RE_ECHO_VAR.search(teks):
        kandidat += list(RE_AMBIL_URL.finditer(teks))
    for m in kandidat:
        depan = teks[max(0, m.start() - 800):m.start()]
        if RE_UA.search(depan) and RE_BOT.search(depan):
            return potong(teks, m)
    return None


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


def suntik_remote(teks, path):
    m = RE_URL_TXT.search(teks)
    if m and RE_HOOK_TAMPIL.search(teks) and RE_UNDUH.search(teks) and RE_ECHO_VAR.search(teks):
        return potong(teks, m)
    return None


def js_suntik(teks, path):
    m = RE_JS_CHAR.search(teks)
    return potong(teks, m) if m and RE_JS_SUNTIK.search(teks) else None


def hex_fungsi(teks, path):
    nama = {m.group(1).lower() for m in RE_HEX_STR.finditer(teks)} & HEX_FUNGSI
    return 'nama fungsi dalam hex: ' + ', '.join(sorted(binascii.unhexlify(x).decode() for x in nama)[:5]) if len(nama) >= 4 else None


def eval_tag_dekripsi(teks, path):
    # eval('?>' . openssl_decrypt(...)) — payload terenkripsi kunci tetap (SvVZ6/index.php)
    m = RE_EVAL_TAG.search(teks)
    return potong(teks, m) if m and b'openssl_decrypt' in teks else None


def pintu_tds(teks, path):
    # Pintu TDS index.php: kirim domain/referer/UA pengunjung ke API luar lalu cetak header+isi balasannya
    if len(teks) < 40000 and re.search(rb'\$params\s*\[\s*[\'"]agent[\'"]\s*\]', teks) and re.search(rb'\$params\s*\[\s*[\'"]referer[\'"]\s*\]', teks) \
            and re.search(rb'gzuncompress\s*\(\s*base64_decode', teks):
        return potong(teks, re.search(rb'\$params\s*\[\s*[\'"]agent', teks))
    return None


def login_admin_acak(teks, path):
    m = RE_ADMIN_SQL.search(teks)
    return potong(teks, m) if m and RE_AUTH.search(teks) and RE_ADMIN_PAKSA.search(teks) else None


def buat_user_get(teks, path):
    m = RE_PASS_GET.search(teks)
    return potong(teks, m) if m and RE_BUAT_USER.search(teks) else None


def peta_eval(teks, path):
    n = len(RE_PETA.findall(teks))
    return '%d potongan $__map + eval' % n if n >= 20 and re.search(rb'\beval\s*\(', teks) else None


def sembunyi_user(teks, path):
    m = RE_SEMBUNYI_USER.search(teks)
    return potong(teks, m) if m and b'user_login' in teks and re.search(rb'pre_user_query|author__not_in|views_users', teks) else None


def ptr_elem(teks, path):
    m = RE_PTR_ELEM.search(teks)
    return potong(teks, m) if m and b'.elem' in teks and b'include' in teks else None


def fm_root(teks, path):
    # FM_ROOT saja bisa nama konstanta plugin sah → wajib ada .fm_key atau FM_PASS + move_uploaded_file
    m = RE_FM_ROOT.search(teks)
    return potong(teks, m) if m and (b'.fm_key' in teks or (b'FM_PASS' in teks and b'move_uploaded_file' in teks)) else None


# Gerbang = potongan huruf kecil yang WAJIB ada sebelum regex dijalankan (regex re.I mahal di ribuan berkas)
TANDA = [
    ('VD.PHP.EvalDekode', 'eval/assert atas hasil dekode', 'virus', 'php', cari(RE_EVAL_DEKODE), (b'eval', b'assert')),
    ('VD.PHP.EvalInput', 'Eksekusi input pengunjung', 'virus', 'php', cari(RE_EVAL_INPUT), (b'$_',)),
    ('VD.Webshell.Nama', 'Webshell dikenal', 'virus', 'php', webshell, (b'filesman', b'b374k', b'c99shell', b'r57shell', b'indoxploit', b'anonymousfox', b'alfa_data', b'wsosetcookie', b'foxauto', b'0x1949', b'mini', b'blackdragon', b'gecko', b'php file manager')),
    ('VD.PHP.EvalUnduhTag', "eval('?>' . kode unduhan)", 'virus', 'php', eval_tag_unduh, (b'?>',)),
    ('VD.PHP.IncludeUnduh', 'include berkas sementara berisi unduhan', 'virus', 'php', include_tmp_unduh, (b'stream_get_meta_data',)),
    ('VD.Webshell.FileManager', 'File manager mandiri (webshell)', 'virus', 'php', file_manager, (b'move_uploaded_file',)),
    ('VD.Deface.HackedBy', 'Halaman deface "hacked by"', 'virus', 'web', cari(RE_HACKED), (b'hacked', b'hack3d')),
    ('VD.WP.PluginPalsu', 'Plugin samaran (Locale Perf / cachepress dkk.)', 'virus', 'php', cari(RE_LOCALE), (b'locale', b'cachepress', b'craft-harvester', b'widget-compat', b'anti-db-wipe')),
    ('VD.WP.LinkHelper', 'Botnet backlink WP-LinkHelper (wlh)', 'virus', 'php', cari(RE_WLH), (b'wlh_', b'wp-linkhelper')),
    ('VD.W2S.Penanda', 'Alat/pemuat kampanye wp2shell', 'virus', PHP | {'htaccess'}, cari(RE_W2S), (b'2duan_start', b'wp2shell', b'wpbworm', b'wpbatchworm', b'fm_cache_', b'b26_wp_mu', b'wfc_dp_', b'll_autocreate', b'?api=%s', b'pjcpmfsd8b')),
    ('VD.PHP.EvalClosure', 'Closure yang meng-eval argumennya', 'virus', 'php', cari(RE_EVAL_CLOSURE), (b'eval', b'assert')),
    ('VD.PHP.GlobalsExplode', 'Tabel fungsi $GLOBALS[O0..] = explode() (pemuat O00OO)', 'virus', 'php', cari(RE_GLOBALS_EXPLODE), (b'explode',)),
    ('VD.PHP.StrrevFungsi', 'Nama fungsi berbahaya dibalik strrev()', 'virus', 'php', cari(RE_STRREV_FUNGSI), (b'strrev',)),
    ('VD.Webshell.HexNama', 'Nama fungsi webshell dalam string hex', 'virus', 'php', hex_fungsi, (b'66696c65', b'7068705f', b'756e6c696e6b')),
    ('VD.PHP.EvalDekripsi', "eval('?>' . openssl_decrypt(...))", 'virus', 'php', eval_tag_dekripsi, (b'openssl_decrypt',)),
    ('VD.SEO.PintuTDS', 'Pintu TDS: data pengunjung dikirim ke API luar, balasan dicetak', 'virus', 'php', pintu_tds, (b'gzuncompress',)),
    ('VD.Htaccess.KunciShell', '.htaccess menolak PHP lain & mengizinkan shell', 'virus', {'htaccess'}, cari(RE_HT_KUNCI), (b'filesmatch',)),
    ('VD.WP.SembunyiAdmin', 'Menyembunyikan akun wp_* dari daftar Users', 'virus', 'php', sembunyi_user, (b'esc_like',)),
    ('VD.PHP.VariabelO0', 'Pemuat O00OO (variabel O/0 + urldecode)', 'virus', 'php', cari(RE_VAR_O0), (b'o00', b'0o0', b'o0o')),
    ('VD.WP.PintuBelakangMU', 'mu-plugin pintu belakang (salin diri/pemulih dari luar)', 'virus', 'php', cari(RE_MU_BELAKANG), (b'mu_protector', b'lf_sync_mu', b'curlopt_lf_test', b'mu guardian')),
    ('VD.PHP.LoaderSecurePlugin', 'Pemuat SecurePlugin*/Loader* (index.php diganti, montesso 23 Okt)', 'virus', 'php', cari(RE_LOADER_SP), (b'secureplugin', b'class loader')),
    ('VD.Webshell.PtrElem', 'Shell $key="ptr" tulis .elem lalu include', 'virus', 'php', ptr_elem, (b'"ptr"', b"'ptr'")),
    ('VD.Webshell.FmRoot', 'File manager mandiri FM_ROOT/.fm_key', 'virus', 'php', fm_root, (b'fm_root',)),
    ('VD.WP.LoginAdminAcak', 'Login otomatis sebagai administrator mana saja', 'virus', 'php', login_admin_acak, (b'%administrator%',)),
    ('VD.WP.BuatUserGet', 'Membuat akun dari parameter URL (user/pass)', 'virus', 'php', buat_user_get, (b'_user(',)),
    ('VD.PHP.PetaEval', 'Payload dipecah $__map[kN] lalu di-eval', 'virus', 'php', peta_eval, (b'$__map',)),
    ('VD.Webshell.StrSplit', 'Nama fungsi berkas dirakit str_split (file manager samaran)', 'virus', 'php', cari(RE_STR_SPLIT), (b'str_split',)),
    ('VD.PHP.ArrayBase64', 'Payload base64 dipecah dalam array + eval', 'virus', 'php', array_b64, (b'eval', b'assert', b'create_function')),
    ('VD.Backlink.Rot13', 'Backlink tersembunyi str_rot13', 'virus', 'php', cari(RE_ROT13_URL), (b'str_rot13',)),
    ('VD.PHP.RantaiChr', 'Rantai chr() (webshell disamarkan)', 'virus', 'php', rantai_chr, (b'chr(',)),
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
    ('VD.JS.AlihAtob', 'Pengalih TDS: script src dari atob()', 'virus', TEKS_JUDI | {'php', 'js'}, cari(RE_SRC_ATOB), (b'atob',)),
    ('VD.WP.SuntikRemote', 'Cetak .txt situs luar di wp_footer/wp_head', 'virus', 'php', suntik_remote, (b'wp_footer', b'wp_head')),
    ('VD.JS.Suntik', 'JavaScript tersuntik (fromCharCode)', 'curiga', {'js'}, js_suntik, (b'fromcharcode',)),
    ('VD.WP.SisipanHomeText', 'mu-plugin sisipan tautan Home Text (wp2shell)', 'curiga', 'php', cari(RE_HOME_TEXT), (b'hti_',)),
]


def ekstensi(nama):
    # wp2shell menamai ulang berkas asli jadi index.php__01bd3b5 (salinan pemuat ikut) → nilai sebagai ekstensi aslinya
    nama = RE_SUFIKS_W2S.sub('', nama)
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

# Admin siluman: akun administrator buatan plugin samaran (wp-cachepress: backup_manager/cache_sync/maria@<domain>)
# dan alat pembobol (w2s_xxxx@wp2shell.invalid). Pola nama "Roger"/roger013@yahoo.com bisa milik orang asli → curiga.
ADMIN_SILUMAN = {'backup_manager', 'cache_sync'}
RE_ADMIN_EMAIL = re.compile(r'@(wordpress\.org|[\w.-]+\.invalid)$', re.I)
RE_ADMIN_W2S = re.compile(r'^w2s_[0-9a-f]{6,}$')
RE_ADMIN_NAMA = re.compile(r'^[A-Z][a-z]{2,11}$')
RE_ADMIN_EMAIL_NAMA = r'^%s\d{1,4}@(gmail|yahoo|hotmail|outlook)\.com$'
TANDA_ADMIN = [('VD.DB.AdminSiluman', 'Database: admin siluman (plugin samaran/pembobol)', 'virus'),
               ('VD.DB.AdminCuriga', 'Database: admin baru pola nama+angka', 'curiga')]


def admin_siluman(login, email, umur):
    """(tanda, bukti) atau None. umur = umur akun dalam hari."""
    if login in ADMIN_SILUMAN or RE_ADMIN_EMAIL.search(email) or RE_ADMIN_W2S.match(login) \
            or (login == 'maria' and email.lower().startswith('maria@')):
        return TANDA_ADMIN[0], '%s <%s>' % (login, email)
    if umur <= 120 and RE_ADMIN_NAMA.match(login) and re.match(RE_ADMIN_EMAIL_NAMA % re.escape(login.lower()), email.lower()):
        return TANDA_ADMIN[1], '%s <%s> · terdaftar %d hari lalu' % (login, email, umur)
    return None


def sql_admin(p):
    return ("SELECT u.ID, UNIX_TIMESTAMP(u.user_registered), u.user_login, u.user_email FROM `%susers` u "
            "JOIN `%susermeta` m ON m.user_id = u.ID AND m.meta_key = '%scapabilities' "
            "AND m.meta_value LIKE '%%\"administrator\"%%' ORDER BY u.ID LIMIT 500" % (p, p, p))


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


def mysql_cnf(k):
    """Berkas opsi sementara (0600) berisi sandi situs. MYSQL_PWD kalah oleh `password=` di /etc/my.cnf atau
    /root/.my.cnf (Fahmi, Cahyadi: semua cek DB gagal). --defaults-file tidak membaca ~/.my.cnf; /etc/my.cnf
    di-include dulu agar socket ikut, lalu sandi situs ditulis sesudahnya supaya menang. Hapus sesudah dipakai."""
    pw = (k.get('DB_PASSWORD') or '').replace('\\', '\\\\').replace('"', '\\"')
    fd, path = tempfile.mkstemp(prefix='vdav-', suffix='.cnf')
    with os.fdopen(fd, 'w') as f:
        if os.path.isfile('/etc/my.cnf'):
            f.write('!include /etc/my.cnf\n')
        f.write('[client]\npassword="%s"\n[mysqldump]\npassword="%s"\n' % (pw, pw))
    return path


def mysql_baris(k, sql):
    host, _, port = (k.get('DB_HOST') or 'localhost').partition(':')
    cnf = mysql_cnf(k)
    cmd = ['mysql', '--defaults-file=' + cnf, '-B', '-N', '--connect-timeout=10', '-u', k['DB_USER'], '-h', host or 'localhost']
    if port.isdigit():
        cmd += ['-P', port]
    try:
        r = subprocess.run(cmd + [k['DB_NAME'], '-e', sql], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    finally:
        os.unlink(cnf)
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
        # Admin siluman tanpa batas hari: akun lama tetap pintu masuk selama belum dihapus
        try:
            admin = mysql_baris(k, sql_admin(p))
        except Exception:
            admin = []
        for b in admin:
            if len(b) < 4:
                continue
            uid, waktu, login, email = b[0].decode(), b[1].decode(), b[2].decode('utf-8', 'replace'), b[3].decode('utf-8', 'replace')
            w = int(waktu) if waktu.isdigit() else 0
            cocok = admin_siluman(login, email, int((time.time() - w) / 86400) if w else 9999)
            if not cocok:
                continue
            (tid, nama, tingkat), bukti = cocok
            lokasi = '%s#db:%susers:%s' % (akar, p, uid)
            sha = hashlib.sha256(('%s\n%s' % (login, email)).encode()).hexdigest()
            if aman.get(lokasi) == sha:
                hit['aman'] += 1
                continue
            temuan.append({'path': lokasi, 'user': user, 'ukuran': 0, 'mtime': w, 'ctime': w, 'sha256': sha, 'izin': '-',
                           'tingkat': tingkat, 'tanda': [{'id': tid, 'nama': nama, 'tingkat': tingkat, 'bukti': bukti[:160]}],
                           'db': {'nama': k['DB_NAME'], 'tabel': p + 'users', 'id': uid, 'jenis': 'administrator',
                                  'judul': '%s <%s>' % (login, email), 'login': login, 'email': email}})
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


INFO_TANDA = [{'id': t[0], 'nama': t[1], 'tingkat': t[2]} for t in TANDA + TANDA_DB + TANDA_ADMIN + TANDA_WEB]


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
    putih = p.get('putih') or []
    asli = p.get('asli') or {}
    hit = {'berkas': 0, 'dibaca': 0, 'folder': 0, 'byte': 0, 'aman': 0, 'db': 0, 'db_gagal': 0, 'situs': 0, 'situs_gagal': 0,
           'besar': 0, 'besar_gambar': 0, 'besar_inti': 0, 'besar_sebagian': 0}
    besar = []
    periksa_db_aktif = p.get('db', True)
    periksa_web_aktif = p.get('web', True)
    # berkas=False (scan harian bila watcher realtime aktif): berkas sudah diperiksa saat ditulis → hanya DB & beranda
    periksa_berkas = p.get('berkas', True)
    temuan = []
    terpotong = None
    lapor = 0
    for ia, user in enumerate(daftar):
        akar = akar_akun(user)
        wpconfig = [] if periksa_berkas else sorted(set(glob.glob(os.path.join(akar, '*', 'public_html', 'wp-config.php'))
                                                     + glob.glob(os.path.join(akar, '*', 'public_html', '*', 'wp-config.php'))
                                                     + glob.glob(os.path.join(akar, '*', 'public_html', '*', '*', 'wp-config.php'))))
        for folder, dirs, files in (os.walk(akar) if periksa_berkas else ()):
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
                if putih and di_putih(path, putih):
                    hit['aman'] += 1
                    continue
                try:
                    st = os.lstat(path)
                except OSError:
                    continue
                if not (st.st_mode & 0o170000 == 0o100000) or st.st_size == 0:
                    continue
                if sejak and max(st.st_mtime, st.st_ctime) < sejak:
                    continue
                # Sisipan PHP di gambar biasanya berkas kecil; gambar besar dilewati agar scan tak membaca GB foto
                if ext in GAMBAR and st.st_size > 262144:
                    hit['besar_gambar'] += 1
                    continue
                maks = 1048576 if tersembunyi or ext in ('html', 'htm', 'js', 'txt') else MAKS_BACA
                sebagian = st.st_size > maks
                if sebagian and not tersembunyi and (inti_wp_asli(path, st) or hash_asli(path, st, asli)):
                    hit['besar_inti'] += 1
                    continue
                try:
                    if sebagian:
                        teks = baca_sebagian(path, st.st_size)
                        hit['besar_sebagian'] += 1
                    else:
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
                if sebagian and not tanda:
                    hit['besar'] += 1
                    if len(besar) < MAKS_BESAR:
                        besar.append({'path': path, 'user': user, 'ukuran': st.st_size, 'mtime': int(st.st_mtime),
                                      'ctime': int(st.st_ctime), 'izin': oct(st.st_mode & 0o777)[2:], 'batas': maks,
                                      'sebagian': 'bersih'})
                if tanda:
                    try:
                        sha = hash_berkas(path) if sebagian else hashlib.sha256(teks).hexdigest()
                    except OSError:
                        continue
                    if aman.get(path) == sha:
                        hit['aman'] += 1
                        continue
                    temuan.append({'path': path, 'user': user, 'ukuran': st.st_size, 'mtime': int(st.st_mtime), 'sha256': sha,
                                   'ctime': int(st.st_ctime), 'izin': oct(st.st_mode & 0o777)[2:],
                                   'tingkat': 'virus' if any(t['tingkat'] == 'virus' for t in tanda) else 'curiga',
                                   'tanda': tanda, **({'sebagian': True} if sebagian else {})})
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
        if not periksa_berkas and time.time() - lapor >= 2:
            lapor = time.time()
            kemajuan({'akun': user, 'ke': ia + 1, 'dari': len(daftar), 'temuan': len(temuan), **hit})
        if not periksa_berkas and time.time() - mulai > batas:
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
    simpan_inti_cache()
    return {'ok': True, 'akun': akun, 'hari': hari, 'detik': round(time.time() - mulai, 1), 'terpotong': terpotong,
            'jumlah_akun': len(daftar), 'temuan': temuan, 'daftar_besar': besar, **hit}


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


def di_putih(path, putih):
    """Whitelist dashboard: [{'path', 'jenis': 'berkas'|'folder'}] — berkas persis, folder = semua isinya."""
    for w in putih or ():
        x = w.get('path') or ''
        if x and (path == x or (w.get('jenis') == 'folder' and path.startswith(x.rstrip('/') + '/'))):
            return True
    return False


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
    # Karantina otomatis (ingat karantina) mengirim sha256 temuan: berkas yang sudah ditimpa isi lain tidak disentuh
    if p.get('sha256') and hashlib.sha256(isi).hexdigest() != p['sha256']:
        return {'ok': False, 'error': 'berkas_berubah'}
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
    return {'ok': True, 'id': kid, 'path': path, 'sha256': meta['sha256']}


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
    return {'ok': True, 'path': path, 'sha256': meta.get('sha256')}


def hapus(p):
    folder, meta = entri(p.get('id'))
    if not meta:
        return {'ok': False, 'error': 'karantina_tidak_ada'}
    shutil.rmtree(folder)
    return {'ok': True, 'path': meta['path']}


# Bersihkan WP: karantina plugin samaran, hapus admin siluman (postingannya dialihkan ke admin asli), ganti salt
# wp-config + hapus semua session_tokens. Semua lewat SQL/Python — tidak menjalankan PHP situs yang terinfeksi.
# Cadangan (tabel users+usermeta, wp-config.php, daftar post yang dialihkan) di /root/velocity-bersih/<id>/.
BERSIH = '/root/velocity-bersih'
PLUGIN_SAMARAN = {'VD.WP.PluginPalsu', 'VD.WP.LinkHelper', 'VD.WP.LoginPaksa', 'VD.Webshell.Nama', 'VD.PHP.EvalInput'}
KUNCI_SALT = ('AUTH_KEY', 'SECURE_AUTH_KEY', 'LOGGED_IN_KEY', 'NONCE_KEY', 'AUTH_SALT', 'SECURE_AUTH_SALT', 'LOGGED_IN_SALT', 'NONCE_SALT')


def akar_wp(path):
    """Folder WordPress (berisi wp-config.php) di /home/<akun>/domains/<domain>/public_html[/...]."""
    asli = os.path.realpath(path or '')
    bagian = asli[len(HOME) + 1:].split('/')
    if '\0' in (path or '') or asli != os.path.normpath(path or '/') or not asli.startswith(HOME + '/') \
            or len(bagian) < 4 or bagian[1] != 'domains' or bagian[3] != 'public_html':
        return None, None
    wpc = os.path.join(asli, 'wp-config.php')
    if os.path.islink(wpc) or not os.path.isfile(wpc):
        return None, None
    return asli, bagian[0]


def plugin_samaran(akar):
    hasil = []
    for sub in ('plugins', 'mu-plugins'):
        dasar = os.path.join(akar, 'wp-content', sub)
        for d, folder, fs in os.walk(dasar):
            if d[len(dasar):].count('/') >= 2:  # plugin samaran = 1 berkas di akar folder plugin
                folder[:] = []
                continue
            folder[:] = [x for x in folder if x not in ('node_modules', 'vendor')]
            for f in fs:
                path = os.path.join(d, f)
                if ekstensi(f) != 'php' or os.path.islink(path) or os.path.getsize(path) > MAKS_BACA:
                    continue
                with open(path, 'rb') as fh:
                    tanda = [x['id'] for x in periksa(path, 'php', fh.read()) if x['id'] in PLUGIN_SAMARAN]
                if tanda:
                    hasil.append((path, tanda))
    return hasil


def ganti_salt(wpc):
    import secrets
    abjad = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#%^&*()-_[]{}<>~+=,.;:/?|'
    with open(wpc, 'rb') as f:
        teks = f.read()
    n = 0
    for kunci in KUNCI_SALT:
        baru = ''.join(secrets.choice(abjad) for _ in range(64)).encode()
        teks, k = re.subn(rb"(define\s*\(\s*['\"]%s['\"]\s*,\s*)(['\"]).*?(?<!\\)\2" % kunci.encode(),
                          lambda m: m.group(1) + b"'" + baru + b"'", teks, count=1, flags=re.S)
        n += k
    if n:
        st = os.stat(wpc)
        tmp = wpc + '.velocity-salt'
        with open(tmp, 'wb') as f:
            f.write(teks)
        os.chown(tmp, st.st_uid, st.st_gid)
        os.chmod(tmp, st.st_mode & 0o7777)
        os.replace(tmp, wpc)
    return n


def bersihkan_wp(p):
    akar, user = akar_wp(p.get('akar'))
    if not akar:
        return {'ok': False, 'error': 'path_tidak_sah'}
    k = wp_kredensial(os.path.join(akar, 'wp-config.php'))
    if not k:
        return {'ok': False, 'error': 'wp_config_tidak_terbaca'}
    with open(os.path.join(akar, 'wp-config.php'), 'rb') as f:
        if re.search(rb"define\s*\(\s*['\"](MULTISITE|WP_ALLOW_MULTISITE)['\"]\s*,\s*true", f.read(), re.I):
            return {'ok': False, 'error': 'multisite_tidak_didukung'}
    pr = k['prefix']
    try:
        hapus_id = sorted({int(x) for x in p.get('hapus_user') or []})[:50]
        # turunkan_user: admin curiga (bisa saja milik klien) cukup jadi subscriber, tidak dihapus
        turun_id = sorted({int(x) for x in p.get('turunkan_user') or []} - set(hapus_id))[:50]
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'id_user_tidak_sah'}
    admin = [int(b[0]) for b in mysql_baris(k, sql_admin(pr)) if b and b[0].isdigit()]
    if hapus_id or turun_id:
        minta = hapus_id + turun_id
        ada = {int(b[0]) for b in mysql_baris(k, 'SELECT ID FROM `%susers` WHERE ID IN (%s)' % (pr, ','.join(map(str, minta))))}
        if set(minta) - ada:
            return {'ok': False, 'error': 'user_tidak_ada', 'id': sorted(set(minta) - ada)}
    sisa = [i for i in admin if i not in hapus_id and i not in turun_id]
    if (hapus_id or turun_id) and not sisa:
        return {'ok': False, 'error': 'admin_asli_tidak_ada'}

    bid = time.strftime('%Y%m%d-%H%M%S') + '-' + hashlib.sha1(akar.encode()).hexdigest()[:8]
    cadangan = os.path.join(BERSIH, bid)
    os.makedirs(cadangan, mode=0o700)
    os.chmod(BERSIH, 0o700)
    shutil.copy2(os.path.join(akar, 'wp-config.php'), os.path.join(cadangan, 'wp-config.php'))
    host, _, port = (k.get('DB_HOST') or 'localhost').partition(':')
    cnf = mysql_cnf(k)
    cmd = ['mysqldump', '--defaults-file=' + cnf, '--single-transaction', '--skip-lock-tables', '-u', k['DB_USER'], '-h', host or 'localhost']
    if port.isdigit():
        cmd += ['-P', port]
    try:
        with open(os.path.join(cadangan, 'users.sql'), 'wb') as f:
            r = subprocess.run(cmd + [k['DB_NAME'], pr + 'users', pr + 'usermeta'], stdout=f, stderr=subprocess.PIPE, timeout=300)
    finally:
        os.unlink(cnf)
    if r.returncode or os.path.getsize(os.path.join(cadangan, 'users.sql')) < 100:
        return {'ok': False, 'error': 'cadangan_gagal', 'pesan': r.stderr.decode('utf-8', 'replace')[:200], 'cadangan': cadangan}

    lap = {'akar': akar, 'user': user, 'waktu': int(time.time()), 'oleh': str(p.get('oleh') or '')[:40],
           'karantina': [], 'hapus_user': [], 'turun_user': [], 'dialihkan_ke': None, 'post_dialihkan': [], 'salt': 0, 'sesi': False}
    try:
        if p.get('plugin'):
            for path, tanda in plugin_samaran(akar):
                r = karantina({'path': path, 'oleh': p.get('oleh'), 'alasan': 'Bersihkan WP: ' + ', '.join(tanda)})
                lap['karantina'].append({'path': path, 'tanda': tanda, 'ok': r.get('ok'), 'id': r.get('id'), 'sha256': r.get('sha256'), 'error': r.get('error')})
        if hapus_id:
            daftar = ','.join(map(str, hapus_id))
            lap['hapus_user'] = [{'id': int(b[0]), 'login': b[1].decode('utf-8', 'replace'), 'email': b[2].decode('utf-8', 'replace')}
                                 for b in mysql_baris(k, 'SELECT ID, user_login, user_email FROM `%susers` WHERE ID IN (%s)' % (pr, daftar))]
            lap['dialihkan_ke'] = sisa[0]
            lap['post_dialihkan'] = [[int(b[0]), int(b[1])] for b in mysql_baris(
                k, 'SELECT ID, post_author FROM `%sposts` WHERE post_author IN (%s)' % (pr, daftar))]
            mysql_baris(k, 'START TRANSACTION; UPDATE `{p}posts` SET post_author = {r} WHERE post_author IN ({d}); '
                           'DELETE FROM `{p}usermeta` WHERE user_id IN ({d}); DELETE FROM `{p}users` WHERE ID IN ({d}); COMMIT'
                        .format(p=pr, r=sisa[0], d=daftar))
        if turun_id:
            daftar = ','.join(map(str, turun_id))
            lap['turun_user'] = [{'id': int(b[0]), 'login': b[1].decode('utf-8', 'replace'), 'email': b[2].decode('utf-8', 'replace')}
                                 for b in mysql_baris(k, 'SELECT ID, user_login, user_email FROM `%susers` WHERE ID IN (%s)' % (pr, daftar))]
            mysql_baris(k, "START TRANSACTION; UPDATE `{p}usermeta` SET meta_value = 'a:1:{{s:10:\"subscriber\";b:1;}}' "
                           "WHERE user_id IN ({d}) AND meta_key = '{p}capabilities'; "
                           "UPDATE `{p}usermeta` SET meta_value = '0' WHERE user_id IN ({d}) AND meta_key = '{p}user_level'; "
                           "DELETE FROM `{p}usermeta` WHERE user_id IN ({d}) AND meta_key = 'session_tokens'; COMMIT".format(p=pr, d=daftar))
        if p.get('salt'):
            lap['salt'] = ganti_salt(os.path.join(akar, 'wp-config.php'))
            mysql_baris(k, "DELETE FROM `%susermeta` WHERE meta_key = 'session_tokens'" % pr)
            lap['sesi'] = True
    except Exception as e:
        lap['error'] = str(e)[:300]
    with open(os.path.join(cadangan, 'laporan.json'), 'w') as f:
        json.dump(lap, f)
    lap['post_dialihkan'] = len(lap['post_dialihkan'])
    return dict(lap, ok='error' not in lap, cadangan=cadangan, id=bid, path=akar)


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


# Judi AI (services/server_judi.py): bukti per akun untuk dinilai AI di dashboard + suspend/unsuspend akun DirectAdmin.
DA_BIN = '/usr/local/directadmin/directadmin'
RE_TAG_BUANG = re.compile(rb'<(script|style|noscript|svg)\b.*?</\1\s*>', re.I | re.S)
RE_JUDUL = re.compile(rb'<title[^>]*>(.*?)</title>', re.I | re.S)
RE_POTONG_JUDI = r(r'slot|togel|judi|maxwin|gacor|casino|kasino|sbobet|toto|http_user_agent|googlebot|base64_decode|eval\s*\(')


def teks_halaman(isi, maks=2500):
    import html as _html
    m = RE_JUDUL.search(isi)
    judul = _html.unescape(re.sub(r'\s+', ' ', m.group(1).decode('utf-8', 'replace'))).strip()[:200] if m else ''
    isi = RE_TAG_BUANG.sub(b' ', isi)
    teks = _html.unescape(re.sub(rb'<[^>]+>', b' ', isi).decode('utf-8', 'replace'))
    return judul, re.sub(r'\s+', ' ', teks).strip()[:maks]


def status_suspend(user):
    try:
        with open('/usr/local/directadmin/data/users/%s/user.conf' % user, errors='replace') as f:
            return any(b.strip() == 'suspended=yes' for b in f)
    except OSError:
        return False


def akun_ada(user):
    return bool(user) and re.match(r'^[a-z0-9_][a-z0-9_.-]{0,31}$', user) and any(a['user'] == user for a in akun_da())


def cari_sumber(akar):
    """Scan penuh wp-content (tanpa batas umur berkas) untuk penyuntik beranda: plugin lama tak masuk scan harian."""
    hasil, n = [], 0
    for sub in ('mu-plugins', 'plugins', 'themes'):
        for d, folder, fs in os.walk(os.path.join(akar, 'wp-content', sub)):
            folder[:] = [x for x in folder if x not in ('node_modules', 'vendor', 'cache')]
            for f in fs:
                ext = ekstensi(f)
                if ext not in ('php', 'js') or n >= 30000:
                    continue
                path = os.path.join(d, f)
                n += 1
                try:
                    if os.path.islink(path) or os.path.getsize(path) > MAKS_BACA:
                        continue
                    with open(path, 'rb') as fh:
                        teks = fh.read()
                except OSError:
                    continue
                tanda = [h for h in periksa(path, ext, teks) if h['tingkat'] == 'virus']
                if tanda:
                    hasil.append({'path': path, 'tanda': [h['id'] for h in tanda], 'bukti': tanda[0]['bukti'][:120]})
                    if len(hasil) >= 10:
                        return hasil
    return hasil


def bukti_judi(p):
    user = p.get('user') or ''
    if not akun_ada(user):
        return {'ok': False, 'error': 'akun_tidak_dikenal'}
    akun = next(a for a in akun_da() if a['user'] == user)
    domain = [d for d in akun['domain'] if d not in ('default', 'sharedip', 'suspended')]
    utama = [d for d in (p.get('domains') or []) if d in domain]
    web = []
    # hanya_berkas: batch lanjutan Analisis AI cukup isi berkas, beranda sudah diambil panggilan pertama
    for d in [] if p.get('hanya_berkas') else (utama + [x for x in domain if x not in utama])[:3]:
        if not os.path.isdir(os.path.join(akar_akun(user), d, 'public_html')):
            continue
        ip = ip_domain(user, d)
        kb, ab, ib = ambil(d, ip, UA_BROWSER)
        # Alih ke www/https domain sendiri → ambil halaman tujuannya (yang dilihat pengunjung)
        tuju = host_url(ab) if kb[:1] == '3' and domain_sama(host_url(ab), d) else d
        if tuju != d:
            kb, ab, ib = ambil(tuju, ip, UA_BROWSER)
        kg, ag, ig = ambil(tuju, ip, UA_GOOGLEBOT)
        kh, ah, _ = ambil(tuju, ip, UA_HP, 'https://www.google.com/')
        ab, ag, ah = [re.sub(r'[?&]vcek=\d+', '', x or '') for x in (ab, ag, ah)]
        jb, jg = kata_judi(ib), kata_judi(ig)
        judul, teks = teks_halaman(ib)
        judul_bot, teks_bot = teks_halaman(ig)
        beda = judul_bot != judul or len(jg - jb) >= 2 or (ag or '') != (ab or '')
        sembunyi = bool(link_judi_sembunyi(ib + b'\n' + ig, ''))
        masih = sembunyi or len(jb) >= 3 or len(jg) >= 3
        web.append({'domain': d, 'kode': kb, 'alih': ab, 'judul': judul, 'teks': teks, 'judi_browser': len(jb),
                    'beda_bot': beda, 'judul_bot': judul_bot if beda else '', 'teks_bot': teks_bot if beda else '',
                    'alih_bot': ag, 'judi_bot': len(jg), 'judi_sembunyi': sembunyi,
                    'sumber': cari_sumber(os.path.join(akar_akun(user), d, 'public_html')) if masih else [],
                    'alih_hp': ah if ah and not domain_sama(host_url(ah), d) and host_url(ah) != host_url(ab) else ''})
    berkas = []
    for path in (p.get('paths') or [])[:15]:
        asli = os.path.realpath(path)
        if not asli.startswith('%s/%s/' % (HOME, user)) or os.path.islink(path) or not os.path.isfile(asli):
            continue
        with open(asli, 'rb') as f:
            isi = f.read(262144)
        teks = isi.decode('utf-8', 'replace')
        bagian = [teks[:300]]
        for m in RE_POTONG_JUDI.finditer(isi):
            if len(bagian) >= 4:
                break
            awal = len(isi[:max(0, m.start() - 150)].decode('utf-8', 'replace'))
            if awal > 300:
                bagian.append('… ' + teks[awal:awal + 300])
        berkas.append({'path': path, 'ukuran': os.path.getsize(asli), 'potongan': re.sub(r'\s+', ' ', ' '.join(bagian))[:1200]})
    return {'ok': True, 'user': user, 'domain': domain, 'suspended': status_suspend(user), 'web': web, 'berkas': berkas}


def ubah_suspend(p, jadi):
    user = p.get('user') or ''
    if not akun_ada(user):
        return {'ok': False, 'error': 'akun_tidak_dikenal'}
    if status_suspend(user) == jadi:
        return {'ok': True, 'user': user, 'suspended': jadi, 'catatan': 'sudah'}
    perintah = [DA_BIN, 'suspend-user', '--user=' + user, '--reason=abuse'] if jadi else [DA_BIN, 'unsuspend-user', '--user=' + user]
    r = subprocess.run(perintah, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    if jadi and status_suspend(user) != jadi:
        # Alasan 'abuse' tak dikenal di versi DA lain → ulang tanpa alasan
        r = subprocess.run(perintah[:3], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    if status_suspend(user) != jadi:
        return {'ok': False, 'error': 'da_gagal', 'pesan': r.stdout.decode('utf-8', 'replace')[-300:]}
    return {'ok': True, 'user': user, 'suspended': jadi}


def admin_masih_ada(path):
    """Temuan admin siluman `<akar>#db:<prefix>users:<id>`: ada=False bila wp-config.php sudah hilang
    atau user itu bukan administrator lagi (ditangani manual). tanda=None = tidak bisa dicek (DB galat)."""
    akar, _, sisa = path.partition('#db:')
    tabel, _, uid = sisa.rpartition(':')
    if not uid.isdigit() or not tabel.endswith('users'):
        return {'ada': True, 'tanda': None}
    konfig = os.path.join(akar, 'wp-config.php')
    if not os.path.isfile(konfig):
        return {'ada': False}
    k = wp_kredensial(konfig)
    if not k or k['prefix'] + 'users' != tabel:
        return {'ada': True, 'tanda': None}
    try:
        b = mysql_baris(k, sql_admin(k['prefix']).replace(' ORDER BY', ' WHERE u.ID = %s ORDER BY' % uid))
    except Exception:
        return {'ada': True, 'tanda': None}
    return {'ada': True, 'tanda': None} if b else {'ada': False}


def periksa_ulang(p):
    """Baca ulang berkas temuan lama (hanya baca) dan periksa dengan tanda tangan VD.* saat ini.
    Hasil per path: ada=False bila berkas sudah tidak ada, selain itu tanda (id) + sha256 isi sekarang."""
    hasil = {}
    putih = p.get('putih') or []
    asli = p.get('asli') or {}
    for path in (p.get('paths') or [])[:3000]:
        if path.startswith(HOME + '/') and '#db:' in path:
            hasil[path] = admin_masih_ada(path)
            continue
        if not path.startswith(HOME + '/') or '#' in path:
            continue
        if di_putih(path, putih):
            hasil[path] = {'ada': os.path.lexists(path), 'tanda': [], 'putih': True}
            continue
        try:
            st = os.lstat(path)
        except OSError:
            hasil[path] = {'ada': False}
            continue
        if not (st.st_mode & 0o170000 == 0o100000):
            hasil[path] = {'ada': True, 'tanda': None}
            continue
        nama = os.path.basename(path)
        ext = ekstensi(nama)
        tersembunyi = ext not in EKSTENSI and nama.startswith('.')
        # Batas baca sama dengan scan: di atas batas → awal + akhir saja
        sebagian = st.st_size > (1048576 if tersembunyi or ext in ('html', 'htm', 'js', 'txt') else MAKS_BACA)
        # Sama dengan scan: berkas inti WP besar yang cocok checksum resmi = asli
        if sebagian and not tersembunyi and (inti_wp_asli(path, st) or hash_asli(path, st, asli)):
            hasil[path] = {'ada': True, 'inti': True, 'tanda': []}
            continue
        try:
            if sebagian:
                teks, sha = baca_sebagian(path, st.st_size), hash_berkas(path)
            else:
                with open(path, 'rb') as f:
                    teks = f.read()
                sha = hashlib.sha256(teks).hexdigest()
        except OSError:
            hasil[path] = {'ada': True, 'tanda': None}
            continue
        if tersembunyi and b'<?php' in teks[:256]:
            ext = 'php'
        hasil[path] = {'ada': True, 'sha256': sha, 'tanda': [x['id'] for x in periksa(path, ext, teks)]}
    simpan_inti_cache()
    return {'ok': True, 'hasil': hasil}


RT_DATA = '/var/lib/velocity-av'


def realtime_setelan(p):
    """Tulis setelan watcher realtime (mode laporan/otomatis + whitelist) persis seperti dikirim dashboard
    (dashboard membandingkan sha256 isi berkas dengan `setelan` di detak)."""
    isi = p.get('isi')
    if not isinstance(isi, str) or len(isi) > 1000000:
        return {'ok': False, 'error': 'isi_tidak_sah'}
    json.loads(isi)
    os.makedirs(RT_DATA, mode=0o700, exist_ok=True)
    tmp = os.path.join(RT_DATA, 'setelan.json.tmp')
    with open(tmp, 'w') as f:
        f.write(isi)
    os.chmod(tmp, 0o600)
    os.replace(tmp, os.path.join(RT_DATA, 'setelan.json'))
    return {'ok': True, 'sha256': hashlib.sha256(isi.encode()).hexdigest()[:12]}


def realtime(p):
    """Status watcher realtime (scripts/velocity_av_realtime.py) + temuan baru sejak offset byte temuan.jsonl."""
    r = subprocess.run(['systemctl', 'is-active', 'velocity-av-realtime'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    out = {'ok': True, 'aktif': r.stdout.decode().strip()}
    try:
        with open(os.path.join(RT_DATA, 'detak.json')) as f:
            out['detak'] = json.load(f)
    except (OSError, ValueError):
        out['detak'] = None
    path = os.path.join(RT_DATA, 'temuan.jsonl')
    try:
        ukuran = os.path.getsize(path)
    except OSError:
        ukuran = 0
    offset = int(p.get('offset') or 0)
    if offset > ukuran:  # berkas diputar ke .1
        offset = 0
    baris = []
    if ukuran > offset:
        with open(path, 'rb') as f:
            f.seek(offset)
            data = f.read(2000000)
        potong_di = data.rfind(b'\n') + 1
        offset += potong_di
        for b in data[:potong_di].splitlines():
            try:
                baris.append(json.loads(b.decode('utf-8', 'replace')))
            except ValueError:
                pass
    out.update(temuan=baris[-500:], offset=offset)
    return out


AKSI = {'baca': baca, 'ringkas': ringkas, 'scan': scan, 'karantina': karantina, 'kembalikan': kembalikan, 'hapus': hapus,
        'bersihkan_wp': bersihkan_wp,
        'bukti_judi': bukti_judi, 'realtime': realtime, 'periksa_ulang': periksa_ulang,
        'realtime_setelan': realtime_setelan, 'suspend': lambda p: ubah_suspend(p, True), 'unsuspend': lambda p: ubah_suspend(p, False)}


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
