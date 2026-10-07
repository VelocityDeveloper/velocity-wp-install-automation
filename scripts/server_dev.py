#!/usr/bin/env python3
"""Server dev Laravel di Local PC: status nyala/mati/perlu restart, aksi, dan mati otomatis saat menganggur.

Daftar project dari config/local-projects.json (yang stack-nya Laravel). Dipakai:
  - /api/laravel/server (GET) dan /api/laravel/server/<id>/<nyala|mati|restart> (POST), lewat laravel_proyek.handle
  - server-dev-tidur.timer tiap jam: `server_dev.py --tidurkan` mematikan project tanpa aktivitas >= BATAS_DIAM
    (PC pernah hang karena RAM habis oleh 14 project dev yang menyala 24 jam, Okt 2026).

Aktivitas = request HTTP selain "/" (cek kesehatan dashboard hanya memanggil "/"), berkas kode diubah,
commit git, atau tombol Nyalakan/Restart. Project dengan "selalu_nyala": true tidak pernah dimatikan otomatis.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROJECTS_FILE = REPO / 'config' / 'local-projects.json'
STATE_FILE = Path('/var/lib/velocity/laravel/server-dev.json')
BATAS_DIAM = 24 * 3600
AKSI = ('nyala', 'mati', 'restart')
# Folder kode yang dipantau untuk aktivitas pengembangan (vendor/node_modules/storage tidak).
FOLDER_KODE = ('app', 'routes', 'resources', 'database', 'config', 'tests', 'bootstrap/app.php', '.env')
REQUEST_RE = re.compile(r'^\s*\d{4}-\d\d-\d\d \d\d:\d\d:\d\d (/\S*) .*~ [\d.]+\s*m?s')

_kunci = threading.Lock()
_cache = {}


def _jalankan(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (subprocess.TimeoutExpired, OSError) as e:
        return 1, str(e)


def _tersimpan(kunci, ttl, fn):
    """Cache sederhana per kunci; pemeriksaan journal & berkas mahal bila dipanggil tiap polling."""
    with _kunci:
        ada = _cache.get(kunci)
        if ada and time.time() - ada[0] < ttl:
            return ada[1]
    nilai = fn()
    with _kunci:
        _cache[kunci] = (time.time(), nilai)
    return nilai


def daftar_project():
    try:
        semua = json.loads(PROJECTS_FILE.read_text()).get('projects', [])
    except (OSError, ValueError):
        return []
    return [p for p in semua if 'laravel' in (p.get('stack') or '').lower() and p.get('layanan')]


def baca_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def ubah_state(fn):
    with _kunci:
        data = baca_state()
        fn(data)
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=1))
        os.replace(tmp, STATE_FILE)


def info_layanan(nama):
    _, out = _jalankan(['systemctl', 'show', f'{nama}.service', '--timestamp=unix',
                        '-p', 'ActiveState', '-p', 'SubState', '-p', 'ActiveEnterTimestamp',
                        '-p', 'MemoryCurrent', '-p', 'MemoryMax', '-p', 'LoadState'])
    p = dict(l.split('=', 1) for l in out.splitlines() if '=' in l)
    angka = lambda k: int(p[k]) if p.get(k, '').isdigit() else None
    mulai = p.get('ActiveEnterTimestamp', '').lstrip('@')
    return {
        'nama': nama,
        'ada': p.get('LoadState') == 'loaded',
        'state': p.get('ActiveState', '?'),
        'aktif': p.get('ActiveState') in ('active', 'activating', 'reloading'),
        'gagal': p.get('ActiveState') == 'failed',
        'sejak': int(mulai) if mulai.isdigit() else None,
        'memori': angka('MemoryCurrent'),
        'memori_max': angka('MemoryMax'),
    }


def _layanan_web(p):
    return next((n for n in p['layanan'] if n.endswith('-dev')), p['layanan'][0])


def request_terakhir(p):
    """Waktu request HTTP nyata terakhir (bukan "/") dari journal layanan web, maks 48 jam ke belakang."""
    def cari():
        _, out = _jalankan(['journalctl', '-u', f'{_layanan_web(p)}.service', '--since', '-48h', '-r',
                            '-n', '5000', '-o', 'short-unix', '--no-pager', '-q'])
        for baris in out.splitlines():
            waktu, _, pesan = baris.partition(' ')
            m = REQUEST_RE.match(pesan.split(': ', 1)[-1])
            if m and m.group(1) != '/':
                try:
                    return int(float(waktu))
                except ValueError:
                    continue
        return None
    return _tersimpan(('http', p['id']), 60, cari)


def berkas_terakhir(p):
    """mtime terbaru berkas kode project (agen/developer sedang bekerja)."""
    def cari():
        dasar, terbaru = Path(p.get('folder') or '/nonexistent'), 0
        for sub in FOLDER_KODE:
            akar = dasar / sub
            if akar.is_file():
                terbaru = max(terbaru, akar.stat().st_mtime)
                continue
            for d, subdir, berkas in os.walk(akar):
                subdir[:] = [s for s in subdir if s not in ('node_modules', 'vendor', '.git')]
                for b in berkas:
                    try:
                        terbaru = max(terbaru, os.stat(os.path.join(d, b)).st_mtime)
                    except OSError:
                        pass
        git = dasar / '.git'
        if git.is_dir():
            _, out = _jalankan(['git', '-c', 'safe.directory=*', '-C', str(dasar), 'log', '-1', '--format=%ct'])
            if out.strip().isdigit():
                terbaru = max(terbaru, int(out.strip()))
        return int(terbaru) or None
    return _tersimpan(('berkas', p['id']), 300, cari)


def _kode_http(port):
    _, out = _jalankan(['curl', '-s', '-o', '/dev/null', '-m', '5', '-w', '%{http_code}',
                        f'http://127.0.0.1:{int(port)}/'], timeout=7)
    return int(out) if out.strip().isdigit() else 0


def status_project(p, state=None):
    state = baca_state() if state is None else state
    s = state.get(p['id'], {})
    layanan = [info_layanan(n) for n in p['layanan']]
    layanan = [l for l in layanan if l['ada']]
    aktif = [l for l in layanan if l['aktif']]
    http_t, berkas_t = request_terakhir(p), berkas_terakhir(p)
    aktivitas = max(filter(None, [http_t, berkas_t, s.get('aktivitas'), s.get('dinyalakan')]), default=None)
    alasan = []
    if not layanan:
        kondisi = 'tidak_ada'
    elif not aktif:
        kondisi = 'mati'
    else:
        kondisi = 'nyala'
        mati = [l['nama'] for l in layanan if not l['aktif']]
        if mati:
            alasan.append(f"layanan tidak jalan: {', '.join(mati)}")
        kode = _tersimpan(('kode', p['id']), 30, lambda: _kode_http(p['port'])) if p.get('port') else 200
        if kode == 0 or kode >= 500:
            alasan.append(f'halaman tidak merespons (HTTP {kode or "timeout"})')
        # queue:work & scheduler memuat kode sekali saat mulai; kode yang berubah sesudahnya belum terpakai.
        pekerja = [l for l in aktif if not l['nama'].endswith('-dev') and l['sejak']]
        if berkas_t and pekerja and berkas_t > min(l['sejak'] for l in pekerja) + 60:
            alasan.append('kode berubah sesudah queue/scheduler dijalankan')
        penuh = [l['nama'] for l in aktif if l['memori'] and l['memori_max'] and l['memori'] > .9 * l['memori_max']]
        if penuh:
            alasan.append(f"memori hampir batas: {', '.join(penuh)}")
        if alasan:
            kondisi = 'perlu_restart'
    mulai = min((l['sejak'] for l in aktif if l['sejak']), default=None)
    dasar = max(filter(None, [aktivitas, mulai]), default=None)
    return {
        'id': p['id'], 'nama': p.get('nama'), 'port': p.get('port'), 'stack': p.get('stack'),
        'kondisi': kondisi, 'alasan': alasan,
        'layanan': [{k: l[k] for k in ('nama', 'state', 'sejak', 'memori', 'memori_max')} for l in layanan],
        'memori': sum(l['memori'] or 0 for l in aktif),
        'aktivitas': aktivitas,
        'aktivitas_sumber': {'http': http_t, 'berkas': berkas_t},
        'selalu_nyala': bool(p.get('selalu_nyala')),
        'mati_otomatis': None if p.get('selalu_nyala') or not aktif or not dasar else dasar + BATAS_DIAM,
        'dimatikan': s.get('dimatikan'),
    }


def status_semua():
    daftar, state = daftar_project(), baca_state()
    hasil = [None] * len(daftar)

    def kerja(i, p):
        hasil[i] = status_project(p, state)
    utas = [threading.Thread(target=kerja, args=(i, p)) for i, p in enumerate(daftar)]
    for t in utas:
        t.start()
    for t in utas:
        t.join()
    return {'server': hasil, 'batas_diam': BATAS_DIAM, 'diperiksa': int(time.time())}


def aksi(pid, jenis, oleh=''):
    p = next((x for x in daftar_project() if x['id'] == pid), None)
    if not p:
        raise ValueError('server_tidak_dikenal')
    if jenis not in AKSI:
        raise ValueError('aksi_tidak_sah')
    if jenis == 'mati' and p.get('selalu_nyala'):
        raise ValueError('server_selalu_nyala')
    perintah = {'nyala': 'start', 'mati': 'stop', 'restart': 'restart'}[jenis]
    kode, out = _jalankan(['systemctl', perintah, *[f'{n}.service' for n in p['layanan']]], timeout=60)
    if kode:
        raise ValueError('systemctl_gagal')
    sekarang = int(time.time())

    def catat(d):
        s = d.setdefault(pid, {})
        if jenis == 'mati':
            s['dimatikan'] = {'waktu': sekarang, 'oleh': oleh or 'dashboard'}
        else:
            s['dinyalakan'] = sekarang
            s.pop('dimatikan', None)
    ubah_state(catat)
    # artisan serve butuh beberapa detik sebelum menjawab; tunggu supaya status tidak langsung "tidak merespons".
    if jenis != 'mati' and p.get('port'):
        for _ in range(20):
            if _kode_http(p['port']):
                break
            time.sleep(1)
    with _kunci:
        for k in [k for k in _cache if k[1] == pid]:
            _cache.pop(k)
    return status_project(p)


def tidurkan(uji=False):
    """Dipanggil timer tiap jam: simpan aktivitas terakhir, matikan project yang diam >= BATAS_DIAM."""
    sekarang = int(time.time())
    for p in daftar_project():
        st = status_project(p)
        if st['aktivitas']:
            ubah_state(lambda d: d.setdefault(p['id'], {}).update(aktivitas=st['aktivitas']))
        if st['mati_otomatis'] and sekarang >= st['mati_otomatis']:
            print(f"matikan {p['id']}: aktivitas terakhir {time.strftime('%Y-%m-%d %H:%M', time.localtime(st['aktivitas'] or 0))}")
            if not uji:
                aksi(p['id'], 'mati', 'otomatis (diam 24 jam)')
        elif uji:
            sisa = (st['mati_otomatis'] - sekarang) / 3600 if st['mati_otomatis'] else None
            print(f"{p['id']:34} {st['kondisi']:14} sisa={'-' if sisa is None else f'{sisa:.1f}j'} {'; '.join(st['alasan'])}")


if __name__ == '__main__':
    if '--tidurkan' in sys.argv:
        tidurkan(uji='--uji' in sys.argv)
    else:
        print(json.dumps(status_semua(), indent=1))
