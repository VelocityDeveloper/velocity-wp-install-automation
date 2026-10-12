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
# Setelan yang boleh diubah dari dashboard: kunci → (min, maks) untuk angka; 'cc' = daftar kode negara.
SETELAN = {
    'DENY_IP_LIMIT': (50, 5000), 'DENY_TEMP_IP_LIMIT': (50, 2000),
    'LF_PERMBLOCK': (0, 1), 'LF_PERMBLOCK_COUNT': (1, 20),
    'LF_SSHD': (0, 100), 'LF_SSHD_PERM': (0, 604800), 'LF_FTPD': (0, 100), 'LF_SMTPAUTH': (0, 100),
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
    if ket.startswith('BFM:'):
        return 'cpguard'
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
            out.append({'ip': p[1], 'port': p[2] or '*', 'arah': p[3], 'sisa': int(sisa), 'ket': '|'.join(p[5:]).strip(),
                        'waktu': int(p[0])})
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
    # Blokir yang tidak lewat lfd (cPGuard BFM, dashboard, manual) — waktunya dari komentar csf.deny
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
    pola = ['/usr/local/lsws/logs/error.log', '/usr/local/lsws/logs/error.log.*', '/var/log/httpd/error_log', '/var/log/httpd/error_log.*']
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
            if not m:
                continue
            try:
                t = int(time.mktime(time.strptime('%s %s' % (re.sub(r'\s+', ' ', m.group(1)), m.group(2)), '%b %d %H:%M:%S %Y')))
            except ValueError:
                continue
            if t < batas:
                continue
            isi = m.group(4)
            f = {k: (r.search(isi).group(1) if r.search(isi) else '') for k, r in WAF_KUNCI.items()}
            if not f['msg']:
                r = RE_RULE.search(isi)
                f['msg'] = NAMA_RULE.get(r.group(1), 'Rule ' + r.group(1)) if r else ''
            kode = re.search(r'with code (\d+)', isi)
            kode = kode.group(1) if kode else ('deteksi' if isi.startswith('Warning') else '-')
            ip = m.group(3).split(':')[0] if m.group(3).count(':') == 1 else m.group(3)
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
            'velocity_waf': (baca('/etc/velocity-waf/VERSI').strip() or 'terpasang') if os.path.isfile('/etc/modsecurity.d/velocity-waf.conf') else None}


AKSI = {'ringkas': ringkas, 'cek': cek, 'blokir': blokir, 'lepas': lepas, 'izinkan': izinkan,
        'cabut_izin': cabut_izin, 'atur': atur, 'log': log, 'waf': waf}


def jalankan(kode):
    p = json.loads(base64.b64decode(kode).decode())
    fungsi = AKSI.get(p.get('aksi'))
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
