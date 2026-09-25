"""Baca 'FORM ISIAN WEBSITE' yang dikirim klien di folder On Progress.

Stdlib saja — tidak butuh antiword/catdoc/LibreOffice (tidak tersedia di
AlmaLinux 9); PDF lewat pdftotext (poppler-utils). Format dideteksi lewat magic
bytes, bukan ekstensi, karena sebagian file .doc di Drive sebenarnya zip dan
sebaliknya: .docx, .doc (OLE), .odt, PDF berteks.

fields = "Label: isi" (parse_fields) + isian di bawah judul bagian template
(parse_sections, audit 2026-09-24) yang hanya mengisi label yang belum ada.
"""
import hashlib
import html
import json
import re
import subprocess
import zipfile
from pathlib import Path

MARKERS = ('domain', 'nama', 'slogan', 'menu', 'telp', 'email', 'form', 'alamat', 'produk')
NOISE = re.compile(
    r'^(Root Entry|SummaryInformation|DocumentSummaryInformation|WordDocument|'
    r'Normal(\.dotm?)?|WpsCustomData|KSOProductBuildVer|\d?Table|Data|CompObj|'
    r'ObjectPool|Microsoft.*|MSWordDoc|Word\.Document.*|Times New Roman|Calibri|'
    r'Arial|Symbol|Cambria|WPS Office.*|Font Paragraf Default|Tabel Normal|'
    r'Tidak Ada Daftar|Teks Balon( KAR)?|Hyperlink|Sebutan Yang Belum Terselesaikan|'
    # ID heksa sisa .doc biner; wajib memuat huruf A-F supaya nomor telepon polos
    # (paragraf "082137751984" di company profile) tidak ikut terbuang.
    r'(?=[0-9-]*[A-F])[0-9A-F-]{8,}.*)$', re.I)
# Nilai yang dibiarkan kosong oleh klien ditulis sebagai deretan titik.
BLANK = re.compile(r'^[.\s_-]*$')
# Label milik teks panduan template, bukan isian klien.
SKIP_LABELS = {'misal', 'keterangan', 'catatan', 'contoh', 'http', 'https',
               'dapat di lihat di sini', 'judul email', 'note'}
# Sebagian klien menuliskan password di dalam form; jangan pernah teruskan —
# nilai ini ikut terkirim ke API AI eksternal oleh pemanggil modul ini.
# Tanpa \b di belakang "pass": form nyata menulis "Passwordnya: ..." dan lolos.
CRED_LABEL = re.compile(r'pass(word)?|\bsandi\b|user ?name|\buser\b|\blogin\b|\bakun\b|\bpin\b|token|api[ _-]?key', re.I)


def _runs(raw, step, decode):
    out, buf = [], []
    for i in range(0, len(raw) - step + 1, step):
        ch = decode(raw, i)
        if ch is not None and (ch.isprintable() or ch == '\t'):
            buf.append(ch)
        else:
            if len(buf) >= 4:
                out.append(''.join(buf))
            buf = []
    if len(buf) >= 4:
        out.append(''.join(buf))
    return out


def _utf16(raw):
    return _runs(raw, 2, lambda r, i: chr(r[i]) if r[i + 1] == 0 else None)


def _eightbit(raw):
    def dec(r, i):
        b = r[i]
        if 32 <= b < 127 or b == 9:
            return chr(b)
        if 160 <= b <= 255:
            return bytes([b]).decode('cp1252', 'ignore') or None
        return None
    return _runs(raw, 1, dec)


def _from_zip(path):
    with zipfile.ZipFile(path) as z:
        nama = z.namelist()
        if 'word/document.xml' in nama:
            xml = z.read('word/document.xml').decode('utf8', 'replace')
        elif 'content.xml' in nama:
            # .odt (LibreOffice/WPS): paragraf <text:p>/<text:h>, ganti baris <text:line-break/>.
            xml = z.read('content.xml').decode('utf8', 'replace')
            xml = re.sub(r'<text:line-break\s*/>|</text:(p|h)>', '\n', xml)
            xml = re.sub(r'<text:(tab|s)\b[^>]*/>', ' ', xml)
            return html.unescape(re.sub(r'<[^>]+>', '', xml)).split('\n')
        else:
            return []
    # Ganti baris di dalam paragraf (<w:br/>, Shift+Enter) juga pemisah: tanpa ini isian & panduan
    # template menempel ("azahralaundryexpress.comNama domain adalah ...", audit 2026-09-24).
    xml = re.sub(r'<w:(br|cr)\b[^>]*/>', '\n', xml)
    xml = re.sub(r'<w:tab\b[^>]*/>', ' ', xml)
    # Entitas XML (&amp; &quot;) dikembalikan: "Tours &amp; Travel" bukan nama klien.
    return html.unescape(re.sub(r'<[^>]+>', '', re.sub(r'</w:p>', '\n', xml))).split('\n')


def _clean(lines):
    out = []
    for ln in lines:
        ln = ' '.join(ln.split())
        if len(ln) >= 3 and not NOISE.match(ln):
            out.append(ln)
    return out


def _score(lines):
    blob = ' '.join(lines).lower()
    return (sum(m in blob for m in MARKERS), len(lines))


def extract_text(path):
    """Baris teks dari satu dokumen form. Kosong kalau formatnya tak didukung."""
    path = Path(path)
    try:
        head = path.open('rb').read(4)
        if head.startswith(b'PK'):
            return _clean(_from_zip(path))
        if head.startswith(b'%PDF'):
            # Form yang disimpan klien sebagai PDF (bukan hasil scan): teks lewat pdftotext (poppler).
            run = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True, timeout=120)
            return _clean(re.sub(r' {3,}', '  ', run.stdout).splitlines())
        if head.startswith(b'\xd0\xcf\x11\xe0'):
            raw = path.read_bytes()
            # Word menyimpan teks .doc sebagai UTF-16LE atau 8-bit terkompresi,
            # berbeda per file; ambil hasil yang paling berisi.
            wide, narrow = _clean(_utf16(raw)), _clean(_eightbit(raw))
            return wide if _score(wide) >= _score(narrow) else narrow
    except (OSError, zipfile.BadZipFile, ValueError, subprocess.SubprocessError):
        pass
    return []


# Isian di baris sesudah "Label:" yang kosong di barisnya: hanya yang jelas berupa email/URL/nomor.
_ISI_LANJUT = re.compile(r'^([^\s@]+@[^\s@]+\.\w+|https?://\S+|www\.\S+|\+?[\d][\d\s.()-]{7,})$', re.I)


def parse_fields(lines):
    """Ambil pasangan 'Label: nilai', buang yang dibiarkan kosong klien."""
    fields = {}
    lines = list(lines)
    for idx, ln in enumerate(lines):
        # Form Portal Berita menulis isian berbutir ("-nama media: Mulawarman TV"); tanpa ini
        # baris itu tidak terbaca dan nama situs jatuh ke biodata (mulawarmantv.com 2026-09-18).
        ln = re.sub(r'^\s*[-•*]+\s*(?=[A-Za-z])', '', ln)
        # "Kontak untuk diweb 0811..." tanpa titik dua / tanpa spasi di "di web"
        # (wisesayasatidar.com 2026-09-18) lolos dari pola label umum, sehingga widget
        # Hubungi Kami & tombol WhatsApp kosong. Disimpan dengan label baku.
        m = re.match(r'^\s*kontak\s+(?:utk|untuk)\s+di\s*web\b\s*:?\s*(.*)$', ln, re.I)
        if m:
            # Baris .doc bisa menempel ke teks panduan berikutnya ("0821...Pada gambar di atas, ...").
            value = re.split(r'\.{3,}|\*|Pada gambar di atas', m.group(1), flags=re.I)[0].strip()
            value = re.sub(r'\s*\((silahkan|wajib|untuk|jika)[^)]*\)\s*$', '', value, flags=re.I).strip()
            if value and not BLANK.match(value):
                fields.setdefault('Kontak untuk di web', value)
            continue
        m = re.match(r'^([A-Za-z][A-Za-z0-9 /_()-]{2,40}?)\s*:\s*(.*)$', ln)
        if not m:
            continue
        label, value = m.group(1).strip(), m.group(2).strip()
        if label.lower() in SKIP_LABELS or CRED_LABEL.search(label) or CRED_LABEL.search(value):
            continue
        # Daftar pilihan desain template ("Pilihan 7: www.toko8...") & contoh jawaban bukan isian klien.
        if re.match(r'^(pilihan\s*\d+|pilihannya\b.*|pilihan warna.*|contoh jawaban)$', label, re.I):
            continue
        # Label sampah hasil baca .doc biner (mis. "iY0", "FKb") tidak punya kata utuh / huruf hidup.
        if not re.search(r'[A-Za-z]{3}', label) or not re.search(r'[aiueo]', label, re.I) or not label.isascii():
            continue
        # Teks panduan template menempel di belakang jawaban klien, dipisah deretan titik, tanda
        # bintang, "(optional)" atau "Misal:" — di .docx tanpa spasi: "HijauMisal: warna dasar ... biru dan
        # hijau" terbaca biru+hijau (audit 2026-09-24).
        value = re.split(r'\.{3,}|\*|\(\s*(?:optional|wajib)\b|Misal\s*:', value, flags=re.I)[0].strip()
        if not value:
            # "Email:" lalu tautan mailto di baris berikutnya (.doc): ambil isian yang jelas email/URL/nomor.
            for lanjut in lines[idx + 1:idx + 4]:
                lanjut = ' '.join(str(lanjut).split())
                if re.match(r'^(HYPERLINK|mailto:)', lanjut, re.I):
                    continue
                if _ISI_LANJUT.match(lanjut):
                    value = lanjut
                break
        value = re.sub(r'\s*\((silahkan|wajib|untuk|jika)[^)]*\)\s*$', '', value, flags=re.I).strip()
        if value and not BLANK.match(value):
            fields.setdefault(label, value)
    return fields


# Judul bagian template FORM ISIAN yang isinya ditulis klien di baris BERIKUTNYA (bukan "Label: isi").
# Label hasil dipilih supaya cocok dengan pola pemakai yang sudah ada (velocity-child-theme data_klien,
# installer_status judul situs, site-finish). Lima jenis template: paket biasa/F lama ("NAMA PERUSAHAAN
# ANDA"), paket G ("NAMA PERUSAHAAN/ INSTANSI" + "KONTAK / INSTANSI"), portal berita ("NAMA MEDIA"),
# compro PDF ("KONTAK YG DITAMPILKAN"), toko (FORM 1 "DATA WEBSITE" berformat "Label: isi").
_JUDUL_BAGIAN = (
    (r'NAMA DOMAIN', 'Domain'),
    # Template sekolah/kampus: "NAMA INSTANSI PENDIDIKAN", "KONTAK / INSTANSI PENDIDIKAN".
    (r'NAMA (PERUSAHAAN\s*/\s*INSTANSI|INSTANSI)( PENDIDIKAN)?', 'Nama Perusahaan / Instansi'),
    # Template paket biasa/F lama: nama di FORM 1 hanya CADANGAN bila "Nama Perusahaan:" biodata kosong
    # (label ini kalah urutan dari field biodata). Diukur 2026-09-24 pada 94 proyek: bila keduanya terisi,
    # biodata lebih sering tepat (edytravelservices, kamiteknik, pemdeslampok).
    (r'NAMA PERUSAHAAN( ANDA)?', 'Nama Perusahaan Anda'),
    (r'NAMA MEDIA', 'Nama Media'),
    (r'SLOGAN (PERUSAHAAN|MEDIA|INSTANSI)( ANDA|\s*/\s*INSTANSI)?( PENDIDIKAN)?', 'Slogan'),
    (r'LOGO (PERUSAHAAN|MEDIA|INSTANSI)( ANDA|\s*/\s*INSTANSI)?( PENDIDIKAN)?', None),
    (r'KONTAK\s*/\s*INSTANSI( PENDIDIKAN)?|KONTAK MEDIA|KONTAK YG DITAMPILKAN', 'Kontak untuk di web'),
    (r'SUSUNAN MENU ATAS', 'Susunan menu atas'),
    (r'ISI DARI SETIAP MENU ATAS', 'Isi menu atas'),
    (r'SISI KIRI', 'Sisi kiri'), (r'ISI DARI SISI KIRI', 'Isi sisi kiri'),
    (r'SISI KANAN', 'Sisi kanan'), (r'ISI DARI SISI KANAN', 'Isi sisi kanan'),
    (r'TAMBAHAN DATA|DATA TAMBAHAN', 'Data tambahan'),
    (r'PENJELASAN SINGKAT USAHA ANDA', 'Penjelasan usaha'),
    (r'LAYANAN\s*/\s*PRODUK', 'Layanan / produk'),
    (r'CUSTOMER\s*/\s*KLIEN', 'Customer / klien'),
    (r'FOTO PERUSAHAAN\s*/\s*TIM', None),
    (r'DESIGN YANG DIPILIH|TEMPLATE YANG DIPILIH', 'Desain yang dipilih'),
    (r'APAKAH ADA WEBSITE YANG INGIN DICONTOH[^:]*', 'Website referensi'),
    (r'APAKAH ANDA SUDAH MEMPUNYAI KONSEP DESAIN SENDIRI[^:]*', 'Konsep desain sendiri'),
    (r'WARNA TEMA WEB( YANG ANDA PILIH)?', 'Warna tema web'),
    (r'SAMPEL WARNA TEMA WEB', None),
    (r'PESAN TAMBAHAN DARI ANDA', None),
)
# Tanpa re.I: judul template selalu huruf besar; "Nama Perusahaan: ..." di BIODATA (FORM 2) milik parse_fields.
_JUDUL_RE = [(re.compile(rf'^\s*(?:{p})\s*(?P<titik>:)?\s*(?P<isi>.*)$'), label) for p, label in _JUDUL_BAGIAN]
# Baris pemisah bagian template lain (akhir isian).
_BATAS = re.compile(r'^\s*(FORM\s*\d|BIO\s*A?DATA|SYARAT DAN KETENTUAN|ISIAN DATA|DESAIN WEBSITE|ILUSTRASI|'
                    r'SUSUNAN TATA LETAK|APAKAH DESAIN WEBNYA|PILIHANNYA BERIKUT|Paket Website Yang Anda Pilih|'
                    r'kontak\s+(utk|untuk)\s+di\s*web)\b', re.I)
# Kalimat panduan template yang tercetak di bawah judul (bukan isian klien).
_PANDUAN = re.compile(
    r'^(silah?kan|contoh|misal|msial|jika bingung|untuk (isi|penjelasan|layanan)|pada gambar|nama domain adalah|'
    r'\*|alamat dan telp|bisa (berisi|data)|kontak berikut|penjelasan usaha anda|responsive desain|\(|hyperlink\b|'
    r'mailto:|-{5,}|dapat di ?lihat|tolong anda kirimkan company profile|ada \d+ pilihan|pilihan \d+|'
    r'\. jika tidak|jika tidak jawab|jawablah|.*alamatwebcontoh)', re.I)
# Isian di baris berikut pada "Label:" yang dibiarkan kosong di barisnya (mis. "Email:" lalu tautan mailto).
_LABEL_BARIS = re.compile(r'^([A-Za-z][A-Za-z0-9 /_()-]{2,40}?)\s*:\s*$')


def _isi_bagian(baris):
    """Isian klien di bawah satu judul: buang titik-titik, panduan template, baris HYPERLINK."""
    hasil = []
    for b in baris:
        # Kode field Word yang ikut terbaca di tengah baris: HYPERLINK "mailto:x@y" \t "_blank".
        b = re.sub(r'HYPERLINK\s+"[^"]*"(\s*\\[a-z]\s*"[^"]*")*', ' ', b)
        b = re.sub(r'^[.\s]{3,}', '', ' '.join(b.split())).strip()
        # Panduan yang menempel di belakang isian: deretan titik, "(optional)", "Misal:", "(Setelah web jadi".
        b = re.split(r'\.{5,}|\(\s*(?:optional|wajib|setelah|silah?kan)|Misal\s*:|Contoh\s*:|PILIHANNYA BERIKUT',
                     b, flags=re.I)[0].strip(' .')
        if not b or BLANK.match(b) or _PANDUAN.match(b) or not re.search(r'[A-Za-z0-9]{2}', b):
            continue
        # Nomor rekening/ID template yang tercetak di setiap form.
        if b in ('22226127635',):
            continue
        if b not in hasil:
            hasil.append(b)
    return '\n'.join(hasil)[:2000]


def parse_sections(lines):
    """Isian berbentuk judul bagian + isi di baris berikutnya (FORM 1 template resmi).

    parse_fields hanya mengenal "Label: isi", jadi "NAMA PERUSAHAAN ANDA\\nCahaya ratu petir"
    tidak pernah terbaca: judul situs cahayaratupetir.com jatuh ke tebakan nama domain
    ("Cahayaratupetir") dan tiap pemakai menambal dengan regex sendiri (audit 2026-09-24)."""
    hasil, i = {}, 0
    # Titik-titik isian kosong di depan judul (".......... PILIHANNYA BERIKUT INI:") diabaikan.
    lines = [re.sub(r'^[.\s]{3,}', '', ' '.join(str(l).split())) for l in lines]
    while i < len(lines):
        cocok = next(((m, label) for rx, label in _JUDUL_RE for m in [rx.match(lines[i])] if m), None)
        if not cocok:
            i += 1
            continue
        m, label = cocok
        j = i + 1
        while j < len(lines) and j - i <= 60 and not _BATAS.match(lines[j]) \
                and not any(rx.match(lines[j]) for rx, _ in _JUDUL_RE):
            j += 1
        # Isian sebaris ("TEMPLATE YANG DIPILIH: toko30...") berarti baris berikutnya panduan/daftar pilihan.
        # Tanpa titik dua, sisa huruf besar masih bagian judul varian lain ("... INSTANSI PENDIDIKAN").
        sebaris = '' if not m.group('titik') and m.group('isi').isupper() else _isi_bagian([m.group('isi')])
        # "Fitur mengikuti:" sebaris lalu tautannya di baris berikut: keduanya dipakai.
        isi = sebaris if sebaris and not sebaris.endswith(':') else \
            '\n'.join(x for x in (sebaris, _isi_bagian(lines[i + 1:j])) if x)
        # Kolom nama yang diisi alamat domain ("rigaswicaksono.com") bukan nama usaha.
        if label and label.startswith('Nama') and re.fullmatch(r'(https?://)?(www\.)?[\w-]+(\.[\w-]+)+/?', isi, re.I):
            isi = ''
        if label and isi:
            hasil.setdefault(label, isi)
        i = j
    return hasil


# Hasil baca agen Claude Code (scripts/baca-form-claude, keputusan user 2026-09-25): per folder proyek,
# berlaku selama md5 berkas form sama.
FORM_CLAUDE = Path('/var/lib/velocity/form-claude')


def berkas_form(folder):
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob('*') if p.is_file() and p.name.upper().startswith('FORM ISIAN'))


def md5_form(berkas):
    h = hashlib.md5()
    for p in berkas:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest() if berkas else ''


def hasil_claude(folder, berkas=None):
    """Data terstruktur hasil baca agen Claude untuk folder ini, atau None (belum dibaca / form berubah)."""
    folder = Path(folder)
    berkas = berkas_form(folder) if berkas is None else berkas
    try:
        simpan = json.loads((FORM_CLAUDE / f'{folder.name.lower()}.json').read_text())
    except (OSError, ValueError):
        return None
    data = simpan.get('data')
    return data if isinstance(data, dict) and berkas and simpan.get('md5') == md5_form(berkas) else None


def fields_dari_claude(d):
    """Data agen -> label field yang dipakai skrip lama (data_klien, judul situs manifest, site-finish,
    vd-store-settings, paket-g-konten, AI konten). Urutan penting: pemakai mengambil label cocok pertama."""
    def teks(x):
        return ' '.join(str(x or '').split()) if not isinstance(x, str) or '\n' not in x else str(x).strip()
    kontak = d.get('kontak_web') or {}

    def nomor(n):
        # "+62 857 9608 5227" / "0812-3456-789": tanpa spasi & strip supaya dikenali nomor_wa (allikan.com).
        return re.sub(r'(?<=\d)[\s.-]+(?=\d)', '', re.sub(r'^\+62[\s.-]+', '+62', str(n).strip()))
    # Alamat tanpa label: alamat_kontak_web mengambil baris beralamat apa adanya.
    baris_kontak = [f'WA: {nomor(n)}' for n in kontak.get('wa') or []] + [f'Telp: {nomor(n)}' for n in kontak.get('telepon') or []] \
        + [f'Email: {e}' for e in kontak.get('email') or []] + ([kontak['alamat']] if kontak.get('alamat') else []) \
        + ([f"Maps: {kontak['maps']}"] if kontak.get('maps') else []) \
        + [f"{x.get('jenis', '')}: {x.get('url', '')}" for x in kontak.get('sosmed') or [] if x.get('url')]
    bio = d.get('biodata') or {}
    toko = d.get('toko') or {}
    warna = d.get('warna') or {}
    ref = [r.get('url', '') + (f" ({r['catatan']})" if r.get('catatan') else '') for r in d.get('referensi_desain') or []]
    ref_isi = [r.get('url', '') + (f" ({r['catatan']})" if r.get('catatan') else '') for r in d.get('referensi_konten') or []]
    pasangan = [
        ('Nama Perusahaan / Instansi', d.get('nama_usaha')), ('Slogan', d.get('slogan')), ('Domain', d.get('domain')),
        ('Kontak untuk di web', '\n'.join(baris_kontak) or kontak.get('teks')),
        ('Paket Website Yang Anda Pilih', d.get('paket')),
        ('Susunan menu atas', ', '.join(d.get('menu_atas') or [])), ('Isi menu atas', d.get('isi_menu')),
        ('Desain yang dipilih', d.get('desain_dipilih')), ('Website referensi', '\n'.join(ref)),
        ('Referensi konten', '\n'.join(ref_isi)), ('Konsep desain sendiri', d.get('konsep_desain')),
        # Kata warna saja (pick_colors mencari kata warna); kalimat klien tetap di label kedua.
        ('Warna tema web', ', '.join(warna.get('warna') or [])), ('Keterangan warna', warna.get('teks')),
        ('Nama Toko', toko.get('nama_toko')), ('Bank pembayaran', toko.get('bank')),
        ('Asal pengiriman', toko.get('asal_pengiriman')), ('Ekspedisi pengiriman', toko.get('ekspedisi')),
        ('Kategori Produk', toko.get('kategori_produk')), ('Ongkir otomatis', toko.get('ongkir_otomatis')),
        ('Layanan / produk', d.get('layanan_produk')), ('Data tambahan', d.get('data_tambahan')),
        ('Pesan tambahan', d.get('pesan_tambahan')),
        # Biodata pemilik (administrasi) — label sama dengan form supaya penyaring data pemilik tetap bekerja.
        ('Nama anda', bio.get('nama')), ('Nama Perusahaan', bio.get('nama_perusahaan')),
        ('Alamat lengkap', bio.get('alamat')), ('Kota/ Kabupaten', bio.get('kota')), ('Propinsi', bio.get('provinsi')),
        ('Kodepos', bio.get('kodepos')), ('WhatsApp', nomor(bio.get('wa') or '')), ('Email', bio.get('email')),
    ]
    fields = {k: teks(v) for k, v in pasangan if teks(v)}
    if d.get('tolak_biodata_tampil'):
        fields['Biodata tidak boleh tampil'] = 'ya'
    # Rubrik portal berita: paket-g-konten mengenalinya dari isi "berisi berita ...".
    for r in d.get('rubrik') or []:
        nama = teks(r.get('nama'))
        if nama and nama.lower() not in {k.lower() for k in fields}:
            isi = teks(r.get('isi'))
            fields[nama.upper()] = isi if re.search(r'berisi\s+(berita|artikel|info)', isi, re.I) else f'berisi berita {isi or nama.lower()}'.strip()
    return fields


def read_client_form(folder):
    """Gabungan teks + field terurai dari semua form di folder project.

    Sumber field: hasil baca agen Claude (scripts/baca-form-claude) bila ada & form tidak berubah;
    tanpa itu pengurai pola (parse_fields + parse_sections). 'sumber' = 'claude' | 'pola'."""
    folder = Path(folder)
    docs = berkas_form(folder)
    text, fields, unread = [], {}, []
    for doc in docs:
        lines = extract_text(doc)
        if not lines:
            unread.append(doc.name)
            continue
        text.extend(lines)
        for k, v in parse_fields(lines).items():
            fields.setdefault(k, v)
        # Isian judul bagian hanya MENGISI yang kosong: "Label: isi" yang sudah terbaca tetap menang,
        # jadi situs yang datanya sudah benar tidak berubah.
        ada = {k.lower() for k in fields}
        for k, v in parse_sections(lines).items():
            if k.lower() not in ada:
                fields.setdefault(k, v)
    data = hasil_claude(folder, docs)
    if data is None:
        return {'text': '\n'.join(text), 'fields': fields, 'unreadable': unread, 'sumber': 'pola', 'data': None}
    # Agen yang menentukan isian klien; field pola hanya pelengkap label yang tidak dikenal skema
    # (mis. "Tiktok", "Maps"), tanpa rubrik/warna/kontak/nama versi pola yang bisa berupa contoh template.
    hasil = fields_dari_claude(data)
    kunci = {k.lower() for k in hasil}
    for k, v in fields.items():
        if k.lower() in kunci or re.search(r'berisi\s+(berita|artikel|info)', v, re.I) \
                or re.search(r'^(nama|warna|kontak|slogan|email|e-mail|alamat|kota|prop|kode ?pos|hp|telp|wa|whats)', k, re.I):
            continue
        hasil[k] = v
    return {'text': '\n'.join(text), 'fields': hasil, 'unreadable': unread, 'sumber': 'claude', 'data': data}


# Kalimat bawaan template di bagian PESAN TAMBAHAN (bukan tulisan klien).
_TEMPLATE_PESAN = re.compile(
    r'^(silah?kan anda sampaikan|silah?kan anda sampikan|setelah semua form|judul email|bantuanvelocity@|'
    r'hyperlink\b|mailto:|-{5,}|form\s*\d)', re.I)


def pesan_tambahan(text):
    """Tulisan klien di bagian "PESAN TAMBAHAN DARI ANDA" (FORM 5), tanpa kalimat template.

    Isi form adalah acuan pengerjaan (keputusan user 2026-09-24): permintaan di sini — mis.
    "halaman paket & hasil pekerjaan, data dan gambar bisa diambil dari totalantipetir.com"
    (cahayaratupetir.com) — wajib dikerjakan, jadi installer melaporkannya sampai ditandai selesai."""
    m = re.search(r'PESAN\s+TAMBAHAN[^\n]*\n(.*?)(?:\nSetelah semua form|\nJudul email|\Z)', text or '', re.S | re.I)
    if not m:
        return ''
    hasil = []
    for baris in m.group(1).splitlines():
        b = baris.strip()
        if not b or BLANK.match(b) or _TEMPLATE_PESAN.match(b):
            continue
        # Sisa .doc biner (karakter kendali/huruf acak) bukan tulisan klien.
        if sum(c.isalnum() or c.isspace() for c in b) < 0.8 * len(b):
            continue
        if b not in hasil:
            hasil.append(b)
    return '\n'.join(hasil).strip()


if __name__ == '__main__':
    import sys
    res = read_client_form(sys.argv[1])
    print(f'--- {len(res["fields"])} field, {len(res["text"].splitlines())} baris ---')
    for k, v in res['fields'].items():
        print(f'  {k}: {v[:70]}')
    if res['unreadable']:
        print('  tidak terbaca:', res['unreadable'])
