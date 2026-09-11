"""Kumpulkan teks data klien dari folder project sebagai bahan konten AI.

Sumber: seluruh isi FORM ISIAN WEBSITE (bukan hanya pasangan "Label: nilai") dan
dokumen lain kiriman klien — company profile PDF/DOCX, konsep website, susunan
menu, catatan .txt. Foto, video, dan file desain dilewati.

Teks ini dikirim ke API AI eksternal, jadi baris kredensial selalu dibuang dan
bagian data pribadi pemilik di form ditandai supaya tidak ditampilkan di situs.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from client_form import extract_text

OCR_PAGES = 6

DOC_EXTS = {'.pdf', '.docx', '.doc', '.txt'}
# Dokumen yang biasanya paling kaya isi didahulukan saat anggaran karakter habis.
PRIORITY = re.compile(r'profil|profile|compro|konsep|isian|menu|katalog', re.I)
TOTAL_BUDGET = 16000
PER_DOC_BUDGET = 7000
# Sengaja tanpa \b di belakang "pass": form nyata menulis "Passwordnya: ...".
CRED = re.compile(r'pass(word)?|kata ?sandi|\bsandi\b|user ?name|\blogin\b|cpanel|\bpin\b|token|api[ _-]?key', re.I)
# Teks panduan bawaan template form, bukan isian klien.
GUIDE = re.compile(r'^(silahkan|silakan|misal|contoh|jika bingung|untuk isi|pada gambar|\(tampilan|'
                   r'nama domain adalah|responsive desain itu|hyperlink|dapat di ?lihat|\*)', re.I)
ALLOWED = re.compile(r"[A-Za-z0-9\s.,:;!?'\"()\[\]\-/&@+%#=_]")
PERSONAL_START = re.compile(r'data pribadi pemilik', re.I)
PERSONAL_END = re.compile(r'apakah desain|warna tema|konsep desain|responsive', re.I)
# Label form yang berisi data pribadi pemilik, bukan data usaha.
PERSONAL_LABELS = re.compile(r'^(nama anda|nama pemilik|email|e-mail|whatsapp|no hp|no\. hp)', re.I)


def _ocr_pdf(path):
    """PDF hasil scan (company profile berupa gambar) tidak punya lapisan teks;
    baca beberapa halaman pertama lewat OCR tesseract (bahasa Indonesia + Inggris)."""
    if not shutil.which('pdftoppm') or not shutil.which('tesseract'):
        return []
    lines = []
    with tempfile.TemporaryDirectory() as tmp:
        try:
            subprocess.run(['pdftoppm', '-r', '150', '-f', '1', '-l', str(OCR_PAGES), '-png', str(path), f'{tmp}/p'],
                           capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            return []
        for img in sorted(Path(tmp).glob('p*.png')):
            try:
                r = subprocess.run(['tesseract', str(img), 'stdout', '-l', 'ind+eng'],
                                   capture_output=True, text=True, timeout=90)
            except subprocess.TimeoutExpired:
                continue
            # PDF penuh desain menghasilkan serpihan acak ("OY el Rea j"); simpan
            # hanya baris yang sebagian besar berupa kata.
            for line in r.stdout.splitlines():
                tokens = line.split()
                words = [t for t in tokens if re.fullmatch(r"[A-Za-z][A-Za-z'.,&-]{2,}", t)]
                if len(tokens) >= 2 and len(words) / len(tokens) >= 0.6:
                    lines.append(line)
    return lines


def _doc_lines(path):
    ext = path.suffix.lower()
    try:
        if ext == '.pdf':
            r = subprocess.run(['pdftotext', '-layout', '-l', '20', '-q', str(path), '-'],
                               capture_output=True, text=True, timeout=60)
            lines = r.stdout.splitlines()
            if len(''.join(lines).strip()) < 200:
                lines = _ocr_pdf(path) or lines
            return lines
        if ext == '.txt':
            return path.read_text(errors='replace').splitlines()
        return extract_text(path)  # .docx / .doc, dideteksi lewat magic bytes
    except (OSError, subprocess.TimeoutExpired):
        return []


def _mark_personal(lines):
    out, inside = [], False
    for line in lines:
        if not inside and PERSONAL_START.search(line):
            inside = True
            out.append('[MULAI DATA ADMINISTRASI PEMILIK - rahasia: jangan tampilkan nama, email, '
                       'atau WhatsApp pribadi ini di website]')
            continue
        if inside and PERSONAL_END.search(line):
            inside = False
            out.append('[SELESAI DATA ADMINISTRASI PEMILIK]')
        out.append(line)
    if inside:
        out.append('[SELESAI DATA ADMINISTRASI PEMILIK]')
    return out


def _clean_lines(lines):
    out, seen, drop_next = [], set(), False
    for raw in lines:
        line = ' '.join(str(raw).split())
        if drop_next:
            drop_next = False
            # Nilai kredensial kadang ditulis di baris sesudah labelnya.
            if len(line) <= 40 and ' ' not in line:
                continue
        if CRED.search(line):
            drop_next = True
            continue
        if len(line) < 3 or line.lower() in seen or GUIDE.match(line):
            continue
        # Sisa biner .doc (ÿÿÿ, nama font, id acak) gagal di sini.
        if sum(1 for c in line if ALLOWED.match(c)) / len(line) < 0.9:
            continue
        if not re.search(r'[A-Za-z]{2}', line) and not re.search(r'\d{6}', line):
            continue
        if ' ' not in line and len(line) > 25 and '@' not in line and '.' not in line:
            continue
        seen.add(line.lower())
        out.append(line)
    return out


def collect_client_docs(folder, total_budget=TOTAL_BUDGET):
    """{'sources': [(nama, teks)], 'unreadable': [...], 'skipped': [...]}"""
    folder = Path(folder)
    result = {'sources': [], 'unreadable': [], 'skipped': []}
    if not folder.is_dir():
        return result
    files = [p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in DOC_EXTS]
    # Dokumen teks asli (docx/txt) didahulukan dari PDF: PDF sering hasil scan
    # yang hanya terbaca lewat OCR dan menghabiskan anggaran karakter.
    files.sort(key=lambda p: (not p.name.upper().startswith('FORM ISIAN'),
                              not PRIORITY.search(p.name), p.suffix.lower() == '.pdf', str(p).lower()))
    used = 0
    for path in files:
        name = str(path.relative_to(folder))
        # Manifest/catatan hosting (<domain>.txt) berisi kredensial, bukan data usaha.
        if path.suffix.lower() == '.txt' and (path.stem.strip().lower() == folder.name.lower()
                                              or 'credential' in path.name.lower()):
            continue
        lines = [' '.join(str(l).split()) for l in _doc_lines(path)]
        if path.name.upper().startswith('FORM ISIAN'):
            lines = _mark_personal(lines)
        text = '\n'.join(_clean_lines(lines))
        if len(text) < 40:
            result['unreadable'].append(name)  # mis. PDF hasil scan tanpa teks
            continue
        room = min(PER_DOC_BUDGET, total_budget - used)
        if room < 300:
            result['skipped'].append(name)
            continue
        if len(text) > room:
            text = text[:room].rsplit('\n', 1)[0]
        result['sources'].append((name, text))
        used += len(text)
    return result


def format_for_prompt(fields, docs):
    """Teks data klien siap masuk prompt: field terstruktur + isi dokumen."""
    parts = []
    rows = [f'- {k}: {v}' for k, v in fields.items()
            if not CRED.search(k) and not CRED.search(v) and not PERSONAL_LABELS.match(k)]
    if rows:
        parts.append('DATA TERSTRUKTUR DARI FORM:\n' + '\n'.join(rows))
    for name, text in docs['sources']:
        parts.append(f'DOKUMEN KLIEN "{name}":\n{text}')
    return '\n\n'.join(parts) or '(tidak ada data klien)'


if __name__ == '__main__':
    import sys
    res = collect_client_docs(sys.argv[1])
    for name, text in res['sources']:
        print(f'--- {name}: {len(text)} karakter')
    print('tidak terbaca:', res['unreadable'], '| dilewati (anggaran habis):', res['skipped'])
