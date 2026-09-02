#!/usr/bin/env python3
import json
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path('/home/project')


def cronjobs():
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
    return rows


def domains():
    rows = []
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        manifests = sorted(folder.glob('*.txt'))
        for manifest in manifests or [None]:
            domain = folder.name
            rows.append({
                'domain': domain,
                'manifest': manifest.name if manifest else None,
                'folder': True,
                'status': 'READY' if manifest else 'NO_MANIFEST',
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


ThreadingHTTPServer(('127.0.0.1', 9121), Handler).serve_forever()
