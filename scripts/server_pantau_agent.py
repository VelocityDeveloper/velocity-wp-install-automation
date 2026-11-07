# -*- coding: utf-8 -*-
"""Pantauan Realtime VelocityGuard — agen satu server (dijalankan lewat `ssh ... python3 -`).

Dipakai services/server_pantau.py (halaman /server/pantau). Pemanggil menambahkan `jalankan(<base64 JSON>)`.
Mencetak SATU objek JSON. Wajib jalan di Python 3.6 (CloudLinux 8 platform-python). Ringan: log dibaca MUNDUR
dari ekor sampai melewati batas jendela (maks BACA_MAKS byte per berkas), tanpa scan log domain.

Aksi:
- periksa {jendela}: email (antrean, frozen, kirim/bounce/tunda, auth gagal, spam ditolak, pengirim teratas),
  peretasan (blokir LFD per pemicu, auth SMTP/SSH gagal per IP, WAF ModSecurity), DDoS (SYN_RECV, koneksi
  80/443 per IP, conntrack), sistem (load/CPU, RAM, disk, layanan).
- hapus_frozen {umur}: pesan frozen >= umur detik DISALIN dulu ke /root/velocity-cadangan/exim-frozen-<waktu>/ lalu exim -Mrm.
- tahan_pengirim {pengirim} / lepas_pengirim {pengirim}: exim -Mf / -Mt semua pesan antrean dari pengirim itu (bisa dibalik).
- jalankan_antrean: exim -q di latar (proses antrean sekali).
"""
import base64
import glob
import json
import os
import re
import shutil
import subprocess
import time

BACA_MAKS = 16 * 1024 * 1024
BLOK = 256 * 1024
BULAN = {b: i + 1 for i, b in enumerate(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'))}
IP_RE = r'(\d{1,3}(?:\.\d{1,3}){3}|[0-9a-fA-F]{0,4}(?::[0-9a-fA-F]{0,4}){2,7})'
AKUN_SISTEM = ('root', 'mail', 'diradmin', 'admin', 'apache', 'nobody', 'lsadm')


def jalan(cmd, batas=30, masuk=None):
    try:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE if masuk else None, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True, errors='replace')
    except OSError as e:
        return 127, str(e)
    try:
        out, _ = p.communicate(masuk, timeout=batas)
        return p.returncode, out or ''
    except subprocess.TimeoutExpired:
        p.kill()
        return 124, ''


def ada(cmd):
    return shutil.which(cmd) is not None


def baca_mundur(path, batas, waktu):
    """Baris berkas dari ekor ke belakang selama waktu(baris) >= batas (baris tanpa stempel dilewati)."""
    try:
        f = open(path, 'rb')
    except OSError:
        return
    with f:
        f.seek(0, 2)
        pos = f.tell()
        sisa = b''
        dibaca = 0
        while pos > 0 and dibaca < BACA_MAKS:
            n = min(BLOK, pos)
            pos -= n
            f.seek(pos)
            baris = (f.read(n) + sisa).split(b'\n')
            dibaca += n
            sisa = baris.pop(0) if pos > 0 else b''
            for b in reversed(baris):
                t = b.decode('utf-8', 'replace')
                w = waktu(t)
                if w is None:
                    continue
                if w < batas:
                    return
                yield t


def w_iso(t):  # 2026-11-07 16:38:46 (exim) / 2026-11-07 16:38:46.123 (litespeed)
    try:
        return time.mktime(time.strptime(t[:19], '%Y-%m-%d %H:%M:%S'))
    except ValueError:
        return None


def w_syslog(t):  # Nov  7 16:38:46
    try:
        bln = BULAN[t[:3]]
        w = time.mktime(time.strptime('%d-%02d-%02d %s' % (time.localtime().tm_year, bln, int(t[4:6]), t[7:15]), '%Y-%m-%d %H:%M:%S'))
        return w - 365 * 86400 if w > time.time() + 86400 else w
    except (KeyError, ValueError):
        return None


def w_nginx(t):  # 2026/11/07 16:38:46
    try:
        return time.mktime(time.strptime(t[:19], '%Y/%m/%d %H:%M:%S'))
    except ValueError:
        return None


def w_apache(t):  # [Sat Nov 07 16:38:46.123456 2026]
    m = re.match(r'\[\w{3} (\w{3}) (\d{2}) (\d{2}:\d{2}:\d{2})(?:\.\d+)? (\d{4})\]', t)
    if not m:
        return None
    try:
        return time.mktime(time.strptime('%s-%02d-%s %s' % (m.group(4), BULAN[m.group(1)], m.group(2), m.group(3)), '%Y-%m-%d %H:%M:%S'))
    except (KeyError, ValueError):
        return None


def tambah(d, k, n=1):
    d[k] = d.get(k, 0) + n


def teratas(d, n=8):
    return [{'k': k, 'n': v} for k, v in sorted(d.items(), key=lambda x: -x[1])[:n]]


# ---------- email ----------
def antrean():
    if not ada('exim'):
        return {'ada': False}
    _, t = jalan(['exim', '-bpc'], 20)
    try:
        total = int(t.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {'ada': True, 'error': 'exim_bpc'}
    hasil = {'ada': True, 'total': total, 'frozen': None, 'frozen_24j': None, 'pengirim': [], 'tertua_jam': None}
    if total > 20000:  # exim -bp antrean raksasa terlalu berat tiap menit
        return hasil
    _, t = jalan(['exim', '-bp'], 60)
    frozen, frozen_lama, umur_maks, pengirim = 0, 0, 0, {}
    for b in t.splitlines():
        m = re.match(r'\s*(\d+)([mhd])\s+\S+\s+\S+-\S+-\S+\s+<([^>]*)>(.*)', b)
        if not m:
            continue
        n = int(m.group(1))
        jam = n / 60.0 if m.group(2) == 'm' else n * (24 if m.group(2) == 'd' else 1)
        umur_maks = max(umur_maks, jam)
        tambah(pengirim, m.group(3) or '<> (bounce)')
        if 'frozen' in m.group(4):
            frozen += 1
            frozen_lama += 1 if jam >= 24 else 0
    hasil.update(frozen=frozen, frozen_24j=frozen_lama, tertua_jam=round(umur_maks, 1), pengirim=teratas(pengirim, 6))
    return hasil


def ip_dari(b):
    m = re.search(r'\[(\d{1,3}(?:\.\d{1,3}){3}|[0-9a-fA-F:]+:[0-9a-fA-F:]+)\](?!:\d)', b)
    return m.group(1) if m else None


def email(batas):
    log = '/var/log/exim/mainlog' if os.path.exists('/var/log/exim/mainlog') else '/var/log/exim_mainlog'
    h = {'masuk': 0, 'terkirim': 0, 'bounce': 0, 'tunda': 0, 'auth_gagal': 0, 'rcpt_ditolak': 0, 'spam_ditolak': 0,
         'rbl_ditolak': 0, 'dilarang_kirim': 0}
    auth_ip, kirim_akun, spam_ip = {}, {}, {}
    if not os.path.exists(log):
        return None
    for b in baca_mundur(log, batas, w_iso):
        if ' <= ' in b:
            h['masuk'] += 1
            m = re.search(r' A=\w+:(\S+)', b)
            if m:
                tambah(kirim_akun, m.group(1))
            else:
                m = re.search(r' U=(\S+) P=local', b)
                if m and m.group(1) not in AKUN_SISTEM:
                    tambah(kirim_akun, m.group(1) + ' (skrip lokal)')
        elif ' => ' in b or ' -> ' in b:
            h['terkirim'] += 1
        elif ' ** ' in b:
            h['bounce'] += 1
        elif ' == ' in b:
            h['tunda'] += 1
        elif 'authenticator failed' in b:
            h['auth_gagal'] += 1
            ip = ip_dari(b)
            if ip:
                tambah(auth_ip, ip)
        elif 'rejected' in b:
            ip = ip_dari(b)
            k = b.lower()
            if 'spam' in k and 'spamhaus' not in k:
                h['spam_ditolak'] += 1
            elif 'blocked by' in k or 'spamhaus' in k or 'blacklist' in k or 'listed' in k:
                h['rbl_ditolak'] += 1
            elif 'not allowed to send' in k:
                h['dilarang_kirim'] += 1
                continue
            elif 'rejected rcpt' in k:
                h['rcpt_ditolak'] += 1
                continue
            else:
                continue
            if ip:
                tambah(spam_ip, ip)
    return {'log': h, 'auth_ip': teratas(auth_ip), 'pengirim_akun': teratas(kirim_akun), 'spam_ip': teratas(spam_ip, 5)}


# ---------- peretasan ----------
def lfd(batas):
    pemicu, ip, total = {}, {}, 0
    for b in baca_mundur('/var/log/lfd.log', batas, w_syslog):
        if 'Blocked in csf' not in b and 'Temporary Blocked' not in b:
            continue
        total += 1
        m = re.search(r'\]: \(([^)]+)\)', b)
        tambah(pemicu, m.group(1) if m else 'lain')
        m = re.search(r'(?:from|dari) (\S+)', b)
        if m:
            tambah(ip, m.group(1))
    return {'blokir': total, 'pemicu': teratas(pemicu), 'ip': teratas(ip, 5)}


def ssh_gagal(jendela):
    ip, total = {}, 0
    baris = []
    if ada('journalctl'):
        _, t = jalan(['journalctl', '-q', '--no-pager', '--since', '-%ds' % jendela, '-t', 'sshd', '-t', 'sshd-session', '-o', 'cat'], 20)
        baris = t.splitlines()
    for b in baris:
        if 'Failed password' in b or 'Invalid user' in b or 'authentication failure' in b:
            total += 1
            m = re.search(r'from (\S+)', b)
            if m:
                tambah(ip, m.group(1))
    return {'gagal': total, 'ip': teratas(ip, 5)}


def w_campur(t):  # LiteSpeed DA: baris bawaan ISO, baris ModSecurity berformat Apache
    return w_apache(t) if t.startswith('[') else w_iso(t)


def berkas_galat_web():
    pola = [('/usr/local/lsws/logs/error.log', w_campur),('/var/log/httpd/error_log', w_apache),
            ('/var/log/nginx/error.log', w_nginx)] + [(g, w_nginx) for g in glob.glob('/var/log/nginx/*/*error.log')]
    return [(b, w) for b, w in pola if os.path.exists(b)]


def waf(batas):
    total, aturan, ip, domain = 0, {}, {}, {}
    for b, w in berkas_galat_web():
        for t in baca_mundur(b, batas, w):
            if 'ModSecurity' not in t or 'Warning.' in t:
                continue
            total += 1
            m = re.search(r'\[id "(\d+)"\]', t)
            tambah(aturan, m.group(1) if m else '?')
            m = re.search(r'\[client (\S+?)\]', t) or re.search(r'client: (\S+?),', t) or re.search(r'\[(\d{1,3}(?:\.\d{1,3}){3}):\d+', t)
            if m:
                tambah(ip, m.group(1).rsplit(':', 1)[0] if m.group(1).count(':') == 1 else m.group(1))
            m = re.search(r'\[hostname "([^"]+)"\]', t) or re.search(r'host: "([^"]+)"', t)
            if m:
                tambah(domain, m.group(1))
    return {'tolak': total, 'aturan': teratas(aturan, 5), 'ip': teratas(ip, 5), 'domain': teratas(domain, 5)}


# ---------- DDoS / koneksi ----------
def alamat(a):
    a = a.rsplit(':', 1)[0].strip('[]')
    return a[7:] if a.startswith('::ffff:') else a


def koneksi():
    h = {'syn_recv': 0, 'established': 0, 'time_wait': 0, 'web': 0, 'ip_web': [], 'ip_syn': [], 'conntrack': None, 'conntrack_maks': None}
    _, t = jalan(['ss', '-Htan'], 20)
    per_ip, syn_ip = {}, {}
    for b in t.splitlines():
        k = b.split()
        if len(k) < 5:
            continue
        st, port = k[0], k[3].rsplit(':', 1)[-1]
        if st == 'SYN-RECV':
            h['syn_recv'] += 1
            tambah(syn_ip, alamat(k[4]))
        elif st == 'TIME-WAIT':
            h['time_wait'] += 1
        elif st == 'ESTAB':
            h['established'] += 1
            if port in ('80', '443'):
                h['web'] += 1
                tambah(per_ip, alamat(k[4]))
    h['ip_web'] = teratas(per_ip, 8)
    h['ip_syn'] = teratas(syn_ip, 5)
    h['ip_unik_web'] = len(per_ip)
    for k, f in (('conntrack', '/proc/sys/net/netfilter/nf_conntrack_count'), ('conntrack_maks', '/proc/sys/net/netfilter/nf_conntrack_max')):
        try:
            h[k] = int(open(f).read().strip())
        except (OSError, ValueError):
            pass
    return h


# ---------- sistem ----------
def sistem():
    h = {'cpu': os.cpu_count() or 1}
    try:
        h['load'] = [float(x) for x in open('/proc/loadavg').read().split()[:3]]
    except (OSError, ValueError):
        h['load'] = None
    try:
        mem = dict((b.split(':')[0], int(b.split()[1])) for b in open('/proc/meminfo') if ':' in b)
        h['ram_persen'] = round(100 - 100.0 * mem.get('MemAvailable', 0) / max(mem.get('MemTotal', 1), 1), 1)
        h['swap_persen'] = round(100 - 100.0 * mem.get('SwapFree', 0) / mem['SwapTotal'], 1) if mem.get('SwapTotal') else 0
    except (OSError, ValueError, IndexError):
        pass
    disk = {}
    for m in ('/', '/home', '/var'):
        if os.path.ismount(m):
            s = os.statvfs(m)
            disk[m] = round(100 - 100.0 * s.f_bavail / max(s.f_blocks, 1), 1)
    h['disk'] = disk
    layanan = {}
    for grup in (('exim',), ('dovecot',), ('lsws', 'httpd', 'nginx'), ('mysqld', 'mariadb'), ('lfd',), ('directadmin',)):
        for u in grup:
            if any(os.path.exists(d + u + '.service') for d in ('/usr/lib/systemd/system/', '/etc/systemd/system/', '/lib/systemd/system/')):
                _, s = jalan(['systemctl', 'is-active', u], 5)
                if s.strip() == 'active' or u == grup[-1]:
                    layanan[u] = s.strip() or 'unknown'
                    break
    h['layanan'] = layanan
    return h


def periksa(p):
    jendela = max(60, min(3600, int(p.get('jendela') or 300)))
    mulai = time.time()
    batas = mulai - jendela
    em = email(batas) or {}
    em['antrean'] = antrean()
    return {'ok': True, 't': int(mulai), 'jendela': jendela, 'email': em,
            'retas': {'lfd': lfd(batas), 'ssh': ssh_gagal(jendela), 'waf': waf(batas)},
            'ddos': koneksi(), 'sistem': sistem(), 'detik': round(time.time() - mulai, 2)}


# ---------- tindakan ----------
def id_sah(i):
    return re.match(r'^[0-9A-Za-z]{6}-[0-9A-Za-z]{6,11}-[0-9A-Za-z]{2,4}$', i or '') is not None


def berkas_spool(i):
    return glob.glob('/var/spool/exim/input/*/%s-[HD]' % i) + glob.glob('/var/spool/exim/input/%s-[HD]' % i)


def hapus_frozen(p):
    umur = max(3600, int(p.get('umur') or 86400))
    _, t = jalan(['exiqgrep', '-z', '-i', '-o', str(umur)], 60)
    ids = [i for i in t.split() if id_sah(i)]
    if not ids:
        return {'ok': True, 'jumlah': 0}
    cad = '/root/velocity-cadangan/exim-frozen-%s' % time.strftime('%Y%m%d-%H%M%S')
    os.makedirs(cad, 0o700)
    kurang = 0
    for i in ids:
        f = berkas_spool(i)
        kurang += 0 if f else 1
        for x in f:
            shutil.copy2(x, cad)
    if kurang:  # tiap pesan wajib punya salinan; ada yang tak tersalin = batal hapus
        return {'ok': False, 'error': 'salin_cadangan_gagal', 'cadangan': cad, 'kurang': kurang}
    kode, out = jalan(['exim', '-Mrm'] + ids, 180)
    return {'ok': kode == 0, 'jumlah': len(ids), 'cadangan': cad, 'keluaran': out.strip()[-300:]}


def pesan_pengirim(pengirim):
    if not re.match(r'^[\w.+=-]+@[\w.-]+$', pengirim or ''):
        return None
    _, t = jalan(['exiqgrep', '-i', '-f', '^<?%s>?$' % re.escape(pengirim)], 60)
    return [i for i in t.split() if id_sah(i)]


def tahan_pengirim(p, opsi='-Mf'):
    ids = pesan_pengirim(p.get('pengirim'))
    if ids is None:
        return {'ok': False, 'error': 'pengirim_tidak_sah'}
    if not ids:
        return {'ok': True, 'jumlah': 0}
    kode, out = jalan(['exim', opsi] + ids, 120)
    return {'ok': kode == 0, 'jumlah': len(ids), 'keluaran': out.strip()[-300:]}


def jalankan_antrean(_):
    subprocess.Popen(['nice', '-n', '10', 'exim', '-q'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     preexec_fn=os.setsid)
    return {'ok': True}


AKSI = {'periksa': periksa, 'hapus_frozen': hapus_frozen, 'tahan_pengirim': tahan_pengirim,
        'lepas_pengirim': lambda p: tahan_pengirim(p, '-Mt'), 'jalankan_antrean': jalankan_antrean}


def jalankan(kode):
    p = json.loads(base64.b64decode(kode).decode())
    f = AKSI.get(p.get('aksi'))
    try:
        hasil = f(p) if f else {'ok': False, 'error': 'aksi_tidak_dikenal'}
    except Exception as e:  # noqa: BLE001
        hasil = {'ok': False, 'error': 'galat', 'pesan': str(e)[:300]}
    print(json.dumps(hasil, ensure_ascii=False))
