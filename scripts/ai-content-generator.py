#!/usr/bin/env python3
"""
AI Content Generator for Velocity WP Install
Reads manifest + client folder data, calls OpenAI-compatible API,
generates pages (Home, Profile, Gallery, Contact) + articles via WP-CLI
"""
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
from content_sanitize import clean_html

CONTENT_RULES = """Aturan konten (wajib):
- Gunakan HANYA fakta dari data klien di atas: nama usaha, produk/layanan, keunggulan, sejarah, visi-misi, area layanan, alamat, kontak. Jangan mengarang nomor telepon, alamat, harga, angka, penghargaan, atau klaim yang tidak ada di data. Kalau suatu info tidak ada, lewati tanpa menulis contoh palsu.
- Bagian bertanda DATA ADMINISTRASI PEMILIK hanya referensi internal: jangan tampilkan nama, email, atau WhatsApp pribadi pemilik. Kontak publik ambil dari "Kontak utk di web" atau kontak di dokumen perusahaan.
- Abaikan teks panduan bawaan template form (mis. "Silahkan ...", "Misal ...", "Contoh ...") dan contoh isian yang bukan milik klien.
- Kalau klien menjelaskan isi halaman, susunan menu, produk, atau layanan, ikuti dan jabarkan dari situ.
- Jangan menulis tag <img>, <figure>, <iframe>, <form>, URL gambar, atau kata "placeholder"/teks contoh. Foto, galeri, peta, dan tombol WhatsApp dipasang otomatis oleh sistem dari file klien."""

CREDENTIAL_RE = re.compile(r'^\s*(pass(word)?|user(name)?|sandi|login)\s*[:=]', re.I | re.M)

MANIFEST = Path(sys.argv[1]) if len(sys.argv) > 1 else None
ON_PROGRESS = Path('/home/On Progress')
MODE = os.environ.get('INSTALL_MODE', 'dry-run')
AI_CONFIG_DIR = Path('/var/lib/velocity/ai')
AI_MODELS = AI_CONFIG_DIR / 'models.json'
GENERATED_DIR = AI_CONFIG_DIR / 'generated'
LOG_FILE = Path('/var/lib/velocity/installer') / f'ai-{MANIFEST.stem}.log' if MANIFEST else Path('/dev/null')

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

def ai_call(system_prompt, user_prompt, model):
    """Call OpenAI-compatible API"""
    api_key = model.get('api_key', '')
    if not api_key:
        log('ERROR: API key not found in model config')
        return None
    
    endpoint = model.get('endpoint', 'https://api.openai.com/v1')
    model_name = model.get('model', '')
    temperature = model.get('temperature', 0.7)
    max_tokens = model.get('max_tokens', 4096)
    
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
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            content = result['choices'][0]['message']['content']
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
  {{"slug":"profile","title":"Profil","content":"<HTML company/organization profile: history, vision-mission, values, team if available. 300-500 words.>"}},
  {{"slug":"gallery","title":"Gallery","content":"<HTML short intro for the photo gallery describing the client's products or activities. 60-120 words. Photos are added automatically.>"}},
  {{"slug":"contact","title":"Kontak","content":"<HTML contact info: public phone/WhatsApp, email, address, opening hours only if present in client data, plus an invitation to get in touch. 80-200 words. No form, no map.>"}},
  {{"slug":"tagline","title":"Tagline","content":"<client's slogan if present, otherwise a plain-text summary of the business, max 8 words, no HTML>"}}
]

Use Indonesian language. Content should be professional HTML without images, forms, iframes, or placeholders."""
    
    response = ai_call(system_prompt, user_prompt, model)
    if not response:
        return None
    
    try:
        pages = json.loads(response)
        if not isinstance(pages, list):
            log('ERROR: AI response is not a JSON array')
            return None
        return pages
    except json.JSONDecodeError as e:
        log(f'ERROR: Failed to parse pages JSON: {e}')
        log(f'Response: {response[:500]}')
        return None

def generate_articles(site_title, domain, client_info, model, num_articles=5, category='Blog',
                      rincian_topik=''):
    """Artikel untuk satu kategori.

    `category` bukan sekadar label yang ditempel: semua artikel dalam satu
    panggilan harus benar-benar membahas layanan itu. Tanpa batasan ini, AI
    menulis artikel umum lalu kategorinya jadi tidak nyambung — mis. artikel
    interior masuk kategori "Bangun Baru".
    """
    system_prompt = "You are a professional Indonesian web content writer. Generate content in valid JSON format. All text content must be in Indonesian language. Output ONLY valid JSON array, no markdown fences, no extra text."
    
    client_info = client_info.strip() or '(tidak ada data klien)'
    topik = f'{category}. {rincian_topik}'.strip() if rincian_topik else category
    
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
    
    response = ai_call(system_prompt, user_prompt, model)
    if not response:
        return None
    
    try:
        articles = json.loads(response)
        if not isinstance(articles, list):
            log('ERROR: AI response is not a JSON array')
            return None
        return articles
    except json.JSONDecodeError as e:
        log(f'ERROR: Failed to parse articles JSON: {e}')
        log(f'Response: {response[:500]}')
        return None

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
        "global $shortcode_tags;"
        "foreach (array_keys($shortcode_tags) as $t) {"
        "  if (preg_match('/^([a-z0-9]+)_layanan$/', $t, $m) && function_exists($m[1] . '_data')) {"
        "    foreach ((array) call_user_func($m[1] . '_data', 'layanan') as $l) {"
        "      if (!empty($l['judul'])) {"
        "        $r = !empty($l['rincian']) ? implode(', ', (array) $l['rincian']) : '';"
        "        echo $l['judul'] . \"\\t\" . trim(($l['teks'] ?? '') . ' ' . $r) . \"\\n\";"
        "      }"
        "    } break;"
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
    layanan = []
    for baris in hasil.stdout.splitlines():
        if not baris.strip():
            continue
        judul, _, keterangan = baris.partition('\t')
        # Judul kategori dipakai apa adanya; batasi panjang agar wajar.
        layanan.append({'judul': judul.strip()[:60], 'keterangan': keterangan.strip()[:400]})
    return layanan[:6]


def publish_content(domain, da_user, ssh_port, ssh_user, target_host, pages, articles):
    """Publish generated content to WordPress via SSH + WP-CLI"""
    ssh_key = os.environ.get('WP_INSTALL_SSH_KEY_FILE', '')
    if not ssh_key or not Path(ssh_key).is_file():
        log('ERROR: SSH key not found')
        return False
    
    docroot = f'/home/{da_user}/domains/{domain}/public_html'
    
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
                ['ssh', '-i', ssh_key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=accept-new',
                 '-o', 'ConnectTimeout=15', '-p', str(ssh_port), f'{ssh_user}@{target_host}',
                 'bash', '-s'],
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
  # Ditimpa hanya kalau masih placeholder, mode finish, atau isinya belum berubah
  # sejak terakhir ditulis installer (md5 sama) — suntingan manusia tidak hilang.
  if [[ "$current" == '{placeholder}' || "{refresh}" == 1 ]] || {{ [[ -n "$stored" ]] && [[ "$stored" == "$(cur_md5 "$page_id")" ]]; }}; then
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
    model = get_default_model()
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
    if articles:
        log('Pakai konten artikel tersimpan')
    else:
        # Kategori mengikuti layanan yang benar-benar ada di child theme situs.
        # Kalau temanya tidak punya daftar layanan (paket lain), kembali ke
        # satu kategori seperti sebelumnya.
        kategori = kategori_layanan(domain, da_user, ssh_port, ssh_user, target_host)
        if kategori:
            log(f'Kategori dari layanan situs: {", ".join(k["judul"] for k in kategori)}')
            articles = []
            for layanan in kategori:
                nama = layanan['judul']
                log(f'Generating {per_kategori} artikel untuk kategori "{nama}"...')
                bagian = generate_articles(site_title, domain, client_info, model,
                                           per_kategori, nama, layanan.get('keterangan', '')) or []
                for art in bagian:
                    # Kategori dari AI kadang meleset; yang dipakai yang diminta.
                    art['category'] = nama
                articles.extend(bagian)
        else:
            log('Tema tanpa daftar layanan, memakai satu kategori')
            articles = generate_articles(site_title, domain, client_info, model,
                                         num_articles, article_category)
    if not articles:
        log('ERROR: Failed to generate articles')
        sys.exit(3)
    
    articles_file = GENERATED_DIR / f'{domain}-articles.json'
    articles_file.write_text(json.dumps(articles, indent=2, ensure_ascii=False))
    log(f'Articles saved: {articles_file}')
    
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
    success = publish_content(domain, da_user, ssh_port, ssh_user, target_host, pages, articles)
    
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
