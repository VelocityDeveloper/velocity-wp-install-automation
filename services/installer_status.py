#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path('/home/project')
# servers config: env INSTALLER_SERVERS (JSON array) or file
SERVERS_FILE_CANDIDATES = [
    Path(__file__).resolve().parent.parent / 'config' / 'servers.json',
    Path('/etc/velocity/servers.json'),
]
API_TOKEN = os.environ.get('INSTALLER_API_TOKEN', '').strip()
# simple in-memory rate limit: ip -> list[timestamps]
_rate = {}
RATE_LIMIT = 30  # req per 60s
RATE_WINDOW = 60

_cron_cache = {'at': 0, 'value': []}
CACHE_TTL = 30


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
    # env takes precedence
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
    required = ['target_host', 'ssh_user', 'da_user', 'domain', 'db_name', 'db_user', 'admin_user', 'admin_email', 'site_title']
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
    commands = [
        ['systemctl', 'list-timers', '--all', '--no-legend', '--no-pager'],
        ['crontab', '-l'],
    ]
    rows = []
    for command in commands:
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and 'No timers listed' not in line:
                rows.append(line)
    # do not leak full raw crontab — only summary + truncated preview
    summary = {'count': len(rows), 'preview': rows[:5]}
    _cron_cache['at'] = now
    _cron_cache['value'] = summary
    return summary


def domains():
    rows = []
    if not ROOT.exists():
        return rows
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        manifests = sorted(folder.glob('*.txt'))
        for manifest in manifests or [None]:
            domain = folder.name
            if manifest:
                ok, detail = validate_manifest(manifest)
                status = 'READY' if ok else detail
            else:
                status = 'NO_MANIFEST'
            rows.append({
                'domain': domain,
                'manifest': manifest.name if manifest else None,
                'folder': True,
                'status': status,
            })
    for manifest in sorted(ROOT.glob('*.txt')):
        rows.append({
            'domain': manifest.stem,
            'manifest': manifest.name,
            'folder': (ROOT / manifest.stem).is_dir(),
            'status': 'READY' if (ROOT / manifest.stem).is_dir() else 'NO_FOLDER',
        })
    return rows


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
        self.send_error(404)

    def log_message(self, fmt, *args):
        # structured stdout log
        try:
            print(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'msg': fmt % args}))
        except Exception:
            pass


if __name__ == '__main__':
    # ensure config dir exists for servers.json
    (Path(__file__).resolve().parent.parent / 'config').mkdir(exist_ok=True)
    ThreadingHTTPServer(('127.0.0.1', 9121), Handler).serve_forever()
