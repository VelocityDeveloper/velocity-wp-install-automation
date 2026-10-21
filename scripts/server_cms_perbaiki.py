# -*- coding: utf-8 -*-
"""Perbaiki kerentanan CMS (WordPress) di satu akun hosting (dijalankan di server lewat `ssh ... python3 -`).

Dipakai tombol "Perbaiki" halaman /server/cms (services/server_cms.py → POST /api/servers/cms/perbaiki).
Pemanggil menambahkan `jalankan(<perintah base64 JSON>)` di akhir kode ini. Setiap situs selesai dicetak satu
baris JSON {"situs": {...}}; baris terakhir = ringkasan {"ok": ...}. Harus jalan di Python 3.6.
BERBEDA dengan server_cms_agent.py (hanya baca), agen ini MENGUBAH situs klien:
1. Cadangan DB (mysqldump kredensial wp-config) + folder plugin/tema yang akan diganti →
   /root/velocity-cadangan/<domain>/cms-perbaiki-<waktu>/. Cadangan gagal → situs dilewati.
2. WP-CLI sebagai pemilik akun (--skip-plugins --skip-themes): plugin & tema rentan diperbarui ke rilis
   terbaru; inti WP mode 'minor' (`core update --minor`, cabang sama) atau 'terbaru' (`core update`, berkas inti
   ikut dicadangkan & dikembalikan bila beranda rusak) + update-db.
3. Beranda dicek sebelum/sesudah; sebelumnya hidup lalu jadi 5xx/mati → folder plugin/tema dikembalikan
   dari cadangan (inti tidak dikembalikan, dilaporkan).
4. Sesudah update tema: blok <style id="*kirki*"> beranda yang hilang (tema velocity ≥2.7 membuang CSS Kirki)
   ditambahkan ke CSS Tambahan.
Pengaman sebelum update (fungsi periksa, juga aksi `cek` hanya baca untuk dialog konfirmasi): komponen dilewati
bila syarat PHP (PHP web situs, bukan PHP CLI) / WP dari wordpress.org tak terpenuhi, perkiraan kebutuhan
melebihi sisa kuota akun, atau Kirki di tabel posts MyISAM (Kirki 6.4 gagal membuat tabel ber-FK, berulang tiap request).
"""
import base64
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

CADANGAN = '/root/velocity-cadangan'
PHAR = '/usr/local/share/velocity/wp-cli.phar'
URL_PHAR = 'https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar'
PHP_CALON = ['/usr/local/php83/bin/php', '/opt/alt/php83/usr/bin/php', '/usr/local/php84/bin/php', '/opt/alt/php84/usr/bin/php',
             '/usr/local/php82/bin/php', '/opt/alt/php82/usr/bin/php', '/usr/local/bin/php', '/usr/bin/php']
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
DA_USERS = '/usr/local/directadmin/data/users'
DA_OPSI = '/usr/local/directadmin/custombuild/options.conf'
PERLU_INTI_MB = 60  # zip + ekstrak di wp-content/upgrade sebelum disalin
PERLU_INTI_TERBARU_MB = 95  # + pertambahan ukuran inti antar versi besar (±25–35 MB)
RE_PHP_HDR = re.compile(r'^x-powered-by:\s*php/(\d+\.\d+)', re.I | re.M)
RE_KIRKI = re.compile(r'<style[^>]*\bid=["\']([^"\']*kirki[^"\']*)["\'][^>]*>(.*?)</style>', re.S | re.I)
RE_VERSI_WP = re.compile(r"\$wp_version\s*=\s*'([^']+)'")
RE_USER = re.compile(r'^[a-z_][a-z0-9_-]{0,31}$')
RE_SLUG = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$')
RE_DEF = re.compile(rb"define\s*\(\s*['\"](DB_NAME|DB_USER|DB_PASSWORD|DB_HOST)['\"]\s*,\s*['\"]((?:\\.|[^'\"\\])*)['\"]")
RE_PREFIX = re.compile(rb"\$table_prefix\s*=\s*['\"]([A-Za-z0-9_]+)['\"]")
BATAS_WP = 600


def lapor(obj):
    sys.stdout.write(json.dumps(obj, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def jalan(cmd, batas=BATAS_WP, **kw):
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=batas, **kw)
        return r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')
    except subprocess.TimeoutExpired:
        return 124, '', 'timeout'


# ---------- WP-CLI ----------

_wpcli = {}


def php_cli(versi):
    """[php, flag...] yang bisa memuat Phar; utamakan versi PHP web situs (WP lama fatal di PHP 8, mis. 4.9
    get_magic_quotes_gpc), lalu PHP_CALON. None bila tak ada."""
    angka = (versi or '').replace('.', '')
    calon = (['/usr/local/php%s/bin/php' % angka, '/opt/alt/php%s/usr/bin/php' % angka] if angka.isdigit() else []) + PHP_CALON
    for php in calon:
        if not os.access(php, os.X_OK):
            continue
        flag = ['-d', 'memory_limit=512M', '-d', 'disable_functions=', '-d', 'max_execution_time=0']
        uji = ['-r', 'exit(class_exists("Phar") ? 0 : 1);']
        if jalan([php] + flag + uji, 30)[0]:
            flag += ['-d', 'extension=phar.so']  # alt-php CloudLinux tanpa phar bawaan
            if jalan([php] + flag + uji, 30)[0]:
                continue
        return [php] + flag
    return None


def siapkan_wp(versi=None):
    """[php, flag..., phar] yang bisa dijalankan pemilik akun, atau None. Disimpan per versi PHP."""
    if versi in _wpcli:
        return _wpcli[versi]
    _wpcli[versi] = _siapkan_wp(versi)
    return _wpcli[versi]


def _siapkan_wp(versi):
    cli = php_cli(versi)
    if not cli:
        return None
    php, flag = cli[0], cli[1:]
    phar = '/usr/local/bin/wp'
    awal = b''
    try:
        with open(phar, 'rb') as f:
            awal = f.read(200)
    except (OSError, IOError):
        pass
    if not (awal.startswith(b'#!') and b'php' in awal.split(b'\n')[0]):
        phar = PHAR
        if not os.path.isfile(phar):
            os.makedirs(os.path.dirname(phar), mode=0o755, exist_ok=True)
            tmp = phar + '.tmp'
            if jalan(['curl', '-fsSL', '--max-time', '120', '-o', tmp, URL_PHAR], 150)[0] or \
                    jalan([php] + flag + [tmp, '--info'], 60)[0]:
                return None
            os.chmod(tmp, 0o644)
            os.rename(tmp, phar)
    return [php] + flag + [phar]


def wp(user, akar, wpcli, args, batas=BATAS_WP):
    sebagai = ['runuser', '-u', user, '--'] if shutil.which('runuser') else ['sudo', '-u', user]
    env = ['env', 'HOME=/home/' + user, 'PATH=/usr/local/bin:/usr/bin:/bin', 'WP_CLI_CACHE_DIR=/tmp/vd-wpcli-' + user]
    return jalan(sebagai + env + wpcli + ['--path=' + akar, '--skip-plugins', '--skip-themes', '--no-color'] + args, batas, cwd='/tmp')


# ---------- Cadangan ----------

def wp_kredensial(path):
    try:
        with open(path, 'rb') as f:
            teks = f.read(200000)
    except (OSError, IOError):
        return None
    d = {k.decode(): re.sub(rb'\\(.)', rb'\1', v).decode('utf-8', 'replace') for k, v in RE_DEF.findall(teks)}
    m = RE_PREFIX.search(teks)
    if not m or not d.get('DB_NAME') or not d.get('DB_USER'):
        return None
    d['prefix'] = m.group(1).decode()
    return d


def kredensial(akar):
    return wp_kredensial(os.path.join(akar, 'wp-config.php')) or wp_kredensial(os.path.join(os.path.dirname(akar), 'wp-config.php'))


def mysql_cmd(k, program):
    """(perintah, berkas opsi). Berkas opsi 0600 agar sandi situs menang atas /root/.my.cnf; hapus sesudah dipakai."""
    pw = (k.get('DB_PASSWORD') or '').replace('\\', '\\\\').replace('"', '\\"')
    fd, cnf = tempfile.mkstemp(prefix='vdcms-', suffix='.cnf')
    with os.fdopen(fd, 'w') as f:
        if os.path.isfile('/etc/my.cnf'):
            f.write('!include /etc/my.cnf\n')
        f.write('[client]\npassword="%s"\n[mysqldump]\npassword="%s"\n' % (pw, pw))
    host, _, port = (k.get('DB_HOST') or 'localhost').partition(':')
    cmd = [program, '--defaults-file=' + cnf, '-u', k['DB_USER'], '-h', host or 'localhost']
    if port.isdigit():
        cmd += ['-P', port]
    return cmd, cnf


def engine_posts(k):
    """ENGINE tabel <prefix>posts ('MyISAM'/'InnoDB'), None bila tak terbaca."""
    cmd, cnf = mysql_cmd(k, 'mysql')
    try:
        kode, out, _ = jalan(cmd + ['-B', '-N', '--connect-timeout=10', k['DB_NAME'], '-e',
                                    "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '%sposts'" % k['prefix']], 60)
    finally:
        os.unlink(cnf)
    return (out.strip() or None) if kode == 0 else None


def dump_db(k, tujuan):
    """mysqldump → tujuan (.sql.gz)."""
    cmd, cnf = mysql_cmd(k, 'mysqldump')
    cmd += ['--single-transaction', '--skip-lock-tables']
    try:
        with gzip.open(tujuan, 'wb') as out:
            p = subprocess.Popen(cmd + [k['DB_NAME']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            for blok in iter(lambda: p.stdout.read(1 << 20), b''):
                out.write(blok)
            galat = p.stderr.read().decode('utf-8', 'replace')
            kode = p.wait()
    finally:
        os.unlink(cnf)
    if kode or os.path.getsize(tujuan) < 200:
        return galat.strip()[:200] or 'dump_kosong'
    return None


def folder_komponen(akar, jenis, slug):
    dasar = os.path.join(akar, 'wp-content', 'plugins' if jenis == 'plugin' else 'themes')
    for nama in (slug, slug + '.php') if jenis == 'plugin' else (slug,):
        p = os.path.join(dasar, nama)
        if os.path.lexists(p) and not os.path.islink(p):
            return p
    return None


def kembalikan(akar, arsip):
    wpc = os.path.join(akar, 'wp-content')
    with tarfile.open(arsip) as t:
        nama = {n.split('/')[0] + '/' + n.split('/')[1] for n in t.getnames() if n.count('/') >= 1}
        for n in nama:
            p = os.path.join(wpc, n)
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            elif os.path.lexists(p):
                os.unlink(p)
        t.extractall(wpc)  # root: pemilik & izin asli ikut kembali


def cadangkan_inti(akar, arsip):
    """Berkas inti: wp-admin, wp-includes, dan berkas di akar (subfolder lain = situs/berkas lain, tidak ikut)."""
    with tarfile.open(arsip, 'w:gz') as t:
        for n in sorted(os.listdir(akar)):
            p = os.path.join(akar, n)
            if n in ('wp-admin', 'wp-includes') or (os.path.isfile(p) and not os.path.islink(p)):
                t.add(p, arcname=n)


def kembalikan_inti(akar, arsip):
    for n in ('wp-admin', 'wp-includes'):
        p = os.path.join(akar, n)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
    with tarfile.open(arsip) as t:
        t.extractall(akar)


# ---------- Cek beranda ----------

def ip_domain(user, domain):
    for berkas, kunci in ((os.path.join(DA_USERS, user, 'domains', domain + '.ip_list'), None), (os.path.join(DA_USERS, user, 'user.conf'), 'ip=')):
        try:
            with open(berkas) as f:
                for baris in f:
                    b = baris.strip()
                    if kunci and b.startswith(kunci):
                        return b[len(kunci):]
                    if not kunci and re.match(r'^[\d.]+$', b):
                        return b
        except (OSError, IOError):
            continue
    return None


def ambil(domain, sub, ip):
    """(kode HTTP, header, HTML) beranda; https lalu http. Query acak agar tak dijawab cache halaman."""
    for skema, port in (('https', 443), ('http', 80)):
        fh, hdr = tempfile.mkstemp(prefix='vdcms-')
        fb, isi = tempfile.mkstemp(prefix='vdcms-')
        os.close(fh)
        os.close(fb)
        try:
            cmd = ['curl', '-sk', '-D', hdr, '-o', isi, '-w', '%{http_code}', '-A', UA, '--max-time', '40']
            if ip:
                cmd += ['--resolve', '%s:%d:%s' % (domain, port, ip)]
            _, out, _ = jalan(cmd + ['%s://%s%s/?vdcek=%d' % (skema, domain, sub, time.time())], 60)
            kode = int(out) if out.isdigit() else 0
            if kode:
                with open(hdr, 'rb') as f:
                    h = f.read(20000).decode('latin-1')
                with open(isi, 'rb') as f:
                    return kode, h, f.read(3000000).decode('utf-8', 'replace')
        finally:
            os.unlink(hdr)
            os.unlink(isi)
    return 0, '', ''


def cek_http(domain, sub, ip):
    return ambil(domain, sub, ip)[0]


def css_kirki(html):
    return {m.group(1): m.group(2).strip() for m in RE_KIRKI.finditer(html or '') if m.group(2).strip()}


def hidup(kode):
    return 0 < kode < 500


# ---------- Pengaman sebelum update ----------

def baca_conf(path):
    out = {}
    try:
        with open(path) as f:
            for baris in f:
                k, _, v = baris.strip().partition('=')
                out[k] = v
    except (OSError, IOError):
        pass
    return out


def php_web(user, domain, header=''):
    """(versi 'X.Y', sumber) PHP yang melayani situs. Urutan: header X-Powered-By; domain php1_select=1 →
    PHP Selector CloudLinux (bila bukan native); selain itu phpN_release DirectAdmin. (None, None) = tak diketahui."""
    m = RE_PHP_HDR.search(header or '')
    if m:
        return m.group(1), 'header'
    n = baca_conf(os.path.join(DA_USERS, user, 'domains', domain + '.conf')).get('php1_select') or '1'
    if n == '1' and shutil.which('selectorctl'):
        out = jalan(['selectorctl', '--user-current', '--user=' + user], 30)[1].split()
        if out and re.match(r'^\d+\.\d+$', out[0]):
            return out[0], 'selector'
    rel = baca_conf(DA_OPSI).get('php%s_release' % n, '')
    return (rel, 'directadmin') if re.match(r'^\d+\.\d+$', rel) else (None, None)


def kuota(user):
    """(terpakai MB, batas MB) dari quota sistem berkas; (None, None) = tak terbatas/tak diketahui."""
    for baris in jalan(['quota', '-w', '-u', user], 30)[1].splitlines():
        b = baris.split()
        if len(b) >= 4 and b[0].startswith('/') and b[1].rstrip('*').isdigit() and b[2].isdigit() and b[3].isdigit():
            batas = int(b[3]) or int(b[2])
            if batas:
                return int(b[1].rstrip('*')) / 1024.0, batas / 1024.0
    return None, None


def ukuran_mb(path):
    if os.path.isfile(path):
        return os.path.getsize(path) / 1048576.0
    total = 0
    for d, _, berkas in os.walk(path):
        for b in berkas:
            try:
                total += os.lstat(os.path.join(d, b)).st_size
            except OSError:
                pass
    return total / 1048576.0


_syarat = {}


def syarat(jenis, slug):
    """{php, wp} rilis terbaru di wordpress.org; {} bila bukan dari wordpress.org / gagal diambil."""
    if (jenis, slug) not in _syarat:
        url = ('https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&request[slug]=%s' if jenis == 'plugin'
               else 'https://api.wordpress.org/themes/info/1.2/?action=theme_information&request[slug]=%s') % slug
        try:
            d = json.loads(jalan(['curl', '-gfsS', '--max-time', '20', '-A', UA, url], 30)[1])
        except ValueError:
            d = None
        _syarat[(jenis, slug)] = {'php': d.get('requires_php') or None, 'wp': d.get('requires') or None} \
            if isinstance(d, dict) and not d.get('error') else {}
    return _syarat[(jenis, slug)]


_terbaru = []


def wp_terbaru():
    """{version, php} rilis WordPress terbaru dari api.wordpress.org; {} bila gagal."""
    if not _terbaru:
        try:
            o = json.loads(jalan(['curl', '-fsS', '--max-time', '20', '-A', UA, 'https://api.wordpress.org/core/version-check/1.7/'], 30)[1])['offers'][0]
            _terbaru.append({'version': o.get('version'), 'php': o.get('php_version')})
        except (ValueError, KeyError, IndexError, TypeError):
            _terbaru.append({})
    return _terbaru[0]


def vt(v):
    return tuple(int(x) for x in re.findall(r'\d+', str(v or ''))[:4])


def versi_wp(akar):
    try:
        with open(os.path.join(akar, 'wp-includes', 'version.php')) as f:
            m = RE_VERSI_WP.search(f.read(4096))
        return m.group(1) if m else None
    except (OSError, IOError):
        return None


def periksa(user, akar, s, k, header, sisa):
    """Putuskan komponen mana yang aman diperbarui. sisa = sisa kuota MB (None = tak terbatas), dikurangi perkiraan
    kebutuhan tiap komponen yang lolos. s['core']: 'minor' | 'terbaru' | 'cek' (nilai kedua mode tanpa memilih,
    untuk dialog) | kosong. Kembalikan (info, plugin, tema, core: 'minor'/'terbaru'/False, sisa)."""
    mode = 'minor' if s.get('core') is True else s.get('core')
    baru = wp_terbaru() if mode in ('terbaru', 'cek') else {}
    php, sumber = php_web(user, s.get('domain') or '', header)
    wpv = versi_wp(akar)
    info = {'php': php, 'php_sumber': sumber, 'wp': wpv, 'sisa_mb': None if sisa is None else round(sisa, 1), 'keputusan': []}
    plugin = [x for x in s.get('plugin') or [] if RE_SLUG.match(x)][:40]
    tema = [x for x in s.get('tema') or [] if RE_SLUG.match(x)][:10]
    engine = engine_posts(k) if k and any(x.lower() == 'kirki' for x in plugin) else None
    lolos = {'plugin': [], 'theme': []}

    def putus(jenis, slug, perlu, alasan, **lain):
        if alasan is None and sisa is not None and perlu > sisa:
            alasan = 'kuota kurang: perlu ±%d MB, sisa %d MB' % (round(perlu), max(0, round(sisa)))
        info['keputusan'].append(dict({'jenis': jenis, 'slug': slug, 'ok': alasan is None, 'alasan': alasan, 'perlu_mb': round(perlu, 1)}, **lain))
        return alasan is None

    for jenis, daftar in (('plugin', plugin), ('theme', tema)):
        for slug in daftar:
            sy = syarat(jenis, slug)
            alasan, lain = None, {}
            if jenis == 'plugin' and slug.lower() == 'kirki' and engine == 'MyISAM':
                alasan = 'tabel posts MyISAM — Kirki 6.4 gagal membuat tabelnya; ubah ke InnoDB dulu (manual)'
            elif sy.get('php') and php and vt(php)[:2] < vt(sy['php'])[:2]:
                alasan = 'butuh PHP %s, PHP web situs %s' % (sy['php'], php)
            elif sy.get('wp') and wpv and (vt(baru.get('version')) < vt(sy['wp']) if mode == 'terbaru'
                                           else vt(wpv)[:2] < vt(sy['wp'])[:2] if mode else vt(wpv) < vt(sy['wp'])):
                # Update minor tetap di cabang yang sama → plugin yang butuh cabang lebih tinggi baru bisa bila inti 'terbaru'
                alasan = 'butuh WordPress %s (inti %s%s)' % (sy['wp'], wpv, ', update minor tetap di cabang ini' if mode in ('minor', 'cek') else '')
                lain = {'wp_butuh': sy['wp']}
            p = folder_komponen(akar, jenis, slug)
            perlu = 2 * ukuran_mb(p) + 1 if p else 5  # zip + ekstrak baru sebelum folder lama dibuang
            if putus(jenis, slug, perlu, alasan, **lain):
                lolos[jenis].append(slug)
                if sisa is not None:
                    sisa -= perlu
    core = False
    for m in ('minor', 'terbaru') if mode == 'cek' else (mode,) if mode in ('minor', 'terbaru') else ():
        perlu, alasan = (PERLU_INTI_MB, None) if m == 'minor' else (PERLU_INTI_TERBARU_MB, None)
        if m == 'terbaru':
            if not baru.get('version'):
                alasan = 'versi terbaru WordPress tak terbaca'
            elif wpv and vt(wpv) >= vt(baru['version']):
                alasan = 'sudah versi terbaru (%s)' % wpv
            elif baru.get('php') and php and vt(php)[:2] < vt(baru['php'])[:2]:
                alasan = 'WordPress %s butuh PHP %s, PHP web situs %s' % (baru['version'], baru['php'], php)
        if putus('core', m, perlu, alasan, ke=baru.get('version') if m == 'terbaru' else None) and mode != 'cek':
            core = m
            if sisa is not None:
                sisa -= perlu
    return info, lolos['plugin'], lolos['theme'], core, sisa


def disuspend(user):
    # Akun DA tersuspend: user MariaDB ikut dikunci (mysqldump error 4151 "account is locked") & situs 403
    return baca_conf(os.path.join(DA_USERS, user, 'user.conf')).get('suspended') == 'yes'


def cek(p):
    """Hanya baca: hasil periksa() untuk dialog konfirmasi sebelum perbaikan dijalankan."""
    user = p.get('user') or ''
    if not RE_USER.match(user) or not os.path.isdir('/home/' + user):
        return {'ok': False, 'error': 'akun_tidak_sah'}
    if disuspend(user):
        return {'ok': False, 'error': 'akun_disuspend'}
    pakai, batas = kuota(user)
    sisa = None if batas is None else batas - pakai
    out = []
    for s in (p.get('situs') or [])[:30]:
        akar = akar_sah(user, s.get('path'))
        if not akar:
            out.append({'path': s.get('path'), 'error': 'path_tidak_sah'})
            continue
        kode, hdr, html = ambil(s.get('domain') or '', s.get('sub') or '', ip_domain(user, s.get('domain') or ''))
        info, _, _, _, sisa = periksa(user, akar, s, kredensial(akar), hdr, sisa)
        info.update(path=akar, http=kode, kirki_css=len(css_kirki(html)))
        out.append(info)
    return {'ok': True, 'kuota': {'pakai': None if pakai is None else round(pakai, 1), 'batas': None if batas is None else round(batas, 1)}, 'situs': out}


# ---------- Perbaikan ----------

def akar_sah(user, path):
    akar = os.path.realpath(path or '')
    if not re.match(r'^/home/%s/domains/[^/]+/public_html(/[^/]+){0,2}$' % re.escape(user), akar) or akar != path:
        return None
    if not os.path.isfile(os.path.join(akar, 'wp-includes', 'version.php')):
        return None
    return akar


def ringkas_json(teks):
    """Keluaran `--format=json` WP-CLI → [{name, old_version, new_version, status}] (baris lain dibuang)."""
    for baris in reversed(teks.strip().splitlines()):
        if baris.startswith('['):
            try:
                return json.loads(baris)
            except ValueError:
                pass
    return []


def satu_situs(user, s, wpcli, tanda, oleh):
    akar = akar_sah(user, s.get('path'))
    hasil = {'path': s.get('path'), 'domain': s.get('domain'), 'ok': False, 'langkah': []}
    if not akar:
        hasil['error'] = 'path_tidak_sah'
        return hasil
    domain = s.get('domain') or ''
    ip = ip_domain(user, domain)
    hasil['http_sebelum'], hdr, html = ambil(domain, s.get('sub') or '', ip)
    k = kredensial(akar)
    if not k:
        hasil['error'] = 'wp_config_tidak_terbaca'
        return hasil
    # Kuota dibaca ulang tiap situs: update situs sebelumnya di akun yang sama sudah memakainya
    pakai, batas = kuota(user)
    hasil['cek'], plugin, tema, core, _ = periksa(user, akar, s, k, hdr, None if batas is None else batas - pakai)
    if not (plugin or tema or core):
        hasil.update(ok=True, kosong=True)
        return hasil
    wpcli = siapkan_wp(hasil['cek'].get('php')) or wpcli
    hasil['php_cli'] = wpcli[0]
    kirki_sebelum = css_kirki(html) if tema else {}
    folder = os.path.join(CADANGAN, re.sub(r'[^A-Za-z0-9._-]', '_', domain) or user, 'cms-perbaiki-' + tanda + (s.get('sub') or '').replace('/', '-'))
    os.makedirs(folder, mode=0o700, exist_ok=True)
    hasil['cadangan'] = folder
    galat = dump_db(k, os.path.join(folder, 'db.sql.gz'))
    if galat:
        hasil['error'] = 'cadangan_db_gagal'
        hasil['pesan'] = galat
        return hasil
    arsip = os.path.join(folder, 'komponen.tar.gz')
    with tarfile.open(arsip, 'w:gz') as t:
        for jenis, daftar in (('plugin', plugin), ('theme', tema)):
            for slug in daftar:
                p = folder_komponen(akar, jenis, slug)
                if p:
                    t.add(p, arcname=os.path.relpath(p, os.path.join(akar, 'wp-content')))
    arsip_inti = os.path.join(folder, 'inti.tar.gz')
    if core == 'terbaru':
        cadangkan_inti(akar, arsip_inti)
    with open(os.path.join(folder, 'catatan.json'), 'w') as f:
        json.dump({'oleh': oleh, 'waktu': int(time.time()), 'akar': akar, 'plugin': plugin, 'tema': tema, 'core': core, 'cek': hasil['cek']}, f)

    def langkah(nama, args, json_out=True):
        kode, out, err = wp(user, akar, wpcli, args)
        baris = (err.strip() or out.strip()).splitlines()
        fatal = [b for b in baris if re.search(r'Fatal error|Uncaught|^Error:', b)]
        item = {'langkah': nama, 'ok': kode == 0, 'pesan': (fatal or baris or [''])[0 if fatal else -1].strip()[:300]}
        if json_out:
            item['komponen'] = [{'slug': x.get('name'), 'dari': x.get('old_version'), 'ke': x.get('new_version'), 'status': x.get('status')}
                                for x in ringkas_json(out)]
        hasil['langkah'].append(item)
        return item

    if plugin:
        p1 = langkah('plugin', ['plugin', 'update'] + plugin + ['--format=json'])
    if tema:
        langkah('tema', ['theme', 'update'] + tema + ['--format=json'])
    if core:
        c = langkah('inti', ['core', 'update'] + (['--minor'] if core == 'minor' else []), False)
        if c['ok']:
            langkah('inti-db', ['core', 'update-db'], False)
            # Plugin yang menunggu inti lebih baru (mis. CF7 butuh WP 7.1) dicoba sekali lagi
            sisa = [x['slug'] for x in (p1['komponen'] if plugin else []) if x['status'] != 'Updated']
            if sisa:
                langkah('plugin-ulang', ['plugin', 'update'] + sisa + ['--format=json'])
    m = os.path.join(akar, '.maintenance')
    if os.path.isfile(m):
        os.unlink(m)

    hasil['http_sesudah'], _, html = ambil(domain, s.get('sub') or '', ip)
    if hidup(hasil['http_sebelum']) and not hidup(hasil['http_sesudah']) and (plugin or tema or core == 'terbaru'):
        try:
            if plugin or tema:
                kembalikan(akar, arsip)
            if core == 'terbaru':
                # DB sudah di-upgrade: tidak dikembalikan (versi db lebih baru aman untuk berkas lama); dump ada di cadangan
                kembalikan_inti(akar, arsip_inti)
                hasil['inti_dikembalikan'] = True
            hasil['dikembalikan'] = True
        except Exception as e:  # noqa: BLE001
            hasil['dikembalikan'] = False
            hasil['pesan'] = ('gagal mengembalikan: %s' % e)[:200]
        hasil['http_akhir'] = cek_http(domain, s.get('sub') or '', ip)
    hilang = {i: c for i, c in kirki_sebelum.items() if i not in css_kirki(html)}
    if hilang and hidup(hasil['http_sesudah']) and not hasil.get('dikembalikan'):
        css = '\n/* Dipulihkan %s VelocityGuard: CSS Kirki (%s) hilang sesudah update tema */\n%s\n' % (
            time.strftime('%Y-%m-%d'), ', '.join(sorted(hilang)), '\n'.join(hilang.values()))
        langkah('css-kirki', ['eval', "wp_update_custom_css_post(wp_get_custom_css() . base64_decode('%s'));"
                              % base64.b64encode(css.encode()).decode()], False)
        hasil['css_dipulihkan'] = sorted(hilang)
    # Situs yang memang sudah mati sebelum diperbaiki tidak dihitung gagal karena beranda
    akhir = hasil.get('http_akhir', hasil['http_sesudah'])
    hasil['ok'] = not hasil.get('dikembalikan') and (hidup(akhir) or not hidup(hasil['http_sebelum'])) \
        and all(x['ok'] for x in hasil['langkah'])
    return hasil


def perbaiki(p):
    user = p.get('user') or ''
    if not RE_USER.match(user) or not os.path.isdir('/home/' + user):
        return {'ok': False, 'error': 'akun_tidak_sah'}
    if disuspend(user):
        return {'ok': False, 'error': 'akun_disuspend'}
    wpcli = siapkan_wp()
    if not wpcli:
        return {'ok': False, 'error': 'wp_cli_tidak_tersedia'}
    tanda = time.strftime('%Y%m%d-%H%M%S')
    semua = []
    for i, s in enumerate((p.get('situs') or [])[:30]):
        try:
            h = satu_situs(user, s, wpcli, tanda, str(p.get('oleh') or '')[:40])
        except Exception as e:  # noqa: BLE001 — satu situs gagal tidak menghentikan yang lain
            h = {'path': s.get('path'), 'domain': s.get('domain'), 'ok': False, 'error': ('%s: %s' % (type(e).__name__, e))[:200]}
        semua.append(h)
        lapor({'situs': h, 'ke': i + 1})
    return {'ok': True, 'situs': len(semua), 'gagal': sum(1 for h in semua if not h['ok'])}


AKSI = {'perbaiki': perbaiki, 'cek': cek}


def jalankan(kode):
    try:
        p = json.loads(base64.b64decode(kode).decode())
        fn = AKSI.get(p.get('aksi'))
        out = fn(p) if fn else {'ok': False, 'error': 'aksi_tidak_dikenal'}
    except Exception as e:  # noqa: BLE001
        out = {'ok': False, 'error': ('%s: %s' % (type(e).__name__, e))[:200]}
    lapor(out)
