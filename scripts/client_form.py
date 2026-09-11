"""Baca 'FORM ISIAN WEBSITE' yang dikirim klien di folder On Progress.

Stdlib saja — tidak butuh antiword/catdoc/LibreOffice (tidak tersedia di
AlmaLinux 9). Format dideteksi lewat magic bytes, bukan ekstensi, karena
sebagian file .doc di Drive sebenarnya zip dan sebaliknya.
"""
import re
import zipfile
from pathlib import Path

MARKERS = ('domain', 'nama', 'slogan', 'menu', 'telp', 'email', 'form', 'alamat', 'produk')
NOISE = re.compile(
    r'^(Root Entry|SummaryInformation|DocumentSummaryInformation|WordDocument|'
    r'Normal(\.dotm?)?|WpsCustomData|KSOProductBuildVer|\d?Table|Data|CompObj|'
    r'ObjectPool|Microsoft.*|MSWordDoc|Word\.Document.*|Times New Roman|Calibri|'
    r'Arial|Symbol|Cambria|WPS Office.*|Font Paragraf Default|Tabel Normal|'
    r'Tidak Ada Daftar|Teks Balon( KAR)?|Hyperlink|Sebutan Yang Belum Terselesaikan|'
    r'[0-9A-F-]{8,}.*)$', re.I)
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
        if 'word/document.xml' not in z.namelist():
            return []
        xml = z.read('word/document.xml').decode('utf8', 'replace')
    return re.sub(r'<[^>]+>', '', re.sub(r'</w:p>', '\n', xml)).split('\n')


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
        if head.startswith(b'\xd0\xcf\x11\xe0'):
            raw = path.read_bytes()
            # Word menyimpan teks .doc sebagai UTF-16LE atau 8-bit terkompresi,
            # berbeda per file; ambil hasil yang paling berisi.
            wide, narrow = _clean(_utf16(raw)), _clean(_eightbit(raw))
            return wide if _score(wide) >= _score(narrow) else narrow
    except (OSError, zipfile.BadZipFile, ValueError):
        pass
    return []


def parse_fields(lines):
    """Ambil pasangan 'Label: nilai', buang yang dibiarkan kosong klien."""
    fields = {}
    for ln in lines:
        m = re.match(r'^([A-Za-z][A-Za-z0-9 /_()-]{2,40}?)\s*:\s*(.*)$', ln)
        if not m:
            continue
        label, value = m.group(1).strip(), m.group(2).strip()
        if label.lower() in SKIP_LABELS or CRED_LABEL.search(label) or CRED_LABEL.search(value):
            continue
        # Label sampah hasil baca .doc biner (mis. "iY0") tidak punya kata utuh.
        if not re.search(r'[A-Za-z]{3}', label):
            continue
        # Teks panduan template menempel di belakang jawaban klien, dipisah
        # deretan titik atau tanda bintang.
        value = re.split(r'\.{3,}|\*', value)[0].strip()
        value = re.sub(r'\s*\((silahkan|wajib|untuk|jika)[^)]*\)\s*$', '', value, flags=re.I).strip()
        if value and not BLANK.match(value):
            fields.setdefault(label, value)
    return fields


def read_client_form(folder):
    """Gabungan teks + field terurai dari semua form di folder project."""
    folder = Path(folder)
    docs = sorted(p for p in folder.glob('*')
                  if p.is_file() and p.name.upper().startswith('FORM ISIAN'))
    text, fields, unread = [], {}, []
    for doc in docs:
        lines = extract_text(doc)
        if not lines:
            unread.append(doc.name)
            continue
        text.extend(lines)
        for k, v in parse_fields(lines).items():
            fields.setdefault(k, v)
    return {'text': '\n'.join(text), 'fields': fields, 'unreadable': unread}


if __name__ == '__main__':
    import sys
    res = read_client_form(sys.argv[1])
    print(f'--- {len(res["fields"])} field, {len(res["text"].splitlines())} baris ---')
    for k, v in res['fields'].items():
        print(f'  {k}: {v[:70]}')
    if res['unreadable']:
        print('  tidak terbaca:', res['unreadable'])
