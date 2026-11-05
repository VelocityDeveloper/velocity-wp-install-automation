"""Rekap token per project dengan rincian per alur, dari /var/lib/velocity/ai/usage.jsonl (GET /api/ai/token-proyek,
halaman /token/proyek; permintaan user 2 Nov 2026).

Project: slug project-NNN (installer Laravel) atau domain situs (installer WordPress). Baris lain (bot/agen internal,
laporan, pemantau server) tidak dihitung sebagai project; jumlahnya tetap dikembalikan di `di_luar_project` supaya total
bisa ditelusuri ke usage.jsonl. `tanggal` = WIB. Hanya membaca, tidak mengubah berkas.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

AI_USAGE = Path('/var/lib/velocity/ai/usage.jsonl')
PROYEK_LARAVEL = Path('/var/lib/velocity/laravel/proyek')
WIB = timezone(timedelta(hours=7))
RE_LARAVEL = re.compile(r'^project-\d+$')
RE_DOMAIN = re.compile(r'^(?:[a-z0-9-]+\.)+[a-z]{2,}$')
RE_DOMAIN_DALAM = re.compile(r'(?:[a-z0-9-]+\.)+[a-z]{2,}')
RE_FITUR = re.compile(r'-(F\d+)$')
# Domain sistem & peran bot internal: bukan situs klien walau bentuknya domain
BUKAN_SITUS = re.compile(r'(?:^|\.)velocity\.ai\.id$')
PERAN_INTERNAL = re.compile(r'^(?:office_|agen_)')

# kunci alur -> (urutan, kelompok, label). Urutan mengikuti jalannya alur di installer.
# Dashboard memetakan ulang alur Laravel ke tahap Brief/Estimasi/Install/Agen/Review di web-vue/src/tahapToken.js
# (BRIEF_LARAVEL): mode baru di sini perlu ditambahkan juga di sana, kalau tidak masuk tahap "Lainnya".
ALUR_LARAVEL = {
    'saran': (10, 'Brief', 'Saran platform'),
    'rangkuman': (20, 'Brief', 'Rangkuman konsep'),
    'contoh': (30, 'Contoh tampilan', 'Buat contoh tampilan'),
    'contoh_revisi': (31, 'Contoh tampilan', 'Revisi contoh tampilan'),
    'kemiripan_contoh': (32, 'Contoh tampilan', 'Cek kemiripan contoh'),
    'susun': (40, 'Dokumen', 'Susun PRD & DESIGN'),
    'diagram': (41, 'Dokumen', 'ERD & flowchart'),
    'estimasi': (42, 'Dokumen', 'Fitur & estimasi'),
    'kemiripan_app': (90, 'Agen fitur', 'Cek kemiripan aplikasi'),
}
ALUR_WORDPRESS = {
    'baca_form': (10, 'Persiapan', 'Baca form klien'),
    'desain_claude:tema': (20, 'Desain', 'Agen desain: tema'),
    'desain_claude:halaman': (21, 'Desain', 'Agen desain: halaman'),
    'desain_claude': (22, 'Desain', 'Agen desain'),
    'tema': (23, 'Desain', 'Tampilan tema'),
    'fse': (24, 'Desain', 'FSE apply'),
    'konten': (30, 'Konten', 'Konten AI'),
    'isi_contoh': (31, 'Konten', 'Isi contoh'),
    'foto': (32, 'Konten', 'Foto'),
    'artikel': (33, 'Konten', 'Terjemah artikel'),
    'redaksi_klien': (34, 'Konten', 'Redaksi klien'),
    'permintaan_claude': (40, 'Permintaan', 'Agen permintaan form'),
}
TOKEN = ('total', 'input', 'cache_tulis', 'cache_baca', 'output')
_cache = {}


def domain_bersih(domain):
    """Baca form lama mencatat nama subfolder ("x.com baru", "redesign x.com"): ambil domainnya."""
    d = str(domain or '').strip().lower()
    if ' ' in d:
        m = RE_DOMAIN_DALAM.search(d)
        if m:
            return m.group(0)
    return d


def jenis_project(domain, peran):
    if RE_LARAVEL.match(domain):
        return 'laravel'
    if RE_DOMAIN.match(domain) and not BUKAN_SITUS.search(domain) and not PERAN_INTERNAL.match(peran):
        return 'wordpress'
    return None


def kunci_alur(jenis, b, revisi_awal=None):
    """-> (urutan, kelompok, label, kunci) satu baris usage. revisi_awal = {fid: epoch revisi pertama} project Laravel.

    Run agen yang mengerjakan revisi = tahap Review: ditandai `tahap: review` oleh laravel-agen (sejak 5 Nov 2026), atau
    untuk catatan lama, run yang selesai sesudah revisi pertama fitur itu diminta (fitur.json revisi[].waktu). Revisi
    hanya bisa diminta saat fitur sudah selesai dikerjakan, jadi run sesudahnya pasti run revisi."""
    peran, mode = b.get('peran') or '-', b.get('mode') or ''
    if jenis == 'laravel':
        if peran == 'laravel_agen':
            m = RE_FITUR.search(b.get('run') or '')
            fid = m.group(1) if m else '?'
            nomor = int(fid[1:]) if fid[1:].isdigit() else 999
            awal = (revisi_awal or {}).get(fid)
            if b.get('tahap') == 'review' or (awal and _epoch(b.get('ts')) >= awal):
                return 200 + nomor, 'Review', f'Revisi {fid}', f'review:{fid}'
            return 100 + nomor, 'Agen fitur', f'Agen {fid}', f'agen:{fid}'
        k = ALUR_LARAVEL.get(mode)
        return (*k, mode) if k else (80, 'Lainnya', mode or peran, mode or peran)
    kunci = peran
    if peran == 'desain_claude' and b.get('tahap'):
        kunci = f'{peran}:{b["tahap"]}'
    elif peran == 'claude_vision':  # alur asal = skrip pemanggil (cari logo, produk toko, ...)
        pemanggil = b.get('tahap') or '-'
        return 50, 'Baca gambar', f'Baca gambar: {pemanggil}', f'claude_vision:{pemanggil}'
    k = ALUR_WORDPRESS.get(kunci)
    return (*k, kunci) if k else (80, 'Lainnya', peran, kunci)


def _baca(berkas):
    st = berkas.stat()
    kunci = (str(berkas), st.st_mtime_ns, st.st_size)
    if _cache.get('kunci') != kunci:
        baris = []
        for s in berkas.read_text(errors='replace').splitlines():
            try:
                b = json.loads(s)
            except ValueError:
                continue
            if isinstance(b, dict):
                baris.append(b)
        _cache.update(kunci=kunci, baris=baris)
    return _cache['baris']


def _tanggal(ts):
    try:
        return datetime.fromisoformat(str(ts)).astimezone(WIB).strftime('%Y-%m-%d')
    except ValueError:
        return ''


def _epoch(ts):
    try:
        return datetime.fromisoformat(str(ts)).timestamp()
    except ValueError:
        return 0


def _revisi_awal(slug, dasar):
    """{fid: epoch revisi pertama} dari fitur.json; {} bila tidak ada."""
    try:
        fitur = json.loads((dasar / slug / 'fitur.json').read_text())
        return {x['id']: min(int(r['waktu']) for r in x['revisi'] if r.get('waktu'))
                for x in fitur if any(r.get('waktu') for r in x.get('revisi') or [])}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {}


def _token(b):
    masuk, keluar = int(b.get('prompt_tokens') or 0), int(b.get('completion_tokens') or 0)
    baca, tulis = int(b.get('cache_read_tokens') or 0), int(b.get('cache_creation_tokens') or 0)
    # Baris gateway hanya punya prompt/completion: seluruh prompt = input
    murni = int(b['input_tokens']) if b.get('input_tokens') is not None else masuk - baca - tulis
    return {'total': int(b.get('total_tokens') or masuk + keluar), 'input': murni, 'cache_tulis': tulis, 'cache_baca': baca, 'output': keluar}


def _kosong():
    return {**dict.fromkeys(TOKEN, 0), 'panggilan': 0, 'gagal': 0, 'parsial': 0, 'biaya_usd': 0.0, 'mulai': '', 'terakhir': ''}


def _tambah(t, b, tok):
    for k in TOKEN:
        t[k] += tok[k]
    t['panggilan'] += int(b.get('permintaan') or 1)
    t['gagal'] += 0 if b.get('ok') else 1
    t['parsial'] += 1 if b.get('parsial') else 0
    t['biaya_usd'] += float(b.get('biaya_usd') or 0)
    ts = str(b.get('ts') or '')
    t['mulai'] = min(t['mulai'] or ts, ts)
    t['terakhir'] = max(t['terakhir'], ts)


def _info_laravel(slug, dasar):
    try:
        judul = json.loads((dasar / slug / 'proyek.json').read_text()).get('judul') or ''
    except (OSError, ValueError):
        return '', {}  # project sudah dihapus: token tetap terhitung, nama tidak ada
    try:
        fitur = {x.get('id'): x.get('judul') or '' for x in json.loads((dasar / slug / 'fitur.json').read_text())}
    except (OSError, ValueError, AttributeError):
        fitur = {}
    return judul, fitur


def rekap(dari='', sampai='', berkas=AI_USAGE, dasar_laravel=PROYEK_LARAVEL):
    """dari/sampai = 'YYYY-MM-DD' WIB (inklusif), kosong = tanpa batas."""
    try:
        baris = _baca(Path(berkas))
    except OSError:
        baris = []
    per, total, luar = {}, _kosong(), {'total': 0, 'baris': 0, 'per_peran': {}}
    # Token per tanggal per installer untuk grafik harian: semua tanggal, tidak ikut dari/sampai
    harian, revisi = {}, {}
    for b in baris:
        tgl = _tanggal(b.get('ts'))
        domain, peran = domain_bersih(b.get('domain')), str(b.get('peran') or '-')
        jenis = jenis_project(domain, peran)
        if jenis and tgl:
            h = harian.setdefault(tgl, {})
            h[jenis] = h.get(jenis, 0) + _token(b)['total']
        if (dari and tgl < dari) or (sampai and tgl > sampai):
            continue
        tok = _token(b)
        if not jenis:
            luar['total'] += tok['total']
            luar['baris'] += 1
            luar['per_peran'][peran] = luar['per_peran'].get(peran, 0) + tok['total']
            continue
        p = per.setdefault(domain, {'id': domain, 'jenis': jenis, **_kosong(), 'model': set(), 'alur': {}})
        if jenis == 'laravel' and domain not in revisi:
            revisi[domain] = _revisi_awal(domain, Path(dasar_laravel))
        urut, grup, label, kunci = kunci_alur(jenis, b, revisi.get(domain))
        a = p['alur'].setdefault(kunci, {'kunci': kunci, 'urut': urut, 'kelompok': grup, 'label': label, **_kosong(), 'model': set()})
        model = b.get('model') or b.get('model_id') or '-'
        for t in (total, p, a):
            _tambah(t, b, tok)
        p['model'].add(model)
        a['model'].add(model)
    hasil = []
    for p in per.values():
        p['nama'], fitur = _info_laravel(p['id'], Path(dasar_laravel)) if p['jenis'] == 'laravel' else ('', {})
        alur = sorted(p.pop('alur').values(), key=lambda a: (a['urut'], a['label']))
        for a in alur:
            a.pop('urut')
            a['model'] = sorted(a['model'])
            a['biaya_usd'] = round(a['biaya_usd'], 4)
            if a['kunci'].startswith(('agen:', 'review:')):
                a['judul'] = fitur.get(a['kunci'].split(':', 1)[1], '')
        p['alur'] = alur
        p['model'] = sorted(p['model'])
        p['biaya_usd'] = round(p['biaya_usd'], 4)
        hasil.append(p)
    hasil.sort(key=lambda p: -p['total'])
    total['biaya_usd'] = round(total['biaya_usd'], 4)
    luar['per_peran'] = dict(sorted(luar['per_peran'].items(), key=lambda kv: -kv[1]))
    return {'proyek': hasil, 'total': total, 'di_luar_project': luar, 'harian': dict(sorted(harian.items())),
            'dari': dari, 'sampai': sampai, 'file': str(berkas)}


def rincian_alur(id_proyek, kunci, berkas=AI_USAGE, dasar_laravel=PROYEK_LARAVEL, batas=40):
    """Rincian satu poin alur (GET /api/ai/token-proyek/rincian): daftar run + gabungan bagian yang makan token.
    Seluruh riwayat project, tanpa saringan tanggal. Satu run = baris-baris usage berurutan dengan skrip & run yang sama
    yang ditulis dalam selang <= 3 detik (satu baris per model; ts dibuat ulang per baris). `rincian` per run hanya ada untuk run agen sejak 5 Nov 2026 (catat_claude.HitungUsage)."""
    try:
        baris = _baca(Path(berkas))
    except OSError:
        baris = []
    domain = domain_bersih(id_proyek)
    revisi = None
    jalan, total, akhir = [], _kosong(), {}
    alat, berinci = {}, {'run': 0, 'total': 0, 'giliran': 0, 'konteks_awal': 0, 'konteks_akhir': 0, 'output': 0}
    for b in baris:
        if domain_bersih(b.get('domain')) != domain:
            continue
        jenis = jenis_project(domain, str(b.get('peran') or '-'))
        if not jenis:
            continue
        if jenis == 'laravel' and revisi is None:
            revisi = _revisi_awal(domain, Path(dasar_laravel))
        if kunci_alur(jenis, b, revisi)[3] != kunci:
            continue
        tok = _token(b)
        _tambah(total, b, tok)
        k, detik = (b.get('script'), b.get('run')), _epoch(b.get('ts'))
        j = akhir.get(k)
        if not j or abs(detik - j['_detik']) > 3:
            j = akhir[k] = {'ts': str(b.get('ts') or ''), **_kosong(), 'giliran': 0, 'model': [], '_detik': detik}
            jalan.append(j)
        j['_detik'] = detik
        _tambah(j, b, tok)
        j['giliran'] = max(j['giliran'], int(b.get('giliran') or 0))
        j['model'].append(b.get('model') or b.get('model_id') or '-')
        r = b.get('rincian')
        if isinstance(r, dict) and r.get('alat'):
            j['rincian'] = r
    # Penyebut persen = total semua model run berinci (subagen bisa memakai model lain di baris lain)
    for j in jalan:
        r = j.get('rincian')
        if not r:
            continue
        berinci['run'] += 1
        berinci['total'] += j['total']
        for x in ('giliran', 'konteks_awal', 'konteks_akhir', 'output'):
            berinci[x] += int(r.get(x) or 0)
        for nama, a in r['alat'].items():
            g = alat.setdefault(nama, {'n': 0, 'tambah': 0, 'beban': 0, 'run': 0})
            for x in ('n', 'tambah', 'beban'):
                g[x] += int(a.get(x) or 0)
            g['run'] += 1
    daftar = sorted(jalan, key=lambda j: j['ts'], reverse=True)
    for j in daftar:
        j.pop('_detik', None)
        j['biaya_usd'] = round(j['biaya_usd'], 4)
        for x in ('mulai', 'terakhir'):
            j.pop(x, None)
    total['biaya_usd'] = round(total['biaya_usd'], 4)
    total['giliran'] = sum(j['giliran'] for j in daftar)
    terbesar = max(daftar, key=lambda j: j['total'], default=None)
    return {'id': domain, 'kunci': kunci, 'total': total, 'jumlah_run': len(daftar), 'run': daftar[:batas],
            'run_terbesar': terbesar, 'berinci': berinci,
            'alat': dict(sorted(alat.items(), key=lambda kv: -kv[1]['beban']))}
