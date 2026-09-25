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

Pembacaan diperdalam (permintaan user 2026-09-17): header (baris, logo, menu, ajakan,
isi topbar), footer (isi tiap kolom, baris hak cipta), tiap seksi beranda (label kecil,
sisi foto, ruang), dan HALAMAN DALAM referensi (tentang/layanan/produk/galeri/kontak/
artikel dari menu referensi: banner judul + susunan seksi). Rencana ini juga yang
dipakai audit kemiripan (scripts/fse-audit-kemiripan) sebagai kunci jawaban.

Pemakaian:  referensi_desain.py <manifest|domain> [--segar]
Hasil:      /var/lib/velocity/fse-rencana/<domain>/desain-referensi.json
            (+ referensi-ukur.json & referensi-ukur-<halaman>.json mentah, referensi-potret*.png)
Baris terakhir keluaran: `referensi: ada:<url> ...` | `referensi: tidak_ada` | `referensi: gagal:<alasan>`
Pengukuran dilakukan scripts/referensi-desain.js (Playwright, DOM terender).
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Sama dengan fse-apply: uji di lokasi lain tidak menimpa rencana situs sungguhan.
RENCANA_DIR = Path(os.environ.get('VELOCITY_FSE_RENCANA') or '/var/lib/velocity/fse-rencana')
ON_PROGRESS = Path('/home/On Progress')
UA = 'velocity-installer/1.0 (+https://velocitydeveloper.com)'
# Naikkan bila bentuk rencana/klasifikasi berubah: tembolok versi lama diukur ulang
# (versi 2: warna tombol WhatsApp mengambang dibuang dari warna referensi;
#  versi 4: detail header/topbar/footer/seksi + halaman dalam;
#  versi 5: pohon menu, font menu, detail kartu/tombol/wadah, halaman FAQ & halaman jasa).
VERSI = 13
# Halaman dalam referensi yang diukur, dikenali dari alamat/teks menu -> slug halaman situs klien.
HALAMAN_DALAM = [
    ('tentang', r'about|tentang|profil|profile|company|who-we-are|sejarah', 'tentang-kami'),
    ('layanan', r'service|layanan|jasa|solusi|solution|sourcing|logistic', 'layanan'),
    ('produk', r'product|produk|shop|toko|katalog|catalog|store', 'produk'),
    ('galeri', r'galeri|gallery|portfolio|portofolio|proyek|project', 'galeri'),
    ('faq', r'\bfaq\b|pertanyaan|tanya-jawab|tanya jawab', 'faq'),
    ('kontak', r'contact|kontak|hubungi', 'hubungi-kami'),
    ('artikel', r'blog|berita|news|artikel|article', 'berita'),
]
WARNA_BUKAN_MEREK = {'#25d366', '#128c7e', '#075e54', '#34b7f1', '#dcf8c6'}

# Font sistem: tidak perlu dimuat dari Google Fonts.
FONT_SISTEM = {'arial', 'helvetica', 'helvetica neue', 'georgia', 'times new roman', 'times', 'verdana',
               'tahoma', 'segoe ui', 'system-ui', '-apple-system', 'sans-serif', 'serif', 'roboto'}


# Folder/zip desain kiriman klien (ekspor HTML situs jadi), dicari di folder proyek.
NAMA_DESAIN = re.compile(r'desain|design|mockup|mock-up|template|tampilan|layout', re.I)


def desain_lokal(domain):
    """Desain situs yang DIKIRIM klien (HTML statis berisi index.html) -> URL file://, atau ''.

    centralimpex.com 2026-09-17: form isian tidak menyebut website contoh, tetapi klien
    mengirim folder desain/ (ekspor Next.js 8 halaman). Desain milik klien sendiri lebih
    kuat daripada website contoh, jadi didahulukan. Zip yang belum diekstrak dibuka ke
    fse-rencana/<domain>/desain-klien/ (tanpa jalur keluar folder)."""
    folder = ON_PROGRESS / domain
    if not folder.is_dir():
        return ''
    calon = []
    for idx in folder.rglob('index.html'):
        rel = idx.relative_to(folder).parts
        if len(rel) <= 4 and any(NAMA_DESAIN.search(b) for b in rel[:-1]):
            calon.append(idx)
    if not calon:
        import zipfile
        for z in sorted(folder.rglob('*.zip')):
            if not NAMA_DESAIN.search(z.name):
                continue
            tujuan = RENCANA_DIR / domain / 'desain-klien' / z.stem
            try:
                with zipfile.ZipFile(z) as arsip:
                    nama = [n for n in arsip.namelist() if n.endswith('index.html') and n.count('/') <= 3]
                    if not nama:
                        continue
                    akar = tujuan.resolve()
                    for info in arsip.infolist():
                        target = (tujuan / info.filename).resolve()
                        if not str(target).startswith(str(akar)) or info.file_size > 50_000_000:
                            continue
                        if info.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(arsip.read(info))
                    calon.append(tujuan / min(nama, key=len))
            except (OSError, zipfile.BadZipFile):
                continue
    if not calon:
        return ''
    pilih = min(calon, key=lambda x: (len(x.parts), str(x)))
    return pilih.resolve().as_uri()


def cari_alamat(teks, bukan):
    """URL situs pertama di teks: http(s):// lebih dulu, lalu domain polos.

    Klien sering menulis domain polos ("kontraktorhijau.com") — dulu hanya http(s)://
    yang ditangkap, sehingga jasakontraktorindo.com (2026-09-17) tercatat tanpa
    referensi dan desainnya tidak mengikuti pilihan klien."""
    url = next((u.rstrip('.,)"') for u in re.findall(r'https?://[^\s"<>]+', teks)
                if not re.search(bukan, u, re.I)), '')
    if url:
        return url
    polos = re.findall(r'(?<![@\w./-])((?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*'
                       r'\.(?:com|net|org|id|biz|info|io|co)(?:/[^\s"<>]*)?)(?![\w@-])', teks, re.I)
    return next(('https://' + u.rstrip('.,)"') for u in polos if not re.search(bukan, u, re.I)), '')


def referensi_form(domain):
    """Referensi desain: desain kiriman klien (desain_lokal) lebih dulu, lalu URL
    "website yang ingin dicontoh" + catatan klien dari FORM ISIAN.

    Contoh isian template form (alamatWebContoh.com) dan tautan syarat & ketentuan
    Velocity bukan referensi."""
    sys.path.insert(0, str(HERE))
    lokal = desain_lokal(domain)
    if lokal:
        return {'url': lokal, 'catatan': 'desain dikirim klien di folder proyek', 'sumber': 'desain_klien'}
    try:
        from client_form import read_client_form
        form = read_client_form(ON_PROGRESS / domain)
        teks = form.get('text') or ''
    except Exception:
        return {}
    bukan = r'velocitydeveloper|alamatwebcontoh|example\.|suryagrup\.com|^(https?://)?(www\.)?contoh\.|' + re.escape(domain)
    if form.get('sumber') == 'claude':
        # Form dibaca agen Claude (scripts/baca-form-claude): referensi DESAIN sudah dipisah dari contoh
        # template & dari web sumber isi ("materi ambil dari ..."), jadi tidak ditebak lagi dari teks.
        for r in (form.get('data') or {}).get('referensi_desain') or []:
            url = cari_alamat(str(r.get('url') or ''), bukan)
            if url:
                return {'url': url, 'catatan': str(r.get('catatan') or '')[:400]}
        return {}
    awal = re.search(r'INGIN\s+DICONTOH|YANG\s+ANDA\s+SUKAI\s+DESAINNYA', teks, re.I)
    potong = ''
    if awal:
        akhir = re.search(r'Contoh\s+Jawaban|WARNA\s+TEMA', teks[awal.end():], re.I)
        potong = teks[awal.end():awal.end() + (akhir.start() if akhir else 1500)]
    url = cari_alamat(potong, bukan)
    if not url:
        # Referensi juga sering ditulis di kolom lain, mis. SUSUNAN MENU ATAS:
        # "contoh seperti kontraktorhijau.com" (jasakontraktorindo.com) atau
        # "Samakan Seperti ptjakartapanganagro.com" (jakartaswasembadapangan.com).
        # Di luar kolom referensi hanya domain yang didahului kata ajakan meniru.
        for m in re.finditer(r'(?:seperti|mirip|samakan|contoh(?:nya)?|referensi|acuan|mengikuti)\b[^\n]{0,40}', teks, re.I):
            # "materi/konten/isi samakan X" = isi yang ditiru, bukan desain.
            if re.search(r'(materi|konten|isi|artikel)\W+(\w+\W+)?$', teks[max(0, m.start() - 30):m.start()], re.I):
                continue
            url = cari_alamat(m.group(0), bukan)
            if url:
                potong = teks[max(0, m.start() - 200):m.end() + 200]
                break
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
    ('testimoni', r'testimon|review|ulasan|kata (mereka|klien|pelanggan)|what (our )?(clients?|customers?) say'
                  r'|kepuasan (klien|pelanggan)|cerita (klien|pelanggan)'),
    # Paket harga/pilihan layanan (kontraktorhijau.com "Pilih Paket ..."): dibangun tanpa angka.
    ('paket', r'\bpaket\b|\bharga\b|pricing|\bpackages?\b|price list|pilihan layanan'),
    ('faq', r'\bfaq\b|pertanyaan|tanya jawab|frequently'),
    ('alur', r'\balur\b|langkah|tahap|cara (kerja|pesan|order|pemesanan)|\bproses\b|how it works|\bsteps?\b'),
    ('keunggulan', r'kenapa|mengapa|\bwhy\b|keunggulan|kelebihan|alasan|advantage|benefit'),
    ('artikel', r'artikel|berita|\bblog\b|\bnews\b|latest update|update terbaru|tulisan'),
    ('ajakan', r'inquir|enquir|\brfq\b|request a quote|minta penawaran|get started|mulai sekarang'),
    ('pasar', r'\bmarkets?\b|\bpasar\b|regions?\b|wilayah|negara tujuan|countries|global reach|jangkauan|coverage'),
    ('klien', r'klien kami|\bclients?\b|partner|\bmitra\b|dipercaya|trusted|kepercayaan'),
    ('galeri', r'galeri|gallery|portofolio|portfolio|proyek|project|dokumentasi|bukti kualitas|hasil (kerja|pekerjaan)'),
    ('produk', r'produk|product|katalog|catalog|koleksi|collection|\bshop\b|\btoko\b|kategori|categor'),
    ('layanan', r'layanan|services?\b|\bjasa\b|solusi|solutions?\b|what we do|capabilit|what we offer'),
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


# Nama kelas seksi dari pembuat situs (centralimpex.com: intro-section, markets-section,
# inquiry-cta) — petunjuk yang lebih kuat daripada kata di judul.
KELAS_SEKSI = [
    ('ajakan', r'\bcta\b|-cta\b|cta-|call-to-action|inquiry'),
    ('testimoni', r'testimon|review'),
    ('faq', r'\bfaq'),
    ('pasar', r'market|region'),
    ('tentang', r'\bintro|about|tentang'),
    ('kontak', r'contact|kontak'),
    ('layanan', r'service|layanan'),
    ('produk', r'product|produk'),
]


def jenis_seksi(s, indeks):
    k = s.get('kartu') or {}
    ju = s.get('judul_utama') or {}
    teks_judul = ' '.join([ju.get('teks', '')] + list(s.get('judul') or [])).lower()
    label = ((s.get('label') or {}).get('teks') or '').lower()
    if indeks == 0 and s['tinggi'] >= 350 and (s['foto_latar'] or s['slider'] or s['berdampingan']
                                               or ju.get('ukuran', 0) >= 34 or ju.get('tag') == 'h1'):
        return 'hero'
    if s['angka_besar'] >= 3:
        return 'angka'
    if s['form'] or s['peta']:
        return 'kontak'
    # Deret foto berketerangan pendek = galeri/portofolio, walau judulnya menyebut "jasa".
    if k.get('foto', 0) >= 3 and k.get('keterangan', 0) >= 3 and s['kata'] <= 12 * max(k.get('n', 1), 1) + 60:
        return 'galeri'
    # Pita gelap berisi foto | teks + tombol di akhir halaman = ajakan terbelah ("Survei Dulu ...").
    if s['berdampingan'] and s['foto'] >= 1 and s['tombol'] >= 1 and s['luminansi'] < 110 and not s['foto_latar']:
        return 'ajakan'
    kelas = ' '.join(k for k in re.split(r'\s+', (s.get('kelas') or '').lower())
                     if not k.startswith(('wp-', 'has-', 'is-', 'fl-', 'elementor-')))
    for jenis, pola in KELAS_SEKSI:
        if re.search(pola, kelas):
            if jenis == 'ajakan' and (s['tinggi'] > 520 or k.get('n', 0) >= 3):
                continue
            return jenis
    judul_utama = (ju.get('teks') or '').lower()
    for sumber in (judul_utama, label, teks_judul):
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
            if jenis == 'ajakan' and (s['tinggi'] > 520 or k.get('n', 0) >= 3):
                continue
            if jenis == 'paket' and k.get('n', 0) < 2:
                continue
            return jenis
    if s['akordeon']:
        return 'faq'
    if k.get('n', 0) >= 6 and s['kata'] <= 6:
        return 'klien'  # deret logo tanpa teks
    if s['foto'] >= 6 and s['kata'] < 60:
        return 'galeri'
    if s['tinggi'] <= 420 and s['tombol'] >= 1 and s['kata'] <= 70 and k.get('n', 0) < 3:
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


def gabung_kepala(seksi):
    """Satukan baris judul page builder dengan baris isi di bawahnya.

    Divi/Elementor/Beaver menaruh judul seksi dan deret kartunya di baris terpisah yang
    sama-sama selebar layar, sehingga terukur sebagai dua seksi: judul "Kontraktor Bangunan
    Berpengalaman" terbaca sebagai ajakan dan kartunya sebagai seksi tanpa judul
    (kontraktorhijau.com 2026-09-17). Baris kepala = ada judul, tanpa deret kartu/foto/form,
    teks pendek; baris berikutnya berlatar sama, rapat (<= 70px), dan judulnya tidak lebih besar."""
    hasil = []
    for s in seksi:
        if hasil:
            a = hasil[-1]
            ka = a.get('kartu') or {}
            ja, js_ = a.get('judul_utama') or {}, s.get('judul_utama') or {}
            kepala = (ja and (ka.get('n', 0) < 2 or a['kata'] <= 30) and not a['foto'] and not a['form'] and a['kata'] <= 70
                      and a['tinggi'] <= 320 and not a.get('_gabungan'))
            rapat = 0 <= s['y'] - (a['y'] + a['tinggi']) <= 70 and s.get('latar') == a.get('latar')
            if kepala and rapat and (not js_ or js_.get('ukuran', 0) < ja.get('ukuran', 0) * 0.8):
                g = dict(s)
                g.update({
                    'y': a['y'], 'tinggi': s['y'] + s['tinggi'] - a['y'], 'judul_utama': ja,
                    'judul': list(a.get('judul') or []) + list(s.get('judul') or []),
                    'label': a.get('label') or s.get('label'), 'kata': a['kata'] + s['kata'],
                    'tombol': a['tombol'] + s['tombol'], 'kepala_tombol': a['tombol'],
                    'ruang_atas': a.get('ruang_atas', 0), 'kelas': f"{a.get('kelas', '')} {s.get('kelas', '')}",
                    '_gabungan': True,
                })
                hasil[-1] = g
                continue
        hasil.append(s)
    return hasil


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
    return gabung_kepala(hasil)


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
    lanjut, cat = susun_seksi(seksi, 1 if catatan else 0, susunan[-1]['jenis'] if susunan else '')
    susunan += lanjut
    catatan += cat
    return rencana_global(ukur, ref, h, seksi, susunan, catatan)


def ruang(s):
    """Ruang atas/bawah isi seksi -> rapat | sedang | lega."""
    r = ((s.get('ruang_atas') or 0) + (s.get('ruang_bawah') or 0)) / 2
    return 'rapat' if r < 40 else 'lega' if r > 100 else 'sedang'


def butir_seksi(s, jenis):
    k = s.get('kartu') or {}
    label = s.get('label') or {}
    butir = {
        'jenis': jenis, 'latar': latar_seksi(s),
        # Dua blok berdampingan (foto | teks) bukan deret kartu.
        'kolom': max(2, min(int(k.get('kolom') or 3), 6)) if k.get('n', 0) >= (3 if s['berdampingan'] else 2) else 0,
        'kartu_foto': bool(k.get('foto', 0) >= 2), 'kartu_ikon': bool(k.get('ikon', 0) >= 2),
        'rata': 'tengah' if (s.get('judul_utama') or {}).get('rata') == 'center' else 'kiri',
        'berdampingan': bool(s['berdampingan']), 'slider': bool(s['slider']),
        'kartu_radius': max(0, min(int(round(k.get('radius') or 0)), 40)), 'kartu_bayangan': bool(k.get('bayangan')),
        'kartu_bingkai': bool(k.get('berbingkai')),
        'judul_referensi': (s.get('judul_utama') or {}).get('teks', '')[:60],
        # Detail 2026-09-17: label kecil di atas judul, sisi foto, kerapatan ruang.
        'label': bool(label), 'label_kapital': bool(label.get('kapital')),
        'foto_posisi': s.get('foto_posisi') or '',
        'ruang': ruang(s),
        'tinggi': int(s.get('tinggi') or 0),
        'kontras_rendah': list(s.get('kontras_rendah') or [])[:5],
        # Latar seksi berupa video (bukan foto diam): hero situs klien memakai video
        # latar juga, seperti referensi (permintaan user 2026-09-18).
        'video_latar': bool(s.get('video_latar')),
    }
    if jenis == 'hero':
        butir['varian'] = hero_varian(s)
    # Rencana VERSI 5: detail komponen yang dipakai pustaka komponen fse-apply.
    butir.update({
        'jumlah': int(k.get('n') or 0),
        'akordeon': bool(s.get('akordeon')),
        'form': bool(s.get('form')),
        'bar_bawah': bool(s.get('bar_bawah')),
        'kotak': bool(s.get('kotak_latar')),
        'kartu_tombol': bool(k.get('n') and (k.get('tombol') or 0) >= k.get('n', 0) - 1 and k.get('n', 0) >= 2),
        'kartu_keterangan': bool((k.get('keterangan') or 0) >= 2),
        'sorot': int(k.get('sorot', -1) if k.get('sorot') is not None else -1),
        'kepala_tombol': int(s.get('kepala_tombol') or 0),
    })
    return butir


def susun_seksi(seksi, awal=0, sebelumnya='', jenis_dari=None):
    """Seksi terukur -> [butir rencana], [catatan]. jenis_dari(s, i) boleh menggantikan
    klasifikasi (audit membaca kelas vf-ref-<jenis> situs sendiri)."""
    susunan, catatan = [], []
    for i, s in enumerate(seksi):
        jenis = (jenis_dari(s, i + awal) if jenis_dari else None) or jenis_seksi(s, i + awal)
        if jenis == 'lain':
            catatan.append(f"seksi_tak_dikenal:{(s.get('judul_utama') or {}).get('teks', '')[:30]}")
            continue
        if (susunan[-1]['jenis'] if susunan else sebelumnya) == jenis:
            continue  # deret logo/galeri yang terpecah dua baris
        susunan.append(butir_seksi(s, jenis))
    return susunan, catatan


def kelompok_latar(latar):
    """Latar dibandingkan per kelompok: warna klien menggantikan warna referensi."""
    return {'terang': 'terang', 'abu': 'terang', 'gelap': 'warna', 'aksen': 'warna'}.get(latar, latar or '')


def banner_halaman(ukur):
    j = ukur.get('judul_halaman') or {}
    if not j.get('ada'):
        return {'ada': False}
    latar = 'foto' if j.get('foto_latar') else latar_seksi({'latar': j.get('latar'), 'luminansi': j.get('luminansi', 255)})
    return {'ada': True, 'latar': latar, 'rata': j.get('rata') or 'kiri', 'breadcrumb': bool(j.get('breadcrumb')),
            'tinggi': 'tinggi' if (j.get('tinggi') or 0) >= 260 else 'sedang' if (j.get('tinggi') or 0) >= 150 else 'pendek'}


def rencana_halaman(ukur, jenis_dari=None):
    """Satu halaman dalam: banner judul + susunan seksi di bawahnya."""
    seksi = bersihkan_seksi(ukur.get('seksi') or [])
    banner = banner_halaman(ukur)
    if banner['ada'] and seksi:
        seksi = seksi[1:]
    susunan, catatan = susun_seksi(seksi, 1, jenis_dari=jenis_dari)
    isi = set()
    for s in ukur.get('seksi') or []:
        if s.get('form'):
            isi.add('form')
        if s.get('peta'):
            isi.add('peta')
    return {'url': ukur.get('url', ''), 'banner': banner, 'seksi': susunan, 'catatan': catatan, 'isi': sorted(isi),
            'form_peta_berdampingan': any(s.get('berdampingan') and (s.get('form') or s.get('peta'))
                                          for s in ukur.get('seksi') or [])}


def rencana_header(ukur):
    h = ukur.get('header') or {}
    t = ukur.get('topbar_info') or {}
    aj = h.get('ajakan') or {}
    return {
        'gelap': bool(h.get('gelap')), 'logo_posisi': h.get('logo_posisi') or 'kiri',
        'menu_posisi': h.get('menu_posisi') or 'kanan', 'tombol_ajakan': bool(h.get('tombol_ajakan')),
        'lengket': bool(h.get('lengket')), 'menu_kapital': bool(h.get('huruf_menu_kapital')),
        'topbar': bool(ukur.get('topbar')),
        'topbar_gelap': bool(t.get('gelap')),
        'topbar_isi': sorted(set(t.get('isi') or [])),
        'dua_baris': (h.get('baris') or 1) >= 2,
        'tinggi': int(h.get('tinggi') or 0),
        'logo_tinggi': int(h.get('logo_tinggi') or 0),
        'menu_ukuran': round(float(h.get('menu_ukuran') or 0), 1),
        'menu_tebal': int(h.get('menu_tebal') or 0),
        'cari': bool(h.get('cari')),
        'dropdown': bool(h.get('dropdown')),
        'garis_bawah': bool(h.get('garis_bawah')),
        'ajakan_radius': int(round(aj.get('radius') or 0)) if aj else None,
        'isi': sorted(set(h.get('isi') or [])),
        'menu_berwarna': bool(h.get('menu_berwarna')),
        'keranjang': bool(h.get('keranjang')),
        'melayang': h.get('melayang') or None,
        'transparan': bool(h.get('transparan')),
    }


def rencana_footer(ukur):
    f = ukur.get('footer') or {}
    b = f.get('bawah') or {}
    kolom = [{'judul': c.get('judul', ''), 'isi': [x for x in c.get('isi') or [] if x != 'lain'], 'lebar': c.get('lebar', 0)}
             for c in f.get('kolom_rinci') or []]
    return {
        'gelap': bool(f.get('gelap')), 'kolom': max(2, min(int(f.get('kolom') or 3), 5)),
        'kolom_isi': [c['isi'] for c in kolom],
        'kolom_judul': [c['judul'] for c in kolom],
        'logo': bool(f.get('logo')), 'sosmed': bool(f.get('sosmed')),
        'bawah': bool(b), 'bawah_rata': b.get('rata', ''), 'bawah_beda_latar': bool(b.get('beda_latar')),
        'pita': bool(b.get('pita')),
        'judul_kapital': bool(f.get('judul_kapital')),
    }


def jenis_menu(label, url):
    """Label/URL menu referensi -> jenis halaman (tentang/layanan/.../faq) atau ''."""
    jalur = urllib.parse.urlparse(url or '').path
    if (label or '').strip().lower() in ('home', 'beranda', 'utama'):
        return 'beranda'
    jenis = next((nama for nama, pola, _ in HALAMAN_DALAM if re.search(pola, f'{label} {jalur}'.lower())), '')
    if not jenis and (jalur in ('', '/') or re.search(r'/index\.html?$', jalur)):
        return 'beranda'
    return jenis


def jenis_wadah(ukur, persen):
    """Wadah isi: {'wadah': persen} (cair), {'wadah_px': n} (tetap), + 'wadah_maks' bila cair berbatas.

    Diputuskan dari lebar isi di layar 1366 & 1920 (ukur['lebar_isi_dua']); tanpa data itu
    persen lama dipakai hanya bila >= 0.9 (wadah cair lebar seperti 95%) — persen kecil lebih
    mungkin wadah px tetap yang kebetulan terbaca di satu lebar layar."""
    dua = ukur.get('lebar_isi_dua') or {}
    w1, w2 = int(dua.get('1366') or 0), int(dua.get('1920') or 0)
    if w1 >= 400 and w2 >= 400:
        if abs(w2 - w1) <= 60:
            return {'wadah': 0, 'wadah_px': max(w1, w2)}
        if abs(w2 / 1920 - w1 / 1366) <= 0.04:
            return {'wadah': round(w1 / 1366, 3), 'wadah_px': 0}
        # Membesar tetapi tidak sebanding: persen yang dibatasi lebar maksimum.
        return {'wadah': round(w1 / 1366, 3), 'wadah_px': 0, 'wadah_maks': w2}
    return {'wadah': persen if persen >= 0.9 else 0, 'wadah_px': 0}


def wadah_tetap(seksi, layar):
    """True bila seksi-seksi isi memang kotak berwadah tetap (tepinya menjorok ke dalam),
    bukan pita selebar layar. Dipakai tema untuk membuat seksi jadi kartu berwadah."""
    kotak = [s for s in seksi if int(s.get('lebar') or 0) >= 400 and int(s.get('tinggi') or 0) >= 150]
    if len(kotak) < 2:
        return False
    menjorok = [s for s in kotak if int(s['lebar']) <= layar * 0.985 and int(s.get('kiri') or 0) >= 8]
    return len(menjorok) >= max(2, len(kotak) // 2)


def lebar_wadah(seksi, layar):
    """Lebar isi khas (persentil 75 lebar isi seksi) dibanding lebar layar, 0..1."""
    nilai = sorted(min(x.get('lebar_isi') or 0, layar) for x in seksi if (x.get('lebar_isi') or 0) > layar * 0.3)
    if not nilai:
        return 0
    return round(nilai[min(len(nilai) - 1, int(len(nilai) * 0.75))] / max(layar, 1), 3)


def rencana_menu(ukur):
    """Pohon menu referensi ringkas: label, jenis halaman, jumlah & label anak.

    Dipakai fse-apply untuk menyusun menu & halaman situs klien mengikuti referensi
    (label diganti isi klien; anak layanan = layanan klien, anak blog = kategori)."""
    hasil = []
    for m in ukur.get('menu_pohon') or []:
        hasil.append({'label': m.get('label', '')[:40], 'jenis': jenis_menu(m.get('label', ''), m.get('url', '')),
                      'anak': [a.get('label', '')[:40] for a in m.get('anak') or []][:16]})
    return hasil


def rencana_global(ukur, ref, h, seksi, susunan, catatan):
    # Deret slider (kategori, logo) jarang mewakili kartu situs: kartu biasa didahulukan.
    berkartu = [s for s in seksi if (s.get('kartu') or {}).get('n', 0) >= 2]
    # Kartu bergaya (berbingkai/bersudut/berbayang) mewakili desain lebih baik daripada
    # pembungkus kolom polos yang kebetulan berjumlah banyak.
    bergaya = [s['kartu'] for s in berkartu if not s['slider'] and (s['kartu'].get('berbingkai') or s['kartu'].get('radius')
                                                                  or s['kartu'].get('border') or s['kartu'].get('bayangan'))]
    kartu_pertama = (bergaya[0] if bergaya else
                     next((s['kartu'] for s in berkartu if not s['slider']), berkartu[0]['kartu'] if berkartu else {}))
    font = ukur.get('font') or {}
    tombol = ukur.get('tombol') or {}
    font_teks, font_judul = font.get('teks', ''), font.get('judul', '') or font.get('teks', '')
    return {
        'versi': VERSI,
        'url': ref.get('url', ''), 'catatan_klien': ref.get('catatan', ''),
        'header': rencana_header(ukur),
        'seksi': susunan,
        'font': {
            'teks': font_teks, 'judul': font_judul,
            'teks_google': google_font(font_teks), 'judul_google': google_font(font_judul) if font_judul != font_teks else google_font(font_teks),
            'menu': font.get('menu', ''), 'menu_google': google_font(font.get('menu', '')) if font.get('menu') not in (font_teks, font_judul) else False,
            'judul_tebal': int(font.get('judul_tebal') or 700), 'judul_kapital': bool(font.get('judul_kapital')),
            'serif_judul': bool(re.search(r'serif|georgia|times|playfair|merriweather|lora', font_judul, re.I)
                                and not re.search(r'sans', font_judul, re.I)),
        },
        'tombol': {'radius': max(0, min(int(round(tombol.get('radius') or 6)), 999)),
                   'kapital': bool(tombol.get('kapital')),
                   'padding': tombol.get('padding') or [], 'tebal': int(tombol.get('tebal') or 0),
                   'ukuran': round(float(tombol.get('ukuran') or 0), 1)},
        'kartu': {'radius': max(0, min(int(round(kartu_pertama.get('radius') or 0)), 40)),
                  'bayangan': bool(kartu_pertama.get('bayangan')),
                  'border': round(float(kartu_pertama.get('border') or 0), 1),
                  'border_warna': kartu_pertama.get('border_warna', ''),
                  'padding': int(kartu_pertama.get('padding') or 0),
                  'jarak': int(kartu_pertama.get('jarak') or 0)},
        # Lebar isi terlebar dibanding layar (kontraktorhijau.com 95%, situs Bootstrap ~1140px).
        **jenis_wadah(ukur, lebar_wadah(seksi, ukur.get('lebar_layar') or 1366)),
        # Seksi berwadah TETAP: kotaknya sendiri lebih sempit dari layar (bukan selebar
        # layar berisi wadah). Beaver Builder `.fl-row-fixed-width` — northseaaconsulting.com
        # hero 1320px di tengah layar 1366 (2026-09-18).
        'wadah_tetap': wadah_tetap(seksi, ukur.get('lebar_layar') or 1366),
        'judul_ukuran': {'h1': round(float(font.get('ukuran_h1') or 0), 1), 'h2': round(float(font.get('ukuran_h2') or 0), 1)},
        'menu': rencana_menu(ukur),
        'footer': rencana_footer(ukur),
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
    hasil = rencana(ukur, {'url': url})
    hasil['halaman'] = ukur_halaman_dalam(folder, ukur)
    return hasil, 'diukur'


def pilih_halaman_dalam(tautan, beranda, pohon=None):
    """Tautan menu referensi -> {nama: url}, satu per jenis halaman, beranda tidak ikut.

    Submenu (pohon menu) ikut dibaca: anak pertama menu layanan = contoh halaman jasa
    (`layanan_detail`), yang tautannya tersembunyi sampai di-hover."""
    akar = urllib.parse.urlparse(beranda)
    pilih = {}
    tautan = list(tautan or [])
    for m in pohon or []:
        tautan.append({'teks': m.get('label', ''), 'url': m.get('url', '')})
        if 'layanan_detail' not in pilih and m.get('anak') and re.search(HALAMAN_DALAM[1][1], f"{m.get('label', '')} {m.get('url', '')}", re.I):
            anak = m['anak'][0].get('url', '')
            if anak.startswith(('http', 'file')):
                pilih['layanan_detail'] = urllib.parse.urlunparse(urllib.parse.urlparse(anak)._replace(query='', fragment=''))
    for t in tautan or []:
        u = urllib.parse.urlparse(t.get('url', ''))
        # Desain lokal (file://): hanya nama berkas yang berarti, bukan folder proyek.
        jalur = (urllib.parse.unquote(u.path).rsplit('/', 1)[-1] if u.scheme == 'file'
                 else u.path.strip('/')).lower()
        if not jalur or (u.path.rstrip('/') == akar.path.rstrip('/')):
            continue
        teks = (t.get('teks') or '').lower()
        for nama, pola, _ in HALAMAN_DALAM:
            if nama not in pilih and (re.search(pola, jalur) or re.search(pola, teks)):
                pilih[nama] = urllib.parse.urlunparse(u._replace(query='', fragment=''))
                break
    return pilih


def ukur_halaman_dalam(folder, ukur_beranda):
    """Ukur halaman dalam referensi (satu browser) -> {nama: rencana_halaman}. Gagal = {}."""
    pilih = pilih_halaman_dalam(ukur_beranda.get('tautan_menu'), ukur_beranda.get('url', ''), ukur_beranda.get('menu_pohon'))
    if not pilih:
        return {}
    argumen = []
    for nama, url in pilih.items():
        (folder / f'referensi-ukur-{nama}.json').unlink(missing_ok=True)
        argumen += [url, str(folder / f'referensi-ukur-{nama}.json'), str(folder / f'referensi-potret-{nama}.png')]
    try:
        subprocess.run(['node', str(HERE / 'referensi-desain.js')] + argumen,
                       capture_output=True, text=True, timeout=180 + 90 * len(pilih))
    except (OSError, subprocess.SubprocessError):
        pass
    hasil = {}
    for nama in pilih:
        try:
            hasil[nama] = rencana_halaman(json.loads((folder / f'referensi-ukur-{nama}.json').read_text()))
        except (OSError, ValueError):
            continue
    return hasil


def periksa(domain, segar=False):
    """Langkah installer: (rencana|None, status). Rencana tersimpan untuk fse-apply."""
    ref = referensi_form(domain)
    if not ref.get('url'):
        return None, 'tidak_ada'
    hasil, sumber = ukur_referensi(domain, ref['url'], segar)
    if not hasil:
        return None, f'gagal:{sumber}'
    hasil['catatan_klien'] = ref.get('catatan', '')
    hasil['sumber_referensi'] = ref.get('sumber', 'form')
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
    f = hasil['footer']
    print(f"referensi: topbar={'ya' if h['topbar'] else 'tidak'}{'(' + ','.join(h['topbar_isi']) + ')' if h.get('topbar_isi') else ''} "
          f"dua_baris={'ya' if h.get('dua_baris') else 'tidak'} cari={'ya' if h.get('cari') else 'tidak'} "
          f"footer_kolom={f['kolom']} [{' | '.join('+'.join(k) or '-' for k in f.get('kolom_isi') or [])}] "
          f"hak_cipta={f.get('bawah_rata') or 'tidak_ada'}")
    for nama, hal in (hasil.get('halaman') or {}).items():
        b = hal['banner']
        print(f"referensi: halaman {nama}: banner={(b['latar'] + '/' + b['rata']) if b['ada'] else 'tidak_ada'}"
              f" susunan={' > '.join(s['jenis'] for s in hal['seksi']) or '-'}")
    if hasil['catatan']:
        print('referensi: catatan=' + ','.join(hasil['catatan']))
    print(f"referensi: ada:{hasil['url']} ({status})")
    return 0


if __name__ == '__main__':
    sys.exit(main())
