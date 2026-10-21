"""Status PC Backup untuk dashboard: mount SSHFS + ringkasan mesin lewat SSH.

PC Backup = Ubuntu 24.04 + pool ZFS `Backup` (sejak 13 Okt 2026, pengganti TrueNAS). Server DirectAdmin
dibackup lewat rsync (backup-rsync-<server>.timer di PC Backup, status di pc_restore.py); backup FTP
bawaan DA tidak dipakai lagi sejak 20 Okt 2026. Snapshot harian oleh timer backup-snapshot. Dijangkau `ssh pc-backup` (root, Tailscale).
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
# Server DirectAdmin -> alias ~/.ssh/config (dipakai pc_restore.py untuk restore)
SERVER_DA = {'wulan': 'wulan', 'farnaz': 'farnaz', 'kiya': 'kiya', 'cahyadi': 'cahyadi', 'fahmi': 'fahmi'}

# Dijalankan di PC Backup (python3 Ubuntu); keluaran satu objek JSON. Hanya membaca.
SKRIP_PC = r'''
import json, os, re, subprocess, time
def sh(*a):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ''
out = {'waktu': int(time.time())}
m = re.search(r'^PRETTY_NAME="?([^"\n]*)', open('/etc/os-release').read(), re.M)
out['sistem'] = {'host': os.uname().nodename, 'os': m.group(1) if m else '',
                 'uptime': int(float(open('/proc/uptime').read().split()[0]))}
out['layanan'] = {n: sh('systemctl', 'is-active', n).strip() for n in ('tailscaled', 'zfs-zed', 'smartmontools', 'backup-snapshot.timer', 'zfs-scrub-mingguan.timer', 'zfs-pulihkan.timer')}
u = re.search(r'Status: (\w+)', sh('ufw', 'status'))
out['layanan']['ufw'] = u.group(1) if u else 'tidak ada'

out['pool'] = []
for b in sh('zpool', 'list', '-Hp', '-o', 'name,size,alloc,free,health').splitlines():
    n, s, a, f, h = b.split('\t')
    out['pool'].append({'nama': n, 'ukuran': int(s), 'terpakai': int(a), 'sisa': int(f), 'status': h})

# Kesehatan HDD: SMART (smartctl -j) + error ZFS per disk. Pool stripe: SATU disk rusak = seluruh pool hilang.
vdev = {}
# -v: ZFS sendiri memetakan blok rusak (gagal checksum/baca) ke nama berkas; hanya blok yang pernah dibaca (scrub = semua)
out['zfs_rusak'], out['zfs_scan'], daftar_rusak = [], '', False
for b in sh('zpool', 'status', '-v', '-P', '-L').splitlines():
    m = re.match(r'\s+/dev/([a-z]+)\d*\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)', b)
    if m:
        r, w, c = (int(x) for x in m.group(3, 4, 5))
        vdev[m.group(1)] = {'status': m.group(2), 'galat': r + w + c, 'baca': r, 'tulis': w, 'cksum': c}
    elif b.strip().startswith('scan:'):
        out['zfs_scan'] = b.strip()[5:].strip()
    elif b.startswith('errors:'):
        daftar_rusak = 'Permanent errors' in b
    elif daftar_rusak and b.strip() and len(out['zfs_rusak']) < 100:
        out['zfs_rusak'].append(b.strip())
# Satu berkas bisa muncul 2x+ (berkas aktif + tiap snapshot yang berbagi blok rusak) → gabung per path asli
rusak, titik = {}, {}
for e in out['zfs_rusak']:
    m = re.match(r'([^@\s:]+)@([^:]+):(/.*)', e)
    if m:
        ds, snap, rel = m.groups()
        if ds not in titik:
            titik[ds] = sh('zfs', 'get', '-Ho', 'value', 'mountpoint', ds).strip()
        e = titik[ds].rstrip('/') + rel if titik[ds].startswith('/') else e
    x = rusak.setdefault(e, {'berkas': e, 'aktif': False, 'snapshot': []})
    if m:
        x['snapshot'].append(snap)
    else:
        x['aktif'] = True
out['zfs_rusak'] = list(rusak.values())
out['disk'] = []
for n in sh('lsblk', '-dno', 'NAME,TYPE').splitlines():
    n, jenis = (n.split() + [''])[:2]
    if jenis != 'disk':
        continue
    try:
        j = json.loads(sh('smartctl', '-j', '-i', '-H', '-A', '-l', 'selftest', '/dev/' + n) or '{}')
    except ValueError:
        j = {}
    atr = {a['id']: a['raw']['value'] for a in j.get('ata_smart_attributes', {}).get('table', [])}
    uji = (j.get('ata_smart_self_test_log', {}).get('standard', {}).get('table') or [{}])[0]
    out['disk'].append({
        'nama': n, 'model': j.get('model_name', ''), 'serial': j.get('serial_number', ''),
        'ukuran': j.get('user_capacity', {}).get('bytes'), 'rpm': j.get('rotation_rate'),
        'sehat': j.get('smart_status', {}).get('passed'), 'suhu': j.get('temperature', {}).get('current'),
        'jam': j.get('power_on_time', {}).get('hours'),
        'realloc': atr.get(5), 'pending': atr.get(197), 'uncorrect': atr.get(198), 'crc': atr.get(199),
        'uji_terakhir': uji.get('type', {}).get('string'), 'uji_hasil': uji.get('status', {}).get('string'),
        'uji_jam': uji.get('lifetime_hours'), 'pool': vdev.get(n),
    })

# Run rsync terakhir per server (.status.json ditulis /root/backup-rsync.py) + jadwal timer-nya
try:
    timer = {t['unit']: t for t in json.loads(sh('systemctl', 'list-timers', '--all', '-o', 'json', 'backup-rsync-*') or '[]')}
except ValueError:
    timer = {}
out['rsync'] = []
for s in sorted(os.listdir('/srv/backup/rsync')):
    try:
        x = json.load(open(f'/srv/backup/rsync/{s}/.status.json'))
    except (OSError, ValueError):
        continue
    x.pop('terakhir', None)
    t = timer.get(f'backup-rsync-{s}.timer', {})
    x['berikutnya'] = t['next'] // 1000000 if t.get('next') else None
    m = re.search(r'OnCalendar=\S+ (\d\d:\d\d)', sh('systemctl', 'show', '-p', 'TimersCalendar', '--value', f'backup-rsync-{s}.timer'))
    x['jadwal'] = m.group(1) if m else None
    x['berjalan'] = sh('systemctl', 'is-active', f'backup-rsync-{s}.service').strip() in ('active', 'activating')  # oneshot: activating selama jalan
    out['rsync'].append(x)

snap = [b.split('\t') for b in sh('zfs', 'list', '-Hp', '-t', 'snapshot', '-o', 'name,creation', '-s', 'creation', '-d', '1', 'Backup/rsync').splitlines() if '\t' in b]
out['snapshot'] = {'jumlah': len(snap), 'terbaru': int(snap[-1][1]) if snap else None,
                   'terlama': int(snap[0][1]) if snap else None, 'jam': '23:00', 'simpan_hari': 7}
# Riwayat zfs-pulihkan-rusak: berkas rsync rusak yang dihapus agar disalin ulang malam berikutnya
try:
    out['pulih'] = [json.loads(b) for b in open('/var/lib/zfs-pulihkan/riwayat.jsonl').read().splitlines()[-10:]][::-1]
except (OSError, ValueError):
    out['pulih'] = []
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
