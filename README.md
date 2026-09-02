# Velocity WordPress install automation

n8n-driven WordPress installer for DirectAdmin servers.

Flow: n8n reads `/home/project/<domain>/<domain>.txt`, validates non-secret settings, then runs `scripts/website-install-from-manifest` through Execute Command. SSH and database secrets stay outside Git and enter through environment variables or protected files.

## Required n8n environment contract

Set these in n8n service environment, not in workflow JSON:

- `WP_INSTALL_SSH_KEY_FILE` — root-readable private key path
- `WP_INSTALL_DB_PASSWORD_FILE` — root-readable file containing database password
- `WP_INSTALL_ADMIN_PASSWORD_FILE` — root-readable file containing WordPress admin password
- `WP_INSTALL_GITHUB_TOKEN_FILE` — optional; only needed for private Velocity repositories

Use n8n Credentials or your deployment secret store to create/update these protected files. Never put secret values in manifests, workflow JSON, Git, or command arguments.

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

Database must already exist. `apply` installs WordPress in DirectAdmin `public_html`, creates `wp-config.php`, installs required plugin/theme, and runs `wp core install`.

## Manual dry run

```bash
INSTALL_MODE=dry-run \
MANIFEST=/home/project/example.com/example.com.txt \
./scripts/website-install-from-manifest
```

## Apply

Only run from n8n after reviewing dry-run output:

```bash
INSTALL_MODE=apply \
MANIFEST=/home/project/example.com/example.com.txt \
WP_INSTALL_SSH_KEY_FILE=/run/secrets/wp-install-ssh-key \
WP_INSTALL_DB_PASSWORD_FILE=/run/secrets/wp-install-db-password \
WP_INSTALL_ADMIN_PASSWORD_FILE=/run/secrets/wp-install-admin-password \
./scripts/website-install-from-manifest
```

`apply` is destructive: it writes WordPress files and database state on target server. Backup/rollback remains operator responsibility.
