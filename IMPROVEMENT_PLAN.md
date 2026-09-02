# Velocity WP Install Automation — Improvement Plan

> Status: PLAN (belum eksekusi) — minta approval sebelum masuk Fase 1
> Tanggal: 2026-09-02
> Scope audit: `scripts/website-install-from-manifest`, `workflows/website-install-workflow.json`, `services/installer_status.py`, `web/installer/index.html`, `README.md`

## Ringkasan Temuan

| #   | Komponen                        | Severity     | Masalah                                                                                          |
| --- | ------------------------------- | ------------ | ------------------------------------------------------------------------------------------------ | ---------------------------------- |
| 1   | `website-install-from-manifest` | **CRITICAL** | `wp plugin/theme install <git-url>` pasti gagal — WP-CLI tidak support git URL                   |
| 2   | `website-install-from-manifest` | **CRITICAL** | `WP_INSTALL_GITHUB_TOKEN_FILE` didefinisikan di README tapi tidak pernah dipakai di script       |
| 3   | `website-install-from-manifest` | **CRITICAL** | Tidak ada backup sebelum `wp core download --force` — install timpa `public_html` tanpa rollback |
| 4   | `website-install-from-manifest` | HIGH         | `--skip-check` sembunyikan error koneksi DB                                                      |
| 5   | `website-install-from-manifest` | HIGH         | Secret via `WP_DB_PASSWORD=%q` + `printf ...                                                     | ssh bash -s`bocor di`ps`/`history` |
| 6   | `website-install-from-manifest` | HIGH         | Tidak ada file lock / idempotency — 2x `apply` paralel corrupt DB/files                          |
| 7   | `website-install-from-manifest` | HIGH         | Validasi lemah: `da_user`, `db_name`, `db_user`, `ssh_user`, `admin_email` tidak divalidasi      |
| 8   | `website-install-from-manifest` | MEDIUM       | `StrictHostKeyChecking=accept-new` tanpa known_hosts pinning                                     |
| 9   | `website-install-from-manifest` | MEDIUM       | `read_secret` dan `cfg[]` tidak cek permission 0400 / trim value                                 |
| 10  | `website-install-workflow.json` | HIGH         | Hanya 1 node `dry-run`, tidak ada node `apply`, branching, error handling, notifikasi            |
| 11  | `website-install-workflow.json` | HIGH         | Interpolasi `{{$json.domain}}` tanpa escaping — injection via nama domain                        |
| 12  | `installer_status.py`           | HIGH         | Frontend fetch `/api/servers` tapi backend tidak punya endpoint itu — selalu gagal               |
| 13  | `installer_status.py`           | HIGH         | `systemctl list-timers` + `crontab -l` dijalankan tiap request — DoS + bocor crontab             |
| 14  | `installer_status.py`           | MEDIUM       | `self.path != '/api/installer'` gagal untuk `?query` — harus pakai `urlparse`                    |
| 15  | `installer_status.py`           | MEDIUM       | Tidak ada auth / rate-limit — listing `/home/project` terbuka ke localhost tanpa kontrol         |
| 16  | `index.html`                    | HIGH         | Tombol `[ install ]` hanya tambah class `selected` — UX menipu, tidak trigger apa-apa            |
| 17  | `index.html`                    | MEDIUM       | Poll 10s tanpa backoff/pause saat tab hidden                                                     |
| 18  | Semua                           | MEDIUM       | Tidak ada logging terstruktur, tidak ada health check, tidak ada backup/rollback docs            |

## Plan — 3 Fase Berurutan

### FASE 1 — Safety & Correctness (WAJIB, prioritas 1)

> Tujuan: installer benar-benar bisa install dan tidak merusak site
> Estimasi effort: terbesar, harus dikerjakan berurutan

**1.1 `scripts/website-install-from-manifest`**

- [ ] Ganti `wp plugin/theme install <git-url>` → `git clone` ke tmp + `wp plugin install <path> --activate` (atau `wp plugin activate` setelah copy)
- [ ] Implementasi `WP_INSTALL_GITHUB_TOKEN_FILE`: jika ada, gunakan `git -c credential.helper` / header `Authorization` untuk private repo
- [ ] Hapus `--skip-check` di `wp config create` — fail fast jika DB tidak bisa konek
- [ ] Tambah validasi regex untuk `da_user`, `db_name`, `db_user`, `ssh_user`, `admin_email`, `site_title`
- [ ] Trim & sanitize `value` dari manifest (`value=$(echo "$value" | sed 's/^[ \t]*//;s/[ \t]*$//')`)
- [ ] Tambah `flock -n /tmp/velocity-install-<domain>.lock` untuk cegah paralel `apply`
- [ ] Cek `command -v wp`, cek `public_html` exists, cek `wp core is-installed` untuk idempotency guard
- [ ] Backup `public_html` ke `/home/<da_user>/backup/pre-install-<timestamp>.tar.gz` sebelum `wp core download --force`
- [ ] Cek permission secret files harus `0400` atau `0600` dan owned root
- [ ] Ganti inject secret via `env -0` / file descriptor atau `WP_CLI` env passthrough via `SendEnv`, bukan `%q` di command line

**1.2 Secrets hardening**

- [ ] Dokumentasikan rotation & audit secrets di README

**1.3 `workflows/website-install-workflow.json`**

- [ ] Tambah node `IF` (dry-run OK? → apply, else → notify error)
- [ ] Tambah node `Execute Command` untuk `apply` terpisah dari `dry-run`
- [ ] Tambah `Error Workflow` + notifikasi (Slack/Email)
- [ ] Escape domain via wrapper script `scripts/n8n-run-install.sh` yang validasi input, bukan inline `{{$json.domain}}`
- [ ] Aktifkan `retry` + `timeout` di Execute Command, set `active: true` setelah review

**Exit criteria Fase 1:** `dry-run` + `apply` berhasil install WP + velocity-addons + velocity-theme di server staging tanpa error, 2x apply tidak corrupt.

---

### FASE 2 — Reliability & Observability (prioritas 2)

**2.1 `services/installer_status.py`**

- [ ] Tambah endpoint `/api/servers` (baca dari `config/servers.json` atau env `INSTALLER_SERVERS`)
- [ ] Tambah `/health` endpoint
- [ ] Cache `cronjobs()` 30 detik (`functools.lru_cache` + TTL) — jangan run tiap request
- [ ] Jangan bocorkan raw crontab — hanya tampilkan jumlah + next run, atau butuh auth
- [ ] Fix `self.path` parsing pakai `urllib.parse.urlparse(self.path).path`
- [ ] Tambah auth via `Authorization: Bearer <token>` (token dari file env) + rate-limit sederhana (e.g. 10 req/s per IP)
- [ ] Tambah `Cache-Control: no-store` tetap, tapi tambah `X-Content-Type-Options`

**2.2 Logging & Monitoring**

- [ ] Script tulis JSON log ke `/var/log/velocity-install/<domain>-<timestamp>.json`
- [ ] n8n execution history + simpan output dry-run sebagai artifact
- [ ] Tambah `services/installer_status.py` log ke stdout dengan format JSON

**2.3 `web/installer/index.html`**

- [ ] Fix fetch `/api/servers` — handle empty/error dengan pesan jelas
- [ ] Tampilkan detail error manifest (bukan hanya READY/MISSING) — parse JSON error dari script
- [ ] Tambah preview output `dry-run` sebelum tombol install aktif
- [ ] Tambah modal konfirmasi "Yakin apply ke <domain> di <server>? Ini destruktif."
- [ ] Pause polling saat `document.hidden`

**Exit criteria Fase 2:** status page tampil server list benar, tidak bocor crontab, ada log terstruktur.

---

### FASE 3 — Ops & UX Lanjut (prioritas 3)

- [ ] Idempotency penuh: `wp core is-installed` → skip `install` jika sudah, update jika perlu
- [ ] Cek disk space & PHP version sebelum install (`df -h`, `php -v`)
- [ ] Backup/rollback otomatis + dokumentasi operator
- [ ] Antrian install — queue per domain (n8n Queue Mode atau file lock global)
- [ ] Rate-limit apply per domain (max 1 per 5 menit)
- [ ] E2E test: buat domain dummy di staging, jalankan full flow dry-run → apply → verify

## Urutan Eksekusi yang Direkomendasikan

```
FASE 1 (wajib) → review & test di staging → FASE 2 → FASE 3
```

Tidak disarankan loncat ke Fase 2/3 sebelum Fase 1 selesai karena bug CRITICAL di 1.1 akan membuat Fase 2/3 tidak berguna (install tetap gagal).

## Keputusan yang Butuh Approval Kamu

1. **Setuju Fase 1 dulu?** (rekomendasi: YA)
2. **Private repo velocity-addons/theme** — butuh token GitHub? Jika YA, kita implement 1.1 token helper. Jika TIDAK (public), kita tetap clone tanpa token.
3. **Workflow apply** — mau auto-apply setelah dry-run OK, atau tetap manual trigger terpisah?
4. **Auth untuk installer_status.py** — pakai Bearer token atau cukup localhost + reverse proxy auth?

## Next Step

Balas dengan:

- `setuju fase 1` → saya langsung eksekusi
- atau pilih subset task yang mau didahulukan
