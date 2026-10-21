#!/usr/bin/env python3
"""VelocityGuard realtime — berkas web yang baru ditulis langsung diperiksa tanda tangan VD.* (jalan di server hosting).

fanotify FAN_CLOSE_WRITE dengan tanda mount (satu tanda untuk seluruh mount /home, bukan watch per folder seperti
inotify yang habis di jutaan folder). Setiap berkas yang selesai ditulis di /home/<akun>/domains/ diperiksa fungsi
periksa() dari agen antivirus (server_antivirus_agent.py, dipasang sebagai agen.py di folder yang sama), aturan
ekstensi/ukuran sama dengan scan berkas.

Setelan dari dashboard (aksi agen `realtime_setelan`): /var/lib/velocity-av/setelan.json {mode, putih}. Mode
`otomatis` → berkas yang kena aturan sangat yakin (KARANTINA_OTOMATIS) langsung dikarantina lewat agen.karantina()
(/root/velocity-karantina, bisa dikembalikan dari dashboard); berkas inti WP tidak pernah. Whitelist dilewati.

Keluaran (dibaca dashboard lewat SSH, aksi agen `realtime`):
  /var/lib/velocity-av/temuan.jsonl   satu baris JSON per temuan (format sama dengan temuan scan + t, proses, pid)
  /var/lib/velocity-av/detak.json     tiap 60 dtk: mulai, diperiksa, temuan, overflow, galat, sidik agen

Celah yang diketahui (ditutup scan mingguan semua berkas): rename/move di dalam mount yang sama tidak memicu
FAN_CLOSE_WRITE, event bisa hilang saat antrean kernel penuh (dihitung `overflow`), dan berkas lama tidak dibaca.
Dijalankan unit systemd velocity-av-realtime (nice, IO idle, CPUQuota) — lihat scripts/velocity-av-realtime-pasang.
"""
import ctypes
import hashlib
import json
import os
import select
import struct
import sys
import time

FOLDER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FOLDER)
import agen  # noqa: E402  (salinan server_antivirus_agent.py)

DATA = '/var/lib/velocity-av'
TEMUAN = os.path.join(DATA, 'temuan.jsonl')
DETAK = os.path.join(DATA, 'detak.json')
SETELAN = os.path.join(DATA, 'setelan.json')
# Hanya aturan yang praktis tak pernah positif palsu (diuji 139 rb PHP lokal); sisanya cukup dilaporkan
KARANTINA_OTOMATIS = {'VD.PHP.EvalUnduhTag', 'VD.PHP.IncludeUnduh', 'VD.Webshell.Nama', 'VD.Webshell.FileManager',
                      'VD.WP.PluginPalsu', 'VD.PHP.EvalInput', 'VD.WP.LoginPaksa'}
BERKAS_INTI = ('/index.php', '/wp-config.php', '/.htaccess', '/wp-load.php', '/wp-settings.php')
AKAR = '/home'
MAKS_TEMUAN_BERKAS = 20 * 1024 * 1024  # temuan.jsonl diputar ke .1 bila lebih besar

FAN_CLOSE_WRITE = 0x08
FAN_Q_OVERFLOW = 0x4000
FAN_CLOEXEC = 0x01
FAN_CLASS_NOTIF = 0x00
FAN_MARK_ADD = 0x01
FAN_MARK_MOUNT = 0x10
AT_FDCWD = -100
META = struct.Struct('=IBBHQii')  # fanotify_event_metadata: event_len, vers, reserved, metadata_len, mask, fd, pid

libc = ctypes.CDLL(None, use_errno=True)
libc.fanotify_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
libc.fanotify_mark.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_uint64, ctypes.c_int, ctypes.c_char_p]


def sidik_agen():
    with open(os.path.join(FOLDER, 'agen.py'), 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


def pasang_fanotify():
    fd = libc.fanotify_init(FAN_CLOEXEC | FAN_CLASS_NOTIF, os.O_RDONLY | os.O_LARGEFILE | os.O_CLOEXEC)
    if fd < 0:
        raise OSError(ctypes.get_errno(), 'fanotify_init')
    if libc.fanotify_mark(fd, FAN_MARK_ADD | FAN_MARK_MOUNT, FAN_CLOSE_WRITE, AT_FDCWD, AKAR.encode()) < 0:
        raise OSError(ctypes.get_errno(), 'fanotify_mark ' + AKAR)
    return fd


def muat_setelan(lama):
    """(setelan, sha) — dibaca ulang hanya bila isi berkas berubah."""
    try:
        with open(SETELAN, 'rb') as f:
            isi = f.read()
    except OSError:
        return {'mode': 'laporan', 'putih': []}, ''
    sha = hashlib.sha256(isi).hexdigest()[:12]
    if lama and lama[1] == sha:
        return lama
    try:
        return json.loads(isi.decode()), sha
    except ValueError:
        return {'mode': 'laporan', 'putih': []}, sha


def boleh_otomatis(path, tanda):
    if '/wp-admin/' in path or '/wp-includes/' in path or path.endswith(BERKAS_INTI):
        return False
    return any(x['id'] in KARANTINA_OTOMATIS for x in tanda)


def perlu_diperiksa(path):
    """(ext, tersembunyi) bila path berkas web yang diperiksa scan berkas, selain itu None."""
    bagian = path.split('/')
    if len(bagian) < 6 or bagian[1] != 'home' or bagian[3] != 'domains':
        return None
    if any(b in agen.LEWATI for b in bagian[4:-1]):
        return None
    nama = bagian[-1]
    ext = agen.ekstensi(nama)
    tersembunyi = ext not in agen.EKSTENSI and nama.startswith('.')
    if (ext not in agen.EKSTENSI and not tersembunyi) or ('/cache' in path and ext not in agen.PHP and ext != 'htaccess'):
        return None
    return ext, tersembunyi


def baca(fd, st, ext, tersembunyi):
    """Isi berkas dari fd event (bukan buka ulang path: berkas bisa sudah diganti), None bila dilewati."""
    if ext in agen.GAMBAR and st.st_size > 262144:
        return None
    maks = 1048576 if tersembunyi or ext in ('html', 'htm', 'js', 'txt') else agen.MAKS_BACA
    if st.st_size == 0:
        return None
    # Berkas besar: awal + akhir saja (agen.POTONG_BESAR); agen_sama() lalu tak cocok → tidak dikarantina otomatis
    n = agen.POTONG_BESAR
    teks = os.pread(fd, st.st_size, 0) if st.st_size <= maks else \
        os.pread(fd, n, 0) + b'\n' + os.pread(fd, n, max(st.st_size - n, n))
    if tersembunyi and b'<?php' not in teks[:256]:
        return None
    return teks


def tulis_temuan(baris):
    try:
        if os.path.getsize(TEMUAN) > MAKS_TEMUAN_BERKAS:
            os.replace(TEMUAN, TEMUAN + '.1')
    except OSError:
        pass
    with open(TEMUAN, 'a') as f:
        f.write(json.dumps(baris, separators=(',', ':')) + '\n')


def agen_sama(path, teks):
    try:
        with open(path, 'rb') as f:
            return f.read() == teks
    except OSError:
        return False


def nama_proses(pid):
    try:
        with open('/proc/%d/comm' % pid) as f:
            return f.read().strip()[:40]
    except OSError:
        return ''


def jalan():
    os.makedirs(DATA, mode=0o700, exist_ok=True)
    fd = pasang_fanotify()
    stat = {'mulai': int(time.time()), 'diperiksa': 0, 'temuan': 0, 'karantina': 0, 'overflow': 0, 'galat': 0,
            'sidik': sidik_agen(), 'pid': os.getpid()}
    setelan = muat_setelan(None)
    terakhir = {}  # path → (ukuran, mtime) supaya tulis berulang yang sama tidak diperiksa dua kali
    detak = 0
    sendiri = os.getpid()
    while True:
        buf = os.read(fd, 65536) if select.select([fd], [], [], 30)[0] else b''
        i = 0
        while i + META.size <= len(buf):
            panjang, _, _, _, mask, efd, pid = META.unpack_from(buf, i)
            i += panjang or META.size
            if mask & FAN_Q_OVERFLOW:
                stat['overflow'] += 1
            if efd < 0:
                continue
            try:
                if pid == sendiri:
                    continue
                path = os.readlink('/proc/self/fd/%d' % efd)
                jenis = perlu_diperiksa(path)
                if not jenis or agen.di_putih(path, setelan[0].get('putih')):
                    continue
                st = os.fstat(efd)
                kunci = (st.st_size, st.st_mtime)
                if terakhir.get(path) == kunci:
                    continue
                terakhir[path] = kunci
                teks = baca(efd, st, *jenis)
                if teks is None:
                    continue
                stat['diperiksa'] += 1
                tanda = agen.periksa(path, 'php' if jenis[1] else jenis[0], teks)
                if tanda:
                    stat['temuan'] += 1
                    baris = {'t': int(time.time()), 'path': path, 'user': path.split('/')[2], 'ukuran': st.st_size,
                             'mtime': int(st.st_mtime), 'ctime': int(st.st_ctime), 'izin': oct(st.st_mode & 0o777)[2:],
                             'sha256': hashlib.sha256(teks).hexdigest() if len(teks) == st.st_size else agen.hash_berkas(path),
                             'pid': pid, 'proses': nama_proses(pid),
                             'tingkat': 'virus' if any(x['tingkat'] == 'virus' for x in tanda) else 'curiga',
                             'tanda': tanda}
                    if setelan[0].get('mode') == 'otomatis' and boleh_otomatis(path, tanda):
                        # Isi di disk harus sama dengan yang diperiksa (berkas bisa sudah ditimpa lagi)
                        r = agen.karantina({'path': path, 'oleh': 'Realtime otomatis',
                                            'alasan': ', '.join(x['id'] for x in tanda)}) if agen_sama(path, teks) else {
                            'ok': False, 'error': 'berkas_berubah'}
                        baris['karantina'] = {'ok': bool(r.get('ok')), 'id': r.get('id'), 'error': r.get('error')}
                        if r.get('ok'):
                            stat['karantina'] += 1
                    tulis_temuan(baris)
            except OSError:
                stat['galat'] += 1
            finally:
                os.close(efd)
        sekarang = time.time()
        if sekarang - detak >= 60:
            detak = sekarang
            setelan = muat_setelan(setelan)
            stat['setelan'] = setelan[1]
            stat['mode'] = setelan[0].get('mode') or 'laporan'
            if len(terakhir) > 50000:
                terakhir.clear()
            with open(DETAK + '.tmp', 'w') as f:
                json.dump(dict(stat, t=int(sekarang)), f)
            os.replace(DETAK + '.tmp', DETAK)


if __name__ == '__main__':
    jalan()
