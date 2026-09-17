"""Bersihkan HTML konten AI sebelum dipasang di situs klien.

AI menulis gambar dengan alamat karangan (/wp-content/uploads/...jpg yang 404),
elemen "placeholder", form HTML tanpa pemroses, dan iframe peta palsu — semuanya
tampil rusak di situs klien (deliciasnacks-drinks.com, 2026-09-11). Foto, galeri,
peta, dan tombol WhatsApp dipasang terpisah oleh scripts/site-finish dari data
klien yang nyata.
"""
import html
import re
from html.parser import HTMLParser

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
DROP = {'img', 'picture', 'figure', 'iframe', 'form', 'input', 'textarea', 'select', 'option', 'button',
        'script', 'style', 'video', 'audio', 'source', 'svg', 'canvas', 'noscript', 'object', 'embed', 'map'}
PLACEHOLDER = re.compile(r'placeholder|lorem ipsum|\[\s*(gambar|foto|image|img|peta|map|logo|video)[^\]]*\]', re.I)
# Blok teks yang dibuang utuh kalau isinya menyebut placeholder.
TEXT_BLOCKS = {'p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'figcaption', 'small', 'em',
               'strong', 'blockquote', 'a', 'caption', 'label'}
KEEP_EMPTY = {'br', 'hr'}


class _Node:
    __slots__ = ('tag', 'attrs', 'children', 'parent')

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.children, self.parent = tag, attrs, [], parent


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node(None, [], None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs, self.cur)
        self.cur.children.append(node)
        if tag not in VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(_Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.cur = node.parent

    def handle_data(self, data):
        self.cur.children.append(data)

    def handle_comment(self, data):
        self.cur.children.append(('comment', data))


def _has_text(node):
    for child in node.children:
        if isinstance(child, str):
            if child.strip():
                return True
        elif isinstance(child, _Node) and (child.tag in KEEP_EMPTY or _has_text(child)):
            return True
    return False


def _clean(node):
    kept = []
    for child in node.children:
        if isinstance(child, str):
            if PLACEHOLDER.search(child):
                if node.tag in TEXT_BLOCKS:
                    return None
                continue
            kept.append(child)
        elif isinstance(child, tuple):
            kept.append(child)
        else:
            if child.tag in DROP or any(v and PLACEHOLDER.search(v) for _, v in child.attrs):
                continue
            cleaned = _clean(child)
            if cleaned is None or (cleaned.tag not in KEEP_EMPTY and not _has_text(cleaned)):
                continue
            kept.append(cleaned)
    node.children = kept
    return node


def _render(node):
    out = []
    for child in node.children:
        if isinstance(child, str):
            out.append(html.escape(child, quote=False))
        elif isinstance(child, tuple):
            out.append(f'<!--{child[1]}-->')
        else:
            attrs = ''.join(
                f' {k}="{html.escape(v, quote=True)}"' if v is not None else f' {k}'
                for k, v in child.attrs
                # Latar bergambar dengan alamat karangan juga tampil rusak.
                if not (k == 'style' and v and 'url(' in v.lower()))
            if child.tag in VOID:
                out.append(f'<{child.tag}{attrs}>')
            else:
                out.append(f'<{child.tag}{attrs}>{_render(child)}</{child.tag}>')
    return ''.join(out)


def clean_html(content):
    builder = _Builder()
    builder.feed(str(content or ''))
    builder.close()
    text = _render(_clean(builder.root))
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def has_placeholder(content):
    return bool(PLACEHOLDER.search(re.sub(r'<[^>]+>', ' ', str(content or ''))))


# ---------------------------------------------------------------------------
# Kalimat yang tidak boleh terbit walau HTML-nya bersih.
#
# jasakontraktorindo.com (2026-09-17): halaman Tentang Kami terbit dengan
# "Informasi sejarah perusahaan, visi, misi, nilai, dan susunan tim belum tersedia
# dalam data perusahaan." — catatan AI untuk penulis, bukan isi untuk pengunjung.
# Klaim yang sering dikarang untuk jasa (ISO, garansi, gratis, jumlah proyek,
# "berpengalaman 10 tahun") hanya boleh terbit kalau ada di data klien.
PENOLAKAN = re.compile(
    r'(belum|tidak)\s+(tersedia|tercantum|disebutkan|dicantumkan|diberikan|ada)\s+(dalam|di|pada)\s+'
    r'(data|informasi|dokumen|form)'
    r'|data\s+(klien|perusahaan|yang\s+diberikan)\s+(belum|tidak)'
    r'|informasi\s+(lebih\s+lanjut\s+)?(mengenai|tentang)\s+[^.]{0,80}\s+belum\s+tersedia'
    r'|(sebagai|selaku)\s+(model\s+)?AI\b|maaf,?\s+saya\s+tidak', re.I)
KLAIM = [
    ('sertifikasi', re.compile(r'\b(bersertifika\w*|tersertifikasi|terakreditasi|berstandar)\s+(resmi\s+)?(ISO|SNI|internasional)\b'
                               r'|\bsertifikasi\s+ISO\b', re.I)),
    ('garansi', re.compile(r'\bgaransi\s+(hingga\s+|selama\s+)?\d+|\bbergaransi\b', re.I)),
    ('gratis', re.compile(r'\b(konsultasi|survei|survey|desain|ongkir|ongkos\s+kirim|pemasangan)\s+gratis\b'
                          r'|\bgratis\s+(konsultasi|survei|survey|desain|ongkir)\b|\btanpa\s+biaya\s+(konsultasi|survei)\b', re.I)),
    ('angka_pengalaman', re.compile(r'\b(lebih\s+dari\s+|selama\s+)\d+\+?\s+tahun\b|\bberpengalaman\s+(lebih\s+dari\s+)?\d+\s+tahun', re.I)),
    ('angka_proyek', re.compile(r'\b(lebih\s+dari\s+|ribuan\s+|ratusan\s+)?\d[\d.]*\+?\s+(proyek|project|klien|pelanggan)\s+'
                                r'(telah\s+|sudah\s+)?(selesai|diselesaikan|terlayani|dilayani|puas)', re.I)),
    ('peringkat', re.compile(r'\b(nomor|no\.?)\s*(1|satu)\s+(di|se)\b|\bterbaik\s+(di|se)\s*indonesia\b', re.I)),
]


def _kalimat(teks):
    return [k for k in re.split(r'(?<=[.!?])\s+', teks) if k.strip()]


def buang_kalimat_meragukan(content, data_klien=None):
    """Buang kalimat penolakan/catatan AI dan klaim yang tidak ada di data klien.

    data_klien=None: hanya kalimat penolakan (data klien lengkap tidak tersedia,
    mis. artikel pengetahuan umum atau konten tersimpan yang dipakai ulang).

    Mengembalikan (html, daftar_alasan). Butir <li>/judul yang kena dibuang utuh;
    paragraf dibuang per kalimat, dan paragrafnya ikut hilang kalau jadi kosong."""
    data = str(data_klien or '')
    alasan = []

    def cek(teks):
        polos = html.unescape(re.sub(r'<[^>]+>', ' ', teks))
        if PENOLAKAN.search(polos):
            return 'penolakan'
        if data_klien is None:
            return ''
        for nama, pola in KLAIM:
            if pola.search(polos) and not pola.search(data):
                return 'klaim_' + nama
        return ''

    def blok(m):
        tag, isi = m.group(1).lower(), m.group(3)
        if tag in ('li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            sebab = cek(isi)
            if sebab:
                alasan.append(sebab)
                return ''
            return m.group(0)
        sisa = []
        for k in _kalimat(isi):
            sebab = cek(k)
            if sebab:
                alasan.append(sebab)
            else:
                sisa.append(k)
        if not sisa:
            return ''
        return f'<{m.group(1)}{m.group(2) or ""}>' + ' '.join(sisa) + f'</{m.group(1)}>'

    hasil = re.sub(r'<(p|li|h[1-6])(\s[^>]*)?>(.*?)</\1>', blok, str(content or ''),
                   flags=re.I | re.S)
    # Daftar yang semua butirnya terbuang.
    hasil = re.sub(r'<(ul|ol)(\s[^>]*)?>\s*</\1>', '', hasil, flags=re.I)
    return hasil, alasan
