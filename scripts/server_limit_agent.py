# -*- coding: utf-8 -*-
"""Velocity Limit Resource — pengganti LVE CloudLinux untuk server DirectAdmin non-CloudLinux (dijalankan lewat `ssh ... python3 -`).

Limit per user = DA User Cgroups (directadmin.conf cgroup=1): key CPUQuota/MemoryMax/IO*/TasksMax di user.conf,
DA menerapkannya dengan `systemctl set-property user-UID.slice` (drop-in /etc/systemd/system.control). Nilai default
diisi /usr/local/sbin/velocity-cg-default (dipasang build/sanke/cgroup/pasang.sh) dari preset di /etc/velocity-cg/preset;
hook DA user_create/restore/modify_post + timer 15 mnt menjaga user baru & hasil restore. Akun `admin` dikecualikan.
Pengganti EP = pm.max_children FPM (directadmin.conf php_fpm_max_children_default, global); pengganti MySQL Governor =
MAX_USER_CONNECTIONS + MAX_STATEMENT_TIME per akun MariaDB milik user DA (USER, USER_*) — keduanya dari preset yang sama.

Dipakai halaman Server > Limit Resource (installer_status.py). Pemanggil menambahkan `jalankan(<base64 JSON>)`.
Harus tetap jalan di Python 3.6. Aksi:
- status (baca): preset aktif + nilai tiap preset, limit tiap user (user.conf vs slice sebenarnya).
- terapkan {preset}: cadangan → tulis preset → velocity-cg-default --semua → verifikasi slice; gagal → kembalikan.
- atur_user {user, nilai}: override per akun /etc/velocity-cg/user/USER (menang atas preset; nilai None = kembali ke preset):
  cadangan → tulis override → velocity-cg-default USER → verifikasi; gagal → kembalikan.
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
SISTEM_SQL = re.compile(r'^(root|mysql|mariadb\.sys|PUBLIC|da_.*)$')  # sama dengan velocity-cg-default
OV = '/etc/velocity-cg/user'
# nilai override yang diterima form per akun (MySQL 0 = tanpa batas, sama seperti tanpa MySQL Governor)
NILAI_SAH = {'CPUQuota': r'[1-9]\d{0,3}%', 'MemoryMax': r'[1-9]\d{0,5}[MG]', 'IOReadBandwidthMax': r'[1-9]\d{0,6}[KMG]?',
             'IOWriteBandwidthMax': r'[1-9]\d{0,6}[KMG]?', 'IOReadIOPSMax': r'[1-9]\d{0,6}', 'IOWriteIOPSMax': r'[1-9]\d{0,6}',
             'TasksMax': r'[1-9]\d{0,5}', 'EP': r'[1-9]\d{0,3}', 'MySQLConn': r'\d{1,5}', 'MySQLTime': r'\d{1,5}'}


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


def override(u):
    out = {}
    try:
        for b in open('%s/%s' % (OV, u), errors='replace'):
            k, _, v = b.strip().partition('=')
            if k in NILAI_SAH and v:
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


def ep_user(u):  # pm.max_children efektif di konfigurasi FPM user (semua versi PHP, pool bersama & jail)
    out = set()
    for f in glob.glob('%s/%s/php/php-*fpm*.conf' % (USERS, u)):
        for b in open(f, errors='replace'):
            m = re.match(r'pm\.max_children\s*=\s*(\d+)', b)
            if m:
                out.add(int(m.group(1)))
    return sorted(out)


def mysql_akun():  # {User: [{akun, host, koneksi, query}]} semua akun MariaDB; None bila gagal dibaca
    k, o = sh(['/usr/local/bin/mariadb', '-N', '-B', '-e', "SELECT User,Host,IFNULL(JSON_VALUE(Priv,'$.max_user_connections'),0),"
               "IFNULL(JSON_VALUE(Priv,'$.max_statement_time'),0) FROM mysql.global_priv"], 30)
    if k:
        return None
    out = {}
    for b in o.splitlines():
        a, h, c, t = b.split('\t')
        out.setdefault(a, []).append({'akun': a, 'host': h, 'koneksi': c, 'query': re.sub(r'\.0+$', '', t)})
    return out


def ep_global():
    _, o = sh([DA + '/directadmin', 'config'], 30)
    m = re.search(r'^php_fpm_max_children_default=(\d+)', o, re.M)
    return m.group(1) if m else ''


def info():
    k, o = sh([CG, '--json'], 30)
    try:
        return json.loads(o.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def akun_user(sql, u):  # akun MariaDB milik user: USER dan USER_* (nama user DA tanpa '_')
    return [] if sql is None else [x for a, v in sql.items() if (a == u or a.startswith(u + '_')) and not SISTEM_SQL.match(a)
                                   for x in v]


def daftar_user(inf):
    nilai_preset = {}
    for p in inf['daftar'].values():
        for k, v in p.items():
            nilai_preset.setdefault(k, set()).add(v)
    aktif = inf['daftar'][inf['preset']]
    sql = mysql_akun()

    def cocok(k, v, kecuali):  # nilai preset aktif (atau tanpa batas bila dikecualikan); nilai di luar preset = kustom, selalu sah
        if v not in nilai_preset.get(k, ()) and not (v == '0' and not kecuali):
            return True
        return v == ('0' if kecuali else aktif.get(k))
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
        # akun MariaDB milik user: USER dan USER_* (nama user DA tanpa '_')
        akun = akun_user(sql, u)
        ep = ep_user(u)
        ov = {} if kecuali else override(u)
        # ep kosong = konfigurasi FPM tak terbaca → tidak sesuai. admin: EP tetap ikut default global (php_fpm_max_children_default berlaku untuk semua pool), tidak dinilai
        if 'EP' in ov:
            ep_ok = ep == [int(ov['EP'])]
        else:
            ep_ok = kecuali or bool(ep) and all(str(n) == aktif.get('EP') or str(n) not in nilai_preset.get('EP', ()) for n in ep)

        def cocok_u(k, v):  # override menang atas aturan preset
            return v == ov[k] if k in ov else cocok(k, v, kecuali)
        sql_ok = sql is not None and all(cocok_u('MySQLConn', x['koneksi']) and cocok_u('MySQLTime', x['query']) for x in akun)
        ov_ok = all(conf.get(k) == v for k, v in ov.items() if k in KUNCI)  # user.conf sudah memuat override
        # akun dikecualikan = slice tanpa batas apa pun isi user.conf-nya (velocity-cg-default melepasnya)
        harap = {'cpu': None, 'mem': None, 'tasks': None, 'io': [None] * len(IO)} if kecuali else _harap(conf)
        out.append({'user': u, 'uid': uid, 'kecuali': kecuali, 'nilai': conf,
                    'kustom': [k for k, v in conf.items() if v and v not in nilai_preset.get(k, ())], 'override': ov,
                    'nyata': nyata, 'ep': ep, 'mysql': akun, 'sesuai': nyata == harap and ep_ok and sql_ok and ov_ok})
    return out


def status(p):
    alasan = didukung()
    if alasan:
        return {'ok': True, 'didukung': False, 'alasan': alasan}
    inf = info() if os.access(CG, os.X_OK) else None
    if not inf:
        return {'ok': True, 'didukung': True, 'terpasang': False}
    return {'ok': True, 'didukung': True, 'terpasang': True, **inf, 'ep_global': ep_global(), 'users': daftar_user(inf)}


_kunci = []


def kunci():  # pegang /run/velocity-cg.lock sampai proses agen selesai
    f = open(KUNCI_F, 'w')
    for _ in range(600):
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _kunci.append(f)
            return True
        except OSError:
            time.sleep(1)
    return False


def terapkan(p):
    preset = p.get('preset')
    alasan = didukung()
    if alasan:
        return {'ok': False, 'error': alasan}
    if not os.access(CG, os.X_OK):
        return {'ok': False, 'error': 'velocity_cg_belum_terpasang'}
    # kunci dulu (maks 600 dtk, sama dengan flock -w 600 di skrip) supaya cadangan & preset lama tidak terbaca setengah jalan
    if not kunci():
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
    # nilai lama EP & batas MySQL (rollback otomatis = jalankan ulang preset lama; berkas ini untuk pemeriksaan manual)
    with open(cad + '/ep-mysql.json', 'w') as f:
        json.dump({'php_fpm_max_children_default': ep_global(), 'mysql': mysql_akun()}, f)

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
    inf2 = info() or inf
    users = daftar_user(inf2)
    salah = [u['user'] for u in users if not u['sesuai']]
    if ep_global() != inf2['daftar'][preset].get('EP', ep_global()):
        salah.append('php_fpm_max_children_default')
    hasil = {'preset_lama': lama, 'preset': preset, 'cadangan': cad, 'log': log[-2000:], 'users': users}
    if not k and not salah:
        return {'ok': True, 'hasil': hasil}
    # kembalikan: user.conf + preset lama, lalu terapkan ulang per user (mode satu = tanpa lewati; set-property menulis ulang drop-in)
    sh(['tar', 'xzf', cad + '/user-conf.tgz', '-C', '/'], 120)
    tulis_preset(lama)
    for u in users:  # panggilan pertama ikut mengembalikan EP global (rewrite httpd + reload FPM) → batas longgar
        try:
            subprocess.run([CG, u['user']], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300, check=False, env=env)
        except subprocess.TimeoutExpired:
            pass  # lanjut user berikutnya; sisa beda terlihat di daftar_user di bawah
    return {'ok': False, 'error': 'verifikasi_gagal', 'hasil': {**hasil, 'tidak_sesuai': salah, 'dikembalikan': True,
                                                                  'users': daftar_user(info() or inf)}}


def _sql_batas(akun, nilai):  # nilai: {(akun, host): (koneksi, query)}
    gagal = []
    for x in akun:
        a, h = x['akun'], x['host']
        if (a, h) not in nilai or not re.match(r'^[A-Za-z0-9_]+$', a) or not re.match(r'^[A-Za-z0-9_.%:-]+$', h):
            continue
        c, t = nilai[(a, h)]
        k, o = sh(['/usr/local/bin/mariadb', '-e', "ALTER USER '%s'@'%s' WITH MAX_USER_CONNECTIONS %d MAX_STATEMENT_TIME %s"
                   % (a, h, int(c), float(t))], 30)
        if k:
            gagal.append(a)
    return gagal


def _fpm_ulang(uid):  # tulis ulang konfigurasi FPM (custom1) + reload pool user
    sh(['bash', '-c', "echo 'action=rewrite&value=httpd' >> %s/data/task.queue && %s/directadmin taskq >/dev/null 2>&1; "
        "systemctl list-units --no-legend --plain --state=active 'php-isolated-fpm*@%d.service' 'php-fpm*.service' "
        "| awk '{print $1}' | xargs -r systemctl reload" % (DA, DA, uid)], 300)


def _custom1_tanpa_ep(f):
    try:
        isi = [b for b in open(f) if not b.startswith('|?MAX_CHILDREN=')]
    except OSError:
        return
    if any(b.strip() for b in isi):
        with open(f, 'w') as g:
            g.writelines(isi)
    else:
        os.remove(f)


def atur_user(p):
    u, nilai = p.get('user') or '', p.get('nilai')
    alasan = didukung()
    if alasan:
        return {'ok': False, 'error': alasan}
    if not os.access(CG, os.X_OK):
        return {'ok': False, 'error': 'velocity_cg_belum_terpasang'}
    if not re.match(r'^[a-z0-9]+$', u) or not os.path.isfile('%s/%s/user.conf' % (USERS, u)):
        return {'ok': False, 'error': 'user_tidak_ada'}
    if nilai is not None:
        if not isinstance(nilai, dict) or not nilai or any(k not in NILAI_SAH or not re.match('^%s$' % NILAI_SAH[k], str(v))
                                                           for k, v in nilai.items()):
            return {'ok': False, 'error': 'nilai_tidak_sah'}
        nilai = {k: str(v) for k, v in nilai.items()}
    if not kunci():
        return {'ok': False, 'error': 'kunci_sibuk'}
    inf = info()
    if not inf:
        return {'ok': False, 'error': 'velocity_cg_belum_terpasang'}
    if u in inf.get('kecuali', []):
        return {'ok': False, 'error': 'user_dikecualikan'}
    uid = pwd.getpwnam(u).pw_uid
    conf_f, ov_f = '%s/%s/user.conf' % (USERS, u), '%s/%s' % (OV, u)
    c1_f = '%s/%s/php/php-fpm.conf.custom1' % (USERS, u)
    lama = override(u)
    akun = akun_user(mysql_akun(), u)
    cad = '/root/velocity-cadangan/limit-resource-user-%s-%s' % (u, time.strftime('%Y%m%d%H%M%S'))
    os.makedirs(cad)
    for f in (conf_f, ov_f, c1_f):
        if os.path.exists(f):
            shutil.copy2(f, cad + '/' + os.path.basename(f))
    with open(cad + '/mysql.json', 'w') as f:
        json.dump(akun, f)

    # kunci yang dilepas (kembali ke preset): cgroup dihapus dari user.conf & MySQL dinolkan → velocity-cg-default isi preset
    hapus = set(NILAI_SAH) if nilai is None else set(lama) - set(nilai)
    isi = [b for b in open(conf_f) if b.partition('=')[0] not in hapus or b.partition('=')[0] not in KUNCI]
    with open(conf_f + '.tmp', 'w') as f:
        f.writelines(isi)
    shutil.copystat(conf_f, conf_f + '.tmp')
    st = os.stat(conf_f)
    os.chown(conf_f + '.tmp', st.st_uid, st.st_gid)
    os.replace(conf_f + '.tmp', conf_f)
    nol = {(x['akun'], x['host']): ('0' if 'MySQLConn' in hapus else x['koneksi'], '0' if 'MySQLTime' in hapus else x['query'])
           for x in akun}
    _sql_batas(akun, nol)
    if nilai:
        os.makedirs(OV, mode=0o700, exist_ok=True)
        with open(ov_f + '.tmp', 'w') as f:
            f.write(''.join('%s=%s\n' % (k, nilai[k]) for k in sorted(nilai)))
        os.chmod(ov_f + '.tmp', 0o600)
        os.replace(ov_f + '.tmp', ov_f)
    elif os.path.exists(ov_f):
        os.remove(ov_f)
    if 'EP' in hapus and 'EP' in lama:
        _custom1_tanpa_ep(c1_f)
        _fpm_ulang(uid)

    env = dict(os.environ, VCG_TERKUNCI='1')
    try:
        r = subprocess.run([CG, u], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True,
                           timeout=300, check=False, env=env)
        k, log = r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        k, log = 124, 'timeout velocity-cg-default %s (300 dtk)' % u
    baris = next((x for x in daftar_user(info() or inf) if x['user'] == u), None)
    hasil = {'user': u, 'override_lama': lama, 'override': nilai or {}, 'cadangan': cad, 'log': log[-2000:], 'baris': baris}
    if not k and baris and baris['sesuai'] and baris['override'] == (nilai or {}):
        return {'ok': True, 'hasil': hasil}
    # kembalikan berkas + batas MySQL lama, lalu terapkan ulang
    for f in (conf_f, ov_f, c1_f):
        b = cad + '/' + os.path.basename(f)
        if os.path.exists(b):
            shutil.copy2(b, f)
        elif os.path.exists(f):
            os.remove(f)
    _sql_batas(akun, {(x['akun'], x['host']): (x['koneksi'], x['query']) for x in akun})
    _fpm_ulang(uid)
    subprocess.run([CG, u], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300, check=False, env=env)
    return {'ok': False, 'error': 'verifikasi_gagal', 'hasil': {**hasil, 'dikembalikan': True,
                                                                  'baris': next((x for x in daftar_user(info() or inf) if x['user'] == u), None)}}


AKSI = {'status': status, 'terapkan': terapkan, 'atur_user': atur_user}


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
