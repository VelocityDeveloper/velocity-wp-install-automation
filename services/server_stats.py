#!/usr/bin/env python3
import json
import os
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
