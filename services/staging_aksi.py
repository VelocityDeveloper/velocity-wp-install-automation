"""Aksi panel staging lokal: login sekali klik, log, cron, DB, cadangan/pulihkan, buat dan hapus situs.

Layanan ini root, isi folder situs tidak dipercaya: nama situs wajib ada di hasil pindai, nama DB/user
divalidasi regex, perintah tanpa shell. Impor/pulihkan memakai user DB situs itu sendiri, jadi dump tak bisa
menyentuh DB lain; dump ber-USE/CREATE DATABASE tetap ditolak (20 Okt dump seperti itu menimpa DB asli).
Pekerjaan berat berjalan satu per satu di latar supaya staging tidak penuh (lihat insiden 2 Nov di staging_lokal.py).
"""
import gzip
import os
import pwd
import re
import secrets
import shutil
import stat
import subprocess
import threading
import time
import json

import staging_lokal as L

CADANGAN = '/root/velocity-cadangan/staging'
RE_DB = re.compile(rf'^{L.USER}_\w+$')
RE_USER = re.compile(r'^\w+$')
RE_ID = re.compile(r'^\d{8}-\d{6}-[a-z-]+$')
RE_NAMA_BARU = re.compile(r'^[a-z0-9](?:[a-z0-9.-]{0,61}[a-z0-9])?$')
BARU = f'{CADANGAN}/_baru'  # DB situs baru yang belum punya konfigurasi, agar ikut terhapus bersama foldernya
RE_WP_USER = re.compile(r"""^\s*define\(\s*['"]DB_USER['"]\s*,\s*['"]([^'"]+)['"]""", re.M)
RE_WP_SANDI = re.compile(r"""^(\s*define\(\s*['"]DB_PASSWORD['"]\s*,\s*)(['"])(.*?)\2""", re.M)
RE_ENV_USER = re.compile(r"""^DB_USERNAME=["']?([^"'\s]+)""", re.M)
RE_ENV_SANDI = re.compile(r"""^DB_PASSWORD=(.*)$""", re.M)
# Boleh di dalam komentar bersyarat /*!40000 ... */. Dicocokkan hanya di awal baris: isi INSERT tak ikut.
RE_DUMP_TERLARANG = re.compile(
    rb'^\s*(?:/\*!\d*\s*)?(?:USE\s|(?:CREATE|DROP)\s+(?:DATABASE|SCHEMA)\b|GRANT\s|REVOKE\s|(?:CREATE|DROP|ALTER)\s+USER\b|SET\s+PASSWORD\b)',
    re.I)
TANPA_ARSIP = ['--exclude=*/wp-content/cache', '--exclude=*/wp-content/litespeed', '--exclude=*/wp-content/et-cache',
               '--exclude=vd-masuk-*.php']
RENDAH = ['nice', '-n19', 'ionice', '-c3']
SUMBER_LOG = {'php': f'{L.AKAR}/logs/php-fpm.log', 'galat': f'/var/log/httpd/{L.USER}-error.log',
              'akses': f'/var/log/httpd/{L.USER}-access.log'}


class Galat(Exception):
    def __init__(self, kode, status=400):
        super().__init__(kode)
        self.kode = kode
        self.status = status


def _situs(nama):
    s = next((x for x in L.daftar_situs() if x['nama'] == nama), None)
    if not s:
        raise Galat('situs_tidak_dikenal', 404)
    if os.path.islink(s['path']) or not os.path.realpath(s['path']).startswith(L.AKAR + '/') or not os.path.isdir(s['path']):
        raise Galat('folder_situs_tidak_valid')
    return s


def _wajib_konfirmasi(body, nama):
    if body.get('konfirmasi') != nama:
        raise Galat('konfirmasi_salah')


def urai_wp(teks):
    m = RE_WP_SANDI.search(teks)
    return {'db': L._cocok(L.RE_WP_DB, teks), 'user': L._cocok(RE_WP_USER, teks), 'sandi': m.group(3) if m else None}


def urai_env(teks):
    m = RE_ENV_SANDI.search(teks)
    return {'db': L._cocok(L.RE_ENV_DB, teks), 'user': L._cocok(RE_ENV_USER, teks),
            'sandi': m.group(1).strip().strip('"\'') if m else None}


def ganti_sandi_wp(teks, baru):
    hasil, n = RE_WP_SANDI.subn(lambda m: f'{m.group(1)}{m.group(2)}{baru}{m.group(2)}', teks)
    if n != 1:
        raise Galat('sandi_di_konfigurasi_tak_terbaca')
    return hasil


def ganti_sandi_env(teks, baru):
    hasil, n = RE_ENV_SANDI.subn(lambda _: f'DB_PASSWORD={baru}', teks)
    if n != 1:
        raise Galat('sandi_di_konfigurasi_tak_terbaca')
    return hasil


def _berkas_konfig(s):
    return f"{s['path']}/{'wp-config.php' if s['jenis'] == 'wordpress' else '.env'}"


def _kredensial(s):
    if s['jenis'] not in ('wordpress', 'laravel'):
        return None
    teks = L.baca(_berkas_konfig(s))
    k = urai_wp(teks) if s['jenis'] == 'wordpress' else urai_env(teks)
    if not k['db'] or not k['user']:
        return None
    if not RE_DB.match(k['db']) or not RE_USER.match(k['user']):
        raise Galat('nama_db_tidak_valid')
    return k


def _wajib_kredensial(s):
    k = _kredensial(s)
    if not k:
        raise Galat('situs_tanpa_database')
    return k


def _sql_admin(sql):
    r = subprocess.run(['runuser', '-u', 'mysql', '--', 'mysql', '-N'], input=sql, capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise Galat(f'mysql: {r.stderr.strip()[:200]}', 500)
    return r.stdout


def _kutip(teks):
    return teks.replace('\\', '\\\\').replace("'", "''")


def _dump(db, tujuan):
    """Dump tanpa --databases, jadi tak ada USE/CREATE DATABASE. Berkas hanya muncul bila dump lengkap."""
    sementara = f'{tujuan}.tmp'
    fd = os.open(sementara, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, 'wb') as keluar:
            d = subprocess.Popen(RENDAH + ['runuser', '-u', 'mysql', '--', 'mariadb-dump', '--single-transaction', '--quick',
                                           '--routines', '--triggers', '--default-character-set=utf8mb4', db],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            z = subprocess.Popen(['gzip', '-1'], stdin=d.stdout, stdout=keluar)
            d.stdout.close()
            galat = d.stderr.read().decode('utf-8', 'replace')
            if d.wait() or z.wait():
                raise Galat(f'dump_gagal: {galat.strip()[:200]}', 500)
        if not ekor_dump_lengkap(sementara):
            raise Galat('dump_tidak_lengkap', 500)
        os.replace(sementara, tujuan)
    finally:
        if os.path.exists(sementara):
            os.unlink(sementara)


def ekor_dump_lengkap(path):
    with gzip.open(path, 'rb') as f:
        ekor = b''
        while b := f.read(1048576):
            ekor = (ekor + b)[-200:]
    return b'Dump completed' in ekor


def periksa_dump(path):
    """Tolak dump yang bisa menyentuh DB/user lain. Baris INSERT raksasa dibaca potongan, hanya awal baris yang dicocokkan."""
    with open(path, 'rb') as f:
        gz = f.read(2) == b'\x1f\x8b'
    try:
        with (gzip.open(path, 'rb') if gz else open(path, 'rb')) as f:
            awal = True
            while b := f.readline(65536):
                if awal and RE_DUMP_TERLARANG.match(b):
                    raise Galat(f'dump_ditolak: {b[:60].decode("utf-8", "replace").strip()}')
                awal = b.endswith(b'\n')
    except (OSError, EOFError) as e:
        raise Galat(f'berkas_dump_rusak: {e}')


def _impor(k, path):
    """Masuk sebagai user DB situs: dump tak bisa menyentuh DB lain."""
    env = {**os.environ, 'MYSQL_PWD': k['sandi'] or ''}
    with open(path, 'rb') as f:
        gz = f.read(2) == b'\x1f\x8b'
    masuk = RENDAH + ['mysql', '--default-character-set=utf8mb4', '-u', k['user'], k['db']]
    if gz:
        z = subprocess.Popen(['gzip', '-dc', path], stdout=subprocess.PIPE)
        m = subprocess.run(masuk, stdin=z.stdout, capture_output=True, env=env)
        z.stdout.close()
        gagal = z.wait() or m.returncode
    else:
        with open(path, 'rb') as f:
            m = subprocess.run(masuk, stdin=f, capture_output=True, env=env)
        gagal = m.returncode
    if gagal:
        raise Galat(f'impor_gagal: {m.stderr.decode("utf-8", "replace").strip()[:200]}', 500)


def _kosongkan_db(db):
    baris = _sql_admin(f"select table_name, table_type from information_schema.tables where table_schema='{db}'")
    perintah = ['SET FOREIGN_KEY_CHECKS=0;']
    for b in baris.splitlines():
        nama, jenis = b.split('\t')
        kata = 'VIEW' if jenis == 'VIEW' else 'TABLE'
        perintah.append(f"DROP {kata} IF EXISTS `{db}`.`{nama.replace('`', '``')}`;")
    _sql_admin('\n'.join(perintah))


def _ganti_db(k, dump, pengaman):
    """Ganti seluruh isi DB dengan dump; gagal = kembalikan dari dump pengaman."""
    _kosongkan_db(k['db'])
    try:
        _impor(k, dump)
    except Galat:
        _kosongkan_db(k['db'])
        _impor(k, pengaman)
        raise


def _tulis_konfig(path, teks):
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode):
        raise Galat('konfigurasi_bukan_berkas_biasa')
    sementara = f'{path}.vd-tmp'
    fd = os.open(sementara, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IMODE(st.st_mode))
    with os.fdopen(fd, 'w') as f:
        f.write(teks)
    os.chown(sementara, st.st_uid, st.st_gid)
    os.replace(sementara, path)
    subprocess.run(['restorecon', path], capture_output=True)


def _folder_cadangan(nama):
    return f"{CADANGAN}/{nama.replace('/', '__')}"


def _siapkan_folder(path):
    os.makedirs(CADANGAN, mode=0o700, exist_ok=True)  # makedirs tak memberi mode ke folder induk
    os.makedirs(path, mode=0o700, exist_ok=True)


def _ruang_cukup(s):
    if shutil.disk_usage('/root').free < (s.get('disk') or 0) + 5 * 1024 ** 3:
        raise Galat('ruang_cadangan_kurang')


# ---------- Pekerjaan latar: satu per satu ----------
_k = threading.Lock()
_kerja = {'aktif': None, 'terakhir': None}


def status_kerja():
    with _k:
        return {'aktif': _kerja['aktif'], 'terakhir': _kerja['terakhir']}


L.staging_kerja = status_kerja


def _mulai(jenis, nama, fungsi):
    with _k:
        if _kerja['aktif']:
            raise Galat('sedang_ada_pekerjaan', 409)
        _kerja['aktif'] = {'jenis': jenis, 'nama': nama, 'mulai': int(time.time()), 'tahap': 'Memulai'}

    def tahap(teks):
        with _k:
            _kerja['aktif']['tahap'] = teks

    def jalan():
        hasil = {'galat': None, 'pesan': None}
        try:
            hasil['pesan'] = fungsi(tahap)
        except Galat as e:
            hasil['galat'] = e.kode
        except Exception as e:
            hasil['galat'] = str(e)[:300]
        with _k:
            _kerja['terakhir'] = {**_kerja['aktif'], **hasil, 'selesai': int(time.time())}
            _kerja['aktif'] = None
        print(f'staging {jenis} {nama}: {hasil}', flush=True)

    threading.Thread(target=jalan, daemon=True).start()
    return {'ok': True}


# ---------- Cadangan ----------
def _buat_cadangan(s, jenis, tahap):
    _ruang_cukup(s)
    cid = f"{time.strftime('%Y%m%d-%H%M%S')}-{jenis}"
    folder = f"{_folder_cadangan(s['nama'])}/{cid}"
    _siapkan_folder(_folder_cadangan(s['nama']))
    os.makedirs(folder, mode=0o700)
    try:
        tahap(f'Mengarsipkan berkas ({jenis})')
        arsip = f'{folder}/berkas.tar.gz'
        induk, nama_folder = os.path.split(s['path'])
        r = subprocess.run(RENDAH + ['tar', '-czf', arsip, '--numeric-owner', *TANPA_ARSIP, '-C', induk, nama_folder],
                           capture_output=True, text=True)
        if r.returncode > 1:  # 1 = ada berkas berubah saat dibaca, wajar di situs yang hidup
            raise Galat(f'tar_gagal: {r.stderr.strip()[:200]}', 500)
        if subprocess.run(['gzip', '-t', arsip], capture_output=True).returncode:
            raise Galat('arsip_rusak', 500)
        k = _kredensial(s)
        if k:
            tahap(f'Membuat dump database ({jenis})')
            _dump(k['db'], f'{folder}/db.sql.gz')
        with open(f'{folder}/meta.json', 'w') as f:
            json.dump({'nama': s['nama'], 'jenis': jenis, 'waktu': int(time.time()), 'db': k['db'] if k else None,
                       'versi': s.get('versi'), 'path': s['path']}, f)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return cid


def buat_cadangan(body):
    s = _situs(body.get('nama', ''))
    _ruang_cukup(s)
    return _mulai('cadangan', s['nama'], lambda tahap: f"Cadangan {_buat_cadangan(s, 'manual', tahap)} selesai")


def daftar_cadangan(nama):
    s = _situs(nama)
    hasil = []
    akar = _folder_cadangan(s['nama'])
    for cid in sorted(os.listdir(akar), reverse=True) if os.path.isdir(akar) else []:
        folder = f'{akar}/{cid}'
        try:
            with open(f'{folder}/meta.json') as f:
                m = json.load(f)
        except (OSError, ValueError):
            continue
        ukuran = sum(os.path.getsize(f'{folder}/{n}') for n in os.listdir(folder))
        hasil.append({'id': cid, 'jenis': m['jenis'], 'waktu': m['waktu'], 'versi': m.get('versi'), 'ukuran': ukuran,
                      'ada_db': os.path.exists(f'{folder}/db.sql.gz')})
    return {'cadangan': hasil}


def _folder_cid(s, cid):
    if not isinstance(cid, str) or not RE_ID.match(cid):
        raise Galat('cadangan_tidak_valid')
    folder = f"{_folder_cadangan(s['nama'])}/{cid}"
    if not os.path.isfile(f'{folder}/meta.json'):
        raise Galat('cadangan_tidak_ditemukan', 404)
    return folder


def hapus_cadangan(body):
    s = _situs(body.get('nama', ''))
    folder = _folder_cid(s, body.get('id'))
    shutil.rmtree(folder)
    return {'ok': True}


def pulihkan(body):
    s = _situs(body.get('nama', ''))
    _wajib_konfirmasi(body, s['nama'])
    folder = _folder_cid(s, body.get('id'))
    with open(f'{folder}/meta.json') as f:
        if json.load(f)['nama'] != s['nama']:
            raise Galat('cadangan_bukan_milik_situs_ini')
    return _mulai('pulihkan', s['nama'], lambda tahap: _pulihkan(s, folder, tahap))


def _pulihkan(s, folder, tahap):
    pengaman = _buat_cadangan(s, 'sebelum-pulih', tahap)
    dump_pengaman = f"{_folder_cadangan(s['nama'])}/{pengaman}/db.sql.gz"
    k = _kredensial(s)
    kerja = f"{L.AKAR}/tmp/pulih-{secrets.token_hex(6)}"
    os.makedirs(kerja, mode=0o700)
    try:
        tahap('Membongkar arsip')
        r = subprocess.run(RENDAH + ['tar', '-xzpf', f'{folder}/berkas.tar.gz', '--numeric-owner', '--same-owner', '-C', kerja],
                           capture_output=True, text=True)
        baru = f"{kerja}/{os.path.basename(s['path'])}"
        if r.returncode or not os.path.isdir(baru):
            raise Galat(f'bongkar_gagal: {r.stderr.strip()[:200]}', 500)
        tahap('Menukar folder situs')
        lama = f'{kerja}/lama'
        os.rename(s['path'], lama)
        os.rename(baru, s['path'])
        try:
            subprocess.run(['restorecon', '-R', s['path']], capture_output=True)
            if k:
                # Sandi DB mungkin sudah diganti sesudah cadangan dibuat: konfigurasi lama harus ikut sandi yang berlaku
                _samakan_sandi(s, k)
            dump = f'{folder}/db.sql.gz'
            if k and os.path.exists(dump):
                tahap('Memulihkan database')
                _ganti_db(k, dump, dump_pengaman)
        except Exception:
            os.rename(s['path'], f'{kerja}/gagal')
            os.rename(lama, s['path'])
            raise
    finally:
        shutil.rmtree(kerja, ignore_errors=True)
    tahap('Mengecek situs')
    kode = L._http(s['nama']) if s['url'] else None
    return f'Dipulihkan, pengaman sebelumnya {pengaman}' + (f', HTTP {kode}' if kode is not None else '')


def _samakan_sandi(s, k):
    path = _berkas_konfig(s)
    teks = L.baca(path)
    baru = urai_wp(teks) if s['jenis'] == 'wordpress' else urai_env(teks)
    if baru['sandi'] != k['sandi']:
        _tulis_konfig(path, ganti_sandi_wp(teks, k['sandi']) if s['jenis'] == 'wordpress' else ganti_sandi_env(teks, k['sandi']))


# ---------- Database ----------
def ekspor(nama):
    """Dump ke berkas dulu agar lengkap terbukti sebelum dikirim; pemanggil menghapusnya sesudah terkirim."""
    s = _situs(nama)
    k = _wajib_kredensial(s)
    with _k:
        if _kerja['aktif']:
            raise Galat('sedang_ada_pekerjaan', 409)
    _siapkan_folder(f'{CADANGAN}/_sementara')
    path = f"{CADANGAN}/_sementara/{k['db']}-{secrets.token_hex(4)}.sql.gz"
    _dump(k['db'], path)
    return path, f"{k['db']}-{time.strftime('%Y%m%d-%H%M')}.sql.gz"


def terima_impor(rfile, panjang, q):
    s = _situs(q.get('nama', ''))
    _wajib_konfirmasi(q, s['nama'])
    k = _wajib_kredensial(s)
    if panjang <= 0 or panjang > 4 * 1024 ** 3:
        raise Galat('ukuran_tidak_valid')
    _ruang_cukup(s)
    _siapkan_folder(f'{CADANGAN}/_sementara')
    path = f"{CADANGAN}/_sementara/impor-{secrets.token_hex(6)}"
    try:
        with open(path, 'wb') as f:
            sisa = panjang
            while sisa:
                b = rfile.read(min(1048576, sisa))
                if not b:
                    raise Galat('unggahan_terputus')
                f.write(b)
                sisa -= len(b)
        periksa_dump(path)

        def kerja(tahap):
            try:
                pengaman = _buat_cadangan(s, 'sebelum-impor', tahap)
                tahap('Mengimpor database')
                dump_pengaman = f"{_folder_cadangan(s['nama'])}/{pengaman}/db.sql.gz"
                try:
                    _impor(k, path)
                except Galat:
                    _ganti_db(k, dump_pengaman, dump_pengaman)
                    raise Galat(f'impor_gagal, DB dikembalikan dari {pengaman}', 500)
                return f'Impor selesai, pengaman sebelumnya {pengaman}'
            finally:
                os.unlink(path)
        return _mulai('impor', s['nama'], kerja)
    except Exception:
        if os.path.exists(path):
            os.unlink(path)
        raise


def ganti_sandi_db(body):
    s = _situs(body.get('nama', ''))
    _wajib_konfirmasi(body, s['nama'])
    k = _wajib_kredensial(s)
    if k['sandi'] is None:
        raise Galat('sandi_di_konfigurasi_tak_terbaca')
    for x in L.daftar_situs():
        if x['nama'] != s['nama'] and (x['path'] != s['path']):
            try:
                lain = _kredensial(x)
            except Galat:
                continue
            if lain and lain['user'] == k['user']:
                raise Galat(f"user_db_dipakai_situs_lain: {x['nama']}")
    return _mulai('sandi-db', s['nama'], lambda tahap: _ganti_sandi(s, k, tahap))


def _set_sandi(user, sandi):
    hosts = _sql_admin(f"select host from mysql.user where user='{user}'").split()
    if not hosts:
        raise Galat('user_db_tidak_ada')
    _sql_admin(''.join(f"ALTER USER '{user}'@'{_kutip(h)}' IDENTIFIED BY '{_kutip(sandi)}';" for h in hosts))


def _ganti_sandi(s, k, tahap):
    path = _berkas_konfig(s)
    asli = L.baca(path)
    wp = s['jenis'] == 'wordpress'
    baru = secrets.token_urlsafe(24)
    teks_baru = ganti_sandi_wp(asli, baru) if wp else ganti_sandi_env(asli, baru)
    tahap('Mengganti sandi')
    _set_sandi(k['user'], baru)
    try:
        _tulis_konfig(path, teks_baru)
        cek = subprocess.run(['mysql', '-u', k['user'], '-N', '-e', 'select 1', k['db']], capture_output=True,
                             env={**os.environ, 'MYSQL_PWD': baru})
        if cek.returncode:
            raise Galat('sandi_baru_tak_bisa_dipakai', 500)
        if not wp and os.path.exists(f"{s['path']}/bootstrap/cache/config.php"):
            r = subprocess.run(['runuser', '-u', L.USER, '--', '/usr/local/bin/php', 'artisan', 'config:cache'],
                               cwd=s['path'], capture_output=True, text=True)
            if r.returncode:
                raise Galat(f'config_cache_gagal: {r.stderr.strip()[:200]}', 500)
    except Exception:
        _tulis_konfig(path, asli)
        _set_sandi(k['user'], k['sandi'])
        raise
    kode = L._http(s['nama']) if s['url'] else None
    return 'Sandi DB diganti dan konfigurasi diperbarui' + (f', HTTP {kode}' if kode is not None else '')


# ---------- Login sekali klik ----------
TIKET = r"""<?php
// Tiket login sekali pakai dari dashboard Velocity, terhapus begitu dibuka.
@unlink(__FILE__);
if (time() > %d) { http_response_code(410); exit('Tiket kedaluwarsa'); }
require __DIR__ . '/wp-load.php';
$u = get_users(['role' => 'administrator', 'number' => 1, 'orderby' => 'ID']);
if (!$u) { http_response_code(404); exit('Tidak ada administrator'); }
wp_set_current_user($u[0]->ID);
wp_set_auth_cookie($u[0]->ID, false, is_ssl());
do_action('wp_login', $u[0]->user_login, $u[0]);
wp_safe_redirect(admin_url());
exit;
"""


def masuk(body):
    s = _situs(body.get('nama', ''))
    if s['jenis'] != 'wordpress':
        raise Galat('bukan_wordpress')
    nama_berkas = f'vd-masuk-{secrets.token_hex(16)}.php'
    path = f"{s['path']}/{nama_berkas}"
    p = pwd.getpwnam(L.USER)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    with os.fdopen(fd, 'w') as f:
        f.write(TIKET % (int(time.time()) + 60))
    os.chown(path, p.pw_uid, p.pw_gid)
    timer = threading.Timer(120, lambda: os.path.exists(path) and os.unlink(path))
    timer.daemon = True
    timer.start()
    return {'url': f"{s['url']}/{nama_berkas}"}


# ---------- Log ----------
def baca_log(nama, sumber):
    s = _situs(nama)
    path = SUMBER_LOG.get(sumber)
    if not path:
        raise Galat('sumber_log_tidak_dikenal')
    n = s['nama'].removeprefix('apps/')
    tanda = (f' /{n}/', f' /{n} ') if sumber == 'akses' else (f'public_html/{n}/', f'apps/{n}/')
    try:
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            f.seek(max(0, f.tell() - 4 * 1048576))
            baris = f.read().decode('utf-8', 'replace').splitlines()
    except FileNotFoundError:
        baris = []
    return {'baris': [b[:2000] for b in baris if any(t in b for t in tanda)][-200:]}


# ---------- Cron ----------
def simpan_cron(body):
    teks, dasar = body.get('teks'), body.get('dasar')
    if not isinstance(teks, str) or len(teks) > 65536:
        raise Galat('cron_tidak_valid')
    sekarang = subprocess.run(['crontab', '-u', L.USER, '-l'], capture_output=True, text=True).stdout
    if dasar != sekarang:
        raise Galat('cron_sudah_berubah', 409)
    _siapkan_folder(f'{CADANGAN}/_cron')
    cadangan = f"{CADANGAN}/_cron/crontab-{time.strftime('%Y%m%d-%H%M%S')}"
    with open(cadangan, 'w') as f:
        f.write(sekarang)
    r = subprocess.run(['crontab', '-u', L.USER, '-'], input=teks.rstrip('\n') + '\n', capture_output=True, text=True)
    if r.returncode:
        raise Galat(f'cron_ditolak: {r.stderr.strip()[:200]}')
    return {'ok': True}


# ---------- Buat situs ----------
def nama_db_baru(nama):
    """Maksimal 32 karakter (batas aman user MariaDB/DirectAdmin); akhiran acak mencegah bentrok."""
    slug = re.sub(r'[^a-z0-9]', '', nama.lower())[:12] or 'situs'
    return f'{L.USER}_{slug}_{secrets.token_hex(2)}'


def buat_situs(body):
    nama = str(body.get('nama', '')).strip().lower()
    if not RE_NAMA_BARU.match(nama) or '..' in nama or nama == 'apps':
        raise Galat('nama_situs_tidak_valid')
    path = f'{L.AKAR}/public_html/{nama}'
    if os.path.lexists(path) or os.path.lexists(f'{L.AKAR}/apps/{nama}'):
        raise Galat('situs_sudah_ada', 409)
    with _k:
        if _kerja['aktif']:
            raise Galat('sedang_ada_pekerjaan', 409)
    db = nama_db_baru(nama)
    if _sql_admin(f"select count(*) from information_schema.schemata where schema_name='{db}';"
                  f"select count(*) from mysql.user where user='{db}'").split() != ['0', '0']:
        raise Galat('database_sudah_ada', 409)
    sandi = secrets.token_urlsafe(24)
    p = pwd.getpwnam(L.USER)
    os.mkdir(path, 0o755)
    try:
        os.chown(path, p.pw_uid, p.pw_gid)
        subprocess.run(['restorecon', path], capture_output=True)
        # Garis bawah di GRANT adalah wildcard: wajib di-escape agar hak hanya ke DB ini
        pola = db.replace('_', '\\_')
        _sql_admin(f"CREATE DATABASE `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                   f"CREATE USER '{db}'@'localhost' IDENTIFIED BY '{sandi}';"
                   f"GRANT ALL PRIVILEGES ON `{pola}`.* TO '{db}'@'localhost';")
        _siapkan_folder(BARU)
        with open(f'{BARU}/{nama}.json', 'w') as f:
            json.dump({'db': db, 'user': db}, f)
    except Exception:
        os.rmdir(path)
        _sql_admin(f"DROP DATABASE IF EXISTS `{db}`; DROP USER IF EXISTS '{db}'@'localhost';")
        raise

    def tambah(d):
        d['situs'] = sorted([*d['situs'], {'nama': nama, 'jenis': 'kosong', 'path': path, 'url': None, 'versi': None,
                                           'db': None, 'db_ukuran': None, 'disk': 0}], key=lambda x: x['nama'])
        d.setdefault('db_yatim', []).append({'nama': db, 'ukuran': 0})
    L.ubah_cache(tambah)
    return {'nama': nama, 'path': path, 'url': f'{L.URL}/{nama}', 'db': db, 'user': db, 'sandi': sandi}


# ---------- Hapus situs ----------
def _kredensial_hapus(s):
    k = _kredensial(s)
    if k:
        return k
    try:
        with open(f"{BARU}/{s['nama']}.json") as f:
            m = json.load(f)
    except (OSError, ValueError):
        return None
    if not RE_DB.match(m['db']) or not RE_USER.match(m['user']):
        raise Galat('nama_db_tidak_valid')
    return {**m, 'sandi': None}


def alasan_tolak_hapus(s, k, situs_lain, cron_teks, proses):
    """Alasan situs tak boleh dihapus, atau None. Lebih baik salah menolak daripada salah menghapus."""
    nama = s['nama'].removeprefix('apps/')
    for x in situs_lain:
        if x['nama'] == s['nama']:
            continue
        if x['path'].startswith(s['path'] + '/'):
            return f"memuat_situs_lain: {x['nama']}"
        if k and x.get('k') and (x['k']['db'] == k['db'] or x['k']['user'] == k['user']):
            return f"database_dipakai_situs_lain: {x['nama']}"
    for b in cron_teks.splitlines():
        if not b.lstrip().startswith('#') and (nama in b or s['path'] in b):
            return f'masih_dipakai_cron: {b[:80]}'
    for p in proses:
        # Pembungkus `bash -c` hanya memuat teks perintah (mis. sesi Claude yang menyebut domain); anak prosesnya tetap terperiksa
        if not re.match(r'^(/\S*/)?(ba)?sh -c ', p) and (nama in p or s['path'] in p):
            i = p.find(nama)
            return f'sedang_dipakai_proses: {p[max(0, i - 50):i + len(nama) + 10]}'
    return None


def _proses_berjalan():
    hasil = []
    for pid in filter(str.isdigit, os.listdir('/proc')):
        if int(pid) == os.getpid():
            continue
        try:
            with open(f'/proc/{pid}/cmdline', 'rb') as f:
                hasil.append(f.read().replace(b'\0', b' ').decode('utf-8', 'replace').strip())
        except OSError:
            pass
    return hasil


def hapus_situs(body):
    s = _situs(body.get('nama', ''))
    _wajib_konfirmasi(body, s['nama'])
    k = _kredensial_hapus(s)
    lain = []
    for x in L.daftar_situs():
        try:
            lain.append({**x, 'k': _kredensial(x)})
        except Galat:
            lain.append(x)
    cron = subprocess.run(['crontab', '-u', L.USER, '-l'], capture_output=True, text=True).stdout
    alasan = alasan_tolak_hapus(s, k, lain, cron, _proses_berjalan())
    if alasan:
        raise Galat(alasan, 409)
    _ruang_cukup(s)
    return _mulai('hapus', s['nama'], lambda tahap: _hapus_situs(s, k, tahap))


def _hapus_situs(s, k, tahap):
    cid = _buat_cadangan(s, 'sebelum-hapus', tahap)
    folder = f"{_folder_cadangan(s['nama'])}/{cid}"
    if k:
        # Hak akses ikut disimpan: tanpa ini cadangan DB sulit dipakai memulihkan situs yang sudah dihapus
        grants = _sql_admin(f"show grants for '{k['user']}'@'localhost'")
        fd = os.open(f'{folder}/grants.sql', os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(grants)
    tahap('Menghapus situs')
    tautan = f"{L.AKAR}/public_html/{s['nama']}"
    ada_tautan = s['jenis'] == 'laravel' and os.path.islink(tautan)
    kerja = f"{L.AKAR}/tmp/hapus-{secrets.token_hex(6)}"
    os.makedirs(kerja, mode=0o700)
    lama = f'{kerja}/lama'
    os.rename(s['path'], lama)
    try:
        if ada_tautan:
            os.unlink(tautan)
        if k:
            _sql_admin(f"DROP DATABASE IF EXISTS `{k['db']}`; DROP USER IF EXISTS '{k['user']}'@'localhost';")
    except Exception:
        os.rename(lama, s['path'])
        if ada_tautan and not os.path.lexists(tautan):
            os.symlink(f"{s['path']}/public", tautan)
        shutil.rmtree(kerja, ignore_errors=True)
        raise
    shutil.rmtree(kerja)
    baru = f"{BARU}/{s['nama']}.json"
    if os.path.exists(baru):
        os.unlink(baru)

    def buang(d):
        d['situs'] = [x for x in d['situs'] if x['nama'] != s['nama']]
        d['db_yatim'] = [x for x in d.get('db_yatim', []) if not k or x['nama'] != k['db']]
    L.ubah_cache(buang)
    return f"Situs dihapus. Cadangan: {folder}"
