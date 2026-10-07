"""Data & API alur project Laravel (menu Installer > Laravel di dashboard).

Alur (permintaan user 2026-09-25):
  1. Brief     PM menempel catatan/chat diskusi klien -> Claude menyusun draf DESIGN.md + PRD.md -> PM menyunting
  2. Estimasi  Claude memecah PRD jadi fitur + kriteria terima + jam (internal) -> PM menyesuaikan & mengunci
  3. Install   scripts/laravel-installer (laravel new --vue, pola dev sia-vd, repo GitHub)
  4. Agen      scripts/laravel-agen: satu sesi Claude per fitur, berurutan; runner memverifikasi tes + build lalu commit
  5. Review    webmaster mencentang checklist kriteria per fitur (hasil & bukti agen terlihat) -> OK / Revisi
Tahap TIDAK disimpan, tapi dihitung dari data (tahap()).

Identitas: saat diskusi awal folder On Progress biasanya belum ada, jadi project diberi ID urut
`project-001`, `project-002`, ... (kunci penyimpanan, tidak pernah berubah). Relasi ke folder
`/home/On Progress/<domain>` dipilih kapan saja sebelum install. Nama aplikasi (folder /home, database,
layanan, repo) baru ditentukan saat Install — bawaannya dari relasi On Progress — dan disimpan di `app`.

Dipakai services/installer_status.py (handle()) dan skrip laravel-brief / laravel-agen (baca/tulis data).
Semua berkas per project di PROYEK/<slug>/; tulis lewat simpan_json() dengan kunci per project.
"""
import fcntl
import json
import os
import re
import shutil
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs

import server_dev  # (server dev Laravel: status, nyala/mati/restart)

DASAR = Path('/var/lib/velocity/laravel')
PROYEK = DASAR / 'proyek'
SKRIP = Path(__file__).resolve().parent
INSTALLER = SKRIP / 'laravel-installer'
BRIEF = SKRIP / 'laravel-brief'
AGEN = SKRIP / 'laravel-agen'
DB_CNF = Path('/etc/velocity/secrets/mariadb_root.cnf')
AI_USAGE = Path('/var/lib/velocity/ai/usage.jsonl')
LOCAL_PROJECTS = SKRIP.parent / 'config' / 'local-projects.json'
PORT_AWAL, PORT_AKHIR = 8050, 8999
# Semua repo installer Laravel ke org velocitycustomer supaya org utama tidak menumpuk
# (25 Sep untuk project klien; 28 Sep diperluas ke project internal atas permintaan user).
ORG_GITHUB = 'velocitycustomer'
JADWAL = SKRIP.parent / 'config' / 'laravel-jadwal.json'
JADWAL_BAWAAN = {'mesin_mulai': 7, 'mesin_selesai': 22, 'jam_agen_per_project_per_hari': 6,
                 'jam_agen_total_per_hari': 10, 'jam_webmaster_per_hari': 7, 'fitur_gerbang_review': 3}


def konfig_jadwal():
    cfg = dict(JADWAL_BAWAAN)
    cfg.update({k: v for k, v in (baca_json(JADWAL, {}) or {}).items() if k in JADWAL_BAWAAN})
    return cfg


def dasar_jadwal(kecuali=None):
    """Pengaturan jam untuk estimasi + berapa project LAIN yang sedang memakai antrean agen."""
    cfg = konfig_jadwal()
    cfg['project_agen_lain'] = sum(1 for x in daftar() if x['slug'] != kecuali and x['tahap'] == 'agen')
    return cfg


# --- Tim dari CRM new.velocitydeveloper ------------------------------------------
# Pilihan "Nama Anda" = orang sungguhan dari CRM (permintaan user 2026-09-25: nama PM diambil dari CRM), lewat akun
# baca /root/newvdnet-read/api.sh. Akun bawaan per peran (username = nama peran, pm, webcustom, webbiasa) disaring.
CRM_API = Path('/root/newvdnet-read/api.sh')
TIM_CACHE = DASAR / 'tim-crm.json'
TIM_TTL = 6 * 3600
TIM_PERAN = (('pm', 'manager_project'), ('webmaster', 'webdeveloper'), ('revisi', 'revisi'))
AKUN_BAWAAN = {'pm', 'webcustom', 'webbiasa', 'manager_project', 'webdeveloper', 'revisi'}
_tim_lock = threading.Lock()


def _tarik_tim():
    tim = {}
    for kunci, peran in TIM_PERAN:
        r = subprocess.run([str(CRM_API), f'/api/api/users?role={peran}&status=active&per_page=100'],
                           capture_output=True, text=True, timeout=60)
        data = json.loads(r.stdout).get('data')
        if not isinstance(data, list):
            raise ValueError(f'respons CRM {peran} tanpa data')
        tim[kunci] = sorted({str(u.get('name') or '').strip() for u in data
                             if str(u.get('username') or '') not in AKUN_BAWAAN | {peran} and str(u.get('name') or '').strip()})
    return tim


def tim_crm():
    """{'pm': [...], 'webmaster': [...], 'revisi': [...], 'diambil': ts, 'galat': str|None}; cache 6 jam."""
    lama = baca_json(TIM_CACHE, {}) or {}
    if lama and time.time() - lama.get('diambil', 0) < TIM_TTL:
        return lama
    with _tim_lock:
        lama = baca_json(TIM_CACHE, {}) or {}
        if lama and time.time() - lama.get('diambil', 0) < TIM_TTL:
            return lama
        try:
            baru = {**_tarik_tim(), 'diambil': sekarang(), 'galat': None}
            DASAR.mkdir(parents=True, exist_ok=True)
            tulis_json(TIM_CACHE, baru)
            return baru
        except (OSError, ValueError, subprocess.SubprocessError) as e:
            # CRM tidak terjangkau: pakai salinan terakhir, coba lagi 10 menit kemudian
            cadangan = {**lama, 'galat': f'{type(e).__name__}: {str(e)[:120]}',
                        'diambil': lama.get('diambil', 0) and time.time() - TIM_TTL + 600}
            if lama:
                tulis_json(TIM_CACHE, cadangan)
            return cadangan


def jatah_agen_harian(slug):
    """Jam agen yang boleh dipakai project ini hari ini: min(per project, total / jumlah project di tahap Agen).
    Sama dengan rumus porsi di jadwal() web-vue/src/laravel.js."""
    cfg = dasar_jadwal(slug)
    return min(cfg['jam_agen_per_project_per_hari'], cfg['jam_agen_total_per_hari'] / (1 + cfg['project_agen_lain']))


def menit_agen_hari_ini(fitur):
    """Menit kerja agen project ini yang tercatat hari ini (semua fitur, termasuk yang gagal/tertunda)."""
    hari = time.strftime('%Y-%m-%d')
    total = 0.0
    for f in fitur:
        for h in f.get('riwayat_menit') or []:
            if h.get('hari') == hari:
                total += float(h.get('menit') or 0)
    return total


def kalibrasi_agen():
    """Lama kerja agen yang NYATA per fitur dari semua project (fitur dites/ok; jumlah semua sesi, termasuk ulang
    karena gagal & revisi). Estimasi Claude dulu 8–17x lebih besar dari kenyataan (audit 1 Okt), jadi angka ini
    dipakai prompt estimasi, tombol "Sesuaikan" di tab Estimasi, dan perkiraan menit runner."""
    menit, jam = [], []
    for fp in PROYEK.glob('*/fitur.json'):
        for f in baca_json(fp, []) or []:
            riwayat = f.get('riwayat_menit') or []
            if f.get('status') in ('dites', 'ok') and riwayat:
                menit.append(sum(float(r.get('menit') or 0) for r in riwayat))
                jam.append(float(f.get('jam_agen') or 0))
    if len(menit) < 5:
        return None
    urut = sorted(menit)
    return {'fitur': len(menit), 'menit_median': round(urut[len(urut) // 2], 1),
            'menit_p90': round(urut[min(len(urut) - 1, int(len(urut) * 0.9))], 1),
            'rasio': round(sum(menit) / 60 / sum(jam), 3) if sum(jam) else None}


def gerbang_review(fitur):
    """Fitur fondasi (N pertama, config fitur_gerbang_review) yang sudah dikerjakan agen tapi belum direview.
    Selama masih ada, agen tidak memulai fitur sesudah gerbang (laravel-agen -> status menunggu_review), supaya
    masukan webmaster soal struktur dasar datang sebelum puluhan fitur dibangun di atasnya."""
    n = int(konfig_jadwal().get('fitur_gerbang_review') or 0)
    if n <= 0 or len(fitur) <= n:
        return []
    return [f['id'] for f in fitur[:n] if f.get('status') == 'dites']


def info_review(p, fitur):
    """Peringatan review di daftar & halaman project: berapa fitur siap dicek, sejak kapan, dan apakah agen tertahan."""
    tunggu = [f for f in fitur if f.get('status') == 'dites' and f.get('hasil')]
    return {'menunggu': len(tunggu), 'ids': [f['id'] for f in tunggu],
            'tertua': min((f['hasil'].get('waktu') or 0) for f in tunggu) if tunggu else None,
            'gerbang': gerbang_review(fitur), 'gerbang_n': int(konfig_jadwal().get('fitur_gerbang_review') or 0),
            'tertahan': (p.get('agen') or {}).get('status') == 'menunggu_review'}


# --- Matriks peran × halaman (PRD) -> cakupan fitur ---------------------------------
# Audit 1 Okt: 3 dari 6 revisi elearning = "halaman <peran> belum ada". PRD kini wajib punya tabel
# "Matriks peran × halaman"; estimasi mengisi `halaman` per fitur; sel berakses yang tak ada di fitur mana pun = celah.
MATRIKS_RE = re.compile(r'^#{2,3}\s*Matriks peran', re.I | re.M)


def _norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', str(s).lower()).strip()


SEL_KOSONG = {'', 'x', 'tidak', 'n a', 'na'}  # sesudah _norm: '-', '–', '✗' juga jadi ''


def matriks_prd(prd):
    """Tabel Markdown pertama sesudah judul 'Matriks peran …' -> (daftar peran, [(halaman, {peran: sel})]) atau None."""
    m = MATRIKS_RE.search(prd or '')
    if not m:
        return None
    baris = []
    for b in prd[m.end():].splitlines()[1:]:
        b = b.strip()
        if b.startswith('#'):
            break
        if b.startswith('|'):
            baris.append([c.strip() for c in b.strip('|').split('|')])
        elif baris and b:
            break
    if len(baris) < 2:
        return None
    peran = [x.replace('**', '').strip() for x in baris[0][1:]]
    isi = []
    for r in baris[1:]:
        if not r or not r[0] or set(''.join(r)) <= set('-: '):
            continue
        isi.append((r[0].replace('**', '').strip(), {peran[i]: (r[i + 1] if i + 1 < len(r) else '') for i in range(len(peran))}))
    return (peran, isi) if isi else None


def cek_cakupan(prd, fitur):
    """-> None (PRD tanpa matriks) | {'kurang': ['Halaman — Peran', …], 'sel': jumlah sel berakses}."""
    mx = matriks_prd(prd)
    if not mx:
        return None
    ada = {(_norm(h.get('halaman')), _norm(pr)) for f in fitur for h in f.get('halaman') or [] for pr in h.get('peran') or []}
    kurang, sel = [], 0
    for halaman, akses in mx[1]:
        for pr, v in akses.items():
            if _norm(v) in SEL_KOSONG:
                continue
            sel += 1
            if (_norm(halaman), _norm(pr)) not in ada:
                kurang.append(f'{halaman} — {pr}')
    return {'kurang': kurang, 'sel': sel}


def org_github(p):
    return ORG_GITHUB

SLUG_RE = re.compile(r'^[a-z][a-z0-9-]{1,30}[a-z0-9]$')
ID_RE = re.compile(r'^project-\d{3,}$')
ON_PROGRESS = Path('/home/On Progress')
DOMAIN_RE = re.compile(r'^[a-z0-9.-]+\.[a-z]{2,}$')
# Judul/klien/nama masuk ke sed & unit systemd di installer: tolak karakter yang merusak keduanya.
TEKS_RE = re.compile(r'^[^"\'`$\\|&;<>\n\r]{0,80}$')
MD_MAKS = 400_000
STATUS_FITUR = ('antre', 'jalan', 'dites', 'gagal', 'ok', 'revisi')

_proses = {}  # (slug, jenis) -> Popen, supaya anak yang selesai ikut dipanen (tidak jadi zombie)
_kunci_mulai = threading.Lock()


def folder(slug):
    return PROYEK / slug


def sekarang():
    return int(time.time())


@contextmanager
def terkunci(slug):
    folder(slug).mkdir(parents=True, exist_ok=True)
    with open(folder(slug) / '.kunci', 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def baca_json(path, bawaan=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return bawaan


def tulis_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    os.replace(tmp, path)


def baca_teks(slug, nama):
    try:
        return (folder(slug) / nama).read_text()
    except OSError:
        return ''


def tulis_teks(slug, nama, isi):
    p = folder(slug) / nama
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(isi)
    os.replace(tmp, p)


def ubah_proyek(slug, fn):
    """fn(proyek) mengubah dict di tempat; ditulis atomik di bawah kunci project."""
    with terkunci(slug):
        p = baca_json(folder(slug) / 'proyek.json', {})
        fn(p)
        tulis_json(folder(slug) / 'proyek.json', p)
        return p


def ubah_fitur(slug, fn):
    with terkunci(slug):
        f = baca_json(folder(slug) / 'fitur.json', [])
        hasil = fn(f)
        tulis_json(folder(slug) / 'fitur.json', f)
        return hasil


def catat(slug, oleh, aksi):
    def _(p):
        p.setdefault('riwayat', []).append({'waktu': sekarang(), 'oleh': oleh, 'aksi': aksi})
        p['riwayat'] = p['riwayat'][-200:]
    ubah_proyek(slug, _)


# --- Versi brief ---------------------------------------------------------------
# Setiap perubahan isi brief (catatan, dokumen klien, PRD/DESIGN/DATABASE/FLOWCHART) menaikkan proyek.json
# `brief_versi` (permintaan user 2026-09-30: memastikan brief sudah update atau belum). Keluaran yang dibuat dari brief
# (saran, rangkuman, contoh, estimasi) mencatat versi bahannya; bila bagian yang dibacanya berubah sesudah itu → usang.
BAGIAN_BRIEF = {'catatan': 'catatan', 'dokumen': 'dokumen klien', 'prd': 'PRD.md', 'design': 'DESIGN.md',
                'database': 'relasi database', 'flowchart': 'flowchart', 'konten': 'kebutuhan konten'}
BAHAN_KELUARAN = {'saran': ('catatan', 'dokumen'), 'rangkuman': ('catatan', 'dokumen', 'konten'),
                  'contoh': ('catatan', 'dokumen', 'prd', 'design'), 'estimasi': ('prd', 'design', 'database', 'konten')}

# Kebutuhan konten halaman publik (permintaan user 2026-10-01, dari fastcek: hero/FAQ/cara order tertulis di kode,
# klien tak bisa mengubah tanpa developer). PM MENANDAI di tahap Brief (proyek.json `konten`); laravel-brief
# memasukkannya ke prompt susun PRD, estimasi & rangkuman. Tidak semua project butuh, jadi tanpa tanda = tidak dipaksa.
KONTEN_MODE = {'statis': 'Statis', 'bersekat': 'Konten bersekat', 'page_builder': 'Page builder'}

# Status project (permintaan user 2026-10-05): brief yang tidak deal dengan klien ditandai Batal/Ditunda supaya daftar
# /installer/laravel tidak menumpuk; Selesai (5 Okt) = project rampung/serah terima, ikut dikunci seperti Batal/Ditunda. proyek.json `status` {nilai, alasan, oleh, waktu}; tanpa field = aktif.
# Project nonaktif: semua aksi ditolak (`proyek_nonaktif`) kecuali mengubah status, dan laravel-agen-lanjut melewatinya.
STATUS_PROYEK = {'aktif': 'Aktif', 'selesai': 'Selesai', 'ditunda': 'Ditunda', 'batal': 'Batal'}


def status_proyek(p):
    return (p.get('status') or {}).get('nilai') or 'aktif'


def versi_brief(p):
    return int((p or {}).get('brief_versi') or 0)


def naik_versi_brief(slug, oleh, bagian):
    """bagian = kunci BAGIAN_BRIEF yang berubah; kembalikan nomor versi baru."""
    def _(p):
        n = versi_brief(p) + 1
        p['brief_versi'] = n
        p['brief_versi_riwayat'] = (p.get('brief_versi_riwayat') or [])[-99:] + [
            {'versi': n, 'waktu': sekarang(), 'oleh': oleh, 'bagian': list(bagian)}]
    return versi_brief(ubah_proyek(slug, _))


def info_versi_brief(slug, p):
    riwayat = p.get('brief_versi_riwayat') or []
    kel = {'saran': (baca_json(folder(slug) / 'saran.json', None) or {}).get('brief_versi'),
           'rangkuman': (baca_json(folder(slug) / 'rangkuman.json', None) or {}).get('brief_versi'),
           'contoh': (baca_json(folder(slug) / 'contoh.json', None) or {}).get('brief_versi'),
           'estimasi': p.get('estimasi_brief_versi')}
    keluaran = {}
    for k, dari in kel.items():
        if dari is None:
            continue
        berubah = sorted({b for r in riwayat if r['versi'] > dari for b in r['bagian'] if b in BAHAN_KELUARAN[k]},
                         key=list(BAGIAN_BRIEF).index)
        keluaran[k] = {'dari': dari, 'usang': [BAGIAN_BRIEF[b] for b in berubah]}
    return {'versi': versi_brief(p), 'riwayat': [{**r, 'bagian': [BAGIAN_BRIEF.get(b, b) for b in r['bagian']]}
                                                 for r in riwayat[-30:][::-1]],
            'keluaran': keluaran}


# --- Proses latar ---------------------------------------------------------

def pid_hidup(pid):
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    # Zombie masih "ada" untuk kill(0); anggap mati
    try:
        return Path(f'/proc/{int(pid)}/stat').read_text().split(') ')[1][0] != 'Z'
    except (OSError, IndexError):
        return False


def pekerjaan(slug):
    """Pekerjaan latar yang sedang berjalan untuk project ini (atau None)."""
    for (s, _), pr in list(_proses.items()):
        if s == slug:
            pr.poll()
    job = (baca_json(folder(slug) / 'proyek.json', {}) or {}).get('job')
    if job and pid_hidup(job.get('pid')):
        return job
    return None


def jalankan(slug, jenis, perintah, env_tambahan=None, log=None):
    """Mulai skrip latar. Satu pekerjaan per project; log ditimpa per jenis."""
    with _kunci_mulai:
        if pekerjaan(slug):
            return None, 'sedang_berjalan'
        env = dict(os.environ, HOME='/root',
                   PATH='/root/.local/bin:/root/.config/composer/vendor/bin:/usr/local/bin:/usr/bin:/usr/sbin:/bin:/sbin',
                   **(env_tambahan or {}))
        log = log or folder(slug) / f'log-{jenis}.log'
        with open(log, 'w') as lf:
            pr = subprocess.Popen(perintah, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                  env=env, cwd='/root', start_new_session=True)
        _proses[(slug, jenis)] = pr
        ubah_proyek(slug, lambda p: p.update(job={'jenis': jenis, 'pid': pr.pid, 'mulai': sekarang()}))
        return pr.pid, None


# --- Tahap ------------------------------------------------------------------

def nama_app(slug):
    return (baca_json(folder(slug) / 'proyek.json', {}) or {}).get('app') or ''


def install_state(slug):
    app = nama_app(slug)
    return (baca_json(DASAR / f'{app}.json', {}) or {}) if app else {}


def tahap(p, fitur, inst):
    if not p.get('estimasi_kunci'):
        return 'estimasi' if fitur else 'brief'
    if inst.get('status') != 'ok':
        return 'install'
    if any(f.get('status') in ('antre', 'jalan', 'gagal', 'revisi') for f in fitur):
        return 'agen'
    if any(f.get('status') == 'dites' for f in fitur):
        # Review baru terbuka sesudah deploy dev terakhir lolos (laravel-agen, akhir run / tombol Deploy dev)
        return 'review' if ((p.get('agen') or {}).get('deploy') or {}).get('ok') else 'agen'
    return 'selesai'


def ringkas(slug):
    p = baca_json(folder(slug) / 'proyek.json', {}) or {}
    fitur = baca_json(folder(slug) / 'fitur.json', []) or []
    inst = install_state(slug)
    hitung = {s: sum(1 for f in fitur if f.get('status') == s) for s in STATUS_FITUR}
    return {
        **{k: p.get(k) for k in ('slug', 'judul', 'klien', 'domain', 'onprogress', 'app', 'pm', 'dibuat', 'estimasi_kunci')},
        'tahap': tahap(p, fitur, inst), 'job': pekerjaan(slug),
        'status_proyek': status_proyek(p), 'status_info': p.get('status'),
        'fitur_total': len(fitur), 'fitur_status': hitung,
        'jam_agen': round(sum(float(f.get('jam_agen') or 0) for f in fitur), 1),
        'jam_webmaster': round(sum(float(f.get('jam_webmaster') or 0) for f in fitur), 1),
        'install': {k: inst.get(k) for k in ('status', 'port', 'url', 'repo', 'langkah', 'total', 'galat', 'mulai', 'selesai')},
        'agen': p.get('agen') or {},
        'brief_versi': versi_brief(p),
        'review': info_review(p, fitur),
        'token': token_proyek(slug),
    }


# Total token Claude per project di daftar /installer/laravel (permintaan user 2026-10-01).
# laravel-brief & laravel-agen mencatat ke usage.jsonl dengan domain = slug project.
_cache_token = {}


def token_proyek(slug):
    """{'total', 'panggilan', 'biaya_usd', 'brief', 'agen'} atau None bila belum ada pemakaian."""
    try:
        st = AI_USAGE.stat()
    except OSError:
        return None
    kunci = (st.st_mtime_ns, st.st_size)
    if _cache_token.get('kunci') != kunci:
        per = {}
        for s in AI_USAGE.read_text(errors='replace').splitlines():
            try:
                b = json.loads(s)
            except ValueError:
                continue
            if not isinstance(b, dict) or not str(b.get('peran') or '').startswith('laravel_'):
                continue
            d = per.setdefault(b.get('domain') or '-', {'total': 0, 'panggilan': 0, 'biaya_usd': 0.0, 'brief': 0, 'agen': 0})
            n = int(b.get('total_tokens') or 0)
            d['total'] += n
            d['panggilan'] += int(b.get('permintaan') or 1)
            d['biaya_usd'] += float(b.get('biaya_usd') or 0)
            d['agen' if b['peran'] == 'laravel_agen' else 'brief'] += n
        for d in per.values():
            d['biaya_usd'] = round(d['biaya_usd'], 2)
        _cache_token.clear()
        _cache_token.update(kunci=kunci, data=per)
    return _cache_token['data'].get(slug)


def daftar():
    if not PROYEK.is_dir():
        return []
    semua = [ringkas(d.name) for d in PROYEK.iterdir() if (d / 'proyek.json').is_file()]
    return sorted(semua, key=lambda x: x.get('dibuat') or 0, reverse=True)


def detail(slug):
    if not (folder(slug) / 'proyek.json').is_file():
        return None
    p = baca_json(folder(slug) / 'proyek.json', {})
    return {
        **ringkas(slug),
        'riwayat': (p.get('riwayat') or [])[-50:][::-1],
        'catatan': baca_teks(slug, 'catatan.md'),
        'design': baca_teks(slug, 'DESIGN.md'),
        'prd': baca_teks(slug, 'PRD.md'),
        'database': baca_teks(slug, 'DATABASE.md'),
        'flowchart': baca_teks(slug, 'FLOWCHART.md'),
        'fitur': baca_json(folder(slug) / 'fitur.json', []) or [],
        'saran_app': saran_app(p),
        'github_org': org_github(p),
        'tambahan': p['tambahan'] if 'tambahan' in p else tambahan_bawaan(baca_json(folder(slug) / 'fitur.json', []) or [], jalur_laravel(slug)),
        'tambahan_bawaan': 'tambahan' not in p,
        'jadwal': dasar_jadwal(slug),
        'tim': tim_crm(),
        'ringkasan_brief': p.get('ringkasan_brief') or [],
        'catatan_diagram': p.get('catatan_diagram') or [],
        'saran': baca_json(folder(slug) / 'saran.json', None),
        'konten': p.get('konten'),
        'pertanyaan_dijawab': p.get('pertanyaan_dijawab') or [],
        'rangkuman': info_rangkuman(slug),
        'contoh': info_contoh(slug),
        'contoh_platform': platform_contoh(slug),
        'dokumen': daftar_dok(slug),
        'brief': info_versi_brief(slug, p),
        'kalibrasi': kalibrasi_agen(),
        'cakupan': cek_cakupan(baca_teks(slug, 'PRD.md'), baca_json(folder(slug) / 'fitur.json', []) or []),
    }


# Identitas commit repo installer Laravel = akun GitHub VelocityDeveloper (email noreply akun, supaya commit terhubung)
GIT_NAMA = 'Velocity Developer'
GIT_EMAIL = '76415135+VelocityDeveloper@users.noreply.github.com'

ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]|\x1b\].*?(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]|\x1b[=>78]')


def bersih_terminal(teks):
    """Buang kode warna ANSI; baris ber-\\r (progress bar) disisakan bagian terakhirnya."""
    teks = ANSI_RE.sub('', teks)
    return '\n'.join(b.rstrip('\r').rsplit('\r', 1)[-1] for b in teks.split('\n'))


def log(slug, jenis):
    path = DASAR / f'{nama_app(slug)}.log' if jenis == 'install' else folder(slug) / f'log-{jenis}.log'
    try:
        return bersih_terminal(path.read_text(errors='replace')).splitlines()[-800:]
    except OSError:
        return []


# --- Port & prasyarat -------------------------------------------------------

def _port_terpakai():
    pakai = set()
    try:
        pakai |= {int(x['port']) for x in json.loads(LOCAL_PROJECTS.read_text()).get('projects', []) if x.get('port')}
    except (OSError, ValueError, TypeError, KeyError):
        pass
    for f in DASAR.glob('*.json'):
        try:
            d = json.loads(f.read_text())
            if isinstance(d, dict):  # proyek-terhapus.json berisi list
                pakai.add(int(d.get('port')))
        except (OSError, ValueError, TypeError):
            pass
    try:
        out = subprocess.run(['ss', '-Hltn'], capture_output=True, text=True, timeout=5).stdout
        for baris in out.splitlines():
            kol = baris.split()
            if len(kol) >= 4 and kol[3].rpartition(':')[2].isdigit():
                pakai.add(int(kol[3].rpartition(':')[2]))
    except (OSError, subprocess.SubprocessError):
        pass
    return pakai


def port_berikut():
    # Kelipatan 10 mengikuti pola project lokal (8010, 8020, 8040, ...)
    pakai = _port_terpakai()
    return next((p for p in range(PORT_AWAL, PORT_AKHIR + 1, 10) if p not in pakai), None)


_prasyarat_cache = {'t': 0, 'v': None}


def prasyarat():
    if time.time() - _prasyarat_cache['t'] > 60:
        try:
            gh = subprocess.run(['gh', 'auth', 'status'], capture_output=True, timeout=15).returncode == 0
        except (OSError, subprocess.SubprocessError):
            gh = False
        _prasyarat_cache.update(t=time.time(), v={'db_root': DB_CNF.is_file(), 'github': gh})
    return _prasyarat_cache['v']


# --- Aksi -------------------------------------------------------------------

def _teks(payload, kunci, wajib=False):
    v = str(payload.get(kunci) or '').strip()
    if (wajib and not v) or not TEKS_RE.match(v):
        raise ValueError(f'invalid_{kunci}')
    return v


def id_berikut():
    PROYEK.mkdir(parents=True, exist_ok=True)
    nomor = [int(d.name.split('-')[1]) for d in PROYEK.iterdir() if ID_RE.match(d.name)]
    # Nomor project yang sudah dihapus tidak dipakai ulang: token usage.jsonl & log tercatat per slug
    nomor += [int(x.split('-')[1]) for x in (baca_json(TERHAPUS, []) or []) if ID_RE.match(str(x))]
    return f'project-{max(nomor, default=0) + 1:03d}'


def cek_onprogress(nama):
    # Kebanyakan folder On Progress bernama domain, tapi ada juga nama usaha ("PT ...") — keduanya sah
    nama = str(nama or '').strip()
    if not nama:
        return ''
    if '/' in nama or nama.startswith('.') or len(nama) > 150 or not (ON_PROGRESS / nama).is_dir():
        raise ValueError('onprogress_tidak_ada')
    return nama


def domain_dari(nama):
    return nama.lower() if DOMAIN_RE.match(nama.lower()) else ''


def cari_onprogress(q, batas=20):
    q = q.strip().lower()
    if len(q) < 2 or not ON_PROGRESS.is_dir():
        return []
    dipakai = {x.get('onprogress'): x.get('slug') for x in daftar() if x.get('onprogress')}
    hasil = []
    for d in sorted(ON_PROGRESS.iterdir()):
        if q in d.name.lower() and d.is_dir():
            hasil.append({'nama': d.name, 'dipakai': dipakai.get(d.name)})
            if len(hasil) >= batas:
                break
    return hasil


def saran_app(p):
    """Nama aplikasi bawaan: dari relasi On Progress (namaklien.com -> namaklien), kalau tidak dari judul."""
    op = p.get('onprogress') or ''
    dasar = (op.split('.')[0] if domain_dari(op) else op) or p.get('judul') or ''
    s = re.sub(r'[^a-z0-9]+', '-', dasar.lower()).strip('-')[:32].strip('-')
    if s and not s[0].isalpha():
        s = 'app-' + s
    return s[:32].strip('-')


def buat(payload):
    judul, klien, oleh = _teks(payload, 'judul', True), _teks(payload, 'klien'), _teks(payload, 'oleh', True)
    onprogress = cek_onprogress(payload.get('onprogress'))
    with _kunci_mulai:
        slug = id_berikut()
        folder(slug).mkdir(parents=True)
    tulis_json(folder(slug) / 'proyek.json', {'slug': slug, 'judul': judul, 'klien': klien, 'onprogress': onprogress,
                                              'domain': domain_dari(onprogress), 'pm': oleh, 'dibuat': sekarang(), 'riwayat': []})
    tulis_json(folder(slug) / 'fitur.json', [])
    catat(slug, oleh, 'membuat project' + (f' (relasi On Progress {onprogress})' if onprogress else ''))
    return {'slug': slug}


def ubah_identitas(slug, payload):
    """Judul, klien, relasi On Progress, dan domain produksi bisa diubah sampai install dimulai."""
    oleh = _teks(payload, 'oleh', True)
    if install_state(slug).get('status') in ('jalan', 'ok'):
        raise ValueError('sudah_diinstall')
    baru = {'judul': _teks(payload, 'judul', True), 'klien': _teks(payload, 'klien'),
            'onprogress': cek_onprogress(payload.get('onprogress'))}
    domain = str(payload.get('domain') or domain_dari(baru['onprogress']) or '').strip().lower()
    if domain and not DOMAIN_RE.match(domain):
        raise ValueError('invalid_domain')
    baru['domain'] = domain
    ubah_proyek(slug, lambda p: p.update(baru))
    catat(slug, oleh, 'mengubah identitas project' + (f' (relasi On Progress {baru["onprogress"]})' if baru['onprogress'] else ''))
    return baru


def _bersihkan_halaman(daftar):
    """[{halaman, peran[]}] = sel Matriks peran × halaman PRD yang dikerjakan fitur ini."""
    hasil = []
    for h in (daftar if isinstance(daftar, list) else [])[:40]:
        if not isinstance(h, dict):
            continue
        nama = str(h.get('halaman') or '').strip()[:120]
        peran = [str(x).strip()[:60] for x in (h.get('peran') or []) if str(x).strip()][:12]
        if nama and peran:
            hasil.append({'halaman': nama, 'peran': peran})
    return hasil


def _bersihkan_fitur(daftar_fitur):
    """Validasi fitur dari editor estimasi PM. Status & hasil agen tidak bisa diubah dari sini."""
    if not isinstance(daftar_fitur, list) or len(daftar_fitur) > 80:
        raise ValueError('invalid_fitur')
    bersih, ids = [], set()
    for i, f in enumerate(daftar_fitur, 1):
        if not isinstance(f, dict):
            raise ValueError('invalid_fitur')
        judul = str(f.get('judul') or '').strip()[:120]
        if not judul:
            raise ValueError('fitur_tanpa_judul')
        kriteria = [str(k.get('teks') if isinstance(k, dict) else k).strip()[:400]
                    for k in (f.get('kriteria') or [])]
        kriteria = [k for k in kriteria if k][:30]
        if not kriteria:
            raise ValueError('fitur_tanpa_kriteria')
        try:
            jam_agen = max(0.0, min(200.0, float(f.get('jam_agen') or 0)))
            jam_wm = max(0.0, min(200.0, float(f.get('jam_webmaster') or 0)))
        except (TypeError, ValueError):
            raise ValueError('invalid_jam')
        fid = f'F{i:02d}'
        ids.add(fid)
        bersih.append({'id': fid, 'judul': judul, 'deskripsi': str(f.get('deskripsi') or '').strip()[:4000],
                       'kriteria': [{'teks': k} for k in kriteria], 'jam_agen': jam_agen, 'jam_webmaster': jam_wm,
                       'halaman': _bersihkan_halaman(f.get('halaman')), 'status': 'antre'})
    return bersih


def tambahan_bawaan(fitur, laravel=True):
    """Pekerjaan di luar fitur (usulan awal; PM menyesuaikan). Revisi klien = ±25% jam fitur.
    Platform non-Laravel: tanpa agen otomatis, jam agen dipindah ke webmaster."""
    agen = sum(float(f.get('jam_agen') or 0) for f in fitur)
    wm = sum(float(f.get('jam_webmaster') or 0) for f in fitur)
    bulat = lambda x: round(x * 2) / 2  # noqa: E731
    if not laravel:
        return [{**t, 'jam_agen': 0, 'jam_webmaster': t['jam_webmaster'] + t['jam_agen']}
                for t in tambahan_bawaan(fitur)]
    return [
        {'judul': 'Penyesuaian dari jawaban klien atas pertanyaan terbuka', 'jam_agen': 2, 'jam_webmaster': 2},
        {'judul': 'Impor data awal dari klien (barang, harga, stok, pengguna)', 'jam_agen': 1, 'jam_webmaster': 2},
        {'judul': 'UAT: klien mencoba aplikasi & mengumpulkan revisi', 'jam_agen': 0, 'jam_webmaster': 2},
        {'judul': 'Revisi hasil UAT klien', 'jam_agen': bulat(agen * 0.25), 'jam_webmaster': bulat(wm * 0.25)},
        {'judul': 'Deploy produksi (server, domain, SSL, data awal)', 'jam_agen': 0, 'jam_webmaster': 4},
        {'judul': 'Serah terima & pelatihan pengguna', 'jam_agen': 0, 'jam_webmaster': 2},
    ]


def bersihkan_tambahan(daftar_tambahan):
    if not isinstance(daftar_tambahan, list) or len(daftar_tambahan) > 30:
        raise ValueError('invalid_tambahan')
    hasil = []
    for t in daftar_tambahan:
        if not isinstance(t, dict) or not str(t.get('judul') or '').strip():
            raise ValueError('tambahan_tanpa_judul')
        try:
            hasil.append({'judul': str(t['judul']).strip()[:160],
                          'jam_agen': max(0.0, min(200.0, float(t.get('jam_agen') or 0))),
                          'jam_webmaster': max(0.0, min(200.0, float(t.get('jam_webmaster') or 0)))})
        except (TypeError, ValueError):
            raise ValueError('invalid_jam')
    return hasil


JALUR = ('wordpress', 'laravel_vue', 'lainnya')
HOSTING = ('shared_hosting', 'shared_lalu_vps', 'vps', 'cloud_khusus')


def bersihkan_saran(data, model=''):
    """Keluaran Claude tahap saran platform -> isi saran.json (opsi diurutkan skor, rekomendasi pasti ada)."""
    def daftar_teks(x, maks):
        return [str(t).strip() for t in (x or []) if str(t).strip()][:maks]
    opsi, dipakai = [], set()
    for o in data.get('opsi') or []:
        kunci = re.sub(r'[^a-z0-9_]+', '_', str(o.get('kunci') or o.get('jalur') or 'opsi').lower()).strip('_')[:40] or 'opsi'
        while kunci in dipakai:
            kunci += '_2'
        dipakai.add(kunci)
        try:
            skor = max(1, min(10, round(float(o.get('skor') or 0))))
        except (TypeError, ValueError):
            skor = 1
        opsi.append({
            'kunci': kunci, 'jalur': o.get('jalur') if o.get('jalur') in JALUR else 'lainnya',
            'nama': str(o.get('nama') or kunci).strip()[:80], 'stack': str(o.get('stack') or '').strip()[:800],
            'skor': skor, 'kelebihan': daftar_teks(o.get('kelebihan'), 8), 'kekurangan': daftar_teks(o.get('kekurangan'), 8),
            'cocok_bila': str(o.get('cocok_bila') or '').strip()[:600],
            'perkiraan_waktu': str(o.get('perkiraan_waktu') or '').strip()[:120],
            'biaya_berjalan': str(o.get('biaya_berjalan') or '').strip()[:600],
            'hosting': o.get('hosting') if o.get('hosting') in HOSTING else '',
            'syarat_server': [t[:40] for t in daftar_teks(o.get('syarat_server'), 6)],
        })
    if not opsi:
        raise ValueError('saran_kosong')
    opsi.sort(key=lambda o: -o['skor'])
    rek = str(data.get('rekomendasi') or '')
    rek = rek if rek in dipakai else opsi[0]['kunci']
    return {'waktu': sekarang(), 'model': model, 'rekomendasi': rek, 'alasan': str(data.get('alasan') or '').strip(),
            'opsi': opsi, 'pertanyaan_klien': daftar_teks(data.get('pertanyaan_klien'), 8), 'pilihan': None}


def pilih_platform(slug, payload):
    """PM memilih salah satu opsi saran platform (dicatat; membuka tombol lanjut susun PRD, DESIGN.md & diagram)."""
    oleh = _teks(payload, 'oleh', True)
    path = folder(slug) / 'saran.json'
    kunci = str(payload.get('kunci') or '')
    with terkunci(slug):
        saran = baca_json(path, None)
        if not saran:
            raise ValueError('saran_belum_ada')
        o = next((x for x in saran['opsi'] if x['kunci'] == kunci), None)
        if not o:
            raise ValueError('opsi_tidak_ada')
        saran['pilihan'] = {'kunci': kunci, 'jalur': o['jalur'], 'oleh': oleh, 'waktu': sekarang()}
        tulis_json(path, saran)
    catat(slug, oleh, f"memilih platform {o['nama']}")
    return {'pilihan': saran['pilihan']}


def simpan(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    p = baca_json(folder(slug) / 'proyek.json', {})
    diubah, berubah_brief = [], []
    for kunci, nama in (('catatan', 'catatan.md'), ('design', 'DESIGN.md'), ('prd', 'PRD.md'),
                        ('database', 'DATABASE.md'), ('flowchart', 'FLOWCHART.md')):
        if kunci in payload:
            isi = str(payload[kunci] or '')
            if len(isi) > MD_MAKS:
                raise ValueError('terlalu_panjang')
            if kunci != 'catatan' and p.get('estimasi_kunci'):
                raise ValueError('sudah_dikunci')
            if isi != baca_teks(slug, nama):
                tulis_teks(slug, nama, isi)
                diubah.append(nama)
                berubah_brief.append(kunci)
    if 'fitur' in payload:
        if p.get('estimasi_kunci'):
            raise ValueError('sudah_dikunci')
        fitur = _bersihkan_fitur(payload['fitur'])
        ubah_fitur(slug, lambda f: f.__setitem__(slice(None), fitur))
        diubah.append('estimasi')
    if 'tambahan' in payload:
        if p.get('estimasi_kunci'):
            raise ValueError('sudah_dikunci')
        tambahan = bersihkan_tambahan(payload['tambahan'])
        ubah_proyek(slug, lambda x: x.update(tambahan=tambahan))
        diubah.append('pekerjaan di luar fitur')
    if 'konten' in payload:
        mode = payload['konten'] or None
        if mode is not None and mode not in KONTEN_MODE:
            raise ValueError('konten_tidak_sah')
        if (p.get('konten') or {}).get('mode') != mode:
            ubah_proyek(slug, lambda x: x.update(konten={'mode': mode, 'oleh': oleh, 'waktu': sekarang()})
                        if mode else x.pop('konten', None))
            diubah.append('kebutuhan konten: ' + (KONTEN_MODE[mode] if mode else 'belum ditandai'))
            berubah_brief.append('konten')
    if diubah:
        v = naik_versi_brief(slug, oleh, berubah_brief) if berubah_brief else 0
        catat(slug, oleh, 'menyimpan ' + ', '.join(diubah) + (f' (brief v{v})' if v else ''))
    return {'disimpan': diubah, 'brief_versi': versi_brief(baca_json(folder(slug) / 'proyek.json', {}))}


# Panel "Pertanyaan untuk klien" (7 Okt): PM mencentang pertanyaan yang sudah dijawab klien. Kunci = teks pertanyaan
# (dipotong 300 karakter), jadi pertanyaan yang sama dari PRD/Rangkuman/Saran ikut tercentang. Tidak menaikkan versi brief.
def tandai_pertanyaan(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    kunci = ' '.join(str(payload.get('kunci') or '').split())[:300]
    if not kunci:
        raise ValueError('kunci_kosong')
    dijawab = bool(payload.get('dijawab'))

    def ubah(p):
        daftar = [x for x in (p.get('pertanyaan_dijawab') or []) if x != kunci]
        if dijawab:
            daftar.append(kunci)
        p['pertanyaan_dijawab'] = daftar[-300:]
    ubah_proyek(slug, ubah)
    catat(slug, oleh, ('menandai sudah dijawab klien: ' if dijawab else 'membatalkan tanda dijawab: ') + kunci[:80])
    return {'kunci': kunci, 'dijawab': dijawab}


def ubah_status(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    nilai = str(payload.get('nilai') or '')
    if nilai not in STATUS_PROYEK:
        raise ValueError('status_tidak_sah')
    alasan = str(payload.get('alasan') or '').strip()[:500]
    if nilai != 'aktif' and pekerjaan(slug):
        raise ValueError('sedang_berjalan')
    if nilai == 'aktif':
        ubah_proyek(slug, lambda p: p.pop('status', None))
    else:
        ubah_proyek(slug, lambda p: p.update(status={'nilai': nilai, 'alasan': alasan, 'oleh': oleh, 'waktu': sekarang()}))
    catat(slug, oleh, f'mengubah status project jadi {STATUS_PROYEK[nilai]}' + (f' — {alasan}' if alasan and nilai != 'aktif' else ''))
    return {'status_proyek': nilai}


# Hapus project (permintaan user 2026-10-05: project ujicoba menumpuk di daftar). Hanya project yang BELUM diinstall
# (app/database/repo GitHub/layanan dev tidak ikut terhapus — itu dibereskan manual). Folder data dipindah ke
# CADANGAN_HAPUS (bukan rm), preview contoh di nglorok.com dicabut, nomornya dicatat di TERHAPUS agar tak dipakai ulang.
CADANGAN_HAPUS = Path('/root/velocity-cadangan/laravel-proyek-terhapus')
TERHAPUS = DASAR / 'proyek-terhapus.json'


def cabut_preview(slug):
    """Hapus folder contoh di VPS preview (best effort) -> pesan galat atau ''."""
    terbit = ((baca_json(folder(slug) / 'contoh.json', {}) or {}).get('terbit') or {})
    kode = (baca_json(folder(slug) / 'proyek.json', {}) or {}).get('contoh_kode')
    k = konfig_preview()
    if not (terbit and kode and k and re.fullmatch(r'[a-z0-9-]+', kode)):
        return ''
    tujuan = f"{k['PREVIEW_DIR'].rstrip('/')}/{kode}"
    ssh = ['ssh', '-p', k.get('PREVIEW_PORT') or '22', '-i', str(KUNCI_SSH), '-o', 'BatchMode=yes',
           '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=15']
    try:
        r = subprocess.run(ssh + [f"{k.get('PREVIEW_USER') or 'root'}@{k['PREVIEW_HOST']}", f"rm -rf '{tujuan}'"],
                           capture_output=True, text=True, timeout=40)
        return (r.stderr or r.stdout).strip()[-300:] if r.returncode else ''
    except (OSError, subprocess.SubprocessError) as e:
        return f'{type(e).__name__}: {e}'[:300]


def hapus_proyek(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    if str(payload.get('konfirmasi') or '').strip() != slug:
        raise ValueError('konfirmasi_salah')
    with _kunci_mulai:
        if pekerjaan(slug):
            raise ValueError('sedang_berjalan')
        p = baca_json(folder(slug) / 'proyek.json', {}) or {}
        if p.get('app') or install_state(slug).get('status'):
            raise ValueError('sudah_diinstall')
        galat_preview = cabut_preview(slug)
        CADANGAN_HAPUS.mkdir(parents=True, exist_ok=True)
        tujuan = CADANGAN_HAPUS / f"{slug}-{time.strftime('%Y%m%d-%H%M%S')}"
        with terkunci(slug):
            terhapus = baca_json(TERHAPUS, []) or []
            tulis_json(TERHAPUS, sorted(set(terhapus) | {slug}))
            (folder(slug) / '.kunci').unlink(missing_ok=True)
            shutil.move(str(folder(slug)), str(tujuan))
    for k in [k for k in _proses if k[0] == slug]:
        _proses.pop(k, None)
    try:
        with open(tujuan / 'dihapus.json', 'w') as f:
            json.dump({'oleh': oleh, 'waktu': sekarang(), 'judul': p.get('judul')}, f, ensure_ascii=False)
    except OSError:
        pass
    return {'dihapus': slug, 'cadangan': str(tujuan), 'galat_preview': galat_preview}


def kunci_estimasi(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    buka = bool(payload.get('buka'))
    fitur = baca_json(folder(slug) / 'fitur.json', []) or []
    if buka:
        if install_state(slug).get('status') in ('jalan', 'ok'):
            raise ValueError('sudah_diinstall')
        ubah_proyek(slug, lambda p: p.pop('estimasi_kunci', None))
        catat(slug, oleh, 'membuka kunci estimasi')
        return {'kunci': None}
    if not fitur:
        raise ValueError('fitur_kosong')
    if not baca_teks(slug, 'PRD.md').strip() or not baca_teks(slug, 'DESIGN.md').strip():
        raise ValueError('dokumen_kosong')
    k = {'oleh': oleh, 'waktu': sekarang()}
    ubah_proyek(slug, lambda p: p.update(estimasi_kunci=k))
    catat(slug, oleh, 'mengunci estimasi')
    return {'kunci': k}


def jalur_platform(slug):
    """Jalur platform pilihan PM di Saran platform: 'wordpress' | 'laravel_vue' | 'lainnya' | None (belum memilih)."""
    return ((baca_json(folder(slug) / 'saran.json', None) or {}).get('pilihan') or {}).get('jalur')


def jalur_laravel(slug):
    """True bila project mengikuti alur Laravel + Vue (termasuk project lama yang belum memakai Saran platform)."""
    return jalur_platform(slug) in (None, 'laravel_vue')


def mulai_brief(slug, payload, jenis):
    oleh = _teks(payload, 'oleh', True)
    p = baca_json(folder(slug) / 'proyek.json', {})
    # Rangkuman & contoh tampilan hanya membaca bahan (tidak mengubah spesifikasi): tetap boleh sesudah estimasi dikunci
    if p.get('estimasi_kunci') and jenis not in ('rangkuman', 'contoh'):
        raise ValueError('sudah_dikunci')
    if jenis == 'contoh':
        arahan = str(payload.get('arahan') or '').strip()[:2000]
        ubah_proyek(slug, lambda x: x.update(contoh_arahan=arahan))
    if jenis in ('saran', 'susun', 'rangkuman', 'contoh') and not baca_teks(slug, 'catatan.md').strip() and not daftar_dok(slug):
        raise ValueError('catatan_kosong')
    if jenis == 'susun' and not baca_teks(slug, 'PRD.md').strip() and not jalur_platform(slug):
        # Project baru: platform dipilih dulu dari saran; PRD & DESIGN.md bisa untuk platform apa pun
        raise ValueError('platform_belum_dipilih')
    if jenis in ('estimasi', 'diagram') and not baca_teks(slug, 'PRD.md').strip():
        raise ValueError('prd_kosong')
    pid, err = jalankan(slug, jenis, [str(BRIEF), slug, jenis])
    if err:
        raise ValueError(err)
    catat(slug, oleh, 'meminta Claude ' + {'saran': 'menyarankan platform (WordPress / Laravel+Vue / lainnya)',
                                           'susun': 'menyusun DESIGN.md, PRD.md, relasi database & flowchart',
                                           'diagram': 'menyusun relasi database & flowchart dari PRD',
                                           'estimasi': 'memecah fitur & estimasi',
                                           'rangkuman': 'menyusun Rangkuman Website Konsep (Word)',
                                           'contoh': 'membuat contoh tampilan untuk klien'}[jenis])
    return {'pid': pid}


def mulai_install(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    p = baca_json(folder(slug) / 'proyek.json', {})
    if not p.get('estimasi_kunci'):
        raise ValueError('estimasi_belum_dikunci')
    if not jalur_laravel(slug):
        # Estimasi berlaku untuk semua platform; install & agen otomatis hanya jalur Laravel + Vue
        raise ValueError('khusus_laravel')
    inst = install_state(slug)
    if inst.get('status') in ('jalan', 'ok'):
        raise ValueError('sudah_diinstall')
    app = str(payload.get('app') or '').strip().lower()
    if not SLUG_RE.match(app) or '--' in app or ID_RE.match(app):
        raise ValueError('invalid_app')
    lain = next((x for x in daftar() if x.get('app') == app and x.get('slug') != slug), None)
    # Status install lama milik nama yang sama boleh ditimpa hanya bila run sebelumnya gagal
    if Path('/home', app).exists() or lain or ((DASAR / f'{app}.json').exists() and inst.get('status') != 'gagal'):
        raise ValueError('folder_exists')
    if not DB_CNF.is_file():
        raise ValueError('db_root_missing')
    port = port_berikut()
    if port is None:
        raise ValueError('no_port')
    (DASAR / f'{app}.json').unlink(missing_ok=True)
    ubah_proyek(slug, lambda p: p.update(app=app))
    lanjut_agen = '1' if payload.get('lanjut_agen', True) else '0'
    pid, err = jalankan(slug, 'install', [str(INSTALLER)], log=DASAR / f'{app}.log', env_tambahan={
        'SLUG': app, 'JUDUL': p['judul'], 'KLIEN': p.get('klien', ''), 'DOMAIN': p.get('domain', ''),
        'PORT': str(port), 'OLEH': oleh, 'GITHUB_ORG': org_github(p), 'PROYEK_ID': slug, 'PROYEK_DIR': str(folder(slug)), 'LANJUT_AGEN': lanjut_agen})
    if err:
        raise ValueError(err)
    catat(slug, oleh, f'menjalankan install {app} (port {port})')
    return {'pid': pid, 'port': port, 'app': app}


def aksi_agen(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    aksi = payload.get('aksi')
    if aksi == 'berhenti':
        ubah_proyek(slug, lambda p: p.setdefault('agen', {}).update(minta_berhenti=True))
        catat(slug, oleh, 'meminta agen berhenti sesudah fitur yang sedang dikerjakan')
        return {'ok': True}
    if aksi not in ('mulai', 'deploy'):
        raise ValueError('invalid_aksi')
    if install_state(slug).get('status') != 'ok':
        raise ValueError('belum_diinstall')
    if aksi == 'deploy':
        pid, err = jalankan(slug, 'agen', [str(AGEN), slug, '--deploy'])
        if err:
            raise ValueError(err)
        catat(slug, oleh, 'menjalankan deploy dev')
        return {'pid': pid}
    ubah_proyek(slug, lambda p: p.setdefault('agen', {}).update(minta_berhenti=False))
    pid, err = jalankan(slug, 'agen', [str(AGEN), slug])
    if err:
        raise ValueError(err)
    catat(slug, oleh, 'menyerahkan project ke agen Claude')
    return {'pid': pid}


def ulangi_fitur(slug, payload):
    """Fitur gagal -> antre lagi (agen menerima galat sebelumnya sebagai konteks)."""
    oleh = _teks(payload, 'oleh', True)
    fid = str(payload.get('fitur') or '')

    def _(fitur):
        for f in fitur:
            if f['id'] == fid and f.get('status') == 'gagal':
                f['status'] = 'antre'
                return True
        return False
    if not ubah_fitur(slug, _):
        raise ValueError('fitur_tidak_gagal')
    catat(slug, oleh, f'mengantrekan ulang {fid}')
    return {'ok': True}


def review(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    fid = str(payload.get('fitur') or '')
    keputusan = payload.get('keputusan')
    catatan = str(payload.get('catatan') or '').strip()[:4000]
    cek = payload.get('cek') or []
    if keputusan not in ('ok', 'revisi', 'simpan'):
        raise ValueError('invalid_keputusan')
    if keputusan == 'revisi' and not catatan:
        raise ValueError('catatan_revisi_kosong')

    def _(fitur):
        for f in fitur:
            if f['id'] != fid:
                continue
            if f.get('status') not in ('dites', 'ok'):
                raise ValueError('fitur_belum_dites')
            for i, k in enumerate(f['kriteria']):
                k['cek'] = bool(cek[i]) if i < len(cek) else False
            if keputusan == 'ok':
                if not all(k['cek'] for k in f['kriteria']):
                    raise ValueError('kriteria_belum_dicentang')
                f['status'] = 'ok'
            elif keputusan == 'revisi':
                f['status'] = 'revisi'
                f.setdefault('revisi', []).append({'catatan': catatan, 'oleh': oleh, 'waktu': sekarang()})
                # Catatan revisi jadi kriteria baru: agen melaporkan status & bukti, webmaster wajib mencentangnya sebelum OK
                n = len(f['revisi'])
                f['kriteria'].append({'teks': f'Revisi {n}: {catatan}', 'revisi': n, 'cek': False})
            f['review'] = {'oleh': oleh, 'waktu': sekarang(), 'catatan': catatan}
            return True
        return False
    if not ubah_fitur(slug, _):
        raise ValueError('fitur_tidak_ada')
    if keputusan == 'simpan':
        return {'ok': True}
    catat(slug, oleh, f'review {fid}: {"OK" if keputusan == "ok" else "revisi"}')
    return {'ok': True, 'agen_lanjut': lanjut_sesudah_review(slug)}


def lanjut_sesudah_review(slug):
    """Agen yang tertahan gerbang review (menunggu_review) langsung jalan lagi bila semua fitur fondasi sudah
    direview, atau ada revisi yang bisa dikerjakan sambil menunggu. -> True bila agen dimulai."""
    p = baca_json(folder(slug) / 'proyek.json', {})
    fitur = baca_json(folder(slug) / 'fitur.json', []) or []
    if (p.get('agen') or {}).get('status') != 'menunggu_review' or pekerjaan(slug):
        return False
    if gerbang_review(fitur) and not any(f.get('status') == 'revisi' for f in fitur):
        return False
    try:
        aksi_agen(slug, {'oleh': 'Otomatis (sesudah review)', 'aksi': 'mulai'})
        return True
    except ValueError:
        return False


# --- Dokumen klien (tahap Brief) ----------------------------------------------
# Permintaan user 2026-09-29: selain menempel catatan, PM bisa mengunggah dokumen kiriman klien (brief PDF/DOCX,
# daftar kebutuhan XLSX, presentasi, foto/sketsa). Berkas di <proyek>/dokumen/, teksnya diekstrak saat diunggah ke
# dokumen/.teks/<nama>.txt lalu ikut dibaca Claude saat saran platform & susun PRD. Gambar dan PDF hasil scan
# (tanpa lapisan teks) dibaca Claude langsung lewat alat Read (laravel-brief menjalankan Claude di folder ini).

# .xls/.ods/.rtf tidak diterima: LibreOffice di Local PC hanya Impress (tanpa Calc/Writer) jadi tak bisa dibaca
DOK_EKSTENSI = {'.pdf', '.doc', '.docx', '.odt', '.txt', '.md', '.csv', '.xlsx',
                '.ppt', '.pptx', '.pps', '.ppsx', '.odp', '.png', '.jpg', '.jpeg', '.webp', '.gif'}
DOK_GAMBAR = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
DOK_MAKS = 25 * 1024 * 1024
DOK_JUMLAH_MAKS = 30
DOK_NAMA_RE = re.compile(r'[^A-Za-z0-9._() -]+')


def folder_dok(slug):
    return folder(slug) / 'dokumen'


def _nama_dok(nama):
    """Nama berkas aman (tanpa folder) dengan ekstensi yang didukung."""
    nama = DOK_NAMA_RE.sub('_', Path(str(nama or '').replace('\\', '/')).name).strip(' ._')
    stem, ext = os.path.splitext(nama)
    if ext.lower() not in DOK_EKSTENSI or not stem:
        raise ValueError('dokumen_jenis')
    return stem[:90].strip() + ext.lower()


def _teks_xlsx(path):
    """Isi semua sheet .xlsx sebagai baris 'sel | sel | …' (openpyxl tidak terpasang)."""
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    baris = []
    with zipfile.ZipFile(path) as z:
        daftar = z.namelist()
        bersama = []
        if 'xl/sharedStrings.xml' in daftar:
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(f'{ns}si'):
                bersama.append(''.join(t.text or '' for t in si.iter(f'{ns}t')))
        nama_sheet = [s.get('name') for s in ET.fromstring(z.read('xl/workbook.xml')).iter(f'{ns}sheet')] \
            if 'xl/workbook.xml' in daftar else []
        sheet = sorted((n for n in daftar if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', n)),
                       key=lambda n: int(re.search(r'\d+', n.rsplit('/', 1)[1]).group()))
        for i, n in enumerate(sheet):
            baris.append(f"## Sheet: {nama_sheet[i] if i < len(nama_sheet) else i + 1}")
            for row in ET.fromstring(z.read(n)).iter(f'{ns}row'):
                sel = []
                for c in row.iter(f'{ns}c'):
                    v, t = c.find(f'{ns}v'), c.get('t')
                    if t == 's' and v is not None:
                        isi = bersama[int(v.text)] if v.text and v.text.isdigit() and int(v.text) < len(bersama) else ''
                    elif t == 'inlineStr':
                        isi = ''.join(x.text or '' for x in c.iter(f'{ns}t'))
                    else:
                        isi = v.text if v is not None and v.text else ''
                    sel.append(' '.join(isi.split()))
                if any(sel):
                    baris.append(' | '.join(sel).rstrip(' |'))
    return baris


def _ekstrak_dok(path):
    """-> (jenis, teks). jenis: 'teks' (teks ikut prompt), 'visual' (dibaca Claude lewat Read), 'kosong'."""
    ext = path.suffix.lower()
    if ext in DOK_GAMBAR:
        return 'visual', ''
    try:
        if ext in ('.txt', '.md', '.csv'):
            return 'teks', path.read_text(errors='replace')
        if ext == '.pdf':
            r = subprocess.run(['pdftotext', '-layout', '-q', str(path), '-'], capture_output=True, text=True, timeout=90)
            teks = re.sub(r' {3,}', '  ', r.stdout)
            # PDF hasil scan / penuh desain tanpa lapisan teks: Claude membaca halamannya sebagai gambar
            return ('teks', teks) if len(teks.strip()) >= 200 else ('visual', teks)
        if ext == '.xlsx':
            return 'teks', '\n'.join(_teks_xlsx(path))
        from client_form import extract_text
        from presentasi_pdf import PRESENTASI, ke_pdf, teks_pptx
        if ext in PRESENTASI:
            baris = teks_pptx(path) if ext == '.pptx' else []
            pdf = None if baris else ke_pdf(path)  # LibreOffice Impress (terpasang)
            if pdf:
                r = subprocess.run(['pdftotext', '-layout', '-q', str(pdf), '-'], capture_output=True, text=True, timeout=90)
                baris = re.sub(r' {3,}', '  ', r.stdout).splitlines()
            return ('teks', '\n'.join(baris)) if ''.join(baris).strip() else ('kosong', '')
        baris = extract_text(path)  # .docx / .doc / .odt
        return ('teks', '\n'.join(baris)) if baris else ('kosong', '')
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError, subprocess.SubprocessError):
        return 'kosong', ''


def daftar_dok(slug):
    p = baca_json(folder(slug) / 'proyek.json', {}) or {}
    return [d for d in p.get('dokumen') or [] if (folder_dok(slug) / d.get('nama', '')).is_file()]


def _cek_dok_boleh(slug):
    p = baca_json(folder(slug) / 'proyek.json', {}) or {}
    if p.get('estimasi_kunci'):
        raise ValueError('sudah_dikunci')
    job = pekerjaan(slug)
    if job and job.get('jenis') in ('saran', 'susun', 'rangkuman', 'contoh'):
        raise ValueError('sedang_berjalan')


def unggah_dok(slug, nama, oleh, isi):
    """Dipanggil installer_status.py dengan badan mentah (bukan JSON)."""
    if not TEKS_RE.match(oleh or '') or not (oleh or '').strip():
        raise ValueError('invalid_oleh')
    oleh = oleh.strip()
    if status_proyek(baca_json(folder(slug) / 'proyek.json', {})) != 'aktif':
        raise ValueError('proyek_nonaktif')
    if not isi:
        raise ValueError('dokumen_kosong_isi')
    if len(isi) > DOK_MAKS:
        raise ValueError('payload_too_large')
    nama = _nama_dok(nama)
    _cek_dok_boleh(slug)
    d = folder_dok(slug)
    (d / '.teks').mkdir(parents=True, exist_ok=True)
    if len(daftar_dok(slug)) >= DOK_JUMLAH_MAKS:
        raise ValueError('dokumen_terlalu_banyak')
    stem, ext = os.path.splitext(nama)
    n = 2
    while (d / nama).exists():
        nama = f'{stem} ({n}){ext}'
        n += 1
    (d / nama).write_bytes(isi)
    jenis, teks = _ekstrak_dok(d / nama)
    if teks.strip():
        (d / '.teks' / f'{nama}.txt').write_text(teks)
    info = {'nama': nama, 'ukuran': len(isi), 'oleh': oleh, 'waktu': sekarang(), 'jenis': jenis,
            'karakter': len(teks.strip()) if jenis == 'teks' else 0}

    def _(p):
        p['dokumen'] = [x for x in p.get('dokumen') or [] if x.get('nama') != nama] + [info]
    ubah_proyek(slug, _)
    catat(slug, oleh, f'mengunggah dokumen klien {nama} (brief v{naik_versi_brief(slug, oleh, ["dokumen"])})')
    return info


def hapus_dok(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    nama = _nama_dok(payload.get('nama'))
    _cek_dok_boleh(slug)
    if not any(x.get('nama') == nama for x in daftar_dok(slug)):
        raise ValueError('tidak_ada')
    for p in (folder_dok(slug) / nama, folder_dok(slug) / '.teks' / f'{nama}.txt'):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    ubah_proyek(slug, lambda p: p.update(dokumen=[x for x in p.get('dokumen') or [] if x.get('nama') != nama]))
    catat(slug, oleh, f'menghapus dokumen klien {nama} (brief v{naik_versi_brief(slug, oleh, ["dokumen"])})')
    return {'dihapus': nama}


def path_dok(slug, nama):
    """Path berkas untuk diunduh dashboard, atau None."""
    try:
        nama = _nama_dok(nama)
    except ValueError:
        return None
    p = folder_dok(slug) / nama
    return p if any(x.get('nama') == nama for x in daftar_dok(slug)) and p.is_file() else None


def info_rangkuman(slug):
    """Rangkuman Website Konsep terakhir (isi JSON untuk pratinjau) atau None bila belum pernah disusun."""
    docx = folder(slug) / 'rangkuman.docx'
    data = baca_json(folder(slug) / 'rangkuman.json', None)
    if not data or not docx.is_file():
        return None
    return {**data, 'ukuran': docx.stat().st_size, 'nama_berkas': nama_rangkuman(data)}


def nama_rangkuman(data):
    nama = DOK_NAMA_RE.sub('_', str(data.get('judul') or 'Rangkuman Website Konsep')).strip(' ._')[:120]
    return f"{nama or 'Rangkuman Website Konsep'}.docx"


def path_rangkuman(slug):
    """(path, nama unduhan) berkas Word rangkuman, atau None."""
    info = info_rangkuman(slug)
    return (folder(slug) / 'rangkuman.docx', info['nama_berkas']) if info else None


# --- Contoh tampilan (mockup HTML landing + dashboard) untuk dipamerkan ke klien -------------------------
# laravel-brief <id> contoh → <proyek>/contoh/{index.html, dashboard.html (hanya Laravel), aset/} + contoh.json, lalu terbit ke
# VPS preview (nglorok.com, Sumopod) lewat rsync: <PREVIEW_URL>/<kode>/. Kode = slug judul + 6 hex acak supaya
# tautan klien tidak bisa ditebak dari nomor project. Konfigurasi di CONTOH_ENV (tanpa berkas itu: pratinjau lokal saja).
CONTOH_ENV = Path('/etc/velocity/secrets/preview-nglorok.env')
CONTOH_HALAMAN = {'index.html': 'Landing page', 'dashboard.html': 'Dashboard'}
KUNCI_SSH = Path('/root/.ssh/id_ed25519')


def folder_contoh(slug):
    return folder(slug) / 'contoh'


def aset_contoh(slug):
    """Gambar klien yang boleh dipakai mockup: [(nama dokumen, path di mockup 'aset/gambar-N.ext')]."""
    gambar = [x['nama'] for x in daftar_dok(slug) if Path(x['nama']).suffix.lower() in DOK_GAMBAR]
    return [(n, f'aset/gambar-{i}{Path(n).suffix.lower()}') for i, n in enumerate(gambar, 1)]


def platform_contoh(slug):
    """'wordpress' → mockup landing page saja; 'laravel' → landing + dashboard bergaya aplikasi Velocity (SIA VD).
    Urutan: pilihan PM di Saran platform → sudah ada PRD (jalur Laravel) → rekomendasi saran → bawaan laravel."""
    saran = baca_json(folder(slug) / 'saran.json', None) or {}
    jalur = (saran.get('pilihan') or {}).get('jalur')
    if not jalur and not baca_teks(slug, 'PRD.md').strip():
        jalur = next((o.get('jalur') for o in saran.get('opsi') or [] if o.get('kunci') == saran.get('rekomendasi')), None)
    return 'wordpress' if jalur == 'wordpress' else 'laravel'


def info_contoh(slug):
    data = baca_json(folder(slug) / 'contoh.json', None)
    ada = [n for n in CONTOH_HALAMAN if (folder_contoh(slug) / n).is_file()]
    if not data or 'index.html' not in ada:
        return None
    return {**data, 'platform': data.get('platform') or 'laravel', 'platform_kini': platform_contoh(slug),
            'halaman': [{'nama': n, 'label': CONTOH_HALAMAN[n], 'ukuran': (folder_contoh(slug) / n).stat().st_size}
                        for n in ada],
            'bisa_terbit': bool(konfig_preview())}


def path_contoh(slug, nama):
    """Berkas mockup untuk pratinjau di dashboard (index.html, dashboard.html, aset/gambar-N.ext) atau None."""
    if nama not in CONTOH_HALAMAN and not re.fullmatch(r'aset/gambar-\d{1,2}\.(png|jpe?g|webp|gif)', nama or ''):
        return None
    p = folder_contoh(slug) / nama
    return p if p.is_file() else None


def konfig_preview():
    """PREVIEW_HOST/PORT/USER/DIR/URL dari CONTOH_ENV, atau {} bila belum lengkap."""
    k = {}
    try:
        for baris in CONTOH_ENV.read_text().splitlines():
            if '=' in baris and not baris.lstrip().startswith('#'):
                a, b = baris.split('=', 1)
                k[a.strip()] = b.strip().strip('"\'')
    except OSError:
        return {}
    wajib = ('PREVIEW_HOST', 'PREVIEW_DIR', 'PREVIEW_URL')
    return k if all(k.get(x) for x in wajib) else {}


def kode_contoh(slug):
    p = baca_json(folder(slug) / 'proyek.json', {}) or {}
    if p.get('contoh_kode'):
        return p['contoh_kode']
    dasar = re.sub(r'[^a-z0-9]+', '-', re.sub(r'(?i)^website\s+konsep\s+', '', p.get('judul') or slug).lower()).strip('-')
    kode = f"{dasar[:40].strip('-') or 'aplikasi'}-{os.urandom(3).hex()}"
    ubah_proyek(slug, lambda x: x.setdefault('contoh_kode', kode))
    return (baca_json(folder(slug) / 'proyek.json', {}) or {}).get('contoh_kode') or kode


def terbitkan_contoh(slug, oleh='Claude'):
    """rsync folder contoh/ ke VPS preview. -> {'ok', 'url', 'waktu', 'galat'} (juga disimpan di contoh.json)."""
    if not info_contoh(slug):
        raise ValueError('contoh_belum_ada')
    k = konfig_preview()
    if not k:
        raise ValueError('preview_belum_diatur')
    kode = kode_contoh(slug)
    tujuan = f"{k['PREVIEW_DIR'].rstrip('/')}/{kode}/"
    ssh = ['ssh', '-p', k.get('PREVIEW_PORT') or '22', '-i', str(KUNCI_SSH), '-o', 'BatchMode=yes',
           '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=15']
    login = f"{k.get('PREVIEW_USER') or 'root'}@{k['PREVIEW_HOST']}"
    hasil = {'waktu': sekarang(), 'url': f"{k['PREVIEW_URL'].rstrip('/')}/{kode}/", 'ok': False, 'galat': ''}
    try:
        # mkdir lewat ssh dulu (rsync --mkpath butuh rsync ≥3.2.3 di VPS)
        r = subprocess.run(ssh + [login, f"mkdir -p '{tujuan}'"], capture_output=True, text=True, timeout=40)
        if not r.returncode:
            r = subprocess.run(['rsync', '-rt', '--delete', '--chmod=D755,F644', '-e', ' '.join(ssh),
                                f'{folder_contoh(slug)}/', f'{login}:{tujuan}'],
                               capture_output=True, text=True, timeout=120)
        if r.returncode:
            hasil['galat'] = (r.stderr or r.stdout).strip()[-400:]
        else:
            # Pastikan benar-benar tayang lewat Cloudflare/nginx: HTTP 200 DAN isinya mockup kita (pita), karena
            # SPA beranda nglorok.com dulu menjawab 200 untuk alamat apa pun
            c = subprocess.run(['curl', '-s', '-w', '\n%{http_code}', '-m', '20', '-H', 'Cache-Control: no-cache',
                                '-A', 'Mozilla/5.0 (VelocityPreviewCheck)', hasil['url']],
                               capture_output=True, text=True, timeout=30)
            isi, _, hasil['http'] = c.stdout.rpartition('\n')
            hasil['ok'] = hasil['http'] == '200' and 'id="vd-pita"' in isi
            if not hasil['ok']:
                hasil['galat'] = f"berkas terkirim tetapi {hasil['url']} menjawab HTTP {hasil['http'] or '-'}"
    except (OSError, subprocess.SubprocessError) as e:
        hasil['galat'] = f'{type(e).__name__}: {e}'[:400]
    data = baca_json(folder(slug) / 'contoh.json', {}) or {}
    data['terbit'] = hasil
    tulis_json(folder(slug) / 'contoh.json', data)
    catat(slug, oleh, f"menerbitkan contoh tampilan ke {hasil['url']}" if hasil['ok'] else 'gagal menerbitkan contoh tampilan')
    return hasil


def aksi_terbitkan_contoh(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    job = pekerjaan(slug)
    if job and job.get('jenis') == 'contoh':
        raise ValueError('sedang_berjalan')
    return terbitkan_contoh(slug, oleh)


DOK_PROMPT_PER = 40_000
DOK_PROMPT_TOTAL = 150_000


def bahan_dok(slug):
    """-> (blok teks untuk prompt, daftar nama berkas visual yang harus dibaca Claude dengan Read)."""
    bagian, visual, sisa = [], [], DOK_PROMPT_TOTAL
    for x in daftar_dok(slug):
        nama = x['nama']
        if x.get('jenis') == 'visual':
            visual.append(nama)
            continue
        try:
            teks = (folder_dok(slug) / '.teks' / f'{nama}.txt').read_text().strip()
        except OSError:
            teks = ''
        if not teks:
            continue
        batas = min(DOK_PROMPT_PER, sisa)
        if batas <= 0:
            bagian.append(f'<dokumen nama="{nama}">(tidak dimuat: batas panjang bahan tercapai)</dokumen>')
            continue
        potong = teks[:batas] + ('\n…(dipotong)' if len(teks) > batas else '')
        sisa -= len(potong)
        bagian.append(f'<dokumen nama="{nama}">\n{potong}\n</dokumen>')
    blok = ''
    if bagian or visual:
        blok = '\n\n<dokumen_klien>\nDokumen yang diunggah PM dari klien (bahan sama pentingnya dengan catatan diskusi).\n'
        blok += '\n\n'.join(bagian)
        if visual:
            blok += ('\n\nBerkas berikut berupa gambar / PDF hasil scan. WAJIB baca semuanya dengan alat Read '
                     '(ada di folder kerja Anda) sebelum menjawab: ' + ', '.join(f'"{v}"' for v in visual))
        blok += '\n</dokumen_klien>'
    return blok, visual


# --- Router untuk installer_status.py ------------------------------------------

AKSI_POST = {
    'simpan': simpan, 'identitas': ubah_identitas, 'status': ubah_status, 'hapus': hapus_proyek, 'kunci': kunci_estimasi, 'install': mulai_install, 'agen': aksi_agen,
    'ulangi': ulangi_fitur, 'review': review,
    'susun': lambda s, b: mulai_brief(s, b, 'susun'), 'estimasi': lambda s, b: mulai_brief(s, b, 'estimasi'),
    'diagram': lambda s, b: mulai_brief(s, b, 'diagram'), 'saran': lambda s, b: mulai_brief(s, b, 'saran'),
    'pilih_platform': pilih_platform, 'hapus_dokumen': hapus_dok, 'tanya': tandai_pertanyaan,
    'rangkuman': lambda s, b: mulai_brief(s, b, 'rangkuman'),
    'contoh': lambda s, b: mulai_brief(s, b, 'contoh'), 'terbitkan_contoh': aksi_terbitkan_contoh,
}
KODE_GALAT = {'server_tidak_dikenal': 404, 'server_selalu_nyala': 409, 'systemctl_gagal': 500, 'sedang_berjalan': 409, 'slug_dipakai': 409, 'folder_exists': 409, 'sudah_diinstall': 409,
              'sudah_dikunci': 409, 'proyek_nonaktif': 409, 'konfirmasi_salah': 400, 'preview_belum_diatur': 503, 'payload_too_large': 413, 'db_root_missing': 503, 'no_port': 503, 'tidak_ada': 404}


def handle(metode, path, query, payload):
    """-> (kode_http, objek). path diawali /api/laravel."""
    bagian = [x for x in path[len('/api/laravel'):].split('/') if x]
    try:
        if metode == 'GET':
            if not bagian:
                return 200, {'proyek': daftar(), 'port_berikut': port_berikut(), 'prasyarat': prasyarat(),
                             'id_berikut': id_berikut(), 'tim': tim_crm()}
            if bagian == ['server']:
                return 200, server_dev.status_semua()
            if bagian[0] == 'p' and len(bagian) == 2 and ID_RE.match(bagian[1]):
                q = parse_qs(query)
                if 'log' in q:
                    jenis = q['log'][0]
                    if jenis not in ('saran', 'susun', 'diagram', 'estimasi', 'rangkuman', 'contoh', 'install', 'agen'):
                        raise ValueError('invalid_log')
                    return 200, {'log': log(bagian[1], jenis), 'job': pekerjaan(bagian[1])}
                d = detail(bagian[1])
                return (200, d) if d else (404, {'error': 'tidak_ada'})
            if bagian == ['onprogress']:
                return 200, {'hasil': cari_onprogress((parse_qs(query).get('q') or [''])[0])}
            return 404, {'error': 'tidak_ada'}
        if len(bagian) == 3 and bagian[0] == 'server':
            return 200, server_dev.aksi(bagian[1], bagian[2], _teks(payload or {}, 'oleh'))
        if bagian == ['p']:
            return 200, buat(payload)
        if len(bagian) == 3 and bagian[0] == 'p' and ID_RE.match(bagian[1]) and bagian[2] in AKSI_POST:
            if not (folder(bagian[1]) / 'proyek.json').is_file():
                return 404, {'error': 'tidak_ada'}
            if bagian[2] not in ('status', 'hapus') and status_proyek(baca_json(folder(bagian[1]) / 'proyek.json', {})) != 'aktif':
                raise ValueError('proyek_nonaktif')
            return 200, AKSI_POST[bagian[2]](bagian[1], payload)
        return 404, {'error': 'tidak_ada'}
    except ValueError as e:
        kode = str(e)
        return KODE_GALAT.get(kode, 400), {'error': kode}
