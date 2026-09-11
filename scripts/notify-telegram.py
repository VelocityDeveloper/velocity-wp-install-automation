#!/usr/bin/env python3
"""Kirim notifikasi hasil instalasi ke Telegram.

Pemakaian: notify-telegram.py <domain> <status> [tahap]
Status: SUCCESS | FAILED | CLAIMED | MANUAL (dua terakhir dari autopilot)

Kegagalan notifikasi tidak boleh menggagalkan instalasi, jadi semua error
ditelan dan hanya dilaporkan lewat exit code (0 terkirim, 1 tidak).
"""
import html
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = Path('/etc/velocity/secrets/telegram.env')
MANIFEST_ROOT = Path('/home/project')
SENT_LOG = Path('/var/lib/velocity/installer/telegram-sent.jsonl')
LOG_DIR = Path('/var/lib/velocity/installer')
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
    # Boleh lebih dari satu tujuan, dipisah koma (mis. chat pribadi + grup webmaster).
    chats = [c.strip().strip('"\'') for c in chat.split(',') if c.strip().strip('"\'')]
    return token.strip(), chats


def manifest_paket(domain):
    """Paket website dari manifest. Ditulis saat manifest dibuat dari data CRM,
    karena situs yang sudah terpasang tidak lagi muncul di antrean installer."""
    if not domain or '/' in domain or '..' in domain:
        return ''
    try:
        text = (MANIFEST_ROOT / domain / f'{domain}.txt').read_text()
    except OSError:
        return ''
    for line in text.splitlines():
        key, _, value = line.partition('=')
        if key.strip() == 'paket':
            return value.strip()
    return ''


def theme_note(domain):
    """Tema aktif + hasil pencocokan child theme dari log instalasi terakhir."""
    if not domain or '/' in domain or '..' in domain:
        return ''
    try:
        lines = (LOG_DIR / f'{domain}.log').read_text(errors='replace').splitlines()[-800:]
    except OSError:
        return ''
    active = next((l.split(':', 1)[1].strip() for l in reversed(lines) if l.startswith('active_theme:')), '')
    if not active:
        return ''
    child = next((l.split(':') for l in reversed(lines) if l.startswith('child_theme:')), [])
    status = child[1] if len(child) > 1 else ''
    ref = child[2] if len(child) > 2 else ''
    if status == 'not_found' and ref:
        return f'{active} (referensi {ref} tidak ada di API tema)'
    if status in ('api_error', 'download_failed'):
        return f'{active} (child theme gagal: {status})'
    if status == 'matched' and ref:
        return f'{active} (referensi {ref})'
    return active


def build_message(domain, status, stage, paket='', theme=''):
    status = status.upper()
    stage = html.escape(stage or '-')
    head = f'Domain: <code>{domain}</code>\n'
    if paket:
        head += f'Paket: <b>{html.escape(paket)}</b>\n'
    if status == 'SUCCESS':
        if theme:
            head += f'Tema: <code>{html.escape(theme)}</code>\n'
        return (f'✅ <b>Instalasi selesai</b>\n{head}'
                f'Situs: https://{domain}\n'
                f'Admin: https://{domain}/wp-admin')
    if status == 'CLAIMED':
        return (f'🤖 <b>Diambil alih autopilot</b>\n{head}'
                f'Tahap: <code>{stage}</code>')
    if status == 'MANUAL':
        return (f'⚠️ <b>Autopilot berhenti, perlu ditangani manual</b>\n{head}'
                f'Alasan: <code>{stage}</code>')
    return (f'❌ <b>Instalasi gagal</b>\n{head}'
            f'Tahap: <code>{stage}</code>')


def send(token, chat, text):
    data = urllib.parse.urlencode({
        'chat_id': chat,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': 'true',
    }).encode()
    req = urllib.request.Request(API.format(token=token), data=data)
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read().decode('utf-8', 'replace'))
    return body.get('ok', False), (body.get('result') or {}).get('message_id')


def record_sent(domain, status, chat, message_id):
    """Catat message_id supaya pesan bisa dihapus lagi (scripts/telegram-delete).
    Bot API tidak bisa membaca riwayat chat, jadi tanpa catatan ini pesan lama
    tidak bisa ditemukan kembali."""
    try:
        SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with SENT_LOG.open('a') as f:
            f.write(json.dumps({'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'domain': domain,
                                'status': status.upper(), 'chat': chat, 'message_id': message_id}) + '\n')
        os.chmod(SENT_LOG, 0o600)
    except OSError as e:
        print(f'telegram: gagal mencatat message_id ({e})', file=sys.stderr)


def main():
    if len(sys.argv) < 3:
        print('usage: notify-telegram.py <domain> <status> [tahap]', file=sys.stderr)
        return 1
    domain, status, stage = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else '')
    token, chats = load_config()
    if not token or not chats:
        print('telegram: token/chat_id belum diset, notifikasi dilewati', file=sys.stderr)
        return 1
    theme = theme_note(domain) if status.upper() == 'SUCCESS' else ''
    text = build_message(domain, status, stage, manifest_paket(domain), theme)
    failed = 0
    for chat in chats:
        try:
            ok, message_id = send(token, chat, text)
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f'telegram: gagal kirim ke {chat} ({e})', file=sys.stderr)
            failed += 1
            continue
        if ok and message_id:
            record_sent(domain, status, chat, message_id)
        print(f'telegram: terkirim ke {chat}' if ok else f'telegram: ditolak API untuk {chat}', file=sys.stderr)
        failed += 0 if ok else 1
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
