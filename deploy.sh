#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR=${REPO_DIR:-/opt/velocity-wp-install-automation}
INSTALL_ROOT=${INSTALL_ROOT:-/opt/velocity-wp-install-automation}
WEB_ROOT=${WEB_ROOT:-/usr/share/nginx/html}

cd "$REPO_DIR"
git pull --ff-only origin main
bash -n scripts/website-install-from-manifest scripts/installer-runner
python3 -m py_compile scripts/velocity-child-theme scripts/child-theme-apply scripts/velocity-logo scripts/paket-g-setup scripts/site-audit scripts/velocity-map scripts/paket-g-konten scripts/paket-g-foto scripts/compro-klien scripts/cek-fungsi-tema scripts/paket-g-cek-visual scripts/fse-apply scripts/fse-dealer scripts/fse-klinik scripts/referensi_desain.py scripts/fse-cek-referensi scripts/fse-audit-kemiripan scripts/desain-claude scripts/desain-claude-alat services/installer_status.py
node --check scripts/referensi-desain.js
node --check scripts/potret-halaman
node --check scripts/banding-potret
python3 -m py_compile scripts/audit-susulan scripts/notify-telegram.py scripts/content_sanitize.py scripts/ai-content-generator.py scripts/pemilik_wp.py scripts/site-finish scripts/vd-store scripts/vd-store-settings scripts/paket-tour scripts/theme-paket-biasa scripts/site-ssl scripts/permintaan-form scripts/baca-form-claude scripts/permintaan-claude scripts/permintaan-claude-alat scripts/brain-data scripts/brain-aktivitas scripts/claude-pakai scripts/setor-status-ai
python3 -m json.tool workflows/website-install-workflow.json >/dev/null
# Penjaga tema FSE: markup blok templates/parts/patterns harus valid menurut parser
# editor WordPress (kode 3 = alat node belum terpasang di mesin ini, dilewati).
python3 -m json.tool templates/tema-fse/theme.json >/dev/null
# Setiap tema wajib punya screenshot.jpg 1200x900 (aturan user 2026-09-16); tanpa itu
# tema tampil sebagai kotak kosong di Tampilan → Tema.
[[ -s templates/tema-fse/screenshot.jpg ]] || { echo 'ERROR: templates/tema-fse/screenshot.jpg hilang' >&2; exit 1; }
node scripts/cek-blok templates/tema-fse/templates/*.html templates/tema-fse/parts/*.html templates/tema-fse/patterns/*.php >/dev/null || [[ $? == 3 ]]
for f in $(find templates/tema-fse -name '*.php'); do php -l "$f" >/dev/null; done
# Penjaga kontras: template tidak boleh lolos deploy kalau teks di latar gelap
# kembali jatuh ke warna tinta (lihat docs/warna-dan-kontras.md).
python3 scripts/cek-warna-tema >/dev/null
# Penjaga fungsi: render template untuk domain uji — velocity-child-theme menolak
# zip yang memanggil fungsi tema yang tidak didefinisikan (php -l tidak menangkapnya).
uji_tema=$(mktemp -d)
python3 scripts/velocity-child-theme uji-paket-g.test --paket "Paket G" --nama "Uji Paket G" --cache "$uji_tema" | grep -q '^status=generated'
rm -rf "$uji_tema"
# Penjaga palet FSE: situs biasa harus berlatar terang, palet gelap hanya untuk gaya
# dealer. Parameter `gelap` pernah tertimpa variabel warna bernama sama sehingga SEMUA
# situs FSE berlatar hitam (2026-09-16) — cek nilainya, bukan cuma sintaksnya.
python3 scripts/cek-palet-fse >/dev/null

install -d -m 755 "$INSTALL_ROOT/scripts"
if [[ "$(realpath scripts/website-install-from-manifest)" != "$(realpath "$INSTALL_ROOT/scripts/website-install-from-manifest")" ]]; then
  install -m 755 scripts/website-install-from-manifest "$INSTALL_ROOT/scripts/website-install-from-manifest"
fi
if [[ "$(realpath scripts/installer-runner)" != "$(realpath "$INSTALL_ROOT/scripts/installer-runner")" ]]; then
  install -m 755 scripts/installer-runner "$INSTALL_ROOT/scripts/installer-runner"
fi
if [[ "$(realpath scripts/ai-content-generator.py)" != "$(realpath "$INSTALL_ROOT/scripts/ai-content-generator.py")" ]]; then
  install -m 755 scripts/ai-content-generator.py "$INSTALL_ROOT/scripts/ai-content-generator.py"
fi
# Dashboard utama = aplikasi Vue (web-vue/, rute /installer /server /ai /paket /token /brain dilayani
# index.html-nya lewat try_files nginx). Dashboard HTML lama tetap ada di /lama/ dengan tautan
# antarhalaman diarahkan ke /lama/… (2026-09-24).
pasang_lama() {  # pasang_lama <sumber> <tujuan relatif web root>
  install -d -m 755 "$(dirname "$WEB_ROOT/$2")"
  sed -e 's#href="/"#href="/lama/"#g' -e 's#"/\(installer\|server\|ai\|packages\)/#"/lama/\1/#g' "$1" > "$WEB_ROOT/$2.tmp"
  chmod 644 "$WEB_ROOT/$2.tmp" && mv "$WEB_ROOT/$2.tmp" "$WEB_ROOT/$2"
}
pasang_lama web/index.html lama/index.html
pasang_lama web/installer/index.html lama/installer/index.html
pasang_lama web/installer/susulan/index.html lama/installer/susulan/index.html
pasang_lama web/server/index.html lama/server/index.html
pasang_lama web/ai/index.html lama/ai/index.html
pasang_lama web/packages/index.html lama/packages/index.html
# alur.js dipakai dua dashboard: Vue memuat /alur.js, halaman lama /lama/installer/alur.js
install -m 644 web/installer/alur.js "$WEB_ROOT/alur.js"
install -m 644 web/installer/alur.js "$WEB_ROOT/lama/installer/alur.js"
( cd web-vue && { [[ -d node_modules ]] || npm ci --no-audit --no-fund; } && npx vite build >/dev/null )
install -d -m 755 "$WEB_ROOT/v2-assets"
rsync -a --delete web-vue/dist/v2-assets/ "$WEB_ROOT/v2-assets/"
install -m 644 web-vue/dist/ikon.png "$WEB_ROOT/ikon.png"
install -m 644 web-vue/dist/favicon.svg "$WEB_ROOT/favicon.svg"
install -m 644 web-vue/dist/index.html "$WEB_ROOT/index.html"
install -d -m 755 "$WEB_ROOT/brain"
install -m 644 web/brain/index.html "$WEB_ROOT/brain/index.html"
# data.json /brain/ ditulis brain-data.timer, aktivitas.json oleh brain-aktivitas.service (config/brain-*), bukan oleh deploy
systemctl try-restart brain-aktivitas.service

# Tanpa langkah salin, restart hanya berarti kalau unit menunjuk file repo.
# Kalau masih menunjuk salinan lama, deploy akan sukses tapi tidak mengubah apa pun.
if ! systemctl cat installer-status.service 2>/dev/null | grep -q "$INSTALL_ROOT/services/installer_status.py"; then
  echo "ERROR: installer-status.service belum menunjuk $INSTALL_ROOT/services/installer_status.py" >&2
  echo "Perbaiki: install -m 644 config/installer-status.service /etc/systemd/system/ && systemctl daemon-reload" >&2
  exit 1
fi
systemctl restart installer-status.service
nginx -t
systemctl reload nginx
systemctl is-active --quiet installer-status.service
printf 'deploy=ok commit=%s\n' "$(git rev-parse --short HEAD)"
