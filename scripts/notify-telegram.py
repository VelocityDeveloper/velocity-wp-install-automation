#!/usr/bin/env python3
"""Kirim notifikasi hasil instalasi ke Telegram.

Pemakaian: notify-telegram.py <domain> <status> [tahap]
Status: SUCCESS | CHECK (terpasang, perlu dicek) | FAILED | CLAIMED | MANUAL | WAITING (tiga terakhir dari autopilot)

Kegagalan notifikasi tidak boleh menggagalkan instalasi, jadi semua error
ditelan dan hanya dilaporkan lewat exit code (0 terkirim, 1 tidak).
"""
import html
import json
import os
import subprocess
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
RENCANA_DIR = Path('/var/lib/velocity/fse-rencana')
# Nama pemeriksaan audit kemiripan (scripts/fse-audit-kemiripan) dalam bahasa PM.
NAMA_CEK = {
    'latar_gelap': 'latar gelap', 'logo_posisi': 'posisi logo', 'menu_posisi': 'posisi menu',
    'dua_baris': 'logo & menu dua baris', 'tombol_ajakan': 'tombol ajakan', 'topbar': 'topbar',
    'topbar_gelap': 'topbar gelap', 'topbar_isi': 'isi topbar', 'lengket': 'menempel saat digulir',
    'menu_kapital': 'menu huruf kapital', 'menu_berwarna': 'warna teks menu', 'kotak_cari': 'kotak cari',
    'ikon_keranjang': 'ikon keranjang', 'tinggi': 'tinggi (px)', 'logo_tinggi': 'tinggi logo (px)',
    'menu_ukuran': 'ukuran huruf menu (px)', 'garis_bawah': 'garis/bayangan bawah', 'teks_terbaca': 'teks tak terbaca',
    'jumlah_kolom': 'jumlah kolom', 'isi_kolom': 'isi kolom', 'urutan_kolom': 'urutan kolom', 'logo': 'logo',
    'baris_hak_cipta': 'baris hak cipta', 'hak_cipta_rata': 'perataan hak cipta',
    'hak_cipta_latar_beda': 'latar hak cipta berbeda', 'hak_cipta_pita': 'pita hak cipta selebar layar',
    'judul_kapital': 'judul huruf kapital', 'susunan_seksi': 'urutan seksi', 'rincian_seksi': 'skor per seksi',
    'font_teks': 'font teks', 'font_judul': 'font judul', 'sudut_tombol': 'sudut tombol (px)',
    'halaman_ada': 'halaman', 'banner_ada': 'banner judul', 'banner_latar': 'latar banner',
    'banner_rata': 'perataan banner', 'breadcrumb': 'breadcrumb', 'banner_tinggi': 'tinggi banner',
    'isi_kontak': 'isi halaman kontak', 'form_peta_berdampingan': 'form & peta berdampingan',
}


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


def manifest_situs_url(domain):
    """Alamat situs untuk laporan. Klien berhosting di luar dipasang di staging
    velocitydeveloper.co/<domain> (manifest `site_url=`), jadi tautan di Telegram
    harus menunjuk ke sana, bukan ke domain klien yang belum kita pegang."""
    if not domain or '/' in domain or '..' in domain:
        return f'https://{domain}'
    try:
        text = (MANIFEST_ROOT / domain / f'{domain}.txt').read_text()
    except OSError:
        return f'https://{domain}'
    for line in text.splitlines():
        key, _, value = line.partition('=')
        if key.strip() == 'site_url' and value.strip():
            return value.strip().rstrip('/')
    return f'https://{domain}'


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
    active_i = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].startswith('active_theme:')), -1)
    if active_i < 0:
        return ''
    active = lines[active_i].split(':', 1)[1].strip()
    # Paket custom: installer mencatat tema bawaan WordPress (active_theme), baru
    # sesudahnya fse-apply mengaktifkan velocity-fse ("fse: tema_siap:<slug>:<versi>").
    fse = next((l.split(':') for l in lines[active_i:] if l.startswith('fse: tema_siap:')), [])
    if len(fse) >= 4:
        return f'{fse[2]} {fse[3].strip()} (block theme FSE, desain custom)'
    child = next((l.split(':') for l in reversed(lines) if l.startswith('child_theme:')), [])
    status = child[1] if len(child) > 1 else ''
    ref = child[2] if len(child) > 2 else ''
    tema_ref = tema_referensi_web(lines)
    if status == 'not_found' and ref and tema_ref:
        return f'{active} (referensi {ref} memakai {tema_ref})'
    if status == 'not_found' and ref:
        return f'{active} (referensi {ref} tidak ada di API tema)'
    if status in ('api_error', 'download_failed'):
        return f'{active} (child theme gagal: {status})'
    if status == 'matched' and ref:
        return f'{active} (referensi {ref})'
    if status == 'generated':
        # Paket G: child theme kosong bernama project, desainnya dikerjakan manual.
        return f'{active} (child theme baru, desain custom)'
    return active


def tema_referensi_web(lines):
    """Tema yang dipakai web referensi luar (`child_theme_ref_tema:` run terakhir), atau ''."""
    i = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].startswith('child_theme:')), -1)
    if i < 0:
        return ''
    ref = next((l for l in lines[i + 1:i + 4] if l.startswith('child_theme_ref_tema:')), '')
    return ref.split(':', 1)[1].strip() if ref else ''


def peringatan_tema(domain):
    """Peringatan bila child theme web referensi belum ada di API tema (keputusan user
    2026-09-23: paket biasa ber-referensi web luar memakai child theme dari API; kalau
    belum tersedia, PM diberi tahu supaya tema itu didaftarkan)."""
    try:
        lines = (LOG_DIR / f'{domain}.log').read_text(errors='replace').splitlines()[-800:]
    except OSError:
        return ''
    child = next((l.split(':') for l in reversed(lines) if l.startswith('child_theme:')), [])
    if len(child) < 3 or child[1] != 'not_found':
        return ''
    tema = tema_referensi_web(lines)
    if tema:
        return (f'Referensi tema belum tersedia di API: {child[2]} memakai {tema}. '
                f'Situs dipasang dengan tema induk; daftarkan {tema} di api.velocitydeveloper.co '
                f'lalu jalankan ulang.')
    return f'Referensi {child[2]} belum tersedia di API tema, situs memakai tema induk.'


VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.3gp', '.webm', '.m4v', '.wmv', '.flv'}


def catatan_video(domain):
    """Video di folder klien yang tidak diunggah ke situs (aturan: video klien tidak pernah
    diupload, keputusan user 2026-09-14 & 2026-09-24). Kosong bila tidak ada video."""
    folder = Path('/home/On Progress') / domain
    if not domain or '/' in domain or not folder.is_dir():
        return ''
    video = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in VIDEO_EXT)
    if not video:
        return ''
    contoh = ', '.join(p.relative_to(folder).as_posix() for p in video[:3])
    lebih = f' +{len(video) - 3} lainnya' if len(video) > 3 else ''
    return f'{len(video)} video klien tidak diunggah ke situs (aturan: video tidak diupload): {contoh}{lebih}'


def wp_login(domain):
    """(username, password) admin WordPress, dengan urutan sumber yang sama persis
    dengan website-install-from-manifest: manifest `password=` → `da_password_file`
    → secret acak per domain. Keputusan user 2026-09-15: login ikut dikirim di
    laporan instalasi selesai. Nilainya hanya masuk ke teks pesan — tidak pernah
    dicetak ke log instalasi atau telegram-sent.jsonl."""
    if not domain or '/' in domain or '..' in domain:
        return '', ''
    cfg = {}
    try:
        for line in (MANIFEST_ROOT / domain / f'{domain}.txt').read_text().splitlines():
            key, sep, value = line.partition('=')
            if sep:
                cfg[key.strip()] = value.strip()
    except OSError:
        return '', ''
    user = cfg.get('admin_user') or cfg.get('da_user', '')
    password = cfg.get('password', '')
    if not password:
        for path in (cfg.get('da_password_file', ''), f'/etc/velocity/secrets/admin_password_{domain}.txt'):
            try:
                password = Path(path).read_text().replace('\r', '').replace('\n', '') if path else ''
            except OSError:
                password = ''
            if password:
                break
    return user, password


def maintenance_note(domain):
    """'aktif' kalau langkah maintenance di instalasi terakhir berhasil menyala."""
    if not domain or '/' in domain or '..' in domain:
        return ''
    try:
        lines = (LOG_DIR / f'{domain}.log').read_text(errors='replace').splitlines()[-400:]
    except OSError:
        return ''
    last = next((l for l in reversed(lines) if l.startswith('maintenance: maintenance_')), '')
    if 'maintenance_active' in last or 'maintenance_enabled' in last:
        return 'aktif (pengunjung melihat halaman perawatan)'
    if 'maintenance_not_visible' in last:
        return 'dinyalakan, tapi halaman perawatan belum tampil'
    return ''


def _nilai(v):
    if isinstance(v, bool):
        return 'ya' if v else 'tidak'
    if isinstance(v, list):
        return ', '.join(map(str, v[:6])) or '-'
    return str(v if v not in (None, '') else '-')


def perbaikan_desain(domain, batas=25):
    """Daftar yang perlu diperbaiki dari audit kemiripan terakhir (HTML), atau ''.

    Permintaan user 2026-09-17: laporan "perlu dicek" harus menyebut apa saja yang
    belum mirip referensi, bukan hanya nama bagiannya."""
    if not domain or '/' in domain or '..' in domain:
        return ''
    try:
        d = json.loads((RENCANA_DIR / domain / 'audit-kemiripan.json').read_text())
    except (OSError, ValueError):
        return ''
    if d.get('sesuai'):
        return ''
    skor = ' · '.join(f'{k.replace("halaman_", "hal. ")} {v}' for k, v in (d.get('skor') or {}).items())
    baris = []
    # Prioritas user: header, footer, beranda (per seksi), lalu gaya dan halaman dalam.
    prioritas = {'header': 0, 'footer': 1, 'beranda': 2, 'gaya': 3}
    urut = sorted((d.get('bagian') or {}).items(), key=lambda kv: (prioritas.get(kv[0], 4), kv[0]))
    for nama, bagian in urut:
        beda = sorted((c for c in bagian.get('cek') or [] if c.get('skor', 1) < 1 and c['kunci'] != 'rincian_seksi'),
                      key=lambda c: -c.get('bobot', 0))
        for c in beda:
            kunci = c['kunci']
            label = (f"sama di halaman {kunci[len('sama_di_'):]}" if kunci.startswith('sama_di_')
                     else NAMA_CEK.get(kunci, kunci))
            teks = f"{nama.replace('halaman_', 'halaman ')} · {label}: "
            if kunci.startswith('sama_di_'):
                teks += f"{_nilai(c.get('situs'))}, di beranda {_nilai(c.get('referensi'))} (template part tidak konsisten)"
            elif kunci == 'teks_terbaca':
                teks += 'warna teks menyatu dengan latar (' + _nilai(c.get('situs')) + ')'
            else:
                teks += f"situs {_nilai(c.get('situs'))} → referensi {_nilai(c.get('referensi'))}"
            if c.get('hilang'):
                teks += f" (seksi belum ada: {', '.join(c['hilang'])})"
            baris.append(teks)
        if nama == 'beranda':
            for r in d.get('seksi_beranda') or []:
                if r.get('beda'):
                    baris.append(f"beranda · seksi {r['urutan_situs']} {r['jenis']} (skor {r['skor']}): {', '.join(r['beda'])}")
    for t in d.get('temuan') or []:
        baris.append(t.replace('_', ' '))
    if not baris:
        return ''
    # Pesan Telegram maks 4096 karakter (bersama kepala & login): daftar dijaga ≤ 2600.
    pilih, panjang = [], 0
    for b in baris[:batas]:
        b = '• ' + html.escape(b[:160])
        if panjang + len(b) > 2600:
            break
        pilih.append(b)
        panjang += len(b) + 1
    lebih = len(baris) - len(pilih)
    isi = '\n'.join(pilih)
    if lebih > 0:
        isi += f'\n• … {lebih} lainnya'
    ulang = f" setelah {d['percobaan']} kali generate" if d.get('percobaan', 1) > 1 else ''
    return (f"\n<b>Desain belum mirip referensi{ulang}</b> ({html.escape(skor)})\n"
            f"Referensi: {html.escape(d.get('referensi') or '-')}\n"
            f"Perlu diperbaiki:\n{isi}\n"
            f"Screenshot: <code>{html.escape(d.get('potret') or '-')}</code>")


def build_message(domain, status, stage, paket='', theme='', maintenance='', login=('', ''), perbaikan='',
                  peringatan=''):
    status = status.upper()
    stage = html.escape(stage or '-')
    head = f'Domain: <code>{domain}</code>\n'
    if paket:
        head += f'Paket: <b>{html.escape(paket)}</b>\n'
    if status == 'WAITING':
        return (f'⏳ <b>Menunggu akun DirectAdmin</b>\n{head}'
                f'Akun hosting belum dibuat PM. Autopilot mengecek ulang tiap 30 menit '
                f'dan melanjutkan instalasi begitu akun tersedia.')
    if status in ('SUCCESS', 'CHECK'):
        if theme:
            head += f'Tema: <code>{html.escape(theme)}</code>\n'
        if maintenance:
            head += f'Maintenance: <b>{html.escape(maintenance)}</b>\n'
        if peringatan:
            head += f'⚠️ {html.escape(peringatan)}\n'
        video = catatan_video(domain)
        if video:
            head += f'🎬 {html.escape(video)}\n'
        situs = manifest_situs_url(domain)
        links = f'Situs: {situs}\nAdmin: {situs}/wp-admin'
        user, password = login
        if user:
            links += f'\nUsername: <code>{html.escape(user)}</code>'
        if password:
            links += f'\nPassword: <code>{html.escape(password)}</code>'
        if status == 'CHECK':
            # Terpasang, tapi pemeriksaan akhir (scripts/site-qa) menemukan masalah.
            return (f'🟡 <b>Instalasi selesai, perlu dicek</b>\n{head}{links}\n'
                    f'Catatan: <code>{stage}</code>{perbaikan}{permintaan_form(domain) if "permintaan_form_klien" in stage else ""}')
        return f'✅ <b>Instalasi selesai</b>\n{head}{permintaan_selesai_agen(domain)}{links}'
    if status == 'CLAIMED':
        return (f'🤖 <b>Diambil alih autopilot</b>\n{head}'
                f'Tahap: <code>{stage}</code>')
    if status == 'MANUAL':
        return (f'⚠️ <b>Autopilot berhenti, perlu ditangani manual</b>\n{head}'
                f'Alasan: <code>{stage}</code>')
    return (f'❌ <b>Instalasi gagal</b>\n{head}'
            f'Tahap: <code>{stage}</code>')


def hasil_agen_permintaan(domain, umur_maks=12 * 3600):
    """Hasil terakhir agen permintaan klien (scripts/permintaan-claude), bila masih baru."""
    berkas = Path('/var/lib/velocity/permintaan-claude') / domain / 'hasil.json'
    try:
        if time.time() - berkas.stat().st_mtime > umur_maks:
            return {}
        return json.loads(berkas.read_text())
    except (OSError, ValueError):
        return {}


def permintaan_form(domain):
    """Isi PESAN TAMBAHAN klien yang belum dikerjakan (scripts/permintaan-form), untuk pesan CHECK,
    plus butir yang tidak bisa diselesaikan agen Claude (scripts/permintaan-claude) beserta alasannya."""
    try:
        teks = subprocess.run([sys.executable, str(Path(__file__).resolve().parent / 'permintaan-form'), domain, '--teks'],
                              capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        teks = ''
    if not teks:
        return ''
    teks = teks if len(teks) <= 700 else teks[:700] + '…'
    agen = hasil_agen_permintaan(domain)
    sisa = ''
    if agen.get('butir') or agen.get('sisa'):
        ikon = {'selesai': '✅', 'perlu_manusia': '🙋', 'tidak_bisa': '❌'}
        sisa = '\nHasil agen Claude:\n' + '\n'.join(
            f"{ikon.get(b.get('status'), '•')} {html.escape(str(b.get('permintaan', ''))[:120])}"
            + (f" — <i>{html.escape(str(b.get('hasil', ''))[:200])}</i>" if b.get('status') != 'selesai' else '')
            for b in (agen.get('butir') or agen.get('sisa'))[:8]) + '\n'
    return (f'\n\n📝 <b>Permintaan klien di form belum selesai dikerjakan</b> (wajib, isi form = acuan):\n'
            f'<blockquote>{html.escape(teks)}</blockquote>{sisa}\n'
            f'Sesudah dikerjakan: <code>scripts/permintaan-form {html.escape(domain)} --selesai "catatan"</code>')


def permintaan_selesai_agen(domain):
    """Baris laporan SUCCESS: permintaan form dikerjakan agen Claude di run ini."""
    agen = hasil_agen_permintaan(domain)
    if agen.get('status') != 'selesai':
        return ''
    return f"📝 Permintaan form dikerjakan agen Claude: {html.escape(str(agen.get('ringkasan', ''))[:400])}\n"


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


def banding_terbaru(domain, umur_maks=12 * 3600):
    """Gambar perbandingan referensi vs situs dari run paket-g-cek-visual terakhir."""
    run = sorted((Path('/var/lib/velocity/visual') / domain).glob('*/ringkasan.json'))
    if not run or time.time() - run[-1].stat().st_mtime > umur_maks:
        return []
    try:
        data = json.loads(run[-1].read_text())
    except (OSError, ValueError):
        return []
    ada = [Path(f) for f in data.get('banding') or [] if Path(f).is_file()]
    # Batas album Telegram 10 foto: 6 bagian desktop + 4 bagian HP.
    return [f for f in ada if 'beranda-hp' not in f.name][:6] + [f for f in ada if 'beranda-hp' in f.name][:4]


def send_album(token, chat, berkas, keterangan):
    """sendMediaGroup (maks 10 foto) lewat multipart tanpa pustaka tambahan."""
    batas = '----velocity' + os.urandom(8).hex()
    media, bagian = [], []
    for i, f in enumerate(berkas[:10]):
        media.append({'type': 'photo', 'media': f'attach://f{i}', **({'caption': keterangan} if i == 0 else {})})
        bagian.append((f'f{i}', f.name, f.read_bytes()))
    tubuh = b''
    for nama, nilai in (('chat_id', str(chat)), ('media', json.dumps(media))):
        tubuh += (f'--{batas}\r\nContent-Disposition: form-data; name="{nama}"\r\n\r\n{nilai}\r\n').encode()
    for nama, nama_berkas, isi in bagian:
        tubuh += (f'--{batas}\r\nContent-Disposition: form-data; name="{nama}"; filename="{nama_berkas}"\r\n'
                  'Content-Type: image/png\r\n\r\n').encode() + isi + b'\r\n'
    tubuh += f'--{batas}--\r\n'.encode()
    req = urllib.request.Request(API.format(token=token).replace('sendMessage', 'sendMediaGroup'), data=tubuh,
                                 headers={'Content-Type': f'multipart/form-data; boundary={batas}'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode('utf-8', 'replace'))
    return body.get('ok', False), [m.get('message_id') for m in body.get('result') or []]


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
    if sys.argv[1] == '--perbaikan':
        # Pratinjau daftar perbaikan desain tanpa mengirim apa pun.
        print(perbaikan_desain(sys.argv[2]) or '(tidak ada / desain sudah mirip)')
        return 0
    domain, status, stage = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else '')
    token, chats = load_config()
    if not token or not chats:
        print('telegram: token/chat_id belum diset, notifikasi dilewati', file=sys.stderr)
        return 1
    done = status.upper() in ('SUCCESS', 'CHECK')
    text = build_message(domain, status, stage, manifest_paket(domain),
                         theme_note(domain) if done else '', maintenance_note(domain) if done else '',
                         wp_login(domain) if done else ('', ''),
                         perbaikan_desain(domain) if 'desain_belum_mirip' in stage else '',
                         peringatan_tema(domain) if done else '')
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
        # Perbandingan referensi (kiri) vs situs (kanan): cara tercepat PM menilai
        # kemiripan desain tanpa membuka server (permintaan user 2026-09-17).
        if ok and done and '--tanpa-foto' not in sys.argv:
            album = banding_terbaru(domain)
            if album:
                try:
                    ok_album, ids = send_album(token, chat, album,
                                               f'{domain}: kiri = referensi klien, kanan = situs ({len(album)} bagian)')
                    for mid in ids if ok_album else []:
                        record_sent(domain, status, chat, mid)
                except (urllib.error.URLError, OSError, ValueError) as e:
                    print(f'telegram: album banding gagal ke {chat} ({e})', file=sys.stderr)
        print(f'telegram: terkirim ke {chat}' if ok else f'telegram: ditolak API untuk {chat}', file=sys.stderr)
        failed += 0 if ok else 1
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
