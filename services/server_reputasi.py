"""VelocityGuard — tampilan daftar reputasi IP (halaman /server/reputasi). Hanya baca.

Isi daftar diisi timer scripts/velocityguard-reputasi (tiap 15 mnt): ipset `velocityguard_rep` di tiap server,
timeout 7 hari yang diperbarui tiap kali IP terlihat lagi + satu aturan iptables DROP di INPUT.
- ringkasan(): kiriman terakhir (reputasi.json), tren jumlah IP terpilih, status ipset/aturan/paket ditolak per server.
- daftar(): isi ipset satu server (`ipset save`, cache 5 mnt) + data 24 jam (hit, domain, server) dari kiriman terakhir;
  cari (awalan IP / CIDR), urut, halaman 100 baris. "Terakhir terlihat" dihitung dari sisa timeout.
Cepat: isi dikirim ringkas (awk "ip sisa" + gzip: 6 MB/14 dtk → 1,3 MB/2 dtk); utas latar menyegarkan status & isi
tiap server tiap SEGAR detik, request selalu dijawab dari cache (data lama dijawab dulu, penyegaran di belakang).
"""
import gzip
import ipaddress
import json
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

GUARD_DIR = Path('/var/lib/velocity/velocityguard')
SETELAN = GUARD_DIR / 'setelan.json'
HASIL = GUARD_DIR / 'reputasi.json'
RIWAYAT = GUARD_DIR / 'reputasi.jsonl'
SET = 'velocityguard_rep'
TTL = 7 * 86400
PER_HALAMAN = 100
CACHE_ISI = 300
CACHE_STATUS = 120
SEGAR = 240  # utas latar

STATUS = f'''echo "isi=$(ipset list {SET} 2>/dev/null | grep -cE '^[0-9]+[.]')"
r=$(iptables -L INPUT -v -n -x 2>/dev/null | grep "match-set {SET} " | head -1)
[ -n "$r" ] && echo "aturan=ya paket=$(echo "$r" | awk '{{print $1}}') bita=$(echo "$r" | awk '{{print $2}}')" || echo "aturan=tidak"
grep -q 'VELOCITYGUARD-REPUTASI MULAI' /usr/local/csf/bin/csfpre.sh 2>/dev/null && echo csfpre=ya || echo csfpre=tidak'''
ISI = (f"ipset list -n {SET} >/dev/null 2>&1 || {{ echo GAGAL_TIDAK_ADA; exit 0; }}; "
       f"nice -n 10 ipset save {SET} | awk '$1==\"add\"{{print $3, $5}}' | gzip -1")

_daftar_server = _perintah_server = _ssh_key_file = None
_cache = {}  # kunci → (waktu, nilai)
_kunci = {}
_kunci_umum = threading.Lock()


def pasang(daftar_server, perintah_server, ssh_key_file):
    global _daftar_server, _perintah_server, _ssh_key_file
    _daftar_server, _perintah_server, _ssh_key_file = daftar_server, perintah_server, ssh_key_file
    threading.Thread(target=_latar, daemon=True, name='reputasi-latar').start()


def _latar():
    """Hangatkan cache sejak API start lalu segarkan berkala, supaya halaman tidak menunggu SSH."""
    time.sleep(5)
    while True:
        try:
            st = _tersimpan('status', 0, _status_semua, True)
            for x in st:
                if x.get('ok'):
                    srv = next((s for s in servers() if s['host'] == x['host']), None)
                    if srv:
                        try:
                            _tersimpan(('isi', srv['host']), 0, lambda srv=srv: _isi_server(srv), True)
                        except Exception:  # noqa: BLE001
                            pass
        except Exception:  # noqa: BLE001
            pass
        time.sleep(SEGAR)


def _json(p, bawaan):
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return bawaan


def servers():
    s = _json(SETELAN, {})
    hosts = s.get('reputasi_server') or s.get('celah_server') or []
    return [x for x in _daftar_server() if x['host'] in hosts]


def _ssh(srv, remote, batas=60):
    r = subprocess.run(_perintah_server(srv, _ssh_key_file(), remote), capture_output=True, text=True, timeout=batas,
                       check=False)
    if r.returncode:
        raise RuntimeError(((r.stderr or r.stdout).strip().splitlines() or [f'exit_{r.returncode}'])[-1][:200])
    return r.stdout


def _tersimpan(kunci, ttl, fn, paksa=False):
    """Cache; satu pengambilan per kunci pada satu waktu. Ada data (walau lama) & tidak paksa → dijawab seketika,
    penyegaran jalan di belakang. Belum ada data → ditunggu."""
    with _kunci_umum:
        k = _kunci.setdefault(kunci, threading.Lock())
    lama = _cache.get(kunci)
    if lama and not paksa:
        if time.time() - lama[0] >= ttl and k.acquire(blocking=False):
            def segarkan():
                try:
                    _cache[kunci] = (time.time(), fn())
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    k.release()
            threading.Thread(target=segarkan, daemon=True).start()
        return lama[1]
    with k:
        lama = _cache.get(kunci)
        if lama and not paksa and time.time() - lama[0] < ttl:
            return lama[1]
        nilai = fn()
        _cache[kunci] = (time.time(), nilai)
        return nilai


def _status_satu(srv):
    try:
        teks = _ssh(srv, STATUS, 30)
    except Exception as e:  # noqa: BLE001
        return {'host': srv['host'], 'name': srv['name'], 'ok': False, 'error': str(e)[:200]}
    nilai = dict(x.split('=', 1) for x in teks.split() if '=' in x)
    return {'host': srv['host'], 'name': srv['name'], 'ok': True, 'isi': int(nilai.get('isi') or 0),
            'aturan': nilai.get('aturan') == 'ya', 'csfpre': nilai.get('csfpre') == 'ya',
            'paket': int(nilai.get('paket') or 0), 'bita': int(nilai.get('bita') or 0)}


def _status_semua():
    daftar = servers()
    hasil = [None] * len(daftar)

    def kerja(i):
        hasil[i] = _status_satu(daftar[i])
    utas = [threading.Thread(target=kerja, args=(i,), daemon=True) for i in range(len(daftar))]
    for t in utas:
        t.start()
    for t in utas:
        t.join(40)
    return [h or {'host': s['host'], 'name': s['name'], 'ok': False, 'error': 'timeout'} for h, s in zip(hasil, daftar)]


def _riwayat(n=96):
    if not RIWAYAT.exists():
        return []
    with RIWAYAT.open() as f:
        baris = deque(f, maxlen=n)
    out = []
    for b in baris:
        try:
            d = json.loads(b)
        except ValueError:
            continue
        out.append({'waktu': d.get('waktu'), 'jumlah': d.get('jumlah', 0)})
    return out


def ringkasan(segar=False):
    akhir = _json(HASIL, {})
    nama = {s['host']: s['name'] for s in _daftar_server()}
    return {
        'waktu': akhir.get('waktu'), 'jumlah': akhir.get('jumlah', 0),
        'sumber': [{'host': h, 'name': nama.get(h, h), 'ip': n} for h, n in (akhir.get('sumber') or {}).items()],
        'kirim': akhir.get('server') or {},
        'riwayat': _riwayat(),
        'servers': _tersimpan('status', CACHE_STATUS, _status_semua, segar),
        'ttl_hari': TTL // 86400,
    }


def _isi_server(srv):
    r = subprocess.run(_perintah_server(srv, _ssh_key_file(), ISI), capture_output=True, timeout=90, check=False)
    if r.returncode:
        raise RuntimeError(((r.stderr or b'').decode(errors='replace').strip().splitlines() or [f'exit_{r.returncode}'])[-1][:200])
    if r.stdout.startswith(b'GAGAL_TIDAK_ADA'):
        raise RuntimeError(f'ipset {SET} tidak ada di server')
    out = []
    for b in gzip.decompress(r.stdout).decode().splitlines():
        ip, _, sisa = b.partition(' ')
        out.append((ip, int(sisa) if sisa.isdigit() else 0))
    out.sort(key=lambda x: -x[1])  # urutan bawaan (terbaru) sudah jadi; urutan lain di-cache per isi
    return {'t': time.time(), 'ip': out, 'urut': {}}


_info_cache = [0, None, {}]  # mtime reputasi.json, waktu, peta ip


def _info():
    try:
        m = HASIL.stat().st_mtime
    except OSError:
        return {}, 0
    if _info_cache[0] != m:
        d = _json(HASIL, {})
        _info_cache[:] = [m, m, d.get('ip') or {}]
    return _info_cache[2], _info_cache[1]


def _saring(q):
    q = (q or '').strip()
    if not q:
        return None
    if '/' in q:
        try:
            net = ipaddress.ip_network(q, strict=False)
            return lambda ip: ':' not in ip and ipaddress.ip_address(ip) in net
        except ValueError:
            pass
    return lambda ip: ip.startswith(q) or q in ip


def daftar(host='', q='', urut='terbaru', halaman=1, segar=False):
    daftar_srv = servers()
    # host atau nama server; tanpa pilihan → server pertama yang isinya sudah ter-cache (halaman tak menunggu SSH)
    srv = (next((s for s in daftar_srv if host and host in (s['host'], s['name'])), None)
           or next((s for s in daftar_srv if ('isi', s['host']) in _cache), None)
           or (daftar_srv[0] if daftar_srv else None))
    if not srv:
        return {'error': 'tidak_ada_server'}
    try:
        isi = _tersimpan(('isi', srv['host']), CACHE_ISI, lambda: _isi_server(srv), segar)
    except Exception as e:  # noqa: BLE001
        return {'error': str(e)[:200], 'host': srv['host'], 'name': srv['name']}
    info, akhir_t = _info()
    cocok = _saring(q)
    if urut in ('hit', 'lama', 'ip'):
        siap = isi['urut'].get(urut)
        if siap is None or siap[0] != akhir_t:
            urutan = list(isi['ip'])
            if urut == 'hit':
                urutan.sort(key=lambda x: (-(info.get(x[0]) or {}).get('hit', 0), -x[1]))
            elif urut == 'lama':
                urutan.reverse()
            else:
                urutan.sort(key=lambda x: tuple(int(p) for p in x[0].split('.')) if x[0].count('.') == 3 else (999,))
            siap = isi['urut'][urut] = (akhir_t, urutan)
        sumber = siap[1]
    else:
        sumber = isi['ip']
    baris = sumber if cocok is None else [x for x in sumber if cocok(x[0])]
    try:
        halaman = max(1, int(halaman))
    except (TypeError, ValueError):
        halaman = 1
    awal = (halaman - 1) * PER_HALAMAN
    diambil = isi['t']
    potong = []
    for ip, sisa in baris[awal:awal + PER_HALAMAN]:
        i = info.get(ip) or {}
        # sisa timeout diukur saat `ipset save`; terakhir terlihat = saat timeout terakhir di-set ulang ke 7 hari
        potong.append({'ip': ip, 'sisa': max(0, int(sisa - (time.time() - diambil))),
                       'terlihat': int(diambil - (TTL - sisa)), 'aktif_24j': bool(i),
                       'hit': i.get('hit'), 'domain': i.get('domain'), 'server': i.get('server')})
    return {'host': srv['host'], 'name': srv['name'], 'diambil': int(diambil),
            'servers': [{'host': s['host'], 'name': s['name']} for s in daftar_srv], 'total': len(isi['ip']),
            'tersaring': len(baris), 'halaman': halaman, 'per_halaman': PER_HALAMAN, 'baris': potong,
            'aktif_24j': len(info)}
