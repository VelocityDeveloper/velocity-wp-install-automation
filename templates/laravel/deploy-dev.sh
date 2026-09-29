#!/bin/bash
# Perbarui dev {{JUDUL}} di Local PC: {{URL}}
# /home/{{SLUG}} = salinan kerja. Bersih → tarik commit terbaru dari GitHub; ada perubahan belum di-commit →
# tidak pull, hanya build supaya perubahan bisa dicoba.
set -euo pipefail
cd /home/{{SLUG}}
git fetch -q origin   # kredensial GitHub lewat gh (credential helper root)
if [ -z "$(git status --porcelain --untracked-files=no)" ]; then
  git pull -q --ff-only origin main
else
  echo "Ada perubahan belum di-commit, pull dilewati:"; git status --short --untracked-files=no
fi
git log --oneline -1
composer install --no-interaction
npm ci --no-audit --no-fund
npm run build
php artisan migrate --force
php artisan optimize:clear
# Layanan berjalan sebagai user {{PENGGUNA}}; berkas yang dibuat perintah root di atas dikembalikan kepemilikannya.
chown -R {{PENGGUNA}}:{{PENGGUNA}} storage bootstrap/cache
systemctl restart {{SLUG}}-dev {{SLUG}}-queue
sleep 3
curl -s -o /dev/null -w "dev HTTP %{http_code}\n" {{URL}}/login
