# -*- coding: utf-8 -*-
"""Velocity BFM — pengganti Brute Force Monitor cPGuard (dijalankan di server lewat `ssh ... python3 -`).

BFM cPGuard ternyata ±99% bukan login gagal, melainkan hit WAF (bot jahat, crawler, probe) yang diubah jadi
blokir CSF. Penggantinya memakai LFD bawaan CSF: blok aturan kustom di /etc/csf/regex.custom.pm membaca error log
LiteSpeed (CUSTOMn_LOG) dan memblokir IP yang berulang kali DITOLAK Velocity WAF ("ModSecurity: Access denied" +
tag velocity-waf). Selama Velocity WAF masih mode deteksi (baris "Warning"), blok ini tidak memblokir apa pun.

Dipakai halaman Server > Brute Force (installer_status.py). Pemanggil menambahkan `jalankan(<base64 JSON>)`.
Harus tetap jalan di Python 3.6. Aksi:
- status (baca): setelan CSF/LFD terkait, kapasitas csf.deny & sumbernya, status blok Velocity BFM,
  BFM cPGuard 24 jam (bruteforce.db) sebagai pembanding, dan simulasi 24 jam dari log Velocity WAF.
- pasang: tulis/perbarui blok (salinan cadangan dulu), set CUSTOMn_LOG, perl -c, csf -r + restart lfd;
  lfd gagal → semua dikembalikan.
- copot: hapus blok, kembalikan CUSTOMn_LOG, csf -r + restart lfd.
"""
import base64
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime

CSF_CONF = '/etc/csf/csf.conf'
CSF_DENY = '/etc/csf/csf.deny'
TEMPBAN = '/var/lib/csf/csf.tempban'
REGEX = '/etc/csf/regex.custom.pm'
LFD_LOG = '/var/log/lfd.log'
WAF_LOG = '/usr/local/lsws/logs/error.log'
CPG_BFM = '/opt/cpguard/app/data/bruteforce.db'
LOG_KOSONG = '/var/log/customlog'
MULAI = '# VELOCITY-BFM MULAI'
SELESAI = '# VELOCITY-BFM SELESAI'
BATAS_EDIT = '# Do not edit beyond this point'
KUNCI_CSF = ('DENY_IP_LIMIT', 'DENY_TEMP_IP_LIMIT', 'LF_IPSET', 'LF_TRIGGER', 'LF_SELECT', 'LF_INTERVAL', 'LF_PERMBLOCK',
             'LF_PERMBLOCK_COUNT', 'LF_PERMBLOCK_INTERVAL', 'LF_SSHD', 'LF_DIRECTADMIN', 'LF_FTPD', 'LF_SMTPAUTH',
             'LF_POP3D', 'LF_IMAPD', 'LF_MODSEC', 'MODSEC_LOG', 'TESTING')
RE_BARIS_WAF = re.compile(r'^\[(\w{3} \w{3} +\d+ [\d:.]+ \d{4})\] \[(?:\S*:)?error\] \[client (\S+)\] ModSecurity: (Access denied|Warning)'
                          r'.*?\[id "(77\d{5})"\]')
BULAN = {b: i + 1 for i, b in enumerate(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'))}


def baca(p, bawaan=''):
    try:
        with open(p, errors='replace') as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return bawaan


def nilai_csf(teks, kunci):
    m = re.search(r'^%s\s*=\s*"([^"]*)"' % re.escape(kunci), teks, re.M)
    return m.group(1) if m else None


def jalan(cmd, batas=120):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=batas)
    return r.returncode, r.stdout


# Probe yang tak pernah dilakukan pengunjung asli (.env/.git, wp-config, dump/backup, PHP tersembunyi, null byte,
# traversal, bot AI palsu, xmlrpc system.multicall) → kelompok 'berat' (bawaan blokir permanen). Harus sama dengan RE_BERAT di blok Perl.
BERAT = ('7700201', '7700202', '7700203', '7700211', '7700301', '7700302', '7700106', '7700505')
RE_BERAT = '/^(%s)$/' % '|'.join(BERAT)


def kelompok(rid):
    """id aturan Velocity WAF → kunci aturan BFM (harus sama dengan blok Perl)."""
    if rid in BERAT:
        return 'berat'
    if rid.startswith('77005'):
        return 'login'
    if rid == '7700102':
        return 'crawler'
    if rid == '7700103':
        return 'ai'
    if rid == '7700104':
        return 'pencarian'
    if rid == '7700101':
        return 'bot'
    return 'eksploit'


def blok_perl(aturan, slot, sidik):
    """aturan: {kunci: {'aktif', 'ambang', 'durasi'}} → teks blok untuk regex.custom.pm (durasi 1 = permanen di CSF)."""
    def ret(k, teks):
        a = aturan[k]
        return 'return ("%s (id:$id) dari", $ip, "vwaf%s", "%d", "", "%d", "0")' % (teks, k, int(a['ambang']), int(a['durasi']))
    cabang = []
    for k, cocok, teks in (('login', "$id =~ /^77005/", 'Velocity WAF brute force login'),
                           ('crawler', "$id eq '7700102'", 'Velocity WAF crawler SEO'),
                           ('ai', "$id eq '7700103'", 'Velocity WAF crawler AI'),
                           ('pencarian', "$id eq '7700104'", 'Velocity WAF bot AI pencarian'),
                           ('bot', "$id eq '7700101'", 'Velocity WAF bot jahat'),
                           ('berat', '$id =~ ' + RE_BERAT, 'Velocity WAF eksploit berat')):
        if k not in aturan:  # setelan lama tanpa kelompok ini → ikut aturan eksploit
            continue
        cabang.append('\t\tif (%s) {%s}' % (cocok, ret(k, teks) if aturan[k]['aktif'] else 'return 0'))
    akhir = ret('eksploit', 'Velocity WAF eksploit/probe') if aturan['eksploit']['aktif'] else 'return 0'
    return '\n'.join([
        '%s sidik=%s slot=%s' % (MULAI, sidik, slot),
        '# Dikelola dashboard Velocity (Server > Brute Force). Jangan disunting manual: diganti saat Perbarui.',
        '# Memblokir IP yang berulang kali DITOLAK Velocity WAF (mode blokir); baris "Warning" (mode deteksi) diabaikan.',
        '\tif (($globlogs{%s}{$lgfile}) and ($line =~ /^\\[[^\\]]+\\] \\[(?:\\S*:)?error\\] \\[client (\\S+)\\] ModSecurity: Access denied with code \\S+ .*?\\[id "(77\\d{5})"\\].*?\\[tag "velocity-waf"\\]/)) {' % slot,
        '\t\tmy ($ip, $id) = ($1, $2);',
        '\t\t$ip =~ s/^::ffff://;',
        '\t\treturn 0 if $id =~ /^(?:77007\\d\\d|7700107|7700215)$/;',
    ] + cabang + ['\t\t' + akhir, '\t}', SELESAI])


def status_blok(teks):
    m = re.search(r'^%s sidik=(\S+) slot=(\S+)' % re.escape(MULAI), teks, re.M)
    return {'terpasang': bool(m), 'sidik': m.group(1) if m else None, 'slot': m.group(2) if m else None}


def berkas_log_24j(sejak):
    out = []
    for p in sorted(glob.glob(WAF_LOG + '*'), key=lambda x: os.path.getmtime(x), reverse=True):
        if p.endswith('.gz'):
            continue
        try:
            if os.path.getmtime(p) < sejak:
                continue
        except OSError:
            continue
        out.append(p)
    return out[:4]


def waktu_log(teks):
    # "Tue Oct 13 18:29:16.537397 2026"
    try:
        _, b, h, jam, th = teks.split()
        jj, mm, dd = jam.split('.')[0].split(':')
        return time.mktime((int(th), BULAN[b], int(h), int(jj), int(mm), int(dd), 0, 0, -1))
    except (ValueError, KeyError):
        return 0


def simulasi(aturan, interval):
    """Dari log Velocity WAF 24 jam: per aturan BFM, berapa IP yang akan diblokir (≥ ambang dalam jendela interval)."""
    sejak = time.time() - 86400
    per = {}  # kunci → ip → [waktu]
    mode = {'Access denied': 0, 'Warning': 0}
    for p in berkas_log_24j(sejak):
        try:
            f = open(p, 'rb')
        except OSError:
            continue
        with f:
            for b in f:
                if b'velocity-waf' not in b or b'ModSecurity: ' not in b:
                    continue
                m = RE_BARIS_WAF.match(b.decode('utf-8', 'replace'))
                if not m:
                    continue
                t = waktu_log(m.group(1))
                if t < sejak:
                    continue
                mode[m.group(3)] += 1
                rid = m.group(4)
                if rid in ('7700105', '7700107', '7700215') or rid.startswith('77006') or rid.startswith('77007'):
                    continue  # 77006 hanya dicatat; 77007 judi: Googlebot ikut mengakses link spam; 7700107 Meta: IP dipakai pratinjau FB/WA; 7700215 page/N artikel: IP residensial
                per.setdefault(kelompok(rid), {}).setdefault(m.group(2), []).append(t)
    hasil = {}
    for k, a in aturan.items():
        ips = per.get(k, {})
        blokir = []
        for ip, ts in ips.items():
            ts.sort()
            j, puncak = 0, 0
            for i in range(len(ts)):
                while ts[i] - ts[j] > interval:
                    j += 1
                puncak = max(puncak, i - j + 1)
            if puncak >= int(a['ambang']):
                blokir.append([ip, len(ts)])
        blokir.sort(key=lambda x: -x[1])
        hasil[k] = {'hit': sum(len(v) for v in ips.values()), 'ip': len(ips), 'blokir': len(blokir) if a['aktif'] else 0,
                    'contoh': blokir[:10]}
    return {'aturan': hasil, 'baris': mode}


def cpguard_24j():
    if not os.path.isfile(CPG_BFM):
        return None
    try:
        c = sqlite3.connect('file:%s?mode=ro' % CPG_BFM, uri=True, timeout=5)
        sejak = datetime.fromtimestamp(time.time() - 86400).strftime('%Y-%m-%d %H:%M:%S')
        q = lambda s: c.execute(s, (sejak,)).fetchall()
        out = {'hit': q('select count(*) from bruteforce_logs where time > ?')[0][0],
               'ip': q('select count(distinct ip) from bruteforce_logs where time > ?')[0][0],
               'alasan': q('select reason, count(*) from bruteforce_logs where time > ? group by 1 order by 2 desc limit 8')}
        c.close()
        return out
    except sqlite3.Error as e:
        return {'error': str(e)[:200]}


def sumber_deny():
    hit = {'directadmin': 0, 'cpguard': 0, 'lfd': 0, 'velocity': 0, 'dashboard': 0, 'lain': 0}
    total = 0
    for b in baca(CSF_DENY).splitlines():
        b = b.strip()
        if not b or b.startswith('#'):
            continue
        total += 1
        if '# BFM:' in b:  # Brute Force Monitor DirectAdmin (bukan cPGuard)
            hit['directadmin'] += 1
        elif 'cPGuard' in b:
            hit['cpguard'] += 1
        elif 'vwaf' in b or 'Velocity WAF' in b:
            hit['velocity'] += 1
        elif 'lfd:' in b:
            hit['lfd'] += 1
        elif 'velocity:' in b:
            hit['dashboard'] += 1
        else:
            hit['lain'] += 1
    tempban = len([b for b in baca(TEMPBAN).splitlines() if b.strip()])
    return {'total': total, 'sumber': hit, 'tempban': tempban}


def mode_waf():
    """Mode Velocity WAF di server ini (deteksi/blokir) atau None bila tidak terpasang."""
    if not os.path.isfile('/etc/modsecurity.d/velocity-waf.conf'):
        return None
    v = baca('/etc/velocity-waf/VERSI').split()
    return v[1] if len(v) > 1 else 'terpasang'


def status(p):
    conf = baca(CSF_CONF)
    if not conf:
        return {'ok': False, 'error': 'csf_tidak_ada'}
    csf = {k: nilai_csf(conf, k) for k in KUNCI_CSF}
    regex = baca(os.path.realpath(REGEX))
    blok = status_blok(regex)
    slot_ok = None
    if blok['slot']:
        slot_ok = nilai_csf(conf, blok['slot']) == WAF_LOG
    interval = int(csf.get('LF_INTERVAL') or 3600)
    out = {'ok': True, 'csf': csf, 'deny': sumber_deny(), 'blok': dict(blok, slot_ok=slot_ok),
           'lfd_aktif': jalan(['systemctl', 'is-active', 'lfd'], 15)[1].strip() == 'active',
           'waf_log': os.path.isfile(WAF_LOG), 'cpguard': cpguard_24j(),
           'velocity_waf': mode_waf()}
    if p.get('aturan'):
        out['simulasi'] = simulasi(p['aturan'], interval)
    return out


def pilih_slot(conf, blok):
    if blok['slot'] and nilai_csf(conf, blok['slot']) in (WAF_LOG, LOG_KOSONG):
        return blok['slot']
    for i in range(1, 10):
        k = 'CUSTOM%d_LOG' % i
        if nilai_csf(conf, k) == WAF_LOG:
            return k
    for i in range(1, 10):
        k = 'CUSTOM%d_LOG' % i
        if nilai_csf(conf, k) == LOG_KOSONG:
            return k
    return None


def set_csf(conf, kunci, nilai):
    return re.sub(r'^(%s\s*=\s*)"[^"]*"' % re.escape(kunci), lambda m: '%s"%s"' % (m.group(1), nilai), conf, count=1, flags=re.M)


def buang_blok(teks):
    return re.sub(r'\n?%s.*?%s\n?' % (re.escape(MULAI), re.escape(SELESAI)), '\n', teks, flags=re.S)


def muat_ulang(lfd_log_awal):
    k1, o1 = jalan(['csf', '-r'], 180)
    k2, o2 = jalan(['systemctl', 'restart', 'lfd'], 120)
    time.sleep(6)
    aktif = jalan(['systemctl', 'is-active', 'lfd'], 15)[1].strip() == 'active'
    teks = ''
    try:
        with open(LFD_LOG, errors='replace') as f:
            f.seek(lfd_log_awal if os.path.getsize(LFD_LOG) >= lfd_log_awal else 0)
            teks = f.read()
    except OSError:
        pass
    galat = [b[:300] for b in teks.splitlines() if re.search(r'\*Error\*|regex\.custom|syntax error|Global symbol', b, re.I)][:8]
    return {'ok': k1 == 0 and k2 == 0 and aktif and not galat, 'csf_r': k1, 'lfd': aktif, 'galat': galat,
            'keluaran': (o1 + o2).strip()[-400:]}


def ubah(p, pasang):
    regex_asli = os.path.realpath(REGEX)
    conf = baca(CSF_CONF)
    regex = baca(regex_asli)
    if not conf or not regex:
        return {'ok': False, 'error': 'csf_tidak_ada'}
    if BATAS_EDIT not in regex:
        return {'ok': False, 'error': 'regex_custom_tidak_dikenal'}
    blok = status_blok(regex)
    waktu = time.strftime('%Y%m%d%H%M%S')
    cad_conf = CSF_CONF + '.velocity-' + waktu
    cad_regex = regex_asli + '.velocity-' + waktu
    shutil.copy2(CSF_CONF, cad_conf)
    shutil.copy2(regex_asli, cad_regex)
    regex_baru = buang_blok(regex)
    conf_baru = conf
    if pasang:
        slot = pilih_slot(conf, blok)
        if not slot:
            return {'ok': False, 'error': 'slot_custom_log_penuh'}
        teks_blok = blok_perl(p['aturan'], slot, p['sidik'])
        i = regex_baru.index(BATAS_EDIT)
        # Sisipkan tepat sebelum baris "# Do not edit beyond this point" (di dalam sub custom_line, sebelum return 0)
        awal_baris = regex_baru.rfind('\n', 0, regex_baru.rfind('\n', 0, i)) + 1
        regex_baru = regex_baru[:awal_baris] + teks_blok + '\n' + regex_baru[awal_baris:]
        conf_baru = set_csf(conf_baru, slot, WAF_LOG)
    elif blok['slot'] and nilai_csf(conf, blok['slot']) == WAF_LOG:
        conf_baru = set_csf(conf_baru, blok['slot'], LOG_KOSONG)
    for jalur, isi in ((regex_asli, regex_baru), (CSF_CONF, conf_baru)):
        with open(jalur + '.baru', 'w') as f:
            f.write(isi)
        shutil.copymode(jalur, jalur + '.baru')
        os.rename(jalur + '.baru', jalur)
    k, o = jalan(['perl', '-c', regex_asli], 30)
    awal = os.path.getsize(LFD_LOG) if os.path.isfile(LFD_LOG) else 0
    hasil = muat_ulang(awal) if 'syntax OK' in o else {'ok': False, 'galat': [o.strip()[-300:]]}
    if not hasil['ok']:
        shutil.copy2(cad_conf, CSF_CONF)
        shutil.copy2(cad_regex, regex_asli)
        ulang = muat_ulang(os.path.getsize(LFD_LOG) if os.path.isfile(LFD_LOG) else 0)
        return {'ok': False, 'error': 'dikembalikan', 'hasil': hasil, 'lfd_sesudah_kembali': ulang['lfd'],
                'cadangan': [cad_conf, cad_regex]}
    return {'ok': True, 'hasil': hasil, 'cadangan': [cad_conf, cad_regex], 'blok': status_blok(baca(regex_asli))}


AKSI = {'status': status, 'pasang': lambda p: ubah(p, True), 'copot': lambda p: ubah(p, False)}


def jalankan(kode):
    p = json.loads(base64.b64decode(kode).decode())
    fungsi = AKSI.get(p.get('aksi'))
    if not fungsi:
        hasil = {'ok': False, 'error': 'aksi_tidak_dikenal'}
    else:
        try:
            hasil = fungsi(p)
        except Exception as e:
            hasil = {'ok': False, 'error': 'galat', 'pesan': str(e)[:300]}
    print(json.dumps(hasil))
