"""Object Storage media klien (Garage di PC Backup) untuk dashboard, lewat `ssh pc-backup`. Hanya membaca.

Sumber: /srv/backup/s3-pakai/terkini.json (s3-pakai-catat.timer tiap jam :05) + health Garage admin :3903 (seketika).
Sama dengan panel https://storage.velocity.ai.id.
Persen per klien = angka kartu wp-admin ((file + DB + media) / paket), dari ringkas.json layanan media di server
hosting (velocity-media-jaga periksa, tiap 15 mnt). Bucket tanpa ringkasan tetap memakai persen jatah bucket.
"""
import json
import subprocess
import threading
import time

from pc_backup import HOST

CACHE_DETIK = 30
SERVER_HOSTING = ['sanke']   # alias ssh server yang memasang layanan media
SKRIP = ('cat /srv/backup/s3-pakai/terkini.json 2>/dev/null || printf null; echo; '
         'curl -s -o /dev/null -m 5 -w "%{http_code}" http://127.0.0.1:3903/health')

_kunci = threading.Lock()
_cache = {'waktu': 0, 'data': None}


def _ambil():
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', HOST, SKRIP],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or '\n' not in r.stdout.strip():
        raise RuntimeError((r.stderr.strip().splitlines() or ['ssh gagal'])[-1])
    isi, kode = r.stdout.strip().rsplit('\n', 1)
    pakai = json.loads(isi)
    ringkas = _ringkas()
    for b in (pakai or {}).get('bucket') or []:
        a = ringkas.get(b.get('nama'))
        if a:
            # byte/max_byte = angka yang sudah ditampilkan halaman -> total paket seperti kartu wp-admin;
            # ukuran asli bucket & jatah cadangan Garage tetap di byte_bucket/max_byte_bucket
            b.update(byte_bucket=b.get('byte'), max_byte_bucket=b.get('max_byte'),
                     byte=a['hosting'] + a['media'], max_byte=a['paket'], persen=a['persen'], paket=a['paket'],
                     hosting=a['hosting'], media=a['media'], user=a['user'], server=a['server'],
                     domain=a.get('domain') or b.get('domain'))
    return {'pakai': pakai, 'garage_hidup': kode == '200'}


def _ringkas():
    """{bucket: angka kartu wp-admin}; server tak terjangkau dilewati (persen jatah bucket tetap dipakai)."""
    hasil = {}
    for srv in SERVER_HOSTING:
        try:
            r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', srv,
                                'cat /var/lib/velocity-media/ringkas.json'], capture_output=True, text=True, timeout=20)
            for bucket, a in json.loads(r.stdout).get('akun', {}).items():
                hasil[bucket] = dict(a, server=srv)
        except Exception:
            pass
    return hasil


def status(segar=False):
    with _kunci:  # SSH ±1 dtk; kunci cegah banyak tab memanggil bersamaan
        if segar or time.time() - _cache['waktu'] > CACHE_DETIK:
            try:
                _cache.update(data=_ambil(), galat=None)
            except Exception as e:  # PC Backup tak terjangkau: data lama tetap dikirim bersama galat
                _cache['galat'] = str(e)[:300]
            _cache['waktu'] = time.time()
        d = _cache['data'] or {'pakai': None, 'garage_hidup': None}
        return {**d, 'galat': _cache.get('galat'), 'diperbarui': int(_cache['waktu']),
                'panel': 'https://storage.velocity.ai.id'}
