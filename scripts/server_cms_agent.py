# -*- coding: utf-8 -*-
"""Inventaris CMS (WordPress) satu server hosting (dijalankan di server lewat `ssh ... python3 -`).

Dipakai halaman Server > CMS (installer_status.py → /api/servers/cms*). Pemanggil menambahkan satu baris
`jalankan(<perintah base64 JSON>)` di akhir kode ini. Mencetak satu objek JSON di baris terakhir.
Harus tetap jalan di Python 3.6 (CloudLinux 8 platform-python). Param `user` = hanya akun itu (tanpa cPGuard).
HANYA BACA — tidak memasang/mengubah apa pun.

Aksi:
- suspend: status suspend akun DirectAdmin {akun: bool} (semua akun, atau `user` saja; cek cepat tanpa scan).
- inventaris: semua instalasi WordPress di /home/<akun>/domains/<domain>/public_html (sampai 2 folder ke
  dalam, mis. /redesign atau /wp) beserta versi inti, plugin, dan tema (dibaca dari header berkas).
  Juga hasil "CMS Threat" cPGuard dari /opt/cpguard/app/data/cms.db sebagai pembanding selama cPGuard jalan.
Pencocokan dengan basis data kerentanan dilakukan di dashboard (bukan di server).
"""
import base64
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

HOME = '/home'
DA_USERS = '/usr/local/directadmin/data/users'
CPG_CMS = '/opt/cpguard/app/data/cms.db'
KEDALAMAN = 2
MAKS_SITUS = 3000
MAKS_PHP_PLUGIN = 40
BACA_HEADER = 8192
# Folder di dalam public_html yang tidak mungkin berisi instalasi WP terpisah
LEWATI = {'wp-admin', 'wp-includes', 'wp-content', 'cgi-bin', '.well-known', 'node_modules', '.git', 'vendor',
          'cache', 'lscache', 'awstats', 'stats', 'logs', 'tmp', 'images', 'img', 'assets', 'css', 'js', 'fonts'}
RE_VERSI_WP = re.compile(r"\$wp_version\s*=\s*'([^']+)'")
RE_DEFINE = re.compile(r"""define\s*\(\s*['"](DB_NAME|DB_HOST)['"]\s*,\s*['"]([^'"]*)['"]""")
RE_PREFIX = re.compile(r"""\$table_prefix\s*=\s*['"]([A-Za-z0-9_]+)['"]""")
RE_SERIAL = re.compile(r's:\d+:"([^"]+)"')
DA_MYCNF = '/usr/local/directadmin/conf/my.cnf'


def baca_awal(path, n=BACA_HEADER):
    try:
        with open(path, 'rb') as f:
            return f.read(n).decode('utf-8', 'replace')
    except (OSError, IOError):
        return ''


def header(teks, kunci):
    # Header WordPress: "Plugin Name: X" di komentar (boleh diawali * atau #)
    m = re.search(r'^[ \t/*#@]*' + re.escape(kunci) + r':(.*)$', teks, re.M | re.I)
    if not m:
        return ''
    return re.sub(r'\s*(?:\*/|\?>).*$', '', m.group(1)).strip()[:120]


def akun_da():
    try:
        return sorted(u for u in os.listdir(DA_USERS) if os.path.isdir(os.path.join(HOME, u)))
    except OSError:
        return sorted(u for u in os.listdir(HOME) if os.path.isdir(os.path.join(HOME, u, 'domains')))


def disuspend(user):
    # Akun DA tersuspend: situs 403 & DB terkunci → ditandai di dashboard
    return 'suspended=yes' in baca_awal(os.path.join(DA_USERS, user, 'user.conf'), 65536).split('\n')


def daftar_plugin(wpc):
    out = []
    folder = os.path.join(wpc, 'plugins')
    try:
        isi = sorted(os.listdir(folder))
    except OSError:
        return out
    for nama in isi:
        p = os.path.join(folder, nama)
        if nama.startswith('.') or nama == 'index.php':
            continue
        if os.path.isfile(p):
            # Plugin satu berkas (hello.php)
            if nama.endswith('.php'):
                t = baca_awal(p)
                if header(t, 'Plugin Name'):
                    out.append({'slug': nama[:-4], 'nama': header(t, 'Plugin Name'), 'versi': header(t, 'Version')})
            continue
        if not os.path.isdir(p) or os.path.islink(p):
            continue
        utama = None
        try:
            berkas = sorted(f for f in os.listdir(p) if f.endswith('.php'))
        except OSError:
            continue
        # Berkas bernama sama dengan folder hampir selalu berkas utama → baca dulu
        berkas.sort(key=lambda f: f != nama + '.php')
        for f in berkas[:MAKS_PHP_PLUGIN]:
            t = baca_awal(os.path.join(p, f))
            if header(t, 'Plugin Name'):
                utama = t
                break
        if utama is None:
            continue
        out.append({'slug': nama, 'nama': header(utama, 'Plugin Name'), 'versi': header(utama, 'Version')})
    return out


def daftar_tema(wpc):
    out = []
    folder = os.path.join(wpc, 'themes')
    try:
        isi = sorted(os.listdir(folder))
    except OSError:
        return out
    for nama in isi:
        css = os.path.join(folder, nama, 'style.css')
        if nama.startswith('.') or not os.path.isfile(css):
            continue
        t = baca_awal(css)
        if not header(t, 'Theme Name'):
            continue
        out.append({'slug': nama, 'nama': header(t, 'Theme Name'), 'versi': header(t, 'Version'), 'induk': header(t, 'Template')})
    return out


def instalasi(akar, user, domain, sub):
    vp = os.path.join(akar, 'wp-includes', 'version.php')
    m = RE_VERSI_WP.search(baca_awal(vp, 4096))
    if not m:
        return None
    wpc = os.path.join(akar, 'wp-content')
    try:
        mu = sorted(f for f in os.listdir(os.path.join(wpc, 'mu-plugins')) if not f.startswith('.'))[:50]
    except OSError:
        mu = []
    return {'path': akar, 'user': user, 'domain': domain, 'sub': sub, 'versi': m.group(1),
            'plugin': daftar_plugin(wpc), 'tema': daftar_tema(wpc), 'mu_plugin': mu}


def cari_wp(akar, kedalaman):
    """Kembalikan daftar (path, sub) instalasi di bawah akar (termasuk akar sendiri)."""
    hasil = []
    if os.path.isfile(os.path.join(akar, 'wp-includes', 'version.php')) and (
            os.path.isfile(os.path.join(akar, 'wp-config.php')) or os.path.isfile(os.path.join(os.path.dirname(akar), 'wp-config.php'))):
        hasil.append(akar)
    if kedalaman <= 0:
        return hasil
    try:
        isi = os.listdir(akar)
    except OSError:
        return hasil
    for n in sorted(isi):
        p = os.path.join(akar, n)
        if n.startswith('.') or n.lower() in LEWATI or os.path.islink(p) or not os.path.isdir(p):
            continue
        hasil.extend(cari_wp(p, kedalaman - 1))
    return hasil


def status_aktif(situs):
    """Isi s['aktif'] = {plugin: [slug], tema: [stylesheet, template], daftar: bool} dari tabel options tiap situs.
    Satu panggilan mysql (akun admin DA, hanya SELECT) untuk semua situs; situs yang gagal dibaca dibiarkan tanpa 'aktif'."""
    sql = []
    for i, s in enumerate(situs):
        conf = os.path.join(s['path'], 'wp-config.php')
        if not os.path.isfile(conf):
            conf = os.path.join(os.path.dirname(s['path']), 'wp-config.php')
        t = baca_awal(conf, 65536)
        d = dict(RE_DEFINE.findall(t))
        m = RE_PREFIX.search(t)
        db = d.get('DB_NAME', '')
        # shortcut: DB di host lain dilewati (status aktif tak diketahui)
        if not m or not re.match(r'^[A-Za-z0-9_$-]+$', db) or d.get('DB_HOST', 'localhost').split(':')[0] not in ('localhost', '127.0.0.1', ''):
            continue
        sql.append("SELECT %d, option_name, option_value FROM `%s`.`%soptions` WHERE option_name IN "
                   "('active_plugins','template','stylesheet','users_can_register');" % (i, db, m.group(1)))
    if not sql or not os.path.isfile(DA_MYCNF):
        return
    try:
        r = subprocess.run(['mysql', '--defaults-extra-file=' + DA_MYCNF, '--force', '--batch', '--skip-column-names'],
                           input='\n'.join(sql), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        return
    opsi = {}
    for baris in r.stdout.splitlines():
        b = baris.split('\t', 2)
        if len(b) == 3 and b[0].isdigit():
            opsi.setdefault(int(b[0]), {})[b[1]] = b[2]
    for i, o in opsi.items():
        plugin = sorted({p.split('/')[0][:-4] if '/' not in p else p.split('/')[0] for p in RE_SERIAL.findall(o.get('active_plugins', ''))})
        situs[i]['aktif'] = {'plugin': plugin, 'tema': sorted({o.get('stylesheet', ''), o.get('template', '')} - {''}),
                             'daftar': o.get('users_can_register') == '1'}


def cpguard():
    if not os.path.isfile(CPG_CMS):
        return None
    try:
        db = sqlite3.connect('file:%s?mode=ro' % CPG_CMS, uri=True, timeout=5)
        db.row_factory = sqlite3.Row
        situs = {}
        for r in db.execute('SELECT id, path, version, threat_score, threat_rating, issues_count, errors, time FROM cms WHERE status = 1'):
            situs[r['id']] = {'path': (r['path'] or '').rstrip('/'), 'versi': r['version'], 'skor': r['threat_score'],
                              'rating': r['threat_rating'] or 'safe', 'jumlah': r['issues_count'] or 0,
                              'galat': bool((r['errors'] or '').strip() not in ('', '[]', '{}', 'null')),
                              'waktu': r['time'], 'isu': []}
        # Isu komponen yang masih terpasang (status komponen 1); isu lama komponen yang sudah diperbarui dibuang
        q = ('SELECT i.cms_id, i.title, i.cvss_score, i.cvss_rating, i.patched_versions, c.type, c.identifier, c.version '
             'FROM issues i LEFT JOIN components c ON c.id = i.component_id '
             'WHERE i.component_id IS NULL OR c.status = 1')
        for r in db.execute(q):
            s = situs.get(r['cms_id'])
            if s is None or s['rating'].lower() == 'safe' or len(s['isu']) >= 60:
                continue
            s['isu'].append({'jenis': r['type'] or 'core', 'slug': r['identifier'] or '', 'versi': r['version'] or '',
                             'judul': (r['title'] or '')[:200], 'cvss': r['cvss_score'], 'patch': (r['patched_versions'] or '')[:80]})
        db.close()
        return {'situs': list(situs.values())}
    except sqlite3.Error as e:
        return {'error': str(e)[:200]}


def cpguard_jalan():
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            try:
                with open('/proc/%s/comm' % pid) as f:
                    if f.read().strip() == 'cpguard':
                        return True
            except (OSError, IOError):
                pass
    return False


def inventaris(p):
    mulai = time.time()
    situs = []
    terpotong = False
    for user in akun_da():
        if p.get('user') and user != p['user']:  # scan ulang satu akun sesudah perbaikan
            continue
        dom = os.path.join(HOME, user, 'domains')
        susp = disuspend(user)
        try:
            domains = sorted(os.listdir(dom))
        except OSError:
            continue
        for d in domains:
            ph = os.path.join(dom, d, 'public_html')
            if not os.path.isdir(ph) or os.path.islink(ph):
                continue
            for akar in cari_wp(ph, KEDALAMAN):
                if len(situs) >= MAKS_SITUS:
                    terpotong = True
                    break
                sub = akar[len(ph):]
                item = instalasi(akar, user, d, sub)
                if item:
                    if susp:
                        item['suspend'] = True
                    situs.append(item)
    status_aktif(situs)
    return {'ok': True, 'situs': situs, 'terpotong': terpotong, 'cpguard': None if p.get('user') else cpguard(),
            'cpguard_jalan': cpguard_jalan(),
            'detik': round(time.time() - mulai, 1)}


def suspend(p):
    return {'ok': True, 'akun': {u: disuspend(u) for u in ([p['user']] if p.get('user') else akun_da())}}


AKSI = {'inventaris': inventaris, 'suspend': suspend}


def jalankan(kode):
    try:
        p = json.loads(base64.b64decode(kode).decode())
        fn = AKSI.get(p.get('aksi'))
        out = fn(p) if fn else {'ok': False, 'error': 'aksi_tidak_dikenal'}
    except Exception as e:  # noqa: BLE001 — galat apa pun dilaporkan sebagai JSON
        out = {'ok': False, 'error': ('%s: %s' % (type(e).__name__, e))[:200]}
    sys.stdout.write(json.dumps(out, separators=(',', ':')) + '\n')
