# Uji ganti channel youtube-video tanpa jaringan: utama kena uploadLimitExceeded (400), cadangan berhasil.
import importlib.machinery, importlib.util, json, os, sys, tempfile
from pathlib import Path
D = Path(tempfile.mkdtemp())
for sub in ('rahasia', 'cache', 'klien'):
    (D/sub).mkdir()
(D/'klien/a.mp4').write_bytes(b'0' * 1000)
os.environ.update(VELOCITY_YOUTUBE_TOKEN=str(D/'rahasia/youtube-token.json'), VELOCITY_YOUTUBE_CACHE=str(D/'cache'))
(D/'rahasia/youtube-token.json').write_text(json.dumps({'refresh_token': 'U', 'email': 'utama@x'}))
(D/'rahasia/youtube-token-dua.json').write_text(json.dumps({'refresh_token': 'C', 'email': 'dua@x'}))
SKRIP = Path(__file__).resolve().parent.parent / 'scripts'
sys.path.insert(0, str(SKRIP))
L = importlib.machinery.SourceFileLoader('yv', str(SKRIP / 'youtube-video'))
m = importlib.util.module_from_spec(importlib.util.spec_from_loader('yv', L)); L.exec_module(m)
m.klien = lambda: ('id', 'rahasia')
m.berkas_video = lambda domain: (D/'klien', [D/'klien/a.mp4'])
m.info_video = lambda p: (True, 10.0)
def minta(url, data=None, headers=None, method=None, timeout=60):
    if url == m.TOKEN_URL:
        return 200, {}, {'access_token': 'akses-' + data['refresh_token'], 'expires_in': 3600}
    if url == m.UPLOAD_URL:
        if headers['Authorization'] == 'Bearer akses-U':
            return 400, {}, {'error': {'errors': [{'reason': 'uploadLimitExceeded'}]}}
        return 200, {'Location': 'https://sesi/1'}, {}
    if url == 'https://sesi/1':
        return 200, {}, {'id': 'VID1', 'status': {'privacyStatus': 'unlisted'}}
    raise AssertionError(url)
m.minta = minta
assert m.unggah({'domain': 'uji.com'}, 'unlisted', 12, False) == 0
v = list(json.loads((D/'cache/uji.com.json').read_text())['video'].values())[0]
assert v['id'] == 'VID1' and v['akun'] == 'dua@x', v
# Semua channel penuh → KuotaHabis (kode 3), bukan galat biasa.
(D/'cache/uji.com.json').unlink(); m.pakai_token(m.TOKEN_UTAMA)
m.minta = lambda url, data=None, headers=None, method=None, timeout=60: (
    minta(url, data, headers, method) if url == m.TOKEN_URL else (400, {}, {'error': {'errors': [{'reason': 'uploadLimitExceeded'}]}}))
try:
    m.unggah({'domain': 'uji.com'}, 'unlisted', 12, False); raise SystemExit('GAGAL: harus KuotaHabis')
except m.KuotaHabis as e:
    print('semua penuh →', e)
print('LOLOS')
