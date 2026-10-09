"""Menu Security dashboard: status keamanan PC kantor + aksi blokir/buka IP (/api/security).

Sumber data:
- Gerbang login dash.velocity.ai.id (/opt/dash-login): /var/lib/velocity/dash-login/{log.jsonl,blokir.json,pengaturan.json}
- fail2ban jail sshd (fail2ban-client, /var/log/fail2ban.log); perubahan aturan disimpan di
  /etc/fail2ban/jail.d/90-dashboard.local supaya bertahan setelah restart.
- SSH gagal dari journal sshd, firewalld, SELinux, sshd -T, cloudflared.
Firewall hanya dibaca: perubahannya lewat skrip /root/velocity-cadangan/firewall-lan-saja.sh (manual).
"""
import json
import os
import re
import subprocess
import threading
import time
from collections import Counter
from ipaddress import ip_address, ip_network

DASH = '/var/lib/velocity/dash-login'
DASH_LOG = f'{DASH}/log.jsonl'
DASH_BLOKIR = f'{DASH}/blokir.json'
DASH_PENGATURAN = f'{DASH}/pengaturan.json'
DASH_BAWAAN = {'maks_gagal': 5, 'jendela_menit': 15, 'lama_blokir_menit': 60}
F2B_LOG = '/var/log/fail2ban.log'
F2B_DASHBOARD = '/etc/fail2ban/jail.d/90-dashboard.local'
CLOUDFLARED = '/etc/cloudflared/config.yml'
# Jaringan yang tidak boleh diblokir (akses kantor/Tailscale/lokal)
AMAN = tuple(map(ip_network, ('127.0.0.0/8', '::1/128', '192.168.0.0/16', '100.64.0.0/10', 'fd7a:115c:a1e0::/48', 'fe80::/10')))
LAYANAN_PORT = {'ssh': '22/tcp', 'http': '80/tcp', 'https': '443/tcp', 'dns': '53/tcp', 'dhcpv6-client': '546/udp'}

_kunci = threading.Lock()
_cache = {'waktu': 0, 'data': None}


def _jalan(cmd, batas=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=batas)
        return r.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ''


def _aktif(layanan):
    return _jalan(['systemctl', 'is-active', layanan]) == 'active'


def _baca_json(path, bawaan):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return bawaan


def _tulis_json(path, data):
    sementara = path + '.tmp'
    with open(sementara, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(sementara, path)


# ---------------- baca status ----------------

def _firewall():
    if _jalan(['firewall-cmd', '--state']) != 'running':
        return {'aktif': False, 'zona': [], 'hanya_lan': False}
    zona = []
    nama_aktif = [b for b in _jalan(['firewall-cmd', '--get-active-zones']).splitlines() if b and not b.startswith(' ')]
    for nama in nama_aktif:
        isi = {}
        for baris in _jalan(['firewall-cmd', f'--zone={nama}', '--list-all']).splitlines()[1:]:
            if ':' in baris:
                k, _, v = baris.strip().partition(':')
                isi[k.strip()] = v.strip()
        zona.append({
            'nama': nama,
            'sumber': isi.get('sources', '').split(),
            'interface': isi.get('interfaces', '').split(),
            'layanan': isi.get('services', '').split(),
            'port': isi.get('ports', '').split(),
        })
    publik = next((z for z in zona if z['interface'] and not z['sumber']), None)
    terbuka = [l for l in (publik['layanan'] if publik else []) if l != 'dhcpv6-client'] + (publik['port'] if publik else [])
    return {'aktif': True, 'zona': zona, 'hanya_lan': publik is not None and not terbuka,
            'terbuka_internet': terbuka, 'zona_internet': publik['nama'] if publik else None}


def _ssh_konfig():
    hasil = {}
    for baris in _jalan(['sshd', '-T']).splitlines():
        k, _, v = baris.partition(' ')
        if k in ('port', 'permitrootlogin', 'passwordauthentication', 'pubkeyauthentication', 'maxauthtries'):
            hasil[k] = v
    return hasil


def _fail2ban():
    if not _aktif('fail2ban'):
        return {'aktif': False}
    st = _jalan(['fail2ban-client', 'status', 'sshd'])
    ambil = lambda label: (re.search(rf'{label}:\s*(.*)', st) or [None, ''])[1].strip()
    aturan = {k: _jalan(['fail2ban-client', 'get', 'sshd', k]) for k in ('maxretry', 'findtime', 'bantime')}
    abaikan = re.findall(r'[0-9a-fA-F:.]+/\d+|[0-9a-fA-F:.]{3,}', _jalan(['fail2ban-client', 'get', 'sshd', 'ignoreip']).split('ignored:', 1)[-1])
    riwayat = []
    try:
        with open(F2B_LOG, errors='replace') as f:
            for baris in f:
                m = re.match(r'(\S+ \S+?),\d+ .*\[(\w+)\] (Ban|Unban|Restore Ban) (\S+)', baris)
                if m:
                    riwayat.append({'waktu': m[1], 'jail': m[2], 'aksi': m[3], 'ip': m[4]})
    except OSError:
        pass
    return {
        'aktif': True,
        'gagal_sekarang': int(ambil('Currently failed') or 0),
        'gagal_total': int(ambil('Total failed') or 0),
        'blokir_sekarang': int(ambil('Currently banned') or 0),
        'blokir_total': int(ambil('Total banned') or 0),
        'ip_diblokir': ambil('Banned IP list').split(),
        'maxretry': int(aturan['maxretry'] or 0),
        'findtime_menit': int(aturan['findtime'] or 0) // 60,
        'bantime_menit': int(aturan['bantime'] or 0) // 60,
        'abaikan': abaikan,
        'riwayat': riwayat[-50:][::-1],
    }


def _ssh_gagal():
    """Percobaan login SSH gagal 24 jam terakhir, per IP."""
    teks = _jalan(['journalctl', '-u', 'sshd', '--since', '-24h', '-o', 'cat', '--no-pager'], batas=20)
    per_ip = Counter()
    for baris in teks.splitlines():
        if re.search(r'Failed password|Invalid user|authentication failure|maximum authentication attempts|Connection closed by (authenticating|invalid) user', baris):
            m = re.search(r'from ([0-9a-fA-F:.]+)|rhost=([0-9a-fA-F:.]+)| ([0-9a-fA-F:.]+) port \d+', baris)
            if m:
                per_ip[next(g for g in m.groups() if g)] += 1
    return {'total': sum(per_ip.values()), 'per_ip': [{'ip': ip, 'jumlah': n} for ip, n in per_ip.most_common(20)]}


def _tunnel():
    host = []
    try:
        with open(CLOUDFLARED) as f:
            for baris in f:
                m = re.match(r'\s*-\s*hostname:\s*(\S+)', baris)
                if m:
                    host.append(m[1])
    except OSError:
        pass
    return {'aktif': _aktif('cloudflared'), 'hostname': host, 'login_aktif': _aktif('dash-login')}


def _pengaturan_dash():
    p = dict(DASH_BAWAAN)
    p.update({k: v for k, v in _baca_json(DASH_PENGATURAN, {}).items() if k in DASH_BAWAAN and isinstance(v, int) and v > 0})
    return p


def _dash():
    sekarang = time.time()
    blokir = [{'ip': ip, **e} for ip, e in _baca_json(DASH_BLOKIR, {}).items() if not e.get('sampai') or e['sampai'] > sekarang]
    log = []
    try:
        with open(DASH_LOG) as f:
            for baris in f:
                try:
                    log.append(json.loads(baris))
                except ValueError:
                    pass
    except OSError:
        pass
    sehari = [b for b in log if b.get('waktu', 0) > sekarang - 86400]
    return {
        'pengaturan': _pengaturan_dash(),
        'blokir': sorted(blokir, key=lambda e: -e.get('sejak', 0)),
        'log': log[-100:][::-1],
        'hari_ini': {
            'berhasil': sum(b['hasil'] == 'berhasil' for b in sehari),
            'gagal': sum(b['hasil'] == 'gagal' for b in sehari),
            'ditolak': sum(b['hasil'] == 'diblokir' for b in sehari),
            'ip_unik': len({b['ip'] for b in sehari}),
        },
    }


HARI_AKTIVITAS = 14


def _aktivitas():
    """Ringkasan serangan 14 hari ala cPGuard: per hari (login dash + SSH dari fail2ban.log), negara & IP teratas."""
    sekarang = time.time()
    awal = time.strftime('%Y-%m-%d', time.localtime(sekarang - (HARI_AKTIVITAS - 1) * 86400))
    hari = {}
    for i in range(HARI_AKTIVITAS):
        tgl = time.strftime('%Y-%m-%d', time.localtime(sekarang - (HARI_AKTIVITAS - 1 - i) * 86400))
        hari[tgl] = {'login_berhasil': 0, 'login_gagal': 0, 'login_ditolak': 0, 'ssh_gagal': 0, 'ssh_blokir': 0}
    negara, penyerang = Counter(), {}

    def serang(ip, jenis, waktu, negara_ip=''):
        e = penyerang.setdefault(ip, {'ip': ip, 'jumlah': 0, 'jenis': set(), 'terakhir': 0, 'negara': ''})
        e['jumlah'] += 1
        e['jenis'].add(jenis)
        e['terakhir'] = max(e['terakhir'], waktu)
        e['negara'] = e['negara'] or negara_ip

    try:
        with open(DASH_LOG) as f:
            for baris in f:
                try:
                    b = json.loads(baris)
                except ValueError:
                    continue
                tgl = time.strftime('%Y-%m-%d', time.localtime(b.get('waktu', 0)))
                if tgl not in hari:
                    continue
                kunci = {'berhasil': 'login_berhasil', 'gagal': 'login_gagal', 'diblokir': 'login_ditolak'}.get(b.get('hasil'))
                if kunci:
                    hari[tgl][kunci] += 1
                if b.get('negara'):
                    negara[b['negara']] += 1
                if b.get('hasil') in ('gagal', 'diblokir'):
                    serang(b['ip'], 'dash', b['waktu'], b.get('negara', ''))
    except OSError:
        pass
    # Log fail2ban sekarang + satu rotasi sebelumnya (mingguan) cukup untuk 14 hari
    rotasi = sorted(f for f in os.listdir('/var/log') if f.startswith('fail2ban.log-') and not f.endswith('.gz'))
    for path in [f'/var/log/{f}' for f in rotasi[-2:]] + [F2B_LOG]:
        try:
            with open(path, errors='replace') as f:
                for baris in f:
                    if baris[:10] < awal:
                        continue
                    m = re.match(r'(\S+) (\S+?),\d+ .*\[sshd\] (Found|Ban) (\S+)', baris)
                    if not m or m[1] not in hari:
                        continue
                    if m[3] == 'Found':
                        hari[m[1]]['ssh_gagal'] += 1
                        serang(m[4], 'ssh', time.mktime(time.strptime(f'{m[1]} {m[2]}', '%Y-%m-%d %H:%M:%S')))
                    else:
                        hari[m[1]]['ssh_blokir'] += 1
        except OSError:
            pass
    teratas = sorted(penyerang.values(), key=lambda e: -e['jumlah'])[:10]
    for e in teratas:
        e['jenis'] = sorted(e['jenis'])
        e['terakhir'] = int(e['terakhir'])
    return {
        'hari': [{'tgl': t, 'nilai': v} for t, v in hari.items()],
        'negara': [{'kode': k, 'jumlah': n} for k, n in negara.most_common(8)],
        'penyerang': teratas,
    }


def _port_terbuka(fw):
    """Port TCP yang mendengarkan di luar loopback + apakah firewall membukanya ke internet."""
    publik = next((z for z in fw.get('zona', []) if z['nama'] == fw.get('zona_internet')), None)
    dibuka = set(publik['port'] if publik else []) | {LAYANAN_PORT.get(l) for l in (publik['layanan'] if publik else [])}
    hasil = {}
    for baris in _jalan(['ss', '-tlnpH']).splitlines():
        kol = baris.split()
        if len(kol) < 5:
            continue
        alamat, _, port = kol[3].rpartition(':')
        alamat = alamat.strip('[]').split('%')[0]
        if alamat.startswith('127.') or alamat == '::1':
            continue
        proses = (re.search(r'\(\("([^"]+)"', baris) or [None, '-'])[1]
        e = hasil.setdefault(port, {'port': int(port), 'proses': proses, 'alamat': set()})
        e['alamat'].add(alamat)
    daftar = []
    for e in sorted(hasil.values(), key=lambda e: e['port']):
        e['alamat'] = sorted(e['alamat'])
        e['internet'] = f"{e['port']}/tcp" in dibuka
        daftar.append(e)
    return daftar


def status(segar=False):
    with _kunci:
        if not segar and _cache['data'] and time.time() - _cache['waktu'] < 10:
            return _cache['data']
        fw = _firewall()
        data = {
            'diperbarui': int(time.time()),
            'selinux': _jalan(['getenforce']) or 'tidak diketahui',
            'firewall': fw,
            'ssh': _ssh_konfig(),
            'fail2ban': _fail2ban(),
            'ssh_gagal': _ssh_gagal(),
            'tunnel': _tunnel(),
            'dash': _dash(),
            'port': _port_terbuka(fw),
            'aktivitas': _aktivitas(),
        }
        _cache.update(waktu=time.time(), data=data)
        return data


# ---------------- aksi ----------------

def _ip_sah(nilai):
    try:
        return str(ip_address(str(nilai).strip()))
    except ValueError:
        return None


def _angka(body, kunci, minimal, maksimal):
    try:
        n = int(body.get(kunci))
    except (TypeError, ValueError):
        return None
    return n if minimal <= n <= maksimal else None


def _simpan_aturan_f2b(maxretry, findtime, bantime):
    isi = ('# Ditulis menu Security dashboard (scripts/keamanan_pc.py) — menimpa jail.local\n'
           f'[sshd]\nmaxretry = {maxretry}\nfindtime = {findtime}m\nbantime = {bantime}m\n')
    with open(F2B_DASHBOARD, 'w') as f:
        f.write(isi)


def aksi(body, ip_peminta=None):
    """Kembalikan kode galat (str) atau None bila berhasil."""
    jenis = body.get('aksi')
    if jenis in ('dash_buka', 'dash_blokir', 'ssh_buka', 'ssh_blokir'):
        ip = _ip_sah(body.get('ip'))
        if not ip:
            return 'ip_tidak_valid'
        if jenis.endswith('_blokir'):
            if any(ip_address(ip) in n for n in AMAN):
                return 'ip_jaringan_kantor'
            if ip_peminta and ip == ip_peminta:
                return 'ip_sendiri'
        if jenis == 'dash_buka' or jenis == 'dash_blokir':
            data = _baca_json(DASH_BLOKIR, {})
            if jenis == 'dash_buka':
                if data.pop(ip, None) is None:
                    return 'ip_tidak_diblokir'
            else:
                menit = _angka(body, 'menit', 0, 525600)
                if menit is None:
                    return 'durasi_tidak_valid'
                data[ip] = {'sejak': int(time.time()), 'sampai': int(time.time()) + menit * 60 if menit else 0,
                            'alasan': (str(body.get('alasan') or '').strip()[:120] or 'manual dari dashboard')}
            _tulis_json(DASH_BLOKIR, data)
        else:
            perintah = 'unbanip' if jenis == 'ssh_buka' else 'banip'
            hasil = _jalan(['fail2ban-client', 'set', 'sshd', perintah, ip])
            if hasil.strip() not in ('1', ip) and not hasil.strip().isdigit():
                return f'fail2ban: {hasil[:120] or "tidak ada jawaban"}'
    elif jenis == 'dash_pengaturan':
        nilai = {'maks_gagal': _angka(body, 'maks_gagal', 2, 50),
                 'jendela_menit': _angka(body, 'jendela_menit', 1, 1440),
                 'lama_blokir_menit': _angka(body, 'lama_blokir_menit', 1, 525600)}
        if None in nilai.values():
            return 'pengaturan_tidak_valid'
        _tulis_json(DASH_PENGATURAN, nilai)
    elif jenis == 'ssh_pengaturan':
        maxretry, findtime, bantime = (_angka(body, 'maxretry', 2, 50), _angka(body, 'findtime_menit', 1, 1440),
                                       _angka(body, 'bantime_menit', 1, 525600))
        if None in (maxretry, findtime, bantime):
            return 'pengaturan_tidak_valid'
        for k, v in (('maxretry', maxretry), ('findtime', findtime * 60), ('bantime', bantime * 60)):
            _jalan(['fail2ban-client', 'set', 'sshd', k, str(v)])
        _simpan_aturan_f2b(maxretry, findtime, bantime)
    else:
        return 'aksi_tidak_dikenal'
    _cache['data'] = None
    return None
