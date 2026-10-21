#!/usr/bin/env python3
"""Velocity Update — jurnal perubahan perusahaan + kondisi terbarunya.

Data: /var/lib/velocity/velocity-update/data.json. Dipakai server_stats.py (/api/velocity-update)
dan sebagai perintah:

  velocity_update.py daftar                      ringkasan semua update
  velocity_update.py tambah --judul .. --mulai YYYY-MM-DD [--divisi ..] [--jurnal ..] [--pantau ..] [--sumber a,b] [--oleh ..]
  velocity_update.py kondisi <id> "isi" [--oleh ..] [--status ..]
  velocity_update.py pantau [--id u-00N] [--sumber webmaster]   hitung metrik otomatis (timer harian; webmaster 4x sehari)
  velocity_update.py nilai [--oleh ..]           Claude menilai semua update yang berjalan (timer mingguan)
  velocity_update.py sandi < berkas              ganti sandi halaman (dibaca dari stdin; semua sesi lama keluar)

Sumber metrik otomatis (kunci `sumber` per update):
  kasus_support   kasus WA Support (/var/lib/velocity/kasus-support/data.db): kasus/hari, balasan pertama, status
  ai:<Divisi>     pemakaian Claude Code per orang di divisi itu (brain/token.json); ai:semua = semua divisi
  installer_wp    hasil run installer WordPress (/api/installer)
  laravel         project Aplikasi Custom (/api/laravel)
  crm_konsep      order web konsep di CRM (laporan konsep_detail)
  omzet           omzet perusahaan per kategori (CRM Laporan → Rincian Transaksi), bulan berjalan vs tanggal sama
  kasus_tim       penanganan kasus di menu Kasus Support CRM: penangan, catatan, handover, lama selesai
  kasus_ai        kasus Support per orang (penangan + jurnal CRM) dan kasus yang dikerjakan pakai Claude Code
                  (sesi Claude orang itu menyebut domain/nomor HP kasus): menit jurnal pakai AI vs tanpa AI per jenis
  webmaster       tiap webmaster sedang mengerjakan apa: CRM + installer WP/Laravel + sesi Claude (timer 09.00, 13.00, 17.00, 21.30)
  konsep_wm       aplikasi custom/konsep: installer Laravel → order CRM (project_list) → webmaster, disambung per domain
  kasus_harian    laporan kasus Support kemarin per kasus (nomor WA, lama selesai, menit kerja tim, perkiraan menit Claude),
                  urut dari lama selesai terlama; pantau harian menulisnya juga sebagai kondisi
  wa3_jalur       lead wa3 dua jalur (u-011): utama (robot oper ke CS di wa1) vs bidang (AI penuh di wa3) vs 30 hari sebelumnya:
                  lead, membalas, transfer, konversi, nominal, lama chat→bayar (perekam WA wa3 + wa1)
  ai_orang:<Nama> pemakaian Claude satu orang per hari, dibanding median divisinya
  installer_paket hasil installer per kelompok paket (E, F, biasa lain, custom) + perbaikan installer di repo
  bahasa:<akun>   bahasa tim ke klien di kanal WA itu (perekam rekam.velocitygrafis.com) + penilaian Claude mingguan
  harga_domain:<tld>:<lama>:<baru>  kenaikan harga domain (mis. harga_domain:com:206000:266000): klien yang sudah
                  dikirimi pengingat/rincian biaya sudah diinfo CS/AM atau belum, dan penawaran yang masih harga lama
Akhiran @YYYY-MM-DD pada sumber = tanggal pembanding sendiri (mis. ai_orang:Agung@2026-09-29 sejak meeting),
bukan tanggal mulai update.
"""
import argparse
import fcntl
import hashlib
import hmac
import secrets
import json
import os
import re
import sqlite3
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

DIR = Path(os.environ.get('VU_DIR', '/var/lib/velocity/velocity-update'))
DATA = DIR / 'data.json'
KUNCI = DIR / '.kunci'
CACHE_CRM = DIR / 'crm-konsep.json'
LOG_NILAI = DIR / 'nilai.log'
KASUS_DB = Path('/var/lib/velocity/kasus-support/data.db')
TOKEN_JSON = Path('/usr/share/nginx/html/brain/token.json')
API_SH = '/root/newvdnet-read/api.sh'
AI_USAGE = Path('/var/lib/velocity/ai/usage.jsonl')
CLAUDE = '/root/.local/bin/claude'
SANDI = Path('/etc/velocity/secrets/velocity-update.json')   # hash sandi halaman + kunci tanda tangan sesi
SESI_DETIK = 30 * 86400

STATUS = ('berjalan', 'bagus', 'perlu_perhatian', 'selesai', 'dihentikan')
SUMBER_TETAP = ('kasus_support', 'installer_wp', 'laravel', 'crm_konsep', 'konsep_wm', 'omzet', 'webmaster', 'kasus_tim', 'kasus_ai',
                'kasus_harian', 'wa3_jalur', 'kasus_meeting', 'efisiensi_langganan', 'konsep_halaman')
SUMBER_RE = re.compile(r'^(kasus_support|installer_wp|installer_paket|laravel|crm_konsep|konsep_wm|omzet|webmaster|kasus_tim|kasus_ai|kasus_harian|kasus_meeting|efisiensi_langganan|konsep_halaman|wa3_jalur|ai:[A-Za-z ]{1,30}'
                       r'|ai_orang:[A-Za-z .]{1,40}|bahasa:[a-z0-9-]{2,40}|harga_domain:[a-z.]{2,12}:\d{4,8}:\d{4,8})(@\d{4}-\d{2}-\d{2})?$')
REKAM_ENV = Path('/etc/velocity/secrets/pengawas-wa.env')     # REKAM_URL & REKAM_KUNCI (dipinjam dari pengawas-wa)
REPO = Path('/opt/velocity-wp-install-automation')
UA_BROWSER = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
TANGGAL_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
RIWAYAT_MAKS = 180          # cuplikan metrik per sumber (±6 bulan harian)
JENDELA = 14                # hari pembanding sebelum / sesudah


def sekarang():
    return datetime.now().astimezone().isoformat(timespec='seconds')


@contextmanager
def terkunci():
    DIR.mkdir(parents=True, exist_ok=True)
    with open(KUNCI, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def muat():
    try:
        d = json.loads(DATA.read_text())
    except (OSError, ValueError):
        d = {}
    d.setdefault('update', [])
    return d


def simpan(d):
    sementara = DATA.with_suffix('.tmp')
    sementara.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(sementara, DATA)


def id_baru(d, awalan, daftar):
    n = max([int(x['id'].rsplit('-', 1)[1]) for x in daftar if x.get('id', '').startswith(awalan)] or [0]) + 1
    return f'{awalan}{n:03d}'


def cari(d, uid):
    return next((u for u in d['update'] if u['id'] == uid), None)


# ---------- validasi & ubah (dipakai API dan CLI) ----------

def _teks(v, maks):
    return str(v or '').strip()[:maks]


def bersihkan_update(body):
    u = {
        'judul': _teks(body.get('judul'), 140),
        'jurnal': _teks(body.get('jurnal'), 4000),
        'mulai': _teks(body.get('mulai'), 10),
        'divisi': _teks(body.get('divisi'), 60),
        'pantau': _teks(body.get('pantau'), 1000),
        'status': body.get('status') or 'berjalan',
        'sumber': [s for s in (body.get('sumber') or []) if isinstance(s, str) and SUMBER_RE.match(s)][:6],
    }
    if not u['judul']:
        return None, 'judul_kosong'
    if not TANGGAL_RE.match(u['mulai']):
        return None, 'tanggal_tidak_valid'
    if u['status'] not in STATUS:
        return None, 'status_tidak_valid'
    return u, None


def tambah_update(body, oleh='Muh'):
    u, galat = bersihkan_update(body)
    if galat:
        return None, galat
    with terkunci():
        d = muat()
        u.update(id=id_baru(d, 'u-', d['update']), dibuat=sekarang(), diubah=sekarang(), oleh=_teks(oleh, 60) or 'Muh',
                 kondisi=[], metrik={})
        d['update'].append(u)
        simpan(d)
    return u, None


def ubah_update(uid, body):
    u_baru, galat = bersihkan_update(body)
    if galat:
        return None, galat
    with terkunci():
        d = muat()
        u = cari(d, uid)
        if not u:
            return None, 'tidak_ada'
        u.update(u_baru, diubah=sekarang())
        # Metrik sumber yang dilepas ikut dibuang supaya kartu tidak menampilkan angka basi
        u['metrik'] = {k: v for k, v in (u.get('metrik') or {}).items() if k in u['sumber']}
        simpan(d)
    return u, None


def hapus_update(uid):
    with terkunci():
        d = muat()
        n = len(d['update'])
        d['update'] = [u for u in d['update'] if u['id'] != uid]
        if len(d['update']) == n:
            return 'tidak_ada'
        simpan(d)
    return None


def tambah_kondisi(uid, isi, oleh='Muh', status=None, waktu=None, jenis='catatan'):
    isi = _teks(isi, 4000)
    if not isi:
        return None, 'isi_kosong'
    if status and status not in STATUS:
        return None, 'status_tidak_valid'
    with terkunci():
        d = muat()
        u = cari(d, uid)
        if not u:
            return None, 'tidak_ada'
        k = {'id': id_baru(d, 'k-', u['kondisi']), 'waktu': waktu or sekarang(), 'oleh': _teks(oleh, 60) or 'Muh',
             'isi': isi, 'jenis': jenis}
        if status and status != u['status']:
            k['status'] = {'dari': u['status'], 'ke': status}
            u['status'] = status
        u['kondisi'].append(k)
        u['kondisi'].sort(key=lambda x: x['waktu'])
        u['diubah'] = sekarang()
        simpan(d)
    return u, None


def hapus_kondisi(uid, kid):
    with terkunci():
        d = muat()
        u = cari(d, uid)
        if not u:
            return None, 'tidak_ada'
        n = len(u['kondisi'])
        u['kondisi'] = [k for k in u['kondisi'] if k['id'] != kid]
        if len(u['kondisi']) == n:
            return None, 'tidak_ada'
        simpan(d)
    return u, None


def status_api():
    d = muat()
    try:
        nilai = json.loads((DIR / 'nilai.json').read_text())
    except (OSError, ValueError):
        nilai = {}
    return {'update': d['update'], 'pantau_terakhir': d.get('pantau_terakhir'), 'nilai': nilai,
            'status': list(STATUS), 'sumber_tersedia': sumber_tersedia()}


def sumber_tersedia():
    s = [('kasus_support', 'Kasus WA Support'), ('installer_wp', 'Installer WordPress'),
         ('laravel', 'Project Aplikasi Custom'), ('crm_konsep', 'Order web konsep (CRM)'),
         ('konsep_wm', 'Aplikasi custom/konsep: installer → CRM → webmaster'),
         ('omzet', 'Omzet perusahaan (Rincian Transaksi CRM)'),
         ('webmaster', 'Webmaster sedang mengerjakan apa'),
         ('kasus_tim', 'Penanganan kasus Support (CRM)'), ('kasus_ai', 'Kasus Support per orang + dikerjakan pakai Claude'),
         ('wa3_jalur', 'wa3 dua jalur: utama (CS) vs bidang (AI)'),
         ('ai:semua', 'Pemakaian AI semua tim')]
    try:
        for dv in json.loads(TOKEN_JSON.read_text()).get('divisi') or []:
            s.append((f'ai:{dv}', f'Pemakaian AI tim {dv}'))
    except (OSError, ValueError):
        pass
    return [{'kunci': k, 'label': l} for k, l in s]


# ---------- sandi halaman ----------
# Hanya hash PBKDF2 yang disimpan. Sesi = cookie "<kedaluwarsa>.<hmac>" ditandatangani `rahasia`;
# ganti sandi = rahasia baru, jadi semua sesi lama otomatis tidak berlaku.

def _sandi():
    try:
        return json.loads(SANDI.read_text())
    except (OSError, ValueError):
        return None


def atur_sandi(teks):
    teks = teks.strip('\n')
    if len(teks) < 8:
        return 'sandi_terlalu_pendek'
    garam = secrets.token_bytes(16)
    putaran = 300000
    data = {'garam': garam.hex(), 'putaran': putaran, 'rahasia': secrets.token_hex(32),
            'hash': hashlib.pbkdf2_hmac('sha256', teks.encode(), garam, putaran).hex(), 'diubah': sekarang()}
    SANDI.parent.mkdir(parents=True, exist_ok=True)
    sementara = SANDI.with_suffix('.tmp')
    sementara.touch(mode=0o600)
    sementara.write_text(json.dumps(data))
    os.replace(sementara, SANDI)
    return None


def cek_sandi(teks):
    d = _sandi()
    if not d or not isinstance(teks, str):
        return False
    h = hashlib.pbkdf2_hmac('sha256', teks.encode(), bytes.fromhex(d['garam']), d['putaran']).hex()
    return hmac.compare_digest(h, d['hash'])


def buat_sesi():
    d = _sandi()
    habis = str(int(time.time()) + SESI_DETIK)
    return f"{habis}.{hmac.new(d['rahasia'].encode(), habis.encode(), 'sha256').hexdigest()}"


def cek_sesi(token):
    d = _sandi()
    if not d or not token or '.' not in token:
        return False
    habis, tanda = token.split('.', 1)
    benar = hmac.new(d['rahasia'].encode(), habis.encode(), 'sha256').hexdigest()
    return hmac.compare_digest(tanda, benar) and habis.isdigit() and int(habis) > time.time()


# ---------- metrik otomatis ----------

def _tgl(s):
    return date.fromisoformat(s[:10])


def _jendela(mulai):
    """(sebelum_dari, sebelum_sampai, sesudah_dari, sesudah_sampai) — hari penuh, sesudah berakhir kemarin."""
    kemarin = date.today() - timedelta(days=1)
    sesudah_dari = max(mulai, kemarin - timedelta(days=JENDELA - 1))
    return mulai - timedelta(days=JENDELA), mulai - timedelta(days=1), sesudah_dari, kemarin


def _angka(label, sebelum, sesudah, satuan='', arah=None, ket=''):
    return {'label': label, 'sebelum': sebelum, 'sesudah': sesudah, 'satuan': satuan, 'arah': arah, 'ket': ket}


def _hari(a, b):
    return max((b - a).days + 1, 0)


def metrik_kasus_support(mulai):
    if not KASUS_DB.exists():
        return {'galat': 'data kasus support belum ada'}
    c = sqlite3.connect(f'file:{KASUS_DB}?mode=ro', uri=True, timeout=10)
    sb_a, sb_b, ss_a, ss_b = _jendela(mulai)
    baris = c.execute("SELECT akun, nomor, mulai, terakhir, status, pesan_tim, mulai_id FROM kasus "
                      "WHERE pesan_klien > 0 AND substr(mulai,1,10) >= ?", (sb_a.isoformat(),)).fetchall()

    def balasan_pertama(akun, nomor, mulai_id, waktu_mulai):
        r = c.execute("SELECT min(waktu) FROM pesan WHERE akun=? AND chat_nomor=? AND dari_kami=1 AND id>? AND kembar=0",
                      (akun, nomor, mulai_id)).fetchone()[0]
        if not r:
            return None
        return (datetime.fromisoformat(r) - datetime.fromisoformat(waktu_mulai)).total_seconds() / 60

    def ringkas(a, b):
        isi = [x for x in baris if a <= _tgl(x[2]) <= b]
        hari = _hari(a, b)
        # Balasan pertama hanya untuk chat yang masuk di jam kerja (07–21) supaya chat malam tidak merusak median
        bl = [m for x in isi if 7 <= int(x[2][11:13]) < 21
              for m in [balasan_pertama(x[0], x[1], x[6], x[2])] if m is not None and m >= 0]
        return {
            'per_hari': round(len(isi) / hari, 1) if hari else None,
            'total': len(isi),
            'balas_median': round(statistics.median(bl), 1) if bl else None,
            'balas_30': round(100 * sum(m <= 30 for m in bl) / len(bl)) if bl else None,
            'pesan_tim': round(statistics.mean([x[5] for x in isi]), 1) if isi else None,
        }

    sb, ss = ringkas(sb_a, sb_b), ringkas(ss_a, ss_b)
    # Angka menunggu tim diambil dari CRM (status akhir: tanda tim + klien diam 3 hari ikut dihitung), supaya sama
    # dengan menu Kasus Support. Data lokal hanya cadangan bila CRM tidak terjangkau.
    try:
        r = subprocess.run([API_SH, '/api/api/kasus-support?per_page=10'], capture_output=True, text=True, timeout=60)
        rk = json.loads(r.stdout.splitlines()[0])['ringkas']
        menunggu, menunggu_lama, lama_label = rk['per_status']['menunggu_tim'], rk['terlantar'], 'diam ≥3 hari'
    except Exception:  # noqa: BLE001
        menunggu = c.execute("SELECT count(*) FROM kasus WHERE pesan_klien>0 AND status='menunggu_tim'").fetchone()[0]
        menunggu_lama = c.execute("SELECT count(*) FROM kasus WHERE pesan_klien>0 AND status='menunggu_tim' AND terakhir < ?",
                                  ((datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'),)).fetchone()[0]
        lama_label = '>1 hari (data lokal)'
    hari_ini = c.execute("SELECT count(*) FROM kasus WHERE pesan_klien>0 AND substr(mulai,1,10)=?",
                         (date.today().isoformat(),)).fetchone()[0]
    c.close()
    angka = [
        _angka('Kasus ditangani per hari', sb['per_hari'], ss['per_hari'], 'kasus', None,
               'Naik-turun mengikuti jumlah chat masuk, bukan hanya kecepatan tim'),
        _angka('Balasan pertama tim (median)', sb['balas_median'], ss['balas_median'], 'mnt', 'turun',
               'Chat masuk jam 07–21'),
        _angka('Dibalas ≤30 menit', sb['balas_30'], ss['balas_30'], '%', 'naik'),
        _angka('Pesan tim per kasus', sb['pesan_tim'], ss['pesan_tim'], '', None),
    ]
    ringkasan = (f"{ss['per_hari']} kasus/hari, balasan pertama median {ss['balas_median']} mnt"
                 f" (sebelumnya {sb['balas_median']} mnt). Menunggu tim sekarang: {menunggu}"
                 + (f', {menunggu_lama} di antaranya {lama_label}' if menunggu_lama else '') + ' (menu Kasus Support CRM, 30 hari).')
    return {'judul': 'Kasus WA Support', 'angka': angka, 'ringkas': ringkasan,
            'sorot': [{'label': 'Menunggu tim', 'nilai': menunggu, 'buruk': menunggu_lama > 0},
                      {'label': 'Kasus hari ini', 'nilai': hari_ini}],
            'periode': {'sebelum': [sb_a.isoformat(), sb_b.isoformat()], 'sesudah': [ss_a.isoformat(), ss_b.isoformat()]}}


def metrik_ai(divisi):
    try:
        t = json.loads(TOKEN_JSON.read_text())
    except (OSError, ValueError):
        return {'galat': 'token.json tidak terbaca'}
    hari7 = [(date.today() - timedelta(days=i)).isoformat() for i in range(1, 8)]   # 7 hari penuh terakhir
    orang = []
    for p in t.get('pengguna') or []:
        if not p.get('divisi') or (divisi != 'semua' and p['divisi'] != divisi):
            continue
        per_hari = {}
        sesi = 0
        for s in p.get('sesi') or []:
            pakai = False
            for h, m in (s.get('hari') or {}).items():
                if h in hari7:
                    per_hari[h] = per_hari.get(h, 0) + sum(v[4] for v in m.values())
                    pakai = True
            sesi += pakai
        aktif = len(per_hari)
        orang.append({'nama': p['nama'], 'divisi': p['divisi'], 'hari_aktif': aktif, 'sesi': sesi,
                      'panggilan': sum(per_hari.values()),
                      'per_hari_aktif': round(sum(per_hari.values()) / aktif) if aktif else 0})
    if not orang:
        return {'galat': f'tidak ada anggota divisi {divisi} di data token'}
    med = statistics.median([o['panggilan'] for o in orang])
    for o in orang:
        o['minim'] = o['hari_aktif'] <= 2 or (med > 0 and o['panggilan'] < 0.35 * med)
    orang.sort(key=lambda o: -o['panggilan'])
    minim = [o['nama'] for o in orang if o['minim']]
    judul = 'Pemakaian AI ' + ('semua tim' if divisi == 'semua' else f'tim {divisi}')
    ringkasan = (f"7 hari terakhir: {sum(o['hari_aktif'] > 0 for o in orang)}/{len(orang)} orang memakai Claude. "
                 + (f"Pemakaian minim: {', '.join(minim)}." if minim else 'Tidak ada yang tertinggal jauh.'))
    return {'judul': judul, 'orang': orang, 'ringkas': ringkasan,
            'sorot': [{'label': 'Pemakaian minim', 'nilai': len(minim), 'buruk': bool(minim)}],
            'ket': 'Panggilan = jumlah langkah kerja Claude. Minim = aktif ≤2 dari 7 hari atau <35% median divisi.'}


def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'velocity-update/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def metrik_installer_wp(mulai):
    try:
        rows = _get_json('http://127.0.0.1:9121/api/installer')['domains']
    except Exception as e:  # noqa: BLE001 — API lokal mati = metrik dilewati
        return {'galat': f'API installer: {e}'}
    # Installer berubah terus, jadi pembandingnya bergulir: 7 hari terakhir vs 14 hari sebelum itu
    ss_a = date.today() - timedelta(days=6)
    sb_b = ss_a - timedelta(days=1)
    sb_a = sb_b - timedelta(days=13)
    selesai = []
    for r in rows:
        t = ((r.get('lama') or {}).get('terakhir') or {})
        if t.get('selesai') and t.get('mode') == 'apply':
            selesai.append((date.fromtimestamp(t['selesai']), str(t.get('hasil') or ''), t.get('detik') or 0, r))

    def ringkas(a, b):
        isi = [x for x in selesai if a <= x[0] <= b]
        ok = [x for x in isi if x[1].startswith('SUCCESS')]
        minggu = _hari(a, b) / 7
        return {'ok': round(len(ok) / minggu, 1) if minggu else None,
                'gagal': round(len(isi) - len(ok)) if isi else 0,
                'rasio': round(100 * len(ok) / len(isi)) if isi else None,
                'lama': round(statistics.median([x[2] for x in ok]) / 60) if ok else None}

    sb, ss = ringkas(sb_a, sb_b), ringkas(ss_a, date.today())
    per_status = {}
    for r in rows:
        per_status[r.get('status') or '-'] = per_status.get(r.get('status') or '-', 0) + 1
    angka = [_angka('Web selesai otomatis per minggu', sb['ok'], ss['ok'], 'web', 'naik'),
             _angka('Run berhasil', sb['rasio'], ss['rasio'], '%', 'naik'),
             _angka('Lama install (median)', sb['lama'], ss['lama'], 'mnt', 'turun')]
    ringkasan = (f"7 hari terakhir {ss['ok']} web selesai otomatis, berhasil {ss['rasio']}% run "
                 f"(2 minggu sebelumnya {sb['ok']}/minggu). Gagal saat ini: {per_status.get('FAILED', 0)}, "
                 f"dikerjakan webmaster: {per_status.get('dikerjakan webmaster', 0)}.")
    return {'judul': 'Installer WordPress', 'angka': angka, 'ringkas': ringkasan,
            'sorot': [{'label': 'Gagal (perlu dicek)', 'nilai': per_status.get('FAILED', 0), 'buruk': per_status.get('FAILED', 0) > 0},
                      {'label': 'Belum diambil', 'nilai': per_status.get('belum diambil', 0)}],
            'periode': {'sebelum': [sb_a.isoformat(), sb_b.isoformat()], 'sesudah': [ss_a.isoformat(), date.today().isoformat()]},
            'ket': 'Kolom "sebelum" = 14 hari sebelum minggu ini, "sesudah" = 7 hari terakhir.'}


TAHAP_LABEL = {'brief': 'Brief', 'estimasi': 'Estimasi', 'install': 'Install', 'agen': 'Agen', 'review': 'Review', 'selesai': 'Selesai'}


def metrik_laravel(mulai):
    try:
        p = _get_json('http://127.0.0.1:9121/api/laravel')['proyek']
    except Exception as e:  # noqa: BLE001
        return {'galat': f'API laravel: {e}'}
    sb_a, sb_b, ss_a, ss_b = _jendela(mulai)
    ss_b = date.today()

    def dalam(a, b):
        return [x for x in p if a <= date.fromtimestamp(x['dibuat']) <= b]

    sb, ss = dalam(sb_a, sb_b), dalam(ss_a, ss_b)
    per_tahap = {}
    for x in p:
        per_tahap[x['tahap']] = per_tahap.get(x['tahap'], 0) + 1
    per_pm = {}
    for x in ss:
        per_pm[x.get('pm') or '-'] = per_pm.get(x.get('pm') or '-', 0) + 1
    menunggu_review = sum((x.get('review') or {}).get('menunggu', 0) for x in p)
    minggu_sb, minggu_ss = _hari(sb_a, sb_b) / 7, max(_hari(ss_a, ss_b), 1) / 7
    angka = [_angka('Project baru per minggu', round(len(sb) / minggu_sb, 1) if minggu_sb else None,
                    round(len(ss) / minggu_ss, 1), 'project', 'naik'),
             _angka('Sampai tahap Install/Agen/Review', None,
                    sum(per_tahap.get(k, 0) for k in ('install', 'agen', 'review', 'selesai')), 'project', 'naik',
                    'Semua project, kondisi sekarang')]
    ringkasan = (f"{len(ss)} project baru sejak {ss_a.strftime('%d %b')} "
                 f"({', '.join(f'{k} {v}' for k, v in per_pm.items()) or 'belum ada'}). "
                 f"Posisi semua project: " + ', '.join(f"{TAHAP_LABEL.get(k, k)} {v}" for k, v in per_tahap.items())
                 + (f'. Fitur menunggu review webmaster: {menunggu_review}.' if menunggu_review else '.'))
    return {'judul': 'Project Aplikasi Custom', 'angka': angka, 'ringkas': ringkasan,
            'sorot': [{'label': 'Fitur menunggu review', 'nilai': menunggu_review, 'buruk': menunggu_review > 5},
                      {'label': 'Masih di Brief/Estimasi', 'nilai': per_tahap.get('brief', 0) + per_tahap.get('estimasi', 0)}],
            'periode': {'sebelum': [sb_a.isoformat(), sb_b.isoformat()], 'sesudah': [ss_a.isoformat(), ss_b.isoformat()]}}


def _konsep_bulan(bulan):
    """Order web konsep CRM satu bulan. Bulan lampau di-cache permanen, bulan berjalan 6 jam."""
    try:
        cache = json.loads(CACHE_CRM.read_text())
    except (OSError, ValueError):
        cache = {}
    ini = date.today().strftime('%Y-%m')
    c = cache.get(bulan)
    if c and (bulan < ini or time.time() - c['ts'] < 6 * 3600):
        return c['data']
    r = subprocess.run([API_SH, f'/api/api/laporan/rincian_transaksi/konsep_detail?bulan={bulan}'],
                       capture_output=True, text=True, timeout=90)
    data = json.loads(r.stdout).get('data') or []
    cache[bulan] = {'ts': time.time(), 'data': data}
    DIR.mkdir(parents=True, exist_ok=True)
    CACHE_CRM.write_text(json.dumps(cache))
    return data


def metrik_crm_konsep(mulai):
    sb_a = mulai - timedelta(days=60)                       # order konsep jarang: pembanding 60 hari
    kemarin = date.today() - timedelta(days=1)
    bulan, d = set(), sb_a
    while d <= date.today():
        bulan.add(d.strftime('%Y-%m'))
        d += timedelta(days=28)
    bulan.add(date.today().strftime('%Y-%m'))
    try:
        order = [o for b in sorted(bulan) for o in _konsep_bulan(b)]
    except Exception as e:  # noqa: BLE001 — CRM tidak terjangkau
        return {'galat': f'CRM: {str(e)[:200]}'}
    sb = [o for o in order if sb_a <= _tgl(o['tgl_masuk']) < mulai]
    ss = [o for o in order if mulai <= _tgl(o['tgl_masuk']) <= date.today()]
    hsb, hss = _hari(sb_a, mulai - timedelta(days=1)), max(_hari(mulai, kemarin), 1)
    per30 = lambda xs, h: round(len(xs) * 30 / h, 1)  # noqa: E731
    rata = lambda xs: round(statistics.mean([o['biaya'] for o in xs]) / 1e6, 2) if xs else None  # noqa: E731
    angka = [_angka('Order konsep per 30 hari', per30(sb, hsb), per30(ss, hss), 'order', 'naik'),
             _angka('Nominal per 30 hari', round(sum(o['biaya'] for o in sb) * 30 / hsb / 1e6, 1),
                    round(sum(o['biaya'] for o in ss) * 30 / hss / 1e6, 1), 'jt', 'naik'),
             _angka('Rata-rata per order', rata(sb), rata(ss), 'jt', None)]
    ringkasan = (f"{len(ss)} order konsep sejak {mulai.strftime('%d %b')} (Rp{sum(o['biaya'] for o in ss) / 1e6:.1f} jt); "
                 f"laju {per30(ss, hss)} order/30 hari vs {per30(sb, hsb)} sebelumnya.")
    return {'judul': 'Order web konsep (CRM)', 'angka': angka, 'ringkas': ringkasan,
            'daftar': [{'tgl': o['tgl_masuk'], 'nama': o['nama_web'], 'nilai': o['biaya']} for o in ss[-10:]],
            'periode': {'sebelum': [sb_a.isoformat(), (mulai - timedelta(days=1)).isoformat()],
                        'sesudah': [mulai.isoformat(), date.today().isoformat()]},
            'ket': 'Pembanding 60 hari sebelum tanggal mulai; hanya order berjenis "Pembuatan web konsep" di CRM.'}


def _status_wm(wm):
    """Status pengerjaan webmaster, aturannya sama dengan filter status_pengerjaan di ProjectListController."""
    if not wm:
        return 'Belum dikerjakan'
    if wm.get('status_multi') == 'selesai':
        return 'Selesai'
    if not (wm.get('date_selesai') or '').strip():
        return 'Dalam pengerjaan'
    return wm.get('status_project') or 'Menunggu koreksi'


def _domain_kunci(x):
    x = (x or '').strip().lower()
    return x[4:] if x.startswith('www.') else x


def metrik_konsep_wm(mulai):
    """Satu alur aplikasi custom/konsep: analisa di installer Laravel → order "Pembuatan web konsep" di CRM →
    dikerjakan webmaster/agen installer → selesai. Disambung lewat domain (relasi On Progress installer = nama_web CRM)."""
    sb_a = mulai - timedelta(days=60)                       # sama dengan crm_konsep: konsep jarang
    awal = min(sb_a, date.today() - timedelta(days=90))     # yang belum selesai tetap tampil sampai 90 hari
    try:
        r = subprocess.run([API_SH, '/api/api/project_list?jenis=Pembuatan%20web%20konsep'
                            f'&tgl_masuk_start={awal}&tgl_masuk_end={date.today()}&per_page=500'],
                           capture_output=True, text=True, timeout=90)
        proj = json.loads(r.stdout.splitlines()[0])['data']
        # project_list tidak memuat tgl_masuk → diambil dari konsep_detail (id sama)
        bulan, d = set(), awal
        while d <= date.today():
            bulan.add(d.strftime('%Y-%m'))
            d += timedelta(days=28)
        bulan.add(date.today().strftime('%Y-%m'))
        masuk = {o['id']: o for b in sorted(bulan) for o in _konsep_bulan(b)}
    except Exception as e:  # noqa: BLE001 — CRM tidak terjangkau
        return {'galat': f'CRM: {str(e)[:200]}'}
    try:
        inst = _get_json('http://127.0.0.1:9121/api/laravel')['proyek']
    except Exception as e:  # noqa: BLE001 — installer mati: tetap tampilkan sisi CRM
        inst, galat_inst = [], str(e)[:120]
    else:
        galat_inst = None
    per_domain = {}
    for x in inst:
        for k in {_domain_kunci(x.get('domain')), _domain_kunci(x.get('onprogress'))} - {''}:
            per_domain[k] = x

    hari_ini = date.today()

    def info_installer(x):
        fs = x.get('fitur_status') or {}
        return {'slug': x['slug'], 'pm': x.get('pm') or '', 'tahap': TAHAP_LABEL.get(x['tahap'], x['tahap']),
                'fitur': f"{fs.get('ok', 0)}/{x.get('fitur_total') or 0}" if x.get('fitur_total') else '',
                'review': (x.get('review') or {}).get('menunggu', 0)}

    baris, terpakai = [], set()
    for p in proj:
        wm = p.get('wm_project') or {}
        o = masuk.get(p['id']) or {}
        nama = (p.get('webhost') or {}).get('nama_web') or '-'
        mul = (wm.get('date_mulai') or '')[:10] or None
        sel = (wm.get('date_selesai') or '').strip()[:10] or None
        dl = p.get('tgl_deadline')
        x = per_domain.get(_domain_kunci(nama))
        if x:
            terpakai.add(x['slug'])
        baris.append({'id': p['id'], 'sumber': 'keduanya' if x else 'crm', 'tgl': o.get('tgl_masuk'), 'nama': nama,
                      'biaya': o.get('biaya'), 'webmaster': wm.get('webmaster') or '', 'status': _status_wm(wm or None),
                      'mulai': mul, 'selesai_wm': sel, 'deadline': dl, 'telat': bool(dl) and ((sel or hari_ini.isoformat()) > dl),
                      'ket': (p.get('deskripsi') or '').strip()[:120], **(info_installer(x) if x else {})})
    for x in inst:
        if x['slug'] in terpakai:
            continue
        baris.append({'id': x['slug'], 'sumber': 'installer', 'tgl': date.fromtimestamp(x['dibuat']).isoformat(),
                      'nama': x.get('judul') or x['slug'], 'webmaster': '', 'status': 'Belum ada order CRM',
                      'mulai': None, 'selesai_wm': None, 'deadline': None, 'telat': False,
                      'ket': f"{x['slug']} · {x.get('klien') or ''}".strip(' ·'), **info_installer(x)})

    crm = [x for x in baris if x['sumber'] != 'installer']

    def dalam(xs, a, b):
        return [x for x in xs if x['tgl'] and a <= _tgl(x['tgl']) <= b]

    def selisih(a, b):
        return (_tgl(b) - _tgl(a)).days

    def ringkas(xs, a, b):
        hari = _hari(a, b)
        tunggu = [selisih(x['tgl'], x['mulai']) for x in xs if x['mulai']]
        lama = [selisih(x['mulai'], x['selesai_wm']) for x in xs if x['mulai'] and x['selesai_wm']]
        jadi = [x for x in xs if x['selesai_wm']]
        return {'per30': round(len(xs) * 30 / hari, 1) if hari else None,
                'tunggu': statistics.median(tunggu) if tunggu else None,
                'lama': statistics.median(lama) if lama else None,
                'tepat': round(100 * sum(not x['telat'] for x in jadi) / len(jadi)) if jadi else None}

    kemarin = hari_ini - timedelta(days=1)
    sb, ss = dalam(crm, sb_a, mulai - timedelta(days=1)), dalam(crm, mulai, hari_ini)
    a, b = ringkas(sb, sb_a, mulai - timedelta(days=1)), ringkas(ss, mulai, max(kemarin, mulai))
    angka = [_angka('Order konsep per 30 hari', a['per30'], b['per30'], 'order', 'naik'),
             _angka('Masuk → mulai dikerjakan (median)', a['tunggu'], b['tunggu'], 'hari', 'turun'),
             _angka('Lama pengerjaan webmaster (median)', a['lama'], b['lama'], 'hari', 'turun',
                    'Dari mulai dikerjakan sampai webmaster mengisi tanggal selesai'),
             _angka('Selesai webmaster ≤ deadline', a['tepat'], b['tepat'], '%', 'naik')]

    # Daftar: sejak tanggal mulai + yang lebih lama tapi belum Selesai (CRM ≤90 hari; installer semua yang belum selesai)
    tampil = [x for x in baris if (x['tgl'] and _tgl(x['tgl']) >= mulai)
              or (x['status'] != 'Selesai' and x['sumber'] != 'installer')
              or (x['sumber'] == 'installer' and x['tahap'] != 'Selesai')]
    tampil.sort(key=lambda x: x['tgl'] or '9999', reverse=True)
    hitung = lambda st: sum(x['status'] == st for x in ss)  # noqa: E731
    belum = [x for x in tampil if x['status'] == 'Belum dikerjakan']
    telat = [x for x in tampil if x['telat'] and x['status'] != 'Selesai' and not x['selesai_wm']]
    sudah = sum(1 for x in ss if x['selesai_wm'])
    analisa = [x for x in tampil if x['sumber'] == 'installer']
    per_tahap = {}
    for x in analisa:
        per_tahap[x['tahap']] = per_tahap.get(x['tahap'], 0) + 1
    tanpa_inst = [x for x in ss if x['sumber'] == 'crm']
    sambung = [x['nama'] for x in tampil if x['sumber'] == 'keduanya']
    ringkasan = (f"{len(ss)} order konsep masuk CRM sejak {mulai.day} {BULAN_ID[mulai.month - 1]}: {sudah} sudah dikerjakan webmaster "
                 f"(selesai {hitung('Selesai')}, menunggu koreksi {sum(x['status'] not in ('Selesai', 'Dalam pengerjaan', 'Belum dikerjakan') for x in ss)}), "
                 f"{hitung('Dalam pengerjaan')} dalam pengerjaan, {hitung('Belum dikerjakan')} belum dikerjakan"
                 + (f"; {len(telat)} lewat deadline dan belum selesai" if telat else '') + '. '
                 + f"Installer Aplikasi Custom: {len(analisa)} project belum ada order CRM ("
                 + (', '.join(f'{k} {v}' for k, v in per_tahap.items()) or '-') + ')'
                 + (f"; tersambung ke order: {', '.join(sambung)}" if sambung else '; belum ada yang tersambung ke order')
                 + f". {len(tanpa_inst)} order konsep dikerjakan di luar installer."
                 + (f' (Installer tidak terbaca: {galat_inst})' if galat_inst else ''))
    return {'judul': 'Aplikasi custom / konsep: installer → CRM → webmaster', 'angka': angka, 'ringkas': ringkasan,
            'sorot': [{'label': 'Belum dikerjakan', 'nilai': len(belum),
                       'buruk': any(x['tgl'] and (hari_ini - _tgl(x['tgl'])).days >= 2 for x in belum)},
                      {'label': 'Lewat deadline, belum selesai', 'nilai': len(telat), 'buruk': bool(telat)},
                      {'label': 'Analisa installer, belum order', 'nilai': len(analisa)},
                      {'label': 'Order di luar installer', 'nilai': len(tanpa_inst)}],
            'konsep': tampil[:60],
            'periode': {'sebelum': [sb_a.isoformat(), (mulai - timedelta(days=1)).isoformat()],
                        'sesudah': [mulai.isoformat(), hari_ini.isoformat()]},
            'ket': 'Gabungan Project List CRM (jenis "Pembuatan web konsep") dan Installer Laravel (/installer/laravel). '
                   'Disambung lewat domain: relasi On Progress di installer = nama web di CRM. Status CRM sama dengan kolom '
                   'Status Pengerjaan Project List (tanggal selesai webmaster terisi = sudah dikerjakan). Project installer '
                   'tanpa pasangan di CRM = "Belum ada order CRM" (masih analisa/estimasi, atau order belum diinput). '
                   'Telat = tanggal selesai webmaster (atau hari ini) melewati deadline. Angka sebelum/sesudah hanya order CRM, '
                   'pembanding 60 hari sebelum tanggal mulai.'}

# ---------- omzet perusahaan (CRM Laporan → Rincian Transaksi) ----------

CACHE_OMZET = DIR / 'crm-omzet.json'
BULAN_ID = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
# Kategori kotor = tabel Rincian Transaksi (nominal). "Lainnya" = tabel Omzet (semua jenis) dikurangi semuanya
# (email, google maps, apk, AM, dst.).
KATEGORI_OMZET = [('pembuatan', 'Pembuatan'), ('perpanjangan', 'Perpanjangan'), ('tambah_space', 'Tambah Space'),
                  ('jasa_update_web', 'Jasa Update Web'), ('lain_lain', 'Lain - lain'),
                  ('iklan', 'Iklan + Deposit Google (Semua HP)'), ('jasa_iklan', 'Jasa update iklan google')]
LABEL_OMZET = {'pembuatan': 'Pembuatan', 'perpanjangan': 'Perpanjangan', 'tambah_space': 'Tambah space',
               'jasa_update_web': 'Jasa update web', 'lain_lain': 'Lain-lain', 'iklan': 'Iklan + deposit Google',
               'jasa_iklan': 'Jasa update iklan', 'lainnya': 'Jenis lain (email, maps, apk, …)'}


def _bulan_label(k):
    return f"{BULAN_ID[int(k[5:7]) - 1]} {k[2:4]}"


def _crm_cache(kunci, jalur, ttl):
    try:
        cache = json.loads(CACHE_OMZET.read_text())
    except (OSError, ValueError):
        cache = {}
    c = cache.get(kunci)
    if c and time.time() - c['ts'] < ttl:
        return c['data']
    r = subprocess.run([API_SH, jalur], capture_output=True, text=True, timeout=180)
    data = json.loads(r.stdout.splitlines()[0])
    cache = {k: v for k, v in cache.items() if time.time() - v['ts'] < 7 * 86400}
    cache[kunci] = {'ts': time.time(), 'data': data}
    DIR.mkdir(parents=True, exist_ok=True)
    CACHE_OMZET.write_text(json.dumps(cache))
    return data


def _omzet_per_bulan(d):
    """{YYYY-MM: {kategori: nominal kotor, 'kotor': total, 'bersih': Omzet ringkasan CRM, 'order_buat', 'iklan_buat'}}"""
    tab = {t['name']: {r['key']: r for r in t['rows']} for t in d['tables']}
    hasil = {}
    for b in [m['key'] for m in d['months']]:
        x = {k: int((tab.get(nama, {}).get(b) or {}).get('nominal') or 0) for k, nama in KATEGORI_OMZET}
        semua = int(((tab.get('Omzet') or tab.get('Omset') or {}).get(b) or {}).get('nominal') or 0)   # tabel per tanggal: "Omset"
        x['lainnya'] = max(semua - sum(x.values()), 0)
        x['kotor'] = semua
        rb = next((r for r in d['summary']['rows'] if r['key'] == b), {})
        x['bersih'] = int(rb.get('omzet') or 0)
        pb = tab.get('Pembuatan', {}).get(b) or {}
        x['order_buat'] = int(pb.get('jumlah_web') or 0)
        x['iklan_buat'] = int(pb.get('biaya_iklan') or 0)
        x['laba_buat'] = int(pb.get('net_profit') or 0)
        x['web_perpanjang'] = int((tab.get('Perpanjangan', {}).get(b) or {}).get('jumlah_web') or 0)
        hasil[b] = x
    return hasil


def metrik_omzet(mulai):
    hari_ini = date.today()
    ini = hari_ini.strftime('%Y-%m')
    awal = date(hari_ini.year - 2, hari_ini.month, 1)
    try:
        d = _crm_cache(f'bulanan:{awal}', f'/api/api/laporan/rincian_transaksi?dari={awal}&sampai={hari_ini}', 6 * 3600)
        bulan = _omzet_per_bulan(d)
        laju = None
        if hari_ini.day > 1:   # bulan berjalan s/d kemarin vs tanggal yang sama di bulan-bulan lain
            t = _crm_cache(f'tgl:{ini}:{hari_ini.day - 1}', '/api/api/laporan/rincian_transaksi_tgl?'
                           f'dari={date(hari_ini.year - 1, hari_ini.month, 1)}&sampai={hari_ini}&tgl_dari=1&tgl_sampai={hari_ini.day - 1}',
                           3 * 3600)
            laju = _omzet_per_bulan(t)
    except Exception as e:  # noqa: BLE001 — CRM tidak terjangkau
        return {'galat': f'CRM: {str(e)[:200]}'}

    penuh = sorted(b for b in bulan if b < ini)
    mulai_b = mulai.strftime('%Y-%m')
    ss_b = [b for b in penuh if b >= mulai_b] or penuh[-1:]
    sb_b = [b for b in penuh if b < ss_b[0]][-3:]
    rata = lambda bs, k: round(statistics.mean([bulan[b][k] for b in bs]) / 1e6, 1) if bs else None  # noqa: E731
    angka = [_angka('Omzet kotor / bulan', rata(sb_b, 'kotor'), rata(ss_b, 'kotor'), 'jt', 'naik',
                    'Semua transaksi CRM (tabel Omzet di Rincian Transaksi)'),
             _angka('Omzet versi Ringkasan CRM', rata(sb_b, 'bersih'), rata(ss_b, 'bersih'), 'jt', 'naik',
                    'Pembuatan setelah domain & biaya iklan, perpanjangan setelah domain, sisanya kotor'),
             _angka('Pembuatan (kotor)', rata(sb_b, 'pembuatan'), rata(ss_b, 'pembuatan'), 'jt', 'naik'),
             _angka('Laba pembuatan (−domain −iklan)', rata(sb_b, 'laba_buat'), rata(ss_b, 'laba_buat'), 'jt', 'naik'),
             _angka('Perpanjangan (kotor)', rata(sb_b, 'perpanjangan'), rata(ss_b, 'perpanjangan'), 'jt', 'naik'),
             _angka('Tambah space', rata(sb_b, 'tambah_space'), rata(ss_b, 'tambah_space'), 'jt', 'naik'),
             _angka('Iklan + deposit Google', rata(sb_b, 'iklan'), rata(ss_b, 'iklan'), 'jt', 'naik'),
             _angka('Biaya iklan pembuatan', rata(sb_b, 'iklan_buat'), rata(ss_b, 'iklan_buat'), 'jt', 'turun')]
    order = lambda bs: round(statistics.mean([bulan[b]['order_buat'] for b in bs])) if bs else None  # noqa: E731
    cpa = lambda bs: (round(sum(bulan[b]['iklan_buat'] for b in bs) / max(sum(bulan[b]['order_buat'] for b in bs), 1) / 1e3)  # noqa: E731
                      if bs else None)
    angka += [_angka('Order pembuatan / bulan', order(sb_b), order(ss_b), 'order', 'naik'),
              _angka('Biaya iklan per order pembuatan', cpa(sb_b), cpa(ss_b), 'rb', 'turun')]

    # Penyumbang naik/turun: rata-rata periode sesudah vs sebelum per kategori
    beda = []
    if sb_b:
        for k in [k for k, _ in KATEGORI_OMZET] + ['lainnya']:
            a = statistics.mean([bulan[b][k] for b in sb_b])
            b_ = statistics.mean([bulan[b][k] for b in ss_b])
            if abs(b_ - a) >= 1e6:
                beda.append((b_ - a, k))
    beda.sort(reverse=True)

    akhir = penuh[-1]
    tahun_lalu = f"{int(akhir[:4]) - 1}{akhir[4:]}"
    yoy = (round(100 * (bulan[akhir]['kotor'] / bulan[tahun_lalu]['kotor'] - 1)) if bulan.get(tahun_lalu, {}).get('kotor') else None)
    ranking = sorted(penuh[-13:], key=lambda b: bulan[b]['kotor'], reverse=True)
    pos = ranking.index(akhir) + 1
    ring = (f"{_bulan_label(akhir)}: omzet kotor Rp{bulan[akhir]['kotor'] / 1e6:.1f} jt"
            + (' (tertinggi dalam 13 bulan)' if pos == 1 else f' (ke-{pos} dari 13 bulan)')
            + (f", {'+' if yoy >= 0 else ''}{yoy}% dibanding {_bulan_label(tahun_lalu)}" if yoy is not None else '')
            + f"; versi Ringkasan CRM Rp{bulan[akhir]['bersih'] / 1e6:.1f} jt.")
    if sb_b:
        ring += (f" Rata-rata {', '.join(_bulan_label(b) for b in ss_b)} vs 3 bulan sebelumnya: "
                 + '; '.join(f"{LABEL_OMZET[k]} {'+' if v >= 0 else '−'}{abs(v) / 1e6:.1f} jt" for v, k in beda[:4]) + '.')
    sorot = []
    if laju and laju.get(ini):
        lalu = [b for b in sorted(laju) if b < ini][-3:]
        pemb = statistics.mean([laju[b].get('kotor', 0) for b in lalu]) if lalu else 0
        skr = laju[ini].get('kotor', 0)
        sorot.append({'label': f'Bulan ini s/d tgl {hari_ini.day - 1} (kotor)', 'nilai': f"Rp{skr / 1e6:.1f} jt".replace('.', ','),
                      'buruk': bool(pemb) and skr < 0.85 * pemb})
        if pemb:
            sorot.append({'label': 'vs rata-rata 3 bln, tanggal sama', 'nilai': f"{'+' if skr >= pemb else ''}{round(100 * (skr / pemb - 1))}%",
                          'buruk': skr < 0.85 * pemb})
        ring += (f" Bulan ini s/d tgl {hari_ini.day - 1}: Rp{skr / 1e6:.1f} jt"
                 + (f" ({'+' if skr >= pemb else ''}{round(100 * (skr / pemb - 1))}% dari rata-rata 3 bulan di tanggal yang sama)." if pemb else '.'))
    tabel = [{'bulan': b, 'label': _bulan_label(b), **{k: bulan[b][k] for k in
              ('kotor', 'bersih', 'pembuatan', 'laba_buat', 'perpanjangan', 'tambah_space', 'jasa_update_web', 'iklan',
               'lain_lain', 'lainnya', 'order_buat', 'iklan_buat', 'web_perpanjang')},
              'berjalan': b == ini} for b in sorted(bulan)[-13:]][::-1]
    return {'judul': 'Omzet perusahaan (CRM Rincian Transaksi)', 'angka': angka, 'ringkas': ring, 'sorot': sorot,
            'omzet': tabel,
            'periode': {'sebelum': [f'{sb_b[0]}-01', f'{sb_b[-1]}-28'] if sb_b else None,
                        'sesudah': [f'{ss_b[0]}-01', f'{ss_b[-1]}-28']},
            'ket': 'Sumber: new.vd.net Laporan → Rincian Transaksi. "Kotor" = nominal transaksi; "versi Ringkasan CRM" = '
                   'kolom Omzet di tabel ringkasan (pembuatan dikurangi domain & biaya iklan, perpanjangan dikurangi domain). '
                   'Angka sebelum/sesudah = rata-rata per bulan penuh: bulan sejak tanggal mulai (atau bulan penuh terakhir) '
                   'vs 3 bulan sebelumnya. Bulan berjalan dibandingkan di tanggal yang sama. Data CRM di-cache 6 jam.'}


# ---------- webmaster sedang mengerjakan apa (CRM + installer + sesi Claude) ----------

WEBMASTER_JSON = REPO / 'config' / 'webmaster.json'
DOMAIN_TEKS_RE = re.compile(r'\b((?:[a-z0-9-]+\.)+(?:com|id|net|org|co\.id|web\.id|ac\.id|sch\.id|or\.id|my\.id|biz|info|studio|co|io))\b', re.I)
TEMPAT_KANTOR = ('velocitydeveloper', 'velocitygrafis', '192.168.', 'github.com', 'localhost')


def _hari_kerja_antara(a, b):
    """Jumlah hari kerja (Senin–Sabtu) di antara dua datetime."""
    n, d = 0, a.date()
    while d < b.date():
        d += timedelta(days=1)
        n += d.weekday() != 6
    return n


def metrik_webmaster(mulai):
    try:
        conf = json.loads(WEBMASTER_JSON.read_text())['webmaster']
    except (OSError, ValueError, KeyError) as e:
        return {'galat': f'config/webmaster.json: {e}'}
    hari_ini = date.today()
    sekarang_dt = datetime.now()
    alias = {a: w['nama'] for w in conf for a in w['alias']}
    milik = lambda nama: alias.get((nama or '').strip().lower())  # noqa: E731
    try:
        crm = []
        for st in ('Dalam%20pengerjaan', 'Menunggu%20koreksi'):
            r = subprocess.run([API_SH, f'/api/api/project_list?status_pengerjaan={st}&per_page=500'
                                + (f'&tgl_masuk_start={hari_ini - timedelta(days=60)}&tgl_masuk_end={hari_ini}'
                                   if st.startswith('Menunggu') else '')],
                               capture_output=True, text=True, timeout=120)
            crm += json.loads(r.stdout.splitlines()[0])['data']
    except Exception as e:  # noqa: BLE001
        return {'galat': f'CRM: {str(e)[:200]}'}
    try:
        wp = _get_json('http://127.0.0.1:9121/api/installer')['domains']
    except Exception:  # noqa: BLE001 — panel tetap jalan tanpa installer
        wp = []
    try:
        lar = _get_json('http://127.0.0.1:9121/api/laravel')['proyek']
    except Exception:  # noqa: BLE001
        lar = []
    try:
        tok = {p['nama']: p for p in json.loads(TOKEN_JSON.read_text())['pengguna']}
    except (OSError, ValueError, KeyError):
        tok = {}

    orang = {w['nama']: {'nama': w['nama'], 'crm': [], 'installer': [], 'sesi': [], 'domain_lain': [], 'tanda': [],
                         'terakhir_aktif': None} for w in conf}
    basi = []
    for p in crm:
        wm = p.get('wm_project') or {}
        st = _status_wm(wm or None)
        dl = p.get('tgl_deadline')
        x = {'nama_web': (p.get('webhost') or {}).get('nama_web') or '-', 'jenis': p.get('jenis'),
             'paket': ((p.get('webhost') or {}).get('paket') or {}).get('paket'), 'status': st,
             'mulai': (wm.get('date_mulai') or '')[:10] or None, 'deadline': dl,
             'sisa_hari': (_tgl(dl) - hari_ini).days if dl else None, 'catatan': (wm.get('catatan') or '')[:80]}
        siapa = milik(wm.get('webmaster'))
        if siapa:
            orang[siapa]['crm'].append(x)
        elif st == 'Dalam pengerjaan':
            basi.append({**x, 'webmaster': wm.get('webmaster') or '-'})
    for o in orang.values():
        o['crm'].sort(key=lambda x: (x['status'] != 'Dalam pengerjaan', x['deadline'] or '9999'))
    for r in wp:
        siapa = milik(r.get('webmaster'))
        if siapa and r.get('crm_status') == 'dikerjakan webmaster':
            orang[siapa]['installer'].append({'jenis': 'WordPress', 'nama': r['domain'], 'tahap': r.get('status'),
                                              'paket': r.get('paket'), 'review': 0})
    domain_crm = {_domain_kunci(x['nama_web']): siapa for siapa, o in orang.items() for x in o['crm']}
    for x in lar:
        if x['tahap'] in ('selesai',):
            continue
        siapa = milik(x.get('pm')) or domain_crm.get(_domain_kunci(x.get('domain')))
        if siapa and x['tahap'] not in ('brief', 'estimasi'):
            fs = x.get('fitur_status') or {}
            orang[siapa]['installer'].append({'jenis': 'Laravel', 'nama': x.get('domain') or x.get('judul'), 'slug': x['slug'],
                                              'tahap': TAHAP_LABEL.get(x['tahap'], x['tahap']),
                                              'fitur': f"{fs.get('ok', 0)}/{x.get('fitur_total') or 0}",
                                              'review': (x.get('review') or {}).get('menunggu', 0)})
    for w in conf:
        o = orang[w['nama']]
        sesi = sorted((tok.get(w['token']) or {}).get('sesi') or [], key=lambda s: s.get('akhir') or 0, reverse=True)
        if sesi:
            o['terakhir_aktif'] = datetime.fromtimestamp(sesi[0]['akhir']).isoformat(timespec='minutes')
        batas = time.time() - 2 * 86400
        o['sesi'] = [{'judul': (s.get('judul') or '').replace('\n', ' ')[:140], 'jenis': s.get('jenis'),
                      'akhir': datetime.fromtimestamp(s['akhir']).isoformat(timespec='minutes')}
                     for s in sesi[:4] if (s.get('akhir') or 0) >= batas]
        dicatat = {_domain_kunci(x['nama_web']) for x in o['crm']} | {_domain_kunci(x['nama']) for x in o['installer']}
        lain = []
        for s in sesi:
            if (s.get('akhir') or 0) < batas:
                break
            for dm in DOMAIN_TEKS_RE.findall(s.get('judul') or ''):
                dm = _domain_kunci(dm)
                if dm not in dicatat and dm not in lain and not any(k in dm for k in TEMPAT_KANTOR):
                    lain.append(dm)
        o['domain_lain'] = lain[:6]
        # Tanda
        for x in o['crm']:
            if x['status'] == 'Dalam pengerjaan' and x['sisa_hari'] is not None and x['sisa_hari'] <= 1:
                o['tanda'].append(f"{x['nama_web']}: " + ('lewat deadline' if x['sisa_hari'] < 0 else
                                                          'deadline hari ini' if x['sisa_hari'] == 0 else 'deadline besok'))
        rv = sum(x.get('review') or 0 for x in o['installer'])
        if rv > 10:
            o['tanda'].append(f'{rv} fitur menunggu review')
        if not o['terakhir_aktif'] or _hari_kerja_antara(datetime.fromisoformat(o['terakhir_aktif']), sekarang_dt) > 1:
            o['tanda'].append('tidak ada aktivitas Claude >1 hari kerja')
        if not any(x['status'] == 'Dalam pengerjaan' for x in o['crm']) and not o['installer']:
            o['tanda'].append('tidak ada project berjalan di CRM')

    daftar = list(orang.values())
    aktif = sum(1 for o in daftar if o['terakhir_aktif'] and
                (sekarang_dt - datetime.fromisoformat(o['terakhir_aktif'])).total_seconds() < 86400)
    berjalan = sum(1 for o in daftar for x in o['crm'] if x['status'] == 'Dalam pengerjaan')
    mepet = sum(1 for o in daftar for t in o['tanda'] if 'deadline' in t)
    review = sum(x.get('review') or 0 for o in daftar for x in o['installer'])
    ringkasan = (f"{len(daftar)} webmaster, {aktif} aktif di Claude 24 jam terakhir. {berjalan} project berstatus Dalam pengerjaan "
                 f"di CRM; {mepet} deadline ≤1 hari; {review} fitur Laravel menunggu review."
                 + (f" {len(basi)} project 'Dalam pengerjaan' di CRM atas nama orang di luar daftar (kemungkinan basi)." if basi else ''))
    return {'judul': 'Webmaster sedang mengerjakan apa', 'ringkas': ringkasan, 'angka': [],
            'sorot': [{'label': 'Deadline ≤1 hari', 'nilai': mepet, 'buruk': mepet > 0},
                      {'label': 'Fitur menunggu review', 'nilai': review, 'buruk': review > 10},
                      {'label': 'Tidak aktif >1 hari kerja', 'nilai': sum(any('aktivitas' in t for t in o['tanda']) for o in daftar),
                       'buruk': any(any('aktivitas' in t for t in o['tanda']) for o in daftar)},
                      {'label': 'Project basi di CRM', 'nilai': len(basi), 'buruk': len(basi) > 0}],
            'webmaster': daftar, 'basi': sorted(basi, key=lambda x: x['mulai'] or ''),
            'periode': {'sebelum': None, 'sesudah': [hari_ini.isoformat(), hari_ini.isoformat()]},
            'ket': 'Diperbarui 4x sehari (09.00, 13.00, 17.00, 21.30). CRM = Project List (Dalam pengerjaan + Menunggu koreksi 60 hari) atas nama webmaster; '
                   'installer = domain WordPress berstatus "dikerjakan webmaster" + project Laravel (PM/domain cocok) di tahap '
                   'Install/Agen/Review; aktivitas = sesi Claude Code 2 hari terakhir (judul = perintah pertama sesi). '
                   '"Domain lain" = domain yang disebut di sesi Claude tetapi tidak ada di CRM/installer atas nama orang itu '
                   '(bisa revisi/support, bisa juga belum dicatat). Nama per sistem diatur di config/webmaster.json.'}


# ---------- penanganan kasus Support di CRM (menu Tim Support → Kasus Support) ----------

def _waktu_crm(t):
    """ISO dari API Laravel (UTC, akhiran Z) → datetime lokal WIB tanpa zona."""
    if not t:
        return None
    if t.endswith('Z') or '+' in t[10:]:
        return datetime.fromisoformat(t.replace('Z', '+00:00')).astimezone().replace(tzinfo=None)
    return datetime.fromisoformat(t)


def metrik_kasus_tim(mulai):
    hari_ini = date.today()
    sb_a = mulai - timedelta(days=JENDELA)
    awal = min(sb_a, hari_ini - timedelta(days=29))     # 30 hari = rentang bawaan menu Kasus Support
    rows, hal = [], 1
    try:
        while True:
            r = subprocess.run([API_SH, f'/api/api/kasus-support?per_page=200&page={hal}&dari={awal}&sampai={hari_ini}'],
                               capture_output=True, text=True, timeout=120)
            d = json.loads(r.stdout.splitlines()[0])
            rows += d['data']
            if hal >= d['meta']['last_page']:
                break
            hal += 1
    except Exception as e:  # noqa: BLE001
        return {'galat': f'CRM: {str(e)[:200]}'}
    sekarang_dt = datetime.now()
    pesan = _pesan_kasus([k for k in rows if k['status'] == 'selesai'])
    for k in rows:
        k['_mulai'] = _waktu_crm(k['mulai'])
        k['_terakhir'] = _waktu_crm(k['terakhir'])
        k['_lama'] = _lama_kasus(k, pesan)
        k['_orang'] = sorted({(j.get('user') or {}).get('name') or str(j.get('user_id')) for j in k.get('jurnal') or []})
        k['_catatan'] = bool((k.get('catatan') or '').strip())
    sb = [k for k in rows if sb_a <= k['_mulai'].date() < mulai]
    ss = [k for k in rows if k['_mulai'].date() >= mulai]
    kemarin = hari_ini - timedelta(days=1)
    hari_sb, hari_ss = _hari(sb_a, mulai - timedelta(days=1)), _hari(mulai, kemarin)   # per hari: hari penuh saja
    per_hari_ss = round(sum(1 for k in ss if k['_mulai'].date() <= kemarin) / hari_ss, 1) if hari_ss else None
    lama = lambda xs: round(statistics.median([k['_lama'] for k in xs if k['_lama'] is not None]), 1) if any(k['_lama'] is not None for k in xs) else None  # noqa: E731
    pct = lambda xs, f: round(100 * sum(1 for k in xs if f(k)) / len(xs)) if xs else None  # noqa: E731
    angka = [_angka('Kasus per hari', round(len(sb) / hari_sb, 1) if hari_sb else None, per_hari_ss, 'kasus', None,
                    'Hari penuh saja (sampai kemarin)'),
             _angka('Lama sampai selesai (median)', lama(sb), lama(ss), 'jam', 'turun',
                    'Dari chat pertama sampai ditandai selesai tim (atau balasan tim terakhir bila selesai menurut AI/klien diam), '
                    'tanpa waktu menunggu balasan klien (rekaman WA)'),
             _angka('Kasus ada penangan', None, pct(ss, lambda k: k.get('penangan_id')), '%', 'naik', 'Tombol Tangani kasus ditekan'),
             _angka('Kasus ada catatan', None, pct(ss, lambda k: k['_catatan']), '%', 'naik',
                    'Catatan = history untuk shift berikutnya'),
             _angka('Kasus pindah tangan (handover)', None, sum(1 for k in ss if len(k['_orang']) >= 2), 'kasus', None,
                    'Jurnal kasus diisi ≥2 orang (Ambil alih)')]
    tunggu = [k for k in rows if k['status'] == 'menunggu_tim']
    tanpa_cat = sorted([k for k in tunggu if not k['_catatan'] and (sekarang_dt - k['_terakhir']).total_seconds() > 86400],
                       key=lambda k: k['_terakhir'])
    per_orang = {}
    for k in ss:
        if k.get('penangan'):
            o = per_orang.setdefault(k['penangan']['name'], {'pegang': 0, 'catatan': 0, 'menit': 0})
            o['pegang'] += 1
            if k['_lama'] is not None:
                o.setdefault('lama', []).append(k['_lama'])
        for j in k.get('jurnal') or []:
            nm = (j.get('user') or {}).get('name') or str(j.get('user_id'))
            per_orang.setdefault(nm, {'pegang': 0, 'catatan': 0, 'menit': 0})['menit'] += (j.get('time') or 0) / 60
        if k['_catatan'] and k.get('catatan_oleh'):
            per_orang.setdefault(str(k['catatan_oleh']), {'pegang': 0, 'catatan': 0, 'menit': 0})['catatan'] += 1
    # Fokus user 17 Okt: siapa mengerjakan & berapa lama sampai selesai; catatan handover bukan sorotan utama
    teks = [f"{nm}: {o['pegang']} kasus dipegang, selesai median {round(statistics.median(o['lama']) * 60)} mnt, "
            f"{sum(x > 24 for x in o['lama'])} kasus >1 hari, {round(o['menit'])} mnt di jurnal"
            if o.get('lama') else f"{nm}: {o['pegang']} kasus dipegang, {round(o['menit'])} mnt di jurnal"
            for nm, o in sorted(per_orang.items(), key=lambda x: -x[1]['pegang'])]
    teks += [f"Menunggu tim tanpa catatan: {k['nomor']} · {k.get('web') or k.get('nama') or '-'} · {k.get('jenis') or '-'} · "
             f"diam sejak {k['_terakhir'].strftime('%d/%m')} · {(k.get('penangan') or {}).get('name') or 'belum ada penangan'}"
             for k in tanpa_cat[:15]]
    ringkasan = (f"Sejak {mulai.day} {BULAN_ID[mulai.month - 1]}: {len(ss)} kasus" + (f" ({per_hari_ss}/hari)" if per_hari_ss else '') + ", "
                 f"{pct(ss, lambda k: k.get('penangan_id')) or 0}% ada penangan, {pct(ss, lambda k: k['_catatan']) or 0}% ada catatan, "
                 f"{sum(1 for k in ss if len(k['_orang']) >= 2)} pindah tangan. Lama sampai selesai median {lama(ss)} jam "
                 f"(sebelumnya {lama(sb)} jam). Menunggu tim sekarang {len(tunggu)}, {len(tanpa_cat)} di antaranya diam >1 hari tanpa catatan.")
    return {'judul': 'Penanganan kasus di menu Kasus Support (CRM)', 'angka': angka, 'ringkas': ringkasan,
            'sorot': [{'label': 'Menunggu tim', 'nilai': len(tunggu), 'buruk': len(tunggu) > 20},
                      {'label': 'Diam >1 hari tanpa catatan', 'nilai': len(tanpa_cat), 'buruk': len(tanpa_cat) > 0},
                      {'label': 'Menunggu tim tanpa penangan', 'nilai': sum(1 for k in tunggu if not k.get('penangan_id')),
                       'buruk': any(not k.get('penangan_id') for k in tunggu)}],
            'daftar_teks': teks,
            'periode': {'sebelum': [sb_a.isoformat(), (mulai - timedelta(days=1)).isoformat()],
                        'sesudah': [mulai.isoformat(), hari_ini.isoformat()]},
            'ket': 'Data menu Tim Support → Kasus Support di new.vd.net (kasus nyata: klien membalas, bukan "bukan kasus"). '
                   'Penangan, catatan dan jurnal baru ada sejak menu dipakai, jadi angka itu tanpa pembanding. '
                   'Menunggu tim dihitung 30 hari terakhir, sama dengan rentang bawaan menu.'}


KASUS_MENU_SEJAK = date(2026, 10, 2)   # rilis menu Kasus Support: penangan & jurnal baru ada sejak ini
# Nama CRM → nama di token.json. Agung di CRM bernama "Fajar Agung cahyo Romadhon", jangan dicocokkan per kata pertama.
NAMA_SUPPORT = {'Niken Ayu Anjaratri': 'Niken', 'Agus Dwi Yulianto': 'Agus', 'Fajar Irawan': 'Fajar',
                'Fajar Agung cahyo Romadhon': 'Agung'}
JENIS_LABEL = {'web_down': 'Web down/error', 'panduan': 'Panduan', 'login_akses': 'Login/akses', 'ubah_konten': 'Ubah konten',
               'tampilan_fitur': 'Tampilan/fitur', 'hosting_penuh': 'Hosting penuh', 'perpanjangan': 'Perpanjangan',
               'email': 'Email', 'lainnya': 'Lainnya', 'order_baru': 'Order baru', 'domain_ssl': 'Domain/SSL',
               'google_seo': 'Google/SEO', 'file_backup': 'File/backup', 'keamanan': 'Keamanan'}
KASUS_AI_MIN = 3                       # minimal kasus per kelompok sebelum median dibandingkan


def _domain_web(x):
    x = re.sub(r'^https?://', '', (x or '').lower().strip())
    return re.sub(r'^www\.', '', x).split('/')[0]


def _kasus_crm(dari, sampai):
    rows, hal = [], 1
    while True:
        r = subprocess.run([API_SH, f'/api/api/kasus-support?per_page=200&page={hal}&dari={dari}&sampai={sampai}'],
                           capture_output=True, text=True, timeout=120)
        d = json.loads(r.stdout.splitlines()[0])
        rows += d['data']
        if hal >= d['meta']['last_page']:
            return rows
        hal += 1


def _nama_support(n):
    return NAMA_SUPPORT.get(n) or (n or '').split(' ')[0]


def _kasus_orang_ai(k, sesi):
    """(penangan, semua yang ikut menangani, yang memakai Claude untuk kasus ini) — nama pendek seperti token.json."""
    detik = lambda x: datetime.fromisoformat(x.replace('Z', '+00:00')).timestamp()  # noqa: E731
    dom, hp = _domain_web(k.get('web')), (k.get('nomor') or '')[-9:]
    pegang = _nama_support(k['penangan']['name']) if k.get('penangan') else None
    ikut = {_nama_support((j.get('user') or {}).get('name')) for j in k.get('jurnal') or []} | ({pegang} if pegang else set())
    ikut.discard('')
    a, b = detik(k['mulai']) - 3600, detik(k['terakhir']) + 3 * 3600
    ai = set()
    for o in ikut:
        for s in sesi.get(o, []):
            jd = (s.get('judul') or '').lower()
            if s['mulai'] <= b and s['akhir'] >= a and (('.' in dom and dom in jd) or (len(hp) == 9 and hp in re.sub(r'\D', '', jd))):
                ai.add(o)
    return pegang, ikut, ai


def _pesan_kasus(rows):
    """{(akun, nomor): [(waktu, dari_tim)]} dari perekam WA untuk kasus-kasus ini; kanal yang gagal dilewati."""
    if not rows:
        return {}
    awal = min(_waktu_crm(k['mulai']) for k in rows).date()
    akhir = max(_waktu_crm(k['terakhir']) or _waktu_crm(k['mulai']) for k in rows).date()
    hasil = {}
    for akun in {k.get('akun') for k in rows if k.get('akun')}:
        perlu = {k['nomor'] for k in rows if k.get('akun') == akun}
        try:
            pesan = _pesan_rekam(akun, awal, akhir)
        except Exception:  # noqa: BLE001 — perekam tak terjangkau: kasus kanal ini dihitung penuh
            continue
        for m in pesan:
            if m['n'] in perlu:
                hasil.setdefault((akun, m['n']), []).append((datetime.fromisoformat(m['w'][:19]), m['kami']))
    return hasil


def _lama_kasus(k, pesan=None):
    """Jam dari chat pertama sampai selesai (ditandai tim, atau balasan tim terakhir bila selesai menurut AI/klien diam),
    TANPA waktu menunggu klien (arahan user 17 Okt): jeda dari pesan tim sampai balasan klien berikutnya tidak dihitung.
    Jeda yang diakhiri pesan tim (tim sedang memeriksa/mengerjakan) tetap dihitung. Tanpa rekaman WA → dihitung penuh."""
    if k['status'] != 'selesai':
        return None
    mulai = _waktu_crm(k['mulai'])
    akhir = _waktu_crm(k['status_at']) if k.get('status_dari') == 'tim' else (_waktu_crm(k.get('terakhir_tim')) or _waktu_crm(k['terakhir']))
    if not akhir:
        return None
    urut = sorted(x for x in (pesan or {}).get((k.get('akun'), k.get('nomor')), []) if mulai <= x[0] <= akhir)
    if not urut:
        return max((akhir - mulai).total_seconds() / 3600, 0)
    detik, t0, tim0 = 0, mulai, False
    for t, tim in urut + [(akhir, True)]:     # ditandai selesai = langkah tim
        if not (tim0 and not tim):            # tim → klien = menunggu klien, dilewati
            detik += (t - t0).total_seconds()
        t0, tim0 = t, tim
    return max(detik / 3600, 0)


def metrik_kasus_ai(mulai):
    """Kasus per anggota Support + kasus mana yang dikerjakan dengan Claude Code.

    Kasus dianggap pakai AI bila ada sesi Claude milik orang yang menangani kasus itu (penangan/jurnal) yang
    judulnya menyebut domain web kasus atau 9 digit akhir nomor HP klien, dan sesinya berjalan antara 1 jam
    sebelum chat pertama sampai 3 jam sesudah chat terakhir. Waktu kerja = total menit jurnal kasus."""
    awal = max(mulai, KASUS_MENU_SEJAK)
    hari_ini = date.today()
    try:
        rows = _kasus_crm(awal, hari_ini)
    except Exception as e:  # noqa: BLE001
        return {'galat': f'CRM: {str(e)[:200]}'}
    try:
        t = json.loads(TOKEN_JSON.read_text())
    except (OSError, ValueError):
        return {'galat': 'token.json tidak terbaca'}
    sesi = {p['nama']: p.get('sesi') or [] for p in t.get('pengguna') or [] if p.get('divisi') == 'Support'}
    orang, jenis = {}, {}
    for k in rows:
        pegang, ikut, ai = _kasus_orang_ai(k, sesi)
        menit = sum(j.get('time') or 0 for j in k.get('jurnal') or []) / 60
        selesai = k['status'] == 'selesai'
        for o in ikut:
            x = orang.setdefault(o, {'nama': o, 'pegang': 0, 'ikut': 0, 'selesai': 0, 'ai': 0, 'm_ai': [], 'm_non': []})
            x['ikut'] += 1
            x['pegang'] += o == pegang
            x['selesai'] += selesai
            x['ai'] += o in ai
            if selesai and menit > 0:
                x['m_ai' if o in ai else 'm_non'].append(menit)
        if selesai and menit > 0:
            jj = jenis.setdefault(k.get('jenis') or 'lainnya', {'m_ai': [], 'm_non': []})
            jj['m_ai' if ai else 'm_non'].append(menit)
    if not orang:
        return {'galat': 'belum ada kasus bertangan di menu Kasus Support'}
    med = lambda xs: round(statistics.median(xs)) if xs else None  # noqa: E731
    mnt = lambda v: '–' if v is None else f'{v} mnt'  # noqa: E731
    baris_orang = []
    for o in sorted(orang.values(), key=lambda x: -x['ikut']):
        baris_orang.append([o['nama'], o['pegang'], o['ikut'], o['selesai'],
                            f"{o['ai']} ({round(100 * o['ai'] / o['ikut'])}%)", mnt(med(o['m_ai'])), mnt(med(o['m_non']))])
    baris_jenis, cepat_ai, cepat_non = [], [], []
    for j, v in sorted(jenis.items(), key=lambda x: -(len(x[1]['m_ai']) + len(x[1]['m_non']))):
        ma, mn = med(v['m_ai']), med(v['m_non'])
        if len(v['m_ai']) >= KASUS_AI_MIN and len(v['m_non']) >= KASUS_AI_MIN:
            hasil = 'pakai AI lebih cepat' if ma < mn else 'tanpa AI lebih cepat' if ma > mn else 'sama'
            (cepat_ai if ma < mn else cepat_non if ma > mn else []).append(JENIS_LABEL.get(j, j))
        else:
            hasil = 'data belum cukup'
        baris_jenis.append([JENIS_LABEL.get(j, j), f"{mnt(ma)} ({len(v['m_ai'])})", f"{mnt(mn)} ({len(v['m_non'])})", hasil])
    n_ai = sum(o['ai'] for o in orang.values())
    semua_ai = [m for v in jenis.values() for m in v['m_ai']]
    semua_non = [m for v in jenis.values() for m in v['m_non']]
    tgl = f"{awal.day} {BULAN_ID[awal.month - 1]}"
    per_orang = ', '.join(f"{o['nama']} {o['ikut']}" for o in sorted(orang.values(), key=lambda x: -x['ikut']))
    # Perbandingan menit pakai AI vs tanpa AI disembunyikan dulu (permintaan user 17 Okt); baris_jenis, cepat_ai, kolom
    # menit di baris_orang tetap dihitung supaya mudah ditampilkan lagi.
    ringkasan = (f"Sejak {tgl}: {len(rows)} kasus. Ditangani per orang (penangan atau jurnal): {per_orang}. "
                 f"Dikerjakan pakai Claude: {sum(len(v['m_ai']) for v in jenis.values())} kasus selesai.")
    return {'judul': 'Kasus Support per orang & pakai AI', 'ringkas': ringkasan,
            'sorot': [{'label': 'Kasus sejak ' + tgl, 'nilai': len(rows)},
                      {'label': 'Kasus × orang pakai Claude', 'nilai': n_ai}],
            'tabel': [{'judul': 'Per orang',
                       'kolom': ['Nama', 'Dipegang', 'Ikut menangani', 'Selesai', 'Pakai Claude'],
                       'baris': [b[:5] for b in baris_orang]}],
            'periode': {'sesudah': [awal.isoformat(), hari_ini.isoformat()]},
            'ket': 'Data kasus dari menu Kasus Support CRM (penangan dan jurnal baru ada sejak 2 Okt). Dipegang = penangan kasus; '
                   'ikut menangani = penangan atau punya jurnal di kasus itu (handover dihitung untuk keduanya). Pakai Claude = '
                   'ada sesi Claude Code orang itu yang judulnya menyebut domain atau nomor HP klien, berjalan 1 jam sebelum chat '
                   'pertama sampai 3 jam sesudah chat terakhir; sesi yang judulnya tidak menyebut domain/nomor tidak terhitung, jadi '
                   'angka pakai AI adalah batas bawah.'}


SKEMA_KASUS_CLAUDE = {
    'type': 'object', 'required': ['kasus'],
    'properties': {'kasus': {'type': 'array', 'items': {
        'type': 'object', 'required': ['id', 'menit', 'catatan'],
        'properties': {
            'id': {'type': 'integer'},
            'menit': {'type': 'integer', 'description': 'perkiraan menit kerja Claude, bilangan bulat'},
            'catatan': {'type': 'string', 'description': 'maks 12 kata: apa yang dikerjakan Claude / apa yang tetap menunggu klien atau pihak lain'},
        }}}},
}

PROMPT_KASUS_CLAUDE = """Velocity Developer (jasa pembuatan website, Indonesia) punya tim Support yang menangani chat klien di WA.
Untuk tiap kasus di bawah, perkirakan berapa MENIT KERJA yang dibutuhkan Claude Code bila Claude yang mengerjakan.

Yang bisa dilakukan Claude: membaca chat & menulis balasan untuk dikirim tim, SSH ke server hosting Velocity
(DirectAdmin/cPanel), WP-CLI (buat/reset user, update WP/plugin, cek error, ubah konten/tema/fitur), cek HTTP/DNS/SSL/kuota,
membaca log, menulis panduan langkah demi langkah.
Yang TIDAK bisa: menunggu/menghubungi klien, akses akun Google/email pribadi klien, mengubah DNS di nameserver pihak lain,
keputusan penjualan (order baru cukup diarahkan ke CS).

Hitung hanya waktu kerja (termasuk membaca chat dan menulis balasan), BUKAN waktu menunggu klien. Anggap akses server sudah ada.
Kasus yang cukup dijawab/diarahkan: 1–3 menit. Jangan melebih-lebihkan; perkiraan yang jujur.

KASUS (id · jenis · jumlah pesan klien/tim · rangkuman):
"""


def _perkiraan_claude(tgl, kasus):
    """{id: (menit, catatan)} dari Claude untuk kasus satu hari; disimpan per tanggal supaya pantau ulang tidak memanggil lagi."""
    berkas = DIR / f'kasus-harian-{tgl}.json'
    try:
        lama = json.loads(berkas.read_text())
        if {str(k['id']) for k in kasus} <= set(lama):
            return {int(i): tuple(v) for i, v in lama.items()}
    except (OSError, ValueError):
        pass
    prompt = PROMPT_KASUS_CLAUDE + '\n'.join(
        f"- {k['id']} · {JENIS_LABEL.get(k.get('jenis') or '', k.get('jenis') or '-')} · {k.get('pesan_klien')}/{k.get('pesan_tim')} · "
        f"{(k.get('rangkuman') or '(belum ada rangkuman)').replace(chr(10), ' ')[:500]}" for k in kasus)
    run = subprocess.run([CLAUDE, '-p', '--model', 'sonnet', '--output-format', 'json', '--no-session-persistence',
                          '--tools', '', '--json-schema', json.dumps(SKEMA_KASUS_CLAUDE)],
                         input=prompt, capture_output=True, text=True, timeout=600, cwd='/tmp')
    hasil = json.loads(run.stdout)
    _catat_pemakaian(hasil, mode='kasus_harian')
    data = (hasil.get('structured_output') or {}).get('kasus')
    if not isinstance(data, list):
        raise ValueError(str(hasil.get('result') or 'tanpa keluaran')[:200])
    keluar = {int(x['id']): (int(x['menit']), str(x.get('catatan') or '')[:120]) for x in data if 'id' in x and 'menit' in x}
    berkas.write_text(json.dumps(keluar, ensure_ascii=False))
    return keluar


def metrik_kasus_harian(mulai):
    """Laporan kasus Support kemarin (hari penuh): lama selesai, menit kerja tim, perkiraan menit kerja Claude.

    Diurutkan dari lama selesai terlama. Pantau menambahkan ringkasannya sebagai kondisi harian (lihat pantau)."""
    tgl = date.today() - timedelta(days=1)
    try:
        rows = _kasus_crm(tgl, tgl)
    except Exception as e:  # noqa: BLE001
        return {'galat': f'CRM: {str(e)[:200]}'}
    if not rows:
        return {'galat': f'tidak ada kasus {tgl.isoformat()}'}
    try:
        t = json.loads(TOKEN_JSON.read_text())
        sesi = {p['nama']: p.get('sesi') or [] for p in t.get('pengguna') or [] if p.get('divisi') == 'Support'}
    except (OSError, ValueError):
        sesi = {}
    try:
        cl, galat_cl = _perkiraan_claude(tgl.isoformat(), rows), None
    except Exception as e:  # noqa: BLE001 — tabel tetap tampil tanpa kolom Claude
        cl, galat_cl = {}, f'Perkiraan Claude gagal: {type(e).__name__}: {str(e)[:150]}'
    data, pesan = [], _pesan_kasus(rows)
    for k in rows:
        pegang, _, ai = _kasus_orang_ai(k, sesi)
        lama = _lama_kasus(k, pesan)
        data.append({'k': k, 'pegang': pegang or '-', 'ai': ai, 'lama': None if lama is None else round(lama * 60),
                     'tim': round(sum(j.get('time') or 0 for j in k.get('jurnal') or []) / 60),
                     'cl': cl.get(k['id'], (None, ''))})
    data.sort(key=lambda x: (x['lama'] is None, -(x['lama'] or 0)))
    mnt = lambda v: '–' if v is None else f'{v} mnt'  # noqa: E731
    baris, detail = [], []
    for x in data:
        k = x['k']
        web = k.get('web') or k.get('nama') or '-'
        baris.append([k.get('nomor') or '-', (k.get('akun') or '').replace('wa-support-', ''), web if len(web) <= 32 else web[:30] + '…',
                      JENIS_LABEL.get(k.get('jenis') or '', k.get('jenis') or '-'), x['pegang'],
                      mnt(x['lama']) if k['status'] == 'selesai' else 'belum', mnt(x['tim']), mnt(x['cl'][0])])
        detail.append(' · '.join(t for t in [(k.get('rangkuman') or '').replace('\n', ' ').strip(),
                                             f"Claude: {x['cl'][1]}" if x['cl'][1] else '',
                                             f"{'/'.join(sorted(x['ai']))} sudah pakai Claude" if x['ai'] else ''] if t))
    selesai = [x['lama'] for x in data if x['lama'] is not None]
    tot_tim, tot_cl = sum(x['tim'] for x in data), sum(x['cl'][0] or 0 for x in data)
    nama_tgl = f"{tgl.day} {BULAN_ID[tgl.month - 1]}"
    ringkasan = (f"Kasus {nama_tgl}: {len(rows)} kasus, {len(selesai)} selesai dengan median lama selesai "
                 f"{round(statistics.median(selesai)) if selesai else '–'} mnt. Total kerja tim {tot_tim} mnt"
                 + (f", perkiraan bila dikerjakan Claude {tot_cl} mnt." if cl else '.'))
    terlama = '\n'.join(f"- {r[2]} ({r[0]}): selesai {r[5]}, kerja tim {r[6]}, Claude {r[7]}" for r in baris[:5])
    return {'judul': f'Kasus Support {nama_tgl}: lama selesai vs perkiraan Claude', 'ringkas': ringkasan,
            'sorot': [{'label': 'Kasus kemarin', 'nilai': len(rows)},
                      {'label': 'Kerja tim (mnt)', 'nilai': tot_tim},
                      *([{'label': 'Perkiraan Claude (mnt)', 'nilai': tot_cl}] if cl else [])],
            'tabel': [{'judul': f'Kasus {nama_tgl}, urut dari lama selesai terlama',
                       'kolom': ['Nomor WA', 'Kanal', 'Web / klien', 'Jenis', 'Penangan', 'Lama selesai', 'Kerja tim',
                                 'Perkiraan Claude'], 'kanan': [5, 6, 7], 'baris': baris, 'detail': detail}],
            'catatan': galat_cl, 'tanggal': tgl.isoformat(),
            'kondisi_harian': f"Laporan kasus {nama_tgl} (otomatis). {ringkasan}\n\n"
                              f"5 kasus paling lama selesai:\n{terlama}\n\nTabel lengkap semua kasus ada di bagian metrik kartu ini.",
            'periode': {'sesudah': [tgl.isoformat(), tgl.isoformat()]},
            'ket': 'Lama selesai = dari chat pertama sampai ditandai selesai, tanpa waktu menunggu balasan klien (jeda dari pesan tim '
                   'sampai klien membalas, dari rekaman WA; tanpa rekaman dihitung penuh). Kerja tim = total menit '
                   'jurnal. Perkiraan Claude = perkiraan menit kerja Claude Code bila akses server sudah ada, tanpa waktu menunggu klien '
                   '(Claude Sonnet, dari rangkuman kasus; bukan hasil ukur). "sudah pakai Claude" = ada sesi Claude penangan yang '
                   'judulnya menyebut domain/nomor kasus.'}


KASUS_MEETING = DIR / 'kasus-meeting.json'   # [{nomor, kasus, tanggal, catatan, temuan, ditambah}] — ditandai user untuk meeting


def tandai_kasus_meeting(nomor, catatan, kasus_id=None, temuan=''):
    """Tambah kasus ke tabel meeting. Tanpa kasus_id = kasus terbaru nomor itu dalam 30 hari."""
    nomor = re.sub(r'\D', '', nomor)
    rows = [k for k in _kasus_crm(date.today() - timedelta(days=30), date.today()) if (k.get('nomor') or '') == nomor]
    k = next((k for k in rows if k['id'] == kasus_id), None) if kasus_id else max(rows, key=lambda k: k['mulai'], default=None)
    if not k:
        return f'kasus {kasus_id or nomor} tidak ada di Kasus Support 30 hari terakhir'
    with terkunci():
        daftar = json.loads(KASUS_MEETING.read_text()) if KASUS_MEETING.exists() else []
        daftar = [x for x in daftar if x['kasus'] != k['id']]
        daftar.append({'nomor': nomor, 'kasus': k['id'], 'tanggal': _waktu_crm(k['mulai']).date().isoformat(),
                       'catatan': catatan, 'temuan': temuan, 'ditambah': sekarang()})
        KASUS_MEETING.write_text(json.dumps(daftar, ensure_ascii=False, indent=1))
    return None


def metrik_kasus_meeting(mulai):
    """Tabel kasus yang ditandai untuk dibahas di meeting (lihat tandai_kasus_meeting), data kasus diambil ulang dari CRM."""
    daftar = json.loads(KASUS_MEETING.read_text()) if KASUS_MEETING.exists() else []
    if not daftar:
        return {'galat': 'belum ada kasus yang ditandai untuk meeting'}
    tgl = sorted(x['tanggal'] for x in daftar)
    rows = {k['id']: k for k in _kasus_crm(tgl[0], tgl[-1])}
    try:
        t = json.loads(TOKEN_JSON.read_text())
        sesi = {p['nama']: p.get('sesi') or [] for p in t.get('pengguna') or [] if p.get('divisi') == 'Support'}
    except (OSError, ValueError):
        sesi = {}
    pesan = _pesan_kasus(list(rows.values()))
    baris, detail = [], []
    for x in sorted(daftar, key=lambda x: x['tanggal'], reverse=True):
        k = rows.get(x['kasus'])
        if not k:
            baris.append([x['tanggal'], x['nomor'], '-', '-', '-', '-', '-', '-'])
            detail.append(' · '.join(s for s in [f"Catatan meeting: {x['catatan']}", x.get('temuan') or 'Kasus tidak ditemukan lagi di CRM.'] if s))
            continue
        pegang, _, ai = _kasus_orang_ai(k, sesi)
        lama = _lama_kasus(k, pesan)
        baris.append([x['tanggal'], x['nomor'], k.get('web') or k.get('nama') or '-',
                      JENIS_LABEL.get(k.get('jenis') or '', k.get('jenis') or '-'), pegang or '-',
                      f'{round(lama * 60)} mnt' if lama is not None else 'belum',
                      f"{round(sum(j.get('time') or 0 for j in k.get('jurnal') or []) / 60)} mnt",
                      ('Ya, ' + '/'.join(sorted(ai))) if ai else 'Tidak'])
        detail.append(' · '.join(s for s in [f"Catatan meeting: {x['catatan']}", (k.get('rangkuman') or '').replace('\n', ' ').strip(),
                                             f"Temuan: {x['temuan']}" if x.get('temuan') else ''] if s))
    return {'judul': 'Kasus untuk dibahas di meeting', 'ringkas': f'{len(daftar)} kasus ditandai untuk dibahas di meeting.',
            'sorot': [{'label': 'Kasus untuk meeting', 'nilai': len(daftar)}],
            'tabel': [{'judul': 'Kasus untuk meeting (terbaru dulu)',
                       'kolom': ['Tanggal', 'Nomor WA', 'Web / klien', 'Jenis', 'Penangan', 'Lama selesai', 'Kerja tim',
                                 'Pakai Claude'], 'kanan': [5, 6], 'baris': baris, 'detail': detail}],
            'ket': 'Kasus dipilih manual untuk meeting. Lama selesai & kerja tim dihitung sama seperti laporan kasus harian. '
                   'Pakai Claude = ada sesi Claude penangan yang judulnya menyebut domain/nomor kasus.'}


HASIL_KONSEP = {'deal': 'Deal', 'nego': 'Nego', 'menunggu_klien': 'Menunggu klien', 'menunggu_rapat': 'Menunggu rapat/atasan',
                'dana_belum_ada': 'Dana belum ada', 'tidak_lanjut': 'Tidak lanjut', 'belum_ditawari': 'Belum ditawari'}   # = HASIL di konsep.vue
KONSEP_MAKS = 2_500_000   # batas harga konsep untuk pengerjaan <30 hari kerja (u-003)


def metrik_konsep_halaman(mulai):
    """Halaman Konsep CRM (chat konsep wa1/wa-meta): penawaran, telepon/meeting, hasil, order, tautan ke installer."""
    try:
        r = subprocess.run([API_SH, '/api/api/konsep-chat?per_page=200'], capture_output=True, text=True, timeout=120)
        d = json.loads(r.stdout.splitlines()[0])['data']
    except Exception as e:  # noqa: BLE001
        return {'galat': f'CRM konsep-chat: {str(e)[:200]}'}
    rp = lambda v: '–' if not v else f"Rp{v:,}".replace(',', '.')  # noqa: E731
    juta = lambda v: f'Rp{v / 1e6:.2f} jt'.replace('.', ',')  # noqa: E731
    n = {h: [x for x in d if x.get('hasil') == h] for h in HASIL_KONSEP}
    tawar = [x for x in d if x.get('harga_ditawarkan')]
    deal = n['deal']
    meet = [x for x in d if x.get('meeting')]
    lewat = [x for x in tawar if x['harga_ditawarkan'] > KONSEP_MAKS]
    tanpa_proyek = [x for x in d if not x.get('proyek_slug')]
    konversi = round(100 * len(deal) / len(tawar)) if tawar else 0
    urut = ('deal', 'nego', 'menunggu_rapat', 'menunggu_klien', 'dana_belum_ada', 'belum_ditawari', 'tidak_lanjut')
    baris, detail = [], []
    for x in sorted(d, key=lambda x: (urut.index(x['hasil']) if x.get('hasil') in urut else 9, -(x.get('harga_ditawarkan') or 0))):
        o = x.get('order') or {}
        judul = re.sub(r'^Rangkuman (Website |Aplikasi Android )?Konsep ', '', x.get('rangkuman_judul') or '') or '-'
        baris.append([HASIL_KONSEP.get(x.get('hasil'), x.get('hasil') or '-'), x['nomor'], judul if len(judul) <= 40 else judul[:38] + '…',
                      rp(x.get('harga_ditawarkan')), x.get('lama_ditawarkan') or '–', str(len(x.get('meeting') or [])),
                      (x.get('proyek_slug') or '–') + (f" ({x['proyek_tahap']})" if x.get('proyek_tahap') else ''),
                      o.get('nama_web') or '–'])
        detail.append(x.get('hasil_alasan') or '')
    return {'judul': 'Halaman Konsep: penawaran sampai deal',
            'ringkas': (f"{len(d)} chat konsep: {len(tawar)} sudah diberi harga, {len(deal)} deal ({juta(sum(x['harga_ditawarkan'] or 0 for x in deal))}, "
                        f"konversi {konversi}%). Nego {len(n['nego'])}, menunggu klien {len(n['menunggu_klien'])}, menunggu rapat "
                        f"{len(n['menunggu_rapat'])}, dana belum ada {len(n['dana_belum_ada'])}, tidak lanjut {len(n['tidak_lanjut'])}, "
                        f"belum ditawari {len(n['belum_ditawari'])}. {len(meet)} sudah telepon/meeting ({sum(x['hasil'] == 'deal' for x in meet)} deal). "
                        f"{len(lewat)} penawaran di atas Rp2,5 jt; {len(tanpa_proyek)} chat belum punya project installer."),
            'angka': [_angka('Konversi penawaran jadi deal', None, konversi, '%', 'naik', f'{len(deal)} dari {len(tawar)} yang sudah diberi harga'),
                      _angka('Penawaran di atas Rp2,5 jt', None, len(lewat), '', 'turun',
                             ', '.join(f"{rp(x['harga_ditawarkan'])} ({x.get('lama_ditawarkan') or '?'})" for x in lewat) or 'tidak ada'),
                      _angka('Chat tanpa project installer', None, len(tanpa_proyek), '', 'turun',
                             'tanpa estimasi lama pengerjaan dari installer Aplikasi Custom')],
            'sorot': [{'label': 'Deal', 'nilai': len(deal)},
                      {'label': 'Menunggu klien + nego', 'nilai': len(n['menunggu_klien']) + len(n['nego'])},
                      {'label': 'Belum ditawari', 'nilai': len(n['belum_ditawari']), 'buruk': bool(n['belum_ditawari'])}],
            'tabel': [{'judul': 'Semua chat konsep (urut dari yang paling dekat deal)',
                       'kolom': ['Hasil', 'Nomor WA', 'Konsep', 'Harga', 'Lama', 'Telepon/meeting', 'Project installer', 'Order CRM'],
                       'kanan': [3, 5], 'baris': baris, 'detail': detail}],
            'ket': 'Sumber: halaman Konsep new-vd (chat wa1/wa-meta berlabel "konsep" atau ber-link preview installer, disetor tiap 10 menit). '
                   'Harga, lama, telepon/meeting dan hasil dibaca Claude dari chat; order = order CRM yang tersambung ke nomor itu.'}


LANGGANAN = DIR / 'langganan.json'   # daftar langganan perusahaan + status pengganti (u-017), diisi manual


def metrik_efisiensi_langganan(mulai):
    """Tiga tabel: langganan yang sudah diputus, sedang dikerjakan penggantinya, dan belum dikerjakan (nilai Rp/bulan)."""
    try:
        daftar = json.loads(LANGGANAN.read_text())['langganan']
    except (OSError, ValueError, KeyError) as e:
        return {'galat': f'{LANGGANAN.name}: {e}'}
    rp = lambda v: '–' if v is None else f"Rp{v:,}".replace(',', '.')  # noqa: E731
    urut = lambda xs: sorted(xs, key=lambda x: -(x['nilai'] or 0))  # noqa: E731
    putus = urut(x for x in daftar if x.get('diputus'))
    kerja = urut(x for x in daftar if x['dikerjakan'] and not x.get('diputus'))
    belum = urut(x for x in daftar if not x['dikerjakan'] and not x.get('diputus'))
    jml = lambda xs: sum(x['nilai'] or 0 for x in xs)  # noqa: E731
    total = jml(daftar)
    tanpa = lambda xs: f' + {n} pos belum ada nominal' if (n := sum(x['nilai'] is None for x in xs)) else ''  # noqa: E731
    juta = lambda v: f'Rp{v / 1e6:.2f} jt'.replace('.', ',') if v else 'Rp0'  # noqa: E731
    pct = lambda xs: f'{round(100 * jml(xs) / total)}%' if total else '–'  # noqa: E731
    return {'judul': 'Efisiensi langganan: sudah berhenti, dikerjakan, belum',
            'ringkas': (f"Sudah berhenti langganan {len(putus)} pos, hemat {juta(jml(putus))}/bln ({pct(putus)}). "
                        f"Sedang dikerjakan {len(kerja)} pos senilai {juta(jml(kerja))}/bln ({pct(kerja)}). "
                        f"Belum dikerjakan {len(belum)} pos senilai {juta(jml(belum))}/bln ({pct(belum)})."),
            'sorot': [{'label': 'Sudah berhenti langganan (Rp/bln)', 'nilai': rp(jml(putus)), 'baik': True},
                      {'label': 'Sedang dikerjakan (Rp/bln)', 'nilai': rp(jml(kerja))},
                      {'label': 'Belum dikerjakan (Rp/bln)', 'nilai': rp(jml(belum)), 'buruk': True}],
            'tabel': [{'judul': f'Sudah tidak langganan: {len(putus)} pos, hemat {rp(jml(putus))}/bulan' + tanpa(putus),
                       'kolom': ['Langganan', 'Rp/bulan', 'Pengganti', 'Berhenti'], 'kanan': [1],
                       'baris': [[x['nama'], rp(x['nilai']), x.get('pengganti', ''), f"{int(x['diputus'][8:])} {BULAN_ID[int(x['diputus'][5:7]) - 1]}"] for x in putus]},
                      {'judul': f'Sedang dikerjakan: {len(kerja)} pos, {rp(jml(kerja))}/bulan' + tanpa(kerja),
                       'kolom': ['Langganan', 'Rp/bulan', 'Pengganti', 'Progres'], 'kanan': [1],
                       'baris': [[x['nama'], rp(x['nilai']), x.get('pengganti', ''), x.get('progres', '')] for x in kerja]},
                      {'judul': f'Belum dikerjakan: {len(belum)} pos, {rp(jml(belum))}/bulan' + tanpa(belum),
                       'kolom': ['Langganan', 'Rp/bulan'], 'kanan': [1],
                       'baris': [[x['nama'], rp(x['nilai'])] for x in belum]}],
            'ket': f'Total {rp(total)}/bulan. Nilai dari sheet Pengeluaran Jenius + menu Langganan Velocity CRM (nominal dari user; '
                   f'langganan tahunan dibagi 12, USD kurs Rp18.000). "–" = nominal belum ada. Data diisi manual di {LANGGANAN}.'}


def _pakai_harian(p):
    """{tanggal: panggilan} satu orang dari token.json."""
    per_hari = {}
    for s in p.get('sesi') or []:
        for h, m in (s.get('hari') or {}).items():
            per_hari[h] = per_hari.get(h, 0) + sum(v[4] for v in m.values())
    return per_hari


def metrik_ai_orang(nama, mulai):
    try:
        t = json.loads(TOKEN_JSON.read_text())
    except (OSError, ValueError):
        return {'galat': 'token.json tidak terbaca'}
    p = next((x for x in t.get('pengguna') or [] if x['nama'].lower() == nama.lower()), None)
    if not p:
        return {'galat': f'{nama} tidak ada di data token'}
    rekan = [x for x in t['pengguna'] if x.get('divisi') == p.get('divisi') and x is not p]
    awal_data = date.fromtimestamp(t.get('pencatat_sejak') or 0) + timedelta(days=1)   # hari pertama pencatat tidak penuh
    kemarin = date.today() - timedelta(days=1)
    sb_a, sb_b = max(mulai - timedelta(days=JENDELA), awal_data), mulai - timedelta(days=1)
    ss_a, ss_b = mulai, kemarin
    harian = _pakai_harian(p)
    harian_rekan = [_pakai_harian(x) for x in rekan]

    def hari_kerja(a, b):
        # Minggu dilewati: Support hanya 2 orang tiap Minggu, jadi hari itu bukan pembanding yang adil
        return [a + timedelta(days=i) for i in range((b - a).days + 1) if (a + timedelta(days=i)).weekday() != 6]

    def ringkas(a, b):
        hari = hari_kerja(a, b)
        if not hari:
            return {'per_hari': None, 'aktif': None, 'rekan': None, 'n': 0}
        isi = [harian.get(h.isoformat(), 0) for h in hari]
        rekan_med = statistics.median([sum(r.get(h.isoformat(), 0) for h in hari) / len(hari) for r in harian_rekan]) if harian_rekan else None
        per_hari = sum(isi) / len(hari)
        return {'per_hari': round(per_hari), 'aktif': round(100 * sum(v > 0 for v in isi) / len(hari)),
                'rekan': round(100 * per_hari / rekan_med) if rekan_med else None, 'n': len(hari)}

    sb, ss = ringkas(sb_a, sb_b), ringkas(ss_a, ss_b)
    angka = [_angka('Panggilan Claude per hari kerja', sb['per_hari'], ss['per_hari'], '', 'naik'),
             _angka('Hari kerja memakai Claude', sb['aktif'], ss['aktif'], '%', 'naik'),
             _angka(f"Dibanding median rekan {p.get('divisi') or ''}".strip(), sb['rekan'], ss['rekan'], '%', 'naik',
                    '100% = sama dengan median rekan satu divisi')]
    seri = [{'t': (sb_a + timedelta(days=i)).isoformat(), 'v': harian.get((sb_a + timedelta(days=i)).isoformat(), 0)}
            for i in range((date.today() - sb_a).days + 1)]
    tgl = f"{mulai.day} {BULAN_ID[mulai.month - 1]}"
    hitung_mulai = mulai + timedelta(days=1)
    rek = lambda x: f"{x['rekan']}% dari median rekan" if x['rekan'] is not None else 'belum ada rekan divisi pembanding'  # noqa: E731
    if ss['n']:
        ringkasan = (f"Sejak {tgl}: {nama} rata-rata {ss['per_hari']} panggilan/hari kerja "
                     f"({rek(ss)}), sebelumnya {sb['per_hari']} ({rek(sb)}). "
                     f"Pembanding: {sb['n']} hari kerja sebelum vs {ss['n']} sesudah.")
    else:
        ringkasan = (f"Sebelum {tgl}: {nama} rata-rata {sb['per_hari']} panggilan/hari kerja ({rek(sb)}, "
                     f"{sb['n']} hari kerja). Angka sejak {tgl} mulai dihitung "
                     + ('besok.' if hitung_mulai == date.today() + timedelta(days=1) else f"{hitung_mulai.day} {BULAN_ID[hitung_mulai.month - 1]}."))
    return {'judul': f'Pemakaian AI {nama}', 'angka': angka, 'ringkas': ringkasan, 'seri': seri, 'seri_tanda': mulai.isoformat(),
            'periode': {'sebelum': [sb_a.isoformat(), sb_b.isoformat()], 'sesudah': [ss_a.isoformat(), ss_b.isoformat()]},
            'ket': f'Data pemakaian Claude baru tercatat sejak {awal_data.day} {BULAN_ID[awal_data.month - 1]}, jadi pembanding "sebelum" '
                   'sependek itu. Hari Minggu tidak dihitung. Hari ini belum ikut (belum penuh).'}


KELOMPOK_PAKET = (('Paket E', lambda p: p == 'Paket E'), ('Paket F', lambda p: p == 'Paket F'),
                  ('Paket biasa lain', lambda p: 'Biasa' in p),
                  ('Paket custom', lambda p: p == 'Paket G' or 'Custom' in p))
PERBAIKAN_RE = re.compile(r'paket[ -]biasa|paket e\b|paket f\b|theme-paket-biasa|dokumen-klien|site-finish|cari_logo|^installer:', re.I)


def metrik_installer_paket(mulai):
    try:
        rows = _get_json('http://127.0.0.1:9121/api/installer')['domains']
    except Exception as e:  # noqa: BLE001
        return {'galat': f'API installer: {e}'}
    sb_a, sb_b = mulai - timedelta(days=JENDELA), mulai - timedelta(days=1)
    run = []
    for r in rows:
        t = ((r.get('lama') or {}).get('terakhir') or {})
        if t.get('selesai') and t.get('mode') == 'apply':
            run.append((date.fromtimestamp(t['selesai']), str(t.get('hasil') or '').startswith('SUCCESS'), t.get('detik') or 0,
                        r.get('paket') or '', r.get('status')))
    tabel = []
    for nama, cocok in KELOMPOK_PAKET:
        def ringkas(a, b):
            isi = [x for x in run if a <= x[0] <= b and cocok(x[3])]
            ok = [x for x in isi if x[1]]
            return {'run': len(isi), 'ok': round(100 * len(ok) / len(isi)) if isi else None,
                    'lama': round(statistics.median([x[2] for x in ok]) / 60) if ok else None}
        sb, ss = ringkas(sb_a, sb_b), ringkas(mulai, date.today())
        dipegang = sum(1 for x in rows if cocok(x.get('paket') or '') and x.get('status') == 'dikerjakan webmaster')
        tabel.append({'kelompok': nama, 'sebelum': sb, 'sesudah': ss, 'dikerjakan_webmaster': dipegang})
    # Pekerjaan perbaikan: commit repo installer sejak tanggal pembanding yang menyentuh jalur paket biasa
    try:
        log = subprocess.run(['git', '-c', 'safe.directory=*', '-C', str(REPO), 'log', f'--since={mulai.isoformat()} 00:00',
                              '--format=%ad\t%s', '--date=short'], capture_output=True, text=True, timeout=20).stdout
        commit = [dict(zip(('tgl', 'judul'), b.split('\t', 1))) for b in log.splitlines() if '\t' in b]
    except (OSError, subprocess.SubprocessError):
        commit = []
    perbaikan = [c for c in commit if PERBAIKAN_RE.search(c['judul'])]
    ef = [t for t in tabel if t['kelompok'] in ('Paket E', 'Paket F')]
    ringkasan = ('Sejak ' + f"{mulai.day} {mulai.strftime('%b')}: "
                 + '; '.join(f"{t['kelompok']} {t['sesudah']['run']} run, berhasil {t['sesudah']['ok'] if t['sesudah']['ok'] is not None else '–'}%"
                             for t in ef)
                 + f". {len(perbaikan)} perbaikan installer paket biasa masuk repo.")
    return {'judul': 'Installer per paket', 'paket': tabel, 'ringkas': ringkasan,
            'daftar_teks': [f"{c['tgl'][5:]} · {c['judul']}" for c in perbaikan[:8]],
            'sorot': [{'label': 'Perbaikan paket biasa (commit)', 'nilai': len(perbaikan)}],
            'periode': {'sebelum': [sb_a.isoformat(), sb_b.isoformat()], 'sesudah': [mulai.isoformat(), date.today().isoformat()]},
            'ket': 'Run berhasil = installer selesai tanpa galat; belum mengukur seberapa banyak webmaster masih menambah isi. '
                   'Untuk itu catat temuan webmaster/revisi di kondisi.'}


SAPAAN_RE = re.compile(r'\b(pak|bu|bapak|ibu|kak|kakak|mas|mbak)\b', re.I)
SANTUN_RE = re.compile(r'terima ?kasih|makasih|\bmohon\b|\bmaaf\b|silak?h?an|berkenan|\btolong\b|dengan senang hati', re.I)
EMOJI_RE = re.compile('[\U0001F300-\U0001FAFF☀-➿]')
TEMPLAT_RE = re.compile(r'yang Bapak/Ibu kirimkan sudah kami kerjakan', re.I)
CACHE_BAHASA = 'bahasa-{akun}.json'


def _baca_env(p):
    cfg = {}
    try:
        for b in p.read_text().splitlines():
            b = b.strip()
            if b and not b.startswith('#') and '=' in b:
                k, _, v = b.partition('=')
                cfg[k.strip()] = v.strip().strip('"\'')
    except OSError:
        pass
    return cfg


def _pesan_rekam(akun, dari, sampai):
    """Semua pesan satu kanal dari perekam WA (tim & klien), urut waktu, ganda persis dibuang."""
    cfg = _baca_env(REKAM_ENV)
    semua, setelah = [], None
    while True:
        q = {'dari': dari.isoformat(), 'sampai': (sampai + timedelta(days=1)).isoformat(), 'akun': akun, 'limit': 5000}
        if setelah:
            q['setelah_id'] = setelah
        req = urllib.request.Request(cfg['REKAM_URL'].rstrip('/') + '/ekspor?' + urllib.parse.urlencode(q),
                                     headers={'X-Kunci': cfg['REKAM_KUNCI'], 'User-Agent': UA_BROWSER})
        with urllib.request.urlopen(req, timeout=120) as r:
            j = json.loads(r.read())
        semua += j.get('data') or []
        setelah = j.get('setelah_id_berikutnya')
        if not setelah:
            break
    lihat, hasil = set(), []
    for m in sorted(semua, key=lambda m: (m['waktu'], m['id'])):
        teks = (m.get('teks') or '').strip()
        kunci = (m['chat_nomor'], m['waktu'], teks, m.get('dari_kami'), m.get('jenis'))
        if kunci in lihat:
            continue
        lihat.add(kunci)
        hasil.append({'w': m['waktu'], 'n': m['chat_nomor'], 't': teks, 'kami': bool(m.get('dari_kami')), 'akun': akun})
    return hasil


def _pesan_tim(akun, dari, sampai):
    """Pesan teks tim (dari_kami) satu kanal dari perekam WA."""
    return [{'w': m['w'], 'n': m['n'], 't': m['t']} for m in _pesan_rekam(akun, dari, sampai) if m['kami'] and m['t']]


def _ciri_bahasa(pesan):
    isi = [m for m in pesan if not TEMPLAT_RE.search(m['t'])]   # templat laporan revisi selalu sama, tidak mencerminkan gaya
    if not isi:
        return {'n': 0}
    n = len(isi)
    pendek = [m for m in isi if len(m['t'].split()) <= 3 and not SAPAAN_RE.search(m['t']) and not EMOJI_RE.search(m['t'])]
    return {'n': n, 'sapaan': round(100 * sum(bool(SAPAAN_RE.search(m['t'])) for m in isi) / n),
            'santun': round(100 * sum(bool(SANTUN_RE.search(m['t'])) for m in isi) / n),
            'emoji': round(100 * sum(bool(EMOJI_RE.search(m['t'])) for m in isi) / n),
            'pendek': round(100 * len(pendek) / n),
            'kata': round(statistics.median([len(m['t'].split()) for m in isi]))}


SKEMA_BAHASA = {
    'type': 'object', 'required': ['skor_sebelum', 'skor_sesudah', 'kesimpulan', 'contoh_kurang', 'contoh_baik'],
    'properties': {
        'skor_sebelum': {'type': 'number', 'description': 'rata-rata keramahan 1–5 sampel SEBELUM'},
        'skor_sesudah': {'type': 'number', 'description': 'rata-rata keramahan 1–5 sampel SESUDAH'},
        'kesimpulan': {'type': 'string', 'description': '1–3 kalimat: ada perubahan atau tidak, dalam hal apa'},
        'contoh_kurang': {'type': 'array', 'maxItems': 3, 'items': {'type': 'object', 'required': ['asli', 'saran'],
                          'properties': {'asli': {'type': 'string'}, 'saran': {'type': 'string'}}},
                          'description': 'pesan SESUDAH yang masih kurang halus + versi lebih halus'},
        'contoh_baik': {'type': 'array', 'maxItems': 2, 'items': {'type': 'string'}, 'description': 'pesan SESUDAH yang sudah bagus'},
    },
}


def _nilai_bahasa_claude(akun, sb, ss, mulai):
    """Claude membandingkan sampel pesan sebelum/sesudah. Dihitung ulang paling sering tiap 3 hari (±$0,1)."""
    berkas = DIR / f'bahasa-{akun}-claude.json'
    try:
        lama = json.loads(berkas.read_text())
        if lama.get('mulai') == mulai.isoformat() and time.time() - lama['ts'] < 3 * 86400:
            return lama
    except (OSError, ValueError, KeyError):
        pass
    import random
    acak = random.Random(mulai.toordinal())
    pilih = lambda xs: [m['t'][:400] for m in acak.sample(xs, min(40, len(xs)))]  # noqa: E731
    sb_ok = [m for m in sb if not TEMPLAT_RE.search(m['t']) and len(m['t'].split()) >= 2]
    ss_ok = [m for m in ss if not TEMPLAT_RE.search(m['t']) and len(m['t'].split()) >= 2]
    if len(ss_ok) < 15:
        return {'galat': f'baru {len(ss_ok)} pesan sesudah {mulai.isoformat()}, tunggu data lebih banyak'}
    prompt = ('Pesan WhatsApp tim Revisi Velocity Developer (jasa pembuatan website) ke klien. Pemilik meminta tim memperhalus '
              f'bahasa ke klien mulai {mulai.isoformat()}. Nilai keramahan/kehalusan tiap pesan 1–5 (1 = ketus/kaku, '
              '3 = netral sopan, 5 = hangat, jelas, menghargai klien), lalu rata-ratakan per kelompok. Pesan pendek '
              'yang wajar ("baik pak, kami cek dulu") itu 3–4, bukan buruk. Bahasa Indonesia sehari-hari.\n\n'
              f'SEBELUM:\n' + '\n'.join(f'- {t}' for t in pilih(sb_ok)) + '\n\nSESUDAH:\n' + '\n'.join(f'- {t}' for t in pilih(ss_ok)))
    run = subprocess.run([CLAUDE, '-p', '--model', 'opus', '--output-format', 'json', '--no-session-persistence',
                          '--tools', '', '--json-schema', json.dumps(SKEMA_BAHASA)],
                         input=prompt, capture_output=True, text=True, timeout=600, cwd='/tmp')
    hasil = json.loads(run.stdout)
    _catat_pemakaian(hasil, mode='bahasa')
    data = hasil.get('structured_output')
    if not isinstance(data, dict):
        return {'galat': str(hasil.get('result') or 'tanpa keluaran')[:200]}
    data.update(ts=time.time(), mulai=mulai.isoformat(), waktu=sekarang(), n_sebelum=min(40, len(sb_ok)), n_sesudah=min(40, len(ss_ok)))
    berkas.write_text(json.dumps(data, ensure_ascii=False))
    return data


def metrik_bahasa(akun, mulai):
    sb_a, sb_b = mulai - timedelta(days=JENDELA), mulai - timedelta(days=1)
    try:
        pesan = _pesan_tim(akun, sb_a, date.today())
    except Exception as e:  # noqa: BLE001 — perekam tidak terjangkau
        return {'galat': f'perekam WA: {str(e)[:200]}'}
    sb = [m for m in pesan if _tgl(m['w']) <= sb_b]
    ss = [m for m in pesan if _tgl(m['w']) >= mulai]
    a, b = _ciri_bahasa(sb), _ciri_bahasa(ss)
    angka = [_angka('Pesan bersapaan (pak/bu/kak)', a.get('sapaan'), b.get('sapaan'), '%', 'naik'),
             _angka('Pesan berkata santun', a.get('santun'), b.get('santun'), '%', 'naik',
                    'terima kasih, mohon, maaf, silakan, berkenan'),
             _angka('Pesan pendek tanpa sapaan', a.get('pendek'), b.get('pendek'), '%', 'turun',
                    '≤3 kata tanpa sapaan/emoji, mis. "sudah", "iya", "transaksi apa?"'),
             _angka('Pesan dengan emoji', a.get('emoji'), b.get('emoji'), '%', None)]
    try:
        cl = _nilai_bahasa_claude(akun, sb, ss, mulai)
    except Exception as e:  # noqa: BLE001
        cl = {'galat': f'{type(e).__name__}: {str(e)[:150]}'}
    if 'galat' not in cl:
        angka.insert(0, _angka('Keramahan menurut Claude (1–5)', cl['skor_sebelum'], cl['skor_sesudah'], '', 'naik',
                               f"Sampel {cl['n_sebelum']} vs {cl['n_sesudah']} pesan, dinilai {cl['waktu'][:10]}"))
    ringkasan = (cl.get('kesimpulan') or f"Pesan tim bersapaan {b.get('sapaan')}% (sebelumnya {a.get('sapaan')}%), "
                 f"pesan pendek tanpa sapaan {b.get('pendek')}% (sebelumnya {a.get('pendek')}%).")
    return {'judul': f'Bahasa tim ke klien ({akun})', 'angka': angka, 'ringkas': ringkasan,
            'contoh': cl.get('contoh_kurang') or [], 'contoh_baik': cl.get('contoh_baik') or [],
            'catatan': cl.get('galat'),
            'periode': {'sebelum': [sb_a.isoformat(), sb_b.isoformat()], 'sesudah': [mulai.isoformat(), date.today().isoformat()]},
            'ket': f"{a.get('n', 0)} pesan sebelum vs {b.get('n', 0)} sesudah (templat laporan revisi tidak dihitung). "
                   'Persentase dihitung kode; skor keramahan dari Claude, diperbarui paling sering tiap 3 hari.'}


# ---------- kenaikan harga domain: apakah CS & AM sudah menginfo klien ----------

AKUN_CS = ('wa-perpanjangan-xl', 'wa1', 'wa2', 'wa3', 'wa-meta', 'wa-tsel')
AKUN_AM = ('wa-am',)
PENGINGAT_RE = re.compile(r'website bapak/ibu \*(?:www\.)?([^*\s]+)\* (?:akan|sudah) habis masa aktifnya (?:pada|sejak) tanggal', re.I)
PENAWARAN_RE = re.compile(r'biaya perpanjang(?:an)? web\s+\*?(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z]{2,})+)\*?\s*'
                          r'(?:totalnya\s*)?(?:rp\.?\s*)?(\d{1,3}(?:\.\d{3})+)', re.I)
BAYAR_RE = re.compile(r'pembayaran anda sdh sy terima|webnya sudah diperpanjang|pembayaran(?: ini|nya)? sudah (?:kami terima|masuk)', re.I)
INFO_NAIK_RE = re.compile(r'kenaikan|naik|penyesuaian harga|harga (?:baru|terbaru)', re.I)
HARGA_RE = re.compile(r'harga|biaya|domain|perpanjang', re.I)
KEBERATAN_RE = re.compile(r'mahal|kok naik|keberatan|(?:tidak|ga|gak|nggak|enggak) jadi|tidak (?:usah|perlu|akan) diperpanjang|'
                          r'tidak diperpanjang|berhenti dulu', re.I)
NOMOR_KANTOR_REKAM = ('6281311831406', '6285759136638', '6285600566674', '6287734973348', '6282334782971', '6281363471127',
                      '6287742295809', '6282136302531', '6285729319861', '6285701216057', '6285713553048')   # nomor kanal perekam
NOTIF_HARI = 30             # klien yang dikirimi pengingat/penawaran sampai 30 hari sebelum harga naik


def _rupiah(teks):
    return int(re.sub(r'\D', '', teks))


def metrik_harga_domain(arg, mulai):
    """arg 'com:206000:266000' — tld:harga lama:harga baru, berlaku sejak tanggal mulai update."""
    tld, lama, baru = arg.split(':')
    tld, lama, baru = '.' + tld.lstrip('.'), int(lama), int(baru)
    hari_ini = date.today()
    awal = mulai - timedelta(days=NOTIF_HARI)
    batas = mulai.isoformat()
    pesan = []
    for a in AKUN_CS + AKUN_AM:
        pesan += _pesan_rekam(a, awal, hari_ini)
    pesan.sort(key=lambda m: m['w'])
    nomor_kantor = set(NOMOR_KANTOR_REKAM)
    n = {}
    for m in pesan:
        if m['n'] in nomor_kantor:
            continue
        s = n.setdefault(m['n'], {'dom': set(), 'notif': [], 'tawar': [], 'bayar': [], 'info': [], 'klien': []})
        t = m['t']
        if not m['kami']:
            s['klien'].append(m)
            continue
        pg = PENGINGAT_RE.search(t)
        if pg and pg.group(1).lower().endswith(tld):
            s['dom'].add(pg.group(1).lower())
            s['notif'].append(m['w'])
            continue                                   # pengingat otomatis bukan follow up
        tw = PENAWARAN_RE.search(t)
        if tw and tw.group(1).lower().endswith(tld):
            dom = tw.group(1).lower()
            s['dom'].add(dom)
            rinci = re.search(r'domain\s*:?\s*(?:rp\.?\s*)?(\d{1,3}(?:\.\d{3})+)', t, re.I)
            s['tawar'].append({'w': m['w'], 'dom': dom, 'total': _rupiah(tw.group(2)), 'akun': m['akun'],
                               'domain': _rupiah(rinci.group(1)) if rinci else None})
        if BAYAR_RE.search(t):
            s['bayar'].append(m['w'])
        harga_baru = re.search(rf'{baru // 1000}[.,]?000|{baru // 1000}\s*(?:rb|ribu|k)\b', t, re.I)
        if m['w'] >= batas and ((INFO_NAIK_RE.search(t) and HARGA_RE.search(t)) or harga_baru or tw):
            s['info'].append(m)

    # Penawaran sesudah harga naik yang masih memakai harga lama:
    # rincian domain = harga lama, atau total sama persis dgn penawaran domain itu sebelum harga naik
    salah, benar = [], 0
    for nom, s in n.items():
        for tw in s['tawar']:
            if tw['w'] < batas:
                continue
            dulu = [x['total'] for x in s['tawar'] if x['dom'] == tw['dom'] and x['w'] < batas]
            if tw['domain'] == lama or (dulu and tw['total'] == dulu[-1]):
                salah.append((nom, tw))
            elif tw['domain'] == baru or (dulu and tw['total'] == dulu[-1] + baru - lama):
                benar += 1

    # Klien yang harus diinfo: sudah dikirimi pengingat / penawaran sebelum harga naik, belum bayar sebelum harga naik
    target = []
    for nom, s in n.items():
        notif = [w for w in s['notif'] if w < batas] + [x['w'] for x in s['tawar'] if x['w'] < batas]
        if not notif:
            continue
        if any(max(notif) <= b < batas for b in s['bayar']):
            continue
        ditawar = [x for x in s['tawar'] if x['w'] < batas]
        info = [m for m in s['info'] if not any(m['w'] == tw['w'] for _, tw in salah if _ == nom)]
        bayar = [b for b in s['bayar'] if b >= batas]
        balas = [m for m in s['klien'] if m['w'] >= (info[0]['w'] if info else batas)]
        if bayar:
            tanggapan = 'sudah bayar'
        elif any(KEBERATAN_RE.search(m['t']) for m in balas):
            tanggapan = 'keberatan'
        elif balas:
            tanggapan = 'membalas'
        else:
            tanggapan = 'belum membalas'
        target.append({'nomor': nom, 'dom': sorted(s['dom']), 'ditawar': ditawar[-1] if ditawar else None,
                       'notif': max(notif), 'info': info[0] if info else None, 'tanggapan': tanggapan})

    # Sudah bayar sesudah harga naik = beres, termasuk bila bayarnya lewat nomor lain dengan domain yang sama
    dom_lunas = {d for nom, s in n.items() if any(b >= batas for b in s['bayar']) for d in s['dom']}
    for x in target:
        x['lunas'] = x['tanggapan'] == 'sudah bayar' or bool(set(x['dom']) & dom_lunas)
    tawar_lama = [x for x in target if x['ditawar']]
    sudah = [x for x in target if x['info']]
    sudah_tawar = [x for x in tawar_lama if x['info'] or x['lunas']]
    lunas_saja = [x for x in tawar_lama if x['lunas'] and not x['info']]
    oleh = {'CS': sum(1 for x in sudah if x['info']['akun'] in AKUN_CS), 'AM': sum(1 for x in sudah if x['info']['akun'] in AKUN_AM)}
    tanggap = {k: sum(1 for x in sudah if x['tanggapan'] == k) for k in ('sudah bayar', 'keberatan', 'membalas', 'belum membalas')}
    pct = lambda a, b: round(100 * len(a) / len(b)) if b else None  # noqa: E731
    ribu = lambda v: f"{v // 1000}rb"  # noqa: E731
    angka = [_angka(f'Ditawari harga lama, sudah diinfo', None, pct(sudah_tawar, tawar_lama), '%', 'naik',
                    f'{len(sudah_tawar)} dari {len(tawar_lama)} klien yang sudah menerima rincian biaya sebelum {mulai.day} '
                    f'{BULAN_ID[mulai.month - 1]} dan belum bayar (termasuk {len(lunas_saja)} yang sudah bayar sesudah harga naik)'),
             _angka('Semua klien ber-notifikasi, sudah diinfo', None, pct(sudah, target), '%', 'naik',
                    f'{len(sudah)} dari {len(target)} klien {tld} yang menerima pengingat/penawaran {NOTIF_HARI} hari terakhir dan belum bayar'),
             _angka('Penawaran sesudah naik, masih harga lama', None, len(salah), 'penawaran', 'turun',
                    f'{benar} penawaran lain sudah memakai harga baru')]
    teks = [f"Diinfo oleh CS: {oleh['CS']} klien · oleh AM: {oleh['AM']} klien",
            'Tanggapan klien yang sudah diinfo: ' + ', '.join(f'{k} {v}' for k, v in tanggap.items())]
    teks += [f"Masih harga lama: {tw['dom']} · Rp{tw['total']:,} · {tw['w'][5:16]} · {tw['akun']}".replace(',', '.')
             for _, tw in salah]
    belum = sorted([x for x in tawar_lama if not x['info'] and not x['lunas']], key=lambda x: x['ditawar']['w'], reverse=True)
    baris_belum = [[x['ditawar']['dom'], x['nomor'], f"Rp{x['ditawar']['total']:,}".replace(',', '.'),
                    x['ditawar']['w'][5:10], x['ditawar']['akun']] for x in belum]
    ringkasan = (f"Harga domain {tld} naik dari Rp{ribu(lama)} ke Rp{ribu(baru)} sejak {mulai.day} {BULAN_ID[mulai.month - 1]}. "
                 f"{len(tawar_lama)} klien sudah menerima rincian biaya harga lama dan belum bayar; {len(sudah_tawar)} sudah diinfo "
                 f"atau sudah bayar, {len(belum)} belum. "
                 f"Dari semua {len(target)} klien ber-notifikasi, {len(sudah)} sudah diinfo (CS {oleh['CS']}, AM {oleh['AM']}). "
                 f"Penawaran sesudah naik yang masih harga lama: {len(salah)}.")
    return {'judul': f'Follow up kenaikan harga domain {tld}', 'angka': angka, 'ringkas': ringkasan,
            'sorot': [{'label': 'Ditawari harga lama, belum diinfo', 'nilai': len(belum), 'buruk': bool(belum)},
                      {'label': 'Penawaran masih harga lama', 'nilai': len(salah), 'buruk': bool(salah)},
                      {'label': 'Sudah diinfo', 'nilai': len(sudah)}],
            'daftar_teks': teks,
            'tabel': [{'judul': f'Ditawari harga lama, belum diinfo ({len(belum)} klien, penawaran terbaru dulu)',
                       'kolom': ['Domain', 'Nomor WA', 'Ditawari', 'Tanggal', 'Kanal'], 'baris': baris_belum}],
            'periode': {'sebelum': [awal.isoformat(), (mulai - timedelta(days=1)).isoformat()],
                        'sesudah': [mulai.isoformat(), hari_ini.isoformat()]},
            'ket': f'Sumber: rekaman WA kanal CS ({", ".join(AKUN_CS)}) dan AM (wa-am). Klien ber-notifikasi = menerima pengingat '
                   f'otomatis atau rincian biaya untuk web {tld} dalam {NOTIF_HARI} hari sebelum harga naik, dan belum ada pesan '
                   '"pembayaran sudah diterima" sebelum harga naik. Sudah diinfo = sesudah harga naik tim mengirim pesan yang '
                   'menyebut kenaikan/harga baru/angka harga baru, atau penawaran baru dengan harga baru (pengingat otomatis tidak '
                   'dihitung). Konfirmasi bayar di luar kanal-kanal ini tidak terbaca.'}

# ---- wa3 dua jalur (u-011): iklan vd.id utama (robot oper ke CS di wa1) vs bidang (AI penuh di wa3) ----
LUNAS_RE = re.compile(r'pembayaran (?:anda|bapak|ibu|kakak)?\s*(?:sdh|sudah) (?:sy|saya|kami) terima', re.I)
RUPIAH_RE = re.compile(r'(?<![\d.])(\d{1,3}(?:\.\d{3})+)(?![\d.])|(?<![\d.,])(\d+(?:[.,]\d+)?)\s?(jt|juta|rb|ribu)\b', re.I)
NOMINAL_KUNCI_RE = re.compile(r'total|transfer|pembayaran|nominal|\bdp\b|biaya(?!\s+iklan)', re.I)
REKENING_RE = re.compile(r'0301545796|no\.? ?rek', re.I)
KE_TIM_RE = re.compile(r'cek(?:kan)? ke tim|sudah saya cekkan', re.I)
KODE_IKLAN_RE = re.compile(r'\(([a-z0-9\-]+)\)')   # kode halaman iklan di pesan formulir, mis. (hukum2)
LEAD_UJI = ('6285725249041',)   # nomor uji internal robot wa3


def _rupiah_semua(teks):
    """Semua angka rupiah wajar (100 rb–50 jt) di teks: 1.200.000 / 1,2jt / 600rb."""
    hasil = []
    for a, b, s in RUPIAH_RE.findall(teks):
        x = int(a.replace('.', '')) if a else float(b.replace(',', '.')) * (1e6 if s.lower() in ('jt', 'juta') else 1e3)
        if 100_000 <= x <= 50_000_000:
            hasil.append(int(x))
    return hasil


def _nominal_bayar(teks_tim):
    """Nominal yang terakhir diminta tim sebelum konfirmasi bayar: angka sesudah kata total/transfer/DP/biaya terakhir.
    Biaya iklan dan harga perpanjangan tahun ke-2 dilewati."""
    for t in reversed(teks_tim):
        if re.search(r'perpanjang|per tahun|tahun ke', t, re.I):
            continue
        v = None
        for k in NOMINAL_KUNCI_RE.finditer(t):
            a = _rupiah_semua(t[k.end():k.end() + 60])
            if a:
                v = a[0]
        if v:
            return v
    return None


def _lead_wa3(dari):
    """Lead wa3 sejak `dari` (pesan pertama klien) + jalur, balasan, bayar. Chat lanjutan di wa1 ikut dihitung."""
    grup3, grup1 = {}, {}
    for m in _pesan_rekam('wa3', dari - timedelta(days=10), date.today()):
        grup3.setdefault(m['n'], []).append(m)
    for m in _pesan_rekam('wa1', dari, date.today()):
        grup1.setdefault(m['n'], []).append(m)
    hasil = []
    for n, ms in grup3.items():
        klien = [m for m in ms if not m['kami']]
        if not klien or n in LEAD_UJI or 'Coba mas' in klien[0]['t']:
            continue
        t0 = klien[0]['w']
        for m in klien:   # klien lama yang mengisi formulir iklan lagi ≥7 hari kemudian = lead baru
            if KODE_IKLAN_RE.search(m['t']) and (datetime.fromisoformat(m['w'][:19]) - datetime.fromisoformat(t0[:19])).days >= 7:
                t0 = m['w']
        if t0[:10] < dari.isoformat():
            continue
        ms = [m for m in ms if m['w'] >= t0]
        klien, kami = [m for m in ms if not m['kami']], [m for m in ms if m['kami']]
        if not kami:
            jalur = 'tak dibalas'
        else:   # robot jalur utama langsung menyapa "lanjut di wa satunya"; jalur bidang dijawab AI
            jalur = 'utama' if any('wa satunya' in m['t'].lower() for m in kami[:3]) else 'ai'
        lanjut = [m for m in grup1.get(n, []) if m['w'] >= t0[:10]]
        semua = sorted(ms + lanjut, key=lambda m: m['w'])
        lunas = next((m for m in semua if m['kami'] and LUNAS_RE.search(m['t'])), None)
        x = {'n': n, 't': t0, 'jalur': jalur, 'kode': next((k.group(1) for k in map(KODE_IKLAN_RE.search, [m['t'] for m in klien]) if k), '–'),
             'balas': len(klien) > 1 or any(not m['kami'] for m in lanjut),
             'rekening': any(m['kami'] and REKENING_RE.search(m['t']) for m in semua),
             'ke_tim': any(KE_TIM_RE.search(m['t']) for m in kami), 'lunas': lunas and lunas['w']}
        if lunas:
            x['nominal'] = _nominal_bayar([m['t'] for m in semua if m['kami'] and m['w'] < lunas['w']])
            x['jam'] = (datetime.fromisoformat(lunas['w'][:19]) - datetime.fromisoformat(t0[:19])).total_seconds() / 3600
        hasil.append(x)
    return sorted(hasil, key=lambda x: x['t'])


def metrik_wa3_jalur(mulai):
    awal = mulai - timedelta(days=30)
    lead = _lead_wa3(awal)
    for x in lead:
        if x['t'][:10] < mulai.isoformat():
            x['jalur'] = 'sebelum'
    koma = lambda v, d=1: f'{v:.{d}f}'.replace('.', ',')   # noqa: E731
    jam = lambda h: f'{h:.0f} jam' if h < 48 else f'{h / 24:.1f} hari'.replace('.', ',')   # noqa: E731

    def ringkas_jalur(j):
        xs = [x for x in lead if x['jalur'] == j]
        bayar = [x for x in xs if x['lunas']]
        nilai = sum(x.get('nominal') or 0 for x in bayar)
        n = len(xs) or 1
        return xs, bayar, {
            'lead': len(xs), 'balas': f"{sum(x['balas'] for x in xs)} ({100 * sum(x['balas'] for x in xs) / n:.0f}%)",
            'bayar': len(bayar), 'konversi': 100 * len(bayar) / n, 'nilai': nilai,
            'rata': nilai / len(bayar) if bayar else None,
            'lama': statistics.median([x['jam'] for x in bayar]) if bayar else None,
            'tunggu': [x for x in xs if x['rekening'] and not x['lunas']], 'ke_tim': sum(x['ke_tim'] for x in xs)}

    _, _, u = ringkas_jalur('utama')
    _, _, a = ringkas_jalur('ai')
    _, _, sb = ringkas_jalur('sebelum')
    rp = lambda v: f'Rp{koma(v / 1e6)} jt' if v else '–'   # noqa: E731
    kol = (u, a, sb)
    baris = [['Lead masuk'] + [r['lead'] for r in kol],
             ['Klien membalas'] + [r['balas'] for r in kol],
             ['Transfer'] + [r['bayar'] for r in kol],
             ['Konversi'] + [f"{koma(r['konversi'])}%" for r in kol],
             ['Nilai transfer (±)'] + [rp(r['nilai']) for r in kol],
             ['Rata-rata per transfer'] + [rp(r['rata']) for r in kol],
             ['Median chat → bayar'] + [jam(r['lama']) if r['lama'] is not None else '–' for r in kol],
             ['Dikirimi rekening, belum transfer'] + [len(r['tunggu']) for r in kol],
             ['Chat AI bertanya ke tim', '–', a['ke_tim'], '–']]
    bayar = sorted([x for x in lead if x['lunas'] and x['jalur'] != 'sebelum'], key=lambda x: x['lunas'], reverse=True)
    nama = {'utama': 'Utama (CS)', 'ai': 'Bidang (AI)'}
    tunggu = sorted(u['tunggu'] + a['tunggu'], key=lambda x: x['t'], reverse=True)
    tabel = [{'judul': f"Perbandingan jalur sejak {mulai.day} {BULAN_ID[mulai.month - 1]} (lead wa3, lanjutan chat di wa1 ikut dihitung)",
              'kolom': ['Ukuran', 'Utama (CS)', 'Bidang (AI)', 'Sebelum (30 hr)'], 'baris': baris,
              'kanan': [1, 2, 3]},
             {'judul': f'Transfer sejak 2 jalur ({len(bayar)}, terbaru dulu)',
              'kolom': ['Nomor WA', 'Jalur', 'Kode iklan', 'Lead masuk', 'Bayar', 'Lama', 'Nominal (±)'], 'kanan': [5, 6],
              'baris': [[x['n'], nama[x['jalur']], x['kode'], x['t'][5:16], x['lunas'][5:16], jam(x['jam']),
                         (f"Rp{x['nominal'] // 1000} rb" if x['nominal'] < 1e6 else rp(x['nominal'])) if x.get('nominal') else '–']
                        for x in bayar]},
             {'judul': f'Sudah dikirimi rekening, belum transfer ({len(tunggu)}, terbaru dulu)',
              'kolom': ['Nomor WA', 'Jalur', 'Kode iklan', 'Lead masuk'],
              'baris': [[x['n'], nama[x['jalur']], x['kode'], x['t'][5:16]] for x in tunggu]}]
    ringkasan = (f"AI (bidang): {a['lead']} lead → {a['bayar']} transfer ({koma(a['konversi'])}%, {rp(a['nilai'])}); "
                 f"CS (utama): {u['lead']} lead → {u['bayar']} transfer ({koma(u['konversi'])}%, {rp(u['nilai'])}); "
                 f"30 hari sebelum 2 jalur: {koma(sb['konversi'])}%.")
    return {'judul': 'wa3 dua jalur: utama (CS) vs bidang (AI)', 'ringkas': ringkasan, 'tabel': tabel,
            'sorot': [{'label': 'Konversi AI (%)', 'nilai': round(a['konversi'], 1)},
                      {'label': 'Konversi CS (%)', 'nilai': round(u['konversi'], 1)},
                      {'label': 'Konversi sebelum (%)', 'nilai': round(sb['konversi'], 1)}],
            'ket': 'Perekam WA wa3 + wa1. Lead = chat wa3 yang pesan pertama kliennya jatuh di periode (nomor uji robot dibuang). '
                   'Jalur utama = sapaan pertama robot "lanjut di wa satunya"; selain itu jalur bidang (AI). Transfer = pesan tim '
                   '"pembayaran ... sudah kami terima" di wa3/wa1. Nominal = angka terakhir yang diminta tim sebelum konfirmasi '
                   '(perkiraan; DP terhitung DP). Biaya iklan vd.id dan biaya API robot belum tercatat, jadi untung/rugi belum dihitung.',
            'periode': {'sebelum': [awal.isoformat(), (mulai - timedelta(days=1)).isoformat()],
                        'sesudah': [mulai.isoformat(), date.today().isoformat()]}}


def hitung_sumber(sumber, mulai):
    sumber, _, jangkar = sumber.partition('@')
    m = _hitung_sumber(sumber, _tgl(jangkar) if jangkar else mulai)
    if jangkar and m.get('judul'):
        m['judul'] += f" · sejak {_tgl(jangkar).day} {_tgl(jangkar).strftime('%b')}"
        m['jangkar'] = jangkar
    if m.get('ringkas'):
        m['ringkas'] = re.sub(r'(\d)\.(\d)', r'\1,\2', m['ringkas'])   # desimal gaya Indonesia
        m['ringkas'] = re.sub(r'(\d),0(?!\d)', r'\1', m['ringkas'])
    return m


def _hitung_sumber(sumber, mulai):
    if sumber == 'kasus_support':
        return metrik_kasus_support(mulai)
    if sumber == 'installer_wp':
        return metrik_installer_wp(mulai)
    if sumber == 'laravel':
        return metrik_laravel(mulai)
    if sumber == 'crm_konsep':
        return metrik_crm_konsep(mulai)
    if sumber == 'konsep_wm':
        return metrik_konsep_wm(mulai)
    if sumber == 'omzet':
        return metrik_omzet(mulai)
    if sumber == 'webmaster':
        return metrik_webmaster(mulai)
    if sumber == 'kasus_tim':
        return metrik_kasus_tim(mulai)
    if sumber == 'kasus_ai':
        return metrik_kasus_ai(mulai)
    if sumber == 'kasus_harian':
        return metrik_kasus_harian(mulai)
    if sumber == 'wa3_jalur':
        return metrik_wa3_jalur(mulai)
    if sumber == 'kasus_meeting':
        return metrik_kasus_meeting(mulai)
    if sumber == 'efisiensi_langganan':
        return metrik_efisiensi_langganan(mulai)
    if sumber == 'konsep_halaman':
        return metrik_konsep_halaman(mulai)
    if sumber.startswith('ai:'):
        return metrik_ai(sumber[3:])
    if sumber.startswith('ai_orang:'):
        return metrik_ai_orang(sumber[9:], mulai)
    if sumber == 'installer_paket':
        return metrik_installer_paket(mulai)
    if sumber.startswith('bahasa:'):
        return metrik_bahasa(sumber[7:], mulai)
    if sumber.startswith('harga_domain:'):
        return metrik_harga_domain(sumber[13:], mulai)
    return {'galat': 'sumber tidak dikenal'}


def pantau(hanya=None, sumber_saja=None):
    """sumber_saja: hitung hanya sumber ini (mis. 'webmaster' 4x sehari); metrik sumber lain dibiarkan."""
    d = muat()
    hasil, cache = {}, {}
    for u in d['update']:
        if hanya and u['id'] != hanya:
            continue
        if u['status'] in ('selesai', 'dihentikan'):
            continue
        for s in u.get('sumber') or []:
            if sumber_saja and sumber_saja not in (s.partition('@')[0], s.partition(':')[0]):
                continue
            kunci = (s, u['mulai'] if not s.startswith('ai:') and '@' not in s else '')
            if kunci not in cache:
                try:
                    cache[kunci] = hitung_sumber(s, _tgl(u['mulai']))
                except Exception as e:  # noqa: BLE001 — satu sumber gagal tidak boleh menghentikan yang lain
                    cache[kunci] = {'galat': f'{type(e).__name__}: {str(e)[:200]}'}
                cache[kunci]['waktu'] = sekarang()
            hasil.setdefault(u['id'], {})[s] = cache[kunci]
    with terkunci():
        d = muat()
        hari = date.today().isoformat()
        for u in d['update']:
            if u['id'] not in hasil:
                continue
            u['metrik'] = {**{k: v for k, v in (u.get('metrik') or {}).items() if k in u.get('sumber', [])}, **hasil[u['id']]}
            # Cuplikan harian angka "sesudah" untuk melihat tren
            riw = u.setdefault('riwayat_metrik', {})
            for s, m in hasil[u['id']].items():
                if 'galat' in m:
                    continue
                titik = {a['label']: a['sesudah'] for a in m.get('angka') or []}
                titik.update({x['label']: x['nilai'] for x in m.get('sorot') or []})
                r = [x for x in riw.get(s, []) if x['t'] != hari] + [{'t': hari, 'v': titik}]
                riw[s] = r[-RIWAYAT_MAKS:]
        if not hanya and not sumber_saja:
            d['pantau_terakhir'] = sekarang()
        simpan(d)
        kondisi_ada = {u['id']: ' '.join(k['isi'][:40] for k in u['kondisi']) for u in d['update'] if u['id'] in hasil}
    # Laporan kasus harian sekali per tanggal sebagai kondisi (riwayat; tabel di kartu hanya hari terakhir)
    for uid, ms in hasil.items():
        m = ms.get('kasus_harian') or {}
        if m.get('kondisi_harian') and m['kondisi_harian'][:40] not in kondisi_ada.get(uid, ''):
            tambah_kondisi(uid, m['kondisi_harian'], oleh='Claude')
    return hasil


# ---------- penilaian Claude ----------

SKEMA_NILAI = {
    'type': 'object', 'required': ['ringkasan', 'update'],
    'properties': {
        'ringkasan': {'type': 'string', 'description': '2–4 kalimat: gambaran umum semua update minggu ini, yang paling butuh perhatian disebut duluan'},
        'update': {'type': 'array', 'items': {
            'type': 'object', 'required': ['id', 'kondisi', 'saran_status', 'langkah'],
            'properties': {
                'id': {'type': 'string'},
                'kondisi': {'type': 'string', 'description': 'kondisi terbaru 1–3 kalimat, sebut angka bila ada'},
                'saran_status': {'type': 'string', 'enum': list(STATUS)},
                'langkah': {'type': 'string', 'description': 'satu langkah konkret berikutnya untuk pemilik, atau data yang perlu dicatat'},
            }}},
    },
}

PROMPT_NILAI = """Kamu membantu pemilik Velocity Developer (jasa pembuatan website, Indonesia) memantau perubahan
yang sedang diterapkan di perusahaan. Untuk tiap update di bawah: baca jurnal (apa yang diubah & apa yang
mau dipantau), catatan kondisi dari pemilik/tim, dan metrik otomatis (sebelum vs sesudah tanggal mulai).

Tulis kondisi terbaru yang jujur dan singkat dalam bahasa Indonesia sehari-hari:
- Pakai angka metrik bila ada. Sebut bila datanya belum cukup (mis. baru beberapa hari, tidak ada pembanding).
- Bedakan fakta dari dugaan. Jangan memuji tanpa angka.
- Bila tidak ada metrik otomatis dan catatan terakhir sudah lama (>7 hari), katakan kondisinya belum tercatat
  dan sarankan data apa yang perlu dicatat pemilik.
- saran_status: bagus (terbukti membaik), perlu_perhatian (memburuk / ada hambatan), berjalan (belum bisa dinilai).
- langkah: satu tindakan konkret, bukan nasihat umum.
Tanggal hari ini: {hari}.

DATA:
{data}
"""


def _ringkas_untuk_claude(u):
    m = {}
    for s, x in (u.get('metrik') or {}).items():
        if 'galat' in x:
            m[s] = {'galat': x['galat']}
            continue
        m[s] = {k: x[k] for k in ('judul', 'ringkas', 'angka', 'sorot', 'ket', 'periode') if k in x}
        for k in ('paket', 'contoh', 'contoh_baik', 'daftar_teks', 'seri'):
            if x.get(k):
                m[s][k] = x[k]
        if 'orang' in x:
            m[s]['orang'] = [{k: o[k] for k in ('nama', 'hari_aktif', 'panggilan', 'minim')} for o in x['orang']]
    return {'id': u['id'], 'judul': u['judul'], 'mulai': u['mulai'], 'divisi': u.get('divisi'), 'status': u['status'],
            'jurnal': u.get('jurnal'), 'yang_dipantau': u.get('pantau'),
            'kondisi': [{'waktu': k['waktu'][:10], 'oleh': k['oleh'], 'isi': k['isi']} for k in u['kondisi'][-6:]],
            'metrik': m}


def nilai(oleh='Claude'):
    d = muat()
    aktif = [u for u in d['update'] if u['status'] not in ('selesai', 'dihentikan')]
    if not aktif:
        return {'galat': 'tidak ada update aktif'}
    prompt = PROMPT_NILAI.format(hari=date.today().isoformat(),
                                 data=json.dumps([_ringkas_untuk_claude(u) for u in aktif], ensure_ascii=False, indent=1))
    mulai = time.time()
    run = subprocess.run([CLAUDE, '-p', '--model', 'opus', '--output-format', 'json', '--no-session-persistence',
                          '--tools', '', '--json-schema', json.dumps(SKEMA_NILAI)],
                         input=prompt, capture_output=True, text=True, timeout=900, cwd='/tmp')
    hasil = json.loads(run.stdout)
    _catat_pemakaian(hasil)
    data = hasil.get('structured_output')
    if not isinstance(data, dict) or hasil.get('is_error'):
        return {'galat': str(hasil.get('result') or 'tanpa keluaran JSON')[:400]}
    waktu = sekarang()
    ada = {u['id'] for u in aktif}
    for x in data.get('update') or []:
        if x.get('id') not in ada:
            continue
        isi = x['kondisi'].strip() + (f"\n\nLangkah berikutnya: {x['langkah'].strip()}" if x.get('langkah') else '')
        tambah_kondisi(x['id'], isi, oleh=oleh, waktu=waktu, jenis='claude')
        with terkunci():
            d = muat()
            u = cari(d, x['id'])
            if u:
                u['saran_status'] = x.get('saran_status') if x.get('saran_status') in STATUS else None
                simpan(d)
    ringkasan = {'waktu': waktu, 'ringkasan': data.get('ringkasan', ''), 'detik': round(time.time() - mulai),
                 'biaya_usd': round(float(hasil.get('total_cost_usd') or 0), 2)}
    (DIR / 'nilai.json').write_text(json.dumps(ringkasan, ensure_ascii=False))
    return ringkasan


def _catat_pemakaian(hasil, mode='nilai'):
    for model, x in (hasil.get('modelUsage') or {}).items():
        masuk, baca, buat = (int(x.get(k) or 0) for k in ('inputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens'))
        keluar = int(x.get('outputTokens') or 0)
        baris = {'ts': datetime.utcnow().isoformat(timespec='seconds') + '+00:00', 'domain': 'velocity-update',
                 'run': f'velocity-update-{mode}', 'mode': mode, 'peran': 'velocity_update', 'script': 'velocity_update.py',
                 'sumber': 'claude', 'model_id': 'claude-code', 'model': model, 'permintaan': 1,
                 'prompt_tokens': masuk + baca + buat, 'completion_tokens': keluar, 'total_tokens': masuk + baca + buat + keluar,
                 'input_tokens': masuk, 'cache_read_tokens': baca, 'cache_creation_tokens': buat,
                 'biaya_usd': round(float(x.get('costUSD') or 0), 4), 'ok': not hasil.get('is_error')}
        try:
            with open(AI_USAGE, 'a') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps(baris, ensure_ascii=False) + '\n')
        except OSError:
            pass


def nilai_berjalan():
    """Penilaian sedang jalan? (dipakai API supaya tombol tidak memicu dua kali)"""
    try:
        pid = int((DIR / 'nilai.pid').read_text())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def mulai_nilai_latar():
    if nilai_berjalan():
        return 'sedang_jalan'
    log = open(LOG_NILAI, 'a')
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'nilai', '--pantau-dulu'],
                         stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    (DIR / 'nilai.pid').write_text(str(p.pid))
    return None


# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='perintah', required=True)
    sub.add_parser('daftar')
    t = sub.add_parser('tambah')
    for a in ('judul', 'mulai'):
        t.add_argument(f'--{a}', required=True)
    for a in ('divisi', 'jurnal', 'pantau', 'sumber', 'status'):
        t.add_argument(f'--{a}', default='')
    t.add_argument('--oleh', default='Claude')
    k = sub.add_parser('kondisi')
    k.add_argument('id')
    k.add_argument('isi')
    k.add_argument('--oleh', default='Claude')
    k.add_argument('--status')
    p = sub.add_parser('pantau')
    p.add_argument('--id')
    p.add_argument('--sumber', help='hanya sumber ini, mis. webmaster')
    km = sub.add_parser('meeting', help='tandai kasus Support untuk dibahas di meeting (tabel di update yang bersumber kasus_meeting)')
    km.add_argument('nomor')
    km.add_argument('catatan')
    km.add_argument('--kasus', type=int, help='id kasus CRM; bawaan = kasus terbaru nomor itu')
    km.add_argument('--temuan', default='')
    sub.add_parser('sandi')
    n = sub.add_parser('nilai')
    n.add_argument('--pantau-dulu', action='store_true')
    a = ap.parse_args()

    if a.perintah == 'sandi':
        galat = atur_sandi(sys.stdin.read())
        print(galat or f'sandi disimpan di {SANDI}; semua sesi lama keluar')
        return 1 if galat else 0
    if a.perintah == 'daftar':
        for u in muat()['update']:
            akhir = u['kondisi'][-1] if u['kondisi'] else None
            print(f"{u['id']}  {u['mulai']}  [{u['status']}]  {u['judul']}")
            if akhir:
                print(f"         terakhir {akhir['waktu'][:10]} ({akhir['oleh']}): {akhir['isi'][:110]}")
        return 0
    if a.perintah == 'tambah':
        body = {k: getattr(a, k) for k in ('judul', 'mulai', 'divisi', 'jurnal', 'pantau')}
        body['status'] = a.status or 'berjalan'
        body['sumber'] = [s.strip() for s in a.sumber.split(',') if s.strip()]
        u, galat = tambah_update(body, a.oleh)
        print(galat or f"ditambahkan {u['id']}")
        return 1 if galat else 0
    if a.perintah == 'kondisi':
        u, galat = tambah_kondisi(a.id, a.isi, a.oleh, a.status)
        print(galat or 'kondisi dicatat')
        return 1 if galat else 0
    if a.perintah == 'meeting':
        galat = tandai_kasus_meeting(a.nomor, a.catatan, a.kasus, a.temuan)
        if galat:
            print(galat)
            return 1
        for uid, m in pantau(sumber_saja='kasus_meeting').items():
            print(f"{uid}: {m['kasus_meeting'].get('galat') or m['kasus_meeting'].get('ringkas')}")
        return 0
    if a.perintah == 'pantau':
        h = pantau(a.id, a.sumber)
        for uid, m in h.items():
            for s, x in m.items():
                print(f"{uid} {s}: {x.get('galat') or x.get('ringkas')}")
        return 0
    if a.perintah == 'nilai':
        try:
            print(f'[{sekarang()}] mulai penilaian', flush=True)
            if a.pantau_dulu:
                pantau()
            r = nilai()
            print(json.dumps(r, ensure_ascii=False), flush=True)
            return 1 if 'galat' in r else 0
        finally:
            try:
                if int((DIR / 'nilai.pid').read_text()) == os.getpid():
                    (DIR / 'nilai.pid').unlink()
            except (OSError, ValueError):
                pass
    return 2


if __name__ == '__main__':
    sys.exit(main())
