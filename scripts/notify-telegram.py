#!/usr/bin/env python3
"""Kirim notifikasi hasil instalasi ke Telegram.

Pemakaian: notify-telegram.py <domain> <status> [tahap]
Status: SUCCESS | FAILED

Kegagalan notifikasi tidak boleh menggagalkan instalasi, jadi semua error
ditelan dan hanya dilaporkan lewat exit code (0 terkirim, 1 tidak).
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = Path('/etc/velocity/secrets/telegram.env')
API = 'https://api.telegram.org/bot{token}/sendMessage'


def load_config():
    cfg = {}
    try:
        for line in CONFIG.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            cfg[k.strip()] = v.strip()
    except OSError:
        pass
    token = os.environ.get('TELEGRAM_BOT_TOKEN') or cfg.get('TELEGRAM_BOT_TOKEN', '')
    chat = os.environ.get('TELEGRAM_CHAT_ID') or cfg.get('TELEGRAM_CHAT_ID', '')
    return token.strip(), chat.strip()


def build_message(domain, status, stage):
    if status.upper() == 'SUCCESS':
        return (f'✅ <b>Instalasi selesai</b>\n'
                f'Domain: <code>{domain}</code>\n'
                f'Situs: https://{domain}\n'
                f'Admin: https://{domain}/wp-admin')
    return (f'❌ <b>Instalasi gagal</b>\n'
            f'Domain: <code>{domain}</code>\n'
            f'Tahap: <code>{stage or "-"}</code>')


def send(token, chat, text):
    data = urllib.parse.urlencode({
        'chat_id': chat,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': 'true',
    }).encode()
    req = urllib.request.Request(API.format(token=token), data=data)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8', 'replace')).get('ok', False)


def main():
    if len(sys.argv) < 3:
        print('usage: notify-telegram.py <domain> <status> [tahap]', file=sys.stderr)
        return 1
    domain, status, stage = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else '')
    token, chat = load_config()
    if not token or not chat:
        print('telegram: token/chat_id belum diset, notifikasi dilewati', file=sys.stderr)
        return 1
    try:
        ok = send(token, chat, build_message(domain, status, stage))
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f'telegram: gagal kirim ({e})', file=sys.stderr)
        return 1
    print('telegram: terkirim' if ok else 'telegram: ditolak API', file=sys.stderr)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
