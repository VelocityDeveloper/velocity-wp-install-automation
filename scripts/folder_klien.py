"""Folder bahan klien di /home/On Progress untuk satu domain.

Bawaannya /home/On Progress/<domain>. PM bisa menunjuk subfolder lewat deskripsi tiket
pembuatan di CRM, mis. "sub folder desalangkas.com baru" -> /home/On Progress/desalangkas.com/
desalangkas.com baru (keputusan user 2026-09-26): folder domain berisi bahan lama (form, catatan
hosting, revisi) yang tidak boleh ikut terbaca. installer_status.py mencatat petunjuk itu dari CRM
ke PETA setiap antrean ditarik; semua skrip installer membaca folder klien lewat folder_klien().
"""
import json
import re
from pathlib import Path

ON_PROGRESS = Path('/home/On Progress')
PETA = Path('/var/lib/velocity/installer/subfolder-crm.json')
SUBFOLDER_RE = re.compile(r'\bsub\s*-?\s*folder\b\s*[:=\-]?\s*(.+)', re.I)


def subfolder_dari_deskripsi(teks):
    """Nama subfolder dari deskripsi tiket CRM; '' kalau deskripsi tidak menyebutnya."""
    for baris in str(teks or '').splitlines():
        m = SUBFOLDER_RE.search(baris)
        if m:
            # Deskripsi bisa berlanjut ke catatan lain: "sub folder x.com baru, tf jadi 1 ..."
            nama = re.split(r'[,;]', m.group(1))[0]
            nama = nama.strip().strip('"\'“”‘’`').strip().rstrip('/').strip()
            if nama and '/' not in nama and not nama.startswith('.'):
                return nama
    return ''


def _peta():
    try:
        data = json.loads(PETA.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _cocokkan(akar, nama):
    """Subfolder bernama `nama` di `akar`; spasi ganda & huruf besar/kecil diabaikan."""
    tepat = akar / nama
    if tepat.is_dir():
        return tepat
    kunci = ' '.join(nama.lower().split())
    try:
        for d in akar.iterdir():
            if d.is_dir() and ' '.join(d.name.lower().split()) == kunci:
                return d
    except OSError:
        pass
    return None


def folder_klien(domain, akar=ON_PROGRESS):
    """Path folder bahan klien; subfolder dari CRM bila ditunjuk dan sudah ada di Drive."""
    domain = str(domain).strip()
    dasar = Path(akar) / domain
    nama = _peta().get(domain.lower())
    if nama:
        sub = _cocokkan(dasar, nama)
        if sub:
            return sub
    return dasar


def subfolder_crm(domain):
    """Nama subfolder yang ditunjuk CRM untuk domain ('' kalau tidak ada)."""
    return _peta().get(str(domain).strip().lower(), '')
