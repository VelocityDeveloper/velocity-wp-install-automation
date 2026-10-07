"""Ubah presentasi kiriman klien (.pptx/.ppt/.odp) jadi PDF lewat LibreOffice.

Company profile sering dikirim sebagai PowerPoint, bukan PDF. Pembaca dokumen
(client_docs) dan compro-klien dulu hanya mengenal .pdf, jadi berkas itu
dilewati tanpa pesan: chindrasantipratama.com (2026-09-26) terpasang hanya dari
FORM ISIAN padahal compro .pptx-nya sudah di Drive. Hasil PDF disimpan per
(berkas, ukuran, mtime) karena deck 100+ MB butuh beberapa menit untuk diubah.
"""
import hashlib
import html
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

PRESENTASI = {'.pptx', '.ppt', '.pps', '.ppsx', '.odp'}
SIMPAN = Path('/var/lib/velocity/presentasi-pdf')
BATAS_DETIK = 900


def _kunci(path):
    st = path.stat()
    return hashlib.sha1(f'{path.resolve()}|{st.st_size}|{int(st.st_mtime)}'.encode()).hexdigest()[:16]


def ke_pdf(path):
    """Path PDF hasil ubahan, atau None bila LibreOffice tidak ada / gagal."""
    path = Path(path)
    if path.suffix.lower() not in PRESENTASI or not path.is_file():
        return None
    tujuan = SIMPAN / _kunci(path) / f'{path.stem}.pdf'
    if tujuan.is_file() and tujuan.stat().st_size > 0:
        return tujuan
    soffice = shutil.which('soffice') or shutil.which('libreoffice')
    if not soffice:
        return None
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    # Profil LibreOffice sendiri per panggilan: dua proses yang berbagi profil
    # bawaan saling mengunci dan yang kedua keluar tanpa menghasilkan berkas.
    with tempfile.TemporaryDirectory() as profil, tempfile.TemporaryDirectory() as keluar:
        try:
            subprocess.run([soffice, f'-env:UserInstallation=file://{profil}', '--headless',
                            '--convert-to', 'pdf', '--outdir', keluar, str(path)],
                           capture_output=True, timeout=BATAS_DETIK)
        except (OSError, subprocess.TimeoutExpired):
            return None
        hasil = Path(keluar) / f'{path.stem}.pdf'
        if not hasil.is_file() or hasil.stat().st_size == 0:
            return None
        shutil.move(str(hasil), tujuan)
    return tujuan


def teks_pptx(path):
    """Baris teks slide .pptx berurutan, dibaca langsung dari XML-nya.

    Lebih bersih daripada pdftotext atas PDF ubahan: teks rata kiri-kanan di deck
    keluar berjarak antarhuruf ("C h i n d r a") dan baris kotak teks bertumpuk
    ikut hilang. None bila bukan zip .pptx yang sah."""
    try:
        with zipfile.ZipFile(path) as z:
            slide = sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)),
                           key=lambda n: int(re.findall(r'\d+', n)[-1]))
            baris = []
            for n in slide:
                xml = z.read(n).decode('utf8', 'replace')
                for par in re.findall(r'<a:p>.*?</a:p>|<a:p .*?</a:p>', xml, re.S):
                    teks = ''.join(re.findall(r'<a:t>([^<]*)</a:t>', par))
                    teks = html.unescape(teks).strip()
                    if teks:
                        baris.append(teks)
            return baris
    except (OSError, zipfile.BadZipFile, KeyError):
        return None


if __name__ == '__main__':
    import sys
    for arg in sys.argv[1:]:
        print(arg, '->', ke_pdf(arg))
