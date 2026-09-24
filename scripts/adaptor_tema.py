"""Adaptor beranda child theme klasik yang disusun AI dari file tema yang terpasang.

Dipakai scripts/theme-paket-biasa untuk tema yang belum punya adaptor buatan tangan (permintaan
user 2026-09-17, "beri AI akses ke tema biar dia kerjakan sesuai file tema yang ada").

Alur: file PHP child theme diambil dari server -> AI membaca kode beranda & pengaturan
Customizer/Kirki lalu menjawab adaptor JSON -> adaptor divalidasi terhadap kode (nama
pengaturan harus ada di tema, template harus ada, penanda harus dikenal) -> diterapkan ->
beranda diperiksa lewat pratinjau; gagal = pengaturan lama dikembalikan dan adaptor
ditandai gagal (dibuat ulang di run berikutnya dengan alasan kegagalannya).

Adaptor disimpan per tema + sidik file PHP di /var/lib/velocity/tampilan/_adaptor/, jadi
AI hanya dipanggil sekali per versi tema.

Bahasa nilai adaptor:
  "{{hero_judul}}"                      teks data klien (lihat PENANDA)
  "{{id:hero}}" / "{{url:hero}}"        gambar (hero, tentang, logo) sebagai ID lampiran / URL
  {"__untuk__": "layanan", "isi": {..}} daftar berulang per layanan ({{l.judul}}, {{id:layanan}}, ...)
  {"__untuk__": "keunggulan", "isi": {..}}  per keunggulan ({{k.judul}}, {{k.teks}})
  {"__untuk__": "galeri", "isi": {..}}  per foto klien ({{g.judul}}, {{id:galeri}}, {{url:galeri}})
  "{{id:foto1}}" .. "{{url:foto3}}"     foto pendamping (gambar kecil banner, dsb.)
  {"__json__": nilai}                   disimpan sebagai string JSON (repeater yang menyimpan teks JSON)
"""
import hashlib
import io
import json
import re
import os
import shlex
import subprocess
import tarfile
import urllib.request
from pathlib import Path

def situs_url(domain: str) -> str:
    """Alamat situs yang dikerjakan. Klien berhosting di luar dipasang di staging
    velocitydeveloper.co/<domain>; runner mengisinya lewat VELOCITY_LOKAL_URL supaya
    pemeriksaan tidak nyasar ke situs klien yang asli."""
    return (os.environ.get('VELOCITY_LOKAL_URL') or f'https://{domain}').rstrip('/')


FOLDER = Path('/var/lib/velocity/tampilan/_adaptor')
BUKAN_ANAK = ('velocity', 'velocity-fse')
PENANDA = {
    'nama': 'nama usaha/situs',
    'slogan': 'slogan pendek (bisa kosong)',
    'hero_judul': 'judul besar banner (<= 60 karakter)',
    'hero_teks': 'paragraf pembuka banner (<= 260 karakter)',
    'hero_teks_pendek': 'paragraf pembuka versi pendek (<= 130 karakter)',
    'profil': 'profil/tentang usaha (paragraf)',
    'tentang_judul': 'judul bagian tentang/sambutan',
    'layanan_judul': 'judul bagian layanan',
    'layanan_sub': 'subjudul bagian layanan',
    'keunggulan_judul': 'judul bagian keunggulan',
    'telp': 'nomor telepon tampil (bisa kosong)',
    'wa': 'nomor WhatsApp format 628xxx (bisa kosong)',
    'wa_tampil': 'nomor WhatsApp untuk ditampilkan',
    'wa_link': 'tautan https://wa.me/628xxx (bisa kosong)',
    'email': 'email publik (bisa kosong)',
    'alamat': 'alamat usaha (bisa kosong)',
    'link_kontak': 'tautan halaman Hubungi Kami',
    'link_layanan': 'tautan halaman Layanan',
    'link_berita': 'tautan halaman Berita/artikel',
}
PENANDA_ITEM = {
    'layanan': {'l.judul': 'judul layanan', 'l.teks': 'penjelasan layanan', 'l.teks_pendek': 'penjelasan <= 110 karakter',
                'l.rincian': 'rincian layanan dipisah koma', 'l.link': 'tautan ke bagian layanan itu'},
    'keunggulan': {'k.judul': 'judul keunggulan', 'k.teks': 'penjelasan keunggulan'},
    'galeri': {'g.judul': 'keterangan foto'},
}
GAMBAR = ('hero', 'tentang', 'logo', 'foto1', 'foto2', 'foto3')
# Gambar per butir daftar: {{id:layanan}} di dalam "__untuk__": "layanan", {{id:galeri}} di dalam "galeri".
GAMBAR_ITEM = ('layanan', 'galeri')
# Pengaturan seluruh situs, bukan isi beranda: tidak boleh diubah adaptor (AI sempat menulis
# custom_logo "" yang akan menghapus logo klien, juga warna utama & tipe container).
GLOBAL_RE = re.compile(r'^(custom_logo|site_icon|nav_menu_locations|sidebars_widgets|custom_css_post_id|'
                       r'background_.*|header_.*_color|.*_colou?r|justg_.*|container_.*|.*_container_type|'
                       r'font_.*|typography.*|.*_font(_.*)?)$', re.I)
POLA = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'}


# ---------- membaca tema dari server ----------

def baca_tema(ssh, docroot, user):
    """{'tema', 'versi', 'induk', 'depan_slug', 'file': {path: isi}} dari tema aktif situs."""
    meta_php = ('$t = wp_get_theme(); $d = (int) get_option("page_on_front");'
                ' echo wp_json_encode(["tema" => get_stylesheet(), "versi" => $t->get("Version"),'
                ' "induk" => get_template(), "dir" => get_stylesheet_directory(),'
                ' "depan_slug" => $d ? get_post_field("post_name", $d) : "",'
                ' "depan_template" => $d ? get_post_meta($d, "_wp_page_template", true) : ""], JSON_UNESCAPED_SLASHES);')
    wp = f'php -d memory_limit=512M /usr/local/bin/wp eval {shlex.quote(meta_php)}'
    perintah = (f'set -e; cd {shlex.quote(docroot)}; T=$(mktemp -d /tmp/velocity-baca-tema.XXXXXX); '
                f'if id {shlex.quote(user)} >/dev/null 2>&1; then runuser -u {shlex.quote(user)} -- {wp} 2>/dev/null > "$T/meta.json"; '
                f'else {wp} --allow-root 2>/dev/null > "$T/meta.json"; fi; '
                'S=$(sed -n \'s/.*"dir":"\\([^"]*\\)".*/\\1/p\' "$T/meta.json"); [ -d "$S" ]; '
                '(cd "$S" && find . -name "*.php" -not -path "./vendor/*" -not -path "./node_modules/*" -size -300k | head -150) > "$T/daftar"; '
                'tar czf - -C "$T" meta.json -C "$S" -T "$T/daftar"; rm -rf "$T"')
    hasil = subprocess.run(ssh + [perintah], capture_output=True, timeout=180)
    if hasil.returncode != 0:
        raise RuntimeError(f'baca_tema_gagal: {hasil.stderr.decode(errors="replace").strip()[:200]}')
    info = {'file': {}}
    with tarfile.open(fileobj=io.BytesIO(hasil.stdout), mode='r:gz') as tar:
        for anggota in tar.getmembers():
            if not anggota.isfile():
                continue
            isi = tar.extractfile(anggota).read().decode(errors='replace')
            if anggota.name == 'meta.json':
                info.update(json.loads(isi))
            else:
                info['file'][anggota.name.lstrip('./')] = isi
    return info


def sidik_tema(info):
    h = hashlib.md5()
    for nama in sorted(info['file']):
        h.update(nama.encode() + b'\0' + info['file'][nama].encode())
    return h.hexdigest()[:12]


def pengaturan_tema(info):
    """Nama theme_mod yang benar-benar dikenal tema: didaftarkan atau dibaca kodenya."""
    kunci = set()
    for isi in info['file'].values():
        kunci.update(re.findall(r"add_setting\(\s*['\"]([A-Za-z0-9_\-\[\]]+)['\"]", isi))
        kunci.update(re.findall(r"['\"]settings['\"]\s*=>\s*['\"]([A-Za-z0-9_\-]+)['\"]", isi))
        kunci.update(re.findall(r"(?:get_theme_mod|velocitytheme_option)\(\s*['\"]([A-Za-z0-9_\-]+)['\"]", isi))
    return kunci


def template_tema(info):
    return sorted(n for n, isi in info['file'].items()
                  if '/' not in n and re.search(r'Template Name\s*:', isi[:1500]))


def kode_untuk_ai(info, batas=90_000):
    """Kode yang relevan untuk beranda, yang paling penting lebih dulu, dibatasi panjangnya."""
    def nilai(nama, isi):
        skor = 0
        if nama in template_tema(info) or nama in ('front-page.php', 'home.php', 'index.php'):
            skor += 100
        skor += 30 * len(re.findall(r'add_setting|Kirki::add_field|customize_register', isi))
        skor += 5 * len(re.findall(r'get_theme_mod|velocitytheme_option', isi))
        return skor
    urutan = sorted(info['file'].items(), key=lambda x: -nilai(*x))
    bagian, total = [], 0
    for nama, isi in urutan:
        if nilai(nama, isi) <= 0:
            continue
        isi = re.sub(r'/\*\*?.*?\*/', '', isi, flags=re.S)  # komentar blok tidak perlu
        isi = re.sub(r'\n\s*\n+', '\n', isi)
        potong = f'===== {nama} =====\n{isi}\n'
        if total + len(potong) > batas:
            potong = potong[:max(0, batas - total)]
        bagian.append(potong)
        total += len(potong)
        if total >= batas:
            break
    return ''.join(bagian)


# ---------- penyimpanan adaptor ----------

def berkas_adaptor(info):
    return FOLDER / f"{info['tema']}-{re.sub(r'[^0-9A-Za-z.]', '', str(info.get('versi') or '0'))}-{sidik_tema(info)}.json"


def muat_adaptor(info):
    try:
        return json.loads(berkas_adaptor(info).read_text())
    except (OSError, ValueError):
        return None


def simpan_adaptor(info, catatan):
    FOLDER.mkdir(parents=True, exist_ok=True)
    berkas_adaptor(info).write_text(json.dumps(catatan, indent=1, ensure_ascii=False))


# ---------- AI ----------

def minta_ai(gen, model, info, gagal_sebelumnya=''):
    templates = template_tema(info)
    daftar = sorted(pengaturan_tema(info))
    penanda = '\n'.join(f'  {{{{{k}}}}}  {v}' for k, v in PENANDA.items())
    item = '\n'.join(f'  dalam "__untuk__": "{j}": ' + ', '.join(f'{{{{{k}}}}} ({v})' for k, v in d.items())
                     + (f', {{{{id:{j}}}}} / {{{{url:{j}}}}} (gambar butir itu)' if j in GAMBAR_ITEM else '')
                     for j, d in PENANDA_ITEM.items())
    sistem = ('You are a senior WordPress theme developer. You read classic child theme PHP code and map a '
              'company\'s content onto the theme\'s homepage settings. Output ONLY one valid JSON object.')
    permintaan = f"""Tema WordPress aktif: {info['tema']} versi {info.get('versi')} (induk: {info.get('induk')}).
Halaman depan situs: slug "{info.get('depan_slug')}", template sekarang "{info.get('depan_template') or 'default'}".
File yang punya "Template Name": {templates or 'tidak ada'}.
Nama pengaturan (theme_mod) yang dikenal kode tema: {daftar}

TUGAS: baca kode tema di bawah, pahami bagaimana BERANDA-nya dirender (template halaman, front-page.php/home.php,
pengaturan Customizer/Kirki yang dibaca, format nilainya: teks, HTML, ID lampiran, URL, array repeater, string JSON),
lalu susun adaptor supaya beranda tampil lengkap berisi data usaha klien.

Penanda data yang tersedia:
{penanda}
{item}
  gambar: {{{{id:hero}}}} {{{{url:hero}}}} {{{{id:tentang}}}} {{{{url:tentang}}}} {{{{id:logo}}}} {{{{url:logo}}}}
          {{{{id:foto1}}}} {{{{id:foto2}}}} {{{{id:foto3}}}} (dan versi url:) foto pendamping, SELALU tersedia
Nilai boleh gabungan teks & penanda, mis. "<p>{{{{profil}}}}</p>". Daftar berulang:
  {{"__untuk__": "layanan", "isi": {{"<nama field repeater>": "{{{{l.judul}}}}", ...}}}}
Kalau tema menyimpan repeater sebagai TEKS JSON, bungkus: {{"__json__": <nilai>}}.

ATURAN:
- "mods" HANYA berisi pengaturan ISI beranda yang benar-benar dibaca template dan ada di daftar nama di atas.
  JANGAN sertakan pengaturan seluruh situs: logo (custom_logo), warna, font, tipe container/layout, menu,
  widget, latar. Pengaturan header yang berisi data usaha (alamat, telepon, email, tagline) boleh.
- Pakai format yang diharapkan kode (lihat sanitize_callback & cara template membaca nilainya): gambar sebagai ID
  kalau kode memakai wp_get_attachment_*/absint, sebagai URL kalau langsung dipakai di src/url().
- Isi SEMUA bagian beranda yang punya data. Bagian yang tidak ada datanya (logo klien, testimoni, dsb.)
  kosongkan ("" atau []) supaya teks/gambar contoh bawaan tema tidak tampil.
- Galeri/portofolio foto di beranda SELALU diisi dengan {{"__untuk__": "galeri", ...}} (daftarnya boleh kosong
  saat dipasang; installer yang menentukan). Gambar pendamping/gambar kecil banner/slider tambahan diisi
  {{{{id:foto1}}}}..{{{{id:foto3}}}}, jangan dikosongkan.
- Nilai ditulis dengan set_theme_mod() LANGSUNG, TANPA sanitize_callback Customizer. Simpan dalam bentuk yang
  DIBACA template (hasil sesudah sanitize): repeater yang di-json_decode oleh sanitize tetap ditulis sebagai array,
  bukan {{"__json__"}}. Pakai {{"__json__"}} hanya kalau template sendiri yang melakukan json_decode atas nilainya.
- Gambar {{{{id:hero}}}}/{{{{url:hero}}}} SELALU tersedia (foto banner lebar) dan {{{{id:tentang}}}}/{{{{url:tentang}}}}
  juga; setiap layanan punya gambar {{{{id:layanan}}}}. Jangan kosongkan pengaturan gambar banner/slider utama.
- Tautan tombol ke {{{{link_kontak}}}} / {{{{link_layanan}}}}; tautan per layanan pakai {{{{l.link}}}}. Jangan mengarang data.
- "template": nama file template beranda dari daftar di atas yang harus dipasang di halaman depan, atau null
  kalau beranda tema tidak memakai template halaman.
- "bawaan": nilai default yang ditulis kode tema untuk tiap pengaturan di "mods" (dari 'default' add_setting,
  argumen kedua velocitytheme_option/get_theme_mod, atau fungsi default repeater). Dipakai untuk mengenali
  pengaturan yang belum disunting orang dan untuk memeriksa teks contoh tema tidak tampil lagi.
- "periksa": 1-3 teks bawaan tema yang PASTI tampil di beranda kalau pengaturan tidak terisi (mis. judul banner
  contoh). Boleh [].
{('PERCOBAAN SEBELUMNYA GAGAL: ' + gagal_sebelumnya + ' — perbaiki penyebabnya.') if gagal_sebelumnya else ''}

Bentuk jawaban:
{{"template": "page-home.php", "mods": {{}}, "bawaan": {{}}, "periksa": [], "catatan": "ringkas cara beranda dirender"}}

KODE TEMA:
{kode_untuk_ai(info)}"""
    for percobaan in range(2):
        jawab = gen.ai_call(sistem, permintaan, model, timeout=420, max_tokens=8000)
        if not jawab:
            continue
        try:
            awal, akhir = jawab.find('{'), jawab.rfind('}')
            adaptor = json.loads(jawab[awal:akhir + 1], strict=False)
        except ValueError:
            gen.log(f'Adaptor tema percobaan {percobaan + 1}: JSON rusak')
            continue
        if isinstance(adaptor, dict) and isinstance(adaptor.get('mods'), dict):
            buang = [k for k in adaptor['mods'] if GLOBAL_RE.match(k)]
            if buang:
                gen.log(f'Adaptor tema: pengaturan global dibuang {buang}')
            adaptor['mods'] = rapikan({k: v for k, v in adaptor['mods'].items() if k not in buang})
            if isinstance(adaptor.get('bawaan'), dict):
                adaptor['bawaan'] = {k: v for k, v in adaptor['bawaan'].items() if k not in buang}
        salah = validasi(adaptor, info)
        if not salah:
            return adaptor
        gen.log(f'Adaptor tema percobaan {percobaan + 1} ditolak: {salah[:6]} | mods: '
                f'{json.dumps(adaptor.get("mods"), ensure_ascii=False)[:700]}')
        permintaan += f'\n\nJAWABAN SEBELUMNYA DITOLAK: {salah[:10]}. Perbaiki.'
    return None


def _penanda_dalam(nilai, konteks):
    salah = []
    if isinstance(nilai, dict):
        if '__json__' in nilai:
            return _penanda_dalam(nilai['__json__'], konteks)
        if '__untuk__' in nilai:
            if nilai['__untuk__'] not in PENANDA_ITEM:
                return [f'__untuk__ tidak dikenal: {nilai["__untuk__"]}']
            return _penanda_dalam(nilai.get('isi'), nilai['__untuk__'])
        for v in nilai.values():
            salah += _penanda_dalam(v, konteks)
    elif isinstance(nilai, list):
        for v in nilai:
            salah += _penanda_dalam(v, konteks)
    elif isinstance(nilai, str):
        for p in POLA.findall(nilai):
            gambar = re.fullmatch(r'(id|url):([a-z]+[0-9]*)', p)
            if gambar:
                ok = gambar.group(2) in GAMBAR or (gambar.group(2) in GAMBAR_ITEM and konteks == gambar.group(2))
                if ok and gambar.group(0) != nilai.strip('{} '):
                    salah.append(f'penanda gambar harus berdiri sendiri: {p}')
                elif not ok:
                    salah.append(f'gambar tidak dikenal: {p}')
            elif p not in PENANDA and p not in PENANDA_ITEM.get(konteks, {}):
                salah.append(f'penanda tidak dikenal: {p}')
    return salah


def rapikan(nilai):
    """Bentuk perulangan yang lazim ditulis AI dijadikan bentuk baku:
    [{"__untuk__": ..}] -> {"__untuk__": ..};  [{"f": "{{l.judul}}"}] -> {"__untuk__": "layanan", "isi": {..}}."""
    if isinstance(nilai, list):
        if len(nilai) == 1 and isinstance(nilai[0], dict):
            satu = nilai[0]
            if '__untuk__' in satu:
                return rapikan(satu)
            teks = json.dumps(satu, ensure_ascii=False)
            jenis = next((j for j, d in PENANDA_ITEM.items()
                          if any('{{' + k in teks or '{{ ' + k in teks for k in d)
                          or (j in GAMBAR_ITEM and re.search(r'\{\{\s*(id|url):' + j + r'\b', teks))), None)
            if jenis:
                return {'__untuk__': jenis, 'isi': rapikan(satu)}
        return [rapikan(v) for v in nilai]
    if isinstance(nilai, dict):
        return {k: rapikan(v) for k, v in nilai.items()}
    return nilai


def validasi(adaptor, info):
    salah = []
    if not isinstance(adaptor, dict) or not isinstance(adaptor.get('mods'), dict) or not adaptor['mods']:
        return ['mods kosong atau bukan objek']
    kenal = pengaturan_tema(info)
    for k in adaptor['mods']:
        if k not in kenal:
            salah.append(f'pengaturan tidak ada di kode tema: {k}')
    tpl = adaptor.get('template')
    if tpl not in (None, '') and tpl not in template_tema(info):
        salah.append(f'template tidak ada: {tpl}')
    salah += _penanda_dalam(adaptor['mods'], '')
    if not any(POLA.search(json.dumps(v, ensure_ascii=False)) for v in adaptor['mods'].values()):
        salah.append('tidak ada pengaturan yang memakai data klien')
    return salah


# ---------- mengisi penanda ----------

def _teks(v):
    return re.sub(r'[<>]', '', str(v or ''))


def isi_nilai(nilai, data, item=None):
    """Ganti penanda teks; penanda gambar dibiarkan untuk diselesaikan di server."""
    if isinstance(nilai, dict):
        if '__json__' in nilai:
            return json.dumps(isi_nilai(nilai['__json__'], data, item), ensure_ascii=False)
        if '__untuk__' in nilai:
            return [isi_nilai(nilai.get('isi'), data, (nilai['__untuk__'], x)) for x in data['daftar'][nilai['__untuk__']]]
        return {k: isi_nilai(v, data, item) for k, v in nilai.items()}
    if isinstance(nilai, list):
        return [isi_nilai(v, data, item) for v in nilai]
    if not isinstance(nilai, str):
        return nilai

    def ganti(m):
        p = m.group(1).strip()
        if re.fullmatch(r'(id|url):(layanan|galeri)', p) and item and item[0] == p.split(':')[1]:
            return '{{%s:%s-%s}}' % (p.split(':')[0], item[0], item[1]['slug'])
        if re.fullmatch(r'(id|url):[a-z]+[0-9]*', p):
            return m.group(0)
        if item and '.' in p:
            return _teks(item[1].get(p.split('.', 1)[1], ''))
        return _teks(data['teks'].get(p, ''))
    return POLA.sub(ganti, nilai)


# ---------- pemeriksaan hasil ----------

def periksa_beranda(domain, slug, data, adaptor):
    """(lulus, alasan). Beranda dibuka lewat pratinjau (maintenance mode meloloskan is_preview).

    lulus None = TIDAK BISA DIPERIKSA (beranda tak terjangkau / masih halaman maintenance):
    bukan bukti adaptornya salah, jadi pemanggil tidak boleh mencabut hasilnya.
    cahayaratupetir.com 2026-09-22: sertifikat SSL domain belum terbit (masih milik domain
    lain di server) -> urlopen gagal verifikasi -> beranda yang sudah terisi dicabut, situs
    selesai sebagai halaman teks polos. Yang diperiksa di sini isi halaman, bukan sertifikat,
    jadi verifikasi SSL dimatikan."""
    import ssl
    url = (f'{situs_url(domain)}/{slug}/?preview=true' if slug
           else situs_url(domain) + '/')
    konteks = ssl.create_default_context()
    konteks.check_hostname = False
    konteks.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40, context=konteks) as r:
            halaman = r.read().decode(errors='replace')
    except Exception as e:
        return None, f'beranda_tidak_terbuka:{type(e).__name__}'
    if 'maintenance-shell' in halaman:
        return None, 'beranda_masih_halaman_maintenance'
    import html as html_mod
    polos = html_mod.unescape(re.sub(r'<[^>]+>', ' ', halaman))
    polos = re.sub(r'\s+', ' ', polos)
    alasan = []
    judul_layanan = [l['judul'] for l in data['daftar']['layanan']]
    pakai_layanan = '__untuk__": "layanan' in json.dumps(adaptor.get('mods'), ensure_ascii=False).replace("'", '"')
    if pakai_layanan and judul_layanan:
        tampil = [j for j in judul_layanan if j.lower() in polos.lower()]
        if len(tampil) < max(1, len(judul_layanan) // 2):
            alasan.append(f'layanan_tidak_tampil({len(tampil)}/{len(judul_layanan)})')
    for kunci in ('hero_judul', 'nama'):
        if kunci in json.dumps(adaptor.get('mods'), ensure_ascii=False):
            t = data['teks'].get(kunci, '')
            if t and t.lower()[:40] not in polos.lower():
                alasan.append(f'{kunci}_tidak_tampil')
            break
    milik_kita = {str(v).strip().lower() for v in data['teks'].values() if v}
    milik_kita |= {str(x.get('judul', '')).strip().lower() for d in data['daftar'].values() for x in d}
    for contoh in adaptor.get('periksa') or []:
        c = re.sub(r'\s+', ' ', html_mod.unescape(re.sub(r'<[^>]+>', ' ', str(contoh)))).strip()
        if len(c) >= 8 and c.lower() not in milik_kita and c.lower() in polos.lower():
            alasan.append(f'teks_contoh_tema_masih_tampil:{c[:40]}')
    return (not alasan), ','.join(alasan)
