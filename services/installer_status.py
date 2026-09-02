#!/usr/bin/env python3
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path('/home/project')
STATE = Path('/var/lib/velocity/installer')


def cronjobs():
    rows = []
    for command in (['systemctl', 'list-timers', '--all', '--no-legend', '--no-pager'], ['crontab', '-l']):
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=3, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        rows.extend(line.strip() for line in result.stdout.splitlines()
                    if line.strip() and not line.strip().startswith('#') and 'No timers listed' not in line)
    return rows


def domains():
    rows = []
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        manifests = sorted(folder.glob('*.txt'))
        for manifest in manifests or [None]:
            domain = folder.name
            rows.append(domain_row(domain, manifest))
    return rows


def domain_row(domain, manifest):
    row = {'domain': domain, 'manifest': manifest.name if manifest else None,
           'folder': True, 'status': 'READY' if manifest else 'NO_MANIFEST'}
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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/api/installer':
            self.send_error(404)
            return
        body = json.dumps({'root': str(ROOT), 'domains': domains(), 'cronjobs': cronjobs()}, separators=(',', ':')).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


STATE.mkdir(parents=True, exist_ok=True)
ThreadingHTTPServer(('127.0.0.1', 9121), Handler).serve_forever()
