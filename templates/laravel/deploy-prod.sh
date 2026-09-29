#!/bin/bash
# Deploy {{JUDUL}} ke produksi ({{DOMAIN}}) dari commit main di GitHub.
# Build (composer --no-dev + npm run build) dilakukan di Local PC, server cukup menerima hasilnya:
#   PROD_PATH/releases/<waktu>  ← rilis baru,  PROD_PATH/current → rilis aktif,
#   PROD_PATH/shared/.env & shared/storage dipakai bersama semua rilis. 5 rilis terakhir disimpan untuk rollback.
# Tujuan diatur di /root/{{SLUG}}/prod.env.  Pakai: deploy-prod.sh [--yes]
set -euo pipefail
source /root/{{SLUG}}/prod.env
: "${PROD_SSH:?isi PROD_SSH di /root/{{SLUG}}/prod.env}" "${PROD_PATH:?isi PROD_PATH di /root/{{SLUG}}/prod.env}"
PROD_PORT=${PROD_PORT:-22}; PROD_PHP=${PROD_PHP:-php}
SSH=(ssh -p "$PROD_PORT" -o BatchMode=yes "$PROD_SSH")

KERJA=$(mktemp -d /tmp/{{SLUG}}-prod.XXXX); trap 'rm -rf "$KERJA"' EXIT
git clone -q --depth 1 --branch main "$(git -C /home/{{SLUG}} remote get-url origin)" "$KERJA/app"
cd "$KERJA/app"
KOMIT=$(git log --oneline -1); echo "Commit: $KOMIT"
if [ "${1:-}" != "--yes" ]; then
  read -rp "Deploy ke $PROD_SSH:$PROD_PATH ($PROD_DOMAIN)? ketik ya: " J; [ "$J" = ya ] || exit 1
fi
composer install --no-dev --optimize-autoloader --no-interaction -q
npm ci --no-audit --no-fund --loglevel=error
npm run build
rm -rf node_modules .git tests storage
RILIS=$(date +%Y%m%d%H%M%S)
"${SSH[@]}" "mkdir -p '$PROD_PATH/releases/$RILIS' '$PROD_PATH/shared/storage/app/public' '$PROD_PATH/shared/storage/framework/'{cache,sessions,views} '$PROD_PATH/shared/storage/logs' && test -f '$PROD_PATH/shared/.env'" \
  || { echo "Siapkan dulu $PROD_PATH/shared/.env di server"; exit 1; }
rsync -az --delete -e "ssh -p $PROD_PORT" ./ "$PROD_SSH:$PROD_PATH/releases/$RILIS/"
"${SSH[@]}" bash -s <<REMOTE
set -euo pipefail
cd '$PROD_PATH/releases/$RILIS'
ln -sfn '$PROD_PATH/shared/.env' .env
ln -sfn '$PROD_PATH/shared/storage' storage
$PROD_PHP artisan migrate --force
$PROD_PHP artisan storage:link -q || true
$PROD_PHP artisan optimize
ln -sfn '$PROD_PATH/releases/$RILIS' '$PROD_PATH/current.tmp' && mv -Tf '$PROD_PATH/current.tmp' '$PROD_PATH/current'
$PROD_PHP artisan queue:restart -q || true
ls -1dt '$PROD_PATH/releases/'* | tail -n +6 | xargs -r rm -rf
REMOTE
echo "Rilis $RILIS aktif ($KOMIT)"
[ -n "${PROD_DOMAIN:-}" ] && curl -s -o /dev/null -w "https://$PROD_DOMAIN HTTP %{http_code}\n" "https://$PROD_DOMAIN/login" || true
