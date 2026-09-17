#!/usr/bin/env python3
"""
AI Content Generator for Velocity WP Install
Reads manifest + client folder data, calls OpenAI-compatible API,
generates pages (Home, Profile, Gallery, Contact) + articles via WP-CLI
"""
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from client_form import read_client_form
from client_docs import collect_client_docs, format_for_prompt
from content_sanitize import buang_kalimat_meragukan, clean_html

CONTENT_RULES = """Aturan konten (wajib):
- Gunakan HANYA fakta dari data klien di atas: nama usaha, produk/layanan, keunggulan, sejarah, visi-misi, area layanan, alamat, kontak. Jangan mengarang nomor telepon, alamat, harga, angka, penghargaan, atau klaim yang tidak ada di data. Kalau suatu info tidak ada, lewati tanpa menulis contoh palsu.
- Bagian bertanda DATA ADMINISTRASI PEMILIK hanya referensi internal: jangan tampilkan nama, email, atau WhatsApp pribadi pemilik. Kontak publik ambil dari "Kontak utk di web" atau kontak di dokumen perusahaan.
- Jangan pernah menulis bahwa suatu informasi belum tersedia, tidak tercantum, atau tidak ada di data — cukup lewati bagiannya. Jangan menulis sertifikasi, garansi, layanan gratis, lama pengalaman, atau jumlah proyek/klien kecuali tertulis di data klien.
- Abaikan teks panduan bawaan template form (mis. "Silahkan ...", "Misal ...", "Contoh ...") dan contoh isian yang bukan milik klien.
- Kalau klien menjelaskan isi halaman, susunan menu, produk, atau layanan, ikuti dan jabarkan dari situ.
- Jangan menulis tag <img>, <figure>, <iframe>, <form>, URL gambar, atau kata "placeholder"/teks contoh. Foto, galeri, peta, dan tombol WhatsApp dipasang otomatis oleh sistem dari file klien."""

# Artikel contoh portal berita: pengetahuan umum per rubrik. CONTENT_RULES ("HANYA
# fakta dari data klien") membuat AI menolak rubrik umum seperti Rasa/Tokoh
# (anaksegalabangsa.com 2026-09-14) karena prompt berita tidak memuat data klien.
ATURAN_BERITA = """Aturan konten (wajib):
- Tulis pengetahuan umum yang benar dan tidak diperdebatkan. Jangan mengarang angka, harga, penghargaan, kutipan, atau klaim yang tidak bisa diperiksa.
- Jangan menyebut nama, alamat, email, atau nomor telepon siapa pun, termasuk pemilik situs.
- Jangan menulis tag <img>, <figure>, <iframe>, <form>, URL gambar, atau kata "placeholder"/teks contoh. Foto utama dipasang otomatis oleh sistem."""

PENOLAKAN_AI = re.compile(r'data klien|belum tersedia|tidak tersedia|tidak dapat (menulis|membuat)|maaf,? saya', re.I)

CREDENTIAL_RE = re.compile(r'^\s*(pass(word)?|user(name)?|sandi|login)\s*[:=]', re.I | re.M)

MANIFEST = Path(sys.argv[1]) if len(sys.argv) > 1 else None
ON_PROGRESS = Path('/home/On Progress')
MODE = os.environ.get('INSTALL_MODE', 'dry-run')
AI_CONFIG_DIR = Path('/var/lib/velocity/ai')
AI_MODELS = AI_CONFIG_DIR / 'models.json'
GENERATED_DIR = AI_CONFIG_DIR / 'generated'
LOG_FILE = Path('/var/lib/velocity/installer') / f'ai-{MANIFEST.stem}.log' if MANIFEST else Path('/dev/null')
# Satu baris JSON per panggilan AI; dijumlah per domain & run di halaman /ai/ (GET /api/ai/usage).
AI_USAGE = AI_CONFIG_DIR / 'usage.jsonl'

def log(msg):
    ts = subprocess.run(['date', '-Is'], capture_output=True, text=True).stdout.strip()
    line = f'[{ts}] {msg}'
    print(line, file=sys.stderr)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def read_manifest(path):
    cfg = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = re.sub(r'[\s\r]', '', k)
            v = v.strip()
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', k):
                cfg[k] = v
    return cfg

def read_client_data(folder):
    """Read client .txt notes plus the FORM ISIAN document the client filled in"""
    data = {}
    folder = Path(folder)
    for f in sorted(folder.glob('*.txt')):
        # Nama file kredensial tidak selalu persis '<domain>.txt' (mis. ada spasi
        # sebelum ekstensi), jadi cocokkan longgar lalu saring lagi lewat isinya —
        # file ini berisi username/password dan tidak boleh sampai ke API AI.
        if f.stem.strip().lower() == folder.name.strip().lower():
            continue
        body = f.read_text(errors='replace').strip()
        if CREDENTIAL_RE.search(body):
            log(f'Skip {f.name}: berisi kredensial, tidak dikirim ke AI')
            continue
        data[f.stem] = body
    form = read_client_form(folder)
    for label, value in form['fields'].items():
        data.setdefault(label, value)
    if form['fields']:
        log(f'Client form fields: {len(form["fields"])}')
    if form['unreadable']:
        log(f'Client form unreadable (butuh penanganan manual): {form["unreadable"]}')
    return data

def load_ai_models():
    try:
        if AI_MODELS.is_file():
            return json.loads(AI_MODELS.read_text())
    except (OSError, ValueError):
        pass
    return {'models': [], 'default_provider': 'openai'}

def get_default_model():
    data = load_ai_models()
    models = data.get('models', [])
    for m in models:
        if m.get('is_default'):
            return m
    return models[0] if models else None


def get_model(peran):
    """Model untuk satu fungsi installer (halaman /ai/ → models.json 'pemakaian').

    peran: konten (halaman & artikel), isi_contoh (paket-g-konten), foto (paket-g-foto),
    fse (fse-apply). Tanpa pilihan, atau model pilihannya sudah dihapus: model default."""
    data = load_ai_models()
    pilihan = str((data.get('pemakaian') or {}).get(peran) or '')
    model = None
    for m in data.get('models', []):
        if pilihan and m.get('id') == pilihan:
            model = m
    model = model or get_default_model()
    # peran ikut dibawa ke ai_call supaya token tercatat per fungsi.
    return dict(model, peran=peran) if model else None


def domain_proses():
    """Domain yang sedang dikerjakan: dari installer-runner (VELOCITY_DOMAIN), atau nama
    manifest /home/project/<domain>/<domain>.txt kalau script dijalankan sendiri."""
    if os.environ.get('VELOCITY_DOMAIN'):
        return os.environ['VELOCITY_DOMAIN']
    for a in sys.argv[1:]:
        if a.endswith('.txt'):
            return Path(a).stem
    return ''


def catat_token(model, usage, model_jawab, ok):
    """Tulis pemakaian token satu panggilan AI ke usage.jsonl. Tidak boleh menggagalkan run."""
    import fcntl
    from datetime import datetime, timezone
    try:
        prompt = int(usage.get('prompt_tokens') or 0)
        jawaban = int(usage.get('completion_tokens') or 0)
        baris = {
            'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'domain': domain_proses(),
            'run': os.environ.get('VELOCITY_RUN_ID', ''),
            'mode': MODE,
            'peran': model.get('peran', ''),
            'script': Path(sys.argv[0]).name,
            'model_id': model.get('id', ''),
            'model': model_jawab or model.get('model', ''),
            'prompt_tokens': prompt,
            'completion_tokens': jawaban,
            'total_tokens': int(usage.get('total_tokens') or prompt + jawaban),
            'ok': ok,
        }
        with open(AI_USAGE, 'a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(json.dumps(baris, ensure_ascii=False) + '\n')
    except Exception as e:
        log(f'WARNING: pemakaian token tidak tercatat: {e}')

def ai_call(system_prompt, user_prompt, model, timeout=None, max_tokens=None):
    """Call OpenAI-compatible API.

    `timeout` detik (bawaan VELOCITY_AI_TIMEOUT atau 120). Prompt panjang seperti isi
    contoh tema butuh lebih lama: 2026-09-16 layanan AI melambat (prompt satu kalimat
    saja 57 detik) sehingga dua percobaan isi contoh habis waktu dan gagal.
    """
    api_key = model.get('api_key', '')
    if not api_key:
        log('ERROR: API key not found in model config')
        return None
    
    endpoint = model.get('endpoint', 'https://api.openai.com/v1')
    model_name = model.get('model', '')
    temperature = model.get('temperature', 0.7)
    # Model penalar (mis. xiaomi/mimo-v2.5) menghabiskan jatah ini untuk berpikir dan
    # mengembalikan content KOSONG kalau jatahnya habis — gejalanya panggilan "berhasil"
    # (token tercatat) tapi tanpa jawaban (medikaklinikteknologi.com, 2026-09-16).
    max_tokens = max_tokens or model.get('max_tokens') or 4096
    
    payload = json.dumps({
        'model': model_name,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        'temperature': temperature,
        'max_tokens': max_tokens
    }).encode()
    
    req = urllib.request.Request(
        f'{endpoint}/chat/completions',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
    )
    
    tercatat = False
    try:
        with urllib.request.urlopen(req, timeout=timeout or int(os.environ.get('VELOCITY_AI_TIMEOUT', '120'))) as resp:
            result = json.loads(resp.read())
            catat_token(model, result.get('usage') or {}, result.get('model', ''), True)
            tercatat = True
            pilihan = result['choices'][0]
            content = pilihan['message'].get('content') or ''
            if not content.strip():
                log(f"ERROR: jawaban AI kosong (finish_reason={pilihan.get('finish_reason')}, "
                    f"completion_tokens={(result.get('usage') or {}).get('completion_tokens')}, "
                    f"max_tokens={max_tokens})")
                return None
            # Strip markdown code fences
            content = content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].strip().startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                content = '\n'.join(lines)
            return content
    except Exception as e:
        log(f'ERROR: AI API call failed: {e}')
        if not tercatat:
            catat_token(model, {}, '', False)
        return None

def ai_json_list(system_prompt, user_prompt, model, jenis):
    """Panggil AI dan urai array JSON; satu kali ulang kalau JSON-nya rusak.

    centralimpex.com (2026-09-16/17): jawaban AI sesekali terpotong atau berkutip tak
    di-escape ("Unterminated string", "Expecting property name"), sehingga semua halaman
    atau satu kategori artikel hilang dari instalasi."""
    for percobaan in (1, 2):
        prompt = user_prompt if percobaan == 1 else (
            user_prompt + '\n\nIMPORTANT: your previous answer was not valid JSON. Return ONLY a complete, '
            'valid JSON array: escape every double quote inside strings as \\", no trailing commas, '
            'and keep each content within the requested length so the array is not cut off.')
        response = ai_call(system_prompt, prompt, model)
        if not response:
            return None
        try:
            # strict=False: baris baru/tab mentah di dalam teks HTML jawaban AI membuat
            # json.loads gagal "Invalid control character" (sobirin-advokat.com 2026-09-16).
            hasil = json.loads(response, strict=False)
        except json.JSONDecodeError as e:
            log(f'ERROR: Failed to parse {jenis} JSON (percobaan {percobaan}): {e}')
            log(f'Response: {response[:500]}')
            continue
        if not isinstance(hasil, list):
            log('ERROR: AI response is not a JSON array')
            return None
        if percobaan > 1:
            log(f'{jenis} JSON valid pada percobaan {percobaan}')
        return hasil
    return None


def generate_pages(site_title, domain, client_info, model):
    """Generate 4 pages: Home, Profile, Gallery, Contact"""
    system_prompt = "You are a professional Indonesian web content writer. Generate content in valid JSON format. All text content must be in Indonesian language. Output ONLY valid JSON array, no markdown fences, no extra text."
    
    client_info = client_info.strip() or '(tidak ada data klien)'
    
    user_prompt = f"""Generate WordPress page content for a website with these details:
- Site title: {site_title}
- Domain: {domain}
- Client data:
{client_info}

{CONTENT_RULES}

Generate 4 pages plus a tagline. Return JSON array:
[
  {{"slug":"home","title":"Home","content":"<HTML homepage: hero heading and intro, products/services, advantages, call to action. 300-500 words.>"}},
  {{"slug":"profile","title":"Profil","content":"<HTML company/organization profile. Include history, vision-mission, values, or team ONLY when they appear in the client data; silently skip missing parts. Never write that some information is unavailable or not provided. 300-500 words.>"}},
  {{"slug":"gallery","title":"Gallery","content":"<HTML short intro for the photo gallery describing the client's products or activities. 60-120 words. Photos are added automatically.>"}},
  {{"slug":"contact","title":"Kontak","content":"<HTML contact info: public phone/WhatsApp, email, address, opening hours only if present in client data, plus an invitation to get in touch. 80-200 words. No form, no map.>"}},
  {{"slug":"tagline","title":"Tagline","content":"<client's slogan if present, otherwise a plain-text summary of the business, max 8 words, no HTML>"}}
]

Use Indonesian language. Content should be professional HTML without images, forms, iframes, or placeholders."""
    
    return ai_json_list(system_prompt, user_prompt, model, 'pages')

def rapikan_artikel(daftar, category):
    """Artikel valid saja, dengan nama kolom baku.

    AI kadang memakai kolom berbahasa Indonesia ("judul", "isi", "ringkasan"):
    anaksegalabangsa.com menyimpan 3 artikel Pendidikan dengan judul, slug, dan
    isi kosong, yang lalu diam-diam tidak terbit."""
    hasil = []
    for a in daftar if isinstance(daftar, list) else []:
        if not isinstance(a, dict):
            continue
        judul = str(a.get('title') or a.get('judul') or '').strip()
        isi = str(a.get('content') or a.get('isi') or a.get('konten') or '').strip()
        if not judul or len(re.sub(r'<[^>]+>', ' ', isi).split()) < 120:
            continue
        # AI yang menolak menulis tetap mengisi kolom lengkap ("Data Klien Belum
        # Tersedia untuk Artikel Rubrik Tokoh", 166 kata) dan lolos batas panjang.
        if PENOLAKAN_AI.search(judul) or PENOLAKAN_AI.search(isi[:600]):
            continue
        slug = re.sub(r'[^a-z0-9]+', '-', str(a.get('slug') or judul).lower()).strip('-')[:80]
        hasil.append({'title': judul, 'slug': slug, 'category': category, 'content': isi,
                      'excerpt': str(a.get('excerpt') or a.get('ringkasan') or '').strip()})
    return hasil


BIODATA_KUNCI = re.compile(r'^(alamat lengkap|nama anda|nama pemilik|whatsapp|no\.? ?wa|e-?mail|kodepos)$', re.I)


def buang_data_pemilik(konten, client_data):
    """Buang paragraf/butir yang memuat biodata pemilik dari isi halaman & artikel.

    Aturan prompt melarangnya, tetapi halaman Hubungi Kami anaksegalabangsa.com
    tetap terbit dengan "Alamat Media: Desa Kedanyang RT 4 RW 1" — alamat rumah
    pemilik dari bagian biodata FORM ISIAN. Karena itu dijaga di kode."""
    nilai = []
    for kunci, isi in (client_data or {}).items():
        if not BIODATA_KUNCI.match(str(kunci).strip()):
            continue
        teks = re.sub(r'\s+', ' ', str(isi or '')).strip().lower()
        angka = re.sub(r'\D', '', teks)
        if len(angka) >= 8 and len(angka) >= len(re.sub(r'\W', '', teks)) * 0.7:
            nilai.append(('angka', angka))
        elif len(teks) >= 6:
            nilai.append(('teks', teks))
    if not nilai or not konten:
        return konten, 0

    def berisi_biodata(blok):
        polos = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', blok)).strip().lower()
        angka = re.sub(r'\D', '', polos)
        return any((v in angka) if jenis == 'angka' else (v in polos) for jenis, v in nilai)

    dibuang = [0]

    def saring(m):
        if berisi_biodata(m.group(0)):
            dibuang[0] += 1
            return '<!--biodata-dibuang-->'
        return m.group(0)

    hasil = re.sub(r'<(p|li|address|td)\b[^>]*>.*?</\1>', saring, str(konten), flags=re.S | re.I)
    # Judul yang isinya langsung dibuang ("Alamat Media" di atas alamat pemilik)
    # ikut dibuang, begitu pula judul yang kehilangan seluruh isinya.
    hasil = re.sub(r'<h([2-4])\b[^>]*>[^<]*</h\1>\s*(?=<!--biodata-dibuang-->)', '', hasil, flags=re.I)
    hasil = re.sub(r'\s*<!--biodata-dibuang-->\s*', '', hasil)
    hasil = re.sub(r'<(ul|ol)\b[^>]*>\s*</\1>', '', hasil, flags=re.I)
    hasil = re.sub(r'<h[2-4]\b[^>]*>[^<]*</h[2-4]>\s*(?=<h[1-4]\b|</section>|$)', '', hasil, flags=re.I)
    return hasil, dibuang[0]


def generate_articles(site_title, domain, client_info, model, num_articles=5, category='Blog',
                      rincian_topik='', gaya='bisnis'):
    """Artikel untuk satu kategori.

    `category` bukan sekadar label yang ditempel: semua artikel dalam satu
    panggilan harus benar-benar membahas layanan itu. Tanpa batasan ini, AI
    menulis artikel umum lalu kategorinya jadi tidak nyambung — mis. artikel
    interior masuk kategori "Bangun Baru".
    """
    system_prompt = "You are a professional Indonesian web content writer. Generate content in valid JSON format. All text content must be in Indonesian language. Output ONLY valid JSON array, no markdown fences, no extra text."
    
    client_info = client_info.strip() or '(tidak ada data klien)'
    topik = f'{category}. {rincian_topik}'.strip() if rincian_topik else category
    
    if gaya == 'berita':
        # Portal berita custom (2026-09-14): contoh artikel tidak boleh berupa
        # laporan peristiwa karangan — situs berita yang menerbitkan kejadian,
        # nama, atau kutipan fiktif sama dengan menyebar hoaks.
        user_prompt = f"""Tulis {num_articles} artikel contoh untuk rubrik "{category}" di portal berita {site_title} ({domain}).
Keterangan rubrik: {rincian_topik or category}

ATURAN WAJIB:
- Artikel informatif/feature yang TIDAK terikat peristiwa tertentu: penjelasan, panduan, tips, latar belakang isu umum yang sesuai rubrik.
- JANGAN menulis laporan kejadian. JANGAN mengarang peristiwa, nama orang, nama instansi atau perusahaan tertentu, kutipan wawancara, angka statistik, tanggal, atau lokasi kejadian.
- Gaya jurnalistik ringkas: paragraf pendek, subjudul <h2> bila perlu, judul menarik tetapi tidak clickbait.
- Setiap artikel membahas sudut yang berbeda dan jelas termasuk rubrik "{category}".
- Artikel ini pengetahuan umum sesuai rubrik, TIDAK membutuhkan data klien. Jangan menolak, jangan menulis bahwa data belum tersedia.

{ATURAN_BERITA}

Return JSON array:
[
  {{"title":"<judul>","slug":"<url-slug>","category":"{category}","content":"<isi HTML 350-550 kata>","excerpt":"<ringkasan 20-30 kata>"}}
]"""
        for percobaan in range(2):
            response = ai_call(system_prompt, user_prompt, model)
            if not response:
                log(f'Artikel rubrik {category} percobaan {percobaan + 1}: AI tidak menjawab')
                continue
            try:
                articles = rapikan_artikel(json.loads(response[response.find('['):response.rfind(']') + 1]), category)
            except json.JSONDecodeError as e:
                log(f'Artikel rubrik {category} percobaan {percobaan + 1}: JSON rusak ({e})')
                continue
            if articles:
                return articles
            log(f'Artikel rubrik {category} percobaan {percobaan + 1}: tidak ada artikel yang lengkap')
        return None

    user_prompt = f"""Generate {num_articles} blog articles for a website with these details:
- Site title: {site_title}
- Domain: {domain}
- Client data:
{client_info}

TOPIC REQUIREMENT (most important):
Every article MUST be about this one service: {topik}
- Do not write about the client's other services.
- Each article must cover a different angle of this service (persiapan, proses, pemilihan material, biaya, perawatan, kesalahan umum, dsb).
- The article title must make the service recognisable to a reader.

{CONTENT_RULES}

Return JSON array:
[
  {{"title":"<article title>","slug":"<url-slug>","category":"{category}","content":"<article content in HTML, 400-600 words, professional Indonesian>","excerpt":"<short excerpt 20-30 words>"}}
]

Use Indonesian language. Ground the content in the client's actual field of business from the client data."""
    
    return ai_json_list(system_prompt, user_prompt, model, 'articles')

def kategori_layanan(domain, da_user, ssh_port, ssh_user, target_host):
    """Judul layanan dari child theme yang terpasang, untuk dipakai jadi kategori.

    Dibaca dari situs, bukan dari berkas template di installer: awalan fungsi
    tema berbeda per situs, dan menebaknya pernah membuat isi tidak cocok.
    """
    ssh_key = os.environ.get('WP_INSTALL_SSH_KEY_FILE', '')
    if not ssh_key or not Path(ssh_key).is_file():
        return []
    # Judul + keterangan layanan: keterangannya dipakai sebagai batasan topik
    # artikel, supaya isinya benar-benar tentang layanan itu.
    skrip = (
        "global $shortcode_tags; $jenis = ''; $daftar = null;"
        "foreach (array_keys($shortcode_tags) as $t) {"
        "  if (preg_match('/^([a-z0-9]+)_layanan$/', $t, $m) && function_exists($m[1] . '_data')) {"
        "    $jenis = call_user_func($m[1] . '_data', 'jenis');"
        "    $daftar = $jenis === 'berita' ? call_user_func($m[1] . '_data', 'rubrik') : call_user_func($m[1] . '_data', 'layanan');"
        "    break;"
        "  }"
        "}"
        # Tema FSE velocity-fse (scripts/fse-apply): rubrik/layanan tinggal di opsi velocity_situs.
        "$s = get_option('velocity_situs');"
        "if ($daftar === null && is_array($s) && !empty($s['jenis'])) {"
        "  $jenis = $s['jenis'];"
        "  $daftar = $jenis === 'berita' ? ($s['rubrik'] ?? array()) : ($s['layanan'] ?? array());"
        "}"
        "if ($jenis === 'berita') { echo \"#jenis\\tberita\\n\"; }"
        "foreach ((array) $daftar as $l) {"
        "  if (!empty($l['judul'])) {"
        "    $r = !empty($l['rincian']) ? implode(', ', (array) $l['rincian']) : '';"
        "    echo $l['judul'] . \"\\t\" . trim(($l['teks'] ?? '') . ' ' . $r) . \"\\n\";"
        "  }"
        "}"
    )
    perintah = (f'php -d memory_limit=512M /usr/local/bin/wp eval {shlex.quote(skrip)} '
                f'--path=/home/{da_user}/domains/{domain}/public_html --allow-root 2>/dev/null')
    try:
        hasil = subprocess.run(
            ['ssh', '-i', ssh_key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
             '-o', 'ConnectTimeout=15', '-p', str(ssh_port), f'{ssh_user}@{target_host}', perintah],
            capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return []
    layanan, jenis = [], ''
    for baris in hasil.stdout.splitlines():
        if baris.startswith('#jenis\t'):
            jenis = baris.split('\t', 1)[1].strip()
            continue
        if not baris.strip():
            continue
        judul, _, keterangan = baris.partition('\t')
        # Judul kategori dipakai apa adanya; batasi panjang agar wajar.
        layanan.append({'judul': judul.strip()[:60], 'keterangan': keterangan.strip()[:400], 'jenis': jenis})
    # Portal berita bisa punya lebih banyak rubrik daripada layanan perusahaan.
    return layanan[:10 if jenis == 'berita' else 6]


def kategori_isi_contoh(domain):
    """Layanan dari isi contoh (<domain>-tema.json, scripts/paket-g-konten) sebagai kategori artikel.

    Child theme klasik (Paket E/F, dll.) tidak menyimpan daftar layanan, sehingga semua
    artikel dulu masuk satu kategori "Blog" (sedotwcsrirejeki.com, rmbrentcar.com 2026-09-17)."""
    try:
        isi = json.loads((GENERATED_DIR / f'{domain}-tema.json').read_text())
    except (OSError, ValueError):
        return []
    if isi.get('jenis') == 'berita':
        return [{'judul': r['judul'], 'keterangan': str(r.get('teks') or ''), 'jenis': 'berita'}
                for r in isi.get('rubrik') or [] if r.get('judul')]
    return [{'judul': l['judul'], 'keterangan': ' '.join([str(l.get('teks') or '')] + list(l.get('rincian') or [])).strip()}
            for l in isi.get('layanan') or [] if l.get('judul')]


def publish_content(domain, da_user, ssh_port, ssh_user, target_host, pages, articles, pensiun=()):
    """Publish generated content to WordPress via SSH + WP-CLI"""
    ssh_key = os.environ.get('WP_INSTALL_SSH_KEY_FILE', '')
    if not ssh_key or not Path(ssh_key).is_file():
        log('ERROR: SSH key not found')
        return False
    
    # Situs di lokasi tidak baku (staging velocitydeveloper.co): pengganti ssh + docroot
    # lewat VELOCITY_LOKAL_*, sama seperti scripts/fse-apply & scripts/site-finish.
    lokal_ssh = os.environ.get('VELOCITY_LOKAL_SSH', '')
    lokal_docroot = os.environ.get('VELOCITY_LOKAL_DOCROOT', '')
    docroot = lokal_docroot or f'/home/{da_user}/domains/{domain}/public_html'

    def wp_remote(cmd_script):
        """Run WP-CLI command on remote server"""
        full_cmd = f'''set -e
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
WP_BIN=""; for p in /usr/local/bin/wp /usr/bin/wp; do [[ -x "$p" ]] && WP_BIN="$p" && break; done
[[ -n "$WP_BIN" ]] || {{ echo "wp-cli_missing"; exit 10; }}
DOCROOT="{docroot}"
{cmd_script}
'''
        try:
            result = subprocess.run(
                ([lokal_ssh] if lokal_ssh and lokal_docroot else
                 ['ssh', '-i', ssh_key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
                  '-o', 'ConnectTimeout=15', '-p', str(ssh_port), f'{ssh_user}@{target_host}']) + ['bash', '-s'],
                input=full_cmd, capture_output=True, text=True, timeout=120
            )
            return result.stdout.strip(), result.returncode
        except Exception as e:
            log(f'ERROR: SSH command failed: {e}')
            return '', 1
    
    # Konten AI langsung mengisi halaman terbit buatan 1-Click Setup, tidak lagi
    # jadi draft terpisah: dulu pengunjung melihat placeholder satu kalimat
    # sementara konten sungguhan tertahan di draft Home/Profil/Gallery/Kontak.
    # Halaman yang isinya sudah bukan placeholder (disunting manusia) dibiarkan.
    # Beranda sudah dijadikan halaman depan oleh installer.
    page_targets = {
        'home': (('Beranda', 'Home'), 'Selamat datang di website kami.'),
        'profile': (('Tentang Kami',), 'Halaman tentang kami.'),
        'gallery': (('Galeri',), 'Halaman galeri.'),
        'contact': (('Hubungi Kami',), 'Halaman hubungi kami.'),
    }
    # VELOCITY_CONTENT_REFRESH=1 (mode finish): timpa halaman target walau sudah
    # bukan placeholder — untuk situs yang kontennya ditulis sebelum ada penanda
    # md5 dan perlu dibersihkan (gambar karangan, placeholder).
    refresh = '1' if os.environ.get('VELOCITY_CONTENT_REFRESH') == '1' else '0'
    helpers = '''cur_md5() { $WP_BIN post get "$1" --field=post_content --path="$DOCROOT" --allow-root 2>/dev/null | md5sum | cut -d' ' -f1; }
save_md5() { $WP_BIN post meta update "$1" _velocity_content_md5 "$(cur_md5 "$1")" --path="$DOCROOT" --allow-root >/dev/null 2>&1 || true; }
'''
    pages_done = 0
    for page in pages:
        slug = re.sub(r'[^a-z0-9-]', '', str(page.get('slug', '')).lower())
        content = clean_html(page.get('content', ''))
        if slug not in page_targets or not content:
            continue
        titles, placeholder = page_targets[slug]
        escaped_content = content.replace("'", "'\\''")
        title_args = ' '.join(f"'{t}'" for t in titles)
        cmd = helpers + f'''page_id=""
for t in {title_args}; do
  page_id=$($WP_BIN post list --post_type=page --post_status=publish --fields=ID,post_title --path="$DOCROOT" --allow-root 2>/dev/null | awk -F'\\t' -v t="$t" 'NR>1 && $2==t {{print $1; exit}}')
  [[ -n "$page_id" ]] && break
done
if [[ -z "$page_id" ]]; then
  page_id=$($WP_BIN post create --post_type=page --post_status=publish --post_title='{titles[0]}' --post_content='{escaped_content}' --path="$DOCROOT" --allow-root --porcelain 2>/dev/null || true)
  [[ -n "$page_id" ]] && save_md5 "$page_id" && echo "page_created:{slug}:$page_id"
else
  current=$($WP_BIN post get "$page_id" --field=post_content --path="$DOCROOT" --allow-root 2>/dev/null || true)
  stored=$($WP_BIN post meta get "$page_id" _velocity_content_md5 --path="$DOCROOT" --allow-root 2>/dev/null || true)
  fse_milik=$($WP_BIN post meta get "$page_id" _velocity_fse_md5 --path="$DOCROOT" --allow-root 2>/dev/null || true)
  fse_tata=$($WP_BIN post meta get "$page_id" _velocity_fse_layout --path="$DOCROOT" --allow-root 2>/dev/null || true)
  # Tema FSE (scripts/fse-apply): halaman ini milik fse-apply, isinya blok yang
  # disusun dari data situs — tulisan AI TIDAK PERNAH menimpanya, termasuk di mode
  # finish. Pengecualian refresh dulu ada di sini dan merusak situs: generator
  # menulis ulang Tentang Kami/Galeri/Hubungi Kami jadi HTML polos, lalu
  # `fse-apply --isi` menolak memperbaikinya karena isinya tidak lagi cocok dengan
  # md5 miliknya ("sudah disunting orang") — blok kontak, media sosial, dan form
  # pemesanan hilang permanen (bumiairchemitech.com, 2026-09-16).
  if [[ -n "$fse_tata" || -n "$fse_milik" ]]; then
    echo "page_kept_fse:{slug}:$page_id"
  # Ditimpa hanya kalau masih placeholder, mode finish, atau isinya belum berubah
  # sejak terakhir ditulis installer (md5 sama) — suntingan manusia tidak hilang.
  elif [[ "$current" == '{placeholder}' || "{refresh}" == 1 ]] || {{ [[ -n "$stored" ]] && [[ "$stored" == "$(cur_md5 "$page_id")" ]]; }}; then
    $WP_BIN post update "$page_id" --post_content='{escaped_content}' --path="$DOCROOT" --allow-root >/dev/null 2>&1 && save_md5 "$page_id" && echo "page_filled:{slug}:$page_id"
  else
    echo "page_kept:{slug}:$page_id"
  fi
fi
# Draft buatan generator versi lama (slug home/profile/gallery/contact).
for old in $($WP_BIN post list --post_type=page --post_status=draft --name='{slug}' --field=ID --path="$DOCROOT" --allow-root 2>/dev/null); do
  $WP_BIN post delete "$old" --force --path="$DOCROOT" --allow-root >/dev/null 2>&1 && echo "old_draft_deleted:{slug}:$old"
done'''
        output, rc = wp_remote(cmd)
        if 'page_created' in output or 'page_filled' in output:
            pages_done += 1
        log(f'Halaman {slug}: {" ".join(output.split()) or "tanpa_output"}')
    
    # Kategori disiapkan per artikel: artikel dikelompokkan mengikuti layanan
    # klien, jadi satu situs bisa punya beberapa kategori sekaligus.
    def id_kategori(nama):
        aman = nama.replace("'", "'\\''")
        keluaran, _ = wp_remote(f'''cat_id=$($WP_BIN term list category --name='{aman}' --field=term_id --path="$DOCROOT" --allow-root 2>/dev/null | head -1)
if [[ -z "$cat_id" ]]; then
  cat_id=$($WP_BIN term create category '{aman}' --porcelain --path="$DOCROOT" --allow-root 2>/dev/null || true)
  echo "category_created:$cat_id"
else
  echo "category_exists:$cat_id"
fi''')
        cocok = re.search(r'category_(?:created|exists):(\d+)', keluaran)
        if cocok:
            log(f'Kategori {nama}: {cocok.group(1)}')
            return cocok.group(1)
        log(f'Kategori {nama}: gagal dibuat')
        return ''

    peta_kategori = {}
    for art in articles:
        nama = str(art.get('category') or 'Blog')[:60]
        if nama not in peta_kategori:
            peta_kategori[nama] = id_kategori(nama)
    
    # Artikel contoh lama yang kategorinya sudah tidak dipakai situs (mis. semua
    # "Blog" sebelum rubrik ada) dihapus — hanya kalau belum pernah disunting.
    # "Belum disunting" = isinya masih sama dengan versi generator. Tanggal ubah tidak
    # bisa dipakai: installer sendiri memperbarui artikel (terbitkan draft) di run yang sama.
    for slug_lama, md5_isi, md5_baris in pensiun:
        # `wp post get | md5sum` ikut menghitung baris baru di akhir keluaran WP-CLI:
        # tanpa md5 isi + "\n" artikel yang tak pernah disentuh terbaca "disunting"
        # dan tidak pernah dipensiunkan (glcagro.com 2026-09-15).
        if not re.match(r'^[a-z0-9-]+$', str(slug_lama)) \
                or not all(re.match(r'^[0-9a-f]{32}$', str(h)) for h in (md5_isi, md5_baris)):
            continue
        keluaran, _ = wp_remote(f'''pid=$($WP_BIN post list --post_type=post --post_status=publish --name='{slug_lama}' --field=ID --path="$DOCROOT" --allow-root 2>/dev/null | head -1)
if [[ -n "$pid" ]]; then
  h=$($WP_BIN post get "$pid" --field=post_content --path="$DOCROOT" --allow-root | md5sum | cut -d' ' -f1)
  if [[ "$h" == "{md5_isi}" || "$h" == "{md5_baris}" ]]; then
    $WP_BIN post delete "$pid" --force --path="$DOCROOT" --allow-root >/dev/null 2>&1 && echo "article_retired:{slug_lama}"
  else
    echo "article_retire_skip_edited:{slug_lama}"
  fi
fi''')
        if keluaran:
            log(f'Artikel lama {slug_lama}: {keluaran}')

    # Create articles
    articles_done = 0
    for art in articles:
        title = art.get('title', '')
        slug = art.get('slug', '')
        content = clean_html(art.get('content', ''))
        excerpt = art.get('excerpt', '')
        # Kategori artikel ini; kosong berarti pembuatannya gagal dan artikel
        # dibiarkan tanpa kategori daripada masuk ke kategori yang salah.
        cat_id = peta_kategori.get(str(art.get('category') or 'Blog')[:60], '')
        
        if not slug or not title:
            continue
        
        escaped_title = title.replace("'", "'\\''")
        escaped_content = content.replace("'", "'\\''")
        escaped_excerpt = excerpt.replace("'", "'\\''")
        
        # Artikel langsung terbit; draft dari generator versi lama ikut diterbitkan.
        # Status dicari satu per satu: dengan --post_status=any, WP_Query untuk satu
        # slug menyembunyikan draft dari WP-CLI (tanpa user login), sehingga artikel
        # dibuat ulang dengan slug "-2" dan draft lamanya tertinggal.
        cmd = f'''post_id=$($WP_BIN post list --post_type=post --post_status=publish --name='{slug}' --field=ID --path="$DOCROOT" --allow-root 2>/dev/null | head -1)
[[ -n "$post_id" ]] || post_id=$($WP_BIN post list --post_type=post --post_status=draft --name='{slug}' --field=ID --path="$DOCROOT" --allow-root 2>/dev/null | head -1)
if [[ -n "$post_id" ]]; then
  # Duplikat "-2" yang sempat terbit akibat bug di atas.
  for dup in $($WP_BIN post list --post_type=post --post_status=publish --name='{slug}-2' --field=ID --path="$DOCROOT" --allow-root 2>/dev/null); do
    $WP_BIN post delete "$dup" --force --path="$DOCROOT" --allow-root >/dev/null 2>&1 && echo "article_duplicate_deleted:{slug}-2"
  done
fi
if [[ -z "$post_id" ]]; then
  post_id=$($WP_BIN post create --post_type=post --post_status=publish --post_title='{escaped_title}' --post_name='{slug}' --post_content='{escaped_content}' --post_excerpt='{escaped_excerpt}' --path="$DOCROOT" --allow-root --porcelain 2>/dev/null || true)
  [[ -n "$post_id" ]] && echo "article_created:{slug}"
  [[ -n "{cat_id}" && -n "$post_id" ]] && $WP_BIN post term set "$post_id" category {cat_id} --by=id --path="$DOCROOT" --allow-root >/dev/null 2>&1 || true
elif [[ "$($WP_BIN post get "$post_id" --field=post_status --path="$DOCROOT" --allow-root 2>/dev/null)" == draft ]]; then
  $WP_BIN post update "$post_id" --post_status=publish --path="$DOCROOT" --allow-root >/dev/null 2>&1 && echo "article_published:{slug}"
elif [[ "{refresh}" == 1 ]]; then
  $WP_BIN post update "$post_id" --post_content='{escaped_content}' --path="$DOCROOT" --allow-root >/dev/null 2>&1 && echo "article_refreshed:{slug}"
else
  echo "article_exists:{slug}"
fi
# Kategori diterapkan juga ke artikel lama yang terlanjur masuk Uncategorized.
[[ -n "{cat_id}" && -n "$post_id" ]] && $WP_BIN post term set "$post_id" category {cat_id} --by=id --path="$DOCROOT" --allow-root >/dev/null 2>&1 || true'''
        output, rc = wp_remote(cmd)
        if 'article_duplicate_deleted' in output:
            log(f'Duplikat dihapus: {slug}-2')
        if 'article_created' in output or 'article_published' in output:
            articles_done += 1
            log(f'Artikel terbit: {slug}')
    
    log(f'Summary: {pages_done} pages, {articles_done} articles published')
    return True

def load_saved(path):
    """Konten hasil generate sebelumnya, atau None kalau belum ada/rusak."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, list) and data else None

def main():
    if not MANIFEST or not MANIFEST.is_file():
        log('ERROR: Manifest file required')
        sys.exit(2)
    
    domain = MANIFEST.stem
    log(f'AI content generation started for: {domain}')
    
    # Read manifest
    cfg = read_manifest(MANIFEST)
    site_title = cfg.get('site_title', domain)
    da_user = cfg.get('da_user', '')
    ssh_port = cfg.get('ssh_port', '22')
    ssh_user = cfg.get('ssh_user', 'root')
    target_host = cfg.get('target_host', '')
    num_articles = int(cfg.get('num_articles', '5'))
    article_category = cfg.get('article_category', 'Blog')
    # Artikel dikelompokkan mengikuti layanan klien; berapa artikel per layanan
    # bisa diatur lewat manifest.
    per_kategori = max(1, int(cfg.get('articles_per_category', '2')))
    
    # Data klien (form isian, catatan, foto) ada di folder sync Google Drive.
    # Folder manifest hanya berisi <domain>.txt hasil generate, jadi kalau cuma
    # membaca itu, AI menulis konten generik tanpa data klien sama sekali.
    client_data = {}
    for folder in (MANIFEST.parent, ON_PROGRESS / domain):
        if folder.is_dir():
            for k, v in read_client_data(folder).items():
                client_data.setdefault(k, v)
    log(f'Client data files: {list(client_data.keys())}')
    # Isi lengkap FORM ISIAN + dokumen lain (company profile, konsep, susunan menu).
    # Tanpa ini AI hanya menerima nama & alamat dan menulis konten generik.
    # Dokumen (termasuk OCR PDF hasil scan, yang lambat) hanya dibaca kalau memang
    # perlu generate; apply ulang memakai konten tersimpan.
    need_ai = not (load_saved(GENERATED_DIR / f'{domain}-pages.json')
                   and load_saved(GENERATED_DIR / f'{domain}-articles.json'))
    docs = (collect_client_docs(ON_PROGRESS / domain) if need_ai
            else {'sources': [], 'unreadable': [], 'skipped': []})
    for name, text in docs['sources']:
        log(f'Dokumen klien: {name} ({len(text)} karakter)')
    if docs['unreadable']:
        log(f'Dokumen tidak terbaca (mis. PDF hasil scan): {docs["unreadable"]}')
    if docs['skipped']:
        log(f'Dokumen dilewati (anggaran karakter habis): {docs["skipped"]}')
    client_info = format_for_prompt(client_data, docs)
    
    # Load AI model
    model = get_model('konten')
    if not model:
        log('ERROR: No AI model configured')
        sys.exit(2)
    log(f'Using model: {model.get("name", model.get("id"))}')
    
    # Generate pages
    # Apply ulang memakai konten yang sudah pernah dibuat: tanpa biaya AI lagi dan
    # tanpa artikel ganda (slug hasil AI berbeda setiap kali dibuat).
    pages = load_saved(GENERATED_DIR / f'{domain}-pages.json')
    if pages:
        log('Pakai konten halaman tersimpan')
    else:
        log('Generating pages...')
        pages = generate_pages(site_title, domain, client_info, model)
    if not pages:
        log('ERROR: Failed to generate pages')
        sys.exit(3)
    
    pages_file = GENERATED_DIR / f'{domain}-pages.json'
    pages_file.write_text(json.dumps(pages, indent=2, ensure_ascii=False))
    log(f'Pages saved: {pages_file}')
    
    # Generate articles
    articles = load_saved(GENERATED_DIR / f'{domain}-articles.json')
    pensiun = []
    kategori = kategori_layanan(domain, da_user, ssh_port, ssh_user, target_host)
    if not kategori:
        kategori = kategori_isi_contoh(domain)
        if kategori:
            log(f'Kategori dari layanan isi contoh: {", ".join(k["judul"] for k in kategori)}')
    berita = bool(kategori) and kategori[0].get('jenis') == 'berita'
    if berita:
        per_kategori = max(per_kategori, int(cfg.get('articles_per_rubrik', '3')))
    nama_kategori = {k['judul'] for k in kategori}
    if articles and kategori and not any(str(a.get('category')) in nama_kategori for a in articles):
        # Artikel tersimpan dibuat sebelum kategori situs ada (mis. semua "Blog"):
        # dibuat ulang per kategori, yang lama dipensiunkan bila belum disunting.
        log(f'Artikel tersimpan tidak cocok kategori situs ({", ".join(sorted(nama_kategori))}), dibuat ulang')
        pensiun = [(a.get('slug'), hashlib.md5(clean_html(a.get('content', '')).encode()).hexdigest(),
                    hashlib.md5((clean_html(a.get('content', '')) + '\n').encode()).hexdigest())
                   for a in articles if a.get('slug')]
        articles = None
        if not docs['sources']:
            docs = collect_client_docs(ON_PROGRESS / domain)
            client_info = format_for_prompt(client_data, docs)
    if articles and kategori:
        articles = [a for a in articles if str(a.get('title') or '').strip() and str(a.get('slug') or '').strip()]
        ada = {str(a.get('category')) for a in articles}
        kurang = [k for k in kategori if k['judul'] not in ada]
        for k in kurang:
            if not docs['sources']:
                docs = collect_client_docs(ON_PROGRESS / domain)
                client_info = format_for_prompt(client_data, docs)
            log(f'Kategori "{k["judul"]}" belum punya artikel lengkap, dibuatkan {per_kategori}')
            bagian = generate_articles(site_title, domain, client_info, model, per_kategori, k['judul'],
                                       k.get('keterangan', ''), 'berita' if berita else 'bisnis') or []
            for art in bagian:
                art['category'] = k['judul']
            articles.extend(bagian)
    if articles:
        log('Pakai konten artikel tersimpan (+ yang baru dilengkapi)')
    else:
        # Kategori mengikuti layanan (atau rubrik portal berita) yang benar-benar
        # ada di child theme situs. Kalau temanya tidak punya daftar layanan
        # (paket lain), kembali ke satu kategori seperti sebelumnya.
        if kategori:
            log(f'Kategori dari layanan situs: {", ".join(k["judul"] for k in kategori)}')
            articles = []
            for layanan in kategori:
                nama = layanan['judul']
                log(f'Generating {per_kategori} artikel untuk kategori "{nama}"...')
                bagian = generate_articles(site_title, domain, client_info, model,
                                           per_kategori, nama, layanan.get('keterangan', ''),
                                           'berita' if berita else 'bisnis') or []
                for art in bagian:
                    # Kategori dari AI kadang meleset; yang dipakai yang diminta.
                    art['category'] = nama
                articles.extend(bagian)
        else:
            log('Tema tanpa daftar layanan, memakai satu kategori')
            articles = generate_articles(site_title, domain, client_info, model,
                                         num_articles, article_category)
    articles_file = GENERATED_DIR / f'{domain}-articles.json'
    if articles:
        articles_file.write_text(json.dumps(articles, indent=2, ensure_ascii=False))
        log(f'Articles saved: {articles_file}')
    else:
        # Halaman tetap diterbitkan: dulu exit di sini membuat halaman yang sudah jadi
        # ikut tidak terpasang (sobirin-advokat.com tersisa placeholder semua).
        log('ERROR: Failed to generate articles, halaman tetap diterbitkan')
        articles = []
    
    # Biodata pemilik tidak boleh terbit, apa pun yang ditulis AI.
    jumlah_buang = 0
    for daftar in (pages, articles):
        for item in daftar if isinstance(daftar, list) else []:
            if isinstance(item, dict) and item.get('content'):
                item['content'], n = buang_data_pemilik(item['content'], client_data)
                jumlah_buang += n
    if jumlah_buang:
        log(f'Data pribadi pemilik dibuang dari konten: {jumlah_buang} paragraf/butir')
        pages_file.write_text(json.dumps(pages, indent=2, ensure_ascii=False))
        articles_file.write_text(json.dumps(articles, indent=2, ensure_ascii=False))

    # Catatan/penolakan AI ("... belum tersedia dalam data perusahaan") tidak boleh
    # terbit, dan klaim (sertifikasi, garansi, gratis, angka pengalaman/proyek) di
    # halaman hanya boleh kalau ada di data klien (jasakontraktorindo.com 2026-09-17).
    # Klaim hanya dicek saat data klien lengkap terbaca (konten baru dibuat);
    # artikel pengetahuan umum hanya disaring kalimat penolakannya.
    alasan_buang = []
    for daftar, data_cek in ((pages, client_info if need_ai else None), (articles, None)):
        for item in daftar if isinstance(daftar, list) else []:
            if isinstance(item, dict) and item.get('content') and item.get('slug') != 'tagline':
                item['content'], alasan = buang_kalimat_meragukan(item['content'], data_cek)
                alasan_buang += [f"{item.get('slug')}:{a}" for a in alasan]
    if alasan_buang:
        log(f'Kalimat meragukan dibuang: {len(alasan_buang)} ({", ".join(alasan_buang[:8])})')
        pages_file.write_text(json.dumps(pages, indent=2, ensure_ascii=False))
        articles_file.write_text(json.dumps(articles, indent=2, ensure_ascii=False))

    # Dry-run: stop here
    if MODE == 'dry-run':
        log('DRY-RUN complete. Content generated but not published.')
        print(json.dumps({
            'status': 'dry_run',
            'domain': domain,
            'pages_file': str(pages_file),
            'articles_file': str(articles_file),
            'pages_count': len(pages),
            'articles_count': len(articles)
        }))
        sys.exit(0)
    
    if MODE != 'apply':
        log(f'ERROR: invalid INSTALL_MODE={MODE}')
        sys.exit(2)
    
    # Apply: publish content
    log('Publishing content to remote...')
    # Manifest `tanpa_halaman=galeri,layanan` (yukpergimancing.com 2026-09-17): halaman yang sengaja
    # dihapus tidak dibuat ulang oleh generator.
    tanpa = {x.strip().lower() for x in cfg.get('tanpa_halaman', '').split(',') if x.strip()}
    slug_wp = {'home': 'beranda', 'profile': 'tentang-kami', 'gallery': 'galeri', 'contact': 'hubungi-kami'}
    if tanpa:
        pages = [pg for pg in pages if slug_wp.get(str(pg.get('slug', '')).lower()) not in tanpa]
    success = publish_content(domain, da_user, ssh_port, ssh_user, target_host, pages, articles, pensiun)
    
    if success:
        log('AI content generation completed')
        print(json.dumps({
            'status': 'applied',
            'domain': domain,
            'pages_count': len(pages),
            'articles_count': len(articles)
        }))
    else:
        log('ERROR: Failed to publish content')
        sys.exit(4)

if __name__ == '__main__':
    main()
