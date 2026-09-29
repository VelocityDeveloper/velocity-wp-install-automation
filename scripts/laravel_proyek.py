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
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs

DASAR = Path('/var/lib/velocity/laravel')
PROYEK = DASAR / 'proyek'
SKRIP = Path(__file__).resolve().parent
INSTALLER = SKRIP / 'laravel-installer'
BRIEF = SKRIP / 'laravel-brief'
AGEN = SKRIP / 'laravel-agen'
DB_CNF = Path('/etc/velocity/secrets/mariadb_root.cnf')
LOCAL_PROJECTS = SKRIP.parent / 'config' / 'local-projects.json'
PORT_AWAL, PORT_AKHIR = 8050, 8999
# Semua repo installer Laravel ke org velocitycustomer supaya org utama tidak menumpuk
# (25 Sep untuk project klien; 28 Sep diperluas ke project internal atas permintaan user).
ORG_GITHUB = 'velocitycustomer'
JADWAL = SKRIP.parent / 'config' / 'laravel-jadwal.json'
JADWAL_BAWAAN = {'mesin_mulai': 7, 'mesin_selesai': 22, 'jam_agen_per_project_per_hari': 6,
                 'jam_agen_total_per_hari': 10, 'jam_webmaster_per_hari': 7}


def dasar_jadwal(kecuali=None):
    """Pengaturan jam untuk estimasi + berapa project LAIN yang sedang memakai antrean agen."""
    cfg = dict(JADWAL_BAWAAN)
    cfg.update({k: v for k, v in (baca_json(JADWAL, {}) or {}).items() if k in JADWAL_BAWAAN})
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
        'fitur_total': len(fitur), 'fitur_status': hitung,
        'jam_agen': round(sum(float(f.get('jam_agen') or 0) for f in fitur), 1),
        'jam_webmaster': round(sum(float(f.get('jam_webmaster') or 0) for f in fitur), 1),
        'install': {k: inst.get(k) for k in ('status', 'port', 'url', 'repo', 'langkah', 'total', 'galat', 'mulai', 'selesai')},
        'agen': p.get('agen') or {},
    }


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
        'tambahan': p['tambahan'] if 'tambahan' in p else tambahan_bawaan(baca_json(folder(slug) / 'fitur.json', []) or []),
        'tambahan_bawaan': 'tambahan' not in p,
        'jadwal': dasar_jadwal(slug),
        'tim': tim_crm(),
        'ringkasan_brief': p.get('ringkasan_brief') or [],
        'catatan_diagram': p.get('catatan_diagram') or [],
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
            pakai.add(int(json.loads(f.read_text()).get('port')))
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
                       'status': 'antre'})
    return bersih


def tambahan_bawaan(fitur):
    """Pekerjaan di luar fitur (usulan awal; PM menyesuaikan). Revisi klien = ±25% jam fitur."""
    agen = sum(float(f.get('jam_agen') or 0) for f in fitur)
    wm = sum(float(f.get('jam_webmaster') or 0) for f in fitur)
    bulat = lambda x: round(x * 2) / 2  # noqa: E731
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


def simpan(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    p = baca_json(folder(slug) / 'proyek.json', {})
    diubah = []
    for kunci, nama in (('catatan', 'catatan.md'), ('design', 'DESIGN.md'), ('prd', 'PRD.md'),
                        ('database', 'DATABASE.md'), ('flowchart', 'FLOWCHART.md')):
        if kunci in payload:
            isi = str(payload[kunci] or '')
            if len(isi) > MD_MAKS:
                raise ValueError('terlalu_panjang')
            if kunci != 'catatan' and p.get('estimasi_kunci'):
                raise ValueError('sudah_dikunci')
            tulis_teks(slug, nama, isi)
            diubah.append(nama)
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
    if diubah:
        catat(slug, oleh, 'menyimpan ' + ', '.join(diubah))
    return {'disimpan': diubah}


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


def mulai_brief(slug, payload, jenis):
    oleh = _teks(payload, 'oleh', True)
    p = baca_json(folder(slug) / 'proyek.json', {})
    if p.get('estimasi_kunci'):
        raise ValueError('sudah_dikunci')
    if jenis == 'susun' and not baca_teks(slug, 'catatan.md').strip():
        raise ValueError('catatan_kosong')
    if jenis in ('estimasi', 'diagram') and not baca_teks(slug, 'PRD.md').strip():
        raise ValueError('prd_kosong')
    pid, err = jalankan(slug, jenis, [str(BRIEF), slug, jenis])
    if err:
        raise ValueError(err)
    catat(slug, oleh, 'meminta Claude ' + {'susun': 'menyusun DESIGN.md, PRD.md, relasi database & flowchart',
                                           'diagram': 'menyusun relasi database & flowchart dari PRD',
                                           'estimasi': 'memecah fitur & estimasi'}[jenis])
    return {'pid': pid}


def mulai_install(slug, payload):
    oleh = _teks(payload, 'oleh', True)
    p = baca_json(folder(slug) / 'proyek.json', {})
    if not p.get('estimasi_kunci'):
        raise ValueError('estimasi_belum_dikunci')
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
            f['review'] = {'oleh': oleh, 'waktu': sekarang(), 'catatan': catatan}
            return True
        return False
    if not ubah_fitur(slug, _):
        raise ValueError('fitur_tidak_ada')
    if keputusan != 'simpan':
        catat(slug, oleh, f'review {fid}: {"OK" if keputusan == "ok" else "revisi"}')
    return {'ok': True}


# --- Router untuk installer_status.py ------------------------------------------

AKSI_POST = {
    'simpan': simpan, 'identitas': ubah_identitas, 'kunci': kunci_estimasi, 'install': mulai_install, 'agen': aksi_agen,
    'ulangi': ulangi_fitur, 'review': review,
    'susun': lambda s, b: mulai_brief(s, b, 'susun'), 'estimasi': lambda s, b: mulai_brief(s, b, 'estimasi'),
    'diagram': lambda s, b: mulai_brief(s, b, 'diagram'),
}
KODE_GALAT = {'sedang_berjalan': 409, 'slug_dipakai': 409, 'folder_exists': 409, 'sudah_diinstall': 409,
              'sudah_dikunci': 409, 'db_root_missing': 503, 'no_port': 503, 'tidak_ada': 404}


def handle(metode, path, query, payload):
    """-> (kode_http, objek). path diawali /api/laravel."""
    bagian = [x for x in path[len('/api/laravel'):].split('/') if x]
    try:
        if metode == 'GET':
            if not bagian:
                return 200, {'proyek': daftar(), 'port_berikut': port_berikut(), 'prasyarat': prasyarat(),
                             'id_berikut': id_berikut(), 'tim': tim_crm()}
            if bagian[0] == 'p' and len(bagian) == 2 and ID_RE.match(bagian[1]):
                q = parse_qs(query)
                if 'log' in q:
                    jenis = q['log'][0]
                    if jenis not in ('susun', 'diagram', 'estimasi', 'install', 'agen'):
                        raise ValueError('invalid_log')
                    return 200, {'log': log(bagian[1], jenis), 'job': pekerjaan(bagian[1])}
                d = detail(bagian[1])
                return (200, d) if d else (404, {'error': 'tidak_ada'})
            if bagian == ['onprogress']:
                return 200, {'hasil': cari_onprogress((parse_qs(query).get('q') or [''])[0])}
            return 404, {'error': 'tidak_ada'}
        if bagian == ['p']:
            return 200, buat(payload)
        if len(bagian) == 3 and bagian[0] == 'p' and ID_RE.match(bagian[1]) and bagian[2] in AKSI_POST:
            if not (folder(bagian[1]) / 'proyek.json').is_file():
                return 404, {'error': 'tidak_ada'}
            return 200, AKSI_POST[bagian[2]](bagian[1], payload)
        return 404, {'error': 'tidak_ada'}
    except ValueError as e:
        kode = str(e)
        return KODE_GALAT.get(kode, 400), {'error': kode}
