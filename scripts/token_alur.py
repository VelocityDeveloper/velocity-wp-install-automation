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


def kunci_alur(jenis, b):
    """-> (urutan, kelompok, label, kunci) satu baris usage."""
    peran, mode = b.get('peran') or '-', b.get('mode') or ''
    if jenis == 'laravel':
        if peran == 'laravel_agen':
            m = RE_FITUR.search(b.get('run') or '')
            fid = m.group(1) if m else '?'
            nomor = int(fid[1:]) if fid[1:].isdigit() else 999
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
    harian = {}
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
        urut, grup, label, kunci = kunci_alur(jenis, b)
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
            if a['kunci'].startswith('agen:'):
                a['judul'] = fitur.get(a['kunci'][5:], '')
        p['alur'] = alur
        p['model'] = sorted(p['model'])
        p['biaya_usd'] = round(p['biaya_usd'], 4)
        hasil.append(p)
    hasil.sort(key=lambda p: -p['total'])
    total['biaya_usd'] = round(total['biaya_usd'], 4)
    luar['per_peran'] = dict(sorted(luar['per_peran'].items(), key=lambda kv: -kv[1]))
    return {'proyek': hasil, 'total': total, 'di_luar_project': luar, 'harian': dict(sorted(harian.items())),
            'dari': dari, 'sampai': sampai, 'file': str(berkas)}
