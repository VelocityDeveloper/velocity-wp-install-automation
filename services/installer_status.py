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
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path('/home/project')
ON_PROGRESS = Path('/home/On Progress')
STATE = Path('/var/lib/velocity/installer')
RUNNER = Path('/opt/velocity-wp-install-automation/scripts/installer-runner')
SECRETS = Path('/etc/velocity/secrets')
SSH_KEY_CANDIDATES = [SECRETS / 'ssh_key', Path('/root/.ssh/id_ed25519'), Path('/root/.ssh/id_rsa')]
DOMAIN_RE = re.compile(r'^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
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
AI_PROMPTS = AI_CONFIG_DIR / 'prompts'
AI_GENERATED = AI_CONFIG_DIR / 'generated'
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

# Ground truth for "belum diambil" (not yet claimed): vdnet CRM's project-list API,
# filtered to status_pengerjaan=Belum dikerjakan (wm_project not assigned yet).
PROJECT_LIST_API_URL = os.environ.get(
    'PROJECT_LIST_API_URL', 'https://new.velocitydeveloper.net/api/api/public/project-list')
PROJECT_LIST_API_KEY_FILE = SECRETS / 'project_list_api_key'
# Hanya jenis project yang berarti "pasang WordPress". Tanpa saringan ini daftar
# installer ikut memuat tiket Deposit Iklan Google, Tambah Space, dsb — 99% isi
# daftar, padahal tidak ada hubungannya dengan instalasi.
INSTALL_JENIS = {'Pembuatan', 'Pembuatan apk biasa', 'Pembuatan Tanpa Domain', 'Redesign'}
BELUM_DIAMBIL_TTL = 900
BELUM_DIAMBIL_RETRY = 30
# Panduan API menyarankan halaman kecil, bukan satu tarikan raksasa.
PROJECT_LIST_PER_PAGE = 2000
PROJECT_LIST_MAX_PAGES = 25
_belum_diambil_cache = {'at': 0, 'value': {}, 'fetching': False, 'error': ''}
_belum_diambil_lock = threading.Lock()
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


def _fetch_belum_diambil_domains_now():
    """Pull every 'Belum dikerjakan' row from the vdnet project-list API, as
    {domain: paket}. Uses one large per_page instead of many small pages — the
    shared host in front of this API resets/bans connections after a burst of
    rapid requests.
    """
    key = _project_list_api_key()
    if not key:
        return {}
    found = {}
    page = 1
    while True:
        # Urutkan naik berdasarkan id: dataset ini hidup, dan urutan default
        # (tgl_deadline desc) bikin baris baru menggeser halaman berikutnya
        # sehingga ada baris terlewat di batas halaman saat paginasi.
        url = (f'{PROJECT_LIST_API_URL}?status_pengerjaan=Belum+dikerjakan'
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
            data = json.loads(resp.read().decode('utf-8', errors='replace'))
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
            # Satu domain bisa punya beberapa project: pertahankan nilai yang
            # terisi supaya baris kosong tidak menimpanya, dan untuk deadline
            # ambil yang paling dekat karena itu yang paling mendesak.
            cur = found.setdefault(name, {'paket': '', 'deadline': '', 'jenis': []})
            # Autopilot perlu jenisnya: Redesign berarti situsnya sudah hidup.
            if jenis not in cur['jenis']:
                cur['jenis'].append(jenis)
            if paket and not cur['paket']:
                cur['paket'] = paket
            if deadline and (not cur['deadline'] or deadline < cur['deadline']):
                cur['deadline'] = deadline
        last_page = data.get('last_page', page)
        if page >= last_page:
            break
        if page >= PROJECT_LIST_MAX_PAGES:
            # Jangan memotong diam-diam kalau data tumbuh melewati batas.
            print(json.dumps({'event': 'belum_diambil_truncated',
                              'fetched_pages': page, 'last_page': last_page}), flush=True)
            break
        page += 1
        time.sleep(1)  # be gentle with the shared host between pages
    return found


def _refresh_belum_diambil_bg():
    error = ''
    try:
        fresh = _fetch_belum_diambil_domains_now()
        if fresh or not _belum_diambil_cache['value']:
            _belum_diambil_cache['value'] = fresh
    except Exception as e:  # keep serving the last-known set on API hiccup
        # Jangan gagal dalam diam: tanpa jejak ini, satu kegagalan sesaat bikin
        # halaman cuma menampilkan segelintir domain tanpa alasan yang terlacak.
        error = f'{type(e).__name__}: {e}'
        print(json.dumps({'event': 'belum_diambil_refresh_failed', 'error': error}), flush=True)
    finally:
        _belum_diambil_cache['error'] = error
        _belum_diambil_cache['at'] = time.time()
        _belum_diambil_cache['fetching'] = False


def belum_diambil_domains():
    """Cached {domain: {paket, deadline}} for domains the CRM says are not yet claimed.
    First call blocks so the list isn't empty on a cold start; later refreshes
    happen in a background thread so /api/installer never blocks ~24s on them.
    """
    now = time.time()
    if _belum_diambil_cache['at'] == 0:
        # Cold start: tahan request lain sampai tarikan pertama selesai. Tanpa
        # kunci ini, request yang datang saat tarikan berjalan dapat cache
        # kosong dan halaman seolah cuma berisi 2 domain.
        with _belum_diambil_lock:
            if _belum_diambil_cache['at'] == 0:
                _belum_diambil_cache['fetching'] = True
                _refresh_belum_diambil_bg()
        return _belum_diambil_cache['value']
    # Percobaan yang gagal tidak boleh membekukan cache kosong selama TTL penuh.
    ttl = BELUM_DIAMBIL_RETRY if _belum_diambil_cache['error'] else BELUM_DIAMBIL_TTL
    if now - _belum_diambil_cache['at'] >= ttl and not _belum_diambil_cache['fetching']:
        _belum_diambil_cache['fetching'] = True
        threading.Thread(target=_refresh_belum_diambil_bg, daemon=True).start()
    return _belum_diambil_cache['value']


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
    # Hanya pekerjaan yang memang ada: di antrean CRM atau sudah punya folder.
    if (name not in belum_diambil_domains() and not (ON_PROGRESS / name).is_dir()
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


def _queue_row(name, source, belum_diambil, claims, connected_hosts):
    """Baris antrean untuk satu folder project, atau None kalau tidak perlu tampil."""
    manifest = ROOT / name / f'{name}.txt'
    has_manifest = manifest.is_file()
    row = domain_row(name, manifest if has_manifest else None)
    key = name.lower()
    crm = belum_diambil.get(key) or {}
    row['paket'] = crm.get('paket') or None
    row['deadline'] = crm.get('deadline') or None
    row['jenis'] = crm.get('jenis') or []
    row['claim'] = claims.get(key)
    if key in belum_diambil and not row['claim']:
        row['status'] = 'belum diambil'
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
    belum_diambil = belum_diambil_domains()
    claims = load_claims()
    seen = set()
    # primary source: On Progress folders synced from Google Drive
    if ON_PROGRESS.is_dir():
        for folder in sorted(p for p in ON_PROGRESS.iterdir() if p.is_dir()):
            name = folder.name
            if not DOMAIN_RE.match(name) or name in done:
                continue
            seen.add(name)
            row = _queue_row(name, 'onprogress', belum_diambil, claims, connected_hosts)
            if row:
                rows.append(row)
    # fallback: existing /home/project folders (e.g. fahmi = Drive-less, yayasan = FAILED retry)
    if ROOT.is_dir():
        for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
            name = folder.name
            if name in seen or not DOMAIN_RE.match(name) or name in done:
                continue
            row = _queue_row(name, 'project', belum_diambil, claims, connected_hosts)
            if row:
                rows.append(row)
    # CRM adalah sumber kebenaran soal pekerjaan yang ada. Daftar di atas
    # digerakkan oleh folder di disk, jadi project yang foldernya belum
    # tersinkron dari Drive tidak pernah muncul sama sekali — padahal itu justru
    # pekerjaan yang perlu dikejar. Tampilkan, dengan tanda folder belum ada.
    emitted = {r['domain'].lower() for r in rows}
    done_lower = {d.lower() for d in done}
    for name in sorted(belum_diambil):
        if name in emitted or name in done_lower or not DOMAIN_RE.match(name):
            continue
        crm = belum_diambil.get(name) or {}
        claim = claims.get(name)
        rows.append({
            'domain': name,
            'manifest': None,
            'folder': False,
            'status': 'NO_FOLDER' if claim else 'belum diambil',
            'target_host': None,
            'paket': crm.get('paket') or None,
            'deadline': crm.get('deadline') or None,
            'jenis': crm.get('jenis') or [],
            'claim': claim,
            'log': [],
            'source': 'crm',
        })
    return rows


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
    return row


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
                    da_user = re.sub(r'[^a-z0-9]', '', m.group(1).lower())[:8]
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
        # WP admin = DA user, biar login WP sesuai data di txt (username/password DA)
        f'da_password_file=/var/lib/velocity/secret/da_password\n'
        f'admin_email={admin_email or ("admin@" + domain)}\n'
        f'site_title={_site_title_from_form((ON_PROGRESS / domain, src, folder), labels.replace("-", " ").title())}\n'
    )
    # Tanpa baris ini installer melewati pemasangan tema/plugin dan hasilnya
    # WordPress polos dengan tema bawaan.
    theme_pkg, addons_pkg = _velocity_packages()
    if addons_pkg:
        content += f'velocity_addons_pkg={addons_pkg}\n'
    if theme_pkg:
        content += f'velocity_theme_pkg={theme_pkg}\n'
    # Paket website dari CRM untuk laporan Telegram: situs yang sudah terpasang
    # tidak lagi muncul di antrean, jadi paketnya dicatat di manifest.
    paket = str((belum_diambil_domains().get(domain.lower()) or {}).get('paket') or '')
    if re.match(r'^[\w .&()/+-]{1,60}$', paket):
        content += f'paket={paket}\n'
    tmp = manifest.with_suffix('.txt.tmp')
    tmp.write_text(content)
    os.chmod(tmp, 0o640)
    os.replace(tmp, manifest)
    _ensure_secrets(domain)
    return {'generated': True, 'manifest': str(manifest)}, None


def start_run(domain: str, mode: str):
    """Start installer-runner for domain. mode: dry-run | apply | finish.

    finish merapikan ulang situs yang sudah terpasang (konten bersih, aset klien,
    pemeriksaan akhir) tanpa memasang ulang WordPress dan tanpa notifikasi."""
    if not DOMAIN_RE.match(domain) or '/' in domain or '..' in domain:
        return None, 'invalid_domain'
    if mode not in ('dry-run', 'apply', 'finish'):
        return None, 'invalid_mode'
    if mode == 'finish' and not ssh_key_file():
        return None, 'ssh_key_missing'
    manifest = ROOT / domain / f'{domain}.txt'
    if not manifest.is_file():
        return None, 'manifest_not_found'
    ok, detail = validate_manifest(manifest)
    if not ok:
        return None, 'manifest_invalid:' + detail
    proc = _running.get(domain)
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
    """Add a new AI model."""
    if not re.match(r'^[a-zA-Z0-9_-]+$', model_data.get('id', '')):
        return None, 'invalid_id'
    if not model_data.get('endpoint'):
        return None, 'endpoint_required'
    if not model_data.get('api_key'):
        return None, 'api_key_required'
    
    # Use id as model name if not provided
    if not model_data.get('name'):
        model_data['name'] = model_data['id']
    # Use id as model name for API calls if model not specified
    if not model_data.get('model'):
        model_data['model'] = model_data['id']
    
    data = load_ai_models()
    models = data.get('models', [])
    
    # Check for duplicate ID
    for i, m in enumerate(models):
        if m['id'] == model_data['id']:
            # Update existing
            models[i] = model_data
            data['models'] = models
            if model_data.get('is_default'):
                for m in models:
                    m['is_default'] = (m['id'] == model_data['id'])
            save_ai_models(data)
            return model_data, None
    
    # Add new
    models.append(model_data)
    data['models'] = models
    if model_data.get('is_default') or len(models) == 1:
        for m in models:
            m['is_default'] = (m['id'] == model_data['id'])
    save_ai_models(data)
    return model_data, None


def remove_ai_model(model_id):
    """Remove an AI model."""
    data = load_ai_models()
    models = data.get('models', [])
    new_models = [m for m in models if m['id'] != model_id]
    if len(new_models) == len(models):
        return False
    data['models'] = new_models
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
    env = dict(os.environ, INSTALL_MODE=mode)
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


# --- packages management ---

def load_packages():
    try:
        if PACKAGES_META.is_file():
            return json.loads(PACKAGES_META.read_text())
    except (OSError, ValueError):
        pass
    return {}


def save_packages(pkgs):
    tmp = PACKAGES_META.with_suffix('.tmp')
    tmp.write_text(json.dumps(pkgs, indent=2, default=str))
    os.chmod(tmp, 0o600)
    tmp.replace(PACKAGES_META)


def add_package(slug, ptype, name, source, size, version=''):
    if ptype not in ('plugin', 'theme'):
        return None, 'invalid_type'
    if not re.match(r'^[a-zA-Z0-9_-]+$', slug):
        return None, 'invalid_slug'
    pkgs = load_packages()
    pkgs[slug] = {
        'slug': slug,
        'type': ptype,
        'name': name or slug,
        'source': source,
        'size': size,
        'version': version,
        'added_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    save_packages(pkgs)
    return pkgs[slug], None


def remove_package(slug):
    pkgs = load_packages()
    if slug not in pkgs:
        return False
    # remove file if exists
    for ext in ('.zip', '.tar.gz'):
        f = PACKAGES_DIR / f'{slug}{ext}'
        if f.is_file():
            f.unlink()
    del pkgs[slug]
    save_packages(pkgs)
    return True


def download_package_url(url, slug):
    """Download a package from URL to packages dir. Returns path or error."""
    if not url.startswith(('http://', 'https://')):
        return None, 'invalid_url'
    if not re.match(r'^[a-zA-Z0-9_-]+$', slug):
        return None, 'invalid_slug'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Velocity-Installer/1.0'})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
            if len(data) > 200 * 1024 * 1024:  # 200MB limit
                return None, 'file_too_large'
            ct = resp.headers.get('Content-Type', '')
            if 'zip' in ct or url.endswith('.zip'):
                ext = '.zip'
            else:
                ext = '.zip'  # default to zip
            dest = PACKAGES_DIR / f'{slug}{ext}'
            dest.write_bytes(data)
            os.chmod(dest, 0o644)
            return dest, None
    except Exception as e:
        return None, f'download_failed:{e}'


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
        if not _rate_ok(ip):
            self._send_json({'error': 'rate_limited'}, 429)
            return
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/health':
            self._send_json({'status': 'ok'})
            return
        if path == '/api/servers':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json({'servers': load_servers()})
            return
        if path == '/api/installer':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json({'root': str(ROOT), 'domains': domains(), 'cronjobs': cronjobs(),
                             'local_ips': local_ips(), 'servers': load_servers(),
                             'default_target': default_target()})
            return
        if path == '/api/packages':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            self._send_json({'packages': load_packages()})
            return
        # AI endpoints
        if path == '/api/ai/models':
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            data = load_ai_models()
            # mask api_key for listing
            safe = {'models': [], 'default_provider': data.get('default_provider', 'openai')}
            for m in data.get('models', []):
                mm = dict(m)
                if mm.get('api_key'):
                    mm['api_key'] = '***'
                    mm['api_key_set'] = True
                safe['models'].append(mm)
            self._send_json(safe)
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
                          '/api/installer/release', '/api/packages', '/api/packages/download',
                          '/api/ai/models', '/api/ai/models/test', '/api/ai/models/set-default',
                          '/api/ai/content/run')
        is_allowed = path in allowed_static or path.startswith('/api/ai/models/')
        if not is_allowed:
            self.send_error(404)
            return
        if not _check_auth(self):
            self._send_json({'error': 'unauthorized'}, 401)
            return
        # Package upload / URL add
        if path == '/api/packages':
            ct = self.headers.get('Content-Type', '')
            if ct.startswith('multipart/form-data'):
                # File upload
                size = int(self.headers.get('Content-Length') or 0)
                if size > 200 * 1024 * 1024:
                    self._send_json({'error': 'file_too_large'}, 413)
                    return
                boundary = ct.split('boundary=')[1].strip()
                body = self.rfile.read(size)
                parts = body.split(('--' + boundary).encode())
                upload_field = None
                filename = None
                file_data = b''
                slug = None
                ptype = 'plugin'
                for part in parts:
                    if b'Content-Disposition' not in part:
                        continue
                    header, data = part.split(b'\r\n\r\n', 1)
                    header = header.decode('utf-8', errors='replace')
                    if 'name="file"' in header:
                        # extract filename
                        m = re.search(r'filename="([^"]+)"', header)
                        if m:
                            filename = m.group(1)
                        upload_field = data.rstrip(b'\r\n')
                    elif 'name="slug"' in header:
                        slug = data.rstrip(b'\r\n').decode('utf-8', errors='replace').strip()
                    elif 'name="type"' in header:
                        ptype = data.rstrip(b'\r\n').decode('utf-8', errors='replace').strip()
                if not upload_field or not filename:
                    self._send_json({'error': 'no_file'}, 400)
                    return
                if not slug:
                    slug = re.sub(r'[^a-zA-Z0-9_-]', '', Path(filename).stem)[:40]
                ext = '.zip' if filename.endswith('.zip') else '.zip'
                dest = PACKAGES_DIR / f'{slug}{ext}'
                dest.write_bytes(upload_field)
                os.chmod(dest, 0o644)
                result, err = add_package(slug, ptype, Path(filename).stem, f'upload:{filename}', len(upload_field))
                if result is None:
                    self._send_json({'error': err}, 400)
                    return
                self._send_json({'status': 'ok', 'package': result})
                return
            else:
                # JSON: add by URL
                try:
                    length = int(self.headers.get('Content-Length') or 0)
                    payload = json.loads(self.rfile.read(length) or b'{}')
                except (ValueError, OSError):
                    self._send_json({'error': 'invalid_json'}, 400)
                    return
                url = payload.get('url', '')
                slug = payload.get('slug', '')
                ptype = payload.get('type', 'plugin')
                name = payload.get('name', slug)
                if not url or not slug:
                    self._send_json({'error': 'url_and_slug_required'}, 400)
                    return
                dest, err = download_package_url(url, slug)
                if dest is None:
                    self._send_json({'error': err}, 422)
                    return
                result, err = add_package(slug, ptype, name, url, dest.stat().st_size)
                if result is None:
                    self._send_json({'error': err}, 400)
                    return
                self._send_json({'status': 'ok', 'package': result})
                return
        if path == '/api/packages/download':
            try:
                length = int(self.headers.get('Content-Length') or 0)
                payload = json.loads(self.rfile.read(length) or b'{}')
            except (ValueError, OSError):
                self._send_json({'error': 'invalid_json'}, 400)
                return
            url = payload.get('url', '')
            slug = payload.get('slug', '')
            if not url or not slug:
                self._send_json({'error': 'url_and_slug_required'}, 400)
                return
            dest, err = download_package_url(url, slug)
            if dest is None:
                self._send_json({'error': err}, 422)
                return
            self._send_json({'status': 'ok', 'path': str(dest), 'size': dest.stat().st_size})
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
        if path.startswith('/api/ai/models/') and path.endswith('/delete'):
            model_id = path[len('/api/ai/models/'):-len('/delete')]
            if not model_id or not re.match(r'^[a-zA-Z0-9_-]+$', model_id):
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
        if path.startswith('/api/packages/'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            slug = path[len('/api/packages/'):]
            if not slug or not re.match(r'^[a-zA-Z0-9_-]+$', slug):
                self._send_json({'error': 'invalid_slug'}, 400)
                return
            if remove_package(slug):
                self._send_json({'status': 'ok', 'removed': slug})
            else:
                self._send_json({'error': 'not_found'}, 404)
            return
        if path.startswith('/api/ai/models/') and path.endswith('/delete'):
            if not _check_auth(self):
                self._send_json({'error': 'unauthorized'}, 401)
                return
            model_id = path[len('/api/ai/models/'):-len('/delete')]
            if not model_id or not re.match(r'^[a-zA-Z0-9_-]+$', model_id):
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
