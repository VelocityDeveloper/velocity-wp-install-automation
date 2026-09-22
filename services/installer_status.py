#!/usr/bin/env python3
import base64
import hashlib
import io
import ipaddress
import json
import mimetypes
import os
import re
import secrets as pysecrets
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
)
# Fungsi yang TIDAK memakai model endpoint di halaman ini. Desain FSE paket custom ber-referensi
# dikerjakan agen Claude Code (scripts/desain-claude, keputusan user 2026-09-18/19): modelnya
# ditentukan CLI Claude sendiri, jadi barisnya hanya ditampilkan, tidak bisa dipilih. fse-apply
# tetap menyusun tema & halaman sebagai titik awal agen (peran 'fse' di atas hanya dipakai portal
# berita untuk memilih gaya beranda).
AI_PERAN_TETAP = (
    ('desain_claude', 'Desain FSE paket custom: tata letak, CSS & halaman', 'desain-claude',
     'agen Claude Code (claude-opus-5)'),
)
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


def _rate_ok(ip: str) -> bool:
    now = time.time()
    lst = _rate.get(ip, [])
    lst = [t for t in lst if now - t < RATE_WINDOW]
    if len(lst) >= RATE_LIMIT:
        _rate[ip] = lst
        return False
    lst.append(now)
    _rate[ip] = lst
    return True


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


def servers_view():
    pakai = server_usage()
    daftar = [dict(s, index=i, default=(i == 0), domains=pakai.get(str(s.get('host', '')), 0))
              for i, s in enumerate(load_servers()) if isinstance(s, dict)]
    return {'servers': daftar, 'store': str(SERVERS_STORE),
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
    cmd = ['ssh', '-i', str(key), '-p', srv['port'], '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
           '-o', 'StrictHostKeyChecking=accept-new', f"{srv['user']}@{srv['host']}",
           'hostname; test -d /usr/local/directadmin && echo DA=ya || echo DA=tidak']
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


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
from client_form import read_client_form
from hosting_notes import read_hosting_notes

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
                                              'crm_status': '', 'webmaster': ''})
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


def _refresh_crm_projects_bg():
    error = ''
    try:
        fresh = _fetch_crm_projects_now()
        if fresh or not _crm_cache_projects['value']:
            _crm_cache_projects['value'] = fresh
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
    agen = agen_desain(domain)
    if agen:
        skor = agen.get('skor_kini') or {}
        row.update({'status': 'RUNNING', 'stage': 'AGEN DESAIN CLAUDE', 'agen': agen,
                    'message': 'skor ' + ' '.join(f'{k}={v}' for k, v in skor.items())
                    + (' | belum mirip: ' + ','.join(agen.get('belum_mirip') or []) if agen.get('belum_mirip') else '')})
    return row


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
    if (allow_regenerate and user and re.match(r'^[a-z][a-z0-9]{0,15}$', user)
            and user != cfg.get('da_user') and domain not in installed_domains()):
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


def generate_manifest(domain: str):
    """Auto-generate manifest + secrets for domain from existing data."""
    if not DOMAIN_RE.match(domain) or '/' in domain or '..' in domain:
        return None, 'invalid_domain'
    # source folder: /home/project/<domain> or On Progress sync from Drive
    src = ROOT / domain
    if not src.is_dir():
        src = ON_PROGRESS / domain
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
    # derive defaults; ssh target from server store (managed via /server/ panel), fallback static
    labels = domain.split('.')[0]
    # DirectAdmin limit = 8 chars, prioritize username from notes if present
    da_user = ''
    # Catatan hosting dari tim ada di folder Drive sebagai <domain>.txt dan memuat
    # username DirectAdmin asli, yang tidak selalu sama dengan 8 huruf pertama
    # domain (surya-media-berita.com -> suryame1).
    for nf in [ON_PROGRESS / domain / f'{domain}.txt',
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
        # (surya-media-berita.com -> "surya-me") ikut ke db_name dan ditolak installer.
        da_user = re.sub(r'[^a-z0-9]', '', labels.lower())[:8] or 'admin'
    if not re.match(r'^[a-z_]', da_user):
        da_user = 'u' + da_user
    srv = default_target()
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
        f'site_title={_site_title_from_form((ON_PROGRESS / domain, src, folder), labels.replace("-", " ").title())}\n'
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
    if mode not in ('dry-run', 'apply', 'finish', 'maintenance', 'child-theme', 'audit'):
        return None, 'invalid_mode'
    if mode in ('finish', 'maintenance', 'child-theme', 'audit') and not ssh_key_file():
        return None, 'ssh_key_missing'
    manifest = ROOT / domain / f'{domain}.txt'
    if not manifest.is_file():
        return None, 'manifest_not_found'
    proc = _running.get(domain)
    if proc is not None and proc.poll() is None:
        return None, 'already_running'
    # Catatan hosting PM bisa ditulis atau diubah setelah manifest dibuat.
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
    try:
        p = subprocess.Popen(
            [str(RUNNER), domain],
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


# --- AI Model Management ---

# ID model boleh memuat garis miring (permintaan user 2026-09-16): penyedia seperti
# OpenRouter/Together memakai nama berbentuk "vendor/model", mis. `meta-llama/llama-3-70b`.
# Ruas tidak boleh kosong dan `..` ditolak — id ikut masuk ke URL /api/ai/models/<id>/delete.
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
    endpoint = str(model_data.get('endpoint') or '').strip().rstrip('/')
    if not re.match(r'^https?://\S+$', endpoint):
        return None, 'endpoint_required'
    data = load_ai_models()
    models = data.get('models', [])
    lama = next((m for m in models if m.get('id') == model_id), None)
    api_key = str(model_data.get('api_key') or '').strip() or (lama or {}).get('api_key', '')
    if not api_key:
        return None, 'api_key_required'
    baru = dict(lama or {})
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


def desain_claude_aktif():
    """True bila agen desain Claude dinyalakan (DESAIN_CLAUDE=1 di env autopilot)."""
    try:
        for baris in AUTOPILOT_ENV.read_text().splitlines():
            if baris.strip().startswith('DESAIN_CLAUDE='):
                return baris.split('=', 1)[1].strip() == '1'
    except OSError:
        pass
    return False


def set_ai_pemakaian(peran, model_id):
    """Pilih model untuk satu fungsi installer (AI_PERAN); model_id kosong = ikut model default."""
    if peran not in {kunci for kunci, _, _ in AI_PERAN}:
        return None, 'peran_tidak_dikenal'
    data = load_ai_models()
    model_id = str(model_id or '')
    if model_id and not any(m.get('id') == model_id for m in data.get('models', [])):
        return None, 'model_not_found'
    pemakaian = {k: v for k, v in (data.get('pemakaian') or {}).items() if v}
    if model_id:
        pemakaian[peran] = model_id
    else:
        pemakaian.pop(peran, None)
    data['pemakaian'] = pemakaian
    save_ai_models(data)
    return pemakaian, None


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
    """Daftar tema/plugin dari API Velocity. Header signature = md5 tanggal WIB."""
    tanggal = time.strftime('%d%m%Y', time.gmtime(time.time() + 7 * 3600))
    req = urllib.request.Request(f'{VELOCITY_API}/{jenis}', headers={
        'User-Agent': 'velocity-installer/1.0', 'Accept': 'application/json',
        'signature': hashlib.md5(tanggal.encode()).hexdigest()})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp).get('data')
    if not isinstance(data, list):
        raise ValueError('data_api_tidak_valid')
    return [x for x in data if isinstance(x, dict) and x.get('slug')]


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
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        ip = client_ip(self) or 'unknown'
        parsed = urlparse(self.path)
        path = parsed.path
        # Bagan proses /installer/ membaca satu domain tiap 2-3 detik selama run berjalan
        # (satu berkas state + log): dikecualikan dari batas 30 req/60s supaya pantauan
        # realtime tidak berhenti karena 429. Semua endpoint lain tetap dibatasi.
        baca_bagan = path == '/api/installer' and 'domain' in parse_qs(parsed.query)
        if not baca_bagan and not _rate_ok(ip):
            self._send_json({'error': 'rate_limited'}, 429)
            return

        if path == '/health':
            self._send_json({'status': 'ok'})
            return
        if path == '/api/servers':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json(servers_view())
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
                    'peran_tetap': [{'kunci': k, 'label': label, 'script': script, 'model': model,
                                     'aktif': desain_claude_aktif()}
                                    for k, label, script, model in AI_PERAN_TETAP]}
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
        if not _rate_ok(ip):
            self._send_json({'error': 'rate_limited'}, 429)
            return
        path = urlparse(self.path).path
        # Check allowed paths (including dynamic ones)
        allowed_static = ('/api/installer/run', '/api/installer/generate', '/api/installer/claim',
                          '/api/installer/release', '/api/packages/sync',
                          '/api/servers', '/api/servers/delete', '/api/servers/default', '/api/servers/test',
                          '/api/ai/models', '/api/ai/models/test', '/api/ai/models/set-default',
                          '/api/ai/content/run')
        is_allowed = path in allowed_static or path.startswith('/api/ai/models/')
        if not is_allowed:
            self.send_error(404)
            return
        if not _check_auth(self):
            self._send_json({'error': 'unauthorized'}, 401)
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
        if not _rate_ok(ip):
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
    ThreadingHTTPServer(('127.0.0.1', 9121), Handler).serve_forever()
