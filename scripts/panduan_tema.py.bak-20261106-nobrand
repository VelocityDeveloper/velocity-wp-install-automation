"""Panduan isi data dari pembuat child theme (child-theme-data-setup.md di repo GitHub tema).

Permintaan user 2026-10-02 (velocity-perusahaan1): untuk child theme Paket F, langkah tampilan
(scripts/theme-paket-biasa) membaca `child-theme-data-setup.md` di repo VelocityDeveloper/<tema>
bila ada, dan menerapkannya pada instalasi berikutnya. Situs yang sudah ter-deploy tidak disentuh.

Panduan ditulis bebas oleh pembuat tema, jadi AI menerjemahkannya sekali per versi berkas (sidik
sha GitHub) menjadi aturan berstruktur, lalu aturan divalidasi terhadap kode tema yang terpasang:

  sidebar     susunan widget Main Sidebar: [{nama, id_base, opsi_option, opsi}]  (null = tidak diatur)
  logo        ukuran render logo header {lebar, tinggi} + latar_putih bila tidak kontras
  galeri_min  jumlah foto galeri beranda minimal
  layanan_min jumlah layanan minimal
  adaptor     petunjuk tambahan untuk adaptor beranda (bagian Customize) saat adaptor dibuat
  manual      poin panduan yang tidak bisa diterapkan otomatis (dilaporkan di log)

Bagian lain panduan (Home Template, Site Identity, Header Image, Gallery Post Type + VD Gallery)
sudah dikerjakan langkah installer yang ada; aturan di sini hanya menambah yang belum.
"""
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

BERKAS = 'child-theme-data-setup.md'
ORG = 'VelocityDeveloper'
FOLDER = Path('/var/lib/velocity/tampilan/_panduan')
TOKEN_FILE = Path(os.environ.get('WP_INSTALL_GITHUB_TOKEN_FILE') or '/etc/velocity/secrets/github_token')
UA = {'User-Agent': 'velocity-installer/1.0'}
SLUG_RE = re.compile(r'^[a-z0-9-]+$')
# Widget bawaan WordPress yang boleh disebut panduan walau tidak ada di kode tema.
WIDGET_INTI = ('recent-posts', 'search', 'categories', 'archives', 'text', 'custom_html', 'media_image', 'nav_menu')


def _token():
    try:
        return TOKEN_FILE.read_text().strip()
    except OSError:
        return ''


def ambil(tema):
    """(teks, sha) panduan di repo tema; ('', '') kalau berkasnya tidak ada.

    Galat jaringan memakai salinan terakhir di tembolok, supaya GitHub yang sedang lambat tidak
    membuat instalasi berjalan tanpa panduan yang sebenarnya ada."""
    if not SLUG_RE.match(tema or ''):
        return '', ''
    simpan = FOLDER / f'{tema}.md'
    url = f'https://api.github.com/repos/{ORG}/{tema}/contents/{BERKAS}'
    req = urllib.request.Request(url, headers=dict(UA, Accept='application/vnd.github+json'))
    token = _token()
    if token:
        req.add_unredirected_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return '', ''
        data = None
    except (urllib.error.URLError, OSError, ValueError):
        data = None
    if data is None:
        try:
            catatan = json.loads((FOLDER / f'{tema}.json').read_text())
            return simpan.read_text(), catatan['sha']
        except (OSError, ValueError, KeyError):
            return '', ''
    teks = base64.b64decode(data.get('content') or '').decode('utf-8', 'replace')
    sha = str(data.get('sha') or hashlib.sha1(teks.encode()).hexdigest())
    FOLDER.mkdir(parents=True, exist_ok=True)
    simpan.write_text(teks)
    (FOLDER / f'{tema}.json').write_text(json.dumps({'sha': sha}))
    return teks, sha


def kode_widget(info, batas=30_000):
    """Kode tema yang mendaftarkan widget & sidebar (untuk AI menyusun opsi widget)."""
    bagian, total = [], 0
    for nama, isi in sorted(info['file'].items()):
        if not re.search(r'register_widget|wp_register_sidebar_widget|register_sidebar|extends\s+WP_Widget', isi):
            continue
        potong = f'===== {nama} =====\n{isi}\n'[:max(0, batas - total)]
        bagian.append(potong)
        total += len(potong)
        if total >= batas:
            break
    return ''.join(bagian)


def validasi(aturan, info):
    """Buang bagian aturan yang tidak cocok dengan kode tema. -> (aturan bersih, daftar alasan)."""
    alasan = []
    kode = '\n'.join(info['file'].values())
    bersih = {'sidebar': None, 'logo': None, 'galeri_min': None, 'layanan_min': None,
              'adaptor': str(aturan.get('adaptor') or '').strip()[:2000],
              'manual': [str(x)[:200] for x in (aturan.get('manual') or []) if str(x).strip()][:10]}
    sb = aturan.get('sidebar')
    if isinstance(sb, list):
        daftar = []
        for it in sb[:6]:
            if not isinstance(it, dict):
                continue
            base = str(it.get('id_base') or '')
            opsi_nama = str(it.get('opsi_option') or '')
            if not re.match(r'^[a-z0-9_-]+$', base) or (base not in WIDGET_INTI and f"'{base}'" not in kode
                                                         and f'"{base}"' not in kode):
                alasan.append(f'widget_tidak_ada_di_tema:{base or "-"}')
                continue
            if opsi_nama and opsi_nama != f'widget_{base}' and not re.search(r"['\"]" + re.escape(opsi_nama) + r"['\"]", kode):
                alasan.append(f'opsi_widget_tidak_ada_di_tema:{opsi_nama}')
                continue
            opsi = it.get('opsi') if isinstance(it.get('opsi'), dict) else {}
            opsi = {str(k): v for k, v in opsi.items() if isinstance(v, (str, int, float, bool))}
            daftar.append({'nama': str(it.get('nama') or base)[:80], 'id_base': base,
                           'opsi_option': opsi_nama, 'opsi': opsi})
        bersih['sidebar'] = daftar or None
    lg = aturan.get('logo')
    if isinstance(lg, dict):
        try:
            lebar, tinggi = int(lg.get('lebar') or 0), int(lg.get('tinggi') or 0)
        except (TypeError, ValueError):
            lebar = tinggi = 0
        if 60 <= lebar <= 600 and 20 <= tinggi <= 300:
            bersih['logo'] = {'lebar': lebar, 'tinggi': tinggi, 'latar_putih': bool(lg.get('latar_putih'))}
        elif lebar or tinggi:
            alasan.append(f'ukuran_logo_tidak_wajar:{lebar}x{tinggi}')
    for kunci in ('galeri_min', 'layanan_min'):
        try:
            n = int(aturan.get(kunci) or 0)
        except (TypeError, ValueError):
            n = 0
        if 1 <= n <= 12:
            bersih[kunci] = n
    return bersih, alasan


def minta_ai(gen, model, tema, teks, info):
    sistem = ('You are a senior WordPress theme developer. You turn a theme author\'s data setup guide into '
              'machine-readable rules for an installer. Output ONLY one valid JSON object.')
    permintaan = f"""Tema WordPress aktif: {tema} versi {info.get('versi')}.
Pembuat tema menulis panduan pengisian data situs ({BERKAS}) di bawah. Installer sudah otomatis mengerjakan:
template beranda + pengaturan Customizer beranda (adaptor terpisah), Site Identity (logo, judul, tagline, ikon),
Header Image, Gallery Post Type + shortcode VD Gallery, dan widget footer.

TUGAS: ubah panduan jadi aturan berikut. Isi null untuk bagian yang TIDAK disebut panduan — jangan menebak.
- "sidebar": widget yang diminta panduan untuk sidebar utama (Main Sidebar), urut, atau null kalau panduan tidak
  mengatur sidebar. Tiap butir: "nama" (nama widget di panduan), "id_base" (id dasar widget dari KODE di bawah:
  argumen id_base / awalan id wp_register_sidebar_widget, atau id_base WP_Widget; widget inti WordPress pakai
  {list(WIDGET_INTI)}), "opsi_option" (nama option tempat widget itu menyimpan pengaturannya: untuk WP_Widget
  "widget_<id_base>", untuk widget lama yang memakai get_option('...') tulis nama option itu), "opsi" (objek
  pengaturan instance dengan NAMA FIELD dari kode dan nilai bawaan yang masuk akal dari kode form widget,
  mis. judul "Artikel Terbaru"; semua field yang dibaca fungsi tampil widget harus ada).
- "logo": {{"lebar": px, "tinggi": px, "latar_putih": true/false}} kalau panduan menyebut ukuran logo header /
  latar putih bila tidak kontras, selain itu null.
- "galeri_min": jumlah gambar galeri beranda minimal yang disebut panduan, atau null.
- "layanan_min": jumlah layanan yang harus diisi menurut panduan, atau null.
- "adaptor": ringkasan bahasa Indonesia instruksi panduan tentang pengaturan Customizer beranda (bagian mana diisi
  apa, sumber data, jumlah) untuk pembuat adaptor; "" kalau tidak ada.
- "manual": poin panduan yang tidak tercakup aturan di atas maupun yang sudah otomatis (kalimat pendek), boleh [].

PANDUAN:
{teks[:12000]}

KODE WIDGET TEMA:
{kode_widget(info) or '(tidak ada)'}"""
    for _ in range(2):
        jawab = gen.ai_call(sistem, permintaan, model, timeout=300, max_tokens=4000)
        if not jawab:
            continue
        try:
            awal, akhir = jawab.find('{'), jawab.rfind('}')
            hasil = json.loads(jawab[awal:akhir + 1], strict=False)
        except ValueError:
            gen.log('Panduan tema: JSON rusak')
            continue
        if isinstance(hasil, dict):
            return hasil
    return None


def aturan(gen, model, tema, teks, sha, info):
    """Aturan tervalidasi untuk panduan versi ini (tembolok per tema + sha). -> (aturan|None, alasan)."""
    simpan = FOLDER / f"{tema}-{sha[:12]}-aturan.json"
    try:
        mentah = json.loads(simpan.read_text())
    except (OSError, ValueError):
        mentah = None
    if mentah is None:
        if not model:
            return None, ['tanpa_model']
        mentah = minta_ai(gen, model, tema, teks, info)
        if mentah is None:
            return None, ['ai_gagal']
        FOLDER.mkdir(parents=True, exist_ok=True)
        simpan.write_text(json.dumps(mentah, indent=1, ensure_ascii=False))
    return validasi(mentah, info)
