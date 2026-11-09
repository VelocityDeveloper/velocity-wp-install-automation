"""Self-check pemindai staging: python3 services/test_staging_lokal.py"""
import os
import tempfile

import staging_lokal as S

WP = "<?php\n// define('DB_NAME', 'komentar');\ndefine( 'DB_NAME', 'db_wp' );\n"


def tulis(p, isi=''):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w') as f:
        f.write(isi)


with tempfile.TemporaryDirectory() as t:
    a = os.path.realpath(t)
    pub = f'{a}/public_html'
    tulis(f'{pub}/index.html')
    tulis(f'{pub}/satu.com/wp-config.php', WP)
    tulis(f'{pub}/satu.com/wp-includes/version.php', "<?php\n$wp_version = '6.9.1';\n")
    tulis(f'{pub}/induk.id/anak.com/wp-config.php', WP)
    os.makedirs(f'{pub}/kosong.com')
    os.makedirs(f'{pub}/.well-known')
    tulis(f'{pub}/pindah.com/.htaccess', 'Redirect')
    tulis(f'{a}/apps/lar.com/.env', 'APP=1\nDB_DATABASE="db_lar"\n')
    os.makedirs(f'{a}/apps/lar.com/public')
    tulis(f'{a}/apps/yatim.com/.env', 'DB_DATABASE=db_yatim\n')
    os.symlink(f'{a}/apps/lar.com/public', f'{pub}/lar.com')
    # symlink jahat: wp-config menunjuk berkas lain → isinya tidak boleh terbaca
    tulis(f'{a}/rahasia', "define('DB_NAME', 'bocor');")
    os.makedirs(f'{pub}/jahat.com')
    os.symlink(f'{a}/rahasia', f'{pub}/jahat.com/wp-config.php')

    s = {x['nama']: x for x in S.pindai(a)}
    assert set(s) == {'satu.com', 'induk.id/anak.com', 'kosong.com', 'pindah.com', 'lar.com', 'apps/yatim.com', 'jahat.com'}, s
    assert (s['satu.com']['jenis'], s['satu.com']['versi'], s['satu.com']['db']) == ('wordpress', '6.9.1', 'db_wp')
    assert s['induk.id/anak.com']['url'].endswith('/induk.id/anak.com')
    assert s['kosong.com']['jenis'] == 'kosong' and s['kosong.com']['url'] is None
    assert s['pindah.com']['jenis'] == 'lain'
    assert (s['lar.com']['jenis'], s['lar.com']['db'], s['lar.com']['path']) == ('laravel', 'db_lar', f'{a}/apps/lar.com')
    assert s['apps/yatim.com']['url'] is None and s['apps/yatim.com']['db'] == 'db_yatim'
    assert s['jahat.com']['jenis'] == 'wordpress' and s['jahat.com']['db'] is None

    daftar = list(s.values())
    assert S.gabung(daftar, {'db_wp': 10, 'db_tua': 5}) == [{'nama': 'db_tua', 'ukuran': 5}]
    assert s['satu.com']['db_ukuran'] == 10 and s['lar.com']['db_ukuran'] is None
    # cek HTTP hanya untuk nama hasil pindai: tak boleh jadi jalan ke path sembarang
    S._st.update(data={'situs': daftar}, muat=True)
    assert S.cek_http('../../etc/passwd') == {'galat': 'situs_tidak_dikenal'}
    assert S.cek_http('kosong.com') == {'galat': 'situs_tidak_dikenal'}
print('OK')

# ---------- Tahap 2 ----------
import gzip  # noqa: E402

import staging_aksi as A  # noqa: E402

WPC = "<?php\ndefine( 'DB_NAME', 'vdcenterbiz_a' );\ndefine( 'DB_USER', 'vdcenterbiz_a' );\ndefine( 'DB_PASSWORD', 'la\\\"ma' );\ndefine('DB_HOST','localhost');\n"
k = A.urai_wp(WPC)
assert (k['db'], k['user']) == ('vdcenterbiz_a', 'vdcenterbiz_a')
assert "define( 'DB_PASSWORD', 'BARU' );" in A.ganti_sandi_wp(WPC, 'BARU')
assert A.urai_wp(A.ganti_sandi_wp(WPC, 'BARU'))['sandi'] == 'BARU'
ENV = 'APP=1\nDB_DATABASE=vdcenterbiz_a\nDB_USERNAME=vdcenterbiz_a\nDB_PASSWORD="la ma"\n'
assert A.urai_env(ENV) == {'db': 'vdcenterbiz_a', 'user': 'vdcenterbiz_a', 'sandi': 'la ma'}
assert A.urai_env(A.ganti_sandi_env(ENV, 'BARU'))['sandi'] == 'BARU'
try:
    A.ganti_sandi_env('APP=1\n', 'x')
    raise AssertionError('harus gagal')
except A.Galat:
    pass


def ditolak(isi, gz=False):
    with tempfile.NamedTemporaryFile(suffix='.sql') as f:
        f.write(gzip.compress(isi) if gz else isi)
        f.flush()
        try:
            A.periksa_dump(f.name)
            return False
        except A.Galat:
            return True


# Jebakan 20 Okt: dump --databases menulis ke DB asli walau diimpor ke DB lain
for buruk in (b'USE `lain`;\n', b'/*!40000 DROP DATABASE IF EXISTS `x`*/;\n', b'CREATE DATABASE x;\n',
              b'/*!40000 CREATE DATABASE `x` */;\n', b'  use x;\n', b'GRANT ALL ON *.* TO x;\n', b'ALTER USER a;\n'):
    assert ditolak(buruk), buruk
    assert ditolak(b'-- awal\n' + buruk, gz=True), buruk
baik = b"DROP TABLE IF EXISTS `t`;\nCREATE TABLE `t` (a int);\nINSERT INTO `t` VALUES ('USE x;\\nDROP DATABASE y');\n"
assert not ditolak(baik) and not ditolak(baik, gz=True)
assert not ditolak(b'INSERT ' + b'x' * 70000 + b'USE y\n')  # potongan tengah baris panjang bukan awal baris
assert ditolak(b'INSERT ' + b'x' * 70000 + b'\nUSE y\n')  # baris sesudah baris panjang tetap diperiksa

# Nama DB dari konfigurasi klien tak boleh lolos ke SQL
assert not A.RE_DB.match('vdcenterbiz_a`; drop') and not A.RE_DB.match('mysql') and A.RE_DB.match('vdcenterbiz_a1')
assert A.RE_ID.match('20261102-210000-sebelum-pulih') and not A.RE_ID.match('../../etc')
print('OK aksi')

# ---------- Tahap 3 ----------
for buruk in ('', '../x', 'a/b', '.x', 'x.', '-x', 'a b', 'a;b', 'A' * 70, 'x' * 64):
    assert not A.RE_NAMA_BARU.match(buruk), buruk
for baik in ('a', 'contoh.co.id', 'situs-baru.test', 'x' * 63):
    assert A.RE_NAMA_BARU.match(baik), baik
for n in ('a', 'situs-baru-yang-panjang-sekali.co.id', '...'):
    db = A.nama_db_baru(n)
    assert A.RE_DB.match(db) and len(db) <= 32, db

BASE = '/home/x/public_html'
S1 = {'nama': 'a.com', 'path': f'{BASE}/a.com'}
K1 = {'db': 'vdcenterbiz_a', 'user': 'vdcenterbiz_a'}
T = lambda s=S1, k=K1, lain=(), cron='', proses=(): A.alasan_tolak_hapus(s, k, list(lain), cron, list(proses))
assert T() is None
assert T(lain=[{'nama': 'a.com', 'path': S1['path'], 'k': K1}]) is None  # dirinya sendiri
assert T(lain=[{'nama': 'b.com', 'path': f'{BASE}/b.com', 'k': {'db': 'vdcenterbiz_b', 'user': 'vdcenterbiz_b'}}]) is None
assert T(lain=[{'nama': 'b.com', 'path': f'{BASE}/b.com', 'k': K1}]).startswith('database_dipakai_situs_lain')
assert T(lain=[{'nama': 'b.com', 'path': f'{BASE}/b.com', 'k': {'db': 'vdcenterbiz_b', 'user': K1['user']}}]).startswith('database_dipakai')
assert T(lain=[{'nama': 'a.com/anak', 'path': f'{BASE}/a.com/anak'}]).startswith('memuat_situs_lain')
assert T(cron='* * * * * cd /home/x/apps/a.com && php artisan x').startswith('masih_dipakai_cron')
assert T(cron='# * * * * * cd /home/x/apps/a.com') is None  # baris komentar tak aktif
assert T(proses=['/usr/bin/installer-runner a.com']).startswith('sedang_dipakai_proses')
assert T(s={'nama': 'apps/l.com', 'path': '/home/x/apps/l.com'}, cron='cd /home/x/apps/l.com').startswith('masih_dipakai_cron')
assert T(proses=['/bin/bash -c cat a.com']) is None and T(proses=['bash -c x a.com']) is None
assert T(proses=['bash /opt/x/installer-runner a.com']).startswith('sedang_dipakai_proses')
print('OK tahap 3')
