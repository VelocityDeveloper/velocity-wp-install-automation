"""Status PC Backup untuk dashboard: mount SSHFS + ringkasan mesin lewat SSH.

PC Backup = Ubuntu 24.04 + pool ZFS `Backup` (sejak 13 Okt 2026, pengganti TrueNAS). Server DirectAdmin
MENGIRIM backup lewat FTPS (vsftpd, user da-<server>, home /srv/backup/directadmin/<server>) melalui
Tailscale; snapshot harian oleh timer backup-snapshot. Dijangkau `ssh pc-backup` (root, Tailscale).
Isi mesin dipasang di AKAR oleh unit systemd mnt-pc\\x2dbackup.mount (+ .../directadmin baca-saja).
Data di-cache CACHE_DETIK supaya halaman yang dibuka banyak orang tidak membanjiri SSH.
"""
import json
import os
import subprocess
import threading
import time

AKAR = '/mnt/pc-backup'
MOUNT = [AKAR, AKAR + '/directadmin']
HOST = 'pc-backup'
CACHE_DETIK = 60

# Dijalankan di PC Backup (python3 Ubuntu); keluaran satu objek JSON. Hanya membaca.
SKRIP_PC = r'''
import json, os, re, subprocess, time
DA = '/srv/backup/directadmin'
def sh(*a):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ''
out = {'waktu': int(time.time())}
m = re.search(r'^PRETTY_NAME="?([^"\n]*)', open('/etc/os-release').read(), re.M)
out['sistem'] = {'host': os.uname().nodename, 'os': m.group(1) if m else '',
                 'uptime': int(float(open('/proc/uptime').read().split()[0]))}
out['layanan'] = {n: sh('systemctl', 'is-active', n).strip() for n in ('vsftpd', 'tailscaled', 'zfs-zed', 'backup-snapshot.timer')}
u = re.search(r'Status: (\w+)', sh('ufw', 'status'))
out['layanan']['ufw'] = u.group(1) if u else 'tidak ada'

out['pool'] = []
for b in sh('zpool', 'list', '-Hp', '-o', 'name,size,alloc,free,health').splitlines():
    n, s, a, f, h = b.split('\t')
    out['pool'].append({'nama': n, 'ukuran': int(s), 'terpakai': int(a), 'sisa': int(f), 'status': h})
dataset = {}
for b in sh('zfs', 'list', '-Hp', '-o', 'name,used,usedbysnapshots', '-d', '1', 'Backup/directadmin').splitlines()[1:]:
    n, us, sn = b.split('\t')
    dataset[n.rsplit('/', 1)[1]] = {'terpakai': int(us), 'snapshot': int(sn)}

# User FTP (vsftpd.userlist) → server = folder home di /srv/backup/directadmin/<server>
pengguna = {}
try:
    daftar = open('/etc/vsftpd.userlist').read().split()
except OSError:
    daftar = []
for b in open('/etc/passwd'):
    p = b.strip().split(':')
    if len(p) > 5 and p[0] in daftar and p[5].startswith(DA + '/'):
        pengguna[p[0]] = p[5][len(DA) + 1:].split('/')[0]

# Log vsftpd (+ rotasi .1): unggahan per user, 8 hari terakhir
batas = time.time() - 8 * 86400
unggah = {}
RE = re.compile(r'^(\w{3} \w{3} +\d+ [\d:]+ \d{4}) \[pid \d+\] \[([^\]]+)\] (OK|FAIL) UPLOAD: Client "[^"]*", "([^"]*)", (\d+) bytes')
for f in ('/var/log/vsftpd.log.1', '/var/log/vsftpd.log'):
    try:
        isi = open(f, errors='replace').read().splitlines()
    except OSError:
        continue
    for b in isi:
        m = RE.match(b)
        if not m:
            continue
        try:
            t = int(time.mktime(time.strptime(re.sub(r' +', ' ', m.group(1)), '%a %b %d %H:%M:%S %Y')))
        except ValueError:
            continue
        if t >= batas:
            unggah.setdefault(m.group(2), []).append({'t': t, 'ok': m.group(3) == 'OK', 'berkas': m.group(4), 'bytes': int(m.group(5))})

server = []
for nama in sorted(set(pengguna.values()) | set(dataset)):
    user = next((k for k, v in pengguna.items() if v == nama), None)
    akar = os.path.join(DA, nama)
    sets = []
    try:
        isi = sorted(os.listdir(akar))
    except OSError:
        isi = []
    for s in isi:
        p = os.path.join(akar, s)
        if not os.path.isdir(p):
            continue
        n = ukuran = 0
        baru = None
        for e in os.scandir(p):
            if e.is_file(follow_symlinks=False):
                st = e.stat(follow_symlinks=False)
                n += 1
                ukuran += st.st_size
                baru = max(baru or 0, int(st.st_mtime))
        sets.append({'nama': s, 'berkas': n, 'ukuran': ukuran, 'terbaru': baru})
    # Sesi = unggahan beruntun berjeda < 2 jam; sesi terakhir = backup terakhir server itu
    sesi = []
    for x in sorted(unggah.get(user, []), key=lambda x: x['t']):
        if not sesi or x['t'] - sesi[-1]['selesai'] >= 7200:
            sesi.append({'mulai': x['t'], 'selesai': x['t'], 'ok': 0, 'gagal': 0, 'bytes': 0, 'folder': {}})
        s = sesi[-1]
        s['selesai'] = x['t']
        s['ok' if x['ok'] else 'gagal'] += 1
        s['bytes'] += x['bytes'] if x['ok'] else 0
        bagian = x['berkas'].strip('/').split('/')
        d = bagian[0] if len(bagian) > 1 else '/'
        s['folder'][d] = s['folder'].get(d, 0) + 1
    gagal = [x for x in unggah.get(user, []) if not x['ok']][-5:]
    server.append({'server': nama, 'user': user, 'dataset': dataset.get(nama), 'set': sets,
                   'sesi_terakhir': sesi[-1] if sesi else None, 'gagal_terbaru': gagal})
out['server'] = server

snap = [b.split('\t') for b in sh('zfs', 'list', '-Hp', '-t', 'snapshot', '-o', 'name,creation', '-s', 'creation', '-d', '1', 'Backup/directadmin').splitlines() if '\t' in b]
out['snapshot'] = {'jumlah': len(snap), 'terbaru': int(snap[-1][1]) if snap else None,
                   'terlama': int(snap[0][1]) if snap else None, 'jam': '23:00', 'simpan_hari': 7}
print(json.dumps(out))
'''

_kunci = threading.Lock()
_cache = {'waktu': 0, 'data': None, 'galat': None}


def tersambung():
    return all(os.path.ismount(m) for m in MOUNT)


def _ambil_pc():
    r = subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', HOST, 'python3', '-'],
        input=SKRIP_PC, capture_output=True, text=True, timeout=45,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr.strip().splitlines() or ['ssh gagal'])[-1])
    return json.loads(r.stdout)


def status(segar=False):
    with _kunci:
        if segar or time.time() - _cache['waktu'] > CACHE_DETIK:
            try:
                _cache.update(data=_ambil_pc(), galat=None)
            except Exception as e:  # PC Backup mati/Tailscale putus: data lama tetap dikirim bersama galat
                _cache['galat'] = str(e)[:300]
            _cache['waktu'] = time.time()
        return {'akar': AKAR, 'tersambung': tersambung(), 'mount': {m: os.path.ismount(m) for m in MOUNT},
                'pc': _cache['data'], 'galat': _cache['galat'], 'diperbarui': int(_cache['waktu'])}
