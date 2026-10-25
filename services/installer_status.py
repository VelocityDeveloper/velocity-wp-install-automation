#!/usr/bin/env python3
import base64
import gzip
import html
import hashlib
import io
import ipaddress
import json
import mimetypes
import os
import re
import secrets as pysecrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

ROOT = Path('/home/project')
ON_PROGRESS = Path('/home/On Progress')
STATE = Path('/var/lib/velocity/installer')
RUNNER = Path('/opt/velocity-wp-install-automation/scripts/installer-runner')
SECRETS = Path('/etc/velocity/secrets')
SSH_KEY_CANDIDATES = [SECRETS / 'ssh_key', Path('/root/.ssh/id_ed25519'), Path('/root/.ssh/id_rsa')]
DOMAIN_RE = re.compile(r'^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
# Domain yang punya folder/manifest di /home/project tapi BUKAN project klien —
# mis. server host kantor sendiri (keputusan user 2026-09-16: fahmi.hutara.com
# adalah host server, bukan pekerjaan). Daftarnya sengaja eksplisit: "manifest
# tanpa paket=" BUKAN penanda yang aman, karena arusaraadventure.com &
# pondokbungaadi.com juga begitu dan keduanya project sungguhan yang terpasang.
BUKAN_PROJECT_BAWAAN = {'fahmi.hutara.com'}
BUKAN_PROJECT_FILE = Path('/etc/velocity/installer-bukan-project')


def bukan_project():
    """Domain yang tidak boleh tampil/diklaim sebagai project.

    Bawaan di atas + satu domain per baris di BUKAN_PROJECT_FILE ('#' = komentar),
    supaya tim bisa menambah tanpa mengubah kode."""
    names = set(BUKAN_PROJECT_BAWAAN)
    try:
        for line in BUKAN_PROJECT_FILE.read_text(errors='replace').splitlines():
            line = line.split('#', 1)[0].strip().lower()
            if line:
                names.add(line)
    except OSError:
        pass
    return names
SERVERS_FILE_CANDIDATES = [
    Path('/var/lib/velocity/servers.json'),  # server-registry store (managed via /server/ panel)
    Path(__file__).resolve().parent.parent / 'config' / 'servers.json',
    Path('/etc/velocity/servers.json'),
]
API_TOKEN = os.environ.get('INSTALLER_API_TOKEN', '').strip()
# Tailscale's CGNAT range. Python 3.9's ipaddress does not report it as private.
CGNAT_NET = ipaddress.ip_network('100.64.0.0/10')
PACKAGES_DIR = Path('/var/lib/velocity/packages')
PACKAGES_META = PACKAGES_DIR / 'packages.json'
PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
AI_CONFIG_DIR = Path('/var/lib/velocity/ai')
AI_MODELS = AI_CONFIG_DIR / 'models.json'
# Fungsi installer yang memanggil AI. Model per fungsi disimpan di models.json 'pemakaian'
# (halaman /ai/); tanpa pilihan, script memakai model default (get_model di ai-content-generator.py).
AI_PERAN = (
    ('konten', 'Konten halaman & artikel', 'ai-content-generator.py'),
    ('isi_contoh', 'Isi contoh desain: layanan, produk, warna', 'paket-g-konten'),
    ('foto', 'Pemilihan foto contoh', 'paket-g-foto'),
    ('fse', 'FSE builder: gaya beranda portal berita', 'fse-apply'),
    ('tema', 'Pembaca child-theme paket biasa', 'theme-paket-biasa'),
    ('judi', 'VelocityGuard Judi AI: nilai situs judi / diretas (antivirus)', 'server_judi'),
)
# Fungsi yang TIDAK memakai model endpoint di halaman ini. Desain FSE paket custom ber-referensi
# dikerjakan agen Claude Code (scripts/desain-claude, keputusan user 2026-09-18/19): modelnya
# ditentukan CLI Claude sendiri, jadi barisnya hanya ditampilkan, tidak bisa dipilih. fse-apply
# tetap menyusun tema & halaman sebagai titik awal agen (peran 'fse' di atas hanya dipakai portal
# berita untuk memilih gaya beranda).
# Kolom ke-4/5: saklar di env autopilot & nilai bawaannya. Permintaan klien di form (PESAN TAMBAHAN)
# juga dikerjakan agen Claude Code (scripts/permintaan-claude, permintaan user 2026-09-24).
AI_PERAN_TETAP = (
    ('desain_claude', 'Desain FSE paket custom: tata letak, CSS & halaman', 'desain-claude', 'DESAIN_CLAUDE', '0'),
    ('permintaan_claude', 'Permintaan klien di form (pesan tambahan): halaman, data, menu', 'permintaan-claude',
     'PERMINTAAN_CLAUDE', '1'),
    # Pembacaan FORM ISIAN (scripts/baca-form-claude, keputusan user 2026-09-25): selalu menyala.
    ('baca_form', 'Baca form isian klien: nama, kontak, warna, referensi, pesan tambahan', 'baca-form-claude',
     'BACA_FORM_CLAUDE', '1'),
)
# Model agen = Opus terbaru yang dikenal CLI Claude (diresolve & disimpan scripts/desain-claude).
DESAIN_CLAUDE_MODEL = Path('/var/lib/velocity/desain-claude-model.json')
AUTOPILOT_ENV = Path('/etc/velocity/installer-autopilot.env')
AI_PROMPTS = AI_CONFIG_DIR / 'prompts'
AI_GENERATED = AI_CONFIG_DIR / 'generated'
# Ditulis catat_token() di ai-content-generator.py, satu baris per panggilan AI.
AI_USAGE = AI_CONFIG_DIR / 'usage.jsonl'
AI_SCRIPT = Path(__file__).resolve().parent.parent / 'scripts' / 'ai-content-generator.py'
AI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
AI_PROMPTS.mkdir(parents=True, exist_ok=True)
AI_GENERATED.mkdir(parents=True, exist_ok=True)
_rate = {}
RATE_LIMIT = 30
RATE_WINDOW = 60
_cron_cache = {'at': 0, 'value': []}
CACHE_TTL = 30
_running = {}  # domain -> subprocess.Popen
_ai_running = {}  # domain -> subprocess.Popen

# Ground truth antrean: API project-list vdnet, ditarik untuk dua status yang
# sama dengan halaman https://new.velocitydeveloper.net/project_list —
# "Belum dikerjakan" (wm_project belum ada = belum diambil) dan
# "Dalam pengerjaan" (sudah dipegang webmaster). Yang kedua tetap ditampilkan
# supaya daftar di sini tidak lebih pendek daripada daftar yang dibaca PM.
PROJECT_LIST_API_URL = os.environ.get(
    'PROJECT_LIST_API_URL', 'https://new.velocitydeveloper.net/api/api/public/project-list')
PROJECT_LIST_API_KEY_FILE = SECRETS / 'project_list_api_key'
CRM_STATUSES = ('Belum dikerjakan', 'Dalam pengerjaan')
# Hanya jenis project yang berarti "pasang WordPress". Tanpa saringan ini daftar
# installer ikut memuat tiket Deposit Iklan Google, Tambah Space, dsb — 99% isi
# daftar, padahal tidak ada hubungannya dengan instalasi.
# Nilainya harus PERSIS sama dengan opsi jenis_project di CRM
# (DataOpsiController::jenis_project) — 'Pembuatan Tanpa Domain' pernah ditulis
# di sini padahal nilai aslinya 'Pembuatan Tanpa Domain+Hosting', jadi barisnya
# tidak pernah muncul sama sekali. 'Pengembangan' sengaja di luar: situsnya
# sudah hidup, bukan pekerjaan pasang baru.
INSTALL_JENIS = {'Pembuatan', 'Pembuatan apk', 'Pembuatan apk biasa',
                 'Pembuatan apk custom', 'Pembuatan Tanpa Domain',
                 'Pembuatan Tanpa Hosting', 'Pembuatan Tanpa Domain+Hosting',
                 'Pembuatan web konsep', 'Redesign'}
# Deskripsi tiket "Kerjakan diweb velocity dl" = situs dikerjakan dulu di staging
# velocitydeveloper.co/<domain> (akun vdco di server Kiya), bukan di akun DirectAdmin
# domain klien (permintaan user 2026-09-30, cybersumatra.com). Wajib kata kerja + "di":
# "hosting di velocity" atau "migrasi ... kelayanan velocity" tetap pemasangan biasa.
STAGING_HOST = '202.73.26.2'
STAGING_DA_USER = 'vdco'
STAGING_DOMAIN = 'velocitydeveloper.co'
_STAGING_RE = re.compile(
    r'\b\w*(?:kerja|garap|pasang|taruh|instal|upload|buat|bikin)\w*\s+(?:(?:dulu|dlu|dl)\s+)?'
    r'di\s*(?:web(?:site)?|situs|staging|subdomain|subfolder|domain)?\s*'
    r'(?:velocity\s*developer|velocity|vdco|vd)\b'
    r'|velocitydeveloper\.co/|\bstaging\s+(?:di\s+)?(?:velocity|vdco|vd)\b', re.I)


def staging_dari_deskripsi(teks):
    """True kalau deskripsi tiket CRM meminta situs dikerjakan di staging web Velocity."""
    return bool(_STAGING_RE.search(str(teks or '')))


# Status CRM yang dipakai sebagai status baris di halaman.
ST_BELUM_DIAMBIL = 'belum diambil'
ST_DIKERJAKAN_WM = 'dikerjakan webmaster'
CRM_TTL = 900
CRM_RETRY = 30
# Panduan API menyarankan halaman kecil, bukan satu tarikan raksasa.
PROJECT_LIST_PER_PAGE = 2000
PROJECT_LIST_MAX_PAGES = 25
_crm_cache_projects = {'at': 0, 'value': {}, 'fetching': False, 'error': ''}
_crm_projects_lock = threading.Lock()
# "Ambil alih" dicatat lokal: CRM belum punya API tulis, jadi status "Belum
# dikerjakan" di sana tidak berubah walau installer sudah memegang project-nya.
CLAIMS_FILE = STATE / 'claims.json'
CLAIM_BY_RE = re.compile(r'^[a-z0-9:._-]{1,40}$')
_claims_lock = threading.Lock()


# IP publik kantor (akses dash.velocity.ai.id dari jaringan kantor tanpa batas request).
# MyRepublic statis; Telkom dinamis -> IP keluar PC ini dicek ulang tiap 10 menit (pola site-finish _ip_kantor).
# 36.65.0.93 = IndiBiz (Telkom) kantor, dikonfirmasi user 2026-10-19; ganti bila IP IndiBiz berubah.
IP_KANTOR_TETAP = {'202.59.194.129', '36.65.0.93'}
_ip_kantor_terdeteksi = set()


def _pantau_ip_kantor():
    while True:
        for url in ('https://api.ipify.org', 'https://ifconfig.me/ip', 'https://icanhazip.com'):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'curl/8'}), timeout=6) as r:
                    ip = str(ipaddress.ip_address(r.read(64).decode().strip()))
                _ip_kantor_terdeteksi.clear()
                _ip_kantor_terdeteksi.add(ip)
                break
            except (OSError, ValueError):
                continue
        time.sleep(600)


threading.Thread(target=_pantau_ip_kantor, daemon=True).start()


def _rate_ok(ip: str) -> bool:
    # LAN/Tailscale & IP publik kantor tanpa batas; akses publik lain (dash lewat Cloudflare) tetap dibatasi
    if _is_local_net(ip) or ip in IP_KANTOR_TETAP or ip in _ip_kantor_terdeteksi:
        return True
    now = time.time()
    lst = _rate.get(ip, [])
    lst = [t for t in lst if now - t < RATE_WINDOW]
    if len(lst) >= RATE_LIMIT:
        _rate[ip] = lst
        return False
    lst.append(now)
    _rate[ip] = lst
    return True


def _lolos_batas(handler) -> bool:
    # Pengguna yang login dash (cookie vd_dash sah) tanpa batas: IP IndiBiz kantor dinamis
    return sesi_dash.dari_cookie(handler.headers.get('Cookie')) is not None or _rate_ok(rate_ip(handler))


def client_ip(handler: BaseHTTPRequestHandler) -> str:
    """Caller's real IP. Every request arrives through nginx, so the socket peer
    is always loopback and cannot tell LAN from internet. nginx overwrites
    X-Real-IP with the true remote address, so trust that header — but only when
    the peer is loopback, i.e. it really came from our own proxy."""
    peer = handler.client_address[0] if handler.client_address else ''
    try:
        from_proxy = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        from_proxy = False
    if from_proxy:
        try:
            return str(ipaddress.ip_address((handler.headers.get('X-Real-IP') or '').strip()))
        except ValueError:
            pass
    return peer


def rate_ip(handler: BaseHTTPRequestHandler) -> str:
    """Kunci batas request. Akses dash.velocity.ai.id masuk lewat proxy lokal (X-Real-IP 127.0.0.1), jadi semua
    pengguna berbagi satu jatah; untuk itu pakai X-Forwarded-For (diisi CF-Connecting-IP oleh gerbang dash).
    Cek LAN tetap memakai client_ip()."""
    ip = client_ip(handler) or 'unknown'
    try:
        if not ipaddress.ip_address(ip).is_loopback:
            return ip
        # Entri terakhir = yang ditambahkan proxy terdekat, bukan isian klien
        return str(ipaddress.ip_address((handler.headers.get('X-Forwarded-For') or '').split(',')[-1].strip()))
    except ValueError:
        return ip


def _is_local_net(ip: str) -> bool:
    """Loopback, RFC1918 LAN, or Tailscale CGNAT."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private or addr in CGNAT_NET


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    if not API_TOKEN:
        return True
    # LAN / loopback / Tailscale bypass — tetap butuh token dari internet
    if _is_local_net(client_ip(handler)):
        return True
    auth = handler.headers.get('Authorization', '')
    return auth == f'Bearer {API_TOKEN}'


def load_servers():
    raw = os.environ.get('INSTALLER_SERVERS', '').strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    for p in SERVERS_FILE_CANDIDATES:
        if p.is_file():
            try:
                data = json.loads(p.read_text())
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and isinstance(data.get('servers'), list):
                    return data['servers']
            except Exception:
                continue
    return []



# --- kelola server (halaman /server/) ---
# Dulu ditangani server_registry.py terpisah di /usr/local/bin (tanpa repo, tanpa token):
# simpan = hapus lalu tambah di akhir, sehingga mengedit server pertama diam-diam
# mengganti tujuan default installer, dan mengganti IP membuat entri ganda.
# Sekarang disunting per posisi; urutan hanya berubah lewat "jadikan default".
SERVERS_STORE = SERVERS_FILE_CANDIDATES[0]
SERVER_FIELDS = ('name', 'host', 'user', 'port', 'notes')
_servers_lock = threading.Lock()


def clean_server(item):
    """Validasi satu entri server. Kembalikan (dict, None) atau (None, galat)."""
    if not isinstance(item, dict):
        return None, 'data_tidak_valid'
    s = {k: ' '.join(str(item.get(k) or '').split()) for k in SERVER_FIELDS}
    if not s['name'] or len(s['name']) > 80:
        return None, 'nama_wajib'
    if not re.match(r'^[A-Za-z0-9.-]{1,253}$', s['host']):
        return None, 'host_tidak_valid'
    if not re.match(r'^[a-z_][a-z0-9_-]{0,31}$', s['user']):
        return None, 'user_tidak_valid'
    if not re.match(r'^[0-9]{1,5}$', s['port']) or not 1 <= int(s['port']) <= 65535:
        return None, 'port_tidak_valid'
    s['port'] = str(int(s['port']))
    s['notes'] = s['notes'][:500]
    return s, None


def save_servers(servers):
    SERVERS_STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SERVERS_STORE.with_suffix('.tmp')
    tmp.write_text(json.dumps(servers, indent=2) + '\n')
    os.chmod(tmp, 0o600)
    tmp.replace(SERVERS_STORE)


def server_usage():
    """Jumlah manifest per target_host (situs yang dipasang ke server itu)."""
    hitung = {}
    for manifest in ROOT.glob('*/*.txt'):
        if manifest.stem != manifest.parent.name:
            continue
        host = manifest_target(manifest)
        if host:
            hitung[host] = hitung.get(host, 0) + 1
    return hitung


# PC lokal (dashboard ini sendiri) dicatat dengan host 127.0.0.1: perintah dijalankan langsung, tanpa SSH ke diri sendiri
HOST_LOKAL = ('127.0.0.1', 'localhost')


# Koneksi SSH dipakai ulang: satu master per host bertahan 10 mnt, jabat tangan 1–4 dtk per panggilan hilang.
# Master dijalankan terpisah dengan stdio /dev/null — ControlMaster=auto langsung di subprocess.run(capture_output)
# membuat proses master latar memegang pipa stderr, pemanggil ikut menunggu sampai master mati.
SSH_KONTROL = Path('/run/velocity-ssh')
SSH_PERSIST = 600
_ssh_master_kunci = {}  # soket → sedang dibuat
_ssh_master_kunci_induk = threading.Lock()


def _ssh_master(dasar, tujuan, soket):
    """True bila master hidup dan soketnya bisa dipakai. Bila belum, master dibuat di thread latar dan panggilan
    ini konek langsung — server yang tak terjangkau tidak membuat pemanggil menunggu dua kali."""
    try:
        if os.path.exists(soket) and subprocess.run(['ssh', '-S', soket, '-O', 'check', tujuan], stdin=subprocess.DEVNULL,
                                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5).returncode == 0:
            return True
    except (OSError, subprocess.SubprocessError):
        return False
    with _ssh_master_kunci_induk:
        if soket in _ssh_master_kunci:
            return False  # sedang dibuat
        _ssh_master_kunci[soket] = True

    def buat():
        try:
            SSH_KONTROL.mkdir(mode=0o700, exist_ok=True)
            if os.path.exists(soket):
                os.unlink(soket)  # sisa master yang sudah mati
            subprocess.run([*dasar, '-M', '-N', '-f', '-S', soket, '-o', f'ControlPersist={SSH_PERSIST}', tujuan],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            with _ssh_master_kunci_induk:
                _ssh_master_kunci.pop(soket, None)
    threading.Thread(target=buat, daemon=True).start()
    return False


def perintah_server(srv, key, remote, *opsi):
    if srv['host'] in HOST_LOKAL:
        return ['bash', '-c', remote]
    tujuan = f"{srv['user']}@{srv['host']}"
    # ServerAliveInterval di sini: pada koneksi lewat soket yang berlaku setelan master (scan antivirus bisa 60 mnt)
    dasar = ['ssh', '-i', str(key), '-p', srv['port'], '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
             '-o', 'ServerAliveInterval=30', '-o', 'StrictHostKeyChecking=accept-new']
    soket = str(SSH_KONTROL / f"{srv['user']}@{srv['host']}:{srv['port']}")
    kontrol = ['-o', f'ControlPath={soket}', '-o', 'ControlMaster=no'] if _ssh_master(dasar, tujuan, soket) else []
    return [*dasar[:-2], *opsi, *kontrol, *dasar[-2:], tujuan, remote]


def servers_view():
    pakai = server_usage()
    daftar = [dict(s, index=i, default=(i == 0), domains=pakai.get(str(s.get('host', '')), 0))
              for i, s in enumerate(load_servers()) if isinstance(s, dict)]
    return {'servers': daftar, 'pc': server_pc(), 'store': str(SERVERS_STORE), 'store_pc': str(MONITOR_TAMBAHAN),
            'readonly': bool(os.environ.get('INSTALLER_SERVERS', '').strip())}


def _server_index(servers, payload):
    try:
        i = int(payload.get('index'))
    except (TypeError, ValueError):
        return None
    return i if 0 <= i < len(servers) else None


def server_mutasi(aksi, payload):
    """aksi: simpan | hapus | default. Kembalikan (hasil, galat, kode HTTP)."""
    if os.environ.get('INSTALLER_SERVERS', '').strip():
        return None, 'diatur_lewat_env_INSTALLER_SERVERS', 409
    with _servers_lock:
        servers = [x for x in load_servers() if isinstance(x, dict)]
        if aksi == 'simpan':
            item, err = clean_server(payload)
            if err:
                return None, err, 400
            baru = payload.get('index') in (None, '')
            i = None if baru else _server_index(servers, payload)
            if not baru and i is None:
                return None, 'server_tidak_ditemukan', 404
            if any(str(x.get('host')) == item['host'] for j, x in enumerate(servers) if j != i):
                return None, 'host_sudah_terdaftar', 409
            if i is not None and servers[i].get('host') != item['host']:
                pakai = server_usage().get(str(servers[i].get('host')), 0)
                if pakai and not payload.get('pindah_host'):
                    return None, f'host_dipakai_{pakai}_manifest', 409
            if i is None:
                servers.append(item)
            else:
                servers[i] = item
        else:
            i = _server_index(servers, payload)
            if i is None:
                return None, 'server_tidak_ditemukan', 404
            if aksi == 'hapus':
                pakai = server_usage().get(str(servers[i].get('host')), 0)
                if pakai:
                    return None, f'masih_dipakai_{pakai}_manifest', 409
                if len(servers) == 1:
                    return None, 'server_terakhir', 409
                servers.pop(i)
            elif aksi == 'default':
                servers.insert(0, servers.pop(i))
            else:
                return None, 'aksi_tidak_dikenal', 400
        save_servers(servers)
    return servers_view(), None, 200


def server_test(payload):
    """Coba SSH ke server dengan kunci installer; laporkan hostname & DirectAdmin."""
    if payload.get('pc'):
        srv = next((x for x in server_pc() if x['host'] == payload.get('host')), None)
        err = None if srv else 'server_tidak_ditemukan'
    else:
        servers = [x for x in load_servers() if isinstance(x, dict)]
        i = _server_index(servers, payload)
        if i is None:
            return {'ok': False, 'error': 'server_tidak_ditemukan'}
        srv, err = clean_server(servers[i])
    if err:
        return {'ok': False, 'error': err}
    key = ssh_key_file()
    if not key:
        return {'ok': False, 'error': 'kunci_ssh_installer_tidak_ada'}
    cmd = perintah_server(srv, key, 'hostname; test -d /usr/local/directadmin && echo DA=ya || echo DA=tidak')
    mulai = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20, check=False)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'timeout'}
    ms = int((time.time() - mulai) * 1000)
    baris = (r.stdout or '').strip().splitlines()
    if r.returncode != 0 or not baris:
        pesan = (r.stderr or '').strip().splitlines()
        return {'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200], 'ms': ms}
    return {'ok': True, 'hostname': baris[0][:120], 'directadmin': 'DA=ya' in baris, 'ms': ms}

# Kapasitas disk & pemakaian resource tiap server (GET /api/servers/resource).
# Satu SSH per server secara paralel; CPU dari dua cuplikan /proc/stat berjarak 1 detik.
RESOURCE_TTL = 60
_resource_cache = {'at': 0, 'value': None}
_resource_lock = threading.Lock()
RESOURCE_CMD = r"""echo "H $(hostname)"; echo "N $(nproc)"; echo "L $(cut -d' ' -f1-3 /proc/loadavg)"; echo "U $(cut -d. -f1 /proc/uptime)"
a=$(head -1 /proc/stat); sleep 1; b=$(head -1 /proc/stat); echo "C1 $a"; echo "C2 $b"
grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo | sed 's/^/M /'
df -PB1 -x tmpfs -x devtmpfs -x overlay -x squashfs -x efivarfs -x fuse.sshfs 2>/dev/null | awk 'NR>1{print "D",$6,$2,$3,$4}'"""


def _parse_resource(teks):
    out = {'disks': []}
    mem, cpu = {}, {}
    for baris in teks.splitlines():
        kode, _, isi = baris.partition(' ')
        try:
            if kode == 'H':
                out['hostname'] = isi.strip()[:120]
            elif kode == 'N':
                out['cpu_core'] = int(isi)
            elif kode == 'L':
                out['load'] = [float(x) for x in isi.split()[:3]]
            elif kode == 'U':
                out['uptime'] = int(isi)
            elif kode in ('C1', 'C2'):
                cpu[kode] = [int(x) for x in isi.split()[1:]]
            elif kode == 'M':
                k, v = isi.split(':', 1)
                mem[k.strip()] = int(v.split()[0]) * 1024
            elif kode == 'D':
                mount, total, used, free = isi.rsplit(' ', 3)
                total, used, free = int(total), int(used), int(free)
                if total >= 5 * 1024 ** 3 or mount in ('/', '/home'):
                    out['disks'].append({'mount': mount, 'total': total, 'used': used, 'free': free,
                                         'persen': round(used * 100 / (used + free), 1) if used + free else 0})
        except (ValueError, IndexError):
            continue
    # Dataset ZFS anak (/srv/backup/directadmin/…) berbagi ruang kosong pool induknya → cukup tampilkan induknya
    out['disks'] = [d for d in out['disks'] if not any(
        o is not d and o['free'] == d['free'] and d['mount'].startswith(o['mount'].rstrip('/') + '/') for o in out['disks'])]
    if 'C1' in cpu and 'C2' in cpu:
        d = [b - a for a, b in zip(cpu['C1'], cpu['C2'])]
        total = sum(d)
        idle = d[3] + (d[4] if len(d) > 4 else 0)
        out['cpu'] = round((total - idle) * 100 / total, 1) if total > 0 else 0
    if mem.get('MemTotal'):
        t, a = mem['MemTotal'], mem.get('MemAvailable', 0)
        out['ram'] = {'total': t, 'used': t - a, 'persen': round((t - a) * 100 / t, 1)}
    if mem.get('SwapTotal'):
        t, f = mem['SwapTotal'], mem.get('SwapFree', 0)
        out['swap'] = {'total': t, 'used': t - f, 'persen': round((t - f) * 100 / t, 1)}
    return out


def _resource_satu(srv, key):
    cmd = perintah_server(srv, key, RESOURCE_CMD)
    hasil = {'host': srv['host'], 'name': srv['name'], 'jenis': srv.get('jenis', '')}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=25, check=False)
    except subprocess.TimeoutExpired:
        return {**hasil, 'ok': False, 'error': 'timeout'}
    if r.returncode != 0 or not (r.stdout or '').strip():
        pesan = (r.stderr or '').strip().splitlines()
        return {**hasil, 'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}
    return {**hasil, 'ok': True, **_parse_resource(r.stdout)}


# Hasil terakhir disimpan ke disk: halaman /server langsung tampil (juga sesudah layanan restart);
# data yang sudah lewat TTL dijawab seketika lalu disegarkan di thread latar. ?segar=1 tetap menunggu SSH.
RESOURCE_SIMPAN = Path('/var/lib/velocity/server-resource.json')
_resource_latar = threading.Event()


def _resource_muat_disk():
    try:
        data = json.loads(RESOURCE_SIMPAN.read_text())
        _resource_cache.update(at=float(data.get('diambil') or 0), value=data)
    except (OSError, ValueError):
        pass


def _resource_segar_latar():
    if _resource_latar.is_set():
        return
    _resource_latar.set()

    def kerja():
        try:
            server_resource(paksa=True)
        except Exception:
            pass
        finally:
            _resource_latar.clear()
    threading.Thread(target=kerja, daemon=True).start()


def server_resource(paksa=False):
    if not paksa:
        if _resource_cache['value'] is None:
            _resource_muat_disk()
        nilai = _resource_cache['value']
        if nilai is not None:
            if time.time() - _resource_cache['at'] >= RESOURCE_TTL:
                _resource_segar_latar()
            return nilai
    with _resource_lock:
        now = time.time()
        if not paksa and _resource_cache['value'] and now - _resource_cache['at'] < RESOURCE_TTL:
            return _resource_cache['value']
        key = ssh_key_file()
        if not key:
            return {'error': 'kunci_ssh_installer_tidak_ada'}
        servers = server_dipantau()
        hasil = [None] * len(servers)

        def kerja(i):
            hasil[i] = _resource_satu(servers[i], key)
        utas = [threading.Thread(target=kerja, args=(i,), daemon=True) for i in range(len(servers))]
        for t in utas:
            t.start()
        for t in utas:
            t.join(30)
        data = {'servers': [h or {'host': s['host'], 'name': s['name'], 'jenis': s.get('jenis', ''), 'ok': False, 'error': 'timeout'}
                            for h, s in zip(hasil, servers)],
                'diambil': int(now)}
        _resource_cache.update(at=now, value=data)
        try:
            tmp = RESOURCE_SIMPAN.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, separators=(',', ':')))
            tmp.replace(RESOURCE_SIMPAN)
        except OSError:
            pass
        return data


class CacheLatar:
    """Cache data SSH (monitor/firewall/log). Kedaluwarsa → dijawab seketika dan disegarkan di belakang; lebih tua
    dari UMUR_MAKS ikut bertanda 'menyegarkan' supaya halaman memuat ulang cepat. Hanya paksa / belum ada data → ditunggu."""
    UMUR_MAKS = 900

    def __init__(self):
        self.data = {}
        self.jalan = set()
        self.gen = 0
        self.kunci = threading.Lock()

    def ambil(self, kunci, fn, ttl, paksa=False):
        lama = self.data.get(kunci)
        if lama and not paksa:
            umur = time.time() - lama[0]
            if umur < ttl:
                return lama[1]
            self._latar(kunci, fn)
            if umur < self.UMUR_MAKS or not isinstance(lama[1], dict):
                return lama[1]
            return {**lama[1], 'menyegarkan': True}
        return self._isi(kunci, fn, self.gen)

    def _isi(self, kunci, fn, gen):
        nilai = fn()
        # Hasil yang mulai diambil sebelum hapus() (mis. aksi blokir) tidak disimpan
        if not (isinstance(nilai, dict) and nilai.get('error')) and gen == self.gen:
            self.data[kunci] = (time.time(), nilai)
        return nilai

    def _latar(self, kunci, fn):
        with self.kunci:
            if kunci in self.jalan:
                return
            self.jalan.add(kunci)
        gen = self.gen

        def kerja():
            try:
                self._isi(kunci, fn, gen)
            except Exception:
                pass
            finally:
                self.jalan.discard(kunci)
        threading.Thread(target=kerja, daemon=True).start()

    def hapus(self):
        self.gen += 1
        self.data.clear()


# Monitoring sistem & keamanan tiap server (GET /api/servers/monitor). Kolektor
# scripts/server_monitor_agent.py dikirim lewat stdin `ssh ... python3 -` (hanya baca, tanpa
# memasang apa pun di server); hasil JSON per server, cache 60 dtk.
MONITOR_TTL = 60
MONITOR_AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_monitor_agent.py'
_cache_monitor = CacheLatar()
# Hasil needs-restarting per host {host: (waktu, nilai)}: perintahnya 5–20 dtk, cukup dicek tiap 6 jam
REBOOT_TTL = 6 * 3600
# Disimpan ke disk supaya restart layanan tidak membuat pembacaan pertama menjalankan needs-restarting lagi
REBOOT_BERKAS = Path('/var/lib/velocity/server-monitor/reboot.json')
try:
    _reboot_terakhir = {h: tuple(v) for h, v in json.loads(REBOOT_BERKAS.read_text()).items()}
except (OSError, ValueError, TypeError, AttributeError):
    _reboot_terakhir = {}


def _reboot_simpan():
    try:
        REBOOT_BERKAS.parent.mkdir(parents=True, exist_ok=True)
        tmp = REBOOT_BERKAS.with_suffix('.tmp')
        tmp.write_text(json.dumps(dict(_reboot_terakhir)))
        os.replace(tmp, REBOOT_BERKAS)
    except OSError:
        pass
# PC kantor (PC Lokal = dashboard ini, PC Backup), sengaja di luar servers.json agar tidak ikut jadi
# tujuan installer, CSF, WAF, atau antivirus. Entri = kolom server biasa + 'jenis' ('lokal' | 'backup').
# Server hosting dari servers.json berjenis 'hosting'; jenis jadi tag pembeda di halaman Server.
MONITOR_TAMBAHAN = Path('/var/lib/velocity/servers-monitor.json')
JENIS_PC = ('lokal', 'backup')


def server_pc():
    try:
        tambahan = json.loads(MONITOR_TAMBAHAN.read_text())
    except (OSError, ValueError):
        tambahan = []
    out = []
    for item in tambahan if isinstance(tambahan, list) else []:
        srv, err = clean_server(item)
        if not err:
            srv['jenis'] = str(item.get('jenis') or '')[:20]
            out.append(srv)
    return out


def server_dipantau():
    return [dict(s, jenis='hosting') for s in _daftar_server()] + server_pc()


def _monitor_satu(srv, key, kode):
    cmd = perintah_server(srv, key, 'command -v python3 >/dev/null && exec python3 - || exec /usr/libexec/platform-python -')
    hasil = {'host': srv['host'], 'name': srv['name'], 'jenis': srv.get('jenis', '')}
    mulai = time.time()
    try:
        r = subprocess.run(cmd, input=kode, capture_output=True, text=True, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        return {**hasil, 'ok': False, 'error': 'timeout'}
    hasil['ms'] = int((time.time() - mulai) * 1000)
    try:
        data = json.loads((r.stdout or '').strip().splitlines()[-1])
    except (ValueError, IndexError):
        pesan = (r.stderr or '').strip().splitlines()
        return {**hasil, 'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}
    return {**hasil, 'ok': True, **data}


def server_monitor(paksa=False):
    # SSH ke semua server ±5–10 dtk (needs-restarting disimpan 6 jam); lihat CacheLatar
    return _cache_monitor.ambil('semua', _monitor_ambil, MONITOR_TTL, paksa)


def _monitor_ambil():
    now = time.time()
    key = ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}
    try:
        kode = MONITOR_AGEN.read_text()
    except OSError:
        return {'error': 'kolektor_tidak_ada'}
    servers = server_dipantau()
    hasil = [None] * len(servers)

    def kerja(i):
        host = servers[i]['host']
        simpan = _reboot_terakhir.get(host)
        lewati = simpan and now - simpan[0] < REBOOT_TTL
        h = _monitor_satu(servers[i], key, ('LEWATI_REBOOT = True\n' + kode) if lewati else kode)
        aman = h.get('keamanan') if isinstance(h.get('keamanan'), dict) else None
        if aman is not None and 'perlu_reboot' in aman:
            _reboot_terakhir[host] = (now, aman['perlu_reboot'])
        elif aman is not None and lewati:
            # Server sudah reboot sejak pengecekan terakhir → nilai lama tak berlaku, cek ulang putaran berikutnya
            if ((h.get('sistem') or {}).get('uptime') or 0) < now - simpan[0]:
                _reboot_terakhir.pop(host, None)
                aman['perlu_reboot'] = None
            else:
                aman['perlu_reboot'] = simpan[1]
        hasil[i] = h
    utas = [threading.Thread(target=kerja, args=(i,), daemon=True) for i in range(len(servers))]
    for t in utas:
        t.start()
    for t in utas:
        t.join(65)
    _reboot_simpan()
    data = {'servers': [h or {'host': s['host'], 'name': s['name'], 'jenis': s.get('jenis', ''), 'ok': False, 'error': 'timeout'}
                        for h, s in zip(hasil, servers)],
            'diambil': int(now)}
    return data


# Proteksi: kelola CSF/LFD tiap server dari halaman /server/proteksi. Kode scripts/server_firewall_agent.py
# dikirim lewat stdin `ssh ... python3 -` + satu baris perintah (base64 JSON). Aksi ubah dicatat di
# FIREWALL_RIWAYAT (siapa, kapan, server, hasil). Pengaman IP kantor/server/LAN ada di agen.
FIREWALL_TTL = 60
FIREWALL_AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_firewall_agent.py'
FIREWALL_RIWAYAT = Path('/var/lib/velocity/server-firewall/riwayat.jsonl')
FIREWALL_AKSI_UBAH = ('blokir', 'lepas', 'izinkan', 'cabut_izin', 'atur')
FIREWALL_TTL_BOLEH = (0, 3600, 6 * 3600, 86400, 7 * 86400, 30 * 86400)
FIREWALL_TTL_LOG_PANJANG = 300  # log/WAF 7 hari (WAF semua server ±50 dtk)
_cache_firewall = CacheLatar()
_firewall_tulis = threading.Lock()


def _daftar_server():
    out = []
    for item in load_servers():
        if isinstance(item, dict):
            srv, err = clean_server(item)
            if not err:
                out.append(srv)
    return out


def _server_proteksi():
    """Server hosting (CSF) + PC kantor (firewalld/ufw); agen memilih backend sendiri."""
    return server_dipantau()


def _firewall_satu(srv, key, kode, perintah, batas=60):
    cmd = perintah_server(srv, key, 'command -v python3 >/dev/null && exec python3 - || exec /usr/libexec/platform-python -')
    sandi = base64.b64encode(json.dumps(perintah).encode()).decode()
    hasil = {'host': srv['host'], 'name': srv['name'], 'jenis': srv.get('jenis', '')}
    try:
        r = subprocess.run(cmd, input=f"{kode}\njalankan('{sandi}')\n", capture_output=True, text=True,
                           timeout=batas, check=False)
    except subprocess.TimeoutExpired:
        return {**hasil, 'ok': False, 'error': 'timeout'}
    try:
        data = json.loads((r.stdout or '').strip().splitlines()[-1])
    except (ValueError, IndexError):
        pesan = (r.stderr or '').strip().splitlines()
        return {**hasil, 'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}
    if perintah['aksi'] in ('ringkas', 'cek'):
        return {**hasil, 'ok': True, **data}
    return {**hasil, **data}


def _firewall_semua(servers, perintah, batas=60):
    key = ssh_key_file()
    if not key:
        return None, 'kunci_ssh_installer_tidak_ada'
    try:
        kode = FIREWALL_AGEN.read_text()
    except OSError:
        return None, 'agen_firewall_tidak_ada'
    hasil = [None] * len(servers)

    def kerja(i):
        hasil[i] = _firewall_satu(servers[i], key, kode, perintah, batas)
    utas = [threading.Thread(target=kerja, args=(i,), daemon=True) for i in range(len(servers))]
    for t in utas:
        t.start()
    for t in utas:
        t.join(batas + 5)
    return [h or {'host': s['host'], 'name': s['name'], 'jenis': s.get('jenis', ''), 'ok': False, 'error': 'timeout'}
            for h, s in zip(hasil, servers)], None


def server_firewall(paksa=False):
    def ambil():
        now = time.time()
        hasil, err = _firewall_semua(_server_proteksi(), {'aksi': 'ringkas'})
        if err:
            return {'error': err}
        return {'servers': hasil, 'diambil': int(now)}
    return _cache_firewall.ambil('ringkas', ambil, FIREWALL_TTL, paksa)


def _ip_firewall(teks):
    """IP/CIDR → bentuk baku (alamat tunggal tanpa /32), None bila tidak sah."""
    try:
        net = ipaddress.ip_network((teks or '').strip(), strict=False)
    except ValueError:
        return None
    return str(net.network_address) if net.num_addresses == 1 else str(net)


def firewall_cek(ip):
    ip = _ip_firewall(ip)
    if not ip:
        return {'error': 'ip_tidak_sah'}
    hasil, err = _firewall_semua(_server_proteksi(), {'aksi': 'cek', 'ip': ip})
    return {'error': err} if err else {'ip': ip, 'servers': hasil}


def firewall_aksi(payload):
    aksi = payload.get('aksi')
    if aksi not in FIREWALL_AKSI_UBAH:
        return {'error': 'aksi_tidak_dikenal'}, 400
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    # "Semua server" = server hosting saja; PC kantor (firewalld/ufw) hanya lewat pilihan per server
    target = payload.get('server')
    servers = _daftar_server() if target == 'semua' and aksi != 'atur' else _server_proteksi()
    if target != 'semua' or aksi == 'atur':
        servers = [s for s in servers if s['host'] == target]
        if not servers:
            return {'error': 'server_tidak_dikenal'}, 400
    perintah = {'aksi': aksi, 'oleh': oleh}
    if aksi == 'atur':
        setelan = payload.get('setelan')
        if not isinstance(setelan, dict) or not setelan:
            return {'error': 'setelan_kosong'}, 400
        perintah['setelan'] = {str(k): str(v) for k, v in setelan.items()}
    else:
        ip = _ip_firewall(payload.get('ip'))
        if not ip:
            return {'error': 'ip_tidak_sah'}, 400
        perintah['ip'] = ip
        perintah['ket'] = str(payload.get('ket') or '')[:120]
        if aksi == 'blokir':
            try:
                ttl = int(payload.get('ttl') or 0)
            except (TypeError, ValueError):
                ttl = -1
            if ttl not in FIREWALL_TTL_BOLEH:
                return {'error': 'ttl_tidak_sah'}, 400
            perintah['ttl'] = ttl
    hasil, err = _firewall_semua(servers, perintah, 150 if aksi == 'atur' else 60)
    if err:
        return {'error': err}, 500
    now = int(time.time())
    baris = [json.dumps({'t': now, 'oleh': oleh, 'aksi': aksi, 'ip': perintah.get('ip'), 'ket': perintah.get('ket'),
                         'ttl': perintah.get('ttl'), 'setelan': perintah.get('setelan'), 'server': h['name'],
                         'host': h['host'], 'ok': bool(h.get('ok')), 'error': h.get('error')},
                        separators=(',', ':')) for h in hasil]
    with _firewall_tulis:
        FIREWALL_RIWAYAT.parent.mkdir(parents=True, exist_ok=True)
        with FIREWALL_RIWAYAT.open('a') as f:
            f.write('\n'.join(baris) + '\n')
    _cache_firewall.hapus()  # ringkasan & log berikutnya diambil ulang (ditunggu, bukan data lama)
    return {'aksi': aksi, 'servers': hasil}, 200


def firewall_log(host, hari, jenis='log'):
    """Log firewall (jenis 'log' = lfd) atau WAF ('waf' = ModSecurity) satu server (host) atau semua; cache 60 dtk."""
    try:
        hari = max(1, min(14, int(hari)))
    except (TypeError, ValueError):
        hari = 1
    servers = _daftar_server() if host == 'semua' else [s for s in _server_proteksi() if s['host'] == host]
    if host != 'semua':
        if not servers:
            return {'error': 'server_tidak_dikenal'}

    def ambil():
        hasil, err = _firewall_semua(servers, {'aksi': jenis, 'hari': hari, 'maks': (1500 if host != 'semua' else 400) if jenis == 'log' else (3000 if host != 'semua' else 250)}, 120)
        if err:
            return {'error': err}
        return {'hari': hari, 'servers': hasil, 'diambil': int(time.time())}
    return _cache_firewall.ambil((jenis, host, hari), ambil, FIREWALL_TTL if hari == 1 else FIREWALL_TTL_LOG_PANJANG)


def firewall_riwayat(batas=300):
    try:
        baris = FIREWALL_RIWAYAT.read_text().splitlines()[-batas:]
    except OSError:
        return {'riwayat': []}
    out = []
    for b in reversed(baris):
        try:
            out.append(json.loads(b))
        except ValueError:
            continue
    return {'riwayat': out}


# Antivirus: halaman /server/antivirus. Kode scripts/server_antivirus_agent.py dikirim lewat stdin seperti
# firewall. Ringkas = deteksi cPGuard 30 hari + akun + karantina (cache CacheLatar). Scan berjalan di thread
# latar (SSH bisa puluhan menit), kemajuan dari baris `P {json}`, hasil di ANTIVIRUS_DIR/scan/<id>.json.
# Malware hanya dilaporkan; karantina/kembalikan/hapus manual dari dashboard dan dicatat di riwayat.
ANTIVIRUS_AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_antivirus_agent.py'
ANTIVIRUS_DIR = Path('/var/lib/velocity/server-antivirus')
ANTIVIRUS_RIWAYAT = ANTIVIRUS_DIR / 'riwayat.jsonl'
# Berkas yang ditandai aman (buatan sendiri/false positive): {host: {path: {sha256, mtime, ukuran, oleh, waktu}}}.
# Terikat sha256 — berkas yang isinya berubah terdeteksi lagi.
ANTIVIRUS_AMAN = ANTIVIRUS_DIR / 'aman.json'
ANTIVIRUS_TTL = 120
ANTIVIRUS_HARI = (0, 1, 3, 7, 30)
ANTIVIRUS_BATAS_SCAN = 3600  # detik; agen berhenti sendiri (terpotong 'waktu_habis') sebelum SSH diputus
# Scan otomatis per server (aktif lewat halaman Antivirus): harian = berkas berubah 24 jam, mingguan = semua berkas
# semua akun. Hari Minggu hanya mingguan. Virus → Telegram tim server (env pengawas-server).
ANTIVIRUS_JADWAL = ANTIVIRUS_DIR / 'jadwal.json'  # {host: {harian, mingguan, terakhir: {harian, mingguan}}}
ANTIVIRUS_JAM_JADWAL = (1, 30)  # WIB
ANTIVIRUS_BATAS_MINGGUAN = 8 * 3600
ANTIVIRUS_TG = Path('/etc/velocity/secrets/pengawas-server.env')
_cache_antivirus = CacheLatar()
_scan_jalan = {}  # id → data job (termasuk kemajuan) selama berjalan
_scan_kunci = threading.Lock()
_antivirus_tulis = threading.Lock()


def _antivirus_ssh(srv, key, perintah, prioritas_rendah=False):
    sandi = base64.b64encode(json.dumps(perintah).encode()).decode()
    py = 'nice -n 15 ionice -c3 python3 -' if prioritas_rendah else 'python3 -'
    cmd = perintah_server(srv, key, f'command -v python3 >/dev/null && exec {py} || exec /usr/libexec/platform-python -')
    return cmd, f"{ANTIVIRUS_AGEN.read_text()}\njalankan('{sandi}')\n"


def _antivirus_satu(srv, key, perintah, batas=90, prioritas_rendah=False):
    hasil = {'host': srv['host'], 'name': srv['name']}
    try:
        cmd, masukan = _antivirus_ssh(srv, key, perintah, prioritas_rendah)
        r = subprocess.run(cmd, input=masukan, capture_output=True, text=True, timeout=batas, check=False)
    except subprocess.TimeoutExpired:
        return {**hasil, 'ok': False, 'error': 'timeout'}
    except OSError:
        return {**hasil, 'ok': False, 'error': 'agen_antivirus_tidak_ada'}
    try:
        data = json.loads((r.stdout or '').strip().splitlines()[-1])
    except (ValueError, IndexError):
        pesan = (r.stderr or '').strip().splitlines()
        return {**hasil, 'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}
    return {**hasil, **data}


def server_antivirus(paksa=False):
    def ambil():
        key = ssh_key_file()
        if not key:
            return {'error': 'kunci_ssh_installer_tidak_ada'}
        servers = _daftar_server()
        hasil = [None] * len(servers)

        def kerja(i):
            hasil[i] = _antivirus_satu(servers[i], key, {'aksi': 'ringkas'})
        utas = [threading.Thread(target=kerja, args=(i,), daemon=True) for i in range(len(servers))]
        for t in utas:
            t.start()
        for t in utas:
            t.join(95)
        return {'servers': [h or {'host': s['host'], 'name': s['name'], 'ok': False, 'error': 'timeout'}
                            for h, s in zip(hasil, servers)], 'diambil': int(time.time())}
    return _cache_antivirus.ambil('ringkas', ambil, ANTIVIRUS_TTL, paksa)


def _aman_baca():
    try:
        return json.loads(ANTIVIRUS_AMAN.read_text())
    except (OSError, ValueError):
        return {}


# Setelan per server (tab Scan & Karantina): mode karantina otomatis watcher realtime + whitelist berkas/folder.
# Whitelist berlaku di watcher, scan (agen melewatinya), periksa ulang, dan tampilan (temuan lama jadi "aman").
ANTIVIRUS_RT_SETELAN = ANTIVIRUS_DIR / 'realtime-setelan.json'  # {host: {mode, putih: [{path, jenis, oleh, t, alasan}]}}
ANTIVIRUS_FP = ANTIVIRUS_DIR / 'laporan-fp.jsonl'


def _rt_setelan_baca():
    try:
        return json.loads(ANTIVIRUS_RT_SETELAN.read_text())
    except (OSError, ValueError):
        return {}


def _rt_setelan(host, semua=None):
    s = (semua if semua is not None else _rt_setelan_baca()).get(host) or {}
    return {'mode': s.get('mode') if s.get('mode') in ('laporan', 'otomatis') else 'laporan', 'putih': list(s.get('putih') or [])}


def _putih_server(host):
    return [{'path': w['path'], 'jenis': w.get('jenis') or 'berkas'} for w in _rt_setelan(host)['putih']]


def _rt_isi(host):
    """Isi setelan.json untuk watcher (urutan tetap → sha sama dengan detak.setelan)."""
    st = _rt_setelan(host)
    isi = json.dumps({'mode': st['mode'], 'putih': _putih_server(host)}, sort_keys=True, separators=(',', ':'))
    return isi, hashlib.sha256(isi.encode()).hexdigest()[:12]


def _cocok_putih(path, putih):
    for w in putih:
        x = w.get('path') or ''
        if x and (path == x or (w.get('jenis') == 'folder' and path.startswith(x.rstrip('/') + '/'))):
            return w
    return None


def _cocok_aman(t, e):
    # Hasil scan lama belum menyimpan sha256 → pakai mtime + ukuran saat ditandai
    if t.get('sha256'):
        return t['sha256'] == e.get('sha256')
    return t.get('mtime') == e.get('mtime') and t.get('ukuran') == e.get('ukuran')


def _aman_sesudah(job, t, e):
    # Halaman/baris DB tidak punya sha tetap: ditandai aman sesudah scan ini selesai = temuan scan lama sudah ditangani.
    # Scan sesudah tanda aman tetap dicocokkan per sha256, jadi infeksi ulang tetap terlihat.
    return bool((t.get('web') or t.get('db')) and (e.get('waktu') or 0) > (job.get('selesai') or job.get('mulai') or 0))


def _fp_sha(aman):
    """sha256 berkas yang dilaporkan positif palsu (entri aman beralasan "positif palsu: …") di server mana pun.
    Berkas kembar (isi persis sama) di akun/server lain ikut aman; batal aman di berkas asal mencabutnya."""
    out = {}
    for host, daftar in aman.items():
        for path, e in daftar.items():
            if e.get('sha256') and str(e.get('alasan') or '').startswith('positif palsu'):
                out.setdefault(e['sha256'], dict(e, kembar=path, kembar_host=host, alasan=f"positif palsu, isi sama dengan {path}"))
    return out


def _temuan_aman(job, aman):
    daftar = aman.get(job.get('host'), {})
    fp = _fp_sha(aman)
    putih = _rt_setelan(job.get('host'))['putih']
    hitam = _hitam_baca()
    nilai_ai = server_judi.analisis_baca().get(job.get('host')) or {}
    out = []
    for t in job.get('temuan') or []:
        w = _cocok_putih(t.get('path') or '', putih) if putih else None
        if w:
            t = dict(t, aman={'oleh': w.get('oleh'), 'waktu': w.get('t'), 'alasan': f"whitelist {w.get('jenis')}", 'putih': w['path']})
        elif t.get('path') in daftar and (_cocok_aman(t, daftar[t['path']]) or _aman_sesudah(job, t, daftar[t['path']])):
            t = dict(t, aman=daftar[t['path']])
        elif t.get('sha256') in fp:
            t = dict(t, aman=fp[t['sha256']])
        elif t.get('sha256') in hitam:
            t = dict(t, hitam=hitam[t['sha256']])
        n = nilai_ai.get(t.get('path'))
        if n and n.get('sha256') == t.get('sha256'):  # saran Analisis AI untuk isi yang sama
            t = dict(t, ai=n)
        out.append(t)
    return out


# Ingat karantina: sha256 berkas yang pernah dikarantina manual (atau lewat Bersihkan WP), berlaku semua server.
# Berkas berisi persis sama muncul lagi di scan/realtime → dikarantina otomatis; berkas penting (inti WP, index.php,
# wp-config.php, .htaccess, temuan DB/beranda) hanya diberi label `hitam`. Kembalikan, laporan positif palsu dan
# tandai aman mengeluarkan sha dari daftar.
ANTIVIRUS_HITAM = ANTIVIRUS_DIR / 'hitam.json'  # {sha256: {tanda, path, server, host, oleh, t}}
HITAM_OLEH = 'Otomatis ingat karantina'


def _hitam_baca():
    try:
        return json.loads(ANTIVIRUS_HITAM.read_text())
    except (OSError, ValueError):
        return {}


def _hitam_ubah(tambah=None, buang=()):
    """tambah {sha256: info}, buang [sha256]. Jangan dipanggil sambil memegang _antivirus_tulis."""
    tambah = {k: v for k, v in (tambah or {}).items() if k}
    buang = [k for k in buang if k]
    if not tambah and not buang:
        return
    with _antivirus_tulis:
        data = _hitam_baca()
        data.update(tambah)
        for k in buang:
            data.pop(k, None)
        ANTIVIRUS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = ANTIVIRUS_HITAM.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, separators=(',', ':')))
        tmp.replace(ANTIVIRUS_HITAM)


def _hitam_info(srv, path, oleh, tanda):
    return {'tanda': str(tanda or '')[:200], 'path': path, 'server': srv['name'], 'host': srv['host'], 'oleh': oleh, 't': int(time.time())}


def _hitam_penting(path):
    return '#' in path or '/wp-admin/' in path or '/wp-includes/' in path or path.rsplit('/', 1)[-1] in ('index.php', 'wp-config.php', '.htaccess')


def _hitam_terapkan(srv, key, temuan, sumber):
    """Karantina otomatis temuan (hasil _temuan_aman) yang isinya sama dengan karantina sebelumnya.
    Mengembalikan set path yang berhasil dikarantina; notif Telegram + insiden bila path yang sama terinfeksi lagi."""
    ditindak = []
    for t in temuan:
        h = t.get('hitam')
        if not h or t.get('aman') or (t.get('karantina') or {}).get('ok') or _hitam_penting(t.get('path') or ''):
            continue
        alasan = (f"isi sama dengan karantina {time.strftime('%d-%m-%Y', time.localtime(h.get('t') or 0))} "
                  f"oleh {h.get('oleh')}: {h.get('tanda') or '-'}")[:200]
        r = _antivirus_satu(srv, key, {'aksi': 'karantina', 'path': t['path'], 'sha256': t['sha256'], 'oleh': HITAM_OLEH,
                                       'alasan': alasan}, 60)
        with _antivirus_tulis, ANTIVIRUS_RIWAYAT.open('a') as f:
            f.write(json.dumps({'t': int(time.time()), 'oleh': HITAM_OLEH, 'aksi': 'karantina', 'server': srv['name'], 'host': srv['host'],
                                'path': t['path'], 'id': r.get('id'), 'alasan': f'{sumber} · {alasan}'[:300], 'ok': bool(r.get('ok')),
                                'error': r.get('error')}, separators=(',', ':')) + '\n')
        if r.get('ok'):
            ditindak.append((t, h))
    if not ditindak:
        return set()
    _cache_antivirus.hapus()
    baris = []
    for t, h in ditindak[:10]:
        asal = 'infeksi ulang path sama' if h.get('path') == t['path'] else f"asal {h.get('server')}: {(h.get('path') or '').replace('/home/', '', 1)}"
        baris.append(f"• <code>{html.escape(t['path'].replace('/home/', '', 1))}</code> — {html.escape(asal)}")
    if len(ditindak) > 10:
        baris.append(f'… dan {len(ditindak) - 10} lagi')
    ulang = sorted({t['path'].split('/')[2] for t, h in ditindak if h.get('path') == t['path']})
    for akun in ulang:
        try:
            berkas = [t['path'] for t, h in ditindak if t['path'].split('/')[2] == akun]
            velocityguard.insiden_simpan({
                'id': 'ulang-' + hashlib.sha1(f"{srv['host']}:{akun}".encode()).hexdigest()[:8], 'oleh': HITAM_OLEH,
                'tanggal': time.strftime('%Y-%m-%d'), 'status': 'terbuka', 'server': srv['name'],
                'judul': f"Infeksi ulang akun {akun} ({srv['name']})",
                'penyebab': 'Berkas yang sudah dikarantina muncul lagi di path yang sama: ' + ', '.join(berkas[:20]),
                'perbaikan': 'Dikarantina otomatis (ingat karantina). Celah belum ditutup: cek plugin/tema rentan (CMS), '
                             'admin siluman (Bersihkan WP), sandi FTP/cPanel, cron.'})
        except Exception as e:
            print(f'insiden infeksi ulang: {e}', file=sys.stderr)
    teks = [f"🔁 <b>VelocityGuard · Ingat karantina {html.escape(srv['name'])}</b> ({html.escape(sumber)})",
            f"{len(ditindak)} berkas dikarantina otomatis — isinya sama dengan berkas yang pernah dikarantina.", ''] + baris
    if ulang:
        teks += ['', f"⚠️ Path sama terinfeksi lagi ({html.escape(', '.join(ulang))}) → celah belum ditutup, tercatat di Celah & Insiden."]
    teks += ['', f"https://dash.velocity.ai.id/server/antivirus?s={urllib.parse.quote(srv['name'])}&tab=karantina"]
    try:
        kirim_telegram_server('\n'.join(teks))
    except Exception as e:
        print(f'telegram ingat karantina: {e}', file=sys.stderr)
    return {t['path'] for t, h in ditindak}


# Periksa ulang: berkas temuan lama dibaca lagi di server (agen aksi periksa_ulang, hanya baca) dengan VD.* saat ini.
# Temuan yang kini bersih (aturan diperbaiki / berkas dibersihkan) atau berkasnya hilang diberi `kini` dan tidak
# dihitung/ditampilkan lagi di "Semua scan". Diulang bila sidik agen berubah, ada path baru, atau tiap ULANG_SELANG.
ANTIVIRUS_ULANG = ANTIVIRUS_DIR / 'ulang.json'  # {host: {sidik, t, hasil: {path: {ada, tanda, sha256, t}}}}
ULANG_SELANG = 24 * 3600  # sekali sehari (scan harian membawa temuan baru → dicek saat itu juga); cepat = tombol Cek ulang per akun
# Daftar "dilewati karena besar" scan lama diperiksa ulang dengan aturan agen sekarang (checksum inti WP, baca awal+akhir).
# Terpisah dari ulang.json: berkas besar dibaca penuh untuk md5/sha256 → job lama, prioritas rendah.
ANTIVIRUS_BESAR_ULANG = ANTIVIRUS_DIR / 'besar-ulang.json'  # {host: {sidik, t, hasil: {path: {ada, inti?, tanda, t}}}}


def _ulang_baca():
    try:
        return json.loads(ANTIVIRUS_ULANG.read_text())
    except (OSError, ValueError):
        return {}


_bersih_cache = [None, {}]


def _dibersihkan():
    """Bersihkan WP sukses dari riwayat: {(host, akar): [(t, {id admin dihapus} | None)]} (None = riwayat lama tanpa daftar id)."""
    try:
        mtime = ANTIVIRUS_RIWAYAT.stat().st_mtime
    except OSError:
        return {}
    if _bersih_cache[0] != mtime:
        data = {}
        for b in ANTIVIRUS_RIWAYAT.read_text().splitlines():
            try:
                r = json.loads(b)
            except ValueError:
                continue
            if r.get('aksi') == 'bersihkan_wp' and r.get('ok'):
                ids = r.get('hapus_user')
                ids = None if ids is None else ids + (r.get('turun_user') or [])  # diturunkan = bukan admin lagi
                data.setdefault((r.get('host'), r.get('path')), []).append((r.get('t') or 0, None if ids is None else {str(x) for x in ids}))
        _bersih_cache[:] = [mtime, data]
    return _bersih_cache[1]


def _besar_ulang_baca():
    try:
        return json.loads(ANTIVIRUS_BESAR_ULANG.read_text())
    except (OSError, ValueError):
        return {}


def _besar_kini(job, besar_ulang):
    """Buang dari daftar besar berkas yang sesudah scan ini dinilai ulang hilang atau inti WP asli.
    Yang bersih dibaca awal+akhir tetap tampil dengan tag `sebagian: 'bersih'` (dicek manual), yang bertanda membawa `tanda`."""
    hasil = (besar_ulang.get(job.get('host')) or {}).get('hasil') or {}
    waktu = job.get('selesai') or job.get('mulai') or 0
    sisa = []
    for b in job.get('besar') or []:
        r = hasil.get(b.get('path'))
        if r and r.get('t', 0) > waktu:
            if not r.get('ada') or r.get('inti'):
                continue
            if r.get('tanda'):
                b = dict(b, tanda=r['tanda'])
            elif r.get('tanda') == []:
                b = dict(b, sebagian='bersih')
        sisa.append(b)
    buang = len(job.get('besar') or []) - len(sisa)
    if buang and isinstance(job.get('hasil'), dict):
        job['hasil'] = dict(job['hasil'], besar=max((job['hasil'].get('besar') or 0) - buang, len(sisa)))
    job['besar'] = sisa
    return job


def _temuan_admin(t):
    return bool(t.get('db')) and any(x['id'].startswith('VD.DB.Admin') for x in t.get('tanda') or [])


def _temuan_kini(job, temuan, ulang):
    hasil = (ulang.get(job.get('host')) or {}).get('hasil') or {}
    waktu = job.get('selesai') or job.get('mulai') or 0
    bersih = _dibersihkan()
    out = []
    for t in temuan:
        r = hasil.get(t.get('path'))
        if _temuan_admin(t):
            # Admin siluman yang sudah dihapus lewat Bersihkan WP sesudah scan ini → ditangani
            if any(w > waktu and (ids is None or str(t['db'].get('id')) in ids)
                   for w, ids in bersih.get((job.get('host'), t['path'].split('#')[0]), ())):
                t = dict(t, kini='dibersihkan')
            # Ditangani manual: periksa ulang dapati wp-config.php hilang / user bukan admin lagi
            elif r and r.get('t', 0) > waktu and not r.get('ada'):
                t = dict(t, kini='admin_hilang')
        elif r and not t.get('db') and not t.get('web') and r.get('t', 0) > waktu:
            if not r.get('ada'):
                t = dict(t, kini='hilang')
            elif r.get('tanda') == []:
                t = dict(t, kini='bersih')
        out.append(t)
    return out


def _scan_yatim():
    """Saat layanan start: job berstatus 'berjalan' di berkas = sisa proses lama yang mati (restart di tengah scan).
    Ditulis permanen sebagai gagal/terputus — tampilan sudah begitu, tapi pembaca berkas mentah masih melihat 'berjalan'."""
    for b in (ANTIVIRUS_DIR / 'scan').glob('*.json'):
        try:
            job = json.loads(b.read_text())
        except (OSError, ValueError):
            continue
        if job.get('status') == 'berjalan' and b.stem not in _scan_jalan:
            job.update(status='gagal', error='terputus', selesai=job.get('selesai') or int(b.stat().st_mtime))
            job.pop('pid', None)
            _scan_simpan(job)


def _sidik_agen():
    return hashlib.sha256(ANTIVIRUS_AGEN.read_bytes()).hexdigest()[:12]


def _ulang_paths():
    """{host: set(path)} temuan semua scan selesai yang bisa diperiksa ulang (berkas + admin siluman DB)."""
    per_host = {}
    for j in antivirus_scan_daftar()['scan']:
        # Jangan saring pakai jumlah_temuan: angka itu sudah dikurangi hasil periksa ulang ("kini hilang/bersih"),
        # jadi scan yang temuannya semua hilang keluar dari daftar → status hilangnya lenyap → muncul lagi.
        if j.get('status') != 'selesai':
            continue
        try:
            job = json.loads((ANTIVIRUS_DIR / 'scan' / f"{j['id']}.json").read_text())
        except (OSError, ValueError):
            continue
        per_host.setdefault(j['host'], set()).update(
            t['path'] for t in job.get('temuan') or []
            if (not t.get('db') and not t.get('web') and '#' not in t['path']) or _temuan_admin(t))
    return per_host


def antivirus_cek_ulang(payload):
    """Tombol Cek ulang per akun: periksa ulang temuan satu akun sekarang (hanya baca), gabung ke ulang.json."""
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    akun = str(payload.get('akun') or '')
    if not re.fullmatch(r'[a-z0-9_.-]{1,40}', akun):
        return {'error': 'akun_tidak_sah'}, 400
    paths = sorted(p for p in _ulang_paths().get(srv['host']) or () if p.startswith(f'/home/{akun}/'))
    if not paths:
        return {'ok': True, 'diperiksa': 0}, 200
    r = _antivirus_satu(srv, ssh_key_file(), {'aksi': 'periksa_ulang', 'paths': paths[:3000], 'putih': _putih_server(srv['host'])}, 180)
    if not r.get('ok'):
        return {'error': r.get('error') or 'agen_gagal'}, 502
    sekarang = int(time.time())
    with _antivirus_tulis:
        ulang = _ulang_baca()
        ulang.setdefault(srv['host'], {}).setdefault('hasil', {}).update(
            {p: dict(v, t=sekarang) for p, v in (r.get('hasil') or {}).items()})
        tmp = ANTIVIRUS_ULANG.with_suffix('.tmp')
        tmp.write_text(json.dumps(ulang, separators=(',', ':')))
        tmp.replace(ANTIVIRUS_ULANG)
    return {'ok': True, 'diperiksa': len(paths)}, 200


def _ulang_jalan():
    while True:
        try:
            key = ssh_key_file()
            sidik = _sidik_agen()
            ulang = _ulang_baca()
            per_host = _ulang_paths()
            for srv in _daftar_server() if key else []:
                paths = sorted(per_host.get(srv['host']) or ())
                u = ulang.get(srv['host']) or {}
                sidik = _sidik_agen() + _rt_isi(srv['host'])[1]  # whitelist berubah → periksa ulang juga
                lama = u.get('hasil') or {}
                if not paths or (u.get('sidik') == sidik and time.time() - (u.get('t') or 0) < ULANG_SELANG
                                 and all(x in lama for x in paths)):
                    continue
                r = _antivirus_satu(srv, key, {'aksi': 'periksa_ulang', 'paths': paths[:3000], 'putih': _putih_server(srv['host'])}, 180)
                if not r.get('ok'):
                    continue
                sekarang = int(time.time())
                ulang[srv['host']] = {'sidik': sidik, 't': sekarang,
                                      'hasil': {p: dict(v, t=sekarang) for p, v in (r.get('hasil') or {}).items()}}
                with _antivirus_tulis:
                    tmp = ANTIVIRUS_ULANG.with_suffix('.tmp')
                    tmp.write_text(json.dumps(ulang, separators=(',', ':')))
                    tmp.replace(ANTIVIRUS_ULANG)
            _besar_ulang(key)
        except Exception as e:
            print(f'antivirus periksa ulang: {e}', file=sys.stderr)
        time.sleep(600)


# Hash berkas besar yang sudah dicek manual asli (plugin premium tanpa API checksum, mis. bb-plugin vendor-bb-forms.js).
# Berlaku semua server; berkas dengan sha256 + ukuran persis sama tidak masuk daftar "Dilewati karena besar".
ANTIVIRUS_HASH_ASLI = ANTIVIRUS_DIR / 'hash-asli.json'  # {sha256: {ukuran, contoh, catatan, oleh, t}}


def _hash_asli():
    try:
        return {k: v['ukuran'] for k, v in json.loads(ANTIVIRUS_HASH_ASLI.read_text()).items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _besar_ulang(key):
    if not key:
        return
    asli = _hash_asli()
    # Daftar putih hash berubah → daftar besar dinilai ulang juga
    sidik = _sidik_agen() + hashlib.sha256(json.dumps(asli, sort_keys=True).encode()).hexdigest()[:8]
    data = _besar_ulang_baca()
    per_host = {}
    for j in antivirus_scan_daftar()['scan']:
        if j.get('status') != 'selesai':
            continue
        try:
            job = json.loads((ANTIVIRUS_DIR / 'scan' / f"{j['id']}.json").read_text())
        except (OSError, ValueError):
            continue
        per_host.setdefault(j['host'], set()).update(b['path'] for b in job.get('besar') or [] if b.get('path'))
    for srv in _daftar_server():
        paths = sorted(per_host.get(srv['host']) or ())
        u = data.get(srv['host']) or {}
        lama = u.get('hasil') or {}
        # Berkas besar jarang berubah: ulang hanya bila agen berubah atau ada path baru
        if not paths or (u.get('sidik') == sidik and all(x in lama for x in paths)):
            continue
        r = _antivirus_satu(srv, key, {'aksi': 'periksa_ulang', 'paths': paths[:3000], 'putih': _putih_server(srv['host']),
                                       'asli': asli}, 1800, prioritas_rendah=True)
        if not r.get('ok'):
            print(f"antivirus periksa ulang besar {srv['name']}: {r.get('error')}", file=sys.stderr)
            continue
        sekarang = int(time.time())
        data[srv['host']] = {'sidik': sidik, 't': sekarang,
                             'hasil': {p: dict(v, t=sekarang) for p, v in (r.get('hasil') or {}).items()}}
        with _antivirus_tulis:
            tmp = ANTIVIRUS_BESAR_ULANG.with_suffix('.tmp')
            tmp.write_text(json.dumps(data, separators=(',', ':')))
            tmp.replace(ANTIVIRUS_BESAR_ULANG)


def _scan_ringkas(job, aman=None, ulang=None):
    """Job tanpa daftar temuan (untuk daftar scan); temuan yang ditandai aman / kini bersih tidak dihitung."""
    out = {k: v for k, v in job.items() if k not in ('temuan', 'besar')}
    t = [x for x in _temuan_kini(job, _temuan_aman(job, _aman_baca() if aman is None else aman), _ulang_baca() if ulang is None else ulang)
         if not x.get('aman') and not x.get('kini')]
    out['jumlah_temuan'] = len(t)
    out['jumlah_virus'] = sum(1 for x in t if x.get('tingkat') == 'virus')
    return out


def _scan_simpan(job):
    folder = ANTIVIRUS_DIR / 'scan'
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f".{job['id']}.tmp"
    tmp.write_text(json.dumps(job, separators=(',', ':')))
    tmp.replace(folder / f"{job['id']}.json")


def _scan_kerja(job, srv, key):
    batas_job = job.get('batas') or ANTIVIRUS_BATAS_SCAN
    perintah = {'aksi': 'scan', 'akun': job['akun'], 'hari': job['hari'], 'batas': batas_job - 120, 'penuh': job.get('jadwal') == 'mingguan' or bool(job.get('penuh')),
                'aman': {p: e['sha256'] for p, e in _aman_baca().get(srv['host'], {}).items()},
                # Watcher realtime hidup → berkas sudah diperiksa saat ditulis; harian cukup DB & beranda
                'berkas': not (job.get('jadwal') == 'harian' and realtime_aktif(srv['host'])),
                'putih': _putih_server(srv['host']), 'asli': _hash_asli()}
    if not perintah['berkas']:
        job['ringan'] = True
    akhir = None
    try:
        cmd, masukan = _antivirus_ssh(srv, key, perintah, prioritas_rendah=True)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        job['pid'] = proc.pid
        proc.stdin.write(masukan)
        proc.stdin.close()
        pengawas = threading.Timer(batas_job, proc.kill)
        pengawas.start()
        for baris in proc.stdout:
            if baris.startswith('P '):
                try:
                    job['kemajuan'] = json.loads(baris[2:])
                except ValueError:
                    pass
            elif baris.strip():
                akhir = baris
        proc.wait()
        pengawas.cancel()
        galat = (proc.stderr.read() or '').strip().splitlines()
    except OSError as e:
        galat = [str(e)]
    job.pop('pid', None)
    job['selesai'] = int(time.time())
    try:
        data = json.loads(akhir or '')
    except ValueError:
        data = {'ok': False, 'error': 'dihentikan' if job.get('dihentikan') else (galat[-1][:200] if galat else 'tanpa_hasil')}
    if data.get('ok'):
        job.update(status='selesai', temuan=data.pop('temuan', []), besar=data.pop('daftar_besar', []), hasil=data)
    else:
        job.update(status='gagal', error=data.get('error') or 'gagal', pesan=data.get('pesan'))
    _scan_simpan(job)
    with _scan_kunci:
        _scan_jalan.pop(job['id'], None)
    ditindak = set()
    if job['status'] == 'selesai':
        try:
            ditindak = _hitam_terapkan(srv, key, _temuan_aman(job, _aman_baca()), f"scan {job.get('jadwal') or 'oleh ' + str(job.get('oleh'))}")
        except Exception as e:
            print(f'ingat karantina: {e}', file=sys.stderr)
    if job.get('jadwal'):
        try:
            _antivirus_notif(job, ditindak)
        except Exception as e:  # notifikasi gagal tak boleh mengganggu hasil scan
            print(f'antivirus notif gagal: {e}', file=sys.stderr)
        if job['status'] == 'selesai' and server_judi.setelan_server(srv['host'])['aktif']:
            server_judi.proses({**job, 'temuan': _temuan_aman(job, _aman_baca())}, srv)


def _scan_mulai(srv, key, akun, hari, oleh, jadwal=None, penuh=False):
    with _scan_kunci:
        if any(j['host'] == srv['host'] for j in _scan_jalan.values()):
            return None
        job = {'id': time.strftime('%Y%m%d-%H%M%S-') + pysecrets.token_hex(3), 'host': srv['host'], 'server': srv['name'],
               'akun': akun, 'hari': hari, 'oleh': oleh, 'mulai': int(time.time()), 'status': 'berjalan', 'kemajuan': None}
        if jadwal:
            job.update(jadwal=jadwal, batas=ANTIVIRUS_BATAS_MINGGUAN if jadwal == 'mingguan' else ANTIVIRUS_BATAS_SCAN)
        elif penuh:  # full scan manual semua akun semua berkas: batas sama dengan mingguan
            job.update(penuh=True, batas=ANTIVIRUS_BATAS_MINGGUAN)
        _scan_jalan[job['id']] = job
    _scan_simpan(job)  # tercatat walau layanan di-restart di tengah scan (tampil 'terputus')
    threading.Thread(target=_scan_kerja, args=(job, srv, key), daemon=True).start()
    return job


def _antivirus_jadwal_baca():
    try:
        return json.loads(ANTIVIRUS_JADWAL.read_text())
    except (OSError, ValueError):
        return {}


def _antivirus_jadwal_tulis(data):
    ANTIVIRUS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ANTIVIRUS_JADWAL.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(ANTIVIRUS_JADWAL)


def antivirus_jadwal_atur(payload):
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    with _antivirus_tulis:
        data = _antivirus_jadwal_baca()
        j = data.setdefault(srv['host'], {})
        for k in ('harian', 'mingguan'):
            if k in payload:
                j[k] = bool(payload[k])
        _antivirus_jadwal_tulis(data)
        with ANTIVIRUS_RIWAYAT.open('a') as f:
            f.write(json.dumps({'t': int(time.time()), 'oleh': oleh, 'aksi': 'jadwal', 'server': srv['name'], 'host': srv['host'],
                                'alasan': f"harian {'aktif' if j.get('harian') else 'mati'}, mingguan {'aktif' if j.get('mingguan') else 'mati'}",
                                'ok': True}, separators=(',', ':')) + '\n')
    return {'ok': True, 'jadwal': data}, 200


def _antivirus_jadwal_jalan():
    """Dicek tiap menit: sesudah jam jadwal, mulai scan yang belum jalan hari/minggu ini (server sibuk → coba lagi)."""
    while True:
        try:
            kini = time.localtime()
            if (kini.tm_hour, kini.tm_min) >= ANTIVIRUS_JAM_JADWAL:
                jenis = 'mingguan' if kini.tm_wday == 6 else 'harian'
                tanda = time.strftime('%Y-%m-%d', kini)
                data = _antivirus_jadwal_baca()
                key = ssh_key_file()
                for srv in _daftar_server():
                    j = data.get(srv['host']) or {}
                    # Minggu tanpa mingguan aktif → tetap jalankan harian
                    pakai = jenis if j.get(jenis) else ('harian' if jenis == 'mingguan' and j.get('harian') else None)
                    # penuh_sekali = "YYYY-MM-DD": full scan sekali di jam jadwal hari itu, menggantikan harian
                    if j.get('penuh_sekali') == tanda:
                        pakai = 'mingguan'
                    if not pakai or not key or (j.get('terakhir') or {}).get(pakai) == tanda:
                        continue
                    job = _scan_mulai(srv, key, 'semua', 0 if pakai == 'mingguan' else 1, f'Jadwal {pakai}', pakai)
                    if job:
                        with _antivirus_tulis:
                            data = _antivirus_jadwal_baca()
                            data.setdefault(srv['host'], {}).setdefault('terakhir', {})[pakai] = tanda
                            if data[srv['host']].pop('penuh_sekali', None) == tanda:
                                data[srv['host']]['terakhir']['harian'] = tanda
                            _antivirus_jadwal_tulis(data)
        except Exception as e:
            print(f'jadwal antivirus: {e}', file=sys.stderr)
        time.sleep(60)


def kirim_telegram_server(teks):
    """Kirim ke tim server (bot & daftar chat pemantau server); dipakai antivirus & CMS terjadwal."""
    env = dict(b.split('=', 1) for b in ANTIVIRUS_TG.read_text().splitlines() if '=' in b and not b.startswith('#'))
    # Fungsi ini hanya dipakai VelocityGuard (antivirus, CMS, Judi AI, celah, positif palsu) → penerima khususnya ikut;
    # program lain yang memakai berkas env sama (kasus support, pengawas server/IP LAN) hanya TELEGRAM_CHAT_ID
    chat_id = env.get('TELEGRAM_CHAT_ID', '') + ',' + env.get('TELEGRAM_CHAT_ID_VELOCITYGUARD', '')
    for chat in dict.fromkeys(c.strip() for c in chat_id.split(',') if c.strip()):
        data = urllib.parse.urlencode({'chat_id': chat, 'text': teks, 'parse_mode': 'HTML', 'disable_web_page_preview': 'true'}).encode()
        try:
            urllib.request.urlopen(f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}/sendMessage", data, timeout=20).read()
        except OSError as e:
            print(f'telegram server {chat}: {e}', file=sys.stderr)


def _antivirus_notif(job, lewati=()):
    # lewati = path yang sudah dikarantina otomatis (ingat karantina, dikabarkan pesan sendiri)
    temuan = [t for t in _temuan_aman(job, _aman_baca()) if not t.get('aman') and t.get('path') not in lewati]
    virus = [t for t in temuan if t.get('tingkat') == 'virus']
    nama = f"scan {job['jadwal']}"
    if job.get('status') != 'selesai':
        teks = f"⚠️ <b>VelocityGuard · Antivirus {html.escape(job['server'])}</b>: {nama} gagal ({html.escape(str(job.get('error')))})."
    elif virus:
        teks = '\n'.join([f"🦠 <b>VelocityGuard · Virus di {html.escape(job['server'])}</b> ({nama})",
                          f"{len(virus)} virus, {len(temuan) - len(virus)} curiga",
                          '', f"https://dash.velocity.ai.id/server/antivirus?s={urllib.parse.quote(job['server'])}",
                          'Belum ada berkas yang diubah — karantina manual dari dashboard.'])
    else:
        return
    kirim_telegram_server(teks)


# Realtime: watcher fanotify di server (scripts/velocity_av_realtime.py, dipasang velocity-av-realtime-pasang).
# Tiap REALTIME_SELANG temuan baru ditarik lewat agen aksi `realtime` → job "Realtime" per server per hari
# (id <tgl>-000000-<sha1 host>, ikut daftar scan & "Semua scan"), virus → Telegram tim server.
ANTIVIRUS_REALTIME = ANTIVIRUS_DIR / 'realtime.json'  # {host: {aktif, detak, offset, diambil, galat}}
REALTIME_SELANG = 120
REALTIME_CEK_MATI = 600  # server tanpa watcher dicek tiap 10 mnt (terlihat tak lama sesudah dipasang)
REALTIME_BASI = 900  # detak lebih tua → dianggap mati, scan harian kembali memeriksa berkas


def _realtime_baca():
    try:
        return json.loads(ANTIVIRUS_REALTIME.read_text())
    except (OSError, ValueError):
        return {}


def realtime_aktif(host):
    r = _realtime_baca().get(host) or {}
    return r.get('aktif') == 'active' and time.time() - ((r.get('detak') or {}).get('t') or 0) < REALTIME_BASI


def _realtime_job(srv, temuan):
    sid = f"{time.strftime('%Y%m%d')}-000000-{hashlib.sha1(srv['host'].encode()).hexdigest()[:6]}"
    try:
        job = json.loads((ANTIVIRUS_DIR / 'scan' / f'{sid}.json').read_text())
    except (OSError, ValueError):
        job = {'id': sid, 'host': srv['host'], 'server': srv['name'], 'akun': 'realtime', 'hari': 0, 'oleh': 'Realtime',
               'status': 'selesai', 'temuan': [], 'besar': [], 'hasil': {'ok': True, 'akun': 'realtime', 'hari': 0}}
    indeks = {t['path']: i for i, t in enumerate(job['temuan'])}
    for t in temuan:
        if t['path'] in indeks:
            job['temuan'][indeks[t['path']]] = t
        else:
            indeks[t['path']] = len(job['temuan'])
            job['temuan'].append(t)
    # mulai = event terakhir: karantina sesudahnya menyembunyikan temuan di "Semua scan", infeksi ulang muncul lagi
    job['mulai'] = job['selesai'] = max([job.get('selesai') or 0] + [t.get('t') or 0 for t in temuan])
    _scan_simpan(job)


def _rt_dorong(srv, key, sha_server=None):
    """Kirim setelan.json ke watcher bila isinya beda dengan yang dipakai server (dibaca watcher tiap 60 dtk)."""
    isi, sha = _rt_isi(srv['host'])
    if sha_server == sha:
        return {'ok': True, 'sama': True}
    return _antivirus_satu(srv, key, {'aksi': 'realtime_setelan', 'isi': isi}, 60)


def antivirus_realtime_atur(payload):
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    mode = payload.get('mode')
    if mode not in ('laporan', 'otomatis'):
        return {'error': 'mode_tidak_sah'}, 400
    with _antivirus_tulis:
        data = _rt_setelan_baca()
        data.setdefault(srv['host'], {})['mode'] = mode
        _rt_setelan_tulis(data)
        with ANTIVIRUS_RIWAYAT.open('a') as f:
            f.write(json.dumps({'t': int(time.time()), 'oleh': oleh, 'aksi': 'realtime_mode', 'server': srv['name'],
                                'host': srv['host'], 'alasan': f'karantina otomatis {mode}', 'ok': True}, separators=(',', ':')) + '\n')
    key = ssh_key_file()
    r = _rt_dorong(srv, key) if key and realtime_aktif(srv['host']) else {'ok': True}
    return {'ok': True, 'setelan': _rt_setelan(srv['host']), 'terkirim': bool(r.get('ok'))}, 200


def _rt_setelan_tulis(data):
    ANTIVIRUS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = ANTIVIRUS_RT_SETELAN.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, separators=(',', ':')))
    tmp.replace(ANTIVIRUS_RT_SETELAN)


def _realtime_sinkron():
    while True:
        try:
            key = ssh_key_file()
            data = _realtime_baca()
            for srv in _daftar_server() if key else []:
                st = data.setdefault(srv['host'], {})
                sekarang = time.time()
                if st.get('aktif') != 'active' and sekarang - (st.get('diambil') or 0) < REALTIME_CEK_MATI:
                    continue
                r = _antivirus_satu(srv, key, {'aksi': 'realtime', 'offset': st.get('offset') or 0}, 60)
                st['diambil'] = int(sekarang)
                if not r.get('ok'):
                    st['galat'] = r.get('error')
                    continue
                st.update(aktif=r.get('aktif'), detak=r.get('detak'), offset=r.get('offset') or 0, galat=None)
                if r.get('aktif') == 'active':
                    _rt_dorong(srv, key, (r.get('detak') or {}).get('setelan'))
                baru = [t for t in r.get('temuan') or [] if not t.get('path', '').startswith('/home/velocity-av-uji/')]
                if not baru:
                    continue
                _realtime_job(srv, baru)
                ditindak = set()
                try:
                    ditindak = _hitam_terapkan(srv, key, _temuan_aman({'host': srv['host'], 'temuan': baru}, _aman_baca()), 'realtime')
                except Exception as e:
                    print(f'ingat karantina realtime: {e}', file=sys.stderr)
                try:
                    otomatis = [t for t in baru if (t.get('karantina') or {}).get('ok')]
                    _antivirus_notif({'host': srv['host'], 'server': srv['name'], 'status': 'selesai', 'temuan': baru,
                                      'jadwal': f'realtime · {len(otomatis)} dikarantina otomatis' if otomatis else 'realtime'}, ditindak)
                except Exception as e:
                    print(f'antivirus realtime notif: {e}', file=sys.stderr)
            with _antivirus_tulis:
                ANTIVIRUS_DIR.mkdir(parents=True, exist_ok=True)
                tmp = ANTIVIRUS_REALTIME.with_suffix('.tmp')
                tmp.write_text(json.dumps(data, separators=(',', ':')))
                tmp.replace(ANTIVIRUS_REALTIME)
        except Exception as e:
            print(f'antivirus realtime: {e}', file=sys.stderr)
        time.sleep(REALTIME_SELANG)


def antivirus_scan_mulai(payload):
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    akun = str(payload.get('akun') or 'semua')
    if akun != 'semua' and not re.fullmatch(r'[a-z0-9_][a-z0-9_.-]{0,31}', akun):
        return {'error': 'akun_tidak_dikenal'}, 400
    try:
        hari = int(payload.get('hari') or 0)
    except (TypeError, ValueError):
        hari = -1
    penuh = payload.get('penuh') is True and akun == 'semua'
    if penuh:
        hari = 0
    if hari not in ANTIVIRUS_HARI or (akun == 'semua' and hari == 0 and not penuh):
        return {'error': 'hari_tidak_sah'}, 400
    key = ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}, 500
    job = _scan_mulai(srv, key, akun, hari, oleh, penuh=penuh)
    if not job:
        return {'error': 'scan_sedang_jalan'}, 409
    return _scan_ringkas(job), 200


def antivirus_scan_henti(payload):
    with _scan_kunci:
        job = _scan_jalan.get(str(payload.get('id') or ''))
    if not job or not job.get('pid'):
        return {'error': 'scan_tidak_jalan'}, 404
    job['dihentikan'] = True
    try:
        os.kill(job['pid'], signal.SIGTERM)  # ssh putus → agen di server ikut berhenti (SIGPIPE/SIGHUP)
    except OSError:
        pass
    return {'ok': True}, 200


def antivirus_scan_daftar(batas=60):
    out = []
    aman = _aman_baca()
    ulang = _ulang_baca()
    try:
        berkas = sorted((ANTIVIRUS_DIR / 'scan').glob('*.json'), reverse=True)[:batas]
    except OSError:
        berkas = []
    for b in berkas:
        jalan = _scan_jalan.get(b.stem)
        try:
            job = jalan or json.loads(b.read_text())
        except (OSError, ValueError):
            continue
        if job.get('status') == 'berjalan' and not jalan:
            job = {**job, 'status': 'gagal', 'error': 'terputus'}
        out.append(_scan_ringkas(job, aman, ulang))
    return {'scan': out}


def antivirus_scan_detail(sid):
    if not re.fullmatch(r'\d{8}-\d{6}-[0-9a-f]{6}', sid or ''):
        return {'error': 'scan_tidak_ada'}
    if sid in _scan_jalan:
        return _scan_jalan[sid]
    try:
        job = json.loads((ANTIVIRUS_DIR / 'scan' / f'{sid}.json').read_text())
    except (OSError, ValueError):
        return {'error': 'scan_tidak_ada'}
    job['temuan'] = _temuan_kini(job, _temuan_aman(job, _aman_baca()), _ulang_baca())
    _besar_kini(job, _besar_ulang_baca())
    return {**job, 'status': 'gagal', 'error': 'terputus'} if job.get('status') == 'berjalan' else job


def antivirus_scan_gabung(host):
    """Temuan semua scan selesai satu server jadi satu job (path sama → scan terbaru), tanpa berkas yang
    dikarantina sesudah scan penemunya. Dipakai Judi AI "nilai semua yang belum ditangani"."""
    srv_av = next((s for s in (server_antivirus().get('servers') or []) if s.get('host') == host), {})
    dikarantina = {k.get('path'): k.get('waktu') or 0 for k in srv_av.get('karantina') or []}
    temuan, n = {}, 0
    for j in antivirus_scan_daftar()['scan']:  # terbaru dulu
        if j.get('host') != host or j.get('status') != 'selesai':
            continue
        d = antivirus_scan_detail(j['id'])
        n += 1
        for t in d.get('temuan') or []:
            if t.get('path') not in temuan and not t.get('kini') and not dikarantina.get(t.get('path'), 0) > d.get('mulai', 0):
                temuan[t['path']] = t
    if not n:
        return {'error': 'scan_tidak_ada'}
    return {'id': 'semua', 'host': host, 'status': 'selesai', 'gabung': n, 'temuan': list(temuan.values())}


def antivirus_aksi(payload):
    aksi = payload.get('aksi')
    if aksi not in ('karantina', 'kembalikan', 'hapus', 'aman', 'batal_aman', 'putih', 'batal_putih', 'laporan_fp', 'bersihkan_wp', 'lupakan'):
        return {'error': 'aksi_tidak_dikenal'}, 400
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    key = ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}, 500
    perintah = {'aksi': aksi, 'oleh': oleh}
    if aksi == 'lupakan':  # keluarkan satu sha dari daftar ingat karantina (tanpa SSH)
        sha = str(payload.get('sha256') or '')
        h = _hitam_baca().get(sha)
        if not h:
            return {'ok': False, 'error': 'bukan_hitam'}, 200
        _hitam_ubah(buang=[sha])
        with _antivirus_tulis, ANTIVIRUS_RIWAYAT.open('a') as f:
            f.write(json.dumps({'t': int(time.time()), 'oleh': oleh, 'aksi': 'lupakan', 'server': h.get('server'), 'host': h.get('host'),
                                'path': h.get('path'), 'alasan': f"sha256 {sha[:12]}… {str(payload.get('alasan') or '')[:150]}".strip(),
                                'ok': True}, separators=(',', ':')) + '\n')
        return {'ok': True, 'path': h.get('path')}, 200
    if aksi in ('putih', 'batal_putih', 'laporan_fp'):
        return _antivirus_putih_fp(srv, key, aksi, payload, oleh)
    if aksi in ('aman', 'batal_aman'):
        perintah['path'] = str(payload.get('path') or '')
        perintah['alasan'] = str(payload.get('alasan') or '')[:200]
        hasil = _antivirus_tandai(srv, key, aksi, perintah['path'], oleh, perintah['alasan'], str(payload.get('sha256') or ''))
    elif aksi == 'karantina':
        perintah['path'] = str(payload.get('path') or '')
        perintah['alasan'] = str(payload.get('alasan') or '')[:200]
    elif aksi == 'bersihkan_wp':
        hapus_user = payload.get('hapus_user') or []
        turunkan_user = payload.get('turunkan_user') or []
        if not all(isinstance(d, list) and len(d) <= 50 and all(str(x).isdigit() for x in d) for d in (hapus_user, turunkan_user)):
            return {'error': 'id_user_tidak_sah'}, 400
        perintah.update(akar=str(payload.get('akar') or ''), hapus_user=[int(x) for x in hapus_user],
                        turunkan_user=[int(x) for x in turunkan_user],
                        plugin=bool(payload.get('plugin')), salt=bool(payload.get('salt')))
        perintah['path'] = perintah['akar']
    else:
        perintah['id'] = str(payload.get('id') or '')
    if aksi not in ('aman', 'batal_aman'):
        # mysqldump users/usermeta bisa lama di situs besar
        hasil = _antivirus_satu(srv, key, perintah, 360 if aksi == 'bersihkan_wp' else 60)
    if hasil.get('ok') and aksi == 'karantina':
        _hitam_ubah({hasil.get('sha256'): _hitam_info(srv, hasil.get('path') or perintah['path'], oleh, perintah['alasan'])})
    elif hasil.get('ok') and aksi == 'kembalikan':
        _hitam_ubah(buang=[hasil.get('sha256')])
    elif aksi == 'bersihkan_wp':
        _hitam_ubah({k.get('sha256'): _hitam_info(srv, k['path'], oleh, 'Bersihkan WP: ' + ', '.join(k.get('tanda') or []))
                     for k in hasil.get('karantina') or [] if k.get('ok')})
    if aksi == 'bersihkan_wp':
        perintah['alasan'] = (f"hapus {len(hasil.get('hapus_user') or [])} admin, jadi subscriber {len(hasil.get('turun_user') or [])}, karantina {len(hasil.get('karantina') or [])} berkas, "
                              f"salt {hasil.get('salt') or 0}/8 · cadangan {hasil.get('cadangan') or '-'}")
    with _antivirus_tulis:
        ANTIVIRUS_DIR.mkdir(parents=True, exist_ok=True)
        with ANTIVIRUS_RIWAYAT.open('a') as f:
            f.write(json.dumps({'t': int(time.time()), 'oleh': oleh, 'aksi': aksi, 'server': srv['name'], 'host': srv['host'],
                                'path': hasil.get('path') or perintah.get('path'), 'id': hasil.get('id') or perintah.get('id'),
                                'alasan': perintah.get('alasan'), 'ok': bool(hasil.get('ok')), 'error': hasil.get('error'),
                                **({'hapus_user': [u.get('id') for u in hasil.get('hapus_user') or []],
                                    'turun_user': [u.get('id') for u in hasil.get('turun_user') or []]} if aksi == 'bersihkan_wp' and hasil.get('ok') else {})},
                               separators=(',', ':')) + '\n')
    _cache_antivirus.hapus()
    return hasil, 200


def _antivirus_putih_fp(srv, key, aksi, payload, oleh):
    """putih: whitelist berkas/folder (+ kembalikan dari karantina bila `id`); batal_putih; laporan_fp: catat laporan
    positif palsu (Telegram tim server) + kembalikan + tandai aman (terikat isi berkas)."""
    path = str(payload.get('path') or '')
    kid = str(payload.get('id') or '')
    alasan = str(payload.get('alasan') or '')[:300]
    hasil = {'ok': True, 'path': path}
    if aksi == 'putih':
        jenis = 'folder' if payload.get('jenis') == 'folder' else 'berkas'
        if jenis == 'folder':
            path = path.rstrip('/')
        bagian = path.split('/')
        # Folder minimal /home/<akun>/domains/<domain>/<sesuatu> — tidak boleh seluruh akun/domain
        if not path.startswith('/home/') or '..' in bagian or len(bagian) < (7 if jenis == 'folder' else 6) or bagian[3] != 'domains':
            return {'ok': False, 'error': 'path_tidak_sah'}, 200
        if kid:
            hasil = _antivirus_satu(srv, key, {'aksi': 'kembalikan', 'id': kid, 'oleh': oleh}, 60)
            if not hasil.get('ok'):
                return hasil, 200
            _hitam_ubah(buang=[hasil.get('sha256')])
        with _antivirus_tulis:
            data = _rt_setelan_baca()
            st = data.setdefault(srv['host'], {})
            st['putih'] = [w for w in st.get('putih') or [] if w['path'] != path] + [
                {'path': path, 'jenis': jenis, 'oleh': oleh, 't': int(time.time()), 'alasan': alasan}]
            _rt_setelan_tulis(data)
    elif aksi == 'batal_putih':
        with _antivirus_tulis:
            data = _rt_setelan_baca()
            st = data.setdefault(srv['host'], {})
            sisa = [w for w in st.get('putih') or [] if w['path'] != path]
            if len(sisa) == len(st.get('putih') or []):
                return {'ok': False, 'error': 'bukan_putih'}, 200
            st['putih'] = sisa
            _rt_setelan_tulis(data)
    else:  # laporan_fp
        r = _antivirus_satu(srv, key, {'aksi': 'baca', 'id': kid}, 60) if kid else {}
        meta = {'path': r.get('path') or path, 'sha256': r.get('sha256') or payload.get('sha256'), 'alasan_deteksi': payload.get('tanda') or ''}
        if kid:
            hasil = _antivirus_satu(srv, key, {'aksi': 'kembalikan', 'id': kid, 'oleh': oleh}, 60)
            if not hasil.get('ok'):
                return hasil, 200
            path = hasil.get('path') or meta['path']
        _hitam_ubah(buang=[meta['sha256'], hasil.get('sha256')])
        tandai = _antivirus_tandai(srv, key, 'aman', path, oleh, f'positif palsu: {alasan}'[:200], str(payload.get('sha256') or ''))
        with _antivirus_tulis, ANTIVIRUS_FP.open('a') as f:
            f.write(json.dumps({'t': int(time.time()), 'host': srv['host'], 'server': srv['name'], 'oleh': oleh,
                                'catatan': alasan, **meta}, separators=(',', ':')) + '\n')
        try:
            kirim_telegram_server(f"🟡 <b>VelocityGuard · Laporan positif palsu {html.escape(srv['name'])}</b> oleh {html.escape(oleh)}\n"
                                  f"<code>{html.escape(path.replace('/home/', '', 1))}</code>\nAturan: {html.escape(str(meta['alasan_deteksi']))}\n"
                                  f"Catatan: {html.escape(alasan or '-')}\nBerkas dikembalikan & ditandai aman — perbaiki aturan VD.*.")
        except Exception as e:
            print(f'telegram fp: {e}', file=sys.stderr)
        hasil = {'ok': bool(tandai.get('ok')), 'path': path, 'error': tandai.get('error')}
    with _antivirus_tulis:
        with ANTIVIRUS_RIWAYAT.open('a') as f:
            f.write(json.dumps({'t': int(time.time()), 'oleh': oleh, 'aksi': aksi, 'server': srv['name'], 'host': srv['host'],
                                'path': path, 'id': kid or None, 'alasan': alasan or (payload.get('jenis') if aksi == 'putih' else None),
                                'ok': bool(hasil.get('ok')), 'error': hasil.get('error')}, separators=(',', ':')) + '\n')
    if aksi != 'laporan_fp' and realtime_aktif(srv['host']):
        threading.Thread(target=_rt_dorong, args=(srv, key), daemon=True).start()
    _cache_antivirus.hapus()
    return hasil, 200


def _antivirus_tandai(srv, key, aksi, path, oleh, alasan, sha_db=''):
    """Tandai/batalkan aman. sha256 diambil langsung dari server saat ditandai (isi yang dicek user).
    Temuan database (`<akar>#db:<tabel>:<id>`) tak bisa dibaca agen → sha256 dari temuan scan (sha isi entri)."""
    if aksi == 'aman' and '#db:' in path:
        if not re.fullmatch(r'[0-9a-f]{64}', sha_db or ''):
            return {'ok': False, 'error': 'sha_tidak_sah', 'path': path}
        r = {'path': path}
        entri = {'sha256': sha_db, 'mtime': None, 'ukuran': None, 'oleh': oleh, 'waktu': int(time.time()), 'alasan': alasan}
    elif aksi == 'aman':
        r = _antivirus_satu(srv, key, {'aksi': 'baca', 'path': path}, 60)
        if not r.get('ok'):
            return {'ok': False, 'error': r.get('error') or 'gagal', 'path': path}
        entri = {'sha256': r['sha256'], 'mtime': r['mtime'], 'ukuran': r['ukuran'], 'oleh': oleh, 'waktu': int(time.time()), 'alasan': alasan}
    with _antivirus_tulis:
        aman = _aman_baca()
        daftar = aman.setdefault(srv['host'], {})
        if aksi == 'aman':
            daftar[r['path']] = entri
        elif not daftar.pop(path, None):
            return {'ok': False, 'error': 'bukan_aman', 'path': path}
        ANTIVIRUS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = ANTIVIRUS_AMAN.with_suffix('.tmp')
        tmp.write_text(json.dumps(aman, separators=(',', ':')))
        tmp.replace(ANTIVIRUS_AMAN)
    if aksi == 'aman':
        _hitam_ubah(buang=[entri['sha256']])
    return {'ok': True, 'path': path}


def antivirus_baca(server, path, kid):
    """Isi berkas temuan/karantina untuk dilihat (baca saja, tidak dicatat di riwayat)."""
    srv = next((s for s in _daftar_server() if s['host'] == server), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}
    key = ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}
    return _antivirus_satu(srv, key, {'aksi': 'baca', 'id': kid} if kid else {'aksi': 'baca', 'path': path}, 60)


def antivirus_riwayat(batas=300):
    try:
        baris = ANTIVIRUS_RIWAYAT.read_text().splitlines()[-batas:]
    except OSError:
        return {'riwayat': []}
    out = []
    for b in reversed(baris):
        try:
            out.append(json.loads(b))
        except ValueError:
            continue
    return {'riwayat': out}


# WAF: halaman /server/waf — status Velocity WAF (ruleset ModSecurity pengganti cPGuard) per server hosting,
# pasang/ganti mode/perbarui/copot, setelan rakit bersama, dan riwayat. Logika server ada di scripts/velocity_waf.py
# (sama dengan CLI velocity-waf-pasang). Pasang/copot me-restart LiteSpeed (±20–60 dtk) → dijalankan di thread latar
# sebagai job, satu job per server; hasil dicatat di WAF_RIWAYAT.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import velocity_waf  # noqa: E402

WAF_DIR = Path('/var/lib/velocity/server-waf')
WAF_RIWAYAT = WAF_DIR / 'riwayat.jsonl'
WAF_TTL = 120
_cache_waf = CacheLatar()
_waf_job = {}  # id → job (berjalan & selesai sejak layanan start)
_waf_kunci = threading.Lock()


def _waf_catat(baris):
    WAF_DIR.mkdir(parents=True, exist_ok=True)
    with _waf_kunci, WAF_RIWAYAT.open('a') as f:
        f.write(json.dumps(baris, separators=(',', ':'), ensure_ascii=False) + '\n')


def _waf_lokal():
    s = velocity_waf.baca_setelan()
    return {'versi': velocity_waf.versi_lokal(), 'sidik': velocity_waf.sidik_lokal(setelan=s), 'setelan': s}


def server_waf(paksa=False):
    def ambil():
        key = ssh_key_file()
        if not key:
            return {'error': 'kunci_ssh_installer_tidak_ada'}
        servers = _daftar_server()
        hasil = [None] * len(servers)

        def kerja(i):
            hasil[i] = {'host': servers[i]['host'], 'name': servers[i]['name'],
                        **velocity_waf.jalankan(servers[i], key, {'aksi': 'status'}, 40)}
        utas = [threading.Thread(target=kerja, args=(i,), daemon=True) for i in range(len(servers))]
        for t in utas:
            t.start()
        for t in utas:
            t.join(45)
        return {'servers': [h or {'host': s['host'], 'name': s['name'], 'ok': False, 'error': 'timeout'}
                            for h, s in zip(hasil, servers)], 'diambil': int(time.time())}
    data = _cache_waf.ambil('status', ambil, WAF_TTL, paksa)
    if isinstance(data, dict) and not data.get('error'):
        data = {**data, 'lokal': _waf_lokal(), 'job': [j for j in _waf_job.values() if j['status'] == 'berjalan']}
    return data


def _waf_kerja(job, srv, key, perintah):
    hasil = velocity_waf.jalankan(srv, key, perintah, 400)
    job.update(status='selesai' if hasil.get('ok') else 'gagal', selesai=int(time.time()), hasil=hasil)
    _waf_catat({'t': job['selesai'], 'oleh': job['oleh'], 'aksi': job['aksi'], 'mode': job.get('mode'), 'server': srv['name'],
                'host': srv['host'], 'sidik': job.get('sidik'), 'ok': bool(hasil.get('ok')), 'error': hasil.get('error'),
                'alasan': hasil.get('alasan'), 'peringatan': hasil.get('peringatan'), 'domain': hasil.get('domain'),
                'http': [hasil.get('http_sebelum'), hasil.get('http_sesudah'), hasil.get('http_uji_sqlmap')]})
    _cache_waf.hapus()


def waf_aksi(payload):
    aksi = payload.get('aksi')
    if aksi not in ('pasang', 'copot'):
        return {'error': 'aksi_tidak_dikenal'}, 400
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    mode = payload.get('mode')
    if aksi == 'pasang' and mode not in ('deteksi', 'blokir'):
        return {'error': 'mode_tidak_sah'}, 400
    key = ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}, 500
    perintah = {'aksi': aksi, 'mode': mode}
    job = {'id': time.strftime('%Y%m%d-%H%M%S-') + pysecrets.token_hex(3), 'host': srv['host'], 'server': srv['name'],
           'aksi': aksi, 'mode': mode, 'oleh': oleh, 'mulai': int(time.time()), 'status': 'berjalan'}
    if aksi == 'pasang':
        try:
            perintah['berkas'], job['versi'], job['sidik'] = velocity_waf.rakit_berkas(mode)
        except (OSError, SystemExit) as e:
            return {'error': f'rakit_gagal: {e}'[:200]}, 500
    with _waf_kunci:
        if any(j['host'] == srv['host'] and j['status'] == 'berjalan' for j in _waf_job.values()):
            return {'error': 'aksi_sedang_jalan'}, 409
        _waf_job[job['id']] = job
    threading.Thread(target=_waf_kerja, args=(job, srv, key, perintah), daemon=True).start()
    return job, 200


def waf_job(jid):
    return _waf_job.get(jid or '') or {'error': 'job_tidak_ada'}


def waf_setelan(payload):
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    try:
        baru = velocity_waf.bersihkan_setelan(payload.get('setelan'))
    except ValueError as e:
        return {'error': str(e)}, 400
    lama = velocity_waf.baca_setelan()
    velocity_waf.simpan_setelan(baru)
    ubah = {k: baru[k] for k in baru if baru[k] != lama.get(k)}
    if 'ip_putih' in ubah:
        ubah['ip_putih'] = [x['ip'] for x in baru['ip_putih']]
    _waf_catat({'t': int(time.time()), 'oleh': oleh, 'aksi': 'setelan', 'setelan': ubah, 'ok': True})
    return _waf_lokal(), 200


def waf_riwayat(batas=300):
    try:
        baris = WAF_RIWAYAT.read_text().splitlines()[-batas:]
    except OSError:
        return {'riwayat': []}
    out = []
    for b in reversed(baris):
        try:
            out.append(json.loads(b))
        except ValueError:
            continue
    return {'riwayat': out}


# Brute Force: halaman /server/bruteforce — pengganti BFM cPGuard. Blok aturan LFD (regex.custom.pm) yang memblokir IP
# berulang kali ditolak Velocity WAF; setelan ambang/durasi bersama semua server. Agen scripts/server_bfm_agent.py.
# Pasang/copot (csf -r + restart lfd) = job thread latar seperti WAF; dicatat di BFM_DIR/riwayat.jsonl.
BFM_AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_bfm_agent.py'
BFM_DIR = Path('/var/lib/velocity/server-bfm')
BFM_RIWAYAT = BFM_DIR / 'riwayat.jsonl'
BFM_SETELAN = BFM_DIR / 'setelan.json'
BFM_TTL = 300
BFM_ATURAN = {  # kunci → (label, ambang bawaan, durasi bawaan detik [1 = permanen], aktif bawaan)
    'berat': ('Eksploit berat (.env, wp-config, dump, traversal, xmlrpc multicall)', 3, 1, True),
    'eksploit': ('Eksploit & probe', 5, 86400, True),
    'bot': ('Scanner / bot jahat', 10, 86400, True),
    'crawler': ('Crawler SEO', 30, 21600, False),  # kunci lama dipertahankan agar setelan.json tetap berlaku
    'ai': ('Crawler AI', 30, 21600, False),
    'pencarian': ('Bot AI pencarian', 30, 21600, False),
    'login': ('Brute force wp-login / xmlrpc', 20, 3600, True),
}
BFM_DURASI = (1800, 3600, 6 * 3600, 86400, 3 * 86400, 7 * 86400, 1)  # 1 = permanen (format regex.custom.pm CSF)
_cache_bfm = CacheLatar()
_bfm_job = {}
_bfm_kunci = threading.Lock()


def bfm_setelan_baca():
    try:
        data = json.loads(BFM_SETELAN.read_text())
    except (OSError, ValueError):
        data = {}
    out = {}
    for k, (_, ambang, durasi, aktif) in BFM_ATURAN.items():
        a = data.get(k) if isinstance(data.get(k), dict) else {}
        out[k] = {'aktif': bool(a.get('aktif', aktif)), 'ambang': int(a.get('ambang', ambang)), 'durasi': int(a.get('durasi', durasi))}
    return out


def _bfm_sidik(aturan):
    # Kode agen ikut di-hash: blok Perl berubah (mis. pengecualian judi 77007) → server tampil "perlu diperbarui"
    return hashlib.sha1((json.dumps(aturan, sort_keys=True) + BFM_AGEN.read_text()).encode()).hexdigest()[:10]


def _bfm_satu(srv, key, perintah, batas=120, agen=BFM_AGEN):
    cmd = perintah_server(srv, key, 'command -v python3 >/dev/null && exec python3 - || exec /usr/libexec/platform-python -')
    sandi = base64.b64encode(json.dumps(perintah).encode()).decode()
    hasil = {'host': srv['host'], 'name': srv['name']}
    try:
        r = subprocess.run(cmd, input=f"{agen.read_text()}\njalankan('{sandi}')\n", capture_output=True, text=True,
                           timeout=batas, check=False)
    except subprocess.TimeoutExpired:
        return {**hasil, 'ok': False, 'error': 'timeout'}
    try:
        return {**hasil, **json.loads((r.stdout or '').strip().splitlines()[-1])}
    except (ValueError, IndexError):
        pesan = (r.stderr or '').strip().splitlines()
        return {**hasil, 'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:200]}


def _bfm_lokal():
    aturan = bfm_setelan_baca()
    return {'aturan': aturan, 'sidik': _bfm_sidik(aturan),
            'label': {k: v[0] for k, v in BFM_ATURAN.items()}, 'durasi_boleh': BFM_DURASI}


def server_bfm(paksa=False):
    def ambil():
        key = ssh_key_file()
        if not key:
            return {'error': 'kunci_ssh_installer_tidak_ada'}
        servers = _daftar_server()
        aturan = bfm_setelan_baca()
        hasil = [None] * len(servers)

        def kerja(i):
            hasil[i] = _bfm_satu(servers[i], key, {'aksi': 'status', 'aturan': aturan}, 150)
        utas = [threading.Thread(target=kerja, args=(i,), daemon=True) for i in range(len(servers))]
        for t in utas:
            t.start()
        for t in utas:
            t.join(155)
        return {'servers': [h or {'host': s['host'], 'name': s['name'], 'ok': False, 'error': 'timeout'}
                            for h, s in zip(hasil, servers)], 'diambil': int(time.time()), 'sidik_simulasi': _bfm_sidik(aturan)}
    data = _cache_bfm.ambil('status', ambil, BFM_TTL, paksa)
    if isinstance(data, dict) and not data.get('error'):
        data = {**data, 'lokal': _bfm_lokal(), 'job': [j for j in _bfm_job.values() if j['status'] == 'berjalan']}
    return data


def _bfm_catat(baris):
    BFM_DIR.mkdir(parents=True, exist_ok=True)
    with _bfm_kunci, BFM_RIWAYAT.open('a') as f:
        f.write(json.dumps(baris, separators=(',', ':'), ensure_ascii=False) + '\n')


def _bfm_kerja(job, srv, key, perintah):
    hasil = _bfm_satu(srv, key, perintah, 420)
    job.update(status='selesai' if hasil.get('ok') else 'gagal', selesai=int(time.time()), hasil=hasil)
    _bfm_catat({'t': job['selesai'], 'oleh': job['oleh'], 'aksi': job['aksi'], 'server': srv['name'], 'host': srv['host'],
                'sidik': job.get('sidik'), 'ok': bool(hasil.get('ok')), 'error': hasil.get('error'),
                'galat': (hasil.get('hasil') or {}).get('galat')})
    _cache_bfm.hapus()


def bfm_aksi(payload):
    aksi = payload.get('aksi')
    if aksi not in ('pasang', 'copot'):
        return {'error': 'aksi_tidak_dikenal'}, 400
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    key = ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}, 500
    aturan = bfm_setelan_baca()
    perintah = {'aksi': aksi, 'aturan': aturan, 'sidik': _bfm_sidik(aturan)}
    job = {'id': time.strftime('%Y%m%d-%H%M%S-') + pysecrets.token_hex(3), 'host': srv['host'], 'server': srv['name'],
           'aksi': aksi, 'oleh': oleh, 'mulai': int(time.time()), 'status': 'berjalan', 'sidik': perintah['sidik']}
    with _bfm_kunci:
        if any(j['host'] == srv['host'] and j['status'] == 'berjalan' for j in _bfm_job.values()):
            return {'error': 'aksi_sedang_jalan'}, 409
        _bfm_job[job['id']] = job
    threading.Thread(target=_bfm_kerja, args=(job, srv, key, perintah), daemon=True).start()
    return job, 200


def bfm_job(jid):
    return _bfm_job.get(jid or '') or {'error': 'job_tidak_ada'}


def bfm_setelan(payload):
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    masuk = payload.get('aturan')
    if not isinstance(masuk, dict):
        return {'error': 'setelan_tidak_sah'}, 400
    lama = bfm_setelan_baca()
    baru = {}
    for k in BFM_ATURAN:
        a = masuk.get(k) if isinstance(masuk.get(k), dict) else {}
        try:
            ambang = int(a.get('ambang', lama[k]['ambang']))
            durasi = int(a.get('durasi', lama[k]['durasi']))
        except (TypeError, ValueError):
            return {'error': 'setelan_tidak_sah'}, 400
        if not 2 <= ambang <= 500 or durasi not in BFM_DURASI:
            return {'error': 'setelan_tidak_sah'}, 400
        baru[k] = {'aktif': bool(a.get('aktif', lama[k]['aktif'])), 'ambang': ambang, 'durasi': durasi}
    BFM_DIR.mkdir(parents=True, exist_ok=True)
    tmp = BFM_SETELAN.with_suffix('.tmp')
    tmp.write_text(json.dumps(baru, indent=1))
    tmp.replace(BFM_SETELAN)
    _bfm_catat({'t': int(time.time()), 'oleh': oleh, 'aksi': 'setelan', 'ok': True,
                'setelan': {k: baru[k] for k in baru if baru[k] != lama[k]}})
    _cache_bfm.hapus()  # simulasi dihitung ulang dengan ambang baru
    return _bfm_lokal(), 200


def bfm_riwayat(batas=300):
    try:
        baris = BFM_RIWAYAT.read_text().splitlines()[-batas:]
    except OSError:
        return {'riwayat': []}
    out = []
    for b in reversed(baris):
        try:
            out.append(json.loads(b))
        except ValueError:
            continue
    return {'riwayat': out}



# Limit Resource: halaman /server/limit — pengganti LVE untuk server DA non-CloudLinux (sanke). Agen scripts/server_limit_agent.py
# membaca/mengganti preset /etc/velocity-cg/preset (kecil|sedang|tinggi) yang diterapkan velocity-cg-default ke semua user DA.
LIMIT_AGEN = Path(__file__).resolve().parent.parent / 'scripts' / 'server_limit_agent.py'
LIMIT_RIWAYAT = Path('/var/lib/velocity/server-limit/riwayat.jsonl')
_cache_limit = CacheLatar()
_limit_job = {}
_limit_kunci = threading.Lock()


def server_limit(paksa=False):
    def ambil():
        key = ssh_key_file()
        if not key:
            return {'error': 'kunci_ssh_installer_tidak_ada'}
        servers = _daftar_server()
        hasil = [None] * len(servers)

        def kerja(i):
            hasil[i] = _bfm_satu(servers[i], key, {'aksi': 'status'}, 60, LIMIT_AGEN)
        utas = [threading.Thread(target=kerja, args=(i,), daemon=True) for i in range(len(servers))]
        for t in utas:
            t.start()
        for t in utas:
            t.join(65)
        return {'servers': [h or {'host': s['host'], 'name': s['name'], 'ok': False, 'error': 'timeout'}
                            for h, s in zip(hasil, servers)], 'diambil': int(time.time())}
    data = _cache_limit.ambil('status', ambil, BFM_TTL, paksa)
    if isinstance(data, dict) and not data.get('error'):
        data = {**data, 'job': [j for j in _limit_job.values() if j['status'] == 'berjalan']}
    return data


def _limit_kerja(job, srv, key, perintah):
    hasil = _bfm_satu(srv, key, perintah, 1800, LIMIT_AGEN)  # > agen: tar 120 + --semua 300 + rollback per user
    job.update(status='selesai' if hasil.get('ok') else 'gagal', selesai=int(time.time()), hasil=hasil)
    LIMIT_RIWAYAT.parent.mkdir(parents=True, exist_ok=True)
    with _limit_kunci, LIMIT_RIWAYAT.open('a') as f:
        f.write(json.dumps({'t': job['selesai'], 'oleh': job['oleh'], 'server': srv['name'], 'host': srv['host'],
                            'preset': perintah.get('preset'), 'user': perintah.get('user'), 'nilai': perintah.get('nilai'),
                            'ok': bool(hasil.get('ok')), 'error': hasil.get('error'),
                            'cadangan': (hasil.get('hasil') or {}).get('cadangan')}, ensure_ascii=False) + '\n')
    _cache_limit.hapus()


def limit_aksi(payload):
    # {preset} = ganti preset server; {user, nilai} = override per akun (nilai null = kembali ke preset), divalidasi lagi di agen
    preset, user = payload.get('preset'), payload.get('user')
    if user is not None:
        nilai = payload.get('nilai')
        if not re.fullmatch(r'[a-z0-9]{1,32}', str(user)) or not (nilai is None or isinstance(nilai, dict) and 0 < len(nilai) <= 12):
            return {'error': 'nilai_tidak_sah'}, 400
        perintah = {'aksi': 'atur_user', 'user': user, 'nilai': nilai}
    elif preset in ('kecil', 'sedang', 'tinggi'):
        perintah = {'aksi': 'terapkan', 'preset': preset}
    else:
        return {'error': 'preset_tidak_dikenal'}, 400
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    key = ssh_key_file()
    if not key:
        return {'error': 'kunci_ssh_installer_tidak_ada'}, 500
    job = {'id': time.strftime('%Y%m%d-%H%M%S-') + pysecrets.token_hex(3), 'host': srv['host'], 'server': srv['name'],
           'aksi': perintah['aksi'], 'preset': preset, 'user': user, 'oleh': oleh, 'mulai': int(time.time()), 'status': 'berjalan'}
    with _limit_kunci:
        if any(j['host'] == srv['host'] and j['status'] == 'berjalan' for j in _limit_job.values()):
            return {'error': 'aksi_sedang_jalan'}, 409
        _limit_job[job['id']] = job
    threading.Thread(target=_limit_kerja, args=(job, srv, key, perintah), daemon=True).start()
    return job, 200


def limit_job(jid):
    return _limit_job.get(jid or '') or {'error': 'job_tidak_ada'}

# Kerentanan CMS (WordPress) per server: halaman /server/cms, logika di services/server_cms.py
import server_cms  # noqa: E402
import sesi_dash  # noqa: E402
server_cms.pasang(lambda: _daftar_server(), lambda: ssh_key_file(), kirim_telegram_server)
# Judi AI: penilai temuan judi sesudah scan antivirus terjadwal (tab Judi AI), logika di services/server_judi.py
import server_judi  # noqa: E402
server_judi.pasang(lambda: _daftar_server(), lambda: ssh_key_file(), kirim_telegram_server, _antivirus_satu)
# Deteksi lonjakan request per domain + penilaian AI (mode deteksi), logika di services/server_lonjakan.py
import server_lonjakan  # noqa: E402
server_lonjakan.pasang(lambda: _daftar_server(), perintah_server, lambda: ssh_key_file(), kirim_telegram_server)
# VelocityGuard: laporan celah harian, kandidat virtual patch, catatan insiden (services/velocityguard.py)
import velocityguard  # noqa: E402
velocityguard.pasang(lambda: _daftar_server(), perintah_server, lambda: ssh_key_file(), kirim_telegram_server)


# Riwayat pemakaian untuk grafik /server/monitoring (GET /api/servers/riwayat?rentang=24j|7h|30h).
# Data dicatat scripts/server-usage-catat (timer 5 mnt); dirata-rata per ember agar ±300 titik per server.
USAGE_RIWAYAT = Path('/var/lib/velocity/server-usage/riwayat.jsonl')
RENTANG_USAGE = {'1j': (3600, 300), '24j': (86400, 300), '7h': (7 * 86400, 1800), '30h': (30 * 86400, 7200)}
USAGE_KOLOM = ('cpu', 'ram', 'swap', 'disk', 'load', 'req', 'conn', 'net_in', 'net_out', 'suhu')


_riwayat_cache = {}


def server_riwayat(rentang, server=None):
    """server=None → semua; server='' → server pertama yang dipantau; selain itu nama server."""
    if rentang not in RENTANG_USAGE:
        rentang = '24j'
    try:
        st = USAGE_RIWAYAT.stat()
        kunci = (st.st_mtime_ns, st.st_size)
    except OSError:
        kunci = None
    # Berkas ±5 MB diurai sekali per perubahan (timer 5 mnt), bukan tiap permintaan
    simpan = _riwayat_cache.get(rentang)
    if not (simpan and kunci and simpan[0] == kunci):
        simpan = (kunci, _riwayat_urai(rentang))
        _riwayat_cache[rentang] = simpan
    data = simpan[1]
    if server is None:
        return data
    if not server:
        daftar = server_dipantau()
        server = daftar[0]['name'] if daftar else ''
    return {**data, 'servers': [s for s in data['servers'] if s['name'] == server]}


def _riwayat_urai(rentang):
    detik, ember = RENTANG_USAGE[rentang]
    batas = time.time() - detik
    per_server = {}
    try:
        f = USAGE_RIWAYAT.open()
    except OSError:
        return {'rentang': rentang, 'ember': ember, 'servers': []}
    with f:
        for baris in f:
            try:
                b = json.loads(baris)
            except ValueError:
                continue
            if b.get('t', 0) < batas:
                continue
            srv = per_server.setdefault(b['host'], {'host': b['host'], 'name': b.get('name'), 'core': None, 'ember': {}})
            srv['name'] = b.get('name') or srv['name']
            k = int(b['t'] // ember * ember)
            # Rata-rata per kolom hanya dari nilai yang ada (titik sar tak punya disk; server tanpa swap = null)
            e = srv['ember'].setdefault(k, {'n': 0, **{c: [0.0, 0] for c in USAGE_KOLOM}})
            if b.get('ok') is False or b.get('cpu') is None:
                continue
            srv['core'] = b.get('core') or srv['core']
            e['n'] += 1
            for c in USAGE_KOLOM:
                if b.get(c) is not None:
                    e[c][0] += float(b[c])
                    e[c][1] += 1
    hasil = []
    for srv in per_server.values():
        titik = []
        for k in sorted(srv['ember']):
            e = srv['ember'][k]
            if e['n']:
                titik.append({'t': k, **{c: (round(e[c][0] / e[c][1], 1) if e[c][1] else None) for c in USAGE_KOLOM}})
            else:
                titik.append({'t': k})
        hasil.append({'host': srv['host'], 'name': srv['name'], 'core': srv['core'], 'titik': titik})
    return {'rentang': rentang, 'ember': ember, 'servers': hasil}


# Sampel pemakaian satu server (dipakai scripts/server-usage-catat tiap 5 mnt & mode Live /api/servers/live).
# RESOURCE_CMD + baris tambahan, hanya baca: /proc, df, .rtreport LiteSpeed, ss, sensor suhu CPU (hwmon).
USAGE_CMD = RESOURCE_CMD + r'''
for h in /sys/class/hwmon/hwmon*; do case "$(cat $h/name 2>/dev/null)" in coretemp|k10temp|zenpower) cat $h/temp*_input 2>/dev/null;; esac; done | sort -n | tail -1 | sed 's/^/T /'
rt=/tmp/lshttpd/.rtreport; [ -r $rt ] && { echo "W $(grep -m1 '^REQ_RATE \[\]' $rt)"; echo "K $(grep -m1 '^MAXCONN' $rt)"; }
echo "E $(ss -Htn state established '( sport = :80 or sport = :443 )' 2>/dev/null | wc -l)"
dev=$(ip -o route get 1.1.1.1 2>/dev/null | sed -n 's/.* dev \([^ ]*\).*/\1/p'); [ -n "$dev" ] && echo "N $(grep -E "^ *$dev:" /proc/net/dev | tr ':' ' ')"
'''


def usage_sampel(srv, key):
    cmd = perintah_server(srv, key, USAGE_CMD)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0 or not (r.stdout or '').strip():
        return None
    out = _parse_resource(r.stdout)
    for baris in r.stdout.splitlines():
        kode, _, isi = baris.partition(' ')
        try:
            if kode == 'W':
                m = re.search(r'REQ_PER_SEC: ([\d.]+)', isi)
                if m:
                    out['req'] = float(m.group(1))
            elif kode == 'K':
                plain, ssl = re.search(r'PLAINCONN: (\d+)', isi), re.search(r'SSLCONN: (\d+)', isi)
                if plain and ssl:
                    out['conn'] = int(plain.group(1)) + int(ssl.group(1))
            elif kode == 'E':
                out['established'] = int(isi.strip() or 0)
            elif kode == 'T':
                out['suhu'] = round(int(isi) / 1000, 1)  # inti CPU terpanas, °C
            elif kode == 'N':
                p = isi.split()  # iface rx_bytes … (kolom ke-9 dari data = tx_bytes)
                out['net'] = {'rx': int(p[1]), 'tx': int(p[9])}
        except (ValueError, IndexError):
            continue
    out['ok'] = True
    return out


def usage_titik(r):
    """Kolom riwayat dari hasil usage_sampel (tanpa net_in/net_out: butuh selisih counter)."""
    return dict(cpu=r.get('cpu'), ram=(r.get('ram') or {}).get('persen'), swap=(r.get('swap') or {}).get('persen'),
                disk=max((d['persen'] for d in r.get('disks') or []), default=None), load=(r.get('load') or [None])[0],
                core=r.get('cpu_core'), req=r.get('req'), conn=r.get('conn', r.get('established')), suhu=r.get('suhu'))


def usage_net(net, lama, now, maks_dt):
    """Mbps masuk/keluar dari selisih counter /proc/net/dev; {} bila catatan lama tak cocok (reboot/terlalu lama)."""
    if lama and 0 < now - lama['t'] <= maks_dt and net['rx'] >= lama['rx'] and net['tx'] >= lama['tx']:
        dt = now - lama['t']
        return {'net_in': round((net['rx'] - lama['rx']) * 8 / dt / 1e6, 2), 'net_out': round((net['tx'] - lama['tx']) * 8 / dt / 1e6, 2)}
    return {}


# Mode Live: satu SSH per permintaan; hasil < 3 dtk dipakai bersama agar beberapa penonton tak menumpuk SSH.
_live_cache = {}
_live_kunci = threading.Lock()


def server_live(nama=None):
    daftar = server_dipantau()
    srv = next((s for s in daftar if s['name'] == nama), daftar[0] if daftar else None)
    if not srv:
        return {'error': 'server tidak ada'}
    with _live_kunci:
        c = _live_cache.setdefault(srv['host'], {'lock': threading.Lock(), 'hasil': None, 'net': None})
    with c['lock']:
        if c['hasil'] and time.time() - c['hasil']['titik']['t'] < 3:
            return c['hasil']
        key = ssh_key_file()
        r = usage_sampel(srv, key) if key else None
        now = time.time()
        titik = {'t': round(now, 1)}
        if r and r.get('ok'):
            titik.update(usage_titik(r))
            if r.get('net'):
                titik.update(usage_net(r['net'], c['net'], now, 120))
                c['net'] = {'t': now, **r['net']}
        c['hasil'] = {'host': srv['host'], 'name': srv['name'], 'ok': bool(r and r.get('ok')), 'titik': titik}
        return c['hasil']


_local_ip_cache = {'at': 0, 'value': []}
LOCAL_IP_TTL = 300


def local_ips():
    """IPv4 lokal (LAN/Tailscale, tanpa loopback). Read-only, untuk badge SERVER INI."""
    now = time.time()
    if now - _local_ip_cache['at'] < LOCAL_IP_TTL:
        return _local_ip_cache['value']
    ips = set()
    try:
        r = subprocess.run(['ip', '-4', '-o', 'addr', 'show'],
                           capture_output=True, text=True, timeout=3, check=False)
        for m in re.finditer(r'inet (\d+\.\d+\.\d+\.\d+)', r.stdout or ''):
            if m.group(1) != '127.0.0.1':
                ips.add(m.group(1))
    except (OSError, subprocess.TimeoutExpired):
        pass
    _local_ip_cache.update(at=now, value=sorted(ips))
    return _local_ip_cache['value']


def manifest_target(manifest):
    """Baca target_host mentah dari manifest. Read-only, tanpa validasi ulang."""
    try:
        for line in Path(manifest).read_text(errors='replace').splitlines():
            s = line.strip()
            if not s or s.startswith('#') or '=' not in s:
                continue
            k, _, v = s.partition('=')
            if k.strip() == 'target_host':
                return v.strip() or None
    except OSError:
        pass
    return None


SCRIPTS_DIR = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))
from client_form import read_client_form
from hosting_notes import read_hosting_notes
from folder_klien import folder_klien, subfolder_dari_deskripsi, PETA as SUBFOLDER_PETA

# Label form yang berisi nama orang/domain, bukan nama usaha.
_BUKAN_NAMA_SITUS = {'nama anda', 'nama domain', 'nama lengkap', 'nama pemilik'}


def _velocity_packages():
    """Slug paket tema & plugin Velocity yang zip-nya benar-benar tersedia."""
    theme = addons = ''
    try:
        meta = json.loads(PACKAGES_META.read_text())
    except (OSError, ValueError):
        return theme, addons
    for slug, info in (meta if isinstance(meta, dict) else {}).items():
        if not (PACKAGES_DIR / f'{slug}.zip').is_file():
            continue
        kind = str((info or {}).get('type') or '')
        if kind == 'theme' and not theme:
            theme = slug
        elif kind == 'plugin' and not addons:
            addons = slug
    return theme, addons


def _site_title_from_form(folders, fallback):
    """Judul situs diambil dari nama usaha di form isian klien. Tanpa ini judul
    hanya tebakan dari nama domain (mis. 'Birutourtravel' alih-alih
    'BIRU TOUR & TRAVEL'). Form-nya ada di folder sync Drive, bukan di folder
    manifest, jadi keduanya diperiksa."""
    for folder in folders:
        try:
            if not Path(folder).is_dir():
                continue
            fields = read_client_form(folder)['fields']
        except Exception:
            continue
        for label, value in fields.items():
            key = ' '.join(label.strip().lower().split())
            if key.startswith('nama ') and key not in _BUKAN_NAMA_SITUS:
                value = value.strip()
                if 2 < len(value) <= 80:
                    return value
    return fallback


def default_target():
    """Server tujuan yang akan dipakai generate_manifest: entri pertama daftar
    server. Dipakai bersama halaman installer supaya 'calon target' yang
    ditampilkan tidak bisa berbeda dari yang benar-benar ditulis ke manifest."""
    servers = load_servers()
    srv = servers[0] if isinstance(servers, list) and servers else {}
    if not isinstance(srv, dict):
        srv = {}
    return {
        'host': str(srv.get('host') or '103.103.175.182'),
        'name': str(srv.get('name') or ''),
        'port': str(srv.get('port') or '22'),
        'user': str(srv.get('user') or 'root'),
    }


def staging_target():
    """Server staging velocitydeveloper.co (Kiya) dari daftar server."""
    servers = load_servers()
    for srv in servers if isinstance(servers, list) else []:
        if isinstance(srv, dict) and str(srv.get('host') or '') == STAGING_HOST:
            return {'host': STAGING_HOST, 'name': str(srv.get('name') or ''),
                    'port': str(srv.get('port') or '22'), 'user': str(srv.get('user') or 'root')}
    return {'host': STAGING_HOST, 'name': 'Kiya', 'port': '57258', 'user': 'root'}


def diminta_staging(domain):
    """Deskripsi tiket CRM domain ini meminta pengerjaan di staging web Velocity."""
    return bool((crm_projects().get(domain.lower()) or {}).get('staging'))


def validate_manifest(path: Path):
    """Lightweight manifest validation, returns (ok, detail)."""
    try:
        text = path.read_text()
    except Exception as e:
        return False, str(e)
    cfg = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' not in line:
            return False, 'invalid_line'
        k, v = line.split('=', 1)
        k = re.sub(r'[\s\r]', '', k)
        v = v.strip()
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', k):
            return False, 'invalid_key:' + k
        cfg[k] = v
    required = ['target_host', 'ssh_user', 'da_user', 'domain', 'db_name', 'db_user', 'admin_email', 'site_title']
    for k in required:
        if not cfg.get(k):
            return False, 'missing_' + k
    if not re.match(r'^[A-Za-z0-9.-]+$', cfg['target_host']):
        return False, 'invalid_target_host'
    if not re.match(r'^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', cfg['domain']):
        return False, 'invalid_domain'
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', cfg['admin_email']):
        return False, 'invalid_admin_email'
    # Sama dengan validasi installer, supaya manifest rusak terlihat di halaman
    # (dan dibuat ulang oleh generate) sebelum autopilot menjalankan dry-run.
    for key in ('db_name', 'db_user'):
        if not re.match(r'^[A-Za-z0-9_]+$', cfg[key]):
            return False, 'invalid_' + key
    if not re.match(r'^[a-z][a-z0-9]*$', cfg['da_user']):
        return False, 'invalid_da_user'
    return True, 'ok'


def cronjobs():
    now = time.time()
    if now - _cron_cache['at'] < CACHE_TTL:
        return _cron_cache['value']
    rows = []
    for command in (['systemctl', 'list-timers', '--all', '--no-legend', '--no-pager'], ['crontab', '-l']):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and 'No timers listed' not in line:
                rows.append(line)
    summary = {'count': len(rows), 'preview': rows[:5]}
    _cron_cache['at'] = now
    _cron_cache['value'] = summary
    return summary


def installed_domains():
    """Domains already installed (state SUCCESS COMPLETE). Hidden from the list."""
    done = set()
    if not STATE.is_dir():
        return done
    for f in STATE.glob('*.json'):
        try:
            saved = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if (isinstance(saved, dict) and saved.get('status') == 'SUCCESS'
                and saved.get('stage') == 'COMPLETE'):
            done.add(f.stem)
    return done


def _project_list_api_key():
    env_key = os.environ.get('PROJECT_LIST_API_KEY', '').strip()
    if env_key:
        return env_key
    try:
        return PROJECT_LIST_API_KEY_FILE.read_text().strip()
    except OSError:
        return ''


def _crm_page(status: str, page: int, key: str):
    # Urutkan naik berdasarkan id: dataset ini hidup, dan urutan default
    # (tgl_deadline desc) bikin baris baru menggeser halaman berikutnya
    # sehingga ada baris terlewat di batas halaman saat paginasi.
    url = (f'{PROJECT_LIST_API_URL}?status_pengerjaan={urllib.parse.quote(status)}'
           f'&per_page={PROJECT_LIST_PER_PAGE}&page={page}'
           f'&order_by=id&order=asc')
    # UA default urllib ('Python-urllib/x.y') kena aturan anti-bot CPGuard
    # di depan API ini dan dibalas 403, padahal request yang sama lolos
    # dengan UA biasa.
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {key}',
        'User-Agent': 'velocity-installer/1.0',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8', errors='replace'))


def _crm_webmaster(item):
    """Nama webmaster pemegang project, kalau CRM sudah menugaskannya."""
    wm = item.get('wm_project') or {}
    if not isinstance(wm, dict):
        return ''
    user = wm.get('user') or {}
    nama = (user.get('name') if isinstance(user, dict) else '') or wm.get('webmaster') or ''
    return str(nama).strip()


def _fetch_crm_projects_now():
    """Tarik antrean CRM untuk tiap status di CRM_STATUSES, jadi
    {domain: {paket, deadline, jenis, crm_status, webmaster}}. Satu per_page
    besar, bukan banyak halaman kecil — host bersama di depan API ini
    me-reset/memblokir koneksi setelah rentetan request cepat.
    """
    key = _project_list_api_key()
    if not key:
        return {}
    found = {}
    for status in CRM_STATUSES:
        page = 1
        while True:
            data = _crm_page(status, page, key)
            for item in data.get('data', []):
                jenis = str(item.get('jenis') or '').strip()
                if jenis not in INSTALL_JENIS:
                    continue
                wh = item.get('webhost') or {}
                name = str(wh.get('nama_web') or '').strip().lower()
                if not name:
                    continue
                paket = str((wh.get('paket') or {}).get('paket') or '').strip()
                deadline = str(item.get('tgl_deadline') or '').strip()
                webmaster = _crm_webmaster(item)
                # Satu domain bisa punya beberapa project: pertahankan nilai yang
                # terisi supaya baris kosong tidak menimpanya, dan untuk deadline
                # ambil yang paling dekat karena itu yang paling mendesak.
                cur = found.setdefault(name, {'paket': '', 'deadline': '', 'jenis': [],
                                              'crm_status': '', 'webmaster': '', 'subfolder': '',
                                              'staging': False})
                if 'apk' not in jenis.lower() and staging_dari_deskripsi(item.get('deskripsi')):
                    cur['staging'] = True
                # Deskripsi tiket "sub folder <nama>" = bahan klien ada di subfolder itu
                # (lihat scripts/folder_klien.py). Urutan id naik: tiket terbaru menang.
                # Tiket apk dilewati: subfolder "apk <domain>" berisi form aplikasi Android,
                # bukan bahan website.
                sub = '' if 'apk' in jenis.lower() else subfolder_dari_deskripsi(item.get('deskripsi'))
                if sub:
                    cur['subfolder'] = sub
                # Autopilot perlu jenisnya: Redesign berarti situsnya sudah hidup.
                if jenis not in cur['jenis']:
                    cur['jenis'].append(jenis)
                if paket and not cur['paket']:
                    cur['paket'] = paket
                if deadline and (not cur['deadline'] or deadline < cur['deadline']):
                    cur['deadline'] = deadline
                if webmaster and not cur['webmaster']:
                    cur['webmaster'] = webmaster
                # "Belum dikerjakan" menang: kalau satu domain punya tiket yang
                # belum diambil, pekerjaan itu memang masih menganggur walau
                # tiket lain di domain sama sudah dipegang webmaster.
                if cur['crm_status'] != ST_BELUM_DIAMBIL:
                    cur['crm_status'] = (ST_BELUM_DIAMBIL if status == 'Belum dikerjakan'
                                         else ST_DIKERJAKAN_WM)
            last_page = data.get('last_page', page)
            if page >= last_page:
                break
            if page >= PROJECT_LIST_MAX_PAGES:
                # Jangan memotong diam-diam kalau data tumbuh melewati batas.
                print(json.dumps({'event': 'crm_projects_truncated', 'status': status,
                                  'fetched_pages': page, 'last_page': last_page}), flush=True)
                break
            page += 1
            time.sleep(1)  # be gentle with the shared host between pages
        time.sleep(1)
    return found


def _simpan_subfolder_crm(fresh):
    """Catat petunjuk subfolder dari CRM ke peta yang dibaca folder_klien() semua skrip.
    Domain yang sudah keluar antrean dipertahankan: skrip finish/audit sesudah install
    tetap harus membaca subfolder yang sama."""
    try:
        peta = json.loads(SUBFOLDER_PETA.read_text())
        if not isinstance(peta, dict):
            peta = {}
    except (OSError, ValueError):
        peta = {}
    baru = dict(peta)
    for domain, info in fresh.items():
        if info.get('subfolder'):
            baru[domain] = info['subfolder']
        else:
            baru.pop(domain, None)
    if baru != peta:
        tmp = SUBFOLDER_PETA.with_suffix('.tmp')
        tmp.write_text(json.dumps(baru, ensure_ascii=False, indent=1, sort_keys=True))
        tmp.replace(SUBFOLDER_PETA)


def _refresh_crm_projects_bg():
    error = ''
    try:
        fresh = _fetch_crm_projects_now()
        if fresh or not _crm_cache_projects['value']:
            _crm_cache_projects['value'] = fresh
        if fresh:
            _simpan_subfolder_crm(fresh)
    except Exception as e:  # keep serving the last-known set on API hiccup
        # Jangan gagal dalam diam: tanpa jejak ini, satu kegagalan sesaat bikin
        # halaman cuma menampilkan segelintir domain tanpa alasan yang terlacak.
        error = f'{type(e).__name__}: {e}'
        print(json.dumps({'event': 'crm_projects_refresh_failed', 'error': error}), flush=True)
    finally:
        _crm_cache_projects['error'] = error
        _crm_cache_projects['at'] = time.time()
        _crm_cache_projects['fetching'] = False


def crm_projects():
    """Cache {domain: {paket, deadline, jenis, crm_status, webmaster}} untuk
    project yang menurut CRM belum diambil atau sedang dikerjakan webmaster.
    Panggilan pertama menahan diri sampai tarikan selesai supaya daftar tidak
    kosong saat cold start; penyegaran berikutnya di thread latar supaya
    /api/installer tidak pernah menunggu ~24s.
    """
    now = time.time()
    if _crm_cache_projects['at'] == 0:
        # Cold start: tahan request lain sampai tarikan pertama selesai. Tanpa
        # kunci ini, request yang datang saat tarikan berjalan dapat cache
        # kosong dan halaman seolah cuma berisi 2 domain.
        with _crm_projects_lock:
            if _crm_cache_projects['at'] == 0:
                _crm_cache_projects['fetching'] = True
                _refresh_crm_projects_bg()
        return _crm_cache_projects['value']
    # Percobaan yang gagal tidak boleh membekukan cache kosong selama TTL penuh.
    ttl = CRM_RETRY if _crm_cache_projects['error'] else CRM_TTL
    if now - _crm_cache_projects['at'] >= ttl and not _crm_cache_projects['fetching']:
        _crm_cache_projects['fetching'] = True
        threading.Thread(target=_refresh_crm_projects_bg, daemon=True).start()
    return _crm_cache_projects['value']


def load_claims():
    try:
        data = json.loads(CLAIMS_FILE.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_claims(claims):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = CLAIMS_FILE.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(claims, indent=1, sort_keys=True))
    os.chmod(tmp, 0o600)
    os.replace(tmp, CLAIMS_FILE)


def claim_domain(domain: str, by: str):
    """Tandai project sudah diambil alih. Idempoten: klaim yang sudah ada tidak ditimpa."""
    if not DOMAIN_RE.match(domain) or '/' in domain or '..' in domain:
        return None, 'invalid_domain'
    by = (by or 'manual').strip().lower()
    if not CLAIM_BY_RE.match(by):
        return None, 'invalid_by'
    name = domain.lower()
    # Host server bukan pekerjaan: jangan sampai bisa diklaim lalu dipasangi WordPress.
    if name in bukan_project():
        return None, 'bukan_project'
    # Hanya pekerjaan yang memang ada: di antrean CRM atau sudah punya folder.
    if (name not in crm_projects() and not (ON_PROGRESS / name).is_dir()
            and not (ROOT / name).is_dir()):
        return None, 'unknown_domain'
    with _claims_lock:
        claims = load_claims()
        if name in claims:
            return {'domain': name, 'claimed': False, **claims[name]}, None
        claims[name] = {'by': by, 'at': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
        _save_claims(claims)
    return {'domain': name, 'claimed': True, **claims[name]}, None


def release_claim(domain: str):
    if not DOMAIN_RE.match(domain) or '/' in domain or '..' in domain:
        return None, 'invalid_domain'
    name = domain.lower()
    with _claims_lock:
        claims = load_claims()
        if claims.pop(name, None) is None:
            return None, 'not_claimed'
        _save_claims(claims)
    return {'domain': name, 'released': True}, None


def _queue_row(name, source, antrean, claims, connected_hosts):
    """Baris antrean untuk satu folder project, atau None kalau tidak perlu tampil."""
    manifest = ROOT / name / f'{name}.txt'
    has_manifest = manifest.is_file()
    row = domain_row(name, manifest if has_manifest else None)
    key = name.lower()
    crm = antrean.get(key) or {}
    row['paket'] = crm.get('paket') or None
    row['deadline'] = crm.get('deadline') or None
    row['jenis'] = crm.get('jenis') or []
    row['crm_status'] = crm.get('crm_status') or None
    row['webmaster'] = crm.get('webmaster') or None
    row['claim'] = claims.get(key)
    if key in antrean and not row['claim']:
        # Status CRM hanya menimpa status installer selama belum ada jejak
        # instalasi: sekali installer punya manifest/run, itu yang lebih baru.
        row['status'] = crm.get('crm_status') or ST_BELUM_DIAMBIL
    elif not has_manifest and not row['claim']:
        return None
    elif has_manifest and row.get('target_host') not in connected_hosts:
        return None
    row['source'] = source
    return row


def domains():
    rows = []
    done = installed_domains()
    connected_hosts = {str(s.get('host', '')).strip() for s in load_servers()
                       if isinstance(s, dict) and str(s.get('host', '')).strip()}
    antrean = crm_projects()
    claims = load_claims()
    abaikan = bukan_project()
    seen = set()
    # primary source: On Progress folders synced from Google Drive
    if ON_PROGRESS.is_dir():
        for folder in sorted(p for p in ON_PROGRESS.iterdir() if p.is_dir()):
            name = folder.name
            if not DOMAIN_RE.match(name) or name in done or name.lower() in abaikan:
                continue
            seen.add(name)
            row = _queue_row(name, 'onprogress', antrean, claims, connected_hosts)
            if row:
                rows.append(row)
    # fallback: existing /home/project folders (e.g. fahmi = Drive-less, yayasan = FAILED retry)
    if ROOT.is_dir():
        for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
            name = folder.name
            if name in seen or not DOMAIN_RE.match(name) or name in done or name.lower() in abaikan:
                continue
            row = _queue_row(name, 'project', antrean, claims, connected_hosts)
            if row:
                rows.append(row)
    # CRM adalah sumber kebenaran soal pekerjaan yang ada. Daftar di atas
    # digerakkan oleh folder di disk, jadi project yang foldernya belum
    # tersinkron dari Drive tidak pernah muncul sama sekali — padahal itu justru
    # pekerjaan yang perlu dikejar. Tampilkan, dengan tanda folder belum ada.
    # Situs COMPLETE yang sedang dikerjakan agen desain Claude tetap tampil (paling atas).
    for name in sorted(done):
        if agen_desain(name):
            manifest = ROOT / name / f'{name}.txt'
            row = domain_row(name, manifest if manifest.is_file() else None)
            try:
                row['paket'] = next((l.partition('=')[2].strip() for l in manifest.read_text(errors='replace').splitlines()
                                     if l.startswith('paket=')), '') or None
            except OSError:
                row['paket'] = None
            crm = antrean.get(name) or {}
            row.update({'deadline': crm.get('deadline') or None, 'claim': claims.get(name), 'source': 'agen'})
            rows.insert(0, row)
    emitted = {r['domain'].lower() for r in rows}
    done_lower = {d.lower() for d in done}
    for name in sorted(antrean):
        if name in emitted or name in done_lower or not DOMAIN_RE.match(name) or name in abaikan:
            continue
        crm = antrean.get(name) or {}
        claim = claims.get(name)
        rows.append({
            'domain': name,
            'manifest': None,
            'folder': False,
            'status': ('NO_FOLDER' if claim
                       else crm.get('crm_status') or ST_BELUM_DIAMBIL),
            'target_host': None,
            'paket': crm.get('paket') or None,
            'deadline': crm.get('deadline') or None,
            'jenis': crm.get('jenis') or [],
            'crm_status': crm.get('crm_status') or None,
            'webmaster': crm.get('webmaster') or None,
            'claim': claim,
            'log': [],
            'source': 'crm',
        })
    # Situs yang sudah COMPLETE ditampilkan di paling bawah (terbaru dulu) supaya bisa dijalankan
    # ulang atau dilihat bagan/log-nya (permintaan user 2026-09-19). Barisnya ditandai
    # source='selesai': onprogress-sync melewatinya, autopilot hanya mengambil 'belum diambil'.
    # Log tidak ikut dikirim (56+ situs); modal log & bagan mengambilnya lewat ?domain=.
    selesai = []
    for name in done:
        if name.lower() in emitted or not DOMAIN_RE.match(name) or name.lower() in abaikan:
            continue
        manifest = ROOT / name / f'{name}.txt'
        row = domain_row(name, manifest if manifest.is_file() else None)
        row['ada_log'] = bool(row.get('log'))
        row['log'] = []
        try:
            row['paket'] = next((l.partition('=')[2].strip() for l in manifest.read_text(errors='replace').splitlines()
                                 if l.startswith('paket=')), '') or None
        except OSError:
            row['paket'] = None
        crm = antrean.get(name) or {}
        row.update({'deadline': crm.get('deadline') or None, 'crm_status': crm.get('crm_status') or None,
                    'webmaster': crm.get('webmaster') or None, 'claim': claims.get(name), 'source': 'selesai'})
        selesai.append(row)
    selesai.sort(key=lambda r: r.get('updated_at') or '', reverse=True)
    return rows + selesai


# Agen desain Claude (scripts/desain-claude) menulis penanda <domain>.json selama berjalan. Situs
# yang sudah COMPLETE tetap tampil di daftar & panel pantau selama agennya bekerja.
DESAIN_CLAUDE_AKTIF = STATE / 'desain-claude'
FSE_RENCANA = Path('/var/lib/velocity/fse-rencana')


def agen_desain(domain):
    """Keadaan agen desain Claude yang sedang berjalan untuk domain, atau None."""
    try:
        d = json.loads((DESAIN_CLAUDE_AKTIF / f'{domain}.json').read_text())
        pid = int(d.get('pid') or 0)
    except (OSError, ValueError, TypeError):
        return None
    if not pid or not Path(f'/proc/{pid}').exists():
        return None
    try:
        audit = json.loads((FSE_RENCANA / domain / 'audit-kemiripan.json').read_text())
        d['skor_kini'] = audit.get('skor') or {}
        d['belum_mirip'] = audit.get('belum_mirip') or []
        d['audit_pada'] = audit.get('waktu', '')
    except (OSError, ValueError):
        pass
    return d


def domain_row(domain, manifest):
    if manifest:
        ok, detail = validate_manifest(manifest)
        base_status = 'READY' if ok else detail
    else:
        base_status = 'NO_MANIFEST'
    row = {'domain': domain, 'manifest': manifest.name if manifest else None,
           'folder': True, 'status': base_status,
           'target_host': manifest_target(manifest) if manifest else manifest_target(ROOT / f'{domain}.txt')}
    state = STATE / f'{domain}.json'
    log = STATE / f'{domain}.log'
    try:
        saved = json.loads(state.read_text())
        if isinstance(saved, dict):
            row.update({k: str(saved[k]) for k in ('status', 'stage', 'message', 'updated_at') if k in saved})
    except (OSError, ValueError):
        pass
    try:
        row['log'] = log.read_text(errors='replace').splitlines()[-200:]
    except OSError:
        row['log'] = []
    row['lama'] = lama_pengerjaan(domain)
    row['token'] = token_domain(domain)
    agen = agen_desain(domain)
    if agen:
        skor = agen.get('skor_kini') or {}
        row.update({'status': 'RUNNING', 'stage': 'AGEN DESAIN CLAUDE', 'agen': agen,
                    'message': 'skor ' + ' '.join(f'{k}={v}' for k, v in skor.items())
                    + (' | belum mirip: ' + ','.join(agen.get('belum_mirip') or []) if agen.get('belum_mirip') else '')})
    return row


# Lama pengerjaan installer: dari "RUNNING: VALIDATING" (awal run) sampai laporan Telegram
# terkirim. Baris telegram berstempel waktu sejak 2026-09-26; log lama memakai stempel baris
# terakhir sebelum baris telegram (SUCCESS/CHECK/FAILED, selisihnya beberapa detik).
POLA_STEMPEL = re.compile(r'^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d)\] (.*)')
_cache_lama = {}


def _detik_iso(teks):
    from datetime import datetime
    return datetime.fromisoformat(teks).timestamp()


def lama_pengerjaan(domain):
    """{'terakhir': run terakhir yang laporannya terkirim, 'berjalan_sejak': awal run yang belum
    mengirim laporan} dari log domain. Di-cache per (mtime, ukuran) karena API dibaca tiap 4 detik."""
    log = STATE / f'{domain}.log'
    try:
        st = log.stat()
    except OSError:
        return {}
    kunci = (st.st_mtime_ns, st.st_size)
    lama = _cache_lama.get(domain)
    if lama and lama[0] == kunci:
        return lama[1]
    runs, kini, stempel = [], None, None
    for baris in log.read_text(errors='replace').splitlines():
        m = POLA_STEMPEL.match(baris)
        isi = m.group(2) if m else baris
        if m:
            stempel = m.group(1)
        if isi == 'RUNNING: VALIDATING' and m:
            kini = {'mulai': stempel, 'mode': None, 'hasil': None, 'selesai': None}
            runs.append(kini)
            continue
        if not kini:
            continue
        if isi.startswith('Mode run: '):
            kini['mode'] = isi[10:].split(' |')[0].strip()
        elif re.match(r'^(SUCCESS|CHECK|FAILED): ', isi):
            kini['hasil'] = isi
        elif isi.startswith('telegram: terkirim') and not kini['selesai']:
            kini['selesai'] = stempel
    hasil = {}
    for r in reversed(runs):
        if r['selesai']:
            try:
                mulai, selesai = _detik_iso(r['mulai']), _detik_iso(r['selesai'])
            except ValueError:
                continue
            hasil['terakhir'] = {'mulai': mulai, 'selesai': selesai, 'detik': round(selesai - mulai),
                                 'mode': r['mode'], 'hasil': r['hasil']}
            break
    if runs and not runs[-1]['selesai'] and not runs[-1]['hasil']:
        try:
            hasil['berjalan_sejak'] = _detik_iso(runs[-1]['mulai'])
        except ValueError:
            pass
    _cache_lama[domain] = (kunci, hasil)
    return hasil


# Total token AI per domain untuk kolom Lama /installer/wordpress (permintaan user 2026-09-28):
# Claude (sumber=claude: agen desain, baca form, dsb.) dipisah dari model lain (endpoint /ai/).
_cache_token = {}


def token_domain(domain):
    """{'claude': {...}, 'lain': {...}, 'total', 'run_terakhir': {...}} dari usage.jsonl, atau {}."""
    try:
        st = AI_USAGE.stat()
    except OSError:
        return {}
    kunci = (st.st_mtime_ns, st.st_size)
    if _cache_token.get('kunci') != kunci:
        per = {}
        for s in AI_USAGE.read_text(errors='replace').splitlines():
            try:
                b = json.loads(s)
            except ValueError:
                continue
            if not isinstance(b, dict) or not b.get('domain'):
                continue
            d = per.setdefault(b['domain'], {'claude': {'token': 0, 'panggilan': 0, 'model': set(), 'biaya_usd': 0.0},
                                             'lain': {'token': 0, 'panggilan': 0, 'model': set()},
                                             'runs': {}})
            sisi = d['claude' if b.get('sumber') == 'claude' else 'lain']
            n = int(b.get('total_tokens') or 0)
            sisi['token'] += n
            sisi['panggilan'] += int(b.get('permintaan') or 1)
            sisi['model'].add(b.get('model') or b.get('model_id') or '-')
            if 'biaya_usd' in sisi:
                sisi['biaya_usd'] += float(b.get('biaya_usd') or 0)
            r = d['runs'].setdefault(b.get('run') or '-', {'run': b.get('run') or '-', 'mode': b.get('mode') or '',
                                                            'claude': 0, 'lain': 0, 'ts': ''})
            r['claude' if b.get('sumber') == 'claude' else 'lain'] += n
            r['ts'] = max(r['ts'], str(b.get('ts') or ''))
        hasil = {}
        for dom, d in per.items():
            for k in ('claude', 'lain'):
                d[k]['model'] = sorted(d[k]['model'])
            d['claude']['biaya_usd'] = round(d['claude']['biaya_usd'], 4)
            runs = d.pop('runs')
            d['total'] = d['claude']['token'] + d['lain']['token']
            d['run_terakhir'] = max(runs.values(), key=lambda r: r['ts']) if runs else None
            hasil[dom] = d
        _cache_token.clear()
        _cache_token.update(kunci=kunci, data=hasil)
    return _cache_token['data'].get(domain, {})


def run_terakhir():
    """Domain dengan state installer paling baru: bagan alur halaman /installer/ menampilkannya
    saat tidak ada installer yang berjalan. None kalau belum pernah ada run."""
    calon = []
    for f in STATE.glob('*.json'):
        if DOMAIN_RE.match(f.stem):
            try:
                calon.append((f.stat().st_mtime, f))
            except OSError:
                pass
    for _, f in sorted(calon, reverse=True):
        try:
            data = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get('status'):
            return {'domain': f.stem, 'status': str(data['status']), 'updated_at': str(data.get('updated_at', ''))}
    return None


def _write_secret(name: str, content: str, perms: int = 0o600):
    SECRETS.mkdir(parents=True, exist_ok=True)
    os.chmod(SECRETS, 0o700)
    p = SECRETS / name
    p.write_text(content)
    os.chmod(p, perms)
    return p


def ssh_key_file():
    for p in SSH_KEY_CANDIDATES:
        if p.is_file():
            return p
    return None


def _ensure_secrets(domain: str):
    """Create per-domain password secrets if absent. Never overwrites."""
    created = []
    for name, val in (
        (f'db_password_{domain}.txt', pysecrets.token_urlsafe(18)),
        (f'admin_password_{domain}.txt', pysecrets.token_urlsafe(18)),
    ):
        p = SECRETS / name
        if not p.is_file():
            _write_secret(name, val)
            created.append(name)
    return created


def _write_manifest_lines(manifest: Path, lines):
    tmp = manifest.with_suffix('.txt.tmp')
    tmp.write_text('\n'.join(lines) + '\n')
    os.chmod(tmp, 0o640)
    os.replace(tmp, manifest)


def _sync_hosting_notes(domain: str, manifest: Path, allow_regenerate: bool = True):
    """Samakan manifest dengan catatan hosting PM (<domain>.txt) sebelum dipakai.

    - Password akun hosting disalin ke secret per domain dan dipakai sebagai
      password admin WordPress. Dulu semua manifest menunjuk satu file password
      bersama, sehingga login WordPress tidak pernah cocok dengan catatan.
    - Username di catatan berbeda dari manifest dan situs belum terpasang ->
      manifest dibuat ulang (PM bisa menulis catatan setelah manifest dibuat).
    Mengembalikan daftar perubahan; nilai kredensial tidak pernah dikembalikan."""
    changes = []
    user, password = read_hosting_notes(domain)
    try:
        lines = manifest.read_text().splitlines()
    except OSError:
        return changes
    cfg = {l.split('=', 1)[0].strip(): l.split('=', 1)[1].strip() for l in lines if '=' in l}
    # Manifest staging (docroot=) selalu memakai akun vdco: username akun klien di
    # catatan bukan alasan membuatnya ulang.
    if (allow_regenerate and user and re.match(r'^[a-z][a-z0-9]{0,15}$', user)
            and user != cfg.get('da_user') and not cfg.get('docroot')
            and domain not in installed_domains()):
        manifest.unlink()
        result, err = generate_manifest(domain)
        if result is None:
            _write_manifest_lines(manifest, lines)
            return changes + [f'manifest_gagal_dibuat_ulang:{err}']
        changes.append('manifest_dibuat_ulang:username_catatan')
        lines = manifest.read_text().splitlines()
    per_domain = SECRETS / f'da_password_{domain}.txt'
    if password:
        if not per_domain.is_file() or per_domain.read_text() != password:
            _write_secret(per_domain.name, password)
            changes.append('password_catatan_disalin')
    new_lines = [l for l in lines if not l.startswith('da_password_file=')]
    # Tanpa password di catatan, installer memakai password acak per domain
    # (WP_INSTALL_ADMIN_PASSWORD_FILE), bukan lagi file password bersama.
    if password:
        new_lines.append(f'da_password_file={per_domain}')
    if new_lines != lines:
        _write_manifest_lines(manifest, new_lines)
        changes.append('manifest_password_diperbarui')
    return changes


def _sync_staging(domain: str, manifest: Path):
    """Deskripsi CRM bisa ditulis sesudah manifest dibuat (cybersumatra.com: manifest
    mengarah ke akun DA klien yang belum ada). Selama situs belum terpasang, manifest
    tanpa docroot= dibuat ulang ke staging. Arah sebaliknya tidak otomatis."""
    if domain in installed_domains() or not diminta_staging(domain):
        return []
    try:
        text = manifest.read_text()
    except OSError:
        return []
    if re.search(r'^docroot=', text, re.M):
        return []
    manifest.unlink()
    result, err = generate_manifest(domain)
    if result is None:
        _write_manifest_lines(manifest, text.splitlines())
        return [f'staging_gagal_dibuat:{err}']
    return ['manifest_dialihkan_ke_staging']


def generate_manifest(domain: str):
    """Auto-generate manifest + secrets for domain from existing data."""
    if not DOMAIN_RE.match(domain) or '/' in domain or '..' in domain:
        return None, 'invalid_domain'
    # source folder: /home/project/<domain> or On Progress sync from Drive
    src = ROOT / domain
    if not src.is_dir():
        src = folder_klien(domain)
        if not src.is_dir():
            return None, 'no_folder'
    folder = ROOT / domain
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / f'{domain}.txt'
    if manifest.is_file():
        ok, detail = validate_manifest(manifest)
        if ok:
            _ensure_secrets(domain)
            _sync_hosting_notes(domain, manifest, allow_regenerate=False)
            return {'generated': False, 'reason': 'already_valid'}, None
    # Form klien dibaca agen Claude Code dulu (scripts/baca-form-claude, keputusan user 2026-09-25):
    # judul situs & data lain di bawah memakai hasilnya. Tersimpan per isi form; gagal/timeout =
    # read_client_form kembali ke pengurai pola.
    try:
        subprocess.run([sys.executable, str(SCRIPTS_DIR / 'baca-form-claude'), domain],
                       capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        pass
    # derive defaults; ssh target from server store (managed via /server/ panel), fallback static
    labels = domain.split('.')[0]
    # Username dari catatan hosting diutamakan; kalau tidak ada, 7 huruf awal domain
    # (keputusan user 2026-10-09).
    da_user = ''
    # Catatan hosting dari tim ada di folder Drive sebagai <domain>.txt dan memuat
    # username DirectAdmin asli, yang tidak selalu sama dengan huruf awal
    # domain (surya-media-berita.com -> suryame1).
    for nf in [folder_klien(domain) / f'{domain}.txt',
               src / 'notes-credentials.txt', src / 'notes.txt',
               folder / 'notes-credentials.txt', folder / 'notes.txt',
               src / 'FORM ISIAN WEBSITE - paket g.doc']:
        try:
            if nf.is_file():
                txt = nf.read_text(errors='replace')
                m = re.search(r'^\s*(?:user ?name|user|login)\s*[:=]\s*([A-Za-z0-9_-]+)', txt, re.I | re.M)
                if m:
                    # Username asli akun dipakai utuh (bukan dipotong 8): potongan
                    # tidak akan pernah cocok dengan akun yang dibuat PM.
                    da_user = re.sub(r'[^a-z0-9]', '', m.group(1).lower())[:16]
                    break
        except: pass
    if not da_user:
        # Username DirectAdmin hanya huruf & angka. Tanda hubung dari domain
        # (surya-media-berita.com -> "surya-m") ikut ke db_name dan ditolak installer.
        da_user = re.sub(r'[^a-z0-9]', '', labels.lower())[:7] or 'admin'
    if not re.match(r'^[a-z_]', da_user):
        da_user = 'u' + da_user
    # Staging (deskripsi CRM "Kerjakan diweb velocity dl"): akun vdco di Kiya,
    # situs di velocitydeveloper.co/<domain>. Akun DA klien tidak dipakai.
    staging = diminta_staging(domain)
    if staging:
        da_user = STAGING_DA_USER
    srv = staging_target() if staging else default_target()
    target = srv['host']
    port = srv['port']
    if not re.match(r'^[0-9]+$', port) or not (1 <= int(port) <= 65535):
        port = '22'
    ssh_user = srv['user']
    admin_email = ''
    for notes in (src / 'notes-credentials.txt', folder / 'notes-credentials.txt'):
        if admin_email or not notes.is_file():
            continue
        for line in notes.read_text(errors='replace').splitlines():
            if '@' in line and ' ' not in line and not admin_email:
                cand = line.strip().strip('*').strip()
                if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', cand):
                    admin_email = cand
    labels_clean = re.sub(r'[^a-z0-9_]', '', labels.lower()) or 'site'
    # DirectAdmin ownership: DB must be prefixed with da_user + '_'  -> WHERE Db LIKE 'da_user\_%'
    # Untuk pendek, buang repetisi da_user di dalam domain: akademikariset -> ariset
    suffix = labels_clean
    # jika suffix mengandung da_user, ambil sisa setelahnya; jika tidak, potong 6-8 char unik dari tengah/akhir
    if suffix.startswith(da_user):
        suffix = suffix[len(da_user):].lstrip('_')
        if not suffix:
            suffix = 'wp'
    else:
        # akademikariset vs akademik -> ambil sisa unik 'ariset' (len label - len da_user)
        # pancarkannews vs pancarka -> 'nnews'
        # sungailanang vs sungaila -> 'nang'
        # agar pendek: ambil 6 char terakhir atau sisa
        if len(suffix) > len(da_user):
            suffix = suffix[len(da_user):].lstrip('_')
            if len(suffix) > 6:
                suffix = suffix[-6:]
        if not suffix:
            suffix = labels_clean[:6]
    if staging:
        # Semua situs staging berbagi akun vdco: awal nama domain lebih mudah dikenali
        # dan jarang bertabrakan dibanding 6 huruf terakhir (vdco_cybersum_wp).
        suffix = labels_clean
    if len(suffix) > 8:
        suffix = suffix[:8]
    # batasi panjang agar db_name <= 32 char
    max_suffix = 28 - len(da_user)  # reserve _ + suffix + _wp
    if len(suffix) > max_suffix:
        suffix = suffix[:max_suffix]
    db_suffix = suffix + '_wp' if not suffix.endswith('_wp') else suffix
    db_name = f'{da_user}_{db_suffix}'
    db_user = db_name  # samakan user dan db agar simpel; DA juga pakai 1 user per DB
    content = (
        f'target_host={target}\n'
        f'ssh_port={port}\n'
        f'ssh_user={ssh_user}\n'
        f'da_user={da_user}\n'
        f'domain={domain}\n'
        f'db_name={db_name}\n'
        f'db_user={db_user}\n'
        # WP admin = DA user; password-nya ditambahkan _sync_hosting_notes dari
        # catatan hosting PM (bukan file password bersama seperti dulu).
        f'admin_email={admin_email or ("admin@" + domain)}\n'
        f'site_title={_site_title_from_form((folder_klien(domain), src, folder), labels.replace("-", " ").title())}\n'
    )
    # Tanpa baris ini installer melewati pemasangan tema/plugin dan hasilnya
    # WordPress polos dengan tema bawaan.
    try:
        sync_packages()
    except Exception:
        pass  # API gagal: zip terakhir yang tersinkron tetap dipakai
    theme_pkg, addons_pkg = _velocity_packages()
    if addons_pkg:
        content += f'velocity_addons_pkg={addons_pkg}\n'
    if theme_pkg:
        content += f'velocity_theme_pkg={theme_pkg}\n'
    # Versi aturan palet tema FSE. Manifest baru memakai aturan terbaru; situs yang
    # sudah terpasang tidak punya baris ini sehingga tampilannya tidak ikut berubah
    # (permintaan user 2026-09-16: aturan kontras baru hanya untuk build berikutnya).
    content += 'velocity_palet_versi=2\n'
    if staging:
        content += (f'docroot=/home/{STAGING_DA_USER}/domains/{STAGING_DOMAIN}/public_html/{domain}\n'
                    f'site_url=https://{STAGING_DOMAIN}/{domain}\n')
    # Paket website dari CRM untuk laporan Telegram: situs yang sudah terpasang
    # tidak lagi muncul di antrean, jadi paketnya dicatat di manifest.
    paket = str((crm_projects().get(domain.lower()) or {}).get('paket') or '')
    if re.match(r'^[\w .&()/+-]{1,60}$', paket):
        content += f'paket={paket}\n'
    tmp = manifest.with_suffix('.txt.tmp')
    tmp.write_text(content)
    os.chmod(tmp, 0o640)
    os.replace(tmp, manifest)
    _ensure_secrets(domain)
    _sync_hosting_notes(domain, manifest, allow_regenerate=False)
    return {'generated': True, 'manifest': str(manifest)}, None


def _runner_hidup(domain: str):
    """Runner domain ini masih jalan walau tidak tercatat di _running (layanan di-restart
    sesudah run dimulai; runner kini hidup di scope systemd sendiri)."""
    try:
        r = subprocess.run(['pgrep', '-f', f'installer-runner {re.escape(domain)}$'],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def start_run(domain: str, mode: str):
    """Start installer-runner for domain. mode: dry-run | apply | finish | maintenance.

    finish merapikan ulang situs yang sudah terpasang (konten bersih, aset klien,
    pemeriksaan akhir) tanpa memasang ulang WordPress dan tanpa notifikasi.
    maintenance hanya menyalakan maintenance mode velocity-addons (langkah terakhir
    apply) untuk situs yang terpasang sebelum langkah itu ada.
    child-theme hanya memasang & mengaktifkan child theme (dicocokkan dari API atau
    digenerate bernama project untuk Paket G) di situs yang sudah terpasang.
    audit hanya membaca keadaan situs terpasang (scripts/site-audit) dan tidak
    mengubah apa pun, termasuk status instalasi."""
    if not DOMAIN_RE.match(domain) or '/' in domain or '..' in domain:
        return None, 'invalid_domain'
    # Host server bukan project: menyembunyikannya dari daftar saja tidak cukup,
    # karena POST /api/installer/run menerima domain apa pun. Semua mode ditolak —
    # apply di sini berarti memasang WordPress menimpa server host sendiri.
    if domain.lower() in bukan_project():
        return None, 'bukan_project'
    if mode not in ('dry-run', 'apply', 'finish', 'maintenance', 'child-theme', 'audit', 'redesign'):
        return None, 'invalid_mode'
    if mode in ('finish', 'maintenance', 'child-theme', 'audit', 'redesign') and not ssh_key_file():
        return None, 'ssh_key_missing'
    manifest = ROOT / domain / f'{domain}.txt'
    if not manifest.is_file():
        return None, 'manifest_not_found'
    proc = _running.get(domain)
    if (proc is not None and proc.poll() is None) or _runner_hidup(domain):
        return None, 'already_running'
    # Deskripsi CRM & catatan hosting PM bisa ditulis atau diubah setelah manifest dibuat.
    if mode in ('dry-run', 'apply'):
        for change in _sync_staging(domain, manifest):
            print(json.dumps({'event': 'staging_sync', 'domain': domain, 'change': change}), flush=True)
    for change in _sync_hosting_notes(domain, manifest):
        print(json.dumps({'event': 'hosting_notes_sync', 'domain': domain, 'change': change}), flush=True)
    ok, detail = validate_manifest(manifest)
    if not ok:
        return None, 'manifest_invalid:' + detail
    if proc is not None and proc.poll() is None:
        return None, 'already_running'
    STATE.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, INSTALL_MODE=mode)
    # Dry-run kini ikut memeriksa server tujuan, jadi ia juga butuh kunci SSH —
    # bukan hanya apply seperti sebelumnya.
    if ssh_key_file():
        env['WP_INSTALL_SSH_KEY_FILE'] = str(ssh_key_file())
    if mode == 'apply':
        if not ssh_key_file():
            return None, 'ssh_key_missing'
        env['WP_INSTALL_DB_PASSWORD_FILE'] = str(SECRETS / f'db_password_{domain}.txt')
        env['WP_INSTALL_ADMIN_PASSWORD_FILE'] = str(SECRETS / f'admin_password_{domain}.txt')
        for f in (env['WP_INSTALL_DB_PASSWORD_FILE'], env['WP_INSTALL_ADMIN_PASSWORD_FILE']):
            if not Path(f).is_file():
                return None, 'secret_file_missing:' + Path(f).name
    logf = open(STATE / f'{domain}.log', 'a')
    # Runner dijalankan di scope systemd sendiri: dengan KillMode=control-group, restart
    # layanan ini (sering dilakukan sesi lain) dulu ikut membunuh run yang sedang jalan
    # (cybersumatra.com 2026-09-30, dua kali di tahap desain FSE). PID & env tetap sama.
    perintah = [str(RUNNER), domain]
    if shutil.which('systemd-run'):
        unit = f'installer-run-{re.sub(r"[^A-Za-z0-9.-]", "-", domain)}-{int(time.time())}'
        perintah = ['systemd-run', '--scope', '--quiet', '--collect', f'--unit={unit}'] + perintah
    try:
        p = subprocess.Popen(
            perintah,
            stdout=logf, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, env=env,
            start_new_session=True,
        )
    except OSError as e:
        logf.close()
        return None, 'spawn_failed:' + str(e)
    logf.close()
    _running[domain] = p
    return {'domain': domain, 'mode': mode, 'pid': p.pid}, 'started'


# --- Alur project Laravel (menu Installer > Laravel) ---
# Data, tahap, dan aksi ada di scripts/laravel_proyek.py (dipakai juga laravel-brief / laravel-agen).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import laravel_proyek  # noqa: E402

# --- AI Model Management ---

# ID model boleh memuat garis miring (permintaan user 2026-09-16): penyedia seperti
# OpenRouter/Together memakai nama berbentuk "vendor/model", mis. `meta-llama/llama-3-70b`.
# Ruas tidak boleh kosong dan `..` ditolak — id ikut masuk ke URL /api/ai/models/<id>/delete.
CLAUDE_MODEL_ALIAS = ('opus', 'sonnet', 'haiku')
AI_MODEL_ID_RE = re.compile(r'^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$')


def load_ai_models():
    """Load AI models configuration."""
    try:
        if AI_MODELS.is_file():
            return json.loads(AI_MODELS.read_text())
    except (OSError, ValueError):
        pass
    return {'models': [], 'default_provider': 'openai'}


def save_ai_models(data):
    """Save AI models configuration."""
    tmp = AI_MODELS.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2, default=str))
    os.chmod(tmp, 0o600)
    tmp.replace(AI_MODELS)


def add_ai_model(model_data):
    """Tambah atau perbarui model AI dari halaman /ai/.

    Saat memperbarui, API key kosong berarti tetap memakai key tersimpan: halaman tidak
    pernah menerima key asli, jadi form edit mengirim kosong kalau key tidak diganti."""
    model_id = str(model_data.get('id') or '')
    if not AI_MODEL_ID_RE.match(model_id) or '..' in model_id:
        return None, 'invalid_id'
    data = load_ai_models()
    models = data.get('models', [])
    lama = next((m for m in models if m.get('id') == model_id), None)
    if model_data.get('provider') == 'claude_code':
        # Agen Claude Code: tanpa endpoint & API key, dipanggil lewat CLI `claude -p`
        # (scripts/ai-content-generator.py claude_call). Model = alias CLI.
        nama = str(model_data.get('model') or '').strip() or 'opus'
        if nama not in CLAUDE_MODEL_ALIAS:
            return None, 'model_claude_tidak_dikenal'
        baru = {k: v for k, v in (lama or {}).items() if k not in ('endpoint', 'api_key')}
        baru.update({'id': model_id, 'name': model_id, 'provider': 'claude_code', 'model': nama,
                     'is_default': bool((lama or {}).get('is_default'))})
    else:
        endpoint = str(model_data.get('endpoint') or '').strip().rstrip('/')
        if not re.match(r'^https?://\S+$', endpoint):
            return None, 'endpoint_required'
        api_key = str(model_data.get('api_key') or '').strip() or (lama or {}).get('api_key', '')
        if not api_key:
            return None, 'api_key_required'
        baru = {k: v for k, v in (lama or {}).items() if k != 'provider'}
        baru.update({'id': model_id, 'name': model_id, 'endpoint': endpoint, 'api_key': api_key,
                     'model': str(model_data.get('model') or '').strip() or model_id,
                     'is_default': bool((lama or {}).get('is_default'))})
    if lama:
        models[models.index(lama)] = baru
    else:
        models.append(baru)
    if model_data.get('is_default') or len(models) == 1:
        for m in models:
            m['is_default'] = (m['id'] == model_id)
    data['models'] = models
    save_ai_models(data)
    return baru, None


def remove_ai_model(model_id):
    """Hapus model. Fungsi yang memakainya kembali ke model default; kalau yang dihapus
    model default, default pindah ke model pertama yang tersisa."""
    data = load_ai_models()
    models = data.get('models', [])
    sisa = [m for m in models if m['id'] != model_id]
    if len(sisa) == len(models):
        return False
    if sisa and not any(m.get('is_default') for m in sisa):
        sisa[0]['is_default'] = True
    data['models'] = sisa
    data['pemakaian'] = {k: v for k, v in (data.get('pemakaian') or {}).items() if v and v != model_id}
    save_ai_models(data)
    return True


def set_default_ai_model(model_id):
    """Set default AI model."""
    data = load_ai_models()
    models = data.get('models', [])
    found = False
    for m in models:
        if m['id'] == model_id:
            m['is_default'] = True
            found = True
        else:
            m['is_default'] = False
    if not found:
        return False
    save_ai_models(data)
    return True


def model_desain_claude():
    try:
        model = json.loads(DESAIN_CLAUDE_MODEL.read_text()).get('model') or ''
    except (OSError, ValueError):
        model = ''
    return f"agen Claude Code ({model or 'Opus terbaru'})"


def saklar_aktif(kunci, bawaan):
    """True bila saklar agen Claude (mis. DESAIN_CLAUDE=1) menyala di env autopilot."""
    nilai = bawaan
    try:
        for baris in AUTOPILOT_ENV.read_text().splitlines():
            if baris.strip().startswith(kunci + '='):
                nilai = baris.split('=', 1)[1].strip()
    except OSError:
        pass
    return nilai == '1'


def set_ai_pemakaian(peran, model_id):
    """Pilih model untuk satu fungsi installer (AI_PERAN); model_id kosong = ikut model default."""
    if peran not in {kunci for kunci, _, _ in AI_PERAN}:
        return None, 'peran_tidak_dikenal'
    data = load_ai_models()
    model_id = str(model_id or '')
    if model_id and not any(m.get('id') == model_id for m in data.get('models', [])):
        return None, 'model_not_found'
    if peran == 'judi' and model_id and not next(m for m in data['models'] if m.get('id') == model_id).get('endpoint'):
        return None, 'model_tanpa_endpoint'  # server_judi memanggil /chat/completions langsung
    pemakaian = {k: v for k, v in (data.get('pemakaian') or {}).items() if v}
    if model_id:
        pemakaian[peran] = model_id
    else:
        pemakaian.pop(peran, None)
    data['pemakaian'] = pemakaian
    save_ai_models(data)
    return pemakaian, None


def test_claude_model(model):
    """Uji model agen Claude Code dengan satu pesan pendek lewat CLI."""
    claude = next((c for c in ('/root/.local/bin/claude', '/usr/local/bin/claude') if Path(c).is_file()), 'claude')
    env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_DEFAULT_OPUS_MODEL'}
    kunci = SECRETS / 'anthropic_api_key'
    if kunci.is_file() and kunci.read_text().strip():
        env['ANTHROPIC_API_KEY'] = kunci.read_text().strip()
    try:
        r = subprocess.run([claude, '-p', '--model', model.get('model') or 'opus', '--output-format', 'json',
                            '--no-session-persistence', '--tools', ''],
                           input='Balas hanya dengan kata: OK', capture_output=True, text=True,
                           timeout=90, env=env, cwd='/tmp', check=False)
        hasil = json.loads(r.stdout or '{}')
    except subprocess.TimeoutExpired:
        return None, 'test_failed:timeout'
    except (OSError, ValueError) as e:
        return None, f'test_failed:{type(e).__name__}'
    if hasil.get('is_error') or not hasil.get('result'):
        return None, 'test_failed:' + str(hasil.get('result') or r.stderr or 'kosong')[:300]
    return {'response': f"{hasil['result']} · {', '.join(hasil.get('modelUsage') or {})}"}, None


def test_ai_model(model_id):
    """Test AI model by making a simple API call."""
    data = load_ai_models()
    model = None
    for m in data.get('models', []):
        if m['id'] == model_id:
            model = m
            break
    if not model:
        return None, 'model_not_found'
    if model.get('provider') == 'claude_code':
        return test_claude_model(model)

    api_key = model.get('api_key', '')
    if not api_key:
        return None, 'api_key_missing'
    
    endpoint = model.get('endpoint', 'https://api.openai.com/v1')
    model_name = model.get('model', '')
    
    try:
        payload = json.dumps({
            'model': model_name,
            'messages': [{'role': 'user', 'content': 'Say "OK" if you can hear me.'}],
            'max_tokens': 10
        }).encode()
        req = urllib.request.Request(
            f'{endpoint}/chat/completions',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            # Some providers return SSE-style tail like "data: [DONE]" or extra JSON lines
            # Try to extract first valid JSON object
            text = raw.decode('utf-8', errors='replace').strip()
            result = None
            # Try direct parse
            try:
                result = json.loads(text)
            except ValueError:
                # Try to find first {...} block
                import re as _re
                m = _re.search(r'\{.*\}', text, _re.DOTALL)
                if m:
                    try:
                        result = json.loads(m.group(0))
                    except: pass
                # SSE fallback: look for data: {...}
                if result is None:
                    for line in text.splitlines():
                        line=line.strip()
                        if line.startswith('data:'):
                            payload_str=line[5:].strip()
                            if payload_str and payload_str != '[DONE]':
                                try:
                                    result = json.loads(payload_str)
                                    break
                                except: continue
            if result is None:
                # last attempt: truncate before "data:" if present
                if 'data:' in text:
                    try:
                        result = json.loads(text.split('data:')[0].strip())
                    except: pass
            if result is None:
                return None, f'test_failed:unparseable_response:{text[:400]}'
            if isinstance(result, dict) and 'error' in result:
                err = result.get('error')
                if isinstance(err, dict): err = err.get('message') or str(err)
                return None, f'provider_error:{err}'
            if 'choices' in result:
                return {'status': 'ok', 'response': result['choices'][0]['message']['content']}, None
            return None, f'unexpected_response:{str(result)[:400]}'
    except Exception as e:
        return None, f'test_failed:{e}'


# --- AI Content Generation ---

def start_ai_content(domain: str, mode: str = 'dry-run'):
    """Start AI content generation for domain."""
    if not DOMAIN_RE.match(domain) or '/' in domain or '..' in domain:
        return None, 'invalid_domain'
    if mode not in ('dry-run', 'apply'):
        return None, 'invalid_mode'
    manifest = ROOT / domain / f'{domain}.txt'
    if not manifest.is_file():
        return None, 'manifest_not_found'
    
    # Check if AI is already running for this domain
    proc = _ai_running.get(domain)
    if proc is not None and proc.poll() is None:
        return None, 'already_running'
    
    # Check if AI script exists
    if not AI_SCRIPT.is_file():
        return None, 'ai_script_missing'
    
    # Check if models are configured
    ai_data = load_ai_models()
    if not ai_data.get('models'):
        return None, 'no_ai_models_configured'
    
    STATE.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, INSTALL_MODE=mode, VELOCITY_DOMAIN=domain,
               VELOCITY_RUN_ID=time.strftime('%Y%m%d-%H%M%S') + f'-ai-{mode}')
    if mode == 'apply':
        if not ssh_key_file():
            return None, 'ssh_key_missing'
        env['WP_INSTALL_SSH_KEY_FILE'] = str(ssh_key_file())
    
    logf = open(STATE / f'{domain}.ai.log', 'a')
    try:
        p = subprocess.Popen(
            [str(AI_SCRIPT), str(manifest)],
            stdout=logf, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, env=env,
            start_new_session=True,
        )
    except OSError as e:
        logf.close()
        return None, 'spawn_failed:' + str(e)
    logf.close()
    _ai_running[domain] = p
    return {'domain': domain, 'mode': mode, 'pid': p.pid}, 'started'


def get_ai_content_status(domain: str):
    """Get AI content generation status for domain."""
    proc = _ai_running.get(domain)
    if proc is not None:
        if proc.poll() is None:
            return {'status': 'running', 'pid': proc.pid}
        else:
            del _ai_running[domain]
            return {'status': 'completed', 'exit_code': proc.poll()}
    
    # Check if generated content exists
    pages_file = AI_GENERATED / f'{domain}-pages.json'
    articles_file = AI_GENERATED / f'{domain}-articles.json'
    
    result = {'status': 'idle'}
    if pages_file.is_file():
        result['pages_generated'] = True
        result['pages_file'] = str(pages_file)
    if articles_file.is_file():
        result['articles_generated'] = True
        result['articles_file'] = str(articles_file)
    
    return result


def ai_token_usage():
    """Jumlah token AI per domain, dirinci per run installer dan per fungsi."""
    per_domain = {}
    try:
        baris_semua = AI_USAGE.read_text(errors='replace').splitlines()
    except OSError:
        baris_semua = []
    # Sumber (permintaan user 2026-09-18): `endpoint` = model dari endpoint custom halaman /ai/
    # (satu baris = satu request), `claude` = agen desain Claude Code (satu baris per model per
    # sesi agen; jumlah request API di kolom `permintaan`, token cache & biaya dirinci).
    SUMBER_KOSONG = lambda: {'panggilan': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                             'input_tokens': 0, 'cache_read_tokens': 0, 'cache_creation_tokens': 0,
                             'biaya_usd': 0.0, 'model': set()}
    kosong = lambda: {'panggilan': 0, 'gagal': 0, 'prompt_tokens': 0, 'completion_tokens': 0,
                      'total_tokens': 0, 'per_peran': {}, 'mulai': '', 'terakhir': '',
                      'per_sumber': {}}

    def tambah(t, b):
        n = int(b.get('permintaan') or 1)
        t['panggilan'] += n
        t['gagal'] += 0 if b.get('ok') else 1
        for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
            t[k] += int(b.get(k) or 0)
        sumber = t['per_sumber'].setdefault(b.get('sumber') or 'endpoint', SUMBER_KOSONG())
        sumber['panggilan'] += n
        for k in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'input_tokens', 'cache_read_tokens',
                  'cache_creation_tokens'):
            sumber[k] += int(b.get(k) or 0)
        sumber['biaya_usd'] += float(b.get('biaya_usd') or 0)
        sumber['model'].add(b.get('model') or b.get('model_id') or '-')
        peran = b.get('peran') or '-'
        t['per_peran'][peran] = t['per_peran'].get(peran, 0) + int(b.get('total_tokens') or 0)
        ts = str(b.get('ts') or '')
        t['mulai'] = min(t['mulai'] or ts, ts)
        t['terakhir'] = max(t['terakhir'], ts)

    for s in baris_semua:
        try:
            b = json.loads(s)
        except ValueError:
            continue
        domain = b.get('domain') or '(tanpa domain)'
        d = per_domain.setdefault(domain, dict(kosong(), domain=domain, runs={}))
        tambah(d, b)
        run_id = b.get('run') or '(di luar installer-runner)'
        r = d['runs'].setdefault(run_id, dict(kosong(), run=run_id, mode=b.get('mode') or '', model=set()))
        tambah(r, b)
        if b.get('ok'):
            r['model'].add(b.get('model') or b.get('model_id') or '-')

    def rapikan_sumber(t):
        for v in t['per_sumber'].values():
            v['model'] = sorted(v['model'])
            v['biaya_usd'] = round(v['biaya_usd'], 4)

    hasil = []
    total = kosong()
    for d in per_domain.values():
        runs = sorted(d.pop('runs').values(), key=lambda r: r['terakhir'], reverse=True)
        for r in runs:
            r['model'] = sorted(r['model'])
            rapikan_sumber(r)
        d['runs'] = runs
        for k in ('panggilan', 'gagal', 'prompt_tokens', 'completion_tokens', 'total_tokens'):
            total[k] += d[k]
        for nama, v in d['per_sumber'].items():
            tv = total['per_sumber'].setdefault(nama, SUMBER_KOSONG())
            for k, x in v.items():
                tv[k] = tv[k] | x if k == 'model' else tv[k] + x
        rapikan_sumber(d)
        hasil.append(d)
    hasil.sort(key=lambda d: d['terakhir'], reverse=True)
    rapikan_sumber(total)
    for k in ('per_peran', 'mulai', 'terakhir'):
        total.pop(k)
    return {'domains': hasil, 'total': total, 'file': str(AI_USAGE)}


# --- packages dari API Velocity ---
# Permintaan user 2026-09-18: paket tidak lagi dikelola (upload/URL/hapus) di halaman
# /packages/. Tema induk `velocity` & plugin `velocity-addons` yang dipasang installer
# disinkronkan dari API tema/plugin Velocity (sama seperti vd-store & child theme),
# jadi versi terbaru yang dirilis di sana otomatis terpakai.

VELOCITY_API = 'https://api.velocitydeveloper.co/api/v1'
# slug -> (jenis API, tipe paket installer)
PAKET_INSTALLER = {'velocity': ('themes', 'theme'), 'velocity-addons': ('plugins', 'plugin')}
PAKET_SINKRON_JEDA = 600  # detik antar-sinkron otomatis
# Rilis GitHub dibandingkan dengan API: versi yang lebih baru yang dipakai. API Velocity
# kadang tertinggal dari rilis (velocity-addons 2.3.1, 2026-09-22), padahal installer
# harus selalu memasang versi terbaru (permintaan user 2026-09-22).
PAKET_GITHUB = {'velocity-addons': 'Velocity-Developer/velocity-addons', 'velocity': 'Velocity-Developer/velocity'}
GITHUB_TOKEN_FILE = Path(os.environ.get('WP_INSTALL_GITHUB_TOKEN_FILE') or '/etc/velocity/secrets/github_token')
_paket_lock = threading.Lock()
_paket_state = {'at': 0.0, 'api': {}, 'error': ''}


def load_packages():
    try:
        if PACKAGES_META.is_file():
            data = json.loads(PACKAGES_META.read_text())
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        pass
    return {}


def save_packages(pkgs):
    tmp = PACKAGES_META.with_suffix('.tmp')
    tmp.write_text(json.dumps(pkgs, indent=2, default=str))
    os.chmod(tmp, 0o600)
    tmp.replace(PACKAGES_META)


def velocity_api_list(jenis):
    """Daftar tema/plugin dari API Velocity. Header signature = md5 tanggal WIB.
    API berpaginasi (bawaan 15/halaman; tema 71 per 2026-10-03) -> ikuti meta.last_page,
    kalau tidak hanya halaman 1 yang terbaca."""
    tanggal = time.strftime('%d%m%Y', time.gmtime(time.time() + 7 * 3600))
    headers = {'User-Agent': 'velocity-installer/1.0', 'Accept': 'application/json',
               'signature': hashlib.md5(tanggal.encode()).hexdigest()}
    hasil, halaman, terakhir = [], 1, 1
    while halaman <= min(terakhir, 50):
        req = urllib.request.Request(f'{VELOCITY_API}/{jenis}?per_page=100&page={halaman}', headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.load(resp)
        data = body.get('data')
        if not isinstance(data, list):
            raise ValueError('data_api_tidak_valid')
        hasil += [x for x in data if isinstance(x, dict) and x.get('slug')]
        try:
            terakhir = int((body.get('meta') or {}).get('last_page') or 1)
        except (TypeError, ValueError):
            terakhir = 1
        halaman += 1
    return hasil


def _versi_tuple(v):
    return tuple(int(x) for x in re.findall(r'\d+', str(v or ''))[:4]) or (0,)


def github_rilis_terbaru(slug):
    """(versi, url_zip) rilis terbaru di GitHub, atau None. Aset zip pertama yang dipakai."""
    repo = PAKET_GITHUB.get(slug)
    if not repo:
        return None
    headers = {'User-Agent': 'velocity-installer/1.0', 'Accept': 'application/vnd.github+json'}
    try:
        token = GITHUB_TOKEN_FILE.read_text().strip()
    except OSError:
        token = ''
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(f'https://api.github.com/repos/{repo}/releases/latest', headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.load(resp)
    aset = next((a for a in d.get('assets') or [] if str(a.get('name', '')).endswith('.zip')), None)
    if not aset or not str(aset.get('browser_download_url', '')).startswith('https://'):
        return None
    return str(d.get('tag_name') or '').lstrip('vV'), aset['browser_download_url']


def _zip_paket_valid(path, slug, tipe):
    try:
        with zipfile.ZipFile(path) as z:
            nama = z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False
    if tipe == 'theme':
        return f'{slug}/style.css' in nama
    return f'{slug}/{slug}.php' in nama


def _unduh_paket(item, slug, tipe):
    url = item.get('package_file_url') or item.get('package_external_url') or ''
    if not url.startswith('https://'):
        raise ValueError('url_paket_kosong')
    tujuan = PACKAGES_DIR / f'{slug}.zip'
    sementara = PACKAGES_DIR / f'.{slug}.zip.part'
    req = urllib.request.Request(url, headers={'User-Agent': 'velocity-installer/1.0'})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read(200 * 1024 * 1024 + 1)
    if len(data) > 200 * 1024 * 1024:
        raise ValueError('file_too_large')
    sementara.write_bytes(data)
    if not _zip_paket_valid(sementara, slug, tipe):
        sementara.unlink(missing_ok=True)
        raise ValueError('zip_tidak_berisi_' + slug)
    os.chmod(sementara, 0o644)
    sementara.replace(tujuan)
    return url, len(data)


def sync_packages(force=False):
    """Samakan zip tema/plugin installer dengan versi di API. Gagal -> zip lama tetap
    dipakai. Dijeda PAKET_SINKRON_JEDA detik kecuali force."""
    with _paket_lock:
        if not force and time.time() - _paket_state['at'] < PAKET_SINKRON_JEDA:
            return _paket_state
        api, galat = {}, []
        for jenis in ('themes', 'plugins'):
            try:
                api[jenis] = velocity_api_list(jenis)
            except Exception as e:
                galat.append(f'{jenis}: {e}')
        pkgs = load_packages()
        for slug, (jenis, tipe) in PAKET_INSTALLER.items():
            item = next((x for x in api.get(jenis, []) if x.get('slug') == slug), None)
            if not item and jenis in api:
                galat.append(f'{slug}: tidak ada di API')
            calon = []  # (versi, sumber, item unduhan)
            if item:
                calon.append((str(item.get('version') or '').strip(), 'api', item))
            try:
                gh = github_rilis_terbaru(slug)
            except Exception as e:
                gh = None
                galat.append(f'{slug}: github {e}')
            if gh and gh[0]:
                calon.append((gh[0], 'github', {'package_external_url': gh[1], 'name': (item or {}).get('name')}))
            if not calon:
                continue
            # Versi tertinggi menang; seri -> API (sumber resmi) didahulukan.
            versi, sumber, pilih = max(calon, key=lambda c: (_versi_tuple(c[0]), c[1] == 'api'))
            lama = pkgs.get(slug) or {}
            zip_ada = _zip_paket_valid(PACKAGES_DIR / f'{slug}.zip', slug, tipe)
            if zip_ada and lama.get('source') in ('api', 'github') and _versi_tuple(lama.get('version')) >= _versi_tuple(versi):
                continue
            try:
                url, size = _unduh_paket(pilih, slug, tipe)
            except Exception as e:
                galat.append(f'{slug}: {e}')
                continue
            pkgs[slug] = {'slug': slug, 'type': tipe, 'name': pilih.get('name') or slug,
                          'version': versi, 'source': sumber, 'url': url, 'size': size,
                          'added_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        # Paket di luar daftar installer (sisa unggahan manual) tidak dipakai lagi.
        pkgs = {k: v for k, v in pkgs.items() if k in PAKET_INSTALLER}
        save_packages(pkgs)
        _paket_state.update(at=time.time(), api=api, error='; '.join(galat))
        return _paket_state


def packages_view(force=False):
    state = sync_packages(force)
    pkgs = load_packages()
    return {
        'installer': [dict(pkgs.get(slug) or {'slug': slug, 'type': tipe},
                           ada=(PACKAGES_DIR / f'{slug}.zip').is_file())
                      for slug, (_, tipe) in PAKET_INSTALLER.items()],
        'themes': state['api'].get('themes', []),
        'plugins': state['api'].get('plugins', []),
        'synced_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(state['at'])) if state['at'] else '',
        'error': state['error'],
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, obj, code=200):
        body = json.dumps(obj, separators=(',', ':')).encode()
        # Lewat tunnel Cloudflare, JSON besar (hasil scan CMS 2–3,5 MB) terasa lambat tanpa kompresi (±8× lebih kecil)
        gz = len(body) > 2048 and 'gzip' in (self.headers.get('Accept-Encoding') or '')
        if gz:
            body = gzip.compress(body, 5)
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        if gz:
            self.send_header('Content-Encoding', 'gzip')
        self.send_header('Vary', 'Accept-Encoding')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _preview_setuju(self, parsed, payload):
        """Tombol "Setuju" klien di halaman preview velocity.ai.id (publik, tanpa login): hanya kode preview
        acak yang dikirim PM ke klien yang bisa dipakai (laravel_proyek.setuju_klien)."""
        kode = (parse_qs(parsed.query).get('kode') or [''])[0]
        try:
            self._send_json(laravel_proyek.setuju_klien(kode, payload, rate_ip(self)))
        except ValueError as e:
            self._send_json({'error': str(e)}, laravel_proyek.KODE_GALAT.get(str(e), 400))

    def do_GET(self):
        ip = client_ip(self) or 'unknown'
        parsed = urlparse(self.path)
        path = parsed.path
        # Bagan proses /installer/ membaca satu domain tiap 2-3 detik selama run berjalan
        # (satu berkas state + log): dikecualikan dari batas 30 req/60s supaya pantauan
        # realtime tidak berhenti karena 429. Semua endpoint lain tetap dibatasi.
        baca_bagan = path == '/api/installer' and 'domain' in parse_qs(parsed.query)
        # Halaman project Laravel memantau log & status tiap 2-3 detik selama agen/installer berjalan
        baca_bagan = baca_bagan or path.startswith('/api/laravel/p/')
        if not baca_bagan and not _lolos_batas(self):
            self._send_json({'error': 'rate_limited'}, 429)
            return

        if path == '/health':
            self._send_json({'status': 'ok'})
            return
        if path == '/api/preview-setuju':
            self._preview_setuju(parsed, None)
            return
        if path == '/api/servers':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(servers_view())
            return
        if path == '/api/servers/resource':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(server_resource('segar' in parse_qs(parsed.query)))
            return
        if path == '/api/servers/live':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(server_live((parse_qs(parsed.query).get('server') or [None])[0]))
            return
        if path == '/api/servers/riwayat':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            q = parse_qs(parsed.query, keep_blank_values=True)
            self._send_json(server_riwayat((q.get('rentang') or ['24j'])[0], (q.get('server') or [None])[0]))
            return
        if path in ('/api/servers/firewall', '/api/servers/firewall/cek', '/api/servers/firewall/riwayat', '/api/servers/firewall/log', '/api/servers/firewall/waf'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            q = parse_qs(parsed.query)
            if path == '/api/servers/firewall':
                self._send_json(server_firewall('segar' in q))
            elif path == '/api/servers/firewall/cek':
                self._send_json(firewall_cek((q.get('ip') or [''])[0]))
            elif path in ('/api/servers/firewall/log', '/api/servers/firewall/waf'):
                self._send_json(firewall_log((q.get('server') or ['semua'])[0], (q.get('hari') or ['1'])[0], path.rsplit('/', 1)[1]))
            else:
                self._send_json(firewall_riwayat())
            return
        if path in ('/api/servers/antivirus', '/api/servers/antivirus/scan', '/api/servers/antivirus/riwayat', '/api/servers/antivirus/baca'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            q = parse_qs(parsed.query)
            if path == '/api/servers/antivirus':
                self._send_json({**server_antivirus('segar' in q), 'aman': _aman_baca(), 'jadwal': _antivirus_jadwal_baca(),
                                 'realtime': _realtime_baca(), 'hitam': _hitam_baca(),
                                 'sidik_agen': _sidik_agen(), 'rt_setelan': _rt_setelan_baca(),
                                 'jam_jadwal': '%02d:%02d' % ANTIVIRUS_JAM_JADWAL})
            elif path == '/api/servers/antivirus/scan':
                sid = (q.get('id') or [''])[0]
                self._send_json(antivirus_scan_detail(sid) if sid else antivirus_scan_daftar())
            elif path == '/api/servers/antivirus/baca':
                self._send_json(antivirus_baca(*((q.get(k) or [''])[0] for k in ('server', 'path', 'id'))))
            else:
                self._send_json(antivirus_riwayat())
            return
        if path in ('/api/servers/guard/celah', '/api/servers/guard/insiden'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            if path == '/api/servers/guard/insiden':
                self._send_json(velocityguard.insiden())
            else:
                self._send_json(velocityguard.celah((parse_qs(parsed.query).get('tanggal') or [''])[0]))
            return
        if path == '/api/servers/lonjakan':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(server_lonjakan.riwayat((parse_qs(parsed.query).get('server') or [''])[0]))
            return
        if path == '/api/servers/judi':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(server_judi.ringkasan((parse_qs(parsed.query).get('server') or [''])[0]))
            return
        if path in ('/api/servers/cms', '/api/servers/cms/riwayat'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            q = parse_qs(parsed.query)
            if path == '/api/servers/cms/riwayat':
                self._send_json(server_cms.riwayat())
            elif q.get('server'):
                self._send_json(server_cms.detail(q['server'][0]))
            else:
                self._send_json(server_cms.ringkasan())
            return
        if path in ('/api/servers/limit', '/api/servers/limit/job'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            q = parse_qs(parsed.query)
            if path == '/api/servers/limit':
                self._send_json(server_limit('segar' in q))
            else:
                self._send_json(limit_job((q.get('id') or [''])[0]))
            return
        if path in ('/api/servers/bfm', '/api/servers/bfm/job', '/api/servers/bfm/riwayat'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            q = parse_qs(parsed.query)
            if path == '/api/servers/bfm':
                self._send_json(server_bfm('segar' in q))
            elif path == '/api/servers/bfm/job':
                self._send_json(bfm_job((q.get('id') or [''])[0]))
            else:
                self._send_json(bfm_riwayat())
            return
        if path in ('/api/servers/waf', '/api/servers/waf/aturan', '/api/servers/waf/job', '/api/servers/waf/riwayat'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            q = parse_qs(parsed.query)
            if path == '/api/servers/waf':
                self._send_json(server_waf('segar' in q))
            elif path == '/api/servers/waf/aturan':
                self._send_json(velocity_waf.daftar_aturan())
            elif path == '/api/servers/waf/job':
                self._send_json(waf_job((q.get('id') or [''])[0]))
            else:
                self._send_json(waf_riwayat())
            return
        if path == '/api/servers/monitor':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(server_monitor('segar' in parse_qs(parsed.query)))
            return
        if path == '/api/laravel' or path.startswith('/api/laravel/'):
            if not _is_local_net(ip):
                self._send_json({'error': 'forbidden'}, 403)
                return
            m = re.fullmatch(r'/api/laravel/p/(project-\d{3,})/contoh/(.+)', path)
            if m:
                # Contoh tampilan (mockup HTML) untuk iframe pratinjau di halaman project
                berkas = laravel_proyek.path_contoh(m.group(1), m.group(2))
                if not berkas:
                    self._send_json({'error': 'tidak_ada'}, 404)
                    return
                data = berkas.read_bytes()
                jenis = mimetypes.guess_type(berkas.name)[0] or 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-Type', jenis + ('; charset=utf-8' if jenis == 'text/html' else ''))
                self.send_header('Content-Security-Policy',
                                 "default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                                 "font-src https://fonts.gstatic.com data:; script-src 'unsafe-inline' https://cdn.jsdelivr.net")
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            m = re.fullmatch(r'/api/laravel/p/(project-\d{3,})/(dokumen|rangkuman\.docx)', path)
            if m:
                # Unduh / buka dokumen klien yang diunggah di tahap Brief, atau Word Rangkuman Website Konsep
                if m.group(2) == 'dokumen':
                    berkas = laravel_proyek.path_dok(m.group(1), (parse_qs(parsed.query).get('nama') or [''])[0])
                    nama = berkas.name if berkas else ''
                else:
                    berkas, nama = laravel_proyek.path_rangkuman(m.group(1)) or (None, '')
                if not berkas:
                    self._send_json({'error': 'tidak_ada'}, 404)
                    return
                data = berkas.read_bytes()
                jenis = mimetypes.guess_type(berkas.name)[0] or 'application/octet-stream'
                tampil = 'inline' if jenis.startswith('image/') or jenis == 'application/pdf' else 'attachment'
                self.send_response(200)
                self.send_header('Content-Type', jenis)
                self.send_header('Content-Disposition', f"{tampil}; filename*=UTF-8''{urllib.parse.quote(nama)}")
                self.send_header('Content-Security-Policy', "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'")
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            kode, obj = laravel_proyek.handle('GET', path, parsed.query, None)
            self._send_json(obj, kode)
            return
        if path == '/api/installer/susulan':
            # Laporan scripts/audit-susulan: situs jadi yang belum ikut aturan terbaru (hanya dibaca).
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            try:
                self._send_json(json.loads((STATE / 'audit-susulan.json').read_text()))
            except (OSError, ValueError):
                self._send_json({'waktu': '', 'jumlah': 0, 'perlu_susulan': 0, 'situs': []})
            return
        if path == '/api/installer':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            # ?domain=<domain>: satu baris untuk bagan proses di halaman /installer/. Domain yang
            # sudah terpasang hilang dari antrean di bawah, padahal bagan tetap perlu status akhir
            # run-nya; log lebih panjang supaya awal run apply penuh tidak terpotong.
            satu = (parse_qs(parsed.query).get('domain') or [''])[0].strip().lower()
            if satu:
                if not DOMAIN_RE.match(satu) or '/' in satu or '..' in satu:
                    self._send_json({'error': 'invalid_domain'}, 400)
                    return
                manifest = ROOT / satu / f'{satu}.txt'
                row = domain_row(satu, manifest if manifest.is_file() else None)
                try:
                    row['log'] = (STATE / f'{satu}.log').read_text(errors='replace').splitlines()[-1500:]
                except OSError:
                    pass
                # Paket menentukan cabang bagan (Paket G / F / Toko Online / lainnya).
                try:
                    row['paket'] = next((l.partition('=')[2].strip() for l in manifest.read_text(errors='replace').splitlines()
                                         if l.startswith('paket=')), '')
                except OSError:
                    row['paket'] = ''
                self._send_json({'domain_row': row})
                return
            self._send_json({'root': str(ROOT), 'domains': domains(), 'cronjobs': cronjobs(),
                             'local_ips': local_ips(), 'servers': load_servers(),
                             'default_target': default_target(), 'terakhir': run_terakhir()})
            return
        if path == '/api/packages':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(packages_view())
            return
        # AI endpoints
        if path == '/api/ai/models':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            data = load_ai_models()
            # mask api_key for listing
            safe = {'models': [], 'default_provider': data.get('default_provider', 'openai'),
                    'pemakaian': {k: v for k, v in (data.get('pemakaian') or {}).items() if v},
                    'peran': [{'kunci': k, 'label': label, 'script': script} for k, label, script in AI_PERAN],
                    'peran_tetap': [{'kunci': k, 'label': label, 'script': script, 'model': model_desain_claude(),
                                     'aktif': saklar_aktif(saklar, bawaan)}
                                    for k, label, script, saklar, bawaan in AI_PERAN_TETAP]}
            for m in data.get('models', []):
                mm = dict(m)
                if mm.get('api_key'):
                    mm['api_key'] = '***'
                    mm['api_key_set'] = True
                safe['models'].append(mm)
            self._send_json(safe)
            return
        if path == '/api/ai/usage':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(ai_token_usage())
            return
        if path.startswith('/api/ai/content/'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            domain = path[len('/api/ai/content/'):]
            self._send_json(get_ai_content_status(domain))
            return
        self.send_error(404)

    def do_POST(self):
        ip = client_ip(self) or 'unknown'
        if not _lolos_batas(self):
            self._send_json({'error': 'rate_limited'}, 429)
            return
        path = urlparse(self.path).path
        if path == '/api/preview-setuju':
            try:
                length = int(self.headers.get('Content-Length') or 0)
                payload = json.loads(self.rfile.read(min(max(length, 0), 4096)) or b'{}')
            except (ValueError, OSError):
                payload = None
            if not isinstance(payload, dict):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            self._preview_setuju(urlparse(self.path), payload)
            return
        # Check allowed paths (including dynamic ones)
        allowed_static = ('/api/installer/run', '/api/installer/generate', '/api/installer/claim',
                          '/api/installer/release', '/api/packages/sync',
                          '/api/servers', '/api/servers/delete', '/api/servers/default', '/api/servers/test',
                          '/api/servers/firewall/aksi',
                          '/api/servers/antivirus/scan', '/api/servers/antivirus/henti', '/api/servers/antivirus/aksi',
                          '/api/servers/antivirus/jadwal', '/api/servers/antivirus/realtime', '/api/servers/antivirus/cek_ulang',
                          '/api/servers/judi/setelan', '/api/servers/judi/nilai', '/api/servers/judi/aksi', '/api/servers/judi/henti', '/api/servers/judi/bersihkan',
                          '/api/servers/waf/aksi', '/api/servers/waf/setelan',
                          '/api/servers/bfm/aksi', '/api/servers/bfm/setelan',
                          '/api/servers/limit/aksi',
                          '/api/servers/cms/scan',
                          '/api/servers/cms/jadwal', '/api/servers/cms/perbaiki', '/api/servers/cms/perbaiki/cek',
                          '/api/servers/guard/celah/scan', '/api/servers/guard/insiden',
                          '/api/ai/models', '/api/ai/models/test', '/api/ai/models/set-default',
                          '/api/ai/content/run')
        is_allowed = path in allowed_static or path.startswith('/api/ai/models/') or path.startswith('/api/laravel/')
        if not is_allowed:
            self.send_error(404)
            return
        if not _check_auth(self):
            self._send_json({'error': 'unauthorized'}, 401)
            return
        # Nama pelaku ("oleh") di riwayat aksi = akun yang masuk ke dash.velocity.ai.id, bukan ketikan bebas.
        tolak = sesi_dash.pasang_pelaku(self)
        if tolak:
            self._send_json(tolak[1], tolak[0])
            return
        if path.startswith('/api/laravel/'):
            # Membuat user sistem, layanan, database, repo GitHub, dan menjalankan agen: hanya dari LAN
            # kantor/Tailscale, dan Origin wajib sama dengan Host supaya halaman lain tidak bisa memicunya.
            origin = urlparse(self.headers.get('Origin') or '').netloc
            if not _is_local_net(ip) or (origin and origin != (self.headers.get('Host') or '')):
                self._send_json({'error': 'forbidden'}, 403)
                return
            m = re.fullmatch(r'/api/laravel/p/(project-\d{3,})/unggah', path)
            if m:
                # Dokumen klien: badan = isi berkas mentah, nama & pengunggah di query string
                q = parse_qs(urlparse(self.path).query)
                try:
                    length = int(self.headers.get('Content-Length') or 0)
                except ValueError:
                    length = -1
                if length < 0 or length > laravel_proyek.DOK_MAKS:
                    self._send_json({'error': 'payload_too_large'}, 413)
                    return
                if not (laravel_proyek.folder(m.group(1)) / 'proyek.json').is_file():
                    self._send_json({'error': 'tidak_ada'}, 404)
                    return
                try:
                    obj = laravel_proyek.unggah_dok(m.group(1), (q.get('nama') or [''])[0], (q.get('oleh') or [''])[0],
                                                    self.rfile.read(length))
                    self._send_json(obj)
                except ValueError as e:
                    self._send_json({'error': str(e)}, laravel_proyek.KODE_GALAT.get(str(e), 400))
                return
            try:
                length = int(self.headers.get('Content-Length') or 0)
                if length > 1_000_000:
                    self._send_json({'error': 'payload_too_large'}, 413)
                    return
                payload = json.loads(self.rfile.read(length) or b'{}')
            except (ValueError, OSError):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            if not isinstance(payload, dict):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            kode, obj = laravel_proyek.handle('POST', path, '', payload)
            self._send_json(obj, kode)
            return
        if path == '/api/packages/sync':
            self._send_json(packages_view(force=True))
            return
        if path.startswith('/api/servers'):
            try:
                length = int(self.headers.get('Content-Length') or 0)
                payload = json.loads(self.rfile.read(length) or b'{}')
            except (ValueError, OSError):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            if not isinstance(payload, dict):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            if path == '/api/servers/test':
                self._send_json(server_test(payload))
                return
            if path == '/api/servers/firewall/aksi':
                # Mengubah firewall server produksi: Origin wajib sama dengan Host (bukan dipicu halaman lain)
                origin = urlparse(self.headers.get('Origin') or '').netloc
                if origin and origin != (self.headers.get('Host') or ''):
                    self._send_json({'error': 'forbidden'}, 403)
                    return
                obj, kode = firewall_aksi(payload)
                self._send_json(obj, kode)
                return
            if path.startswith('/api/servers/antivirus/'):
                # Scan & karantina di server produksi: Origin wajib sama dengan Host
                origin = urlparse(self.headers.get('Origin') or '').netloc
                if origin and origin != (self.headers.get('Host') or ''):
                    self._send_json({'error': 'forbidden'}, 403)
                    return
                fn = {'/api/servers/antivirus/scan': antivirus_scan_mulai, '/api/servers/antivirus/henti': antivirus_scan_henti,
                      '/api/servers/antivirus/aksi': antivirus_aksi, '/api/servers/antivirus/jadwal': antivirus_jadwal_atur,
                      '/api/servers/antivirus/realtime': antivirus_realtime_atur,
                      '/api/servers/antivirus/cek_ulang': antivirus_cek_ulang}[path]
                obj, kode = fn(payload)
                self._send_json(obj, kode)
                return
            if path.startswith('/api/servers/judi/'):
                # Suspend akun & karantina di server produksi: Origin wajib sama dengan Host
                origin = urlparse(self.headers.get('Origin') or '').netloc
                if origin and origin != (self.headers.get('Host') or ''):
                    self._send_json({'error': 'forbidden'}, 403)
                    return
                if path == '/api/servers/judi/nilai':
                    obj, kode = server_judi.nilai_mulai(payload, lambda sid: antivirus_scan_gabung(payload.get('server'))
                                                        if sid == 'semua' else antivirus_scan_detail(sid))
                else:
                    obj, kode = {'/api/servers/judi/setelan': server_judi.setelan_atur,
                                 '/api/servers/judi/henti': server_judi.henti,
                                 '/api/servers/judi/bersihkan': server_judi.bersihkan_riwayat}.get(path, server_judi.aksi)(payload)
                self._send_json(obj, kode)
                return
            if path in ('/api/servers/guard/celah/scan', '/api/servers/guard/insiden'):
                origin = urlparse(self.headers.get('Origin') or '').netloc
                if origin and origin != (self.headers.get('Host') or ''):
                    self._send_json({'error': 'forbidden'}, 403)
                    return
                obj, kode = (velocityguard.celah_mulai if path == '/api/servers/guard/celah/scan' else velocityguard.insiden_simpan)(payload)
                self._send_json(obj, kode)
                return
            if path in ('/api/servers/cms/scan', '/api/servers/cms/jadwal', '/api/servers/cms/perbaiki', '/api/servers/cms/perbaiki/cek'):
                # Scan hanya membaca server; perbaiki MENGUBAH situs klien (update plugin/tema/inti). Origin wajib = Host
                origin = urlparse(self.headers.get('Origin') or '').netloc
                if origin and origin != (self.headers.get('Host') or ''):
                    self._send_json({'error': 'forbidden'}, 403)
                    return
                obj, kode = {'/api/servers/cms/scan': server_cms.scan_mulai, '/api/servers/cms/jadwal': server_cms.jadwal_atur,
                             '/api/servers/cms/perbaiki': server_cms.perbaiki_mulai,
                             '/api/servers/cms/perbaiki/cek': server_cms.perbaiki_cek}[path](payload)
                self._send_json(obj, kode)
                return
            if path.startswith('/api/servers/bfm/'):
                # Pasang/copot mengubah csf.conf + regex.custom.pm dan me-restart lfd server produksi
                origin = urlparse(self.headers.get('Origin') or '').netloc
                if origin and origin != (self.headers.get('Host') or ''):
                    self._send_json({'error': 'forbidden'}, 403)
                    return
                obj, kode = (bfm_aksi if path == '/api/servers/bfm/aksi' else bfm_setelan)(payload)
                self._send_json(obj, kode)
                return
            if path == '/api/servers/limit/aksi':
                # Ganti preset = set-property cgroup semua user DA server produksi: Origin wajib sama dengan Host
                origin = urlparse(self.headers.get('Origin') or '').netloc
                if origin and origin != (self.headers.get('Host') or ''):
                    self._send_json({'error': 'forbidden'}, 403)
                    return
                obj, kode = limit_aksi(payload)
                self._send_json(obj, kode)
                return
            if path.startswith('/api/servers/waf/'):
                # Pasang/copot WAF me-restart LiteSpeed server produksi: Origin wajib sama dengan Host
                origin = urlparse(self.headers.get('Origin') or '').netloc
                if origin and origin != (self.headers.get('Host') or ''):
                    self._send_json({'error': 'forbidden'}, 403)
                    return
                obj, kode = (waf_aksi if path == '/api/servers/waf/aksi' else waf_setelan)(payload)
                self._send_json(obj, kode)
                return
            aksi = {'/api/servers': 'simpan', '/api/servers/delete': 'hapus',
                    '/api/servers/default': 'default'}[path]
            hasil, err, kode = server_mutasi(aksi, payload)
            self._send_json(hasil if hasil else {'error': err}, kode)
            return
        # AI Model Management
        if path == '/api/ai/models':
            try:
                length = int(self.headers.get('Content-Length') or 0)
                payload = json.loads(self.rfile.read(length) or b'{}')
            except (ValueError, OSError):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            result, err = add_ai_model(payload)
            if result is None:
                err_key = err.split(':')[0] if err else ''
                code = {'invalid_id': 400, 'endpoint_required': 400, 'api_key_required': 400}.get(err_key, 422)
                self._send_json({'error': err}, code)
                return
            safe_model = dict(result); safe_model['api_key'] = '***' if safe_model.get('api_key') else ''; safe_model['api_key_set'] = bool(result.get('api_key'))
            self._send_json({'status': 'ok', 'model': safe_model})
            return
        if path == '/api/ai/models/test':
            try:
                length = int(self.headers.get('Content-Length') or 0)
                payload = json.loads(self.rfile.read(length) or b'{}')
            except (ValueError, OSError):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            model_id = payload.get('model_id', '')
            result, err = test_ai_model(model_id)
            if result is None:
                err_key = err.split(':')[0] if err else ''
                code = {'model_not_found': 404, 'api_key_file_not_found': 404}.get(err_key, 422)
                self._send_json({'error': err, 'model_id': model_id}, code)
                return
            self._send_json({'status': 'ok', 'model_id': model_id, **result})
            return
        if path == '/api/ai/models/set-default':
            try:
                length = int(self.headers.get('Content-Length') or 0)
                payload = json.loads(self.rfile.read(length) or b'{}')
            except (ValueError, OSError):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            model_id = payload.get('model_id', '')
            if set_default_ai_model(model_id):
                self._send_json({'status': 'ok', 'default_model': model_id})
            else:
                self._send_json({'error': 'model_not_found', 'model_id': model_id}, 404)
            return
        if path == '/api/ai/models/pemakaian':
            try:
                length = int(self.headers.get('Content-Length') or 0)
                payload = json.loads(self.rfile.read(length) or b'{}')
            except (ValueError, OSError):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            pemakaian, err = set_ai_pemakaian(str(payload.get('peran') or ''), payload.get('model_id'))
            if pemakaian is None:
                self._send_json({'error': err}, 404 if err == 'model_not_found' else 400)
                return
            self._send_json({'status': 'ok', 'pemakaian': pemakaian})
            return
        if path.startswith('/api/ai/models/') and path.endswith('/delete'):
            # Halaman mengirim id ter-encode (encodeURIComponent), jadi garis miring datang
            # sebagai %2F dan tidak memecah rute.
            model_id = unquote(path[len('/api/ai/models/'):-len('/delete')])
            if not model_id or not AI_MODEL_ID_RE.match(model_id) or '..' in model_id:
                self._send_json({'error': 'invalid_model_id'}, 400)
                return
            if remove_ai_model(model_id):
                self._send_json({'status': 'ok', 'removed': model_id})
            else:
                self._send_json({'error': 'not_found'}, 404)
            return
        # AI Content Generation
        if path == '/api/ai/content/run':
            try:
                length = int(self.headers.get('Content-Length') or 0)
                if length > 4096:
                    self._send_json({'error': 'payload_too_large'}, 413)
                    return
                payload = json.loads(self.rfile.read(length) or b'{}')
            except (ValueError, OSError):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            domain = str(payload.get('domain') or '')
            mode = str(payload.get('mode') or 'dry-run')
            result, err = start_ai_content(domain, mode)
            if result is None:
                code = {'already_running': 409, 'invalid_domain': 400, 'invalid_mode': 400, 'no_ai_models_configured': 422, 'ai_script_missing': 422}.get(err.split(':')[0], 422)
                self._send_json({'error': err, 'domain': domain, 'mode': mode}, code)
                return
            self._send_json({'status': 'started', **result})
            return
        # Installer actions (JSON only)
        try:
            length = int(self.headers.get('Content-Length') or 0)
            if length > 4096:
                self._send_json({'error': 'payload_too_large'}, 413)
                return
            payload = json.loads(self.rfile.read(length) or b'{}')
        except (ValueError, OSError):
            self._send_json({'error': 'invalid_json'}, 400)
            return
        domain = str(payload.get('domain') or '')
        if path == '/api/installer/generate':
            result, err = generate_manifest(domain)
            if result is None:
                code = {'invalid_domain': 400, 'no_folder': 404}.get(err, 422)
                self._send_json({'error': err, 'domain': domain}, code)
                return
            self._send_json({'status': 'ok', **result})
            return
        if path == '/api/installer/claim':
            result, err = claim_domain(domain, str(payload.get('by') or 'manual'))
            if result is None:
                code = {'invalid_domain': 400, 'invalid_by': 400, 'unknown_domain': 404}.get(err, 422)
                self._send_json({'error': err, 'domain': domain}, code)
                return
            self._send_json({'status': 'ok', **result})
            return
        if path == '/api/installer/release':
            result, err = release_claim(domain)
            if result is None:
                self._send_json({'error': err, 'domain': domain}, 400 if err == 'invalid_domain' else 404)
                return
            self._send_json({'status': 'ok', **result})
            return
        mode = str(payload.get('mode') or 'dry-run')
        result, err = start_run(domain, mode)
        if result is None:
            code = {'already_running': 409, 'invalid_domain': 400, 'invalid_mode': 400}.get(err.split(':')[0], 422)
            self._send_json({'error': err, 'domain': domain, 'mode': mode}, code)
            return
        self._send_json({'status': 'started', **result})

    def do_DELETE(self):
        ip = client_ip(self) or 'unknown'
        if not _lolos_batas(self):
            self._send_json({'error': 'rate_limited'}, 429)
            return
        path = urlparse(self.path).path
        if path.startswith('/api/ai/models/') and path.endswith('/delete'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            # Halaman mengirim id ter-encode (encodeURIComponent), jadi garis miring datang
            # sebagai %2F dan tidak memecah rute.
            model_id = unquote(path[len('/api/ai/models/'):-len('/delete')])
            if not model_id or not AI_MODEL_ID_RE.match(model_id) or '..' in model_id:
                self._send_json({'error': 'invalid_model_id'}, 400)
                return
            if remove_ai_model(model_id):
                self._send_json({'status': 'ok', 'removed': model_id})
            else:
                self._send_json({'error': 'not_found'}, 404)
            return
        self.send_error(404)

    def log_message(self, fmt, *args):
        try:
            print(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'msg': fmt % args}))
        except Exception:
            pass


if __name__ == '__main__':
    (Path(__file__).resolve().parent.parent / 'config').mkdir(exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    # Panaskan cache halaman Monitoring & Proteksi (tampilan bawaan) agar kunjungan pertama tak menunggu SSH
    def panaskan():
        for fn in (server_resource, server_monitor, server_firewall):
            try:
                fn()
            except Exception:
                pass
    threading.Thread(target=panaskan, daemon=True).start()
    _scan_yatim()
    threading.Thread(target=_antivirus_jadwal_jalan, daemon=True).start()
    threading.Thread(target=_realtime_sinkron, daemon=True).start()
    threading.Thread(target=_ulang_jalan, daemon=True).start()
    threading.Thread(target=server_cms.jadwal_jalan, daemon=True).start()
    threading.Thread(target=velocityguard.jadwal_jalan, daemon=True).start()
    threading.Thread(target=server_lonjakan.jalan, daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1', 9121), Handler).serve_forever()
