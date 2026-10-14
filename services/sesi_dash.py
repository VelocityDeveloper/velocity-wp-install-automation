"""Sesi login dash.velocity.ai.id (gerbang /opt/dash-login) untuk nama pelaku di riwayat aksi.

Cookie vd_dash = "<user>.<kedaluwarsa>.<hmac>" ditandatangani /etc/velocity/secrets/dash_session_key,
jadi bisa diverifikasi di sini tanpa memanggil dash-login. Nama tampilan akun VD.net diambil dari
/var/lib/velocity/dash-login/profil.json (diisi dash-login tiap masuk lewat VD.net).

Lewat LAN/Tailscale browser tidak membawa cookie ini → tidak ada sesi → aksi yang mencatat
"oleh" ditolak dengan login_diperlukan (halaman mengarahkan ke tombol Masuk dengan VD.net).
"""
import hashlib
import hmac
import io
import json
import time
from http.cookies import SimpleCookie

KUNCI_SESI = '/etc/velocity/secrets/dash_session_key'
PROFIL = '/var/lib/velocity/dash-login/profil.json'
COOKIE = 'vd_dash'


def _kunci():
    try:
        with open(KUNCI_SESI) as f:
            return f.read().strip().encode() or None
    except OSError:
        return None


def dari_cookie(header_cookie):
    """{'user','username','nama','sumber'} bila cookie vd_dash sah, selain itu None."""
    if not header_cookie:
        return None
    c = SimpleCookie()
    try:
        c.load(header_cookie)
    except Exception:
        return None
    if COOKIE not in c:
        return None
    kunci = _kunci()
    try:
        user, sampai, sig = c[COOKIE].value.rsplit('.', 2)
        if not kunci or int(sampai) < time.time():
            return None
        benar = hmac.new(kunci, f'{user}|{sampai}'.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, benar):
            return None
    except ValueError:
        return None
    vdnet = user.startswith('vdnet:')
    username = user.split(':', 1)[1] if vdnet else user
    nama = ''
    if vdnet:
        try:
            with open(PROFIL) as f:
                nama = (json.load(f).get(username) or {}).get('nama') or ''
        except (OSError, ValueError):
            pass
    return {'user': user, 'username': username, 'nama': (nama or username)[:40], 'sumber': 'vdnet' if vdnet else 'lokal'}


def pasang_pelaku(handler, batas=1_000_000):
    """Ganti field "oleh" di badan JSON / query permintaan POST dengan nama akun yang masuk.

    Dipanggil sebelum badan dibaca handler. Mengembalikan None bila boleh lanjut, atau
    (kode, objek_galat) bila permintaan membawa "oleh" tapi tidak ada sesi login.
    Badan non-JSON atau terlalu besar dibiarkan apa adanya (unggahan berkas membawa oleh di query).
    """
    from urllib.parse import urlparse, parse_qs, urlencode
    sesi = None
    sudah = False

    def ambil():
        nonlocal sesi, sudah
        if not sudah:
            sesi, sudah = dari_cookie(handler.headers.get('Cookie')), True
        return sesi

    u = urlparse(handler.path)
    q = parse_qs(u.query, keep_blank_values=True)
    if 'oleh' in q:
        if not ambil():
            return 401, {'error': 'login_diperlukan'}
        q['oleh'] = [sesi['nama']]
        handler.path = u._replace(query=urlencode(q, doseq=True)).geturl()
        return None

    try:
        panjang = int(handler.headers.get('Content-Length') or 0)
    except ValueError:
        return None
    if panjang <= 0 or panjang > batas:
        return None
    mentah = handler.rfile.read(panjang)
    badan = mentah
    try:
        data = json.loads(mentah or b'{}')
    except ValueError:
        data = None
    if isinstance(data, dict) and 'oleh' in data:
        if not ambil():
            handler.rfile = io.BytesIO(mentah)
            return 401, {'error': 'login_diperlukan'}
        data['oleh'] = sesi['nama']
        badan = json.dumps(data, ensure_ascii=False).encode()
    handler.rfile = io.BytesIO(badan)
    del handler.headers['Content-Length']
    handler.headers['Content-Length'] = str(len(badan))
    return None
