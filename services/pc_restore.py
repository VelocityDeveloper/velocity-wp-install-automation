"""Lihat, unduh & restore backup rsync dari PC Backup (menu PC Backup ▸ Restore Backup).

Salinan rsync ada di PC Backup /srv/backup/rsync/<server>/{home/<user>/, db/<db>.sql}, terpasang di PC ini lewat
SSHFS di AKAR (pc_backup.AKAR + /rsync). Versi lama = snapshot ZFS harian (<server>/.zfs/snapshot/<nama>/).
Restore dijalankan dari PC ini (SSHFS → `ssh <server>`), karena PC Backup hanya punya akses BACA ke server DA.
Sebelum menimpa, isi lama selalu dicadangkan di server tujuan: berkas lewat rsync --backup-dir, DB lewat dump.
"""
import json
import os
import re
import subprocess
import threading
import time
import uuid

import pc_backup

AKAR = pc_backup.AKAR + '/rsync'
MY_CNF = '/usr/local/directadmin/conf/my.cnf'
CADANGAN = '/root/velocity-cadangan/restore'  # di server DA, satu filesystem dengan /home
SSH = 'ssh -o BatchMode=yes -o ConnectTimeout=10'
RE_NAMA = re.compile(r'^[A-Za-z0-9_.-]+$')

_tugas = {}
_kunci = threading.Lock()


class Galat(Exception):
    def __init__(self, kode, status=400):
        super().__init__(kode)
        self.kode = kode
        self.status = status


def _server(server):
    if server not in pc_backup.SERVER_DA or not os.path.isdir(os.path.join(AKAR, server)):
        raise Galat('server_tidak_ada', 404)
    return server


def _akar_versi(server, versi):
    dasar = os.path.join(AKAR, server)
    if not versi or versi == 'terbaru':
        return dasar
    snap = os.path.join(dasar, '.zfs', 'snapshot')
    if not RE_NAMA.match(versi) or versi not in os.listdir(snap):
        raise Galat('versi_tidak_ada', 404)
    return os.path.join(snap, versi)


def _waktu_snapshot(nama, p):
    m = re.search(r'(\d{8})-(\d{4})', nama)
    if m:
        return int(time.mktime(time.strptime(m.group(1) + m.group(2), '%Y%m%d%H%M')))
    return int(os.stat(p).st_mtime)


def _durasi_run(p):
    """Lama run rsync yang terekam di <versi>/.status.json (snapshot ikut menyimpan status run saat itu), detik."""
    try:
        with open(os.path.join(p, '.status.json')) as f:
            st = json.load(f)
        return st['selesai'] - st['mulai'] if st.get('selesai') else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def status_rsync(server):
    """Status run rsync terakhir: <server>/.status.json ditulis skrip rsync (tahap, akun ke-, byte, DB, gagal)."""
    try:
        with open(os.path.join(AKAR, server, '.status.json')) as f:
            st = json.load(f)
    except (OSError, ValueError):
        return None
    # Penulis status mati di tengah jalan = tidak diperbarui > 10 menit
    if st.get('tahap') in ('berkas', 'db') and time.time() - st.get('diperbarui', 0) > 600:
        st['tahap'] = 'terhenti'
    return st


def backup_sekarang(b):
    """Jalankan run rsync di luar jadwal: systemctl start backup-rsync-<server> di PC Backup (tak menunggu selesai)."""
    server = _server(b.get('server'))
    st = status_rsync(server)
    if st and st.get('tahap') in ('berkas', 'db'):
        raise Galat('backup_berjalan', 409)
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', pc_backup.HOST,
                        'systemctl', 'start', '--no-block', f'backup-rsync-{server}.service'], capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise Galat('gagal_mulai', 502)
    return {'ok': True}


def daftar(server=None, versi=None):
    servers = sorted(s for s in (os.listdir(AKAR) if os.path.isdir(AKAR) else []) if s in pc_backup.SERVER_DA)
    if not servers:
        return {'akar': AKAR, 'server': [], 'versi': [], 'akun': [], 'tersambung': pc_backup.tersambung()}
    server = _server(server or servers[0])
    akar = _akar_versi(server, versi)
    db = {}
    try:
        for e in os.scandir(os.path.join(akar, 'db')):
            if e.name.endswith('.sql') and e.is_file():
                st = e.stat()
                db.setdefault(e.name.split('_', 1)[0], []).append(
                    {'nama': e.name[:-4], 'ukuran': st.st_size, 'waktu': int(st.st_mtime), 'path': e.path})
    except FileNotFoundError:
        pass
    akun = []
    home = os.path.join(akar, 'home')
    for u in sorted(os.listdir(home)) if os.path.isdir(home) else []:
        p = os.path.join(home, u)
        if os.path.isdir(p):
            d = sorted(db.get(u, []), key=lambda x: x['nama'])
            akun.append({'user': u, 'path': p, 'db': d, 'waktu': max([x['waktu'] for x in d], default=None)})
    snap = os.path.join(AKAR, server, '.zfs', 'snapshot')
    versi_ada = [{'id': 'terbaru', 'waktu': max((a['waktu'] for a in akun if a['waktu']), default=None),
                  'durasi': _durasi_run(os.path.join(AKAR, server))}]
    try:
        for n in sorted(os.listdir(snap), reverse=True):
            versi_ada.append({'id': n, 'waktu': _waktu_snapshot(n, os.path.join(snap, n)), 'durasi': _durasi_run(os.path.join(snap, n))})
    except OSError:
        pass
    return {'akar': AKAR, 'server': servers, 'server_aktif': server, 'versi': versi_ada, 'versi_aktif': versi or 'terbaru',
            'akun': akun, 'tersambung': pc_backup.tersambung(), 'status': status_rsync(server)}


def _jalankan(t, args, **kw):
    t['log'].append('$ ' + ' '.join(args)[:400])
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)
    for baris in p.stdout:
        t['log'].append(baris.rstrip()[:400])
        del t['log'][:-200]
    if p.wait() != 0:
        raise RuntimeError(f'perintah gagal (kode {p.returncode})')


def _restore_berkas(t, b, akar):
    alias, user, rel = pc_backup.SERVER_DA[t['server']], t['user'], t['path']
    src = os.path.join(akar, 'home', user, rel) if rel else os.path.join(akar, 'home', user)
    folder = os.path.isdir(src) and not os.path.islink(src)
    if t['tujuan'] == 'terpisah':
        dest = f"/home/{user}/restore-{t['stempel']}/{rel or user}"
    else:
        dest = f'/home/{user}/{rel}' if rel else f'/home/{user}'
    args = ['rsync', '-aHs', '--numeric-ids', '--mkpath', '--stats', '-e', SSH]
    if t['tujuan'] == 'asli':
        # Berkas yang tertimpa/terhapus di server dipindah ke folder cadangan, bukan hilang
        args += ['--backup', f"--backup-dir={t['cadangan']}"]
        if folder and b.get('hapus'):
            args.append('--delete')
    _jalankan(t, args + [src + ('/' if folder else ''), f'{alias}:{dest}' + ('/' if folder else '')])
    t['hasil'] = dest


def _restore_db(t, akar):
    alias, db = pc_backup.SERVER_DA[t['server']], t['db']
    sql = os.path.join(akar, 'db', db + '.sql')
    with open(sql, 'rb') as f:
        f.seek(max(0, os.path.getsize(sql) - 200))
        if b'Dump completed' not in f.read():
            raise RuntimeError('dump di backup tidak utuh (tanpa "Dump completed"), restore dibatalkan')
    cad = t['cadangan'] + '.sql.gz'
    # Isi DB sekarang didump dulu; kalau dump gagal, impor tidak dijalankan
    _jalankan(t, ['ssh', '-o', 'BatchMode=yes', alias,
                  f'set -o pipefail; test -d /var/lib/mysql/{db} || {{ echo "DB {db} tidak ada di server"; exit 3; }}; '
                  f'mkdir -p {CADANGAN} && mariadb-dump --defaults-extra-file={MY_CNF} --single-transaction --quick '
                  f'--routines --triggers --events --hex-blob {db} | gzip > {cad} && ls -la {cad}'])
    with open(sql, 'rb') as f:
        _jalankan(t, ['ssh', '-o', 'BatchMode=yes', alias, f'mariadb --defaults-extra-file={MY_CNF} {db} && echo "impor {db} selesai"'], stdin=f)
    t['hasil'] = db


def _kerja(t, b, akar):
    try:
        if t['jenis'] == 'db':
            _restore_db(t, akar)
        else:
            _restore_berkas(t, b, akar)
        t['status'] = 'selesai'
    except Exception as e:
        t['status'] = 'gagal'
        t['log'].append(f'GAGAL: {e}')
    t['selesai'] = int(time.time())
    print(f"restore {t['id']} {t['status']} {t['server']}/{t['user']} {t['jenis']} {t.get('db') or t['path'] or '/'}", flush=True)


def mulai(b):
    server = _server(b.get('server'))
    akar = _akar_versi(server, b.get('versi'))
    user = b.get('user')
    if not isinstance(user, str) or not RE_NAMA.match(user) or not os.path.isdir(os.path.join(akar, 'home', user)):
        raise Galat('akun_tidak_ada', 404)
    jenis = b.get('jenis')
    stempel = time.strftime('%Y%m%d-%H%M%S')
    t = {'id': uuid.uuid4().hex[:12], 'server': server, 'user': user, 'versi': b.get('versi') or 'terbaru', 'jenis': jenis,
         'path': '', 'db': None, 'tujuan': 'asli', 'stempel': stempel, 'status': 'berjalan', 'log': [],
         'mulai': int(time.time()), 'selesai': None, 'hasil': None}
    if jenis == 'db':
        db = b.get('db')
        if not isinstance(db, str) or not RE_NAMA.match(db) or not db.startswith(user + '_') \
                or not os.path.isfile(os.path.join(akar, 'db', db + '.sql')):
            raise Galat('db_tidak_ada', 404)
        t['db'] = db
        t['cadangan'] = f'{CADANGAN}/{db}-{stempel}'
    elif jenis == 'berkas':
        rel = os.path.normpath(str(b.get('path') or '').strip('/')) if b.get('path') else ''
        if rel in ('.', '..') or rel.startswith('../') or '\0' in rel:
            raise Galat('path_tidak_valid')
        rel = '' if rel == '.' else rel
        if not os.path.lexists(os.path.join(akar, 'home', user, rel)):
            raise Galat('tidak_ditemukan', 404)
        t['path'] = rel
        t['tujuan'] = 'terpisah' if b.get('tujuan') == 'terpisah' else 'asli'
        t['cadangan'] = f'{CADANGAN}/{user}-{stempel}'
    else:
        raise Galat('jenis_tidak_valid')
    with _kunci:
        if any(x['status'] == 'berjalan' and x['server'] == server and x['user'] == user for x in _tugas.values()):
            raise Galat('restore_akun_ini_masih_berjalan', 409)
        _tugas[t['id']] = t
    threading.Thread(target=_kerja, args=(t, b, akar), daemon=True).start()
    return {'id': t['id']}


def tugas(id_=None):
    if id_:
        t = _tugas.get(id_)
        if not t:
            raise Galat('tidak_ditemukan', 404)
        return t
    return {'tugas': sorted(({k: v for k, v in t.items() if k != 'log'} for t in _tugas.values()),
                            key=lambda x: -x['mulai'])[:20]}
