"""Unduh zip plugin dari API plugin Velocity (api.velocitydeveloper.co/api/v1/plugins).

Pola yang sama dengan scripts/vd-store, untuk plugin lain yang didaftarkan di ApiCo
(velocity-produk sejak 2026-10-06). Zip disimpan di /var/lib/velocity/packages/<slug>-<versi>.zip;
kalau API/unduhan gagal, zip terbaru di tembolok dipakai.

  import plugin_api
  zip_path, versi = plugin_api.ambil_paket('velocity-produk', log=print)
"""
import hashlib
import json
import os
import re
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

API_URL = 'https://api.velocitydeveloper.co/api/v1/plugins'
PACKAGES = Path('/var/lib/velocity/packages')
UA = 'velocity-installer/1.0'
# Paket E/F: katalog/produk = velocity-produk dari API, tidak lagi velocity-paket (+ Meta Box)
# (keputusan user 2026-10-06). Paket lain tetap memakai plugin lokal templates/plugins/.
PAKET_EF = {'pakete', 'paketf'}
PLUGIN_API_EF = ('velocity-produk',)
PLUGIN_LOKAL_BUKAN_EF = ('velocity-paket',)


def paket_ef(paket):
    return re.sub(r'\s+', '', (paket or '').lower()) in PAKET_EF


def plugin_agen(paket, lokal):
    """Slug plugin yang boleh dipasang agen permintaan form: (lokal, dari_api)."""
    if paket_ef(paket):
        return sorted(s for s in lokal if s not in PLUGIN_LOKAL_BUKAN_EF), list(PLUGIN_API_EF)
    return sorted(lokal), []


def zip_valid(path, slug):
    """Zip harus berisi folder <slug>/ dengan berkas utama <slug>/<slug>.php."""
    try:
        with zipfile.ZipFile(path) as z:
            return f'{slug}/{slug}.php' in z.namelist()
    except (zipfile.BadZipFile, OSError):
        return False


def versi_key(path):
    m = re.search(r'-(\d+(?:\.\d+)*)\.zip$', path.name)
    return tuple(int(p) for p in m.group(1).split('.')) if m else ()


def daftar_api(timeout=30):
    # Header signature = md5 tanggal ddmmyyyy WIB (tanpa itu API membalas "Signature header is required.").
    tanggal = datetime.now(timezone(timedelta(hours=7))).strftime('%d%m%Y')
    req = urllib.request.Request(API_URL, headers={
        'User-Agent': UA, 'Accept': 'application/json',
        'signature': hashlib.md5(tanggal.encode()).hexdigest()})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp).get('data') or []


def ambil_paket(slug, log=print):
    """(path zip, versi) versi terbaru di API; (None, '') bila API & tembolok sama-sama kosong."""
    PACKAGES.mkdir(parents=True, exist_ok=True)
    try:
        item = next(p for p in daftar_api() if p.get('slug') == slug)
        versi = str(item.get('version') or '').strip()
        url = item.get('package_file_url') or item.get('package_external_url')
        if not re.match(r'^\d+(\.\d+)*$', versi) or not url:
            raise ValueError('data_api_tidak_lengkap')
        tujuan = PACKAGES / f'{slug}-{versi}.zip'
        if not zip_valid(tujuan, slug):
            sementara = tujuan.with_suffix('.part')
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=120) as resp:
                sementara.write_bytes(resp.read())
            if not zip_valid(sementara, slug):
                sementara.unlink(missing_ok=True)
                raise ValueError('zip_tidak_valid')
            os.replace(sementara, tujuan)
            log(f'paket_diunduh:{slug}-{versi}')
        return tujuan, versi
    except Exception as e:  # API/unduhan gagal → pakai tembolok
        tembolok = sorted((p for p in PACKAGES.glob(f'{slug}-*.zip') if zip_valid(p, slug)), key=versi_key)
        if not tembolok:
            log(f'paket_tidak_tersedia:{slug}:{type(e).__name__}')
            return None, ''
        pilih = tembolok[-1]
        versi = '.'.join(map(str, versi_key(pilih)))
        log(f'pakai_tembolok:{slug}-{versi}:{type(e).__name__}')
        return pilih, versi
