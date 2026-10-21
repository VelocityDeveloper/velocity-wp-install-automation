"""Status Nextcloud di PC Backup (https://cloud.velocity.ai.id) untuk dashboard, lewat `ssh pc-backup`.

Nextcloud 35 tanpa container: kode /var/www/nextcloud, data dataset ZFS Backup/nextcloud (/srv/backup/nextcloud/data),
nginx 127.0.0.1:8250 di belakang tunnel cloudflared. Hanya membaca (occ status/user/setupchecks, zfs, systemctl).
`occ setupchecks` butuh ±25 dtk, jadi data lama dikirim bertanda 'menyegarkan' sementara SSH berjalan di latar.
"""
import json
import subprocess
import threading
import time

from pc_backup import HOST

URL = 'https://cloud.velocity.ai.id'
CACHE_DETIK = 300

# Dijalankan di PC Backup sebagai root; occ dipanggil sebagai www-data. Keluaran satu objek JSON.
SKRIP = r'''
import json, os, subprocess, time
NC = '/var/www/nextcloud'
DS = 'Backup/nextcloud'
DUMP = '/srv/backup/nextcloud/db-dump/nextcloud.sql.gz'
def sh(*a, t=60):
    try:
        return subprocess.run(a, capture_output=True, text=True, timeout=t, cwd='/').stdout
    except Exception:
        return ''
def occ(*a, t=60):
    return sh('sudo', '-u', 'www-data', 'php', NC + '/occ', '--no-warnings', *a, t=t)
def occ_json(*a, t=60):
    try:
        return json.loads(occ(*a, '--output=json', t=t) or 'null')
    except ValueError:
        return None
out = {'waktu': int(time.time())}
out['status'] = occ_json('status') or {}
out['layanan'] = {n: sh('systemctl', 'is-active', n).strip() for n in
                  ('nginx', 'php8.3-fpm', 'redis-server', 'mariadb', 'cloudflared', 'nextcloud-cron.timer')}
c = occ('config:app:get', 'core', 'lastcron').strip()
out['cron_terakhir'] = int(c) if c.isdigit() else None
z = sh('zfs', 'list', '-Hp', '-o', 'used,avail,quota,usedbysnapshots', DS).split()
out['dataset'] = dict(zip(('terpakai', 'sisa', 'kuota', 'snapshot'), map(int, z))) if len(z) == 4 else None
snap = [b.split('\t') for b in sh('zfs', 'list', '-Hp', '-t', 'snapshot', '-o', 'name,creation', '-s', 'creation', DS).splitlines() if '\t' in b]
out['snapshot'] = {'jumlah': len(snap), 'terbaru': int(snap[-1][1]) if snap else None}
try:
    st = os.stat(DUMP)
    out['dump'] = {'waktu': int(st.st_mtime), 'ukuran': st.st_size}
except OSError:
    out['dump'] = None
# shortcut: user:info dipanggil per user (±1 dtk/user), ganti ke kueri DB bila user sudah puluhan
out['pengguna'] = []
for uid, u in (occ_json('user:list', '--info') or {}).items():
    s = (occ_json('user:info', uid) or {}).get('storage') or {}
    out['pengguna'].append({'id': uid, 'nama': u.get('display_name'), 'email': u.get('email'), 'aktif': u.get('enabled'),
                            'grup': u.get('groups', []), 'kuota': u.get('quota'), 'terpakai': s.get('used'),
                            'total': s.get('total') if s.get('quota', -3) >= 0 else None, 'terakhir': u.get('last_seen')})
apps = occ_json('app:list') or {}
out['aplikasi'] = {'aktif': len(apps.get('enabled', {})), 'mati': len(apps.get('disabled', {}))}
out['pembaruan'] = {'inti': occ('update:check').strip(), 'aplikasi': occ('app:update', '--showonly').strip()}
out['cek'] = []
for kat, v in (occ_json('setupchecks', t=120) or {}).items():
    for x in v.values():
        if x.get('severity') not in ('success', None):
            out['cek'].append({'kategori': kat, 'tingkat': x['severity'], 'nama': x.get('name'), 'keterangan': x.get('description')})
print(json.dumps(out))
'''

_kunci = threading.Lock()
_cache = {'waktu': 0, 'data': None, 'galat': None, 'jalan': False}


def _ambil():
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=6', HOST, 'python3', '-'],
                       input=SKRIP, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError((r.stderr.strip().splitlines() or ['ssh gagal'])[-1])
    return json.loads(r.stdout)


def _segarkan():
    try:
        data, galat = _ambil(), None
    except Exception as e:  # PC Backup mati/Tailscale putus: data lama tetap dikirim bersama galat
        data, galat = None, str(e)[:300]
    with _kunci:
        if data:
            _cache['data'] = data
        _cache.update(galat=galat, waktu=time.time(), jalan=False)


def status(segar=False):
    with _kunci:
        basi = segar or time.time() - _cache['waktu'] > CACHE_DETIK
        if basi and not _cache['jalan']:
            _cache['jalan'] = True
            threading.Thread(target=_segarkan, daemon=True).start()
        tunggu = _cache['data'] is None and _cache['galat'] is None
    if tunggu:  # belum pernah ada data: tunggu SSH pertama selesai
        while _cache['jalan']:
            time.sleep(0.5)
    with _kunci:
        return {'url': URL, 'nc': _cache['data'], 'galat': _cache['galat'], 'diperbarui': int(_cache['waktu']),
                'menyegarkan': _cache['jalan']}
