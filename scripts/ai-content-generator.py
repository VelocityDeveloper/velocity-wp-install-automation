#!/usr/bin/env python3
"""
AI Content Generator for Velocity WP Install
Reads manifest + client folder data, calls OpenAI-compatible API,
generates pages (Home, Profile, Gallery, Contact) + articles via WP-CLI
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

MANIFEST = Path(sys.argv[1]) if len(sys.argv) > 1 else None
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
    """Read all .txt files in client folder except the manifest itself"""
    data = {}
    folder = Path(folder)
    for f in sorted(folder.glob('*.txt')):
        if f.name == f'{folder.name}.txt':
            continue
        key = f.stem
        data[key] = f.read_text(errors='replace').strip()
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

def generate_pages(site_title, domain, client_data, model):
    """Generate 4 pages: Home, Profile, Gallery, Contact"""
    system_prompt = "You are a professional Indonesian web content writer. Generate content in valid JSON format. All text content must be in Indonesian language. Output ONLY valid JSON array, no markdown fences, no extra text."
    
    client_info = '\n'.join(f'{k}: {v}' for k, v in client_data.items())
    
    user_prompt = f"""Generate WordPress page content for a website with these details:
- Site title: {site_title}
- Domain: {domain}
- Client data:
{client_info}

Generate 4 pages. Return JSON array:
[
  {{"slug":"home","title":"Home","content":"<HTML content for homepage with hero section, features, CTA. 300-500 words. Professional Indonesian.>"}},
  {{"slug":"profile","title":"Profil","content":"<HTML content about the company/organization profile. 300-500 words.>"}},
  {{"slug":"gallery","title":"Gallery","content":"<HTML content for gallery page with image placeholders. 200-300 words.>"}},
  {{"slug":"contact","title":"Kontak","content":"<HTML content for contact page with form, address, map placeholder. 200-300 words.>"}}
]

Use Indonesian language. Content should be professional HTML. Include image placeholders where needed."""
    
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

def generate_articles(site_title, domain, client_data, model, num_articles=5, category='Blog'):
    """Generate blog articles"""
    system_prompt = "You are a professional Indonesian web content writer. Generate content in valid JSON format. All text content must be in Indonesian language. Output ONLY valid JSON array, no markdown fences, no extra text."
    
    client_info = '\n'.join(f'{k}: {v}' for k, v in client_data.items())
    
    user_prompt = f"""Generate {num_articles} blog articles for a website with these details:
- Site title: {site_title}
- Domain: {domain}
- Category: {category}
- Client data:
{client_info}

Return JSON array:
[
  {{"title":"<article title>","slug":"<url-slug>","category":"{category}","content":"<article content in HTML, 400-600 words, professional Indonesian>","excerpt":"<short excerpt 20-30 words>"}}
]

Use Indonesian language. Topics should be relevant to the business/niche."""
    
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
    
    # Create pages
    pages_created = 0
    for page in pages:
        slug = page.get('slug', '')
        title = page.get('title', '')
        content = page.get('content', '')
        
        if not slug or not title:
            continue
        
        # Escape content for bash
        escaped_content = content.replace("'", "'\\''")
        
        cmd = f'''if $WP_BIN post list --post_type=page --post_status=any --slug='{slug}' --path="$DOCROOT" --allow-root --format=count 2>/dev/null | grep -q '^0$'; then
  echo "page_created:{slug}"
  $WP_BIN post create --post_type=page --post_status=draft --post_title='{title}' --post_name='{slug}' --post_content='{escaped_content}' --path="$DOCROOT" --allow-root 2>/dev/null
else
  echo "page_exists:{slug}"
fi'''
        output, rc = wp_remote(cmd)
        if 'page_created' in output:
            pages_created += 1
            log(f'Page created: {slug}')
    
    # Set homepage
    home_cmd = f'''if $WP_BIN post list --post_type=page --post_status=draft --slug=home --path="$DOCROOT" --allow-root --format=count 2>/dev/null | grep -q '1'; then
  $WP_BIN option set show_on_front 'page' --path="$DOCROOT" --allow-root 2>/dev/null
  home_id=$($WP_BIN post list --post_type=page --post_status=draft --slug=home --path="$DOCROOT" --allow-root --field=ID 2>/dev/null | head -1)
  $WP_BIN option set page_on_front "$home_id" --path="$DOCROOT" --allow-root 2>/dev/null && echo "homepage_set:$home_id"
fi'''
    wp_remote(home_cmd)
    
    # Create category
    category_name = articles[0].get('category', 'Blog') if articles else 'Blog'
    cat_escaped = category_name.replace("'", "'\\''")
    cat_cmd = f'''cat_id=$($WP_BIN term list category --path="$DOCROOT" --allow-root --fields=term_id,name 2>/dev/null | while IFS=',' read id name; do
  if [[ "$name" == "{cat_escaped}" ]]; then echo "$id"; break; fi
done | head -1)
if [[ -z "$cat_id" ]]; then
  cat_id=$($WP_BIN term create category '{cat_escaped}' --path="$DOCROOT" --allow-root 2>/dev/null | grep -o '[0-9]*$')
  echo "category_created:{category_name}:$cat_id"
else
  echo "category_exists:{category_name}:$cat_id"
fi'''
    cat_output, _ = wp_remote(cat_cmd)
    
    cat_id = ''
    if 'category_created' in cat_output or 'category_exists' in cat_output:
        match = re.search(r':(\d+)$', cat_output.strip())
        if match:
            cat_id = match.group(1)
    
    # Create articles
    articles_created = 0
    for art in articles:
        title = art.get('title', '')
        slug = art.get('slug', '')
        content = art.get('content', '')
        excerpt = art.get('excerpt', '')
        
        if not slug or not title:
            continue
        
        escaped_title = title.replace("'", "'\\''")
        escaped_content = content.replace("'", "'\\''")
        escaped_excerpt = excerpt.replace("'", "'\\''")
        
        cmd = f'''if $WP_BIN post list --post_type=post --post_status=any --slug='{slug}' --path="$DOCROOT" --allow-root --format=count 2>/dev/null | grep -q '^0$'; then
  echo "article_created:{slug}"
  post_id=$($WP_BIN post create --post_type=post --post_status=draft --post_title='{escaped_title}' --post_name='{slug}' --post_content='{escaped_content}' --post_excerpt='{escaped_excerpt}' --path="$DOCROOT" --allow-root 2>/dev/null --echo 2>/dev/null | grep -o '[0-9]*$')
  [[ -n "{cat_id}" ]] && $WP_BIN post term set "$post_id" category {cat_id} --path="$DOCROOT" --allow-root 2>/dev/null || true
else
  echo "article_exists:{slug}"
fi'''
        output, rc = wp_remote(cmd)
        if 'article_created' in output:
            articles_created += 1
            log(f'Article created: {slug}')
    
    log(f'Summary: {pages_created} pages, {articles_created} articles created')
    return True

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
    
    # Read client data
    client_folder = MANIFEST.parent
    client_data = read_client_data(client_folder)
    log(f'Client data files: {list(client_data.keys())}')
    
    # Load AI model
    model = get_default_model()
    if not model:
        log('ERROR: No AI model configured')
        sys.exit(2)
    log(f'Using model: {model.get("name", model.get("id"))}')
    
    # Generate pages
    log('Generating pages...')
    pages = generate_pages(site_title, domain, client_data, model)
    if not pages:
        log('ERROR: Failed to generate pages')
        sys.exit(3)
    
    pages_file = GENERATED_DIR / f'{domain}-pages.json'
    pages_file.write_text(json.dumps(pages, indent=2, ensure_ascii=False))
    log(f'Pages saved: {pages_file}')
    
    # Generate articles
    log('Generating articles...')
    articles = generate_articles(site_title, domain, client_data, model, num_articles, article_category)
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
