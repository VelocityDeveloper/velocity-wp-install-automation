"""Tanya Claude (CLI `claude -p`, langganan yang sama dengan agen desain) tentang gambar.

Model gateway installer (`medium`) tidak bisa membaca gambar, dan model GPT gateway sering
kena batas pemakaian; Claude CLI dipakai untuk pekerjaan yang butuh melihat gambar:
memastikan logo klien (cari_logo) dan mengenali produk dari foto (toko-biasa).

Gambar disalin sebagai thumbnail JPEG ke folder kerja sementara (g01.jpg, g02.jpg, ...)
supaya token hemat dan nama berkas klien (spasi, emoji) tidak mengganggu. Claude hanya
diberi alat Read di folder itu.

tanya(prompt, gambar, ...) -> objek JSON jawaban Claude, atau None bila gagal/tak tersedia.
Di dalam prompt, gambar disebut dengan nama g01.jpg dst. sesuai urutan daftar `gambar`.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

CLAUDE = shutil.which('claude') or '/root/.local/bin/claude'
KUNCI_API = Path('/etc/velocity/secrets/anthropic_api_key')
MODEL = os.environ.get('VELOCITY_VISION_MODEL', 'sonnet')


def nama_gambar(i):
    return f'g{i + 1:02d}.jpg'


def _thumbnail(sumber, tujuan, sisi=512):
    from PIL import Image, ImageOps
    with Image.open(sumber) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA')
            latar = Image.new('RGB', im.size, 'white')
            latar.paste(im, mask=im.split()[-1])
            im = latar
        else:
            im = im.convert('RGB')
        im.thumbnail((sisi, sisi))
        im.save(tujuan, 'JPEG', quality=80)


def _urai_json(teks):
    teks = (teks or '').strip()
    pagar = re.search(r'```(?:json)?\s*(.*?)```', teks, re.S)
    if pagar:
        teks = pagar.group(1).strip()
    for awal, akhir in (('[', ']'), ('{', '}')):
        i, j = teks.find(awal), teks.rfind(akhir)
        if i >= 0 and j > i:
            try:
                return json.loads(teks[i:j + 1])
            except ValueError:
                continue
    return None


def tanya(prompt, gambar, timeout=300, sisi=512, log=None):
    """Kirim prompt + gambar ke Claude; kembalikan JSON hasil urai, atau None."""
    if not Path(CLAUDE).exists():
        if log:
            log('vision: claude_cli_tidak_ada')
        return None
    kerja = Path(tempfile.mkdtemp(prefix='velocity-vision-'))
    try:
        for i, g in enumerate(gambar):
            try:
                _thumbnail(g, kerja / nama_gambar(i), sisi)
            except Exception as e:  # berkas rusak: lewati, nomor tetap
                if log:
                    log(f'vision: thumbnail_gagal:{Path(g).name}:{type(e).__name__}')
        env = dict(os.environ)
        if KUNCI_API.is_file():
            env['ANTHROPIC_API_KEY'] = KUNCI_API.read_text().strip()
        perintah = [CLAUDE, '-p', prompt, '--model', MODEL, '--output-format', 'json',
                    '--no-session-persistence', '--allowedTools', 'Read', '--add-dir', str(kerja)]
        try:
            run = subprocess.run(perintah, cwd=kerja, capture_output=True, text=True, timeout=timeout, env=env)
            hasil = json.loads(run.stdout or '{}')
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            if log:
                log(f'vision: gagal:{type(e).__name__}')
            return None
        if hasil.get('is_error'):
            if log:
                log(f"vision: gagal:{str(hasil.get('result', ''))[:120]}")
            return None
        if log:
            log(f"vision: ok gambar={len(gambar)} biaya_usd={hasil.get('total_cost_usd', 0):.3f}")
        return _urai_json(hasil.get('result', ''))
    finally:
        shutil.rmtree(kerja, ignore_errors=True)
