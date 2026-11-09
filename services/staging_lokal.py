"""Panel staging lokal untuk dashboard (/staging): pengganti DirectAdmin akun vdcenterbiz di PC ini.

Modul ini hanya membaca; aksi yang mengubah ada di staging_aksi.py. Pindai situs dan ukuran dijalankan di latar lalu di-cache (TTL_DETIK + berkas
CACHE agar tahan restart), karena `du` 20 GB terlalu berat untuk per request. Yang murah (layanan, FPM,
cron, disk) dibaca tiap request.
Cek HTTP sengaja per situs atas klik, bukan massal: 2 Nov cek 88 situs (3 paralel) memicu wp-cron tiap
situs, pool FPM 12 penuh, antrean >30 dtk selama beberapa menit dan staging ikut melambat.
Isi folder situs tidak dipercaya: berkas dibaca tanpa mengikuti symlink, keluaran hanya hasil regex.
"""
import glob
import http.client
import json
import os
import re
import shutil
import subprocess
import threading
import time
from urllib.parse import quote

USER = 'vdcenterbiz'
AKAR = f'/home/{USER}/domains/velocitydatacenter.biz'
URL = 'https://velocitydatacenter.biz'
HOST = 'velocitydatacenter.biz'
PORT_APACHE = 8191
# Meniru kunjungan dari kantor. Maintenance velocity-addons tetap bisa menjawab 500 (wp_die) walau IP ini dipakai.
IP_KANTOR = '202.59.194.129'
KONF_FPM = f'/etc/opt/remi/php83/php-fpm.d/{USER}.conf'
LAYANAN = ['httpd', 'php83-php-fpm', 'mariadb', 'cloudflared']
CACHE = '/var/lib/velocity/staging-lokal.json'
TTL_DETIK = 3600
WAKTU_HTTP = 60

RE_WP_DB = re.compile(r"""^\s*define\(\s*['"]DB_NAME['"]\s*,\s*['"]([^'"]+)['"]""", re.M)
RE_WP_VERSI = re.compile(r"""^\$wp_version\s*=\s*['"]([^'"]+)['"]""", re.M)
RE_ENV_DB = re.compile(r"""^DB_DATABASE=["']?([^"'\s]+)""", re.M)
RE_MAKS_FPM = re.compile(r'^pm\.max_children\s*=\s*(\d+)', re.M)


def baca(path):
    """Isi awal berkas; '' bila tidak ada atau symlink (O_NOFOLLOW: situs klien bisa menaruh symlink ke berkas root)."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return ''
    try:
        return os.read(fd, 262144).decode('utf-8', 'replace')
    except OSError:
        return ''
    finally:
        os.close(fd)


def _cocok(pola, teks):
    m = pola.search(teks)
    return m.group(1) if m else None


def _wordpress(folder, rel):
    return {'nama': rel, 'jenis': 'wordpress', 'path': folder, 'url': f'{URL}/{rel}',
            'versi': _cocok(RE_WP_VERSI, baca(f'{folder}/wp-includes/version.php')),
            'db': _cocok(RE_WP_DB, baca(f'{folder}/wp-config.php'))}


def _laravel(app, nama, url):
    return {'nama': nama, 'jenis': 'laravel', 'path': app, 'url': url, 'versi': None,
            'db': _cocok(RE_ENV_DB, baca(f'{app}/.env'))}


def pindai(akar=AKAR):
    """Daftar situs di public_html (termasuk satu tingkat bersarang) + aplikasi apps/ yang tak tertaut."""
    pub, apps = f'{akar}/public_html', f'{akar}/apps'
    hasil, tertaut = [], set()

    def telusur(folder, awalan, dalam):
        for e in sorted(os.scandir(folder), key=lambda x: x.name):
            if e.name.startswith('.'):
                continue
            rel = f'{awalan}{e.name}'
            if e.is_symlink():
                t = os.path.realpath(e.path)
                app = os.path.dirname(t)
                if os.path.basename(t) == 'public' and os.path.dirname(app) == os.path.realpath(apps):
                    tertaut.add(app)
                    hasil.append(_laravel(app, rel, f'{URL}/{rel}'))
                else:
                    hasil.append({'nama': rel, 'jenis': 'lain', 'path': e.path, 'url': f'{URL}/{rel}', 'versi': None, 'db': None})
            elif not e.is_dir(follow_symlinks=False):
                continue
            elif os.path.exists(f'{e.path}/wp-config.php'):
                hasil.append(_wordpress(e.path, rel))
            else:
                isi = os.listdir(e.path)
                if not dalam and any(os.path.exists(f'{e.path}/{n}/wp-config.php') for n in isi):
                    telusur(e.path, f'{rel}/', True)
                else:
                    hasil.append({'nama': rel, 'jenis': 'lain' if isi else 'kosong', 'path': e.path,
                                  'url': f'{URL}/{rel}' if isi else None, 'versi': None, 'db': None})

    telusur(pub, '', False)
    if os.path.isdir(apps):
        for e in sorted(os.scandir(apps), key=lambda x: x.name):
            if e.is_dir(follow_symlinks=False) and os.path.realpath(e.path) not in tertaut:
                hasil.append(_laravel(e.path, f'apps/{e.name}', None))
    return hasil


def _du(path):
    r = subprocess.run(['nice', '-n19', 'ionice', '-c3', 'du', '-skx', path], capture_output=True, text=True)
    try:
        return int(r.stdout.split()[0]) * 1024
    except (IndexError, ValueError):
        return None


def _http(rel):
    """Kode HTTP tanpa mengikuti pengalihan, langsung ke Apache lokal (tak lewat tunnel); 0 = tak menjawab."""
    k = http.client.HTTPConnection('127.0.0.1', PORT_APACHE, timeout=WAKTU_HTTP)
    try:
        k.request('GET', f'/{quote(rel)}/', headers={
            'Host': HOST, 'X-Forwarded-Proto': 'https', 'CF-Connecting-IP': IP_KANTOR, 'User-Agent': 'VelocityDash/1'})
        return k.getresponse().status
    except (OSError, http.client.HTTPException):
        return 0
    finally:
        k.close()


def ukuran_db():
    sql = ("select table_schema, sum(data_length+index_length) from information_schema.tables "
           f"where table_schema like '{USER}\\_%' group by 1")
    r = subprocess.run(['runuser', '-u', 'mysql', '--', 'mysql', '-N', '-e', sql],
                       capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise RuntimeError(f'mysql: {r.stderr.strip()[:200]}')
    return {nama: int(float(n)) for nama, n in (b.split('\t') for b in r.stdout.splitlines() if b)}


def gabung(situs, db):
    """Tempel ukuran DB ke situs; yang tak dipakai situs mana pun = DB yatim."""
    for s in situs:
        s['db_ukuran'] = db.get(s['db'])
    dipakai = {s['db'] for s in situs}
    return [{'nama': n, 'ukuran': u} for n, u in sorted(db.items()) if n not in dipakai]


def _sapu_tiket_masuk(akar=AKAR):
    """Tiket login sekali pakai yang tak pernah dibuka (mis. layanan restart sebelum timer menghapusnya)."""
    batas = time.time() - 300
    for pola in ('public_html/*/vd-masuk-*.php', 'public_html/*/*/vd-masuk-*.php'):
        for p in glob.glob(f'{akar}/{pola}'):
            if os.lstat(p).st_mtime < batas:
                os.unlink(p)


def ambil():
    _sapu_tiket_masuk()
    situs = pindai()
    yatim = gabung(situs, ukuran_db())
    for s in situs:  # satu per satu: disk jangan dibebani paralel
        s['disk'] = _du(s['path'])
    return {'waktu': int(time.time()), 'situs': situs, 'db_yatim': yatim, 'disk_total': _du(AKAR)}


def langsung():
    """Data murah, dibaca tiap request."""
    aktif = {n: subprocess.run(['systemctl', 'is-active', n], capture_output=True, text=True).stdout.strip() == 'active'
             for n in LAYANAN}
    ps = subprocess.run(['ps', '-u', USER, '-o', 'rss=,comm='], capture_output=True, text=True).stdout
    fpm = [int(b.split()[0]) for b in ps.splitlines() if 'php-fpm' in b]
    cron = subprocess.run(['crontab', '-u', USER, '-l'], capture_output=True, text=True).stdout
    aktif_kerja = staging_kerja() if staging_kerja else None
    d = shutil.disk_usage('/home')
    return {'akar': AKAR, 'url': URL, 'layanan': aktif,
            'fpm': {'proses': len(fpm), 'memori': sum(fpm) * 1024,
                    'maks': int(_cocok(RE_MAKS_FPM, baca(KONF_FPM)) or 0)},
            'cron': [b for b in cron.splitlines() if re.match(r'^[\d*@]', b)], 'cron_teks': cron,
            'pekerjaan': aktif_kerja,
            'partisi': {'total': d.total, 'terpakai': d.used, 'sisa': d.free}}


staging_kerja = None  # diisi staging_aksi: status pekerjaan latar untuk ditampilkan
_kunci = threading.Lock()
_kunci_http = threading.Lock()
_st = {'data': None, 'jalan': False, 'galat': None, 'muat': False}


def _simpan_cache(data):
    fd = os.open(f'{CACHE}.tmp', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(data, f)
    os.replace(f'{CACHE}.tmp', CACHE)


def ubah_cache(fungsi):
    """Situs baru/terhapus langsung tampak tanpa menunggu pindai ulang (du 20 GB)."""
    with _kunci:
        _muat_cache()
        if _st['data']:
            fungsi(_st['data'])
            _simpan_cache(_st['data'])


def _segarkan():
    try:
        data = ambil()
        _simpan_cache(data)
        hasil = {'data': data, 'galat': None}
    except Exception as e:  # data lama tetap ditampilkan, galatnya diberitahukan
        hasil = {'galat': str(e)[:300]}
    with _kunci:
        _st.update(hasil, jalan=False)


def _muat_cache():
    """Panggil dengan _kunci dipegang."""
    if not _st['muat']:
        _st['muat'] = True
        try:
            with open(CACHE) as f:
                _st['data'] = json.load(f)
        except (OSError, ValueError):
            pass


def daftar_situs():
    with _kunci:
        _muat_cache()
        return (_st['data'] or {}).get('situs', [])


def status(segar=False):
    with _kunci:
        _muat_cache()
        d = _st['data']
        if (segar or not d or time.time() - d['waktu'] > TTL_DETIK) and not _st['jalan']:
            _st['jalan'] = True
            threading.Thread(target=_segarkan, daemon=True).start()
        jalan, galat = _st['jalan'], _st['galat']
    return {**langsung(), **(d or {}), 'menyegarkan': jalan, 'galat': galat}


def cek_http(nama):
    """Cek satu situs atas klik. Nama wajib ada di hasil pindai; hanya satu cek sekaligus."""
    if not any(x['nama'] == nama and x['url'] for x in daftar_situs()):
        return {'galat': 'situs_tidak_dikenal'}
    if not _kunci_http.acquire(blocking=False):
        return {'galat': 'sedang_mengecek'}
    try:
        mulai = time.time()
        return {'kode': _http(nama), 'detik': round(time.time() - mulai, 1)}
    finally:
        _kunci_http.release()
