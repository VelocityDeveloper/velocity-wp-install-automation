# -*- coding: utf-8 -*-
"""Velocity Limit Resource — pengganti LVE CloudLinux untuk server DirectAdmin non-CloudLinux (dijalankan lewat `ssh ... python3 -`).

Limit per user = DA User Cgroups (directadmin.conf cgroup=1): key CPUQuota/MemoryMax/IO*/TasksMax di user.conf,
DA menerapkannya dengan `systemctl set-property user-UID.slice` (drop-in /etc/systemd/system.control). Nilai default
diisi /usr/local/sbin/velocity-cg-default (dipasang build/sanke/cgroup/pasang.sh) dari preset di /etc/velocity-cg/preset;
hook DA user_create/restore/modify_post + timer 15 mnt menjaga user baru & hasil restore. Akun `admin` dikecualikan.

Dipakai halaman Server > Limit Resource (installer_status.py). Pemanggil menambahkan `jalankan(<base64 JSON>)`.
Harus tetap jalan di Python 3.6. Aksi:
- status (baca): preset aktif + nilai tiap preset, limit tiap user (user.conf vs slice sebenarnya).
- terapkan {preset}: cadangan → tulis preset → velocity-cg-default --semua → verifikasi slice; gagal → kembalikan.
"""
import base64
import fcntl
import glob
import json
import os
import pwd
import re
import shutil
import subprocess
import time

DA = '/usr/local/directadmin'
USERS = DA + '/data/users'
CG = '/usr/local/sbin/velocity-cg-default'
PRESET = '/etc/velocity-cg/preset'
KUNCI_F = '/run/velocity-cg.lock'  # sama dengan velocity-cg-default (timer/hook tidak menulis selama terapkan)
KUNCI = ('CPUQuota', 'MemoryMax', 'IOReadBandwidthMax', 'IOWriteBandwidthMax', 'IOReadIOPSMax', 'IOWriteIOPSMax', 'TasksMax')


def sh(cmd, batas=300):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=batas, check=False)
    return r.returncode, r.stdout


def didukung():
    if not os.path.isfile(DA + '/directadmin'):
        return 'bukan_directadmin'
    if os.path.exists('/etc/cloudlinux-release') or os.path.exists('/usr/sbin/lvectl'):
        return 'cloudlinux_pakai_lve'
    return ''


def user_conf(u):
    out = {}
    try:
        for b in open('%s/%s/user.conf' % (USERS, u), errors='replace'):
            k, _, v = b.rstrip('\n').partition('=')
            if k in KUNCI:
                out[k] = v
    except OSError:
        pass
    return out


IO = ('IOReadBandwidthMax', 'IOWriteBandwidthMax', 'IOReadIOPSMax', 'IOWriteIOPSMax')


def slice_nyata(uid):
    cmd = ['systemctl', 'show', 'user-%d.slice' % uid, '-p', 'CPUQuotaPerSecUSec', '-p', 'MemoryMax', '-p', 'TasksMax']
    for k in IO:
        cmd += ['-p', k]
    _, o = sh(cmd, 30)
    out = {}
    for b in o.splitlines():
        k, _, v = b.partition('=')
        if k in IO:  # baris berulang per device: ambil batas /home ("/home 25000000")
            dev, _, n = v.rpartition(' ')
            if dev == '/home':
                out[k] = n
        elif k:
            out[k] = v
    return out


def _cpu(v):  # '1s' / '1.500000s' / '500ms' / 'infinity' → persen
    if not v or v == 'infinity':
        return None
    m = re.match(r'([\d.]+)(ms|s)$', v)
    return round(float(m.group(1)) * (100 if m.group(2) == 's' else 0.1)) if m else v


def _byte(v):
    if not v or v == 'infinity':
        return None
    m = re.match(r'([\d.]+)([KMGT]?)$', v)
    return int(float(m.group(1)) * 1024 ** ' KMGT'.index(m.group(2) or ' ')) if m else v


def _si(v):  # IO systemd: akhiran K/M/G = basis 1000 ('25M' → 25000000)
    m = re.match(r'([\d.]+)([KMGT]?)$', v or '')
    return int(float(m.group(1)) * 1000 ** ' KMGT'.index(m.group(2) or ' ')) if m else None


def _harap(conf):  # nilai user.conf → bentuk systemctl show
    cpu = conf.get('CPUQuota', '').rstrip('%')
    return {'cpu': int(cpu) if cpu.isdigit() else None, 'mem': _byte(conf.get('MemoryMax')),
            'tasks': int(conf['TasksMax']) if conf.get('TasksMax', '').isdigit() else None,
            'io': [_si(conf.get(k)) for k in IO]}


def _nyata(s):
    t = s.get('TasksMax', '')
    return {'cpu': _cpu(s.get('CPUQuotaPerSecUSec')), 'mem': _byte(s.get('MemoryMax')), 'tasks': int(t) if t.isdigit() else None,
            'io': [int(s[k]) if s.get(k, '').isdigit() else None for k in IO]}


def info():
    k, o = sh([CG, '--json'], 30)
    try:
        return json.loads(o.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def daftar_user(inf):
    nilai_preset = {}
    for p in inf['daftar'].values():
        for k, v in p.items():
            nilai_preset.setdefault(k, set()).add(v)
    out = []
    for d in sorted(glob.glob(USERS + '/*/user.conf')):
        u = d.split('/')[-2]
        try:
            uid = pwd.getpwnam(u).pw_uid
        except KeyError:
            continue
        conf = user_conf(u)
        nyata = _nyata(slice_nyata(uid))
        kecuali = u in inf.get('kecuali', [])
        # akun dikecualikan = slice tanpa batas apa pun isi user.conf-nya (velocity-cg-default melepasnya)
        harap = {'cpu': None, 'mem': None, 'tasks': None, 'io': [None] * len(IO)} if kecuali else _harap(conf)
        out.append({'user': u, 'uid': uid, 'kecuali': kecuali, 'nilai': conf,
                    'kustom': [k for k, v in conf.items() if v and v not in nilai_preset.get(k, ())],
                    'nyata': nyata, 'sesuai': nyata == harap})
    return out


def status(p):
    alasan = didukung()
    if alasan:
        return {'ok': True, 'didukung': False, 'alasan': alasan}
    inf = info() if os.access(CG, os.X_OK) else None
    if not inf:
        return {'ok': True, 'didukung': True, 'terpasang': False}
    return {'ok': True, 'didukung': True, 'terpasang': True, **inf, 'users': daftar_user(inf)}


def terapkan(p):
    preset = p.get('preset')
    alasan = didukung()
    if alasan:
        return {'ok': False, 'error': alasan}
    if not os.access(CG, os.X_OK):
        return {'ok': False, 'error': 'velocity_cg_belum_terpasang'}
    # kunci dulu (maks 600 dtk, sama dengan flock -w 600 di skrip) supaya cadangan & preset lama tidak terbaca setengah jalan
    kunci = open(KUNCI_F, 'w')
    for _ in range(600):
        try:
            fcntl.flock(kunci, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError:
            time.sleep(1)
    else:
        return {'ok': False, 'error': 'kunci_sibuk'}
    inf = info()
    if not inf:
        return {'ok': False, 'error': 'velocity_cg_belum_terpasang'}
    if preset not in inf['daftar']:
        return {'ok': False, 'error': 'preset_tidak_dikenal'}
    lama = inf['preset']
    cad = '/root/velocity-cadangan/limit-resource-' + time.strftime('%Y%m%d%H%M%S')
    os.makedirs(cad)
    k, o = sh(['tar', 'czf', cad + '/user-conf.tgz', '-C', '/'] +
              [f[1:] for f in glob.glob(USERS + '/*/user.conf')], 120)
    if k:
        return {'ok': False, 'error': 'cadangan_gagal', 'pesan': o[-300:]}
    if os.path.exists(PRESET):
        shutil.copy2(PRESET, cad + '/preset')

    def tulis_preset(n):
        os.makedirs(os.path.dirname(PRESET), exist_ok=True)
        with open(PRESET + '.tmp', 'w') as f:
            f.write(n + '\n')
        os.replace(PRESET + '.tmp', PRESET)

    env = dict(os.environ, VCG_TERKUNCI='1')
    tulis_preset(preset)
    try:
        r = subprocess.run([CG, '--semua'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                           timeout=300, check=False, env=env)
        k, log = r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        k, log = 124, 'timeout velocity-cg-default --semua (300 dtk)'
    users = daftar_user(info() or inf)
    salah = [u['user'] for u in users if not u['sesuai']]
    hasil = {'preset_lama': lama, 'preset': preset, 'cadangan': cad, 'log': log[-2000:], 'users': users}
    if not k and not salah:
        return {'ok': True, 'hasil': hasil}
    # kembalikan: user.conf + preset lama, lalu terapkan ulang per user (mode satu = tanpa lewati; set-property menulis ulang drop-in)
    sh(['tar', 'xzf', cad + '/user-conf.tgz', '-C', '/'], 120)
    tulis_preset(lama)
    for u in users:
        subprocess.run([CG, u['user']], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=False, env=env)
    return {'ok': False, 'error': 'verifikasi_gagal', 'hasil': {**hasil, 'tidak_sesuai': salah, 'dikembalikan': True,
                                                                  'users': daftar_user(info() or inf)}}


AKSI = {'status': status, 'terapkan': terapkan}


def jalankan(kode):
    p = json.loads(base64.b64decode(kode).decode())
    fungsi = AKSI.get(p.get('aksi'))
    if not fungsi:
        hasil = {'ok': False, 'error': 'aksi_tidak_dikenal'}
    else:
        try:
            hasil = fungsi(p)
        except Exception as e:
            hasil = {'ok': False, 'error': 'galat', 'pesan': str(e)[:300]}
    print(json.dumps(hasil))
