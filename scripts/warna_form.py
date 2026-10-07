"""Nama warna di isian "WARNA TEMA WEB" form klien -> kode hex.

Klien menulis nama ("hitam, emas, biru"), bukan kode. Dipakai site-finish
(theme mod primary_color + CSS) dan paket-g-konten (warna isi contoh), supaya
kedua langkah membaca warna yang sama (suarapurwakarta.com 2026-10-07: form
"hitam, emas, biru" tetapi tema tetap biru bawaan #1e73be).
"""
import re

# Kalimat contoh bawaan template form ("Misal: warna dasar tema web yang saya inginkan biru dan
# hijau.") yang dibiarkan klien -> bukan pilihan warna.
TEKS_TEMPLATE_WARNA = re.compile(r'^\s*(misal|contoh|mis\.)|yang saya inginkan|dibedakan dari', re.I)

# Frasa panjang didahulukan supaya "biru dongker" tidak terbaca "biru".
COLORS = [
    ('biru dongker', '#1f2a44'), ('dongker', '#1f2a44'), ('navy', '#1f2a44'),
    ('biru muda', '#4fa3e0'), ('biru langit', '#4fa3e0'), ('tosca', '#1abc9c'),
    ('merah marun', '#800000'), ('maroon', '#800000'), ('marun', '#800000'),
    ('merah muda', '#e91e63'), ('pink', '#d81b60'), ('magenta', '#c2185b'),
    ('biru', '#1e5aa8'), ('hijau', '#2e7d32'), ('merah', '#c62828'),
    ('orange', '#ef6c00'), ('oranye', '#ef6c00'), ('jingga', '#ef6c00'),
    ('kuning', '#f9a825'), ('gold', '#c9a227'), ('emas', '#c9a227'),
    ('ungu', '#6a1b9a'), ('coklat', '#6d4c41'), ('cokelat', '#6d4c41'),
    ('hitam', '#111111'), ('abu', '#607d8b'),
]


def pick_colors(text, batas=2):
    """Kode hex warna yang disebut di teks, urut kemunculan, tanpa duplikat."""
    low = str(text or '').lower()
    found = []
    for word, hexv in COLORS:
        for m in re.finditer(r'(?<![a-z])' + re.escape(word) + r'(?![a-z])', low):
            found.append((m.start(), -(m.end() - m.start()), m.end(), hexv))
    found.sort()
    picked, last_end = [], -1
    for start, _, end, hexv in found:
        if start < last_end:
            continue
        last_end = end
        if hexv not in picked:
            picked.append(hexv)
    return picked[:batas]


def kontras_putih(hexv):
    def kanal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hexv[i:i + 2], 16) for i in (1, 3, 5))
    lum = 0.2126 * kanal(r) + 0.7152 * kanal(g) + 0.0722 * kanal(b)
    return 1.05 / (lum + 0.05)


def warna_utama(warna):
    """Warna utama tema dari daftar pilihan klien: yang pertama disebut, kecuali
    terlalu terang untuk tulisan putih (menu & tombol Velocity bertulisan putih) —
    "kuning hitam" -> hitam, kuning tetap jadi aksen."""
    for w in warna:
        if kontras_putih(w) >= 3:
            return w
    return warna[0] if warna else ''


def warna_klien(teks, batas=2):
    """pick_colors atas isian form, kosong bila isinya masih kalimat contoh template."""
    teks = re.sub(r'[.\s]+$', '', str(teks or '')).strip()
    return [] if not teks or TEKS_TEMPLATE_WARNA.search(teks) else pick_colors(teks, batas)


def _gelapkan(hexv, target=4.5):
    """Turunkan kecerahan (HLS) sampai tulisan putih di atasnya terbaca (kontras >= target)."""
    import colorsys
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    while l > 0.05:
        r2, g2, b2 = colorsys.hls_to_rgb(h, l, s)
        w = '#%02x%02x%02x' % (round(r2 * 255), round(g2 * 255), round(b2 * 255))
        if kontras_putih(w) >= target:
            return w
        l -= 0.02
    return '#111111'


def warna_logo(path):
    """Warna utama tema dari berkas logo klien (dipakai bila form tidak menyebut warna;
    user 2026-10-07, solomerchandiseapparel.com: logo hitam-emas, situs tetap biru bawaan).

    Latar (transparan / warna sudut gambar / hampir putih) dibuang, sisa piksel dikuantisasi.
    Dipilih warna berwarna (saturasi cukup) yang paling banyak, minimal 6% bagian logo; logo
    tanpa warna (hitam/abu saja) memakai warna gelap terbanyaknya. Hasil digelapkan seperlunya
    supaya menu & tombol bertulisan putih tetap terbaca. '' bila gagal."""
    try:
        import colorsys
        from PIL import Image
        im = Image.open(path)
        im = im.convert('RGBA')
        im.thumbnail((200, 200))
        w, h = im.size
        px = list(im.getdata())
        sudut = [im.getpixel(p) for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
        latar = [c for c in sudut if c[3] > 128]

        def bukan_latar(c):
            if c[3] < 128 or min(c[:3]) > 235:
                return False
            return all(sum(abs(c[i] - s[i]) for i in range(3)) > 40 for s in latar)

        isi = [c[:3] for c in px if bukan_latar(c)]
        if len(isi) < 50:
            return ''
        q = Image.new('RGB', (len(isi), 1))
        q.putdata(isi)
        q = q.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette()
        hitung = sorted(q.getcolors(), reverse=True)
        total = sum(n for n, _ in hitung)
        warna, gelap = [], []
        for n, i in hitung:
            r, g, b = pal[i * 3:i * 3 + 3]
            _, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            hexv = '#%02x%02x%02x' % (r, g, b)
            if s >= 0.3 and v >= 0.25 and n / total >= 0.06:
                warna.append(hexv)
            elif v < 0.5:
                gelap.append(hexv)
        # Logo hitam bergaris tipis: kelompok terbanyak abu-abu tepi antialias -> ambil yang tergelap.
        gelap.sort(key=kontras_putih, reverse=True)
        pilih = (warna or gelap or [''])[0]
        return _gelapkan(pilih) if pilih else ''
    except Exception:
        return ''
