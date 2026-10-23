# -*- coding: utf-8 -*-
"""Kelola CSF/LFD satu server hosting (dijalankan di server lewat `ssh ... python3 -`).

Dipakai halaman Server > Proteksi (installer_status.py → /api/servers/firewall*). Pemanggil menambahkan
satu baris `jalankan(<perintah base64 JSON>)` di akhir kode ini. Mencetak satu objek JSON.
Harus tetap jalan di Python 3.6 (CloudLinux 8 platform-python).

Aksi: ringkas (baca), cek (baca), blokir, lepas, izinkan, cabut_izin, atur (ubah csf.conf, salinan
/etc/csf/csf.conf.velocity-<waktu> + csf -r + restart lfd; dikembalikan otomatis bila csf -r gagal).
Pengaman: IP kantor (SSH_CLIENT pemanggil), IP server sendiri, loopback/LAN/CGNAT, dan IP whitelist
tidak bisa diblokir; CIDR paling lebar /16 (IPv4) atau /48 (IPv6).
"""
import base64
import glob
import gzip
import ipaddress
import json
import os
import re
import shutil
import subprocess
import time

CONF = '/etc/csf/csf.conf'
# Setelan yang boleh diubah dari dashboard: kunci → (min, maks) untuk angka; 'cc' = daftar kode negara;
# 'perm' = lama blokir pemicu LFD (1 = permanen, selain itu detik).
SETELAN = {
    'DENY_IP_LIMIT': (50, 20000), 'DENY_TEMP_IP_LIMIT': (50, 10000),
    'LF_PERMBLOCK': (0, 1), 'LF_PERMBLOCK_COUNT': (1, 20), 'LF_PERMBLOCK_INTERVAL': (3600, 604800),
    'LF_SSHD_PERM': 'perm', 'LF_DIRECTADMIN_PERM': 'perm', 'LF_FTPD_PERM': 'perm', 'LF_SMTPAUTH_PERM': 'perm',
    'LF_POP3D_PERM': 'perm', 'LF_IMAPD_PERM': 'perm', 'LF_HTACCESS_PERM': 'perm', 'LF_MODSEC_PERM': 'perm',
    'LF_SSHD': (0, 100), 'LF_FTPD': (0, 100), 'LF_SMTPAUTH': (0, 100),
    'LF_POP3D': (0, 100), 'LF_IMAPD': (0, 100), 'LF_HTACCESS': (0, 100), 'LF_MODSEC': (0, 100),
    'LF_DIRECTADMIN': (0, 100), 'LF_INTERVAL': (300, 86400),
    'CT_LIMIT': (0, 1000), 'CT_INTERVAL': (10, 300), 'CT_BLOCK_TIME': (300, 86400),
    'CC_DENY': 'cc',
}
JARINGAN_TERLARANG = [ipaddress.ip_network(n) for n in
                      ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '100.64.0.0/10',
                       '0.0.0.0/8', '::1/128', 'fc00::/7', 'fe80::/10')]


def jalan(cmd, batas=30):
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=batas)
        return r.returncode, r.stdout
    except Exception as e:
        return -1, str(e)


def baca(path):
    try:
        with open(path, errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def baris_data(path):
    for b in baca(path).split('\n'):
        b = b.strip()
        if b and not b.startswith('#'):
            yield b


def pecah(b):
    """'1.2.3.4 # komentar - Wed Oct  7 15:27:37 2026' → (ip, komentar, waktu)."""
    alamat, _, ket = b.partition('#')
    ket = ket.strip()
    waktu = None
    m = re.search(r' - (\w{3} \w{3}\s+\d+ \d\d:\d\d:\d\d \d{4})$', ket)
    if m:
        try:
            waktu = int(time.mktime(time.strptime(re.sub(r'\s+', ' ', m.group(1)), '%a %b %d %H:%M:%S %Y')))
            ket = ket[:m.start()].strip()
        except ValueError:
            pass
    return alamat.strip(), ket, waktu


def sumber(ket):
    if ket.startswith('BFM:'):  # Brute Force Monitor DirectAdmin (brute_ip.data: wordpress1=…), bukan cPGuard
        return 'directadmin'
    # Velocity BFM = pemicu LFD kustom vwaf* (regex.custom.pm), termasuk yang jadi permanen lewat LF_PERMBLOCK
    if 'Velocity WAF' in ket or '(vwaf' in ket:
        return 'velocity'
    if ket.startswith('lfd:') or ket.startswith('lfd '):
        return 'lfd'
    if ket.startswith('velocity:'):
        return 'dashboard'
    return 'manual'


def jaringan(teks):
    try:
        return ipaddress.ip_network(teks, strict=False)
    except ValueError:
        return None


def daftar_deny():
    out = []
    for b in baris_data('/etc/csf/csf.deny'):
        if b.lower().startswith('include'):
            continue
        ip, ket, waktu = pecah(b)
        out.append({'ip': ip, 'ket': ket, 'waktu': waktu, 'sumber': sumber(ket)})
    return out


def daftar_allow():
    out = []
    for b in baris_data('/etc/csf/csf.allow'):
        ip, ket, waktu = pecah(b)
        if ip.lower().startswith('include'):
            berkas = ip.split(None, 1)[1] if ' ' in ip else ''
            out.append({'ip': ip, 'ket': ket, 'include': True, 'isi': sum(1 for _ in baris_data(berkas)) if berkas else 0})
            continue
        # Aturan lanjutan (tcp|out|u=0) tetap ditampilkan, tapi tidak bisa dihapus dari dashboard
        out.append({'ip': ip, 'ket': ket, 'waktu': waktu, 'aturan': not jaringan(ip), 'sumber': sumber(ket)})
    return out


def daftar_sementara(berkas):
    """/var/lib/csf/csf.tempban|tempallow: waktu|ip|port|arah|ttl|pesan."""
    out, now = [], time.time()
    for b in baca(berkas).split('\n'):
        p = b.split('|')
        if len(p) < 6:
            continue
        try:
            sisa = int(p[0]) + int(p[4]) - now
        except ValueError:
            continue
        if sisa > 0:
            ket = '|'.join(p[5:]).strip()
            out.append({'ip': p[1], 'port': p[2] or '*', 'arah': p[3], 'sisa': int(sisa), 'ket': ket,
                        'waktu': int(p[0]), 'sumber': sumber(ket)})
    return out


def setelan():
    conf = baca(CONF)
    out = {}
    for k in list(SETELAN) + ['TESTING', 'LF_DAEMON', 'LF_IPSET', 'CC_SRC']:
        m = re.search(r'^%s\s*=\s*"([^"]*)"' % k, conf, re.M)
        if m:
            out[k] = m.group(1)
    return out


def ip_kantor():
    return (os.environ.get('SSH_CLIENT') or '').split(' ')[0] or None


def ip_server():
    _, t = jalan(['hostname', '-I'], 5)
    return [x for x in t.split() if jaringan(x)]


def ringkas(_):
    ada = os.path.isfile(CONF)
    if not ada:
        return {'csf': False}
    _, v = jalan(['csf', '-v'], 10)
    m = re.search(r'v([\d.]+)', v)
    layanan = {}
    for u in ('csf', 'lfd'):
        _, s = jalan(['systemctl', 'is-active', u], 5)
        layanan[u] = s.strip() or 'unknown'
    return {'csf': True, 'versi': m.group(1) if m else None, 'layanan': layanan, 'setelan': setelan(),
            'deny': daftar_deny(), 'allow': daftar_allow(),
            'sementara': daftar_sementara('/var/lib/csf/csf.tempban'),
            'izin_sementara': daftar_sementara('/var/lib/csf/csf.tempallow'),
            'ip_kantor': ip_kantor(), 'ip_server': ip_server()}


def cocok(net, teks):
    lain = jaringan(teks)
    return bool(lain and lain.version == net.version and net.overlaps(lain))


def cek(p):
    net = jaringan(p['ip'])
    hasil = {'ip': p['ip'], 'deny': [], 'sementara': [], 'allow': [], 'ignore': False}
    for d in daftar_deny():
        if cocok(net, d['ip']):
            hasil['deny'].append(d)
    for d in daftar_sementara('/var/lib/csf/csf.tempban'):
        if cocok(net, d['ip']):
            hasil['sementara'].append(d)
    for d in daftar_allow():
        if not d.get('include') and not d.get('aturan') and cocok(net, d['ip']):
            hasil['allow'].append(d)
    hasil['ignore'] = any(cocok(net, b.split('#')[0].strip()) for b in baris_data('/etc/csf/csf.ignore'))
    # Blokir aktif di iptables/ipset (termasuk dari daftar Include/negara yang tidak ada di csf.deny)
    _, g = jalan(['csf', '-g', str(net.network_address) if net.num_addresses == 1 else p['ip']], 30)
    hasil['terblokir_aktif'] = bool(re.search(r'Set:chain_DENY|DROP|DENY', g)) and 'chain_ALLOW' not in g
    hasil['ip_kantor'] = cocok(net, ip_kantor() or '')
    return hasil


def tolak_blokir(net):
    if net.prefixlen < (16 if net.version == 4 else 48):
        return 'cidr_terlalu_lebar'
    for n in JARINGAN_TERLARANG:
        if n.version == net.version and net.overlaps(n):
            return 'ip_lokal'
    if cocok(net, ip_kantor() or ''):
        return 'ip_kantor'
    if any(cocok(net, x) for x in ip_server()):
        return 'ip_server'
    if any(not d.get('include') and not d.get('aturan') and cocok(net, d['ip']) for d in daftar_allow()):
        return 'ada_di_whitelist'
    return None


def keterangan(p):
    ket = re.sub(r'[^\w .,:/@()+=-]', '', p.get('ket') or '')[:120].strip()
    return 'velocity: ' + (ket or 'dari dashboard') + (' (%s)' % p['oleh'] if p.get('oleh') else '')


def blokir(p):
    net = jaringan(p['ip'])
    alasan = tolak_blokir(net)
    if alasan:
        return {'ok': False, 'error': alasan}
    ttl = int(p.get('ttl') or 0)
    if ttl:
        kode, keluar = jalan(['csf', '-td', p['ip'], str(ttl), keterangan(p)])
    else:
        kode, keluar = jalan(['csf', '-d', p['ip'], keterangan(p)])
    return {'ok': kode == 0, 'keluaran': keluar.strip()[-400:], 'cek': cek(p)}


def lepas(p):
    k1, o1 = jalan(['csf', '-dr', p['ip']])
    k2, o2 = jalan(['csf', '-tr', p['ip']])
    hasil = cek(p)
    return {'ok': not hasil['deny'] and not hasil['sementara'], 'keluaran': (o1 + o2).strip()[-400:], 'cek': hasil}


def izinkan(p):
    kode, keluar = jalan(['csf', '-a', p['ip'], keterangan(p)])
    return {'ok': kode == 0, 'keluaran': keluar.strip()[-400:], 'cek': cek(p)}


def cabut_izin(p):
    kode, keluar = jalan(['csf', '-ar', p['ip']])
    return {'ok': kode == 0, 'keluaran': keluar.strip()[-400:], 'cek': cek(p)}


def atur(p):
    ubah = p.get('setelan') or {}
    conf = baca(CONF)
    if not conf:
        return {'ok': False, 'error': 'csf_tidak_ada'}
    baru = conf
    for k, v in ubah.items():
        aturan = SETELAN.get(k)
        if aturan is None:
            return {'ok': False, 'error': 'setelan_tidak_dikenal', 'kunci': k}
        v = str(v).strip()
        if aturan == 'cc':
            v = v.upper().replace(' ', '')
            if v and (not re.match(r'^[A-Z]{2}(,[A-Z]{2})*$', v) or 'ID' in v.split(',')):
                return {'ok': False, 'error': 'nilai_tidak_sah', 'kunci': k}
        elif aturan == 'perm':
            if not re.match(r'^\d+$', v) or not (v == '1' or 300 <= int(v) <= 2592000):
                return {'ok': False, 'error': 'nilai_tidak_sah', 'kunci': k}
        elif not re.match(r'^\d+$', v) or not aturan[0] <= int(v) <= aturan[1]:
            return {'ok': False, 'error': 'nilai_tidak_sah', 'kunci': k}
        baru, n = re.subn(r'^(%s\s*=\s*)"[^"]*"' % k, lambda m: '%s"%s"' % (m.group(1), v), baru, count=1, flags=re.M)
        if not n:
            return {'ok': False, 'error': 'setelan_tidak_ada', 'kunci': k}
    if baru == conf:
        return {'ok': True, 'berubah': False, 'setelan': setelan()}
    cadangan = '%s.velocity-%s' % (CONF, time.strftime('%Y%m%d%H%M%S'))
    shutil.copy2(CONF, cadangan)
    with open(CONF + '.tmp', 'w') as f:
        f.write(baru)
    shutil.copymode(CONF, CONF + '.tmp')
    os.rename(CONF + '.tmp', CONF)
    kode, keluar = jalan(['csf', '-r'], 120)
    if kode != 0:
        shutil.copy2(cadangan, CONF)
        jalan(['csf', '-r'], 120)
        return {'ok': False, 'error': 'csf_restart_gagal', 'keluaran': keluar.strip()[-400:]}
    k2, o2 = jalan(['systemctl', 'restart', 'lfd'], 60)
    return {'ok': k2 == 0, 'berubah': True, 'cadangan': cadangan, 'setelan': setelan(),
            'keluaran': o2.strip()[-200:] if k2 else ''}


# ---- Log firewall: lfd.log (+ arsip .gz) digabung dengan blokir di csf.deny/tempban yang tidak tercatat lfd (cPGuard BFM, manual) ----
RE_SYSLOG = re.compile(r'^(\w{3}\s+\d+ \d\d:\d\d:\d\d) \S+ lfd\[\d+\]: (.*)$')
RE_IP = re.compile(r'(?<![\w.:])(\d{1,3}(?:\.\d{1,3}){3}|[0-9a-f]{0,4}(?::[0-9a-f]{0,4}){2,7})(?![\w.:])', re.I)
RE_CC = re.compile(r'\(([A-Z]{2})/([^/)]*)')
RE_PEMICU = re.compile(r'\[(LF_\w+|CT_\w+|PS_\w+|PORTFLOOD|SYNFLOOD|UDPFLOOD)\]')
DERAU = ('Watching ', 'Tracking...', 'rotated. Reopening', 'Enabled...', 'Lookups...', 'Directory Watching',
         'Restricting syslog', 'LF_APACHE_ERRPORT', 'CC: Retrieving', 'CCL: Retrieving', 'Retrieving and', '*SYSLOG CHECK*')


def jenis_lfd(isi):
    if 'Blocked in csf' in isi or 'Temporary Blocked' in isi or 'blocked in csf' in isi.lower():
        return 'blokir'
    if isi.startswith('*Error*') or 'deny failed' in isi:
        return 'galat'
    if isi.startswith('*SSH login*') or isi.startswith('*SU login*') or isi.startswith('*Console login*'):
        return 'login'
    if 'unblock' in isi.lower() or 'Removing' in isi or 'expired' in isi.lower():
        return 'lepas'
    if 'daemon' in isi or 'Main Process' in isi or 'restart' in isi.lower():
        return 'sistem'
    return 'peringatan'


def baris_lfd(batas):
    berkas = ['/var/log/lfd.log'] + sorted(glob.glob('/var/log/lfd.log-*'), reverse=True)
    for b in berkas:
        try:
            if os.path.getmtime(b) < batas - 86400 and b != '/var/log/lfd.log':
                continue
            buka = gzip.open(b, 'rt', errors='replace') if b.endswith('.gz') else open(b, errors='replace')
            with buka as f:
                for baris in f:
                    yield baris
        except (OSError, EOFError):
            continue


def log(p):
    hari = max(1, min(14, int(p.get('hari') or 1)))
    now = time.time()
    batas = now - hari * 86400
    tahun = time.localtime().tm_year
    kantor = ip_kantor()
    out = []
    for baris in baris_lfd(batas):
        m = RE_SYSLOG.match(baris.rstrip('\n'))
        if not m:
            continue
        isi = m.group(2).strip()
        if not isi or any(d in isi for d in DERAU):
            continue
        try:
            t = time.mktime(time.strptime('%d %s' % (tahun, re.sub(r'\s+', ' ', m.group(1))), '%Y %b %d %H:%M:%S'))
        except ValueError:
            continue
        if t > now + 86400:
            t = time.mktime(time.strptime('%d %s' % (tahun - 1, re.sub(r'\s+', ' ', m.group(1))), '%Y %b %d %H:%M:%S'))
        if t < batas:
            continue
        ip = RE_IP.search(isi)
        cc = RE_CC.search(isi)
        pm = RE_PEMICU.search(isi)
        ev = {'t': int(t), 'jenis': jenis_lfd(isi), 'sumber': 'lfd', 'pesan': isi[:300],
              'ip': ip.group(1) if ip and jaringan(ip.group(1)) else None, 'cc': cc.group(1) if cc else None,
              'pemicu': pm.group(1) if pm else None}
        if ev['ip'] and ev['ip'] == kantor:
            ev['kantor'] = True
        out.append(ev)
    # Blokir yang tidak lewat lfd (BFM DirectAdmin, dashboard, manual) — waktunya dari komentar csf.deny
    for d in daftar_deny():
        if d['sumber'] != 'lfd' and d['waktu'] and d['waktu'] >= batas:
            cc = RE_CC.search(d['ket'])
            out.append({'t': d['waktu'], 'jenis': 'blokir', 'sumber': d['sumber'], 'ip': d['ip'], 'cc': cc.group(1) if cc else None,
                        'pemicu': (re.match(r'BFM: ([\w]+?)\d*=', d['ket']) or [None, None])[1], 'pesan': d['ket'][:300]})
    for d in daftar_sementara('/var/lib/csf/csf.tempban'):
        if d['waktu'] >= batas and not d['ket'].startswith('lfd'):
            out.append({'t': d['waktu'], 'jenis': 'blokir', 'sumber': sumber(d['ket']), 'ip': d['ip'], 'cc': None,
                        'pemicu': None, 'pesan': ('Blokir sementara: ' + d['ket'])[:300], 'sementara': True})
    out.sort(key=lambda e: -e['t'])
    hitung = {}
    for e in out:
        k = 'login_kantor' if e.get('kantor') and e['jenis'] == 'login' else e['jenis']
        hitung[k] = hitung.get(k, 0) + 1
    # Login SSH dari kantor (timer dashboard tiap 5 mnt) hanya dihitung, tidak dikirim satu per satu
    acara = [e for e in out if not (e.get('kantor') and e['jenis'] == 'login')][:int(p.get('maks') or 1500)]
    return {'ok': True, 'hari': hari, 'hitung': hitung, 'acara': acara}


# ---- Log WAF: baris "ModSecurity:" di error log LiteSpeed (+ arsip berukuran) / Apache. Tidak bergantung cPGuard. ----
RE_WAF = re.compile(r'^\[\w{3} (\w{3} +\d+ \d\d:\d\d:\d\d)(?:\.\d+)? (\d{4})\] \[[\w:]+\](?: \[pid \d+(?::tid \d+)?\])? \[client ([^\]]+)\] ModSecurity: (.*)$')
# nginx + libmodsecurity v3 (atha): "2026/07/28 16:45:43 [error] 220823#220823: *33853 [client 1.2.3.4] ModSecurity: …"
RE_WAF_NGX = re.compile(r'^(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d) \[\w+\] \d+#\d+: (?:\*\d+ )?\[client ([^\]]+)\] ModSecurity: (.*)$')
WAF_KUNCI = {k: re.compile(r'\[%s "([^"]*)"\]' % k) for k in ('msg', 'id', 'hostname', 'uri', 'file')}


RE_RULE = re.compile(r"\[Rule: '([^']*)'")
NAMA_RULE = {'IP:DDOS': 'Rate limit: terlalu banyak request beruntun (DDoS/brute force)'}


def kategori_waf(msg):
    m = msg.lower()
    if 'rate limit' in m or 'ddos' in m or 'flood' in m:
        return 'ddos'
    if re.search(r'bot|crawler|user-?agent|scanner|spider', m):
        return 'bot'
    if re.search(r'sql|xss|inject|travers|shell|exec|config|\.env|credential|php|xmlrpc|wp-|upload|backdoor|malware|lfi|rfi|probe', m):
        return 'eksploit'
    return 'lain'


def berkas_waf(batas):
    pola = ['/usr/local/lsws/logs/error.log', '/usr/local/lsws/logs/error.log.*', '/var/log/httpd/error_log', '/var/log/httpd/error_log.*',
            '/var/log/nginx/*error[._]log', '/var/log/nginx/*error[._]log.*', '/var/log/nginx/*/*error.log', '/var/log/nginx/*/*error.log.*']
    out = []
    for g in pola:
        for b in glob.glob(g):
            try:
                if os.path.getmtime(b) >= batas and not b.endswith('.gz'):
                    out.append(b)
            except OSError:
                pass
    return out


def waf(p):
    hari = max(1, min(14, int(p.get('hari') or 1)))
    maks = int(p.get('maks') or 500)
    now = time.time()
    batas = now - hari * 86400
    berkas = berkas_waf(batas)
    acara, total = [], 0
    hitung = {'kode': {}, 'aturan': {}, 'domain': {}, 'ip': {}, 'kategori': {}}
    jam = {}
    if berkas:
        try:
            proc = subprocess.Popen(['grep', '-h', 'ModSecurity: '] + berkas, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    universal_newlines=True, errors='replace')
        except Exception:
            proc = None
        for baris in (proc.stdout if proc else []):
            m = RE_WAF.match(baris)
            n = None if m else RE_WAF_NGX.match(baris)
            if not m and not n:
                continue
            try:
                if m:
                    t = int(time.mktime(time.strptime('%s %s' % (re.sub(r'\s+', ' ', m.group(1)), m.group(2)), '%b %d %H:%M:%S %Y')))
                else:
                    t = int(time.mktime(time.strptime(n.group(1), '%Y/%m/%d %H:%M:%S')))
            except ValueError:
                continue
            if t < batas:
                continue
            isi = m.group(4) if m else n.group(3)
            klien = m.group(3) if m else n.group(2)
            f = {k: (r.search(isi).group(1) if r.search(isi) else '') for k, r in WAF_KUNCI.items()}
            if not f['msg']:
                r = RE_RULE.search(isi)
                f['msg'] = NAMA_RULE.get(r.group(1), 'Rule ' + r.group(1)) if r else ''
            kode = re.search(r'with code (\d+)', isi)
            kode = kode.group(1) if kode else ('deteksi' if isi.startswith('Warning') else '-')
            ip = klien.split(':')[0] if klien.count(':') == 1 else klien
            kat = kategori_waf(f['msg'])
            total += 1
            for k, v in (('kode', kode), ('aturan', f['msg'] or ('id ' + f['id'])), ('domain', f['hostname'].lower()), ('ip', ip), ('kategori', kat)):
                hitung[k][v] = hitung[k].get(v, 0) + 1
            ember = t - t % 3600
            jam.setdefault(ember, {}).setdefault(kat, 0)
            jam[ember][kat] += 1
            acara.append({'t': t, 'ip': ip, 'kode': kode, 'msg': f['msg'][:200], 'id': f['id'], 'domain': f['hostname'].lower(),
                          'uri': f['uri'][:200], 'kategori': kat, 'cpguard': 'cpguard' in f['file'].lower() or 'cPGuard' in f['msg']})
            if len(acara) > maks * 4:
                acara.sort(key=lambda e: -e['t'])
                del acara[maks:]
        if proc:
            proc.wait()
    acara.sort(key=lambda e: -e['t'])
    teratas = {k: sorted(v.items(), key=lambda x: -x[1])[:20] for k, v in hitung.items()}
    # Pelengkap info: apakah ModSecurity aktif & ruleset yang dimuat
    opsi = baca('/usr/local/directadmin/custombuild/options.conf')
    mod = re.search(r'^modsecurity=(.*)$', opsi, re.M)
    rs = re.search(r'^modsecurity_ruleset=(.*)$', opsi, re.M)
    return {'ok': True, 'hari': hari, 'total': total, 'teratas': teratas, 'jam': sorted(jam.items()), 'acara': acara[:maks],
            'berkas': len(berkas), 'modsecurity': mod.group(1).strip() if mod else None,
            'ruleset': rs.group(1).strip() if rs else None, 'cpguard_rules': os.path.isfile('/etc/cpguard/cpguard_modsec100.conf'),
            'velocity_waf': (baca('/etc/velocity-waf/VERSI').strip() or 'terpasang') if any(os.path.isfile('/etc/modsecurity.d/velocity-waf.conf' + x) for x in ('', '.main'))  # .main = DA nginx (sanke)
                            or any('Include /etc/velocity-waf/' in baca(f) for f in glob.glob('/etc/nginx/*.conf')) else None}


AKSI = {'ringkas': ringkas, 'cek': cek, 'blokir': blokir, 'lepas': lepas, 'izinkan': izinkan,
        'cabut_izin': cabut_izin, 'atur': atur, 'log': log, 'waf': waf}


# ---- PC kantor tanpa CSF: firewalld (PC Lokal, AlmaLinux) atau ufw (PC Backup, Ubuntu) ----
# Blokir/whitelist = aturan per IP sumber (tanpa port). Keterangan & waktu disimpan di CATATAN karena
# rich rule firewalld tak punya komentar; ufw menyimpan komentar sendiri. fail2ban (bila ada) = blokir sementara.
CATATAN = '/var/lib/velocity-firewall/catatan.json'
RE_RICH = re.compile(r'^rule family="(ipv4|ipv6)" source address="([^"]+)"(.*?)\s*(accept|drop|reject)(?: type="[^"]*")?$')
RE_UFW = re.compile(r'^\[\s*(\d+)\]\s+(.+?)\s+(ALLOW|DENY|REJECT|LIMIT)(?: (IN|OUT|FWD))?\s+(.+?)(?:\s+#\s*(.*))?$')


def backend_pc():
    if os.path.isfile(CONF):
        return None
    if os.path.isfile('/usr/bin/firewall-cmd'):
        return 'firewalld'
    if os.path.isfile('/usr/sbin/ufw'):
        return 'ufw'
    return None


def catatan():
    try:
        with open(CATATAN) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def simpan_catatan(ip, isi):
    data = catatan()
    if isi is None:
        data.pop(ip, None)
    else:
        data[ip] = isi
    os.makedirs(os.path.dirname(CATATAN), exist_ok=True)
    with open(CATATAN + '.tmp', 'w') as f:
        json.dump(data, f)
    os.rename(CATATAN + '.tmp', CATATAN)


def zona():
    _, z = jalan(['firewall-cmd', '--get-default-zone'], 10)
    return z.strip() or 'public'


def rich_rules(permanen):
    cmd = ['firewall-cmd', '--zone=' + zona(), '--list-rich-rules']
    if permanen:
        cmd.insert(1, '--permanent')
    _, t = jalan(cmd, 15)
    return [b.strip() for b in t.split('\n') if b.strip().startswith('rule ')]


def urai_rich(r):
    """Rich rule → {ip, aksi: allow|deny} bila aturan IP polos (tanpa port/layanan), selain itu None."""
    m = RE_RICH.match(r)
    if not m or m.group(3).strip():
        return None
    return {'ip': m.group(2), 'aksi': 'allow' if m.group(4) == 'accept' else 'deny'}


def fail2ban_ban():
    """IP yang sedang di-ban fail2ban: [{ip, jail, sisa, waktu}]."""
    if not os.path.exists('/usr/bin/fail2ban-client'):
        return []
    kode, st = jalan(['fail2ban-client', 'status'], 10)
    m = re.search(r'Jail list:\s*(.*)', st)
    if kode != 0 or not m:
        return []
    out, now = [], time.time()
    for jail in [j.strip() for j in m.group(1).split(',') if j.strip()]:
        _, t = jalan(['fail2ban-client', 'get', jail, 'banip', '--with-time'], 10)
        for baris in t.split('\n'):
            b = re.match(r'^(\S+)\s+(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \+ (-?\d+) = (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)', baris.strip())
            if b and jaringan(b.group(1)):
                mulai = time.mktime(time.strptime(b.group(2), '%Y-%m-%d %H:%M:%S'))
                habis = time.mktime(time.strptime(b.group(4), '%Y-%m-%d %H:%M:%S'))
                out.append({'ip': b.group(1), 'jail': jail, 'waktu': int(mulai),
                            'sisa': int(habis - now) if int(b.group(3)) >= 0 else 10 ** 9})
    return out


def ufw_aturan():
    _, t = jalan(['ufw', 'status', 'numbered'], 15)
    out = []
    for baris in t.split('\n'):
        m = RE_UFW.match(baris.strip())
        if not m:
            continue
        ke, dari = m.group(2).strip(), m.group(5).strip()
        polos = ke in ('Anywhere', 'Anywhere (v6)') and (m.group(4) or 'IN') == 'IN'
        dari_ip = re.sub(r' \(v6\)$', '', dari)
        out.append({'no': int(m.group(1)), 'ke': ke, 'aksi': m.group(3), 'dari': dari_ip, 'v6': '(v6)' in ke or '(v6)' in dari,
                    'ket': (m.group(6) or '').strip(), 'polos': polos and bool(jaringan(dari_ip)), 'teks': baris.strip()})
    return out


def pc_daftar(fw):
    """(deny, sementara, allow) dalam bentuk yang sama dengan CSF."""
    cat = catatan()
    deny, sementara, allow = [], [], []
    now = time.time()

    def isi(ip, ket=''):
        c = cat.get(ip) or {}
        k = c.get('ket') or ket
        return {'ip': ip, 'ket': k, 'waktu': c.get('waktu'), 'sumber': 'dashboard' if k.startswith('velocity:') else 'manual'}
    if fw == 'firewalld':
        permanen = [x for x in map(urai_rich, rich_rules(True)) if x]
        runtime = [x for x in map(urai_rich, rich_rules(False)) if x]
        tetap = {(x['ip'], x['aksi']) for x in permanen}
        for x in permanen:
            (deny if x['aksi'] == 'deny' else allow).append(isi(x['ip']))
        for x in runtime:
            if (x['ip'], x['aksi']) not in tetap and x['aksi'] == 'deny':
                c = cat.get(x['ip']) or {}
                d = isi(x['ip'])
                d.update(port='*', arah='in', sisa=max(0, int((c.get('sampai') or now) - now)), waktu=c.get('waktu') or int(now))
                sementara.append(d)
        _, svc = jalan(['firewall-cmd', '--zone=' + zona(), '--list-services'], 10)
        _, prt = jalan(['firewall-cmd', '--zone=' + zona(), '--list-ports'], 10)
        if svc.strip():
            allow.append({'ip': 'layanan: ' + svc.strip(), 'ket': 'terbuka untuk semua IP', 'aturan': True})
        if prt.strip():
            allow.append({'ip': 'port: ' + prt.strip(), 'ket': 'terbuka untuk semua IP', 'aturan': True})
        for r in rich_rules(True):
            if not urai_rich(r):
                allow.append({'ip': r, 'ket': '', 'aturan': True})
    else:
        for a in ufw_aturan():
            if a['polos'] and a['aksi'] in ('DENY', 'REJECT'):
                deny.append(isi(a['dari'], a['ket']))
            elif a['polos'] and a['aksi'] == 'ALLOW':
                allow.append(isi(a['dari'], a['ket']))
            else:
                allow.append({'ip': '%s %s dari %s' % (a['ke'], a['aksi'], a['dari']), 'ket': a['ket'], 'aturan': True})
    for b in fail2ban_ban():
        sementara.append({'ip': b['ip'], 'port': '*', 'arah': 'in', 'sisa': b['sisa'], 'waktu': b['waktu'],
                          'ket': 'fail2ban: ' + b['jail'], 'sumber': 'fail2ban'})
    return deny, sementara, allow


def pc_ringkas(fw):
    deny, sementara, allow = pc_daftar(fw)
    layanan = {}
    if fw == 'firewalld':
        _, st = jalan(['firewall-cmd', '--state'], 10)
        layanan['firewalld'] = 'active' if st.strip() == 'running' else (st.strip() or 'mati')
        _, v = jalan(['firewall-cmd', '--version'], 10)
    else:
        _, st = jalan(['ufw', 'status'], 10)
        m = re.search(r'Status: (\w+)', st)
        layanan['ufw'] = (m.group(1) if m else 'unknown')
        _, v = jalan(['ufw', 'version'], 10)
    if os.path.exists('/usr/bin/fail2ban-client'):
        _, f = jalan(['systemctl', 'is-active', 'fail2ban'], 5)
        layanan['fail2ban'] = f.strip() or 'unknown'
    m = re.search(r'([\d.]+)', v)
    return {'csf': False, 'firewall': fw, 'versi': m.group(1) if m else None, 'zona': zona() if fw == 'firewalld' else None,
            'layanan': layanan, 'setelan': {}, 'deny': deny, 'allow': allow, 'sementara': sementara, 'izin_sementara': [],
            'ip_kantor': ip_kantor(), 'ip_server': ip_server()}


def pc_cek(fw, p):
    net = jaringan(p['ip'])
    deny, sementara, allow = pc_daftar(fw)
    hasil = {'ip': p['ip'], 'ignore': False,
             'deny': [d for d in deny if cocok(net, d['ip'])],
             'sementara': [d for d in sementara if cocok(net, d['ip'])],
             'allow': [d for d in allow if not d.get('aturan') and cocok(net, d['ip'])],
             'ip_kantor': cocok(net, ip_kantor() or '')}
    hasil['terblokir_aktif'] = bool(hasil['deny'] or hasil['sementara'])
    return hasil


def rich(ip, aksi):
    return 'rule family="%s" source address="%s" %s' % ('ipv6' if jaringan(ip).version == 6 else 'ipv4', ip, aksi)


def ufw_tambah(aksi, ip, ket):
    """Sisipkan aturan di urutan teratas keluarganya (v4/v6) supaya mendahului aturan ALLOW port."""
    v6 = jaringan(ip).version == 6
    nomor = [a['no'] for a in ufw_aturan() if a['v6'] == v6]
    cmd = ['ufw'] + (['insert', str(nomor[0])] if nomor else []) + [aksi, 'from', ip, 'comment', ket]
    return jalan(cmd, 30)


def ufw_hapus(ip, aksi_ufw):
    keluar = ''
    for a in sorted(ufw_aturan(), key=lambda x: -x['no']):
        if a['polos'] and a['dari'] == ip and a['aksi'] in aksi_ufw:
            _, o = jalan(['ufw', '--force', 'delete', str(a['no'])], 30)
            keluar += o
    return keluar


def pc_blokir(fw, p):
    net = jaringan(p['ip'])
    alasan = tolak_blokir(net)
    if alasan:
        return {'ok': False, 'error': alasan}
    ttl, ket = int(p.get('ttl') or 0), keterangan(p)
    if fw == 'firewalld':
        z = '--zone=' + zona()
        r = rich(p['ip'], 'drop')
        if ttl:
            kode, keluar = jalan(['firewall-cmd', z, '--add-rich-rule=' + r, '--timeout=%ds' % ttl])
        else:
            kode, keluar = jalan(['firewall-cmd', '--permanent', z, '--add-rich-rule=' + r])
            if kode == 0:
                kode, o2 = jalan(['firewall-cmd', z, '--add-rich-rule=' + r])
                keluar += o2
    else:
        if ttl:
            return {'ok': False, 'error': 'ttl_tidak_didukung'}
        kode, keluar = ufw_tambah('deny', p['ip'], ket)
    if kode == 0:
        simpan_catatan(p['ip'], {'ket': ket, 'waktu': int(time.time()), 'sampai': int(time.time()) + ttl if ttl else None})
    return {'ok': kode == 0, 'keluaran': keluar.strip()[-400:], 'cek': pc_cek(fw, p)}


def pc_lepas(fw, p):
    keluar = ''
    if fw == 'firewalld':
        z = '--zone=' + zona()
        for permanen in (True, False):
            for r in rich_rules(permanen):
                x = urai_rich(r)
                if x and x['aksi'] == 'deny' and x['ip'] == p['ip']:
                    _, o = jalan(['firewall-cmd'] + (['--permanent'] if permanen else []) + [z, '--remove-rich-rule=' + r])
                    keluar += o
    else:
        keluar += ufw_hapus(p['ip'], ('DENY', 'REJECT'))
    for b in fail2ban_ban():
        if b['ip'] == p['ip']:
            _, o = jalan(['fail2ban-client', 'set', b['jail'], 'unbanip', b['ip']], 15)
            keluar += o
    hasil = pc_cek(fw, p)
    if not hasil['deny'] and not hasil['sementara'] and not hasil['allow']:
        simpan_catatan(p['ip'], None)
    return {'ok': not hasil['deny'] and not hasil['sementara'], 'keluaran': keluar.strip()[-400:], 'cek': hasil}


def pc_izinkan(fw, p):
    ket = keterangan(p)
    if fw == 'firewalld':
        z = '--zone=' + zona()
        r = rich(p['ip'], 'accept')
        kode, keluar = jalan(['firewall-cmd', '--permanent', z, '--add-rich-rule=' + r])
        if kode == 0:
            kode, o2 = jalan(['firewall-cmd', z, '--add-rich-rule=' + r])
            keluar += o2
    else:
        kode, keluar = ufw_tambah('allow', p['ip'], ket)
    if kode == 0:
        simpan_catatan(p['ip'], {'ket': ket, 'waktu': int(time.time())})
    return {'ok': kode == 0, 'keluaran': keluar.strip()[-400:], 'cek': pc_cek(fw, p)}


def pc_cabut_izin(fw, p):
    keluar = ''
    if fw == 'firewalld':
        z = '--zone=' + zona()
        for permanen in (True, False):
            for r in rich_rules(permanen):
                x = urai_rich(r)
                if x and x['aksi'] == 'allow' and x['ip'] == p['ip']:
                    _, o = jalan(['firewall-cmd'] + (['--permanent'] if permanen else []) + [z, '--remove-rich-rule=' + r])
                    keluar += o
    else:
        keluar = ufw_hapus(p['ip'], ('ALLOW',))
    hasil = pc_cek(fw, p)
    if not hasil['allow']:
        simpan_catatan(p['ip'], None)
    return {'ok': not hasil['allow'], 'keluaran': keluar.strip()[-400:], 'cek': hasil}


RE_SSHD = re.compile(r'^(\d+)(?:\.\d+)? \S+ sshd[^:]*: (.*)$')
RE_F2B = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ fail2ban\.actions\s+\[\d+\]: \w+\s+\[([\w-]+)\] (Ban|Unban|Restore Ban) (\S+)')


def pc_log(fw, p):
    """Log SSH (journal sshd/ssh) + ban fail2ban + blokir dashboard. Login dari LAN/Tailscale hanya dihitung."""
    hari = max(1, min(14, int(p.get('hari') or 1)))
    now = time.time()
    batas = now - hari * 86400
    out = []
    _, t = jalan(['journalctl', '-u', 'sshd', '-u', 'ssh', '--since', '@%d' % int(batas), '-o', 'short-unix', '--no-pager', '-q'], 60)
    for baris in t.split('\n'):
        m = RE_SSHD.match(baris)
        if not m:
            continue
        isi = m.group(2)
        if isi.startswith('Accepted '):
            jenis = 'login'
        elif isi.startswith('Failed ') or isi.startswith('Invalid user'):
            jenis = 'peringatan'
        else:
            continue
        ip = RE_IP.search(isi.split(' from ')[-1]) if ' from ' in isi else None
        ip = ip.group(1) if ip and jaringan(ip.group(1)) else None
        ev = {'t': int(m.group(1)), 'jenis': jenis, 'sumber': 'ssh', 'pesan': isi[:300], 'ip': ip, 'cc': None,
              'pemicu': 'LF_SSHD' if jenis == 'peringatan' else None}
        net = jaringan(ip) if ip else None
        if net and (cocok(net, ip_kantor() or '') or any(n.version == net.version and net.overlaps(n) for n in JARINGAN_TERLARANG)):
            ev['kantor'] = True
        out.append(ev)
    for berkas in ('/var/log/fail2ban.log', '/var/log/fail2ban.log.1'):
        for baris in baca(berkas).split('\n'):
            m = RE_F2B.match(baris)
            if not m:
                continue
            tt = time.mktime(time.strptime(m.group(1), '%Y-%m-%d %H:%M:%S'))
            if tt < batas:
                continue
            out.append({'t': int(tt), 'jenis': 'lepas' if m.group(3) == 'Unban' else 'blokir', 'sumber': 'fail2ban',
                        'ip': m.group(4), 'cc': None, 'pemicu': None, 'sementara': True,
                        'pesan': 'fail2ban [%s] %s %s' % (m.group(2), m.group(3), m.group(4))})
    for ip, c in catatan().items():
        if (c.get('waktu') or 0) >= batas and (c.get('ket') or '').startswith('velocity:'):
            out.append({'t': c['waktu'], 'jenis': 'blokir', 'sumber': 'dashboard', 'ip': ip, 'cc': None, 'pemicu': None,
                        'pesan': c['ket'][:300], 'sementara': bool(c.get('sampai'))})
    out.sort(key=lambda e: -e['t'])
    hitung = {}
    for e in out:
        k = 'login_kantor' if e.get('kantor') and e['jenis'] == 'login' else e['jenis']
        hitung[k] = hitung.get(k, 0) + 1
    acara = [e for e in out if not (e.get('kantor') and e['jenis'] == 'login')][:int(p.get('maks') or 1500)]
    return {'ok': True, 'hari': hari, 'hitung': hitung, 'acara': acara, 'sumber_log': 'ssh+fail2ban'}


AKSI_PC = {'ringkas': lambda fw, p: pc_ringkas(fw), 'cek': pc_cek, 'blokir': pc_blokir, 'lepas': pc_lepas,
           'izinkan': pc_izinkan, 'cabut_izin': pc_cabut_izin, 'log': pc_log}


def jalankan(kode):
    p = json.loads(base64.b64decode(kode).decode())
    fw = backend_pc()
    fungsi = AKSI.get(p.get('aksi'))
    if fw:
        aksi_pc = AKSI_PC.get(p.get('aksi'))
        fungsi = (lambda q: aksi_pc(fw, q)) if aksi_pc else (lambda q: {'ok': False, 'error': 'hanya_csf'})
    if not fungsi:
        hasil = {'ok': False, 'error': 'aksi_tidak_dikenal'}
    elif p.get('aksi') not in ('ringkas', 'atur', 'log', 'waf') and not jaringan(p.get('ip') or ''):
        hasil = {'ok': False, 'error': 'ip_tidak_sah'}
    else:
        try:
            hasil = fungsi(p)
        except Exception as e:
            hasil = {'ok': False, 'error': 'galat', 'pesan': str(e)[:300]}
    print(json.dumps(hasil))
