#!/usr/bin/env python3
import base64
import hashlib
import io
import json
import mimetypes
import os
import re
import secrets as pysecrets
import subprocess
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path('/home/project')
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


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    if not API_TOKEN:
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


def domains():
    rows = []
    if not ROOT.exists():
        return rows
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        # one row per folder: exact <domain>.txt manifest only (other .txt = notes, ignored)
        manifest = folder / f'{folder.name}.txt'
        rows.append(domain_row(folder.name, manifest if manifest.is_file() else None))
    for manifest in sorted(ROOT.glob('*.txt')):
        # stray manifest outside folder structure
        rows.append({
            'domain': manifest.stem,
            'manifest': manifest.name,
            'folder': (ROOT / manifest.stem).is_dir(),
            'status': 'READY' if (ROOT / manifest.stem).is_dir() else 'NO_FOLDER',
        })
    return rows


def domain_row(domain, manifest):
    if manifest:
        ok, detail = validate_manifest(manifest)
        base_status = 'READY' if ok else detail
    else:
        base_status = 'NO_MANIFEST'
    row = {'domain': domain, 'manifest': manifest.name if manifest else None,
           'folder': True, 'status': base_status}
    state = STATE / f'{domain}.json'
    log = STATE / f'{domain}.log'
    try:
        saved = json.loads(state.read_text())
        if isinstance(saved, dict):
            row.update({k: str(saved[k]) for k in ('status', 'stage', 'message', 'updated_at') if k in saved})
    except (OSError, ValueError):
        pass
    try:
        row['log'] = log.read_text(errors='replace').splitlines()[-30:]
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
    folder = ROOT / domain
    if not folder.is_dir():
        return None, 'no_folder'
    manifest = folder / f'{domain}.txt'
    if manifest.is_file():
        ok, detail = validate_manifest(manifest)
        if ok:
            _ensure_secrets(domain)
            return {'generated': False, 'reason': 'already_valid'}, None
    # derive defaults; ssh target from server store (managed via /server/ panel), fallback static
    labels = domain.split('.')[0]
    da_user = re.sub(r'[^a-z0-9_-]', '', labels.lower())[:31] or 'admin'
    if not re.match(r'^[a-z_]', da_user):
        da_user = 'u' + da_user
    servers = load_servers()
    srv = servers[0] if servers else {}
    target = str(srv.get('host') or '103.103.175.182')
    port = str(srv.get('port') or '22')
    if not re.match(r'^[0-9]+$', port) or not (1 <= int(port) <= 65535):
        port = '22'
    ssh_user = str(srv.get('user') or 'root')
    admin_email = ''
    notes = folder / 'notes-credentials.txt'
    if notes.is_file():
        for line in notes.read_text(errors='replace').splitlines():
            if '@' in line and ' ' not in line and not admin_email:
                cand = line.strip().strip('*').strip()
                if re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', cand):
                    admin_email = cand
    content = (
        f'target_host={target}\n'
        f'ssh_port={port}\n'
        f'ssh_user={ssh_user}\n'
        f'da_user={da_user}\n'
        f'domain={domain}\n'
        f'db_name={da_user}_wp\n'
        f'db_user={da_user}_wp\n'
        f'admin_user=admin\n'
        f'admin_email={admin_email or ("admin@" + domain)}\n'
        f'site_title={labels.replace("-", " ").title()}\n'
    )
    tmp = manifest.with_suffix('.txt.tmp')
    tmp.write_text(content)
    os.chmod(tmp, 0o640)
    os.replace(tmp, manifest)
    _ensure_secrets(domain)
    return {'generated': True, 'manifest': str(manifest)}, None


def start_run(domain: str, mode: str):
    """Start installer-runner for domain. mode: dry-run | apply."""
    if not DOMAIN_RE.match(domain) or '/' in domain or '..' in domain:
        return None, 'invalid_domain'
    if mode not in ('dry-run', 'apply'):
        return None, 'invalid_mode'
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
    if mode == 'apply':
        if not ssh_key_file():
            return None, 'ssh_key_missing'
        env['WP_INSTALL_SSH_KEY_FILE'] = str(ssh_key_file())
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
    if model_data.get('provider') not in ('openai', 'anthropic', 'openai_compatible', 'ollama'):
        return None, 'invalid_provider'
    if not model_data.get('model'):
        return None, 'model_required'
    if not model_data.get('api_key_file'):
        return None, 'api_key_file_required'
    if not Path(model_data['api_key_file']).is_file():
        return None, 'api_key_file_not_found'
    
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
    
    api_key_file = model.get('api_key_file', '')
    if not Path(api_key_file).is_file():
        return None, 'api_key_file_not_found'
    
    api_key = Path(api_key_file).read_text().strip()
    base_url = model.get('base_url', 'https://api.openai.com/v1')
    model_name = model.get('model', '')
    
    try:
        import urllib.request
        payload = json.dumps({
            'model': model_name,
            'messages': [{'role': 'user', 'content': 'Say "OK" if you can hear me.'}],
            'max_tokens': 10
        }).encode()
        req = urllib.request.Request(
            f'{base_url}/chat/completions',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if 'choices' in result:
                return {'status': 'ok', 'response': result['choices'][0]['message']['content']}, None
            return None, 'unexpected_response'
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
        ip = self.client_address[0] if self.client_address else 'unknown'
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
            self._send_json({'root': str(ROOT), 'domains': domains(), 'cronjobs': cronjobs()})
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
            self._send_json(load_ai_models())
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
        ip = self.client_address[0] if self.client_address else 'unknown'
        if not _rate_ok(ip):
            self._send_json({'error': 'rate_limited'}, 429)
            return
        path = urlparse(self.path).path
        # Check allowed paths (including dynamic ones)
        allowed_static = ('/api/installer/run', '/api/installer/generate', '/api/packages', '/api/packages/download',
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
                code = {'invalid_id': 400, 'invalid_provider': 400, 'model_required': 400, 'api_key_file_required': 400, 'api_key_file_not_found': 404}.get(err_key, 422)
                self._send_json({'error': err}, code)
                return
            self._send_json({'status': 'ok', 'model': result})
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
        mode = str(payload.get('mode') or 'dry-run')
        result, err = start_run(domain, mode)
        if result is None:
            code = {'already_running': 409, 'invalid_domain': 400, 'invalid_mode': 400}.get(err.split(':')[0], 422)
            self._send_json({'error': err, 'domain': domain, 'mode': mode}, code)
            return
        self._send_json({'status': 'started', **result})

    def do_DELETE(self):
        ip = self.client_address[0] if self.client_address else 'unknown'
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
