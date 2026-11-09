"""Gerbang notifikasi Telegram tim server (tahap 1, 7 Nov 2026): menyaring, meringkas, mendedup. TANPA tindakan otomatis.

Semua pesan kirim_telegram_server (installer_status + server_cms/judi/lonjakan/velocityguard) lewat `kirim()`:
  putus(jenis, server, kunci, fakta) → KIRIM (langsung ke Telegram) / RINGKASAN (dihitung, dikirim 1 pesan harian ±07:57 WIB)
  / BUANG (tidak dipakai saat ini; disediakan).
Aturan per jenis ada di ATURAN di bawah. Dedup: (jenis, server, kunci) yang sama paling banyak 1x KIRIM per 6 jam; sisanya
masuk ringkasan sebagai "tertahan". Saklar mati: berkas DIR/MATI ada → semua KIRIM seperti perilaku lama (tetap dicatat).
Setiap keputusan dicatat ke DIR/keputusan.jsonl.
"""
import html
import json
import re
import threading
import time
from pathlib import Path

KIRIM, RINGKASAN, BUANG = 'KIRIM', 'RINGKASAN', 'BUANG'
DIR = Path('/var/lib/velocity/gerbang-notif')
MATI = DIR / 'MATI'                 # touch → gerbang mati (perilaku lama); rm → aktif lagi
KEADAAN = DIR / 'keadaan.json'      # {dedup: {kunci: t}, gagal: {jenis|server: {n, awal}}, ringkasan_terkirim: 'YYYY-MM-DD'}
RINGKAS = DIR / 'ringkasan.json'    # {mulai, jenis: {jenis: {jumlah, tertahan, server: {nama: n}, contoh: [...]}}}
LOG = DIR / 'keputusan.jsonl'
DEDUP_DETIK = 6 * 3600
JAM_RINGKASAN = (7, 57)             # waktu lokal server (WIB)
YAKIN_JUDI = 80
DASHBOARD = 'https://dash.velocity.ai.id/server/velocityguard'
# jenis gagal berulang: (berapa kali berturut-turut, atau lebih dari N detik sejak gagal pertama) → KIRIM
GAGAL = {'antivirus_gagal': (2, None), 'cms_gagal': (3, 24 * 3600)}

LABEL = {
    'antivirus_gagal': 'Antivirus gagal (belum berulang)',
    'cms_gagal': 'Scan CMS terjadwal gagal (belum 3x/24 jam)',
    'virus': 'Virus terdeteksi (tertahan dedup)',
    'ingat_karantina': 'Ingat karantina (karantina otomatis berkas lama)',
    'positif_palsu': 'Laporan positif palsu',
    'cms_baru': 'Kerentanan CMS baru (non-kritis/bukan kandidat virtual patch)',
    'celah_harian': 'Laporan celah harian tanpa temuan',
    'cek_ulang': 'Cek ulang celah (aman/gagal)',
    'judi_ai': 'Analisis AI judi (tanpa eskalasi)',
    'lonjakan_mulai': 'Lonjakan trafik (tertahan dedup)',
    'lonjakan_reda': 'Lonjakan trafik singkat (<30 mnt, tanpa 5xx)',
    'lain': 'Lain-lain',
}

_kunci = threading.Lock()
_kirim_mentah = None


def pasang(kirim_mentah):
    """kirim_mentah(teks) → bool: kirim langsung ke Telegram tim server (melewati gerbang)."""
    global _kirim_mentah
    _kirim_mentah = kirim_mentah


def aktif():
    return not MATI.exists()


def _baca(path, bawaan):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return bawaan


def _tulis(path, data):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    tmp.replace(path)


def _log(baris):
    DIR.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as f:
        f.write(json.dumps(baris, ensure_ascii=False, separators=(',', ':')) + '\n')


def _judul(teks):
    """Baris pertama tanpa tag HTML, untuk contoh di ringkasan."""
    return re.sub(r'<[^>]+>', '', html.unescape(str(teks or '').split('\n', 1)[0]))[:120]


def syarat(jenis, fakta=None, keadaan=None, server=''):
    """True bila aturan jenis ini meminta KIRIM (sebelum dedup). Gerbang mati → selalu True."""
    if not aktif():
        return True
    f = fakta or {}
    if jenis in GAGAL:
        batas, detik = GAGAL[jenis]
        g = ((keadaan or {}).get('gagal') or {}).get(f'{jenis}|{server}') or {}
        return g.get('n', 0) >= batas or bool(detik and g.get('awal') and time.time() - g['awal'] > detik)
    if jenis == 'virus':
        return True  # sementara tetap dikirim (belum ada karantina otomatis), didedup
    if jenis == 'ingat_karantina':
        return bool(f.get('ulang'))  # hanya bila path sama terinfeksi ulang
    if jenis == 'cms_baru':
        return f.get('kritis_vp', 0) > 0  # kritis DAN kandidat virtual patch (tanpa login)
    if jenis == 'celah_harian':
        return bool(f.get('tinggi_sedang')) or f.get('cve_baru', 0) > 0
    if jenis == 'cek_ulang':
        return bool(f.get('lolos'))
    if jenis == 'judi_ai':
        return bool(f.get('eskalasi'))  # situs_judi/diretas, yakin ≥ YAKIN_JUDI, suspend/karantina dijalankan
    if jenis == 'lonjakan_mulai':
        return f.get('menit', 0) > 30 or bool(f.get('ada_5xx'))
    if jenis == 'lonjakan_reda':
        return bool(f.get('mulai_terkirim'))
    return False  # positif_palsu, lain → ringkasan


def putus(jenis, server='', kunci='', fakta=None, teks='', simpan=True):
    """Keputusan gerbang + pencatatan (dedup, hitungan gagal, ringkasan, log). simpan=False → hanya hitung (uji)."""
    kini = time.time()
    with _kunci:
        k = _baca(KEADAAN, {})
        k.setdefault('dedup', {})
        k.setdefault('gagal', {})
        if jenis in GAGAL:
            g = k['gagal'].setdefault(f'{jenis}|{server}', {'n': 0, 'awal': kini})
            g['n'] += 1
        hidup = aktif()
        alasan = 'gerbang_mati' if not hidup else 'aturan'
        putusan = KIRIM if syarat(jenis, fakta, k, server) else RINGKASAN
        dk = f'{jenis}|{server}|{kunci}'
        tertahan = False
        if hidup and putusan == KIRIM and kini - k['dedup'].get(dk, 0) < DEDUP_DETIK:
            putusan, tertahan, alasan = RINGKASAN, True, 'dedup_6jam'
        if putusan == KIRIM:
            k['dedup'][dk] = kini
        k['dedup'] = {a: t for a, t in k['dedup'].items() if kini - t < DEDUP_DETIK}
        if putusan == RINGKASAN and simpan:
            r = _baca(RINGKAS, {})
            r.setdefault('mulai', int(kini))
            j = r.setdefault('jenis', {}).setdefault(jenis, {'jumlah': 0, 'tertahan': 0, 'server': {}, 'contoh': []})
            j['jumlah'] += 1
            j['tertahan'] += int(tertahan)
            if server:
                j['server'][server] = j['server'].get(server, 0) + 1
            judul = _judul(teks)
            if judul and judul not in j['contoh']:
                j['contoh'] = (j['contoh'] + [judul])[-3:]
            _tulis(RINGKAS, r)
        if simpan:
            _tulis(KEADAAN, k)
            _log({'t': int(kini), 'jenis': jenis, 'server': server, 'kunci': str(kunci)[:200], 'putusan': putusan,
                  'alasan': alasan, 'fakta': fakta or {}})
    return putusan


def sukses(jenis, server):
    """Reset hitungan gagal berturut-turut (scan berhasil)."""
    with _kunci:
        k = _baca(KEADAAN, {})
        if (k.get('gagal') or {}).pop(f'{jenis}|{server}', None) is not None:
            _tulis(KEADAAN, k)


def kirim(teks, jenis='lain', server='', kunci='', fakta=None):
    """Pengganti kirim_telegram_server. Gerbang galat → fail-open (KIRIM)."""
    try:
        putusan = putus(jenis, server, kunci, fakta, teks)
    except Exception as e:  # noqa: BLE001
        print(f'gerbang notif galat ({jenis}): {e}')
        putusan = KIRIM
    if putusan == KIRIM and _kirim_mentah:
        _kirim_mentah(teks)
    return putusan


def teks_ringkasan(r):
    jenis = (r or {}).get('jenis') or {}
    if not any(v.get('jumlah') for v in jenis.values()):
        return None
    mulai = time.strftime('%d/%m %H:%M', time.localtime(r.get('mulai') or time.time()))
    total = sum(v['jumlah'] for v in jenis.values())
    baris = [f"📋 <b>VelocityGuard · Ringkasan harian</b> ({total} notif sejak {mulai} WIB, tidak dikirim satu per satu)", '']
    for nama, v in sorted(jenis.items(), key=lambda x: -x[1]['jumlah']):
        srv = ', '.join(f'{html.escape(s)} {n}' for s, n in sorted(v['server'].items(), key=lambda x: -x[1])[:5])
        tahan = f", {v['tertahan']} tertahan dedup" if v.get('tertahan') else ''
        baris.append(f"• <b>{html.escape(LABEL.get(nama, nama))}</b>: {v['jumlah']}{tahan}" + (f" — {srv}" if srv else ''))
    baris += ['', DASHBOARD, 'https://dash.velocity.ai.id/server/antivirus']
    return '\n'.join(baris)[:4000]


def kirim_ringkasan():
    """Kirim satu pesan ringkasan (tidak kirim bila kosong). Berkas ringkasan dikosongkan bila terkirim."""
    with _kunci:
        r = _baca(RINGKAS, {})
        teks = teks_ringkasan(r)
        if not teks:
            return 'kosong'
        ok = bool(_kirim_mentah and _kirim_mentah(teks))
        if ok:
            arsip = DIR / 'ringkasan-arsip.jsonl'
            with arsip.open('a') as f:
                f.write(json.dumps({'t': int(time.time()), **r}, ensure_ascii=False, separators=(',', ':')) + '\n')
            RINGKAS.unlink(missing_ok=True)
        _log({'t': int(time.time()), 'jenis': 'ringkasan_harian', 'putusan': 'TERKIRIM' if ok else 'GAGAL_KIRIM'})
        return 'terkirim' if ok else 'gagal'


def jalan():
    """Thread installer_status: tiap menit cek apakah sudah ≥07:57 WIB dan ringkasan hari ini belum dikirim."""
    while True:
        try:
            lt = time.localtime()
            hari = time.strftime('%Y-%m-%d', lt)
            if (lt.tm_hour, lt.tm_min) >= JAM_RINGKASAN:
                with _kunci:
                    sudah = _baca(KEADAAN, {}).get('ringkasan_terkirim') == hari
                if not sudah and kirim_ringkasan() in ('terkirim', 'kosong'):
                    with _kunci:
                        k = _baca(KEADAAN, {})
                        k['ringkasan_terkirim'] = hari
                        _tulis(KEADAAN, k)
        except Exception as e:  # noqa: BLE001
            print(f'gerbang ringkasan: {e}')
        time.sleep(60)
