#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

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


def payload():
    stat = os.statvfs('/')
    total = stat.f_blocks * stat.f_frsize
    free = stat.f_bavail * stat.f_frsize
    used = total - free
    return {
        'cpu': cpu_percent(),
        'memory': memory(),
        'disk': {'used': used, 'total': total, 'percent': round(100 * used / total, 1)},
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
        if self.path == '/api/drive':
            self.json_response(200, drive_status())
            return
        if self.path != '/api/stats':
            self.send_error(404)
            return
        self.json_response(200, payload())

    def do_POST(self):
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

    def log_message(self, *_):
        pass


ThreadingHTTPServer(('127.0.0.1', 9120), Handler).serve_forever()
