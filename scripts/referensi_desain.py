#!/usr/bin/env python3
"""Referensi desain web dari FORM ISIAN -> rencana desain FSE (acuan utama).

Keputusan user 2026-09-15: setelah paket dicek, untuk Paket G & paket custom
(Portal Berita Custom, Toko Online Custom) periksa isian "website yang ingin
dicontoh". Kalau ada, desain FSE mengikuti referensi itu sebagai ACUAN UTAMA:
  - tata letak & gaya mengikuti referensi: urutan dan jenis seksi beranda, header
    (terang/gelap, posisi logo & menu, tombol ajakan), jenis hero, latar tiap
    seksi, jumlah kolom kartu, font, radius tombol & kartu, footer;
  - konten tetap milik klien (teks, foto, logo) — tidak menyalin isi referensi,
    dan seksi yang tidak punya data jujur (testimoni, logo klien, angka) dilewati;
  - warna klien menang; warna referensi hanya dipakai kalau klien tidak menyebut
    warna dan tidak punya logo/compro (diputuskan di fse-apply).
Menggantikan aturan 2026-09-14 "jangan terlalu mirip referensi".

Pemakaian:  referensi_desain.py <manifest|domain> [--segar]
Hasil:      /var/lib/velocity/fse-rencana/<domain>/desain-referensi.json
            (+ referensi-ukur.json mentah dan referensi-potret.png)
Baris terakhir keluaran: `referensi: ada:<url> ...` | `referensi: tidak_ada` | `referensi: gagal:<alasan>`
Pengukuran dilakukan scripts/referensi-desain.js (Playwright, DOM terender).
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENCANA_DIR = Path('/var/lib/velocity/fse-rencana')
ON_PROGRESS = Path('/home/On Progress')
UA = 'velocity-installer/1.0 (+https://velocitydeveloper.com)'
# Naikkan bila bentuk rencana/klasifikasi berubah: tembolok versi lama diukur ulang
# (versi 2: warna tombol WhatsApp mengambang dibuang dari warna referensi).
VERSI = 2
WARNA_BUKAN_MEREK = {'#25d366', '#128c7e', '#075e54', '#34b7f1', '#dcf8c6'}

# Font sistem: tidak perlu dimuat dari Google Fonts.
FONT_SISTEM = {'arial', 'helvetica', 'helvetica neue', 'georgia', 'times new roman', 'times', 'verdana',
               'tahoma', 'segoe ui', 'system-ui', '-apple-system', 'sans-serif', 'serif', 'roboto'}


def referensi_form(domain):
    """URL "website yang ingin dicontoh" + catatan klien dari FORM ISIAN.

    Contoh isian template form (alamatWebContoh.com) dan tautan syarat & ketentuan
    Velocity bukan referensi."""
    sys.path.insert(0, str(HERE))
    try:
        from client_form import read_client_form
        teks = read_client_form(ON_PROGRESS / domain).get('text') or ''
    except Exception:
        return {}
    awal = re.search(r'INGIN\s+DICONTOH|YANG\s+ANDA\s+SUKAI\s+DESAINNYA', teks, re.I)
    if not awal:
        return {}
    akhir = re.search(r'Contoh\s+Jawaban|WARNA\s+TEMA', teks[awal.end():], re.I)
    potong = teks[awal.end():awal.end() + (akhir.start() if akhir else 1500)]
    url = next((u.rstrip('.,)"') for u in re.findall(r'https?://[^\s"<>]+', potong)
                if not re.search(r'velocitydeveloper|alamatwebcontoh|example\.', u, re.I)), '')
    if not url:
        return {}
    host = urllib.parse.urlparse(url).netloc.lower().replace('www.', '')
    catatan = next((b.strip() for b in potong.splitlines()
                    if host in b.lower() and not b.strip().startswith(('HYPERLINK', 'http'))), '')
    return {'url': url, 'catatan': catatan[:400]}


# ---------------------------------------------------------------------------
# Klasifikasi seksi
# ---------------------------------------------------------------------------

# Urutan penting: yang lebih spesifik dulu ("Kenapa memilih layanan kami" = keunggulan).
KATA_KUNCI = [
    ('testimoni', r'testimon|review|ulasan|kata (mereka|klien|pelanggan)|what (our )?(clients?|customers?) say'),
    ('faq', r'\bfaq\b|pertanyaan|tanya jawab|frequently'),
    ('alur', r'\balur\b|langkah|cara (kerja|pesan|order|pemesanan)|\bproses\b|how it works|\bsteps?\b'),
    ('keunggulan', r'kenapa|mengapa|\bwhy\b|keunggulan|kelebihan|alasan|advantage|benefit'),
    ('artikel', r'artikel|berita|\bblog\b|\bnews\b|latest update|update terbaru|tulisan'),
    ('klien', r'klien kami|\bclients?\b|partner|\bmitra\b|dipercaya|trusted|kepercayaan'),
    ('galeri', r'galeri|gallery|portofolio|portfolio|proyek|project|dokumentasi'),
    ('produk', r'produk|product|katalog|catalog|koleksi|collection|\bshop\b|\btoko\b|kategori|category'),
    ('layanan', r'layanan|services?\b|\bjasa\b|solusi|solutions?\b|what we do'),
    ('tentang', r'tentang|\babout\b|profil|siapa kami|who we are|welcome|selamat datang'),
    ('kontak', r'kontak|contact|hubungi|lokasi|alamat|location'),
]


def warna_hex(h):
    h = (h or '#ffffff').lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) == 6 else (255, 255, 255)


def latar_seksi(s):
    if s.get('foto_latar'):
        return 'foto'
    if s['luminansi'] < 110:
        return 'gelap'
    r, g, b = warna_hex(s['latar'])
    if max(r, g, b) - min(r, g, b) >= 40:
        return 'aksen'
    return 'abu' if s['luminansi'] < 249 else 'terang'


def jenis_seksi(s, indeks):
    k = s.get('kartu') or {}
    ju = s.get('judul_utama') or {}
    teks_judul = ' '.join([ju.get('teks', '')] + list(s.get('judul') or [])).lower()
    if indeks == 0 and s['tinggi'] >= 350 and (s['foto_latar'] or s['slider'] or s['berdampingan']
                                               or ju.get('ukuran', 0) >= 34 or ju.get('tag') == 'h1'):
        return 'hero'
    if s['angka_besar'] >= 3:
        return 'angka'
    if s['form'] or s['peta']:
        return 'kontak'
    judul_utama = (ju.get('teks') or '').lower()
    for sumber in (judul_utama, teks_judul):
        for jenis, pola in KATA_KUNCI:
            if not re.search(pola, sumber):
                continue
            # Kata kunci saja tidak cukup untuk jenis yang butuh bentuk tertentu.
            if jenis == 'klien' and not (s['foto'] >= 4 and s['kata'] < 8 * max(s['foto'], 1)):
                continue
            if jenis == 'galeri' and s['foto'] < 3:
                continue
            if jenis == 'faq' and not s['akordeon'] and s['kata'] < 40:
                continue
            return jenis
    if s['akordeon']:
        return 'faq'
    if k.get('n', 0) >= 6 and s['kata'] <= 6:
        return 'klien'  # deret logo tanpa teks
    if s['foto'] >= 6 and s['kata'] < 60:
        return 'galeri'
    if s['tinggi'] <= 320 and s['tombol'] >= 1 and s['kata'] <= 70:
        return 'ajakan'
    if s['berdampingan'] and s['foto'] >= 1:
        return 'tentang'
    if k.get('ikon', 0) >= 3:
        return 'keunggulan'
    if k.get('n', 0) >= 3 and k.get('foto', 0) >= 3:
        return 'layanan'
    if s['video']:
        return 'video'
    return 'lain'


def hero_varian(s):
    if not s:
        return 'foto'
    if s['foto_latar'] or s['slider']:
        return 'foto'
    if s['berdampingan']:
        return 'terbelah'
    if s['luminansi'] < 110:
        return 'warna'
    return 'terang'


def bersihkan_seksi(seksi):
    """Buang seksi yang seluruhnya berada di dalam seksi sebelumnya & sisa kosong.

    Tumpang tindih sebagian tetap seksi sendiri: kartu layanan erhaeschemical.com
    sengaja naik menutupi bagian bawah hero."""
    hasil = []
    for s in sorted(seksi, key=lambda x: x['y']):
        if hasil and s['y'] + s['tinggi'] <= hasil[-1]['y'] + hasil[-1]['tinggi'] + 20:
            continue
        if s['tinggi'] < 120 and s['kata'] <= 2 and s['foto'] == 0:
            continue
        hasil.append(s)
    return hasil


def google_font(nama):
    """Nama font tersedia di Google Fonts? (fonts.googleapis.com css2 membalas 200)."""
    if not nama or nama.lower() in FONT_SISTEM:
        return False
    url = 'https://fonts.googleapis.com/css2?family=' + urllib.parse.quote(nama) + ':wght@400;700&display=swap'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 Chrome/126.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def rencana(ukur, ref):
    """Data ukur mentah -> rencana desain yang dipakai fse-apply."""
    h = ukur.get('header') or {}
    seksi = bersihkan_seksi(ukur.get('seksi') or [])
    bawah_header = (h.get('tinggi') or 0) + 250
    susunan, catatan = [], []
    pertama = seksi[0] if seksi else None
    if not pertama or (pertama['y'] > bawah_header and not h.get('transparan_di_atas_hero')) or pertama['y'] > 600:
        # Slider/banner di atas seksi pertama tidak terukur sebagai blok: tetap ada hero.
        susunan.append({'jenis': 'hero', 'varian': 'foto', 'latar': 'foto', 'terukur': False})
        catatan.append('hero_tak_terukur')
    for i, s in enumerate(seksi):
        jenis = jenis_seksi(s, i if not catatan else i + 1)
        if jenis == 'lain':
            catatan.append(f"seksi_tak_dikenal:{(s.get('judul_utama') or {}).get('teks', '')[:30]}")
            continue
        if susunan and susunan[-1]['jenis'] == jenis:
            continue  # deret logo/galeri yang terpecah dua baris
        k = s.get('kartu') or {}
        butir = {
            'jenis': jenis, 'latar': latar_seksi(s),
            'kolom': max(2, min(int(k.get('kolom') or 3), 6)) if k.get('n', 0) >= 2 else 0,
            'kartu_foto': bool(k.get('foto', 0) >= 2), 'kartu_ikon': bool(k.get('ikon', 0) >= 2),
            'rata': 'tengah' if (s.get('judul_utama') or {}).get('rata') == 'center' else 'kiri',
            'berdampingan': bool(s['berdampingan']), 'slider': bool(s['slider']),
            'judul_referensi': (s.get('judul_utama') or {}).get('teks', '')[:60],
        }
        if jenis == 'hero':
            butir['varian'] = hero_varian(s)
        susunan.append(butir)

    kartu_pertama = next((s['kartu'] for s in seksi if (s.get('kartu') or {}).get('n', 0) >= 2), {})
    font = ukur.get('font') or {}
    tombol = ukur.get('tombol') or {}
    footer = ukur.get('footer') or {}
    font_teks, font_judul = font.get('teks', ''), font.get('judul', '') or font.get('teks', '')
    return {
        'versi': VERSI,
        'url': ref.get('url', ''), 'catatan_klien': ref.get('catatan', ''),
        'header': {
            'gelap': bool(h.get('gelap')), 'logo_posisi': h.get('logo_posisi') or 'kiri',
            'menu_posisi': h.get('menu_posisi') or 'kanan', 'tombol_ajakan': bool(h.get('tombol_ajakan')),
            'lengket': bool(h.get('lengket')), 'menu_kapital': bool(h.get('huruf_menu_kapital')),
            'topbar': bool(ukur.get('topbar')),
        },
        'seksi': susunan,
        'font': {
            'teks': font_teks, 'judul': font_judul,
            'teks_google': google_font(font_teks), 'judul_google': google_font(font_judul) if font_judul != font_teks else google_font(font_teks),
            'judul_tebal': int(font.get('judul_tebal') or 700), 'judul_kapital': bool(font.get('judul_kapital')),
            'serif_judul': bool(re.search(r'serif|georgia|times|playfair|merriweather|lora', font_judul, re.I)
                                and not re.search(r'sans', font_judul, re.I)),
        },
        'tombol': {'radius': max(0, min(int(round(tombol.get('radius') or 6)), 999)),
                   'kapital': bool(tombol.get('kapital'))},
        'kartu': {'radius': max(0, min(int(round(kartu_pertama.get('radius') or 0)), 40)),
                  'bayangan': bool(kartu_pertama.get('bayangan'))},
        'footer': {'gelap': bool(footer.get('gelap')), 'kolom': max(2, min(int(footer.get('kolom') or 3), 4))},
        # Tombol WhatsApp mengambang (hijau WA) ada di hampir semua referensi, bukan warna merek.
        'warna_referensi': [w for w in ukur.get('warna_merek') or [] if w.lower() not in WARNA_BUKAN_MEREK][:3],
        'catatan': catatan,
    }


def ukur_referensi(domain, url, segar=False):
    """Jalankan pengukur (sekali per URL) dan kembalikan rencana, atau (None, alasan)."""
    folder = RENCANA_DIR / domain
    folder.mkdir(parents=True, exist_ok=True)
    berkas = folder / 'desain-referensi.json'
    if not segar:
        try:
            lama = json.loads(berkas.read_text())
            if lama.get('url') == url and lama.get('versi') == VERSI:
                return lama, 'tembolok'
        except (OSError, ValueError):
            pass
    mentah = folder / 'referensi-ukur.json'
    mentah.unlink(missing_ok=True)
    try:
        run = subprocess.run(['node', str(HERE / 'referensi-desain.js'), url, str(mentah), str(folder / 'referensi-potret.png')],
                             capture_output=True, text=True, timeout=240)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f'pengukur_gagal:{type(e).__name__}'
    if not mentah.is_file():
        return None, (run.stdout.strip().splitlines() or ['pengukur_tanpa_hasil'])[-1][:120]
    ukur = json.loads(mentah.read_text())
    return rencana(ukur, {'url': url}), 'diukur'


def periksa(domain, segar=False):
    """Langkah installer: (rencana|None, status). Rencana tersimpan untuk fse-apply."""
    ref = referensi_form(domain)
    if not ref.get('url'):
        return None, 'tidak_ada'
    hasil, sumber = ukur_referensi(domain, ref['url'], segar)
    if not hasil:
        return None, f'gagal:{sumber}'
    hasil['catatan_klien'] = ref.get('catatan', '')
    (RENCANA_DIR / domain / 'desain-referensi.json').write_text(json.dumps(hasil, ensure_ascii=False, indent=1))
    return hasil, sumber


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(args) != 1:
        print('usage: referensi_desain.py <manifest|domain> [--segar]', file=sys.stderr)
        return 2
    domain = args[0]
    if domain.endswith('.txt') and Path(domain).is_file():
        domain = next((l.split('=', 1)[1].strip() for l in Path(domain).read_text(errors='replace').splitlines()
                       if l.startswith('domain=')), '')
    domain = domain.lower()
    if not re.match(r'^[a-z0-9.-]+\.[a-z]{2,}$', domain):
        print('referensi: gagal:domain_tidak_valid')
        return 2
    hasil, status = periksa(domain, '--segar' in sys.argv)
    if not hasil:
        print(f'referensi: {status}')
        return 0 if status == 'tidak_ada' else 1
    h = hasil['header']
    print(f"referensi: header={'gelap' if h['gelap'] else 'terang'} logo={h['logo_posisi']} menu={h['menu_posisi']} "
          f"ajakan={'ya' if h['tombol_ajakan'] else 'tidak'} font={hasil['font']['teks']}/{hasil['font']['judul']} "
          f"tombol_radius={hasil['tombol']['radius']} footer={'gelap' if hasil['footer']['gelap'] else 'terang'}")
    print('referensi: susunan=' + ' > '.join(f"{s['jenis']}({s.get('varian') or s['latar']})" for s in hasil['seksi']))
    if hasil['catatan']:
        print('referensi: catatan=' + ','.join(hasil['catatan']))
    print(f"referensi: ada:{hasil['url']} ({status})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
