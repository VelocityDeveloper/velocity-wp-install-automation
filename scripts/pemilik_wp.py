#!/usr/bin/env python3
"""Kembalikan kepemilikan wp-content ke user situs sesudah WP-CLI berjalan sebagai root.

Pemakaian: pemilik_wp.py <manifest>        (dipanggil installer-runner di akhir setiap run)
           import pemilik_wp; pemilik_wp.rapikan()   (di akhir setiap skrip langkah)

`chown -R` docroot hanya terjadi sekali di website-install-from-manifest. Langkah
sesudahnya (fse-apply, child-theme-apply, vd-store, media import, ...) memanggil
WP-CLI sebagai root, sehingga berkas barunya milik root. Yang paling merugikan:
`wp theme/plugin install <zip>` membuat wp-content/upgrade milik root, lalu PHP
situs (user DA) tidak bisa mengekstrak zip -> pasang/perbarui plugin & tema dari
wp-admin gagal (layananhipnoterapi.com 2026-09-18: Site Kit & WPCode; 14 situs lain
di server yang sama).

Pemilik = pemilik wp-content itu sendiri (bukan nama user dari manifest), supaya
staging velocitydeveloper.co ikut benar. Bila wp-content sendiri milik root,
dipakai pemilik docroot; bila itu juga root, tidak ada yang diubah.
"""
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# Remote: $D = docroot. `chown -h` tidak pernah mengikuti symlink keluar docroot.
REMOTE = r'''
W="$D/wp-content"
[ -d "$W" ] || { echo "pemilik: dilewati:wp_content_tidak_ada"; exit 0; }
p=$(stat -c %U:%G "$W")
[ "${p%%:*}" != root ] || p=$(stat -c %U:%G "$D")
[ "${p%%:*}" != root ] || { echo "pemilik: dilewati:pemilik_root"; exit 0; }
n=$(find "$W" -xdev \( ! -user "${p%%:*}" -o ! -group "${p#*:}" \) 2>/dev/null | wc -l)
if [ "$n" -gt 0 ]; then
  chown -R -h "$p" "$W" && echo "pemilik: wp_content_dirapikan:$p:$n" || echo "pemilik: chown_gagal:$p"
else
  echo "pemilik: sudah_benar:$p"
fi
'''


def manifest_dari_argv(argv):
    """Argumen pertama yang bukan opsi = manifest (pola semua skrip langkah)."""
    for a in argv[1:]:
        if not a.startswith('-'):
            return a
    return ''


def read_manifest(path):
    cfg = {}
    for line in Path(path).read_text(errors='replace').splitlines():
        key, sep, value = line.partition('=')
        if sep and re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key.strip()):
            cfg[key.strip()] = value.strip()
    return cfg


def rapikan(manifest=None, argv=None):
    """Satu koneksi SSH: chown -R wp-content ke pemiliknya. Tidak pernah melempar galat."""
    argv = sys.argv if argv is None else argv
    # Uji coba & dry-run tidak boleh mengubah server.
    if os.environ.get('INSTALL_MODE') == 'dry-run' or any(a in ('--coba', '--deteksi') for a in argv):
        return
    manifest = manifest or manifest_dari_argv(argv)
    try:
        if not manifest or not Path(manifest).is_file():
            return
        cfg = read_manifest(manifest)
        domain, da_user = cfg.get('domain', '').lower(), cfg.get('da_user', '')
        key = os.environ.get('WP_INSTALL_SSH_KEY_FILE', '')
        lokal = os.environ.get('VELOCITY_LOKAL_SSH', ''), os.environ.get('VELOCITY_LOKAL_DOCROOT', '')
        if all(lokal):
            ssh, docroot = [lokal[0]], lokal[1]
        else:
            if not (domain and da_user and cfg.get('target_host') and key and Path(key).is_file()):
                return
            ssh = ['ssh', '-i', key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
                   '-o', 'ConnectTimeout=15', '-p', str(cfg.get('ssh_port') or 22),
                   f"{cfg.get('ssh_user') or 'root'}@{cfg['target_host']}"]
            docroot = f'/home/{da_user}/domains/{domain}/public_html'
        run = subprocess.run(ssh + ['bash', '-s'], input=f'D={shlex.quote(docroot)}\n' + REMOTE,
                             capture_output=True, text=True, timeout=300)
        keluar = [l for l in run.stdout.splitlines() if l.startswith('pemilik:')]
        print(keluar[-1] if keluar else f'pemilik: gagal:{(run.stderr.strip().splitlines() or ["tanpa_keluaran"])[-1][:100]}',
              flush=True)
    except Exception as e:
        print(f'pemilik: gagal:{type(e).__name__}', flush=True)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: pemilik_wp.py <manifest>', file=sys.stderr)
        sys.exit(2)
    rapikan(sys.argv[1])
