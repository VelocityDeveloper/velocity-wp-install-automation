#!/usr/bin/env python3
import json
import os
import re
import subprocess
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address, ip_network
from urllib.parse import parse_qs, urlsplit

LAN_NETWORKS = tuple(map(ip_network, ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '100.64.0.0/10')))


def cpu_percent():
    def read():
        values = list(map(int, open('/proc/stat').readline().split()[1:]))
        idle = values[3] + values[4]
        return sum(values), idle
    total_a, idle_a = read()
    time.sleep(0.1)
    total_b, idle_b = read()
    total = total_b - total_a
    return round(100 * (1 - (idle_b - idle_a) / total), 1) if total else 0.0


def memory():
    values = {}
    for line in open('/proc/meminfo'):
        key, value = line.split(':', 1)
        values[key] = int(value.split()[0]) * 1024
    total = values['MemTotal']
    available = values['MemAvailable']
    used = total - available
    return {'used': used, 'total': total, 'percent': round(100 * used / total, 1)}


def disk(path):
    stat = os.statvfs(path)
    total = stat.f_blocks * stat.f_frsize
    free = stat.f_bavail * stat.f_frsize
    used = total - free
    return {'used': used, 'total': total, 'free': free, 'percent': round(100 * used / total, 1)}


def payload():
    return {
        'cpu': cpu_percent(),
        'memory': memory(),
        'disk': disk('/'),
        'disk_home': disk('/home'),
        'load': [round(x, 2) for x in os.getloadavg()],
        'uptime': round(float(open('/proc/uptime').read().split()[0])),
        'cores': os.cpu_count() or 1,
    }


_DRIVE_CACHE = {'ts': 0.0, 'about': None}
_DRIVE_CACHE_TTL = 300.0


def drive_status():
    """Check rclone gdrive connectivity + On Progress sync progress.

    Returns dict: connected(bool), remote_used/free/total, sync{running,...}.
    The `rclone about` call is cached 5 min: while a big sync is listing,
    Drive API is saturated and a fresh call can time out — serve the last
    known-good result with cached:true instead of blocking the dashboard.
    """
    now = time.time()
    out = {'connected': False, 'error': None, 'cached': False}
    if _DRIVE_CACHE['about'] and now - _DRIVE_CACHE['ts'] < _DRIVE_CACHE_TTL:
        out.update(_DRIVE_CACHE['about'])
        out['cached'] = True
    else:
        try:
            proc = subprocess.run(
                ['/usr/bin/rclone', 'about', 'gdrive:', '--json'],
                capture_output=True, text=True, timeout=45)
            if proc.returncode == 0:
                about = json.loads(proc.stdout or '{}')
                fresh = {'connected': True,
                         'remote_used': about.get('used'),
                         'remote_free': about.get('free'),
                         'remote_total': about.get('total')}
                _DRIVE_CACHE['about'] = fresh
                _DRIVE_CACHE['ts'] = now
                out.update(fresh)
            else:
                out['error'] = (proc.stderr or 'rclone about failed').strip()[:200]
        except (subprocess.TimeoutExpired, FileNotFoundError,
                json.JSONDecodeError) as e:
            out['error'] = f'{type(e).__name__}: {e}'[:200]
        if not out['connected'] and _DRIVE_CACHE['about']:
            out.update(_DRIVE_CACHE['about'])
            out['cached'] = True
    sync = {'running': False, 'transferred': None, 'eta': None,
            'elapsed': None, 'listed': None}
    try:
        lines = [l for l in open('/tmp/onprogress-sync.log').read().splitlines()
                 if l.strip()]
        tail = lines[-6:]
        sync['log_tail'] = ' | '.join(tail)[-300:] if tail else None
        for line in tail:
            m = re.search(r'Transferred:\s+(\S+ \S+) / (\S+ \S+).*?ETA (\S+)', line)
            if m:
                sync['transferred'] = f'{m.group(1)} / {m.group(2)}'
                sync['eta'] = m.group(3)
            m = re.search(r'Elapsed time:\s+(\S+)', line)
            if m:
                sync['elapsed'] = m.group(1)
            m = re.search(r'Listed (\d+)', line)
            if m:
                sync['listed'] = m.group(1)
        ps = subprocess.run(['pgrep', '-f', 'rclone copy.*On Progress'],
                            capture_output=True, timeout=5)
        sync['running'] = ps.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        pass
    out['sync'] = sync
    return out


# ---------------------------------------------------------------------------
# Riwayat pemakaian CPU & RAM (grafik di dashboard).
# Mesin ini tidak punya sysstat/sar, jadi perekamnya di sini: satu contoh per
# menit ke JSONL supaya riwayat selamat dari restart service. Retensi 30 hari =
# rentang terpanjang di halaman; berkasnya ditulis ulang berkala agar tidak
# tumbuh selamanya.
METRICS_DIR = '/var/lib/velocity/metrics'
METRICS_FILE = os.path.join(METRICS_DIR, 'system.jsonl')
SAMPLE_EVERY = 60
RETENSI = 30 * 24 * 3600
TULIS_ULANG_TIAP = 1440
RENTANG = {'1h': 3600, '1d': 86400, '7d': 7 * 86400, '30d': 30 * 86400}
# Titik lebih rapat dari ini tidak terlihat di lebar grafik, hanya memberatkan.
TITIK_MAKS = 180

_samples = deque()
_samples_lock = threading.Lock()


def _muat_riwayat():
    batas = time.time() - RETENSI
    try:
        with open(METRICS_FILE) as f:
            for line in f:
                try:
                    row = json.loads(line)
                    t = float(row['t'])
                    if t >= batas:
                        _samples.append((t, float(row['c']), float(row['m'])))
                except (ValueError, TypeError, KeyError):
                    continue  # baris rusak (mis. tulis terpotong) dilewati
    except OSError:
        pass


def _tulis(rows, append):
    os.makedirs(METRICS_DIR, exist_ok=True)
    teks = ''.join(json.dumps({'t': round(t), 'c': c, 'm': m}) + '\n' for t, c, m in rows)
    if append:
        with open(METRICS_FILE, 'a') as f:
            f.write(teks)
        return
    tmp = METRICS_FILE + '.tmp'
    with open(tmp, 'w') as f:
        f.write(teks)
    os.replace(tmp, METRICS_FILE)


def _rekam():
    """Thread perekam. Kegagalan menulis tidak boleh mematikan API stats."""
    sejak_tulis_ulang = 0
    while True:
        try:
            row = (time.time(), cpu_percent(), memory()['percent'])
            with _samples_lock:
                _samples.append(row)
                batas = row[0] - RETENSI
                while _samples and _samples[0][0] < batas:
                    _samples.popleft()
                sejak_tulis_ulang += 1
                padat = sejak_tulis_ulang >= TULIS_ULANG_TIAP
                rows = list(_samples) if padat else [row]
            _tulis(rows, append=not padat)
            if padat:
                sejak_tulis_ulang = 0
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(SAMPLE_EVERY)


def history(rentang):
    """Deret CPU & RAM yang sudah diringkas ke <= TITIK_MAKS titik."""
    nama = rentang if rentang in RENTANG else '1h'
    span = RENTANG[nama]
    batas = time.time() - span
    with _samples_lock:
        data = [s for s in _samples if s[0] >= batas]
        mulai = _samples[0][0] if _samples else None
    lebar = max(SAMPLE_EVERY, span // TITIK_MAKS)
    ember = {}
    for t, c, m in data:
        e = ember.setdefault(int(t // lebar), [0, 0.0, 0.0, 0.0])
        e[0] += 1
        e[1] += c
        e[2] += m
        e[3] = max(e[3], c)
    titik = [{'t': int(k * lebar), 'cpu': round(ember[k][1] / ember[k][0], 1),
              'mem': round(ember[k][2] / ember[k][0], 1), 'cpu_max': round(ember[k][3], 1)}
             for k in sorted(ember)]
    return {'range': nama, 'interval': lebar, 'points': titik, 'samples': len(data),
            'sample_every': SAMPLE_EVERY,
            'recording_since': int(mulai) if mulai else None}


BACKUP_STATUS = '/var/lib/velocity/backup/status.json'


def backup_status():
    """Status backup harian ke Google Drive untuk panel dashboard.

    Isinya ditulis velocity-backup tiap tahap. Jadwal berikutnya ditanyakan ke
    systemd, bukan disimpan di berkas: kalau timer dimatikan atau diubah, panel
    harus ikut jujur, bukan menampilkan jadwal yang sudah tidak berlaku.
    """
    out = {'state': 'belum_pernah', 'phase': None, 'error': None}
    try:
        with open(BACKUP_STATUS) as f:
            out.update(json.load(f))
    except (OSError, ValueError):
        pass
    try:
        proc = subprocess.run(
            ['/usr/bin/systemctl', 'show', 'velocity-backup.timer',
             '--property=NextElapseUSecRealtime', '--property=ActiveState'],
            capture_output=True, text=True, timeout=5)
        props = dict(l.split('=', 1) for l in proc.stdout.splitlines() if '=' in l)
        out['timer_active'] = props.get('ActiveState') == 'active'
        # Meski namanya USec, systemd mencetak properti ini sebagai teks
        # ("Thu 2026-09-17 02:00:07 WIB") dan --timestamp=unix tidak mengubahnya.
        # Ambil tanggal+jamnya saja lalu baca sebagai waktu lokal; singkatan zona
        # (WIB) tidak bisa diandalkan strptime.
        bagian = props.get('NextElapseUSecRealtime', '').split()
        out['next_run'] = (int(time.mktime(time.strptime(
            f'{bagian[1]} {bagian[2]}', '%Y-%m-%d %H:%M:%S'))) if len(bagian) >= 3 else None)
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        out['timer_active'] = None
        out['next_run'] = None
    # Backup yang diam-diam berhenti jalan adalah mode gagal paling mahal: panel
    # tetap hijau karena run terakhir memang sukses, padahal isinya sudah basi.
    last_ok = out.get('last_ok')
    out['stale'] = bool(last_ok and time.time() - last_ok > 48 * 3600)
    return out


PROJECTS_FILE = os.environ.get('LOCAL_PROJECTS_FILE', '/opt/velocity-wp-install-automation/config/local-projects.json')
_PROJECTS_CACHE = {'ts': 0.0, 'data': None}
_PROJECTS_TTL = 10.0
_PROJECTS_LOCK = threading.Lock()


def _jalankan(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return ''


def _layanan(nama):
    keluaran = _jalankan(['/usr/bin/systemctl', 'show', f'{nama}.service', '--timestamp=unix',
                          '--property=ActiveState', '--property=SubState',
                          '--property=ActiveEnterTimestamp', '--property=MemoryCurrent'])
    props = dict(l.split('=', 1) for l in keluaran.splitlines() if '=' in l)
    mulai = props.get('ActiveEnterTimestamp', '').lstrip('@')
    memori = props.get('MemoryCurrent', '')
    return {
        'nama': nama,
        'aktif': props.get('ActiveState') == 'active',
        'status': f"{props.get('ActiveState', '?')}/{props.get('SubState', '?')}",
        'sejak': int(mulai) if mulai.isdigit() else None,
        'memori': int(memori) if memori.isdigit() else None,
    }


def _cek_http(port):
    # Tanpa mengikuti redirect: 302 ke halaman login berarti aplikasinya hidup.
    mulai = time.monotonic()
    try:
        keluaran = subprocess.run(
            ['/usr/bin/curl', '-s', '-o', '/dev/null', '-m', '4', '-A', 'velocity-dashboard/1.0',
             '-w', '%{http_code}', f'http://127.0.0.1:{int(port)}/'],
            capture_output=True, text=True, timeout=6).stdout.strip()
    except (subprocess.TimeoutExpired, OSError, ValueError):
        keluaran = ''
    kode = int(keluaran) if keluaran.isdigit() else 0
    return {'kode': kode, 'ms': round((time.monotonic() - mulai) * 1000)}


def _git(folder):
    if not os.path.isdir(os.path.join(folder, '.git')):
        return None
    git = ['/usr/bin/git', '-c', 'safe.directory=*', '-C', folder]
    cabang = _jalankan(git + ['rev-parse', '--abbrev-ref', 'HEAD'])
    akhir = _jalankan(git + ['log', '-1', '--format=%h%x1f%ct%x1f%s']).split('\x1f')
    remote = re.sub(r'//[^@/]*@', '//', _jalankan(git + ['remote', 'get-url', 'origin']))
    ubah = _jalankan(git + ['status', '--porcelain', '--untracked-files=no'])
    return {
        'cabang': cabang or None,
        'commit': akhir[0] if len(akhir) == 3 else None,
        'waktu': int(akhir[1]) if len(akhir) == 3 and akhir[1].isdigit() else None,
        'pesan': akhir[2] if len(akhir) == 3 else None,
        'remote': re.sub(r'\.git$', '', remote) or None,
        'berubah': len(ubah.splitlines()) if ubah else 0,
    }


def _periksa_project(p):
    hasil = dict(p)
    hasil['layanan'] = [_layanan(n) for n in p.get('layanan', [])]
    hasil['http'] = _cek_http(p['port']) if p.get('port') else None
    hasil['git'] = _git(p['folder']) if p.get('folder') else None
    return hasil


def projects_status():
    """Project yang berjalan di Local PC: identitas dari PROJECTS_FILE, status diperiksa langsung."""
    with _PROJECTS_LOCK:
        if _PROJECTS_CACHE['data'] and time.time() - _PROJECTS_CACHE['ts'] < _PROJECTS_TTL:
            return _PROJECTS_CACHE['data']
        try:
            with open(PROJECTS_FILE) as f:
                daftar = json.load(f).get('projects', [])
        except (OSError, ValueError) as e:
            return {'error': f'daftar_project_tidak_terbaca: {e}', 'projects': []}
        hasil = [None] * len(daftar)

        def kerja(i, p):
            hasil[i] = _periksa_project(p)
        utas = [threading.Thread(target=kerja, args=(i, p)) for i, p in enumerate(daftar)]
        for t in utas:
            t.start()
        for t in utas:
            t.join()
        data = {'projects': hasil, 'diperiksa': int(time.time())}
        _PROJECTS_CACHE.update(ts=time.time(), data=data)
        return data


# Akun uji tiap project disimpan terpisah dari repo (berisi kata sandi), dibaca setiap
# permintaan supaya suntingan dari dashboard langsung tampil tanpa menunggu cache status.
PROJECTS_LOGIN_FILE = os.environ.get('LOCAL_PROJECTS_LOGIN_FILE', '/etc/velocity/secrets/local-projects-login.json')


def projects_login():
    try:
        with open(PROJECTS_LOGIN_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def simpan_login(body):
    pid = str(body.get('id', ''))
    try:
        with open(PROJECTS_FILE) as f:
            ids = {p.get('id') for p in json.load(f).get('projects', [])}
    except (OSError, ValueError):
        ids = set()
    if pid not in ids:
        return 'project_tidak_dikenal'
    path = str(body.get('path', '') or '').strip()[:200]
    if path and not path.startswith('/'):
        return 'path_harus_diawali_garis_miring'
    akun = []
    for a in body.get('akun') or []:
        if not isinstance(a, dict):
            return 'akun_tidak_valid'
        baris = {k: str(a.get(k, '') or '').strip()[:200] for k in ('peran', 'user', 'sandi')}
        if baris['user'] or baris['sandi']:
            akun.append(baris)
    if len(akun) > 20:
        return 'akun_terlalu_banyak'
    semua = projects_login()
    semua[pid] = {'path': path, 'akun': akun}
    sementara = PROJECTS_LOGIN_FILE + '.tmp'
    with open(os.open(sementara, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as f:
        json.dump(semua, f, ensure_ascii=False, indent=2)
    os.replace(sementara, PROJECTS_LOGIN_FILE)
    return None


class Handler(BaseHTTPRequestHandler):
    def json_response(self, status, data):
        body = json.dumps(data, separators=(',', ':')).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path, _, query = self.path.partition('?')
        if path == '/api/drive':
            self.json_response(200, drive_status())
            return
        if path == '/api/backup':
            self.json_response(200, backup_status())
            return
        if path == '/api/projects':
            data = dict(projects_status())
            login = projects_login()
            data['projects'] = [{**p, 'login': login.get(p['id'])} for p in data.get('projects', [])]
            self.json_response(200, data)
            return
        if path == '/api/stats/history':
            self.json_response(200, history((parse_qs(query).get('range') or ['1h'])[0]))
            return
        if path != '/api/stats':
            self.send_error(404)
            return
        self.json_response(200, payload())

    def do_POST(self):
        if self.path == '/api/projects/login':
            self.simpan_login()
            return
        if self.path not in ('/api/shutdown', '/api/restart'):
            self.send_error(404)
            return
        try:
            client = ip_address(self.headers.get('X-Real-IP', self.client_address[0]))
        except ValueError:
            self.json_response(403, {'error': 'forbidden'})
            return
        origin = self.headers.get('Origin', '')
        origin_host = urlsplit(origin).hostname if origin else None
        host = self.headers.get('Host', '').split(':', 1)[0]
        confirm_header = 'X-Shutdown-Confirm' if self.path == '/api/shutdown' else 'X-Restart-Confirm'
        confirm_value = 'shutdown' if self.path == '/api/shutdown' else 'restart'
        if not any(client in network for network in LAN_NETWORKS) or origin_host != host or self.headers.get(confirm_header) != confirm_value:
            self.json_response(403, {'error': 'forbidden'})
            return
        if self.path == '/api/shutdown':
            self.json_response(202, {'status': 'shutdown_scheduled'})
            subprocess.Popen(['/usr/bin/systemctl', 'poweroff'], start_new_session=True)
        else:
            self.json_response(202, {'status': 'restart_scheduled'})
            subprocess.Popen(['/usr/bin/systemctl', 'reboot'], start_new_session=True)

    def simpan_login(self):
        # Sama dengan kontrol daya: hanya dari LAN/Tailscale dan dari halaman dashboard sendiri.
        try:
            client = ip_address(self.headers.get('X-Real-IP', self.client_address[0]))
        except ValueError:
            client = None
        origin = self.headers.get('Origin', '')
        origin_host = urlsplit(origin).hostname if origin else None
        host = self.headers.get('Host', '').split(':', 1)[0]
        if client is None or not any(client in network for network in LAN_NETWORKS) or origin_host != host:
            self.json_response(403, {'error': 'forbidden'})
            return
        try:
            panjang = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(min(panjang, 65536)) or b'{}') if panjang <= 65536 else None
        except ValueError:
            body = None
        if not isinstance(body, dict):
            self.json_response(400, {'error': 'body_tidak_valid'})
            return
        galat = simpan_login(body)
        if galat:
            self.json_response(400, {'error': galat})
            return
        self.json_response(200, {'ok': True, 'login': projects_login().get(body['id'])})

    def log_message(self, *_):
        pass


_muat_riwayat()
threading.Thread(target=_rekam, daemon=True).start()
ThreadingHTTPServer(('127.0.0.1', 9120), Handler).serve_forever()
