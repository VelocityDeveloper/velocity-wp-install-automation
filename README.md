# Velocity WordPress install automation

n8n-driven WordPress installer for DirectAdmin servers.

## Arsitektur

```
n8n (Manual Trigger {domain}) → Dry-run validate → IF dry_run ok? → Apply install → IF applied? → Success
                                   ↓ fail              ↓ fail
                              validation_failed    failed(apply)
```

Secrets tidak ada di workflow JSON — masuk via file terproteksi (env `*_FILE`).

## Required n8n environment contract

Set di n8n service environment, bukan di workflow JSON:

- `WP_INSTALL_SSH_KEY_FILE` — path private key (perm 0400/0600, owned root)
- `WP_INSTALL_DB_PASSWORD_FILE` — file berisi DB password
- `WP_INSTALL_ADMIN_PASSWORD_FILE` — file berisi WP admin password
- `WP_INSTALL_GITHUB_TOKEN_FILE` — opsional; untuk private repo Velocity

Secret files harus **not world-readable** (others=0), validator akan reject jika `perms` = `*44/*45/*46/*47`.

## Manifest

Location: `/home/project/<domain>/<domain>.txt`.

```ini
target_host=103.103.175.182
ssh_port=22
ssh_user=deploy
da_user=directadmin_user
domain=example.com
db_name=example_wp
db_user=example_wp
admin_user=admin
admin_email=admin@example.com
site_title=Example
velocity_addons_repo=https://github.com/VelocityDeveloper/velocity-addons.git
velocity_theme_repo=https://github.com/VelocityDeveloper/velocity-theme.git
```

Validasi: `target_host`, `domain` (FQDN), `da_user/ssh_user` (linux user), `db_name/db_user` (alnum+_), `admin_email`, `ssh_port` 1-65535. Repos harus `https://...`.

Database harus sudah ada. `apply` menginstall WordPress di `public_html` target, membuat `wp-config.php` (tanpa `--skip-check`), `wp core install` idempoten (skip jika sudah installed), dan install plugin/theme via `git clone` + `wp plugin/theme activate` (bukan `wp plugin install <git-url>`).

## Manual dry run

```bash
INSTALL_MODE=dry-run \
MANIFEST=/home/project/example.com/example.com.txt \
./scripts/website-install-from-manifest
# atau via wrapper
./scripts/n8n-run-install dry-run example.com
```

## Apply

Hanya via n8n setelah dry-run OK:

```bash
INSTALL_MODE=apply \
MANIFEST=/home/project/example.com/example.com.txt \
WP_INSTALL_SSH_KEY_FILE=/run/secrets/wp-install-ssh-key \
WP_INSTALL_DB_PASSWORD_FILE=/run/secrets/wp-install-db-password \
WP_INSTALL_ADMIN_PASSWORD_FILE=/run/secrets/wp-install-admin-password \
./scripts/website-install-from-manifest
```

Behavior apply:
- `flock` per-domain cegah paralel apply
- cek `wp-cli`, `git`, `php` ada di remote
- cek disk space ≥500MB
- backup `public_html` → `/home/<da_user>/backup/pre-install-<domain>-<timestamp>.tar.gz` jika tidak kosong
- secrets di-inject via `export` di stdin (single-quote escaped), bukan di `ps` argv

Destruktif: tulis file WP & DB state di target. Backup dibuat otomatis; rollback operator: `tar -xzf backup.tar.gz -C public_html`.

## Installer status API (`services/installer_status.py`)

Loopback `127.0.0.1:9121`.

Endpoints:
- `GET /health` — no auth
- `GET /api/servers` — daftar server (dari `config/servers.json` atau env `INSTALLER_SERVERS` JSON)
- `GET /api/installer` — daftar domain + validasi manifest per-file + cronjobs summary (cache 30s, tidak bocor raw crontab)

Auth: jika `INSTALLER_API_TOKEN` di-set, semua `/api/*` butuh `Authorization: Bearer <token>`. Rate-limit 30 req/60s per IP. Jangan expose port 9121 langsung — via reverse proxy.

Konfigurasi server tujuan: `config/servers.json` (array `[{name,host,port}]`) atau env `INSTALLER_SERVERS`.

## Installer page (`web/installer/index.html`)

Terminal-style `/installer/`.

- pilih server tujuan (dari `/api/servers`)
- lihat validasi manifest (READY vs `missing_*/invalid_*`)
- tombol `[ install ]` → modal konfirmasi → info trigger n8n (tidak eksekusi langsung dari browser)
- polling 10s, pause saat `document.hidden`

## Workflow (`workflows/website-install-workflow.json`)

Import ke n8n. Trigger: Manual Trigger dengan `{"domain":"example.com"}`. Node `Execute Command` pakai wrapper `scripts/n8n-run-install` (validasi & escape domain, cegah injection).

Timeouts: dry-run 30s, apply 300s. Dry-run retry 2x.
