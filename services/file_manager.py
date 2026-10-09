#!/usr/bin/env python3
"""File Manager dashboard Local PC (pengganti File Browser di /files/).

Cakupan seluruh sistem (/), tanpa login: nginx membatasi ke LAN/Tailscale, dan setiap aksi yang
mengubah berkas wajib datang dari halaman dashboard sendiri (Origin = Host), sama dengan kontrol daya.
Pengaman: folder tingkat atas (/etc, /usr, /home, ...) tidak bisa dihapus/dipindah/diganti nama;
berkas & folder baru ikut pemilik folder induknya (situs di /home/<user> tetap milik user itu).
"""
import fnmatch
import json
import mimetypes
import os
import shutil
import stat
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address, ip_network
from urllib.parse import parse_qs, quote, urlsplit

PORT = 9123
LAN_NETWORKS = tuple(map(ip_network, ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '100.64.0.0/10')))
BATAS_BACA_TEKS = 5 * 1024 * 1024
BATAS_ENTRI = 20000
POTONGAN = 1024 * 1024
BATAS_HASIL_CARI = 500
BATAS_WAKTU_CARI = 15  # detik
# Sistem berkas virtual: isinya bukan berkas sungguhan & bisa membuat penelusuran menggantung
LEWATI_CARI = {'/proc', '/sys', '/dev', '/run'}

_NAMA_USER = {}
_NAMA_GRUP = {}


class Galat(Exception):
    def __init__(self, kode, status=400):
        super().__init__(kode)
        self.kode = kode
        self.status = status


def nama_user(uid):
    if uid not in _NAMA_USER:
        import pwd
        try:
            _NAMA_USER[uid] = pwd.getpwuid(uid).pw_name
        except KeyError:
            _NAMA_USER[uid] = str(uid)
    return _NAMA_USER[uid]


def nama_grup(gid):
    if gid not in _NAMA_GRUP:
        import grp
        try:
            _NAMA_GRUP[gid] = grp.getgrgid(gid).gr_name
        except KeyError:
            _NAMA_GRUP[gid] = str(gid)
    return _NAMA_GRUP[gid]


def jalur(p):
    """Path absolut ternormalisasi (symlink TIDAK diikuti, supaya hapus/ganti nama mengenai tautannya)."""
    if not isinstance(p, str) or not p.startswith('/') or '\0' in p:
        raise Galat('path_tidak_valid')
    return os.path.normpath(p).replace('//', '/')


def dilindungi(p):
    # / dan anak langsungnya (/etc, /usr, /home, ...) terlalu berbahaya untuk dihapus/dipindah
    return p.count('/') <= 1


def nama_valid(nama):
    if not isinstance(nama, str) or not nama or nama in ('.', '..') or '/' in nama or '\0' in nama or len(nama) > 255:
        raise Galat('nama_tidak_valid')
    return nama


def ikut_pemilik(p, induk=None):
    """Samakan pemilik berkas/folder baru dengan folder induknya."""
    try:
        st = os.stat(induk or os.path.dirname(p))
        os.lchown(p, st.st_uid, st.st_gid)
    except OSError:
        pass


def ikut_pemilik_pohon(akar, induk):
    ikut_pemilik(akar, induk)
    if os.path.isdir(akar) and not os.path.islink(akar):
        for d, dirs, files in os.walk(akar):
            for n in dirs + files:
                ikut_pemilik(os.path.join(d, n), induk)


def info(p, nama=None):
    st = os.lstat(p)
    link = stat.S_ISLNK(st.st_mode)
    tujuan = None
    jenis = 'berkas'
    if link:
        tujuan = os.readlink(p)
        try:
            jenis = 'folder' if stat.S_ISDIR(os.stat(p).st_mode) else 'berkas'
        except OSError:
            jenis = 'rusak'
    elif stat.S_ISDIR(st.st_mode):
        jenis = 'folder'
    elif not stat.S_ISREG(st.st_mode):
        jenis = 'khusus'
    return {
        'nama': nama or os.path.basename(p) or '/', 'jenis': jenis, 'link': tujuan,
        'ukuran': st.st_size if jenis == 'berkas' and not link else None,
        'waktu': int(st.st_mtime), 'mode': stat.filemode(st.st_mode), 'oktal': oct(st.st_mode & 0o7777)[2:],
        'pemilik': nama_user(st.st_uid), 'grup': nama_grup(st.st_gid),
    }


def daftar(p):
    p = jalur(p)
    if not os.path.isdir(p):
        raise Galat('bukan_folder', 404)
    entri = []
    with os.scandir(p) as it:
        for e in it:
            if len(entri) >= BATAS_ENTRI:
                break
            try:
                entri.append(info(e.path, e.name))
            except OSError:
                entri.append({'nama': e.name, 'jenis': 'rusak'})
    entri.sort(key=lambda x: (x['jenis'] != 'folder', x['nama'].lower()))
    du = shutil.disk_usage(p)
    return {'path': p, 'entri': entri, 'terpotong': len(entri) >= BATAS_ENTRI,
            'disk': {'total': du.total, 'sisa': du.free}}


def cari(akar, kata, jenis='semua', tersembunyi=True):
    """Cari nama berkas/folder di akar beserta seluruh subfoldernya (symlink tidak diikuti).

    Kata tanpa * atau ? = cocok sebagian (tanpa beda huruf besar/kecil); dengan wildcard = pola fnmatch.
    Dibatasi BATAS_HASIL_CARI hasil & BATAS_WAKTU_CARI detik supaya pencarian dari / tidak membebani server.
    """
    akar = jalur(akar)
    if not os.path.isdir(akar):
        raise Galat('bukan_folder', 404)
    kata = (kata or '').strip().lower()
    if not kata:
        raise Galat('kata_kosong')
    pola = any(c in kata for c in '*?[')
    cocok = (lambda n: fnmatch.fnmatchcase(n.lower(), kata)) if pola else (lambda n: kata in n.lower())
    hasil, diperiksa, habis_waktu = [], 0, False
    batas = time.monotonic() + BATAS_WAKTU_CARI
    tumpukan = [akar]
    while tumpukan:
        d = tumpukan.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for e in it:
                diperiksa += 1
                if not tersembunyi and e.name.startswith('.'):
                    continue
                try:
                    folder = e.is_dir(follow_symlinks=False)
                except OSError:
                    folder = False
                if folder and e.path not in LEWATI_CARI:
                    tumpukan.append(e.path)
                if cocok(e.name) and (jenis == 'semua' or (jenis == 'folder') == folder):
                    try:
                        r = info(e.path, e.name)
                    except OSError:
                        r = {'nama': e.name, 'jenis': 'rusak'}
                    r['path'] = e.path
                    hasil.append(r)
                    if len(hasil) >= BATAS_HASIL_CARI:
                        break
        if len(hasil) >= BATAS_HASIL_CARI:
            break
        if time.monotonic() > batas:
            habis_waktu = True
            break
    hasil.sort(key=lambda x: (x['jenis'] != 'folder', x['path'].lower()))
    return {'path': akar, 'kata': kata, 'hasil': hasil, 'diperiksa': diperiksa,
            'terpotong': len(hasil) >= BATAS_HASIL_CARI, 'habis_waktu': habis_waktu}


def baca_teks(p):
    p = jalur(p)
    st = os.stat(p)
    if not stat.S_ISREG(st.st_mode):
        raise Galat('bukan_berkas')
    if st.st_size > BATAS_BACA_TEKS:
        raise Galat('berkas_terlalu_besar')
    with open(p, 'rb') as f:
        isi = f.read()
    if b'\0' in isi[:8192]:
        raise Galat('berkas_biner')
    try:
        teks = isi.decode('utf-8')
    except UnicodeDecodeError:
        teks = isi.decode('latin-1')
    # string: nanodetik melebihi presisi angka JavaScript
    return {'path': p, 'isi': teks, 'waktu': str(st.st_mtime_ns), 'ukuran': st.st_size}


def tulis_teks(b):
    p = jalur(b.get('path'))
    isi = b.get('isi')
    if not isinstance(isi, str):
        raise Galat('isi_tidak_valid')
    ada = os.path.lexists(p)
    if ada:
        st = os.stat(p)
        if not stat.S_ISREG(st.st_mode):
            raise Galat('bukan_berkas')
        # Cegah menimpa perubahan orang/proses lain sejak berkas dibuka
        if b.get('waktu') is not None and str(b['waktu']) != str(st.st_mtime_ns):
            raise Galat('berkas_berubah', 409)
    elif not b.get('baru'):
        raise Galat('tidak_ditemukan', 404)
    sementara = os.path.join(os.path.dirname(p), f'.{os.path.basename(p)}.fm-{os.getpid()}.tmp')
    with open(sementara, 'wb') as f:
        f.write(isi.encode('utf-8'))
    if ada:
        os.chmod(sementara, stat.S_IMODE(st.st_mode))
        os.chown(sementara, st.st_uid, st.st_gid)
    else:
        os.chmod(sementara, 0o644)
        ikut_pemilik(sementara, os.path.dirname(p))
    # os.replace mengikuti path asli; symlink ke berkas tetap dipertahankan dengan menulis ke tujuannya
    os.replace(sementara, os.path.realpath(p) if os.path.islink(p) else p)
    return {'waktu': str(os.stat(p).st_mtime_ns)}


def buat(b):
    induk = jalur(b.get('path'))
    p = os.path.join(induk, nama_valid(b.get('nama')))
    if os.path.lexists(p):
        raise Galat('sudah_ada', 409)
    if b.get('jenis') == 'folder':
        os.mkdir(p, 0o755)
    else:
        with open(p, 'x'):
            pass
        os.chmod(p, 0o644)
    ikut_pemilik(p, induk)
    return {'ok': True}


def ganti_nama(b):
    p = jalur(b.get('path'))
    if dilindungi(p):
        raise Galat('dilindungi', 403)
    baru = os.path.join(os.path.dirname(p), nama_valid(b.get('nama')))
    if os.path.lexists(baru):
        raise Galat('sudah_ada', 409)
    os.rename(p, baru)
    return {'ok': True}


def daftar_path(b):
    paths = b.get('paths')
    if not isinstance(paths, list) or not paths or len(paths) > 1000:
        raise Galat('path_tidak_valid')
    return [jalur(x) for x in paths]


def hapus(b):
    paths = daftar_path(b)
    for p in paths:
        if dilindungi(p):
            raise Galat('dilindungi', 403)
    for p in paths:
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
        elif os.path.lexists(p):
            os.unlink(p)
    return {'ok': True}


def salin_pindah(b, pindah):
    paths = daftar_path(b)
    tujuan = jalur(b.get('tujuan'))
    if not os.path.isdir(tujuan):
        raise Galat('tujuan_bukan_folder')
    timpa = bool(b.get('timpa'))
    rencana = []
    for p in paths:
        if pindah and dilindungi(p):
            raise Galat('dilindungi', 403)
        target = os.path.join(tujuan, os.path.basename(p))
        if target == p or (tujuan + '/').startswith(p + '/'):
            raise Galat('tujuan_di_dalam_sumber')
        if os.path.lexists(target) and not timpa:
            raise Galat('sudah_ada', 409)
        rencana.append((p, target))
    for p, target in rencana:
        if os.path.lexists(target):
            if os.path.isdir(target) and not os.path.islink(target):
                shutil.rmtree(target)
            else:
                os.unlink(target)
        if pindah:
            shutil.move(p, target)
        else:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.copytree(p, target, symlinks=True)
            else:
                shutil.copy2(p, target, follow_symlinks=False)
            ikut_pemilik_pohon(target, tujuan)
    return {'ok': True}


def buat_zip(b):
    paths = daftar_path(b)
    induk = os.path.dirname(paths[0])
    nama = nama_valid(b.get('nama') or (os.path.basename(paths[0]) if len(paths) == 1 else 'arsip') + '.zip')
    if not nama.lower().endswith('.zip'):
        nama += '.zip'
    target = os.path.join(induk, nama)
    if os.path.lexists(target):
        raise Galat('sudah_ada', 409)
    sementara = target + '.fm-tmp'
    try:
        with zipfile.ZipFile(sementara, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            for p in paths:
                dasar = os.path.dirname(p)
                if os.path.isdir(p) and not os.path.islink(p):
                    for d, dirs, files in os.walk(p):
                        rel = os.path.relpath(d, dasar)
                        if not dirs and not files:
                            z.write(d, rel + '/')
                        for n in files:
                            f = os.path.join(d, n)
                            if os.path.isfile(f):
                                z.write(f, os.path.join(rel, n))
                elif os.path.isfile(p):
                    z.write(p, os.path.basename(p))
        os.replace(sementara, target)
    finally:
        if os.path.exists(sementara):
            os.unlink(sementara)
    ikut_pemilik(target, induk)
    return {'ok': True, 'nama': nama}


def ekstrak_zip(b):
    p = jalur(b.get('path'))
    tujuan = jalur(b.get('tujuan') or os.path.dirname(p))
    os.makedirs(tujuan, exist_ok=True)
    akar = os.path.realpath(tujuan)
    with zipfile.ZipFile(p) as z:
        anggota = z.infolist()
        for m in anggota:
            # Zip slip: tolak entri yang keluar dari folder tujuan
            t = os.path.realpath(os.path.join(akar, m.filename))
            if t != akar and not t.startswith(akar + '/'):
                raise Galat('zip_tidak_aman')
        if not b.get('timpa'):
            ada = [m.filename for m in anggota if not m.is_dir() and os.path.lexists(os.path.join(akar, m.filename))]
            if ada:
                raise Galat('sudah_ada', 409)
        z.extractall(akar)
    # Hanya isi zip (termasuk folder perantara yang tak tercatat eksplisit), bukan isi lama folder tujuan
    sudah = set()
    for m in anggota:
        bagian = m.filename.rstrip('/').split('/')
        for i in range(1, len(bagian) + 1):
            t = os.path.join(akar, *bagian[:i])
            if t not in sudah:
                sudah.add(t)
                ikut_pemilik(t, tujuan)
    return {'ok': True, 'jumlah': len(anggota)}


def chmod(b):
    p = jalur(b.get('path'))
    mode = str(b.get('mode') or '')
    if not mode or len(mode) > 4 or any(c not in '01234567' for c in mode):
        raise Galat('mode_tidak_valid')
    os.chmod(p, int(mode, 8))
    return {'ok': True}


AKSI = {
    '/api/fm/tulis': tulis_teks,
    '/api/fm/buat': buat,
    '/api/fm/ganti-nama': ganti_nama,
    '/api/fm/hapus': hapus,
    '/api/fm/salin': lambda b: salin_pindah(b, False),
    '/api/fm/pindah': lambda b: salin_pindah(b, True),
    '/api/fm/zip': buat_zip,
    '/api/fm/unzip': ekstrak_zip,
    '/api/fm/chmod': chmod,
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def json_response(self, status, data):
        body = json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def dari_lan(self):
        try:
            return any(ip_address(self.headers.get('X-Real-IP', self.client_address[0])) in n for n in LAN_NETWORKS)
        except ValueError:
            return False

    def dari_dashboard(self):
        origin = self.headers.get('Origin', '')
        origin_host = urlsplit(origin).hostname if origin else None
        return self.dari_lan() and origin_host == self.headers.get('Host', '').split(':', 1)[0]

    def jalankan(self, fungsi):
        try:
            self.json_response(200, fungsi())
        except Galat as e:
            self.json_response(e.status, {'error': e.kode})
        except FileNotFoundError:
            self.json_response(404, {'error': 'tidak_ditemukan'})
        except PermissionError:
            self.json_response(403, {'error': 'izin_ditolak'})
        except zipfile.BadZipFile:
            self.json_response(400, {'error': 'zip_rusak'})
        except OSError as e:
            self.json_response(400, {'error': f'os: {e.strerror or e}'})

    def do_GET(self):
        path, _, query = self.path.partition('?')
        q = {k: v[0] for k, v in parse_qs(query).items()}
        if not self.dari_lan():
            self.json_response(403, {'error': 'forbidden'})
            return
        if path == '/api/fm/daftar':
            self.jalankan(lambda: daftar(q.get('path', '/')))
        elif path == '/api/fm/baca':
            self.jalankan(lambda: baca_teks(q.get('path', '')))
        elif path == '/api/fm/cari':
            self.jalankan(lambda: cari(q.get('path', '/'), q.get('q', ''), q.get('jenis', 'semua'), q.get('tersembunyi') != '0'))
        elif path == '/api/fm/info':
            self.jalankan(lambda: info(jalur(q.get('path', ''))))
        elif path == '/api/fm/unduh':
            self.unduh(q.get('path', ''), q.get('lihat') == '1')
        else:
            self.json_response(404, {'error': 'tidak_ada'})

    def unduh(self, p, lihat):
        try:
            p = jalur(p)
            f = open(p, 'rb')
        except Galat as e:
            self.json_response(e.status, {'error': e.kode})
            return
        except IsADirectoryError:
            self.json_response(400, {'error': 'bukan_berkas'})
            return
        except OSError:
            self.json_response(404, {'error': 'tidak_ditemukan'})
            return
        with f:
            ukuran = os.fstat(f.fileno()).st_size
            nama = os.path.basename(p)
            jenis = (mimetypes.guess_type(nama)[0] or 'application/octet-stream') if lihat else 'application/octet-stream'
            # Pratinjau HTML/SVG dari berkas sistem jangan dijalankan di origin dashboard
            if lihat and jenis in ('text/html', 'image/svg+xml', 'application/xhtml+xml', 'application/javascript', 'text/javascript'):
                jenis = 'text/plain; charset=utf-8'
            self.send_response(200)
            self.send_header('Content-Type', jenis)
            self.send_header('Content-Length', str(ukuran))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; img-src 'self'; media-src 'self'; style-src 'unsafe-inline'")
            self.send_header('Content-Disposition', f"{'inline' if lihat else 'attachment'}; filename*=UTF-8''{quote(nama)}")
            self.end_headers()
            shutil.copyfileobj(f, self.wfile, POTONGAN)

    def do_PUT(self):
        # Unggah: badan permintaan = isi berkas mentah. ?path=<folder>&nama=<relatif, boleh a/b/c.txt>&timpa=1
        path, _, query = self.path.partition('?')
        if path != '/api/fm/unggah':
            self.json_response(404, {'error': 'tidak_ada'})
            return
        if not self.dari_dashboard():
            self.json_response(403, {'error': 'forbidden'})
            self.close_connection = True
            return
        q = {k: v[0] for k, v in parse_qs(query).items()}
        self.jalankan(lambda: self.terima_unggahan(q))

    def terima_unggahan(self, q):
        try:
            panjang = int(self.headers.get('Content-Length', ''))
        except ValueError:
            self.close_connection = True
            raise Galat('panjang_tidak_ada', 411)
        try:
            induk = jalur(q.get('path', ''))
            bagian = [nama_valid(x) for x in (q.get('nama') or '').split('/')]
            if not os.path.isdir(induk):
                raise Galat('tujuan_bukan_folder')
            # Folder perantara (unggah folder) dibuat & diberi pemilik folder induk
            d = induk
            for n in bagian[:-1]:
                d = os.path.join(d, n)
                if not os.path.isdir(d):
                    os.mkdir(d, 0o755)
                    ikut_pemilik(d, induk)
            target = os.path.join(d, bagian[-1])
            if os.path.lexists(target) and q.get('timpa') != '1':
                raise Galat('sudah_ada', 409)
        except Exception:
            self.close_connection = True  # badan belum dibaca
            raise
        sementara = os.path.join(d, f'.{bagian[-1]}.fm-{threading.get_ident()}.part')
        sisa = panjang
        try:
            with open(sementara, 'wb') as f:
                while sisa > 0:
                    potong = self.rfile.read(min(POTONGAN, sisa))
                    if not potong:
                        raise Galat('unggahan_terputus')
                    f.write(potong)
                    sisa -= len(potong)
            ada = os.path.lexists(target)
            st = os.stat(target) if ada else None
            os.replace(sementara, target)
            if st:
                os.chmod(target, stat.S_IMODE(st.st_mode))
                os.chown(target, st.st_uid, st.st_gid)
            else:
                os.chmod(target, 0o644)
                ikut_pemilik(target, d)
        finally:
            if os.path.exists(sementara):
                os.unlink(sementara)
                self.close_connection = True
        return {'ok': True}

    def do_POST(self):
        fungsi = AKSI.get(self.path)
        if not fungsi:
            self.json_response(404, {'error': 'tidak_ada'})
            return
        if not self.dari_dashboard():
            self.json_response(403, {'error': 'forbidden'})
            self.close_connection = True
            return
        try:
            panjang = int(self.headers.get('Content-Length', 0))
            if panjang > 20 * 1024 * 1024:
                raise ValueError
            body = json.loads(self.rfile.read(panjang) or b'{}')
        except ValueError:
            self.close_connection = True
            body = None
        if not isinstance(body, dict):
            self.json_response(400, {'error': 'body_tidak_valid'})
            return
        mulai = time.time()
        self.jalankan(lambda: fungsi(body))
        print(f'{self.headers.get("X-Real-IP", self.client_address[0])} {self.path} '
              f'{json.dumps({k: v for k, v in body.items() if k != "isi"}, ensure_ascii=False)[:300]} {time.time() - mulai:.1f}s', flush=True)

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    os.umask(0o022)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
