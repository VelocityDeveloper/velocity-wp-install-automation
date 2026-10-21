# -*- coding: utf-8 -*-
"""Kolektor monitoring server hosting (dijalankan di server lewat `ssh ... python3 -`).

HANYA MEMBACA: tidak menulis berkas, tidak mengubah layanan. Mencetak satu objek JSON.
Harus tetap jalan di Python 3.6 (CloudLinux 8 platform-python).
"""
import glob
import json
import os
import re
import subprocess
import socket
import time
from datetime import datetime, timedelta

LAYANAN = ['directadmin', 'litespeed', 'lsws', 'httpd', 'nginx', 'mariadb', 'mysqld', 'exim', 'dovecot',
           'pure-ftpd', 'proftpd', 'named', 'sshd', 'crond', 'lfd', 'fail2ban', 'imunify360', 'imunify-antivirus',
           'clamd', 'redis', 'rspamd',
           # PC Backup (Ubuntu): nama unit Debian + layanan penyimpanan
           'ssh', 'cron', 'vsftpd', 'tailscaled', 'zfs-zed',
           # PC Lokal (dashboard kantor): tunnel publik + layanan dashboard
           'cloudflared', 'installer-status', 'dash-login', 'php-fpm']
PROSES_CPGUARD = ['cpguard', 'cpgosm']


def jalan(cmd, batas=15):
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                           timeout=batas, shell=isinstance(cmd, str))
        return r.returncode, r.stdout
    except Exception:
        return -1, ''


def nama_os():
    m = re.search(r'^PRETTY_NAME="?([^"\n]*)', baca('/etc/os-release'), re.M)
    return m.group(1) if m else ''


def baca(path, default=''):
    try:
        with open(path, errors='replace') as f:
            return f.read()
    except OSError:
        return default


def suhu_cpu():
    """Suhu inti terpanas (°C) + batas panas/kritis dari sensor coretemp/k10temp; {} di VPS tanpa sensor."""
    nilai, batas, kritis = [], [], []
    for h in glob.glob('/sys/class/hwmon/hwmon*'):
        if baca(h + '/name').strip() not in ('coretemp', 'k10temp', 'zenpower'):
            continue
        for f in glob.glob(h + '/temp*_input'):
            for daftar, akhiran in ((nilai, '_input'), (batas, '_max'), (kritis, '_crit')):
                try:
                    daftar.append(int(baca(f[:-6] + akhiran)) / 1000)
                except ValueError:
                    pass
    if not nilai:
        return {}
    return {'suhu': round(max(nilai), 1), 'suhu_batas': min(batas) if batas else None,
            'suhu_kritis': min(kritis) if kritis else None}


def sistem():
    out = {'hostname': os.uname()[1], 'kernel': os.uname()[2],
           'os': baca('/etc/redhat-release').strip() or nama_os()}
    out['uptime'] = int(float(baca('/proc/uptime', '0').split()[0]))
    out['load'] = [float(x) for x in baca('/proc/loadavg', '0 0 0').split()[:3]]
    out['cpu_core'] = os.cpu_count()

    def stat():
        return [int(x) for x in baca('/proc/stat').split('\n')[0].split()[1:]]
    a = stat()
    time.sleep(1)
    b = stat()
    d = [y - x for x, y in zip(a, b)]
    total = sum(d) or 1
    out['cpu'] = round((total - d[3] - (d[4] if len(d) > 4 else 0)) * 100 / total, 1)
    out['iowait'] = round((d[4] if len(d) > 4 else 0) * 100 / total, 1)
    out.update(suhu_cpu())

    mem = {}
    for baris in baca('/proc/meminfo').split('\n'):
        k, _, v = baris.partition(':')
        if v.strip():
            mem[k] = int(v.split()[0]) * 1024
    t, av = mem.get('MemTotal', 0), mem.get('MemAvailable', 0)
    if t:
        out['ram'] = {'total': t, 'used': t - av, 'persen': round((t - av) * 100 / t, 1)}
    t, f = mem.get('SwapTotal', 0), mem.get('SwapFree', 0)
    if t:
        out['swap'] = {'total': t, 'used': t - f, 'persen': round((t - f) * 100 / t, 1)}

    disks = []
    _, teks = jalan(['df', '-PB1', '-x', 'tmpfs', '-x', 'devtmpfs', '-x', 'overlay', '-x', 'squashfs',
                     '-x', 'efivarfs', '-x', 'fuse.sshfs'])
    _, teks_i = jalan(['df', '-Pi', '-x', 'tmpfs', '-x', 'devtmpfs', '-x', 'overlay', '-x', 'squashfs',
                       '-x', 'efivarfs', '-x', 'fuse.sshfs'])
    inode = {}
    for baris in teks_i.split('\n')[1:]:
        p = baris.split()
        if len(p) >= 6 and p[4].endswith('%'):
            inode[p[5]] = int(p[4][:-1] or 0)
    for baris in teks.split('\n')[1:]:
        p = baris.split()
        if len(p) < 6:
            continue
        total, used, free = int(p[1]), int(p[2]), int(p[3])
        if total >= 5 * 1024 ** 3 or p[5] in ('/', '/home'):
            disks.append({'mount': p[5], 'total': total, 'used': used, 'free': free,
                          'persen': round(used * 100 / (used + free), 1) if used + free else 0,
                          'inode': inode.get(p[5])})
    # Dataset ZFS anak berbagi ruang kosong pool induknya → cukup induknya
    out['disks'] = [d for d in disks if not any(
        o is not d and o['free'] == d['free'] and d['mount'].startswith(o['mount'].rstrip('/') + '/') for o in disks)]
    return out


def layanan():
    _, daftar = jalan(['systemctl', 'list-unit-files', '--type=service', '--no-legend'])
    ada = {b.split()[0][:-8] for b in daftar.split('\n') if b.split() and b.split()[0].endswith('.service')}
    hasil = []
    for n in LAYANAN:
        if n not in ada:
            continue
        _, s = jalan(['systemctl', 'is-active', n], 5)
        hasil.append({'nama': n, 'status': s.strip() or 'unknown'})
    return hasil


def proses_cpguard():
    if not os.path.isdir('/opt/cpguard'):
        return None
    _, teks = jalan(['ps', '-eo', 'comm='])
    nama = set(teks.split())
    out = {'proses': {p: p in nama for p in PROSES_CPGUARD}}
    _, v = jalan(['cpgcli', '--version'], 10)
    m = re.search(r'([\d.]+)', v)
    out['versi'] = m.group(1) if m else None
    # Angka 24 jam dari database cPGuard sendiri (pembanding selama jalan paralel)
    data = '/opt/cpguard/app/data/'
    for kunci, db, tabel in (('malware', 'scanner.db', 'scanner_logs'), ('waf', 'waf.db', 'waf_logs'),
                             ('bruteforce', 'bruteforce.db', 'bruteforce_logs'), ('insiden', 'incidents.db', 'incidents')):
        kode, n = jalan(['sqlite3', '-readonly', data + db,
                         "SELECT count(*) FROM %s WHERE time >= datetime('now','-1 day','localtime')" % tabel], 10)
        out[kunci] = int(n.strip()) if kode == 0 and n.strip().isdigit() else None
    return out


RE_LFD = re.compile(r'^(\w{3}\s+\d+ \d\d:\d\d:\d\d) .*?lfd\[\d+\]: (.*)$')
RE_BLOK = re.compile(r'from (\d+\.\d+\.\d+\.\d+|[0-9a-f:]+) \((\w\w)/([^/]*)/.*\[(LF_\w+)\]')


def firewall():
    conf = baca('/etc/csf/csf.conf')
    if not conf:
        return None
    out = {}
    for k in ('TESTING', 'LF_DAEMON', 'LF_SSHD', 'LF_FTPD', 'LF_SMTPAUTH', 'LF_POP3D', 'LF_IMAPD', 'LF_DIRECTADMIN',
              'CT_LIMIT', 'SYNFLOOD', 'LF_PERMBLOCK', 'DENY_IP_LIMIT'):
        m = re.search(r'^%s\s*=\s*"([^"]*)"' % k, conf, re.M)
        if m:
            out[k] = m.group(1)
    out['versi'] = baca('/etc/csf/version.txt').strip() or None
    out['deny_permanen'] = sum(1 for b in baca('/etc/csf/csf.deny').split('\n') if b.strip() and not b.startswith('#'))
    out['allow'] = sum(1 for b in baca('/etc/csf/csf.allow').split('\n') if b.strip() and not b.startswith('#'))
    _, t = jalan(['csf', '-t'], 15)
    out['deny_sementara'] = sum(1 for b in t.split('\n') if 'DENY' in b)

    # Blokir lfd 24 jam terakhir (log syslog tanpa tahun → tahun ditebak)
    batas = datetime.now() - timedelta(hours=24)
    _, ekor = jalan(['tail', '-n', '40000', '/var/log/lfd.log'], 15)
    per_jenis, per_ip, per_negara, terbaru = {}, {}, {}, []
    gagal_login = 0
    for baris in ekor.split('\n'):
        m = RE_LFD.match(baris)
        if not m:
            continue
        try:
            t = datetime.strptime('%d %s' % (batas.year, m.group(1)), '%Y %b %d %H:%M:%S')
        except ValueError:
            continue
        if t > datetime.now() + timedelta(days=1):
            t = t.replace(year=t.year - 1)
        if t < batas:
            continue
        isi = m.group(2)
        if 'Failed' in isi:
            gagal_login += 1
        if 'Blocked in csf' not in isi:
            continue
        b = RE_BLOK.search(isi)
        if not b:
            continue
        ip, kode, negara, pemicu = b.groups()
        per_jenis[pemicu] = per_jenis.get(pemicu, 0) + 1
        per_ip[ip] = per_ip.get(ip, 0) + 1
        per_negara[kode] = per_negara.get(kode, 0) + 1
        terbaru.append({'waktu': t.strftime('%Y-%m-%d %H:%M:%S'), 'ip': ip, 'negara': kode, 'pemicu': pemicu})
    out['blokir_24j'] = sum(per_jenis.values())
    out['gagal_24j'] = gagal_login
    out['per_pemicu'] = sorted(per_jenis.items(), key=lambda x: -x[1])[:8]
    out['per_negara'] = sorted(per_negara.items(), key=lambda x: -x[1])[:8]
    out['ip_teratas'] = sorted(per_ip.items(), key=lambda x: -x[1])[:8]
    out['terbaru'] = terbaru[-10:][::-1]
    return out


def keamanan():
    out = {}
    _, t = jalan(['sshd', '-T'], 10)
    for baris in t.split('\n'):
        k, _, v = baris.partition(' ')
        if k in ('port', 'permitrootlogin', 'passwordauthentication'):
            out['ssh_' + k] = v.strip()
    _, s = jalan(['getenforce'], 5)
    out['selinux'] = s.strip() or None
    opsi = baca('/usr/local/directadmin/custombuild/options.conf')
    for k in ('modsecurity', 'modsecurity_ruleset', 'webserver', 'php1_release', 'php2_release'):
        m = re.search(r'^%s=(.*)$' % k, opsi, re.M)
        if m:
            out[k] = m.group(1).strip()
    # needs-restarting (dnf) makan 5–20 dtk; backend menyisipkan LEWATI_REBOOT = True selama hasil terakhirnya < 6 jam
    if not globals().get('LEWATI_REBOOT'):
        kode, _ = jalan(['needs-restarting', '-r'], 30)
        out['perlu_reboot'] = True if kode == 1 else (False if kode == 0 else None)
        if out['perlu_reboot'] is None and os.path.isfile('/etc/debian_version'):
            out['perlu_reboot'] = os.path.exists('/var/run/reboot-required')
    # PC kantor tanpa CSF: firewalld (AlmaLinux) atau ufw (Ubuntu)
    if not os.path.isfile('/etc/csf/csf.conf') and os.path.isfile('/usr/bin/firewall-cmd'):
        _, f = jalan(['firewall-cmd', '--state'], 10)
        out['firewalld'] = f.strip() or None
    if os.path.isfile('/usr/sbin/ufw'):
        _, u = jalan(['ufw', 'status'], 10)
        m = re.search(r'Status: (\w+)', u)
        out['ufw'] = m.group(1) if m else None
    return out


def penyimpanan():
    """Pool ZFS (PC Backup): ukuran, kesehatan, jumlah & waktu snapshot terakhir. None bila tanpa ZFS."""
    kode, t = jalan(['zpool', 'list', '-Hp', '-o', 'name,size,alloc,free,cap,health'], 10)
    if kode != 0 or not t.strip():
        return None
    pool = []
    for baris in t.strip().split('\n'):
        p = baris.split('\t')
        if len(p) == 6:
            pool.append({'nama': p[0], 'total': int(p[1]), 'used': int(p[2]), 'free': int(p[3]),
                         'persen': int(p[4]), 'health': p[5]})
    _, s = jalan(['zfs', 'list', '-Hp', '-t', 'snapshot', '-o', 'name,creation', '-s', 'creation'], 15)
    snap = [b.split('\t') for b in s.strip().split('\n') if '\t' in b]
    return {'pool': pool, 'snapshot': len(snap),
            'snapshot_terakhir': {'nama': snap[-1][0], 'waktu': int(snap[-1][1])} if snap else None}


def hosting():
    out = {}
    try:
        out['akun'] = len(os.listdir('/usr/local/directadmin/data/users'))
    except OSError:
        out['akun'] = None
    out['domain'] = sum(1 for b in baca('/etc/virtual/domainowners').split('\n') if ':' in b) or None
    kode, q = jalan(['exim', '-bp'], 30)
    if kode == 0:
        # surat sistem (bounce <> / pengirim @hostname server, mis. alert lfd ke root) bukan tanda spam akun
        host = socket.gethostname().lower()
        pengirim = {}
        sistem = 0
        for m in re.finditer(r'^\s*\d+[smhdw]\s+\S+\s+\S+\s+<([^>]*)>', q, re.M):
            a = m.group(1).lower()
            if not a or a.endswith('@' + host):
                sistem += 1
            else:
                pengirim[a] = pengirim.get(a, 0) + 1
        out['antrean_email'] = sistem + sum(pengirim.values())
        out['antrean_sistem'] = sistem
        out['antrean_teratas'] = sorted(pengirim.items(), key=lambda x: -x[1])[:3]
    else:
        out['antrean_email'] = None
    kode, st = jalan(['mysqladmin', '--defaults-extra-file=/usr/local/directadmin/conf/my.cnf', 'status'], 10)
    if kode == 0:
        for k, kunci in (('Threads', 'mysql_threads'), ('Slow queries', 'mysql_slow'), ('Uptime', 'mysql_uptime')):
            m = re.search(r'%s: (\d+)' % k, st)
            if m:
                out[kunci] = int(m.group(1))
    _, ss = jalan(['ss', '-Htn', 'state', 'established', '( sport = :80 or sport = :443 )'], 10)
    per_ip = {}
    for baris in ss.split('\n'):
        p = baris.split()
        if len(p) >= 4:
            ip = p[3].rsplit(':', 1)[0].strip('[]').replace('::ffff:', '')
            per_ip[ip] = per_ip.get(ip, 0) + 1
    out['koneksi_web'] = sum(per_ip.values())
    out['koneksi_ip_teratas'] = sorted(per_ip.items(), key=lambda x: -x[1])[:5]
    # Pemakaian CPU per akun: cuplikan kedua top (jarak 1 dtk), dijumlah per user
    _, tp = jalan(['top', '-b', '-n', '2', '-d', '1', '-w', '200'], 15)
    bagian = tp.split('\n\ntop - ')[-1].split('\n')
    per_user, mulai = {}, False
    for baris in bagian:
        p = baris.split()
        if p[:1] == ['PID']:
            mulai = True
            continue
        if mulai and len(p) >= 12:
            try:
                u = per_user.setdefault(p[1], {'user': p[1], 'cpu': 0.0, 'mem': 0.0, 'proses': 0})
                u['cpu'] += float(p[8].replace(',', '.'))
                u['mem'] += float(p[9].replace(',', '.'))
                u['proses'] += 1
            except ValueError:
                continue
    teratas = sorted(per_user.values(), key=lambda x: -x['cpu'])[:8]
    for u in teratas:
        u['cpu'], u['mem'] = round(u['cpu'], 1), round(u['mem'], 1)
    out['akun_teratas'] = teratas
    return out


def main():
    hasil = {'v': 1}
    for nama, fn in (('sistem', sistem), ('layanan', layanan), ('firewall', firewall), ('keamanan', keamanan),
                     ('hosting', hosting), ('cpguard', proses_cpguard), ('penyimpanan', penyimpanan)):
        t0 = time.time()
        try:
            hasil[nama] = fn()
        except Exception as e:  # satu bagian gagal tidak menggugurkan yang lain
            hasil[nama] = None
            hasil.setdefault('galat', {})[nama] = str(e)[:200]
        hasil.setdefault('durasi', {})[nama] = round(time.time() - t0, 1)
    print(json.dumps(hasil))


main()
