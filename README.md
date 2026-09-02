# Velocity WordPress install automation

Manifest-driven installer helper for n8n and DirectAdmin workflows.

## Current behavior

- Reads key/value manifest data.
- Validates manifest path, domain, keys, and target host.
- Defaults to `dry-run`.
- `apply` remains blocked until installer template is configured.

## Files

- `scripts/website-install-from-manifest` — shell validator.
- `workflows/website-install-workflow.json` — n8n workflow export.

## Dry run

```bash
INSTALL_MODE=dry-run MANIFEST=/home/project/example.txt \
  ./scripts/website-install-from-manifest
```

Do not commit credentials, server passwords, SSH keys, or token files.
