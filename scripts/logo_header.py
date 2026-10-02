"""Logo header tema klasik: terbaca, tidak melewati latarnya, tidak terlalu tinggi.

Permintaan user 2026-10-02 (bintanglasjayakontruksi.com, velocity-perusahaan1): logo asli bertulisan
navy dipasang di latar navy (tulisan hilang), dan logo 700x200 tampil 359x102 sehingga menjorok
keluar dari area biru dan memanjangkan header. Aturannya:
  - logo di desktop tidak melebihi warna latarnya;
  - logo yang senada dengan latar disesuaikan (pelat kontras di belakang logo; warna logo tidak
    diubah, lihat feedback logo putih titikfokusnews);
  - logo yang besar/tinggi dikecilkan supaya latar logo tidak bertambah ke bawah.

scripts/logo-header-cek memotret area logo (dengan logo, berlatar magenta, tanpa logo) di
HP/tablet/desktop; modul ini menilai hasilnya dan menyusun CSS perbaikan dalam penanda
/* velocity-logo-header */ di Additional CSS.
"""
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PENANDA_AWAL, PENANDA_AKHIR = '/* velocity-logo-header */', '/* /velocity-logo-header */'
DESKTOP, TABLET, HP = ('1100', '1366', '1920'), '900', '390'
MEDIA = {'hp': '(max-width:768px)', 'tablet': '(min-width:769px) and (max-width:1099px)', 'desktop': '(min-width:1100px)'}
TINGGI_MAKS = {'hp': 64, 'tablet': 80, 'desktop': 80}
LEBAR_MAKS = {'hp': 240, 'tablet': 260, 'desktop': 280}
# Porsi piksel logo yang nyaris tak terlihat (rasio kontras < 1,25 terhadap latar di belakangnya).
# Kalibrasi bintanglasjayakontruksi.com: tulisan navy di latar navy 0,48; dengan pelat putih 0,19.
BATAS_TAK_TERLIHAT = 0.3

# Tema yang area logonya berupa bidang warna berukuran vw (bukan mengikuti container): bidang
# itu ditambatkan ke container supaya selalu menutupi kolom logo di semua lebar layar.
CSS_TEMA = {
    'velocity-perusahaan1': (
        '@media (min-width:1100px){'
        '#wrapper-navbar::before{width:calc(max(0px,(100% - 1140px)/2) + 290px)!important}'
        '#wrapper-navbar::after{left:calc(max(0px,(100% - 1140px)/2) + 289px)!important;'
        'border-top-width:130px!important;border-right-width:90px!important}}'
        '.header-container .col-md-4 img{width:auto;height:auto;max-width:250px;max-height:80px;object-fit:contain}'
        '@media (max-width:768px){.header-container .col-md-4 img{max-width:220px;max-height:64px}}'
    ),
}


def rentang(lebar):
    return 'hp' if lebar == HP else 'tablet' if lebar == TABLET else 'desktop'


def _luminans(c):
    def k(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * k(c[0]) + 0.7152 * k(c[1]) + 0.0722 * k(c[2])


def _rasio(l1, l2):
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)


def _jarak(p, q):
    return ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2) ** 0.5


def _dominan(piksel):
    k = Counter((r // 24, g // 24, b // 24) for r, g, b in piksel).most_common(1)[0][0]
    anggota = [p for p in piksel if (p[0] // 24, p[1] // 24, p[2] // 24) == k]
    return tuple(sum(c[i] for c in anggota) // len(anggota) for i in range(3))


def analisis(folder, lebar, info):
    """Nilai satu lebar layar dari potret a (logo), b (tanpa logo), c (logo berlatar magenta)."""
    A = Image.open(f'{folder}/logo-{lebar}-a.png').convert('RGB')
    B = Image.open(f'{folder}/logo-{lebar}-b.png').convert('RGB')
    C = Image.open(f'{folder}/logo-{lebar}-c.png').convert('RGB')
    sk = A.width / info['clip'][2]  # devicePixelRatio
    x0 = round((info['kotak'][0] - info['clip'][0]) * sk)
    y0 = round((info['kotak'][1] - info['clip'][1]) * sk)
    x1 = min(A.width, x0 + round(info['kotak'][2] * sk))
    y1 = min(A.height, y0 + round(info['kotak'][3] * sk))
    pa, pb, pc = A.load(), B.load(), C.load()
    latar = [pb[x, y] for x in range(x0, x1) for y in range(y0, y1)]
    utama = _dominan(latar)
    cocok = sum(_jarak(p, utama) < 40 for p in latar) / len(latar)
    muat = x1 - x0  # sampai kolom mana latar logo masih sewarna
    for x in range(x0, x1):
        kol = [pb[x, y] for y in range(y0, y1)]
        if sum(_jarak(p, utama) < 40 for p in kol) / len(kol) < 0.7:
            muat = x - x0
            break
    opak, bening = [], []
    for x in range(x0, x1):
        for y in range(y0, y1):
            (opak if _jarak(pc[x, y], (255, 0, 255)) > 60 else bening).append(pa[x, y])
    # Latar yang benar-benar terlihat di belakang logo (termasuk pelat/padding logo).
    belakang = _dominan(bening) if len(bening) > 0.05 * len(latar) else utama
    lb = _luminans(belakang)
    tak_terlihat = (sum(_rasio(_luminans(p), lb) < 1.25 for p in opak) / len(opak)) if opak else 1
    return {'tinggi': info['kotak'][3], 'lebar': info['kotak'][2], 'melebihi': cocok < 0.9, 'muat': round(muat / sk),
            'tak_terlihat': round(tak_terlihat, 2), 'latar': '#%02x%02x%02x' % belakang,
            'latar_gelap': _luminans(utama) < 0.35}


def ukur(url, folder, nama_logo='', cookie=None):
    """{lebar: hasil analisis} dan pemilih CSS logo; ({}, '') bila logo tak bisa dipotret."""
    env = dict(__import__('os').environ)
    if cookie:
        env['VELOCITY_UKUR_COOKIE'] = json.dumps(cookie)
    Path(folder).mkdir(parents=True, exist_ok=True)
    run = subprocess.run(['node', str(HERE / 'logo-header-cek'), url, str(folder), nama_logo],
                         capture_output=True, text=True, timeout=400, env=env)
    m = re.search(r'^logo:(\{.*\})$', run.stdout, re.M)
    if not m:
        return {}, ''
    mentah = json.loads(m.group(1))
    hasil, pemilih = {}, ''
    for lebar, info in mentah.items():
        if 'kotak' not in info:
            continue
        try:
            hasil[lebar] = analisis(folder, lebar, info)
        except (OSError, ZeroDivisionError, IndexError):
            continue
        pemilih = pemilih or info['pemilih']
    return hasil, pemilih


def masalah(hasil):
    """Daftar (rentang, jenis) yang perlu diperbaiki."""
    keluar = []
    for lebar, h in hasil.items():
        r = rentang(lebar)
        if h['tinggi'] > TINGGI_MAKS[r] + 10:
            keluar.append((r, 'tinggi'))
        if r == 'desktop' and h['melebihi']:
            keluar.append((r, 'melebihi'))
        if h['tak_terlihat'] > BATAS_TAK_TERLIHAT:
            keluar.append((r, 'tak_terlihat'))
    return sorted(set(keluar))


def susun_css(tema, pemilih, hasil, css_lama=''):
    """CSS perbaikan (tanpa penanda) dari hasil ukur; css_lama = aturan putaran sebelumnya."""
    aturan = [css_lama] if css_lama else []
    soal = masalah(hasil)
    if not soal or not pemilih:
        return css_lama
    if tema in CSS_TEMA and CSS_TEMA[tema] not in css_lama and any(j in ('tinggi', 'melebihi') for _, j in soal):
        aturan.append(CSS_TEMA[tema])
    else:
        for r in sorted({r for r, j in soal if j == 'tinggi'}):
            aturan.append(f'@media {MEDIA[r]}{{{pemilih}{{width:auto;height:auto;max-height:{TINGGI_MAKS[r]}px;'
                          f'max-width:min(100%,{LEBAR_MAKS[r]}px);object-fit:contain}}}}')
        if ('desktop', 'melebihi') in soal:
            muat = min(h['muat'] for l, h in hasil.items() if rentang(l) == 'desktop' and h['melebihi'])
            if muat >= 140:
                aturan.append(f'@media {MEDIA["desktop"]}{{{pemilih}{{width:auto;height:auto;max-width:{muat - 8}px}}}}')
            else:
                # Tidak muat di bidang latarnya: logo diberi pelat sendiri supaya tetap utuh terbaca.
                soal.append(('desktop', 'tak_terlihat'))
    for r in sorted({r for r, j in soal if j == 'tak_terlihat'}):
        gelap = any(h['latar_gelap'] for l, h in hasil.items() if rentang(l) == r)
        warna = '#ffffff' if gelap else '#1f2937'
        aturan.append(f'@media {MEDIA[r]}{{{pemilih}{{background:{warna};padding:6px 12px;border-radius:8px;'
                      f'box-sizing:border-box}}}}')
    return '\n'.join(a for a in aturan if a)


def ringkas(hasil):
    return ' '.join(f"{l}:{h['lebar']}x{h['tinggi']}{'/melebihi' if h['melebihi'] and rentang(l) == 'desktop' else ''}"
                    f"/samar={h['tak_terlihat']}" for l, h in sorted(hasil.items(), key=lambda x: int(x[0])))
