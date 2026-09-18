#!/usr/bin/env python3
"""Cari logo asli klien di SEMUA berkas kiriman klien, bukan hanya yang bernama "logo".

Keputusan user 2026-09-16: logo dicari dulu di berkas yang diupload klien — company
profile, compro, maupun berkas lain — dan logo contoh buatan installer baru dipakai
kalau benar-benar tidak ada. Sebelumnya hanya dua sumber: gambar bernama `logo*` di
folder klien, dan potongan dari satu PDF compro terpilih; bumiairchemitech.com punya
logo di deck 24 halaman yang tidak terpilih, jadi situsnya sempat memakai logo contoh.

Urutan (yang lebih pasti lebih dulu):
  1. gambar di folder klien yang namanya menyebut logo/lambang/brand
  2. logo hasil compro-klien (compro.json)
  3. gambar tertanam di PDF mana pun di folder klien (termasuk yang bukan compro)
  4. gambar tertanam di dokumen Office (.docx/.pptx) — logo kop surat & sampul proposal
  5. gambar lain di folder yang berciri logo: PNG bertransparansi, kecil, tidak mendatar

Pemakaian: cari(domain, folder, compro) -> (Path | None, 'sumber')
"""
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
KELUAR = Path('/var/lib/velocity/logos')
NAMA_LOGO = re.compile(r'logo|lambang|brand|logotype', re.I)
# Subfolder acuan desain: isinya logo perusahaan LAIN (situs contoh), bukan logo klien.
BUKAN_KLIEN = re.compile(r'contoh|referensi|screenshot|tangkapan\s*layar|desain', re.I)
GAMBAR = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
MIN_SISI = 64
MAKS_SISI = 2000


def ukuran(path):
    """(lebar, tinggi) dari header berkas; server installer tanpa PIL/ImageMagick."""
    try:
        data = Path(path).open('rb').read(65536)
    except OSError:
        return None
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return struct.unpack('>II', data[16:24])
    if data[:3] == b'\xff\xd8\xff':
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            penanda, panjang = data[i + 1], struct.unpack('>H', data[i + 2:i + 4])[0]
            if penanda in (0xC0, 0xC1, 0xC2, 0xC3):
                tinggi, lebar = struct.unpack('>HH', data[i + 5:i + 9])
                return lebar, tinggi
            i += 2 + panjang
        return None
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        if data[12:16] == b'VP8X':
            lebar = int.from_bytes(data[24:27], 'little') + 1
            tinggi = int.from_bytes(data[27:30], 'little') + 1
            return lebar, tinggi
        return None
    if data[:6] in (b'GIF87a', b'GIF89a'):
        return struct.unpack('<HH', data[6:10])
    return None


def png_transparan(path):
    """PNG dengan kanal alpha atau tRNS — ciri khas berkas logo."""
    try:
        data = Path(path).open('rb').read(1024)
    except OSError:
        return False
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return False
    return data[25] in (4, 6) or b'tRNS' in data


def _ciri_piksel(path):
    """(transparan, warna_berbeda, tinta, detail) dari PNG; None kalau tidak terbaca.

    Dipakai membedakan logo dari tangkapan layar & kotak hiasan: keduanya sempat
    lolos sebagai "logo" (aktualtangerang.com & ptbarikoputrapersada.com, 2026-09-16).
    """
    import colorsys
    try:
        ck = _muat_compro()
        lebar, tinggi, kanal, baris = ck.baca_png(path)
    except Exception:
        return None
    ly, lx = max(1, tinggi // 60), max(1, lebar // 60)
    warna, tembus, tampak, tinta, terang_baris = set(), 0, 0, 0, []
    for y in range(0, tinggi, ly):
        seri = []
        for x in range(0, lebar, lx):
            o = x * kanal
            if kanal == 4 and baris[y][o + 3] < 40:
                tembus += 1
                continue
            tampak += 1
            rgb = baris[y][o:o + 3] if kanal >= 3 else bytes([baris[y][o]] * 3)
            warna.add(tuple(c // 32 for c in rgb))
            l = colorsys.rgb_to_hls(*(c / 255 for c in rgb))[1]
            seri.append(l)
            if l < 0.85:
                tinta += 1
        terang_baris += [abs(seri[i + 1] - seri[i]) for i in range(len(seri) - 1)]
    total = tembus + tampak
    if not total or not tampak:
        return None
    detail = sum(terang_baris) / len(terang_baris) if terang_baris else 0
    return tembus / total, len(warna), tinta / tampak, detail


def mirip_logo(path):
    """Saring kandidat dari PDF/dokumen/gambar lepas: logo, bukan tangkapan layar.

    Logo = latar tembus pandang (atau warnanya sedikit), palet terbatas, dan ada
    tinta yang benar-benar tergambar. Tangkapan layar situs punya ratusan warna
    tanpa transparansi; kotak bayangan hiasan hampir seluruhnya putih.
    """
    ciri = _ciri_piksel(path)
    if not ciri:
        return False
    tembus, warna, tinta, detail = ciri
    if warna > 60:
        return False
    if tembus < 0.15 and warna > 24:
        return False
    # Ambang detail sengaja rendah: logo datar dua warna (BACh) 0.0024, sedangkan
    # kotak bayangan hiasan benar-benar 0.0000.
    return tinta >= 0.05 and detail > 0.0005


def berciri_logo(path):
    dim = ukuran(path)
    if not dim:
        return False
    lebar, tinggi = dim
    if min(lebar, tinggi) < MIN_SISI or max(lebar, tinggi) > MAKS_SISI:
        return False
    rasio = lebar / max(tinggi, 1)
    return 0.4 <= rasio <= 3.0 and png_transparan(path)


def _muat_compro():
    import importlib.machinery
    import importlib.util
    jalur = HERE / 'compro-klien'
    spec = importlib.util.spec_from_loader('compro_klien', importlib.machinery.SourceFileLoader('compro_klien', str(jalur)))
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _render_pdf_vektor(pdf, tujuan):
    """Logo vektor: PDF tanpa gambar tertanam (mis. hasil Vectorizer.AI) tidak
    menghasilkan apa pun lewat pdfimages, jadi halamannya dirender lalu dipangkas
    ke area bertinta. Kasus nyata: solusicerdasconsulting.com/logo.pdf (2026-09-18)."""
    if not shutil.which('pdftocairo'):
        return None
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            dasar = Path(tmp) / 'render'
            subprocess.run(['pdftocairo', '-png', '-r', '400', '-singlefile', str(pdf), str(dasar)],
                           check=True, capture_output=True, timeout=120)
            berkas = dasar.with_suffix('.png')
            if not berkas.is_file():
                return None
            im = Image.open(berkas).convert('RGB')
            latar = Image.new('RGB', im.size, (255, 255, 255))
            kotak = ImageChops.difference(im, latar).convert('L').point(
                lambda v: 255 if v > 12 else 0).getbbox()
            if not kotak:
                return None
            lebar, tinggi = kotak[2] - kotak[0], kotak[3] - kotak[1]
            # Halaman penuh tinta = pindaian/latar berwarna, bukan logo lepas.
            if lebar < 40 or tinggi < 40 or (lebar * tinggi) > 0.92 * im.width * im.height:
                return None
            sisa = 24
            im = Image.open(berkas).convert('RGBA').crop((
                max(kotak[0] - sisa, 0), max(kotak[1] - sisa, 0),
                min(kotak[2] + sisa, im.width), min(kotak[3] + sisa, im.height)))
            # Halaman PDF hampir selalu mengecat kotak putih dulu, jadi `-transp`
            # tidak menghasilkan apa-apa: putihnya dijadikan tembus pandang sendiri
            # (logo di header tema harus tanpa latar, dan `mirip_logo` menolak
            # gambar tanpa transparansi berwarna banyak).
            merah, hijau, biru, _ = im.split()
            paling_gelap = ImageChops.darker(ImageChops.darker(merah, hijau), biru)
            # 250 ke atas = latar, 235 ke bawah = tinta, di antaranya tepi halus.
            im.putalpha(paling_gelap.point(
                lambda v: 0 if v >= 250 else 255 if v <= 235 else round((250 - v) * 255 / 15)))
            if im.height > 400:
                im = im.resize((round(im.width * 400 / im.height), 400), Image.LANCZOS)
            tujuan.parent.mkdir(parents=True, exist_ok=True)
            im.save(tujuan)
            return tujuan
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _dari_pdf(pdf, tujuan):
    """Potong logo dari halaman pertama sebuah PDF (pakai pemotong compro-klien)."""
    if not shutil.which('pdfimages') or not shutil.which('pdfinfo'):
        return None
    try:
        ck = _muat_compro()
        with tempfile.TemporaryDirectory() as tmp:
            gambar = ck.ekstrak_gambar(pdf, 1, Path(tmp))
            hasil = ck.potong_logo(gambar, tujuan)
            if hasil:
                return Path(hasil['berkas'])
    except Exception:
        pass
    return _render_pdf_vektor(pdf, tujuan)


def _dari_office(berkas, tujuan_dir):
    """Gambar tertanam di .docx/.pptx yang berciri logo (kop surat, sampul proposal)."""
    try:
        with zipfile.ZipFile(berkas) as z:
            nama = [n for n in z.namelist()
                    if re.match(r'(word|ppt|xl)/media/', n) and Path(n).suffix.lower() in GAMBAR]
            nama.sort(key=lambda n: z.getinfo(n).file_size, reverse=True)
            for n in nama[:12]:
                keluar = tujuan_dir / f'office-{Path(n).name}'
                keluar.write_bytes(z.read(n))
                if berciri_logo(keluar) or NAMA_LOGO.search(n):
                    return keluar
                keluar.unlink(missing_ok=True)
    except (OSError, zipfile.BadZipFile, KeyError):
        return None
    return None


def cari(domain, folder, compro=None):
    """(berkas, sumber). sumber: nama-berkas | company profile | pdf:<nama> | dokumen:<nama> | gambar-klien."""
    folder = Path(folder)
    berkas = []
    if folder.is_dir():
        berkas = sorted(p for p in folder.rglob('*') if p.is_file()
                        and not any(BUKAN_KLIEN.search(b) for b in p.relative_to(folder).parts))

    # 1. gambar yang namanya memang menyebut logo
    bernama = [p for p in berkas if p.suffix.lower() in GAMBAR and NAMA_LOGO.search(p.name)
               and p.stat().st_size >= 1000]
    if bernama:
        pilih = max(bernama, key=lambda p: (p.suffix.lower() == '.png', p.stat().st_size))
        return pilih, pilih.name

    # 1b. Folder "desain" bisa berisi desain situs MILIK klien sendiri (centralimpex.com
    # 2026-09-17: ekspor HTML berisi central-impex-logo.png). Logo di sana dipakai hanya bila
    # namanya memuat nama domain klien — logo situs contoh perusahaan lain tetap diabaikan.
    label = re.sub(r'[^a-z0-9]', '', domain.lower().split('.')[0])
    if folder.is_dir() and len(label) >= 4:
        milik = sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in GAMBAR | {'.svg'}
                       and NAMA_LOGO.search(p.name) and label in re.sub(r'[^a-z0-9]', '', p.name.lower())
                       and p.suffix.lower() != '.svg' and p.stat().st_size >= 1000)
        if milik:
            pilih = max(milik, key=lambda p: (p.suffix.lower() == '.png', p.stat().st_size))
            return pilih, f'desain-klien:{pilih.name}'

    # 2. hasil potongan compro-klien
    logo_compro = Path(((compro or {}).get('logo') or {}).get('berkas', '') or '')
    if logo_compro.is_file():
        return logo_compro, 'company profile'

    tujuan = KELUAR / domain
    tujuan.mkdir(parents=True, exist_ok=True)

    # 3. PDF lain (proposal, katalog, company profile yang tidak terpilih)
    pdf_terpakai = Path((compro or {}).get('pdf', '') or '')
    for pdf in [p for p in berkas if p.suffix.lower() == '.pdf' and p != pdf_terpakai
                and not p.name.upper().startswith('FORM ISIAN')]:
        hasil = _dari_pdf(pdf, tujuan / 'logo-pdf.png')
        if hasil and mirip_logo(hasil):
            return hasil, f'pdf:{pdf.name}'
        if hasil:
            Path(hasil).unlink(missing_ok=True)

    # 4. dokumen Office
    for dok in [p for p in berkas if p.suffix.lower() in ('.docx', '.pptx')]:
        hasil = _dari_office(dok, tujuan)
        if hasil and mirip_logo(hasil):
            return hasil, f'dokumen:{dok.name}'
        if hasil:
            Path(hasil).unlink(missing_ok=True)

    # 5. gambar lain yang berciri logo (PNG transparan, tidak mendatar, tidak raksasa)
    kandidat = [p for p in berkas if p.suffix.lower() in GAMBAR and berciri_logo(p) and mirip_logo(p)]
    if kandidat:
        pilih = min(kandidat, key=lambda p: p.stat().st_size)
        return pilih, f'gambar-klien:{pilih.name}'
    return None, ''
