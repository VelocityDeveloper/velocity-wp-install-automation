#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR=${REPO_DIR:-/opt/velocity-wp-install-automation}
INSTALL_ROOT=${INSTALL_ROOT:-/opt/velocity-wp-install-automation}
WEB_ROOT=${WEB_ROOT:-/usr/share/nginx/html}

cd "$REPO_DIR"
git pull --ff-only origin main
bash -n scripts/website-install-from-manifest scripts/installer-runner
python3 -m json.tool workflows/website-install-workflow.json >/dev/null

install -d -m 755 "$INSTALL_ROOT/scripts"
if [[ "$(realpath scripts/website-install-from-manifest)" != "$(realpath "$INSTALL_ROOT/scripts/website-install-from-manifest")" ]]; then
  install -m 755 scripts/website-install-from-manifest "$INSTALL_ROOT/scripts/website-install-from-manifest"
fi
if [[ "$(realpath scripts/installer-runner)" != "$(realpath "$INSTALL_ROOT/scripts/installer-runner")" ]]; then
  install -m 755 scripts/installer-runner "$INSTALL_ROOT/scripts/installer-runner"
fi
install -m 644 services/installer_status.py /usr/local/bin/installer_status.py
install -d -m 755 "$WEB_ROOT/installer"
install -m 644 web/installer/index.html "$WEB_ROOT/installer/index.html"

systemctl restart installer-status.service
nginx -t
systemctl reload nginx
systemctl is-active --quiet installer-status.service
printf 'deploy=ok commit=%s\n' "$(git rev-parse --short HEAD)"
