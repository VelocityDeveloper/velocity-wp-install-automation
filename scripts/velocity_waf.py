"""Velocity WAF bersama: rakit berkas ruleset + kirim perintah pasang/copot/status ke server lewat SSH.

Dipakai scripts/velocity-waf-pasang (CLI) dan installer_status.py (halaman Server > WAF). Setelan rakit
(crawler SEO/AI, rate limit, IP putih tambahan) disimpan di SETELAN_BERKAS dan berlaku untuk semua server.
Sidik = hash ruleset repo + setelan; server yang sidiknya beda dari sidik lokal berarti perlu diperbarui.
"""
import base64
import hashlib
import importlib.machinery
import importlib.util
import ipaddress
import json
import subprocess
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
SETELAN_BERKAS = Path('/var/lib/velocity/server-waf/setelan.json')
SETELAN_BAWAAN = {'seo': True, 'ai': True, 'perplexity': 'blokir', 'oai_maks': 30, 'xmlrpc': 10, 'login': 10, 'ip_putih': []}
DATA = ['bot-jahat.txt', 'bot-seo.txt', 'bot-ai.txt', 'bot-ai-pencarian.txt', 'klien-skrip.txt', 'ip-putih.txt', 'ip-ai-pencarian.txt']

REMOTE = r'''
import base64, glob, json, os, re, shutil, subprocess, time
P = json.loads(base64.b64decode(SANDI).decode())
DIR = '/etc/velocity-waf'
INC = '/etc/modsecurity.d/velocity-waf.conf'
ELOG = '/usr/local/lsws/logs/error.log'
# UA browser lengkap: UA polos 'Mozilla/5.0' pernah kena aturan 406 cPGuard. UA uji 'velocity-waf-uji' hanya ada di
# bot-jahat.txt Velocity WAF (bukan daftar cPGuard), jadi uji tidak memicu cPGuard/BFM selama keduanya jalan paralel.
UA_BIASA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 velocity-waf-cek'
out = {'langkah': []}
def jalan(cmd, batas=120):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=batas, shell=isinstance(cmd, str))
    return r.returncode, r.stdout
def baca(p):
    try:
        return open(p).read().strip()
    except (OSError, UnicodeDecodeError):
        return ''
def ngx_main():
    # nginx + libmodsecurity v3 (server non-DA, mis. atha): berkas aturan utama yang dipakai modsecurity_rules_file
    for f in ['/etc/nginx/nginx.conf'] + sorted(glob.glob('/etc/nginx/conf.d/*.conf')):
        m = re.search(r'^\s*modsecurity_rules_file\s+([^;\s]+)', baca(f), re.M)
        if m:
            return m.group(1)
NGX = None if os.path.isfile('/usr/local/lsws/bin/lswsctrl') else ngx_main()
BARIS_NGX = 'Include %s/velocity-waf.conf' % DIR
# Blok bertanda: modsecurity-main.conf atha memuat modsecurity.conf ber-SecRuleEngine DetectionOnly → tanpa On, deny tak jalan
BLOK_NGX = ['# >>> Velocity WAF (dashboard Velocity) — hapus blok ini untuk mencopot', 'SecRuleEngine On', BARIS_NGX, '# <<< Velocity WAF']
def inc_ada():
    return BARIS_NGX in baca(NGX).splitlines() if NGX else os.path.isfile(INC)
def inc_pasang():
    if NGX:
        with open(NGX, 'a') as f:
            f.write('\n' + '\n'.join(BLOK_NGX) + '\n')
        return
    with open(INC, 'w') as f:
        f.write('# Velocity WAF — dipasang scripts/velocity-waf-pasang (dashboard Velocity). Hapus berkas ini untuk mencopot.\nInclude %s/velocity-waf.conf\n' % DIR)
    os.chmod(INC, 0o644)
def inc_copot():
    if not NGX:
        os.remove(INC)
        return
    baris, di_blok = [], False
    for b in open(NGX).read().split('\n'):
        if b == BLOK_NGX[0]:
            di_blok = True
        elif di_blok and b == BLOK_NGX[-1]:
            di_blok = False
        elif not di_blok and b != BARIS_NGX:
            baris.append(b)
    with open(NGX + '.baru', 'w') as f:
        f.write('\n'.join(baris).rstrip('\n') + '\n')
    os.rename(NGX + '.baru', NGX)
def berkas_log():
    # ModSecurity nginx menulis ke error_log per vhost
    return sorted(set(glob.glob('/var/log/nginx/*error.log') + glob.glob('/var/log/nginx/*/*error.log'))) if NGX else [ELOG]
def ukuran_log():
    return {p: os.path.getsize(p) for p in berkas_log() if os.path.isfile(p)}
def log_baru(awal):
    teks = ''
    for p in berkas_log():
        try:
            with open(p, errors='replace') as f:
                a = awal.get(p, 0)
                f.seek(a if os.path.getsize(p) >= a else 0)
                teks += f.read()
        except OSError:
            pass
    return teks
def status():
    versi = baca(DIR + '/VERSI').split()
    cadangan = sorted(glob.glob(DIR + '.bak-*'))
    return {'terpasang': inc_ada(), 'berkas_ada': os.path.isfile(DIR + '/velocity-waf.conf'),
            'versi': versi[0] if versi else None, 'mode': versi[1] if len(versi) > 1 else None,
            'sidik': baca(DIR + '/SIDIK') or None,
            'diubah': int(os.path.getmtime(DIR + '/VERSI')) if os.path.isfile(DIR + '/VERSI') else None,
            'cpguard': os.path.isfile('/etc/modsecurity.d/cpguard_waf.conf') or os.path.isfile('/etc/nginx/cpguard_waf.conf'),
            'cpguard_aturan': len(glob.glob('/etc/cpguard/cpguard_modsec*.conf')),
            'lsws': os.path.isfile('/usr/local/lsws/bin/lswsctrl'), 'modsecurity_d': os.path.isdir('/etc/modsecurity.d'),
            'nginx': bool(NGX), 'cadangan': len(cadangan)}
def situs():
    # domain pertama yang punya docroot, untuk uji HTTP
    if NGX:
        for f in sorted(glob.glob('/etc/nginx/conf.d/*.conf')):
            t = baca(f)
            m = re.search(r'^\s*server_name\s+([^;\s]+)', t, re.M)
            if m and re.search(r'^\s*modsecurity\s+on', t, re.M):
                return m.group(1)
        return None
    for f in sorted(glob.glob('/usr/local/directadmin/data/users/*/domains.list')):
        for d in open(f).read().split():
            if d:
                return d
def ip_situs(domain):
    # IP publik domain (bukan 127.0.0.1: loopback ada di ip-putih.txt sehingga semua aturan dilewati)
    for f in glob.glob('/usr/local/directadmin/data/users/*/domains/%s.conf' % domain):
        for b in open(f, errors='replace'):
            if b.startswith('ip='):
                return b.strip()[3:]
    if NGX:
        m = re.search(r'\bsrc\s+(\S+)', jalan(['ip', '-4', 'route', 'get', '1.1.1.1'], 10)[1])
        if m:
            return m.group(1)
    return '127.0.0.1'
def http(domain, ua):
    # Query unik → tidak dijawab dari LSCache
    kode, o = jalan(['curl', '-sk', '-o', '/dev/null', '-w', '%{http_code}', '--max-time', '20', '-A', ua,
                     '--resolve', '%s:443:%s' % (domain, ip_situs(domain)), 'https://%s/?velocity-waf-cek=%d' % (domain, time.time())], 30)
    return o.strip()
def restart():
    if NGX:
        k, o = jalan('nginx -t && systemctl reload nginx', 60)
        time.sleep(2)
        return k, o.strip()[-300:]
    k, o = jalan(['/usr/local/lsws/bin/lswsctrl', 'restart'], 120)
    time.sleep(6)
    return k, o.strip()[-300:]
def galat_baru(ukuran_awal):
    teks = log_baru(ukuran_awal)
    # Baris rule terpicu ("ModSecurity: …" / "[MODSEC] mod_security rule … triggered!") bukan galat walau berlabel [error]
    return [b[:300] for b in teks.split('\n') if 'velocity-waf' in b.lower() and 'ModSecurity: ' not in b and 'triggered' not in b
            and re.search(r'fail|parse|invalid|unknown|syntax|cannot|could not', b, re.I)][:10]
aksi = P['aksi']
s = status()
if aksi == 'status' or not (s['lsws'] and s['modsecurity_d'] or s['nginx']):
    out.update(ok=aksi == 'status', status=s, error=None if aksi == 'status' else 'bukan_litespeed_modsecurity')
    print(json.dumps(out)); raise SystemExit
cadangan = None
if aksi == 'copot':
    if inc_ada():
        inc_copot()
    k, o = restart()
    out.update(ok=k == 0, status=status(), restart=o); print(json.dumps(out)); raise SystemExit
# --- pasang ---
if os.path.isdir(DIR):
    cadangan = DIR + '.bak-' + time.strftime('%Y%m%d%H%M%S')
    shutil.copytree(DIR, cadangan)
    out['langkah'].append('cadangan ' + cadangan)
os.makedirs(DIR, exist_ok=True)
os.chmod(DIR, 0o755)
for nama, isi in P['berkas'].items():
    jalur = os.path.join(DIR, os.path.basename(nama))
    with open(jalur + '.baru', 'w') as f:
        f.write(isi)
    os.chmod(jalur + '.baru', 0o644)
    os.rename(jalur + '.baru', jalur)
out['langkah'].append('%d berkas ditulis' % len(P['berkas']))
sudah = inc_ada()
if not sudah:
    inc_pasang()
domain = situs()
awal = ukuran_log()
sebelum = http(domain, UA_BIASA) if domain else None
k, o = restart()
out['langkah'].append('%s: %s' % ('nginx -t + reload' if NGX else 'lswsctrl restart', k))
if k != 0:
    out['restart'] = o
galat = galat_baru(awal)
sesudah = http(domain, UA_BIASA) if domain else None
uji = http(domain, 'velocity-waf-uji/1.0') if domain else None
time.sleep(1)
tercatat = 'Velocity WAF - Scanner/bot jahat' in log_baru(awal)
out.update(domain=domain, http_sebelum=sebelum, http_sesudah=sesudah, http_uji_sqlmap=uji, tercatat=tercatat, galat=galat)
rusak = k != 0 or galat or (sesudah or '000')[0] == '5' or sesudah == '000' and sebelum != '000'
harap_blokir = P['mode'] == 'blokir'
if not rusak and harap_blokir and uji != '429':
    rusak = True; out['alasan'] = 'mode blokir tetapi request uji tidak dijawab 429'
if not rusak and not harap_blokir and not tercatat:
    out['peringatan'] = 'request uji belum tercatat di error.log (bisa karena LSCache/situs pertama tidak di server ini) — cek halaman WAF'
if rusak:
    inc_copot() if not sudah else None
    if cadangan:
        shutil.rmtree(DIR); shutil.copytree(cadangan, DIR)
    k2, o2 = restart()
    out.update(ok=False, error='dikembalikan', restart_ulang=k2)
else:
    out.update(ok=True)
out['status'] = status()
print(json.dumps(out))
'''


def _build():
    loader = importlib.machinery.SourceFileLoader('velocity_waf_build', str(AKAR / 'scripts' / 'velocity-waf-build'))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def bersihkan_setelan(data):
    """Setelan dari form → bentuk baku. ValueError(kode) bila tidak sah."""
    s = dict(SETELAN_BAWAAN)
    if not isinstance(data, dict):
        raise ValueError('setelan_tidak_sah')
    for k in ('seo', 'ai'):
        if k in data:
            s[k] = bool(data[k])
    if 'perplexity' in data:
        if data['perplexity'] not in ('catat', 'blokir'):
            raise ValueError('setelan_tidak_sah')
        s['perplexity'] = data['perplexity']
    if 'oai_maks' in data:  # 0 = tanpa batas
        try:
            n = int(data['oai_maks'])
        except (TypeError, ValueError):
            raise ValueError('setelan_tidak_sah')
        if n != 0 and not 5 <= n <= 600:
            raise ValueError('setelan_tidak_sah')
        s['oai_maks'] = n
    for k in ('xmlrpc', 'login'):
        if k in data:
            try:
                n = int(data[k])
            except (TypeError, ValueError):
                raise ValueError('setelan_tidak_sah')
            if not 3 <= n <= 200:
                raise ValueError('setelan_tidak_sah')
            s[k] = n
    if 'ip_putih' in data:
        daftar = data['ip_putih'] if isinstance(data['ip_putih'], list) else []
        out = []
        for item in daftar[:200]:
            ip = str(item.get('ip') if isinstance(item, dict) else item).strip()
            ket = str(item.get('ket') or '')[:80] if isinstance(item, dict) else ''
            try:
                net = ipaddress.ip_network(ip, strict=False)
            except ValueError:
                raise ValueError('ip_tidak_sah')
            if net.prefixlen < (16 if net.version == 4 else 32):
                raise ValueError('cidr_terlalu_lebar')
            ip = str(net.network_address) if net.num_addresses == 1 else str(net)
            if ip not in [x['ip'] for x in out]:
                out.append({'ip': ip, 'ket': ket.replace('\n', ' ')})
        s['ip_putih'] = out
    return s


def baca_setelan():
    try:
        return bersihkan_setelan(json.loads(SETELAN_BERKAS.read_text()))
    except (OSError, ValueError):
        return dict(SETELAN_BAWAAN)


def simpan_setelan(s):
    SETELAN_BERKAS.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETELAN_BERKAS.with_suffix('.tmp')
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=1))
    tmp.replace(SETELAN_BERKAS)


def rakit_berkas(mode, setelan=None):
    """→ (berkas {nama: isi}, versi, sidik). Sidik tidak bergantung mode/tanggal, jadi bisa dibanding antar server."""
    s = setelan or baca_setelan()
    build = _build()
    teks, versi = build.rakit(mode, '/etc/velocity-waf', s['seo'], s['ai'], s['perplexity'], s['oai_maks'], s['xmlrpc'], s['login'])
    berkas = {'velocity-waf.conf': teks}
    for d in DATA:
        berkas[d] = (AKAR / 'waf' / d).read_text()
    if s['ip_putih']:
        berkas['ip-putih.txt'] = berkas['ip-putih.txt'].rstrip('\n') + '\n# Tambahan dari dashboard (Server > WAF > Setelan)\n' + \
            ''.join(f"{x['ip']}\n" for x in s['ip_putih'])
    sidik = sidik_lokal(versi, s)
    berkas['VERSI'] = f'{versi} {mode}\n'
    berkas['SIDIK'] = sidik + '\n'
    return berkas, versi, sidik


def sidik_lokal(versi=None, setelan=None):
    s = setelan or baca_setelan()
    if versi is None:
        versi = versi_lokal()
    tanpa_ket = {**s, 'ip_putih': [x['ip'] for x in s['ip_putih']]}
    return hashlib.sha1(f"{versi}{json.dumps(tanpa_ket, sort_keys=True)}".encode()).hexdigest()[:10]


def versi_lokal():
    teks = (AKAR / 'waf' / 'velocity-waf.conf.in').read_text()
    return hashlib.sha1((teks + ''.join((AKAR / 'waf' / d).read_text() for d in DATA)).encode()).hexdigest()[:10]


def jalankan(srv, key, perintah, batas=400):
    """Kirim REMOTE + perintah ke server. perintah: {'aksi': status|copot|pasang, 'mode', 'berkas'}."""
    sandi = base64.b64encode(json.dumps(perintah).encode()).decode()
    cmd = ['ssh', '-i', str(key), '-p', str(srv['port']), '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
           '-o', 'StrictHostKeyChecking=accept-new', f"{srv['user']}@{srv['host']}",
           'command -v python3 >/dev/null && exec python3 - || exec /usr/libexec/platform-python -']
    try:
        r = subprocess.run(cmd, input=f"SANDI = '{sandi}'\n{REMOTE}", capture_output=True, text=True, timeout=batas)
    except subprocess.TimeoutExpired:
        return {'ok': False, 'error': 'timeout'}
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        pesan = (r.stderr or r.stdout or '').strip().splitlines()
        return {'ok': False, 'error': (pesan[-1] if pesan else f'exit_{r.returncode}')[:300]}


def daftar_aturan():
    """Aturan dari waf/velocity-waf.conf.in untuk ditampilkan (id, pesan, tag, aksi) + isi berkas data."""
    import re
    teks = (AKAR / 'waf' / 'velocity-waf.conf.in').read_text()
    aturan, bagian = [], ''
    for blok in re.split(r'\n(?=\S)', teks):
        m = re.match(r'# ---- (.+?) ----', blok)
        if m:
            bagian = m.group(1)
            continue
        idm = re.search(r'"id:(\d+)', blok)
        msg = re.search(r"msg:'([^']+)'", blok)
        if not idm or not msg:
            continue
        aksi = 'catat'
        for token, nilai in (('@AKSI429@', '429'), ('@AKSI403@', '403'), ('@AKSI406@', '406'), ('@AKSIPPLX@', 'perplexity')):
            if token in blok:
                aksi = nilai
        opsional = next((k for awal, k in (('@SEO@', 'seo'), ('@AI@', 'ai'), ('@OAI@', 'oai_maks')) if blok.startswith(awal)), None)
        aturan.append({'id': idm.group(1), 'pesan': msg.group(1).replace('Velocity WAF - ', ''), 'bagian': bagian,
                       'tag': [t for t in re.findall(r"tag:'([^']+)'", blok) if t != 'velocity-waf'], 'aksi': aksi, 'opsional': opsional})
    data = {}
    for d in DATA:
        baris = (AKAR / 'waf' / d).read_text().splitlines()
        data[d] = {'ket': ' '.join(b.lstrip('# ') for b in baris if b.startswith('#')),
                   'isi': [b.strip() for b in baris if b.strip() and not b.startswith('#')]}
    return {'aturan': aturan, 'data': data}
