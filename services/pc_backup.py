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
# IP Tailscale PC Backup: jadwal DA yang ftp_ip-nya lain = masih mengirim ke tempat lain (mis. FTPS lama)
IP_PC = '100.86.231.119'
# Server DirectAdmin -> alias ~/.ssh/config untuk membaca jadwal & log backup DA (baca-saja)
SERVER_DA = {'wulan': 'wulan'}
CACHE_DA_DETIK = 300

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
        # Hanya arsip backup DA (user.*.tar.zst dst.); berkas uji koneksi (mis. /uji-wulan.bin) tidak dilaporkan
        if not m or '.tar' not in os.path.basename(m.group(4)):
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
    # Berkas yang sedang diterima = berkas terbaru yang masih berubah < 3 menit lalu
    masuk = None
    for akar_, _, fs in os.walk(akar):
        for f in fs:
            st = os.stat(os.path.join(akar_, f))
            if time.time() - st.st_mtime < 180 and (not masuk or st.st_mtime > masuk['mtime']):
                masuk = {'berkas': os.path.relpath(os.path.join(akar_, f), akar), 'ukuran': st.st_size, 'mtime': int(st.st_mtime)}
    server.append({'server': nama, 'user': user, 'dataset': dataset.get(nama), 'set': sets,
                   'sesi_terakhir': sesi[-1] if sesi else None, 'gagal_terbaru': gagal,
                   'sedang_masuk': masuk})
out['server'] = server

snap = [b.split('\t') for b in sh('zfs', 'list', '-Hp', '-t', 'snapshot', '-o', 'name,creation', '-s', 'creation', '-d', '1', 'Backup/directadmin').splitlines() if '\t' in b]
out['snapshot'] = {'jumlah': len(snap), 'terbaru': int(snap[-1][1]) if snap else None,
                   'terlama': int(snap[0][1]) if snap else None, 'jam': '23:00', 'simpan_hari': 7}
print(json.dumps(out))
'''

# Dijalankan di server DA: jadwal backup (TANPA sandi FTP), backup terakhir & unggahan gagal sejak itu
SKRIP_DA = r'''
import glob, json, os, re, time
from urllib.parse import parse_qs
HARI = {'1': 'Sen', '2': 'Sel', '3': 'Rab', '4': 'Kam', '5': 'Jum', '6': 'Sab', '7': 'Min', '0': 'Min', '*': 'Tiap hari'}
def baca(f):
    try:
        return open(f, errors='replace').read().splitlines()
    except OSError:
        return []
def waktu(t):
    return int(time.mktime(time.strptime(t, '%Y:%m:%d-%H:%M:%S')))
jadwal = []
for b in baca('/usr/local/directadmin/data/admin/backup_crons.list'):
    i, _, q = b.partition('=')
    v = {k: x[0] for k, x in parse_qs(q).items()}
    jadwal.append({'id': i, 'hari': [HARI.get(h, h) for h in v.get('dayofweek', '*').split(',')],
                   'jam': '%02d:%02d' % (int(v.get('hour', 0)), int(v.get('minute', 0))),
                   'tujuan': v.get('where'), 'ftp_ip': v.get('ftp_ip'), 'ftp_user': v.get('ftp_username'),
                   'ftp_path': v.get('ftp_path') or v.get('local_path'), 'append': v.get('append_to_path')})
jalan = [waktu(m.group(1)) for m in (re.match(r'^(\d{4}:\d\d:\d\d-[\d:]+): Running Backup: type=admin', b) for b in baca('/var/log/directadmin/system.log')) if m]
batas = jalan[-1] if jalan else time.time() - 86400
gagal = []
for b in baca('/var/log/directadmin/errortaskq.log'):
    m = re.match(r"^(\d{4}:\d\d:\d\d-[\d:]+): uploadFtpFiles\('([^']*)'.*failed", b)
    if m and waktu(m.group(1)) >= batas:
        gagal.append({'t': waktu(m.group(1)), 'berkas': m.group(2)})
# Backup berjalan = /home/tmp/admin.<pid>.* dengan pid dataskq masih hidup; DA mengemas & mengunggah per user urut abjad
unggah = {}
for c in glob.glob('/proc/[0-9]*/cmdline'):
    try:
        a = open(c, 'rb').read().split(b'\0')
    except OSError:
        continue
    if a and a[0].endswith(b'curl') and b'--upload-file' in a:
        f = a[a.index(b'--upload-file') + 1].decode(errors='replace')
        url = next((x.decode(errors='replace') for x in a if x.startswith(b'ftp://')), '')
        unggah[f] = re.sub(r'^ftp://([^/:]+).*$', r'\1', url)
berjalan = None
for d in glob.glob('/home/tmp/admin.*'):
    pid = d.split('.')[1]
    if not os.path.isdir('/proc/' + pid):
        continue
    berkas = sorted(glob.glob(d + '/*/*.tar*[!g]'), key=os.path.getmtime)
    f = berkas[-1] if berkas else None
    pengguna = sorted(os.listdir('/usr/local/directadmin/data/users'))
    m = re.match(r'^user\.[^.]+\.([^.]+)\.', os.path.basename(f)) if f else None
    u = m.group(1) if m else None
    berjalan = {'mulai': jalan[-1] if jalan else None, 'berkas': os.path.basename(f) if f else None,
                'ukuran': os.path.getsize(f) if f else 0, 'tahap': 'mengunggah' if f in unggah else 'mengemas',
                'tujuan': unggah.get(f), 'user': u, 'user_ke': pengguna.index(u) + 1 if u in pengguna else None,
                'user_total': len(pengguna), 'kuota': []}
    # Pemakaian disk tiap user (urut abjad, byte) untuk memperkirakan sisa backup
    for x in pengguna:
        q = 0
        for b in baca('/usr/local/directadmin/data/users/%s/user.usage' % x):
            if b.startswith('quota='):
                q = int(float(b[6:] or 0) * 1048576)
        berjalan['kuota'].append(q)
print(json.dumps({'jadwal': jadwal, 'backup_terakhir': jalan[-1] if jalan else None, 'gagal_unggah': gagal,
                  'berjalan': berjalan}))
'''

_kunci = threading.Lock()
_cache = {'waktu': 0, 'data': None, 'galat': None}
_cache_da = {}
_sampel = {}  # server -> [(waktu, byte terkirim berkas berjalan, nama berkas)] untuk laju terkini


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


def _ambil_da(alias):
    r = subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', alias, 'python3', '-'],
        input=SKRIP_DA, capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError((r.stderr.strip().splitlines() or ['ssh gagal'])[-1])
    return json.loads(r.stdout)


def _perkiraan(nama, b, s):
    """Perkiraan selesai berkas & seluruh backup dari laju terkini dan laju efektif sejak mulai."""
    kini = time.time()
    masuk = (s or {}).get('sedang_masuk') or {}
    terkirim = masuk['ukuran'] if masuk.get('berkas', '').endswith(b.get('berkas') or '\0') else None
    sp = _sampel.setdefault(nama, [])
    if terkirim is not None:
        if sp and sp[-1][2] != b['berkas']:
            sp.clear()
        if not sp or kini - sp[-1][0] >= 20:
            sp.append((kini, terkirim, b['berkas']))
        sp[:] = [x for x in sp if kini - x[0] <= 600]
    laju = (sp[-1][1] - sp[0][1]) / (sp[-1][0] - sp[0][0]) if len(sp) >= 2 and sp[-1][0] > sp[0][0] else None
    sisa_berkas = max(0, b['ukuran'] - terkirim) if terkirim is not None and b['tahap'] == 'mengunggah' else None
    sesi = (s or {}).get('sesi_terakhir') or {}
    selesai = (sesi.get('bytes') or 0) if sesi.get('mulai', 0) >= (b.get('mulai') or 0) - 120 else 0
    efektif = (selesai + (terkirim or 0)) / (kini - b['mulai']) if b.get('mulai') and kini > b['mulai'] + 60 else None
    k, i = b.get('kuota') or [], (b.get('user_ke') or 0) - 1
    eta_total = None
    if i >= 0 and k and efektif and sisa_berkas is not None:
        # rasio terkompresi/pemakaian disk dari user yang sudah dikemas (termasuk berkas berjalan)
        dasar = sum(k[:i + 1])
        rasio = (selesai + b['ukuran']) / dasar if dasar else 0.8
        sisa = sisa_berkas + rasio * sum(k[i + 1:])
        eta_total = int(kini + sisa / efektif)
    b.pop('kuota', None)
    b.update(terkirim=terkirim, laju=int(laju) if laju else None, laju_efektif=int(efektif) if efektif else None,
             eta_berkas=int(kini + sisa_berkas / laju) if sisa_berkas is not None and laju else None,
             eta_total=eta_total)


def status_da(segar=False, pc=None):
    hasil = {}
    for nama, alias in SERVER_DA.items():
        c = _cache_da.setdefault(nama, {'waktu': 0, 'data': None, 'galat': None})
        umur = CACHE_DETIK if (c['data'] or {}).get('berjalan') else CACHE_DA_DETIK
        if segar or time.time() - c['waktu'] > umur:
            try:
                c.update(data=_ambil_da(alias), galat=None)
            except Exception as e:
                c['galat'] = str(e)[:300]
            c['waktu'] = time.time()
        d = c['data'] or {}
        for j in d.get('jadwal', []):
            j['ke_pc'] = j.get('tujuan') == 'ftp' and j.get('ftp_ip') == IP_PC
        hasil[nama] = {**d, 'galat': c['galat'], 'diperbarui': int(c['waktu'])}
        if d.get('berjalan'):
            b = hasil[nama]['berjalan'] = dict(d['berjalan'])
            _perkiraan(nama, b, next((x for x in (pc or {}).get('server', []) if x['server'] == nama), None))
    return hasil


def status(segar=False):
    with _kunci:
        if segar or time.time() - _cache['waktu'] > CACHE_DETIK:
            try:
                _cache.update(data=_ambil_pc(), galat=None)
            except Exception as e:  # PC Backup mati/Tailscale putus: data lama tetap dikirim bersama galat
                _cache['galat'] = str(e)[:300]
            _cache['waktu'] = time.time()
        return {'akar': AKAR, 'tersambung': tersambung(), 'mount': {m: os.path.ismount(m) for m in MOUNT},
                'pc': _cache['data'], 'galat': _cache['galat'], 'diperbarui': int(_cache['waktu']),
                'da': status_da(segar, _cache['data']), 'ip_pc': IP_PC}
