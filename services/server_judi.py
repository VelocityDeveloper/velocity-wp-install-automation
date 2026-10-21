"""Analisis AI (dulu "Judi AI") — penilai temuan antivirus sesudah scan terjadwal (tab "Analisis AI" di /server/antivirus).

Semua temuan (malware, backdoor, admin siluman, SEO spam, judi) dinilai per berkas: berbahaya | positif_palsu | cek_manual
+ saran aksi, disimpan di ANALISIS dan ditampilkan di daftar scan — SARAN SAJA (keputusan user 19 Okt), eksekusi manual.
Temuan bukan judi yang isinya (sha256) sudah pernah dinilai tidak dikirim lagi. Aksi otomatis di bawah hanya untuk akun
dengan tanda judi:

Alur (dipanggil installer_status._scan_kerja sesudah scan terjadwal selesai, atau manual "Nilai ulang"):
1. Kandidat = temuan scan (bukan yang ditandai aman) dengan tanda judi/cloaking (TANDA_JUDI), dikelompokkan per akun.
   Akun di daftar putih dilewati.
2. Bukti per akun diambil agen antivirus aksi `bukti_judi` (judul + teks beranda versi browser & Googlebot,
   potongan berkas temuan, status suspend) lalu dinilai model murah lewat gateway 9router (ai.nglorok.com):
   jenis situs_judi | diretas | berita | aman + yakin + berkas yang seluruhnya berbahaya.
3. Keputusan diambil KODE, bukan AI (AI saja pernah menilai situs korban cloaking sebagai situs judi, yakin 98):
   - suspend akun DA: jenis situs_judi, yakin >= YAKIN_SUSPEND, ada tanda tingkat virus, TIDAK ada tanda cloaking/alih,
     beranda versi browser (pengunjung biasa) sendiri berisi judi, belum tersuspend, maks `maks_suspend` per malam.
   - karantina: jenis diretas → berkas yang dipilih AI ∩ temuan berkas tingkat virus, bukan berkas inti/penting
     (index.php, wp-config.php, .htaccess, wp-admin/, wp-includes/ — itu dibersihkan manual).
   - selain itu laporan saja.
4. Mode per server: `laporan` (rencana dicatat & dikirim Telegram, tanpa aksi) atau `otomatis`.
Keputusan di KEPUTUSAN (jsonl); unsuspend/suspend manual dari dashboard ikut dicatat di sana.
"""
import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

DIR = Path('/var/lib/velocity/server-judi')
SETELAN = DIR / 'setelan.json'  # {model, server: {host: {aktif, mode, daftar_putih, maks_suspend}}}
KEPUTUSAN = DIR / 'keputusan.jsonl'
KEPUTUSAN_ARSIP = DIR / 'keputusan-arsip.jsonl'  # riwayat yang dibersihkan dari tab (jejak suspend tetap ada)
ANALISIS = DIR / 'analisis.json'  # {host: {path: {sha256, putusan, yakin, saran, alasan, user, model, t}}}
PUTUSAN = ('berbahaya', 'positif_palsu', 'cek_manual')
SARAN = ('karantina', 'bersihkan_wp', 'bersihkan_db', 'tandai_aman', 'cek_manual')
MAKS_TEMUAN_AI = 15  # per akun per panggilan (batas teks bukti)
MODELS = Path('/var/lib/velocity/ai/models.json')
AI_USAGE = Path('/var/lib/velocity/ai/usage.jsonl')
MODEL_BAWAAN = 'cmc/z-ai/glm-5.3-flash'  # uji 16 Okt: satu-satunya yang membedakan diretas vs situs judi dengan benar
YAKIN_SUSPEND = 90
MAKS_SUSPEND = 3
TANDA_JUDI = re.compile(r'Judi|Cloaking|AlihGoogle')
TANDA_CLOAK = re.compile(r'Cloaking|AlihGoogle')
BERKAS_INTI = re.compile(r'/(?:index\.php|wp-config\.php|wp-settings\.php|wp-load\.php|wp-blog-header\.php|\.htaccess|\.user\.ini|php\.ini)$'
                         r'|/wp-(?:admin|includes)/')
OLEH = 'Analisis AI'

SISTEM = """Anda pemeriksa abuse hosting Indonesia. Nilai SATU akun hosting dari bukti di bawah.
Definisi jenis (pilih satu):
- situs_judi: situs ini SENDIRI dibuat untuk judi/slot/togel/kasino — pengunjung biasa (versi browser) melihat situs judi.
- diretas: situs sah (toko, sekolah, perusahaan, blog, dll.) yang disusupi: halaman/link judi disisipkan, cloaking
  (Googlebot diberi halaman judi sedangkan pengunjung biasa melihat situs asli), alih ke situs judi, berkas PHP penyusup.
- berita: situs berita/artikel yang MEMBERITAKAN judi (penangkapan, imbauan, opini) tanpa mempromosikan.
- aman: positif palsu lain.
Jika versi browser adalah situs normal tetapi versi Googlebot berisi judi → itu diretas, BUKAN situs_judi.
Temuan DB berupa tulisan (post publish) yang judulnya berita penangkapan/penindakan/imbauan judi, tanpa link judi
tersembunyi atau Googlebot berbeda → itu berita, BUKAN diretas.
"karantina": path berkas dari daftar "Berkas temuan" yang SELURUH isinya berbahaya (penyusup/halaman judi), bukan berkas sah
yang hanya disisipi satu baris. Kosongkan bila tidak yakin.
Akun tanpa temuan judi: jenis "diretas" bila ada malware nyata, selain itu "aman".
Nilai juga SETIAP baris di "Temuan scanner" (tanda tangan regex bisa positif palsu), field "temuan":
- putusan: berbahaya (malware/backdoor/webshell/spam sisipan/admin palsu nyata) | positif_palsu (kode/entri sah: plugin/tema
  resmi, pustaka, konten wajar yang kebetulan cocok pola) | cek_manual (bukti tidak cukup).
- saran: karantina (berkas seluruhnya jahat) | bersihkan_wp (admin siluman / plugin samaran) | bersihkan_db (entri database
  berisi spam/judi) | tandai_aman (positif palsu) | cek_manual (berkas sah yang disisipi kode jahat → bersihkan barisnya, atau bukti kurang).
Jawab HANYA JSON tanpa teks lain: {"jenis":"situs_judi|diretas|berita|aman","yakin":0-100,"alasan":"maks 200 karakter, bahasa Indonesia","karantina":["path", ...],
"temuan":[{"path":"path persis dari daftar","putusan":"berbahaya|positif_palsu|cek_manual","yakin":0-100,"saran":"karantina|bersihkan_wp|bersihkan_db|tandai_aman|cek_manual","alasan":"maks 150 karakter"}]}"""

_daftar_server = None
_ssh_key_file = None
_kirim_tg = None
_agen = None  # installer_status._antivirus_satu(srv, key, perintah, batas)
_kunci = threading.Lock()
_jalan = set()  # host yang sedang dinilai
_kemajuan = {}  # host → {ke, dari, user, mulai, oleh}; tanpa batas akun, bisa dihentikan dari dashboard
_henti = set()  # host yang diminta berhenti (dicek sebelum tiap akun)


def pasang(daftar_server, ssh_key_file, kirim_tg, agen):
    global _daftar_server, _ssh_key_file, _kirim_tg, _agen
    _daftar_server, _ssh_key_file, _kirim_tg, _agen = daftar_server, ssh_key_file, kirim_tg, agen


# ---------- Setelan & catatan ----------

def setelan_baca():
    try:
        return json.loads(SETELAN.read_text())
    except (OSError, ValueError):
        return {}


def setelan_server(host):
    s = (setelan_baca().get('server') or {}).get(host) or {}
    return {'aktif': bool(s.get('aktif')), 'mode': s.get('mode') if s.get('mode') in ('laporan', 'otomatis') else 'laporan',
            'daftar_putih': list(s.get('daftar_putih') or []), 'maks_suspend': int(s.get('maks_suspend') or MAKS_SUSPEND)}


def _tulis_atomik(path, data):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def _catat(baris):
    DIR.mkdir(parents=True, exist_ok=True)
    with _kunci, KEPUTUSAN.open('a') as f:
        f.write(json.dumps({'t': int(time.time()), **baris}, ensure_ascii=False, separators=(',', ':')) + '\n')


def setelan_atur(payload):
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    with _kunci:
        data = setelan_baca()
        s = data.setdefault('server', {}).setdefault(srv['host'], {})
        if 'aktif' in payload:
            s['aktif'] = bool(payload['aktif'])
        if payload.get('mode') in ('laporan', 'otomatis'):
            s['mode'] = payload['mode']
        if 'daftar_putih' in payload:
            s['daftar_putih'] = sorted({re.sub(r'[^a-z0-9_.-]', '', str(x).lower().strip())[:80]
                                        for x in (payload['daftar_putih'] or [])} - {''})[:500]
        if 'maks_suspend' in payload:
            s['maks_suspend'] = max(0, min(20, int(payload.get('maks_suspend') or 0)))
        _tulis_atomik(SETELAN, data)
    akhir = setelan_server(srv['host'])
    _catat({'jenis_catat': 'setelan', 'host': srv['host'], 'server': srv['name'], 'oleh': oleh,
            'alasan': f"{'aktif' if akhir['aktif'] else 'mati'}, mode {akhir['mode']}, daftar putih {len(akhir['daftar_putih'])}, "
                      f"maks suspend {akhir['maks_suspend']}"})
    return {'ok': True, 'setelan': akhir}, 200


_analisis_cache = [None, {}]


def analisis_baca():
    """Penilaian AI per temuan (cache mtime; dibaca daftar scan installer_status tiap permintaan)."""
    try:
        mtime = ANALISIS.stat().st_mtime
    except OSError:
        return {}
    if _analisis_cache[0] != mtime:
        try:
            _analisis_cache[:] = [mtime, json.loads(ANALISIS.read_text())]
        except (OSError, ValueError):
            return _analisis_cache[1]
    return _analisis_cache[1]


def _analisis_simpan(host, baru):
    if not baru:
        return
    with _kunci:
        try:  # baca langsung, bukan cache mtime (dua tulis beruntun bisa ber-mtime sama)
            data = json.loads(ANALISIS.read_text())
        except (OSError, ValueError):
            data = {}
        data[host] = {**(data.get(host) or {}), **baru}
        DIR.mkdir(parents=True, exist_ok=True)
        tmp = ANALISIS.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
        tmp.replace(ANALISIS)
        _analisis_cache[:] = [ANALISIS.stat().st_mtime, data]


def _per_temuan(ai, temuan, user, model):
    """Penilaian per temuan dari jawaban AI → {path: entri}; path di luar daftar temuan dibuang."""
    ada = {t['path']: t for t in temuan}
    out = {}
    for x in ai.get('temuan') or []:
        t = ada.get(x.get('path'))
        if not t or x.get('putusan') not in PUTUSAN:
            continue
        out[t['path']] = {'sha256': t.get('sha256'), 'putusan': x['putusan'], 'yakin': x['yakin'],
                          'saran': x.get('saran') if x.get('saran') in SARAN else 'cek_manual',
                          'alasan': x['alasan'], 'user': user, 'model': model, 't': int(time.time())}
    return out


def _per_sha(data):
    """sha256 → (path, entri) penilaian yang dipakai untuk semua berkas berisi sama di server mana pun:
    koreksi manual didahulukan, selain itu penilaian terbaru."""
    out = {}
    for m in data.values():
        for p, e in m.items():
            sha = e.get('sha256')
            if not sha or '#' in p:
                continue
            lama = out.get(sha)
            if not lama or (e.get('model') == 'manual', e.get('t') or 0) > (lama[1].get('model') == 'manual', lama[1].get('t') or 0):
                out[sha] = (p, e)
    return out


def _salin(sumber, t):
    p, e = sumber
    return {**e, 'user': t.get('user') or '-', 't': int(time.time()), 'salin_dari': p}


def daftar(host=None, batas=300):
    try:
        baris = KEPUTUSAN.read_text().splitlines()[-3000:]
    except OSError:
        baris = []
    out = []
    for b in reversed(baris):
        try:
            d = json.loads(b)
        except ValueError:
            continue
        if host and d.get('host') != host:
            continue
        out.append(d)
        if len(out) >= batas:
            break
    return out


def ringkasan(host):
    try:
        m = model_ai()
    except RuntimeError:
        m = {'id': '', 'model': setelan_baca().get('model') or MODEL_BAWAAN}
    return {'setelan': setelan_server(host), 'keputusan': daftar(host), 'model': m['model'], 'model_id': m['id'],
            'berjalan': host in _jalan, 'kemajuan': _kemajuan.get(host)}


# ---------- AI ----------

def model_ai():
    """Model dari halaman /ai ("Pemakaian per fungsi", models.json pemakaian['judi']; kosong = model default).
    Model tanpa endpoint (agen Claude) → MODEL_BAWAAN (atau setelan.json 'model' lama) lewat gateway 9router."""
    try:
        data = json.loads(MODELS.read_text())
    except (OSError, ValueError):
        data = {}
    models = data.get('models') or []
    mid = (data.get('pemakaian') or {}).get('judi')
    # "Ikut default" di /ai = model default (sama seperti fungsi lain)
    m = next((x for x in models if x.get('id') == mid), None) or next((x for x in models if x.get('is_default')), None)
    if m and m.get('endpoint') and m.get('api_key'):
        return {'id': m['id'], 'model': m.get('model') or m['id'], 'endpoint': m['endpoint'].rstrip('/'), 'api_key': m['api_key']}
    endpoint, kunci = _gateway()
    return {'id': '', 'model': setelan_baca().get('model') or MODEL_BAWAAN, 'endpoint': endpoint, 'api_key': kunci}


def _gateway():
    for m in (json.loads(MODELS.read_text()).get('models') or []):
        if 'ai.nglorok.com' in (m.get('endpoint') or '') and m.get('api_key'):
            return m['endpoint'].rstrip('/'), m['api_key']
    raise RuntimeError('gateway_9router_tidak_ada')


def _catat_token(model, usage, ok, host):
    try:
        with AI_USAGE.open('a') as f:
            f.write(json.dumps({'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'domain': host, 'run': '', 'mode': 'server',
                                'peran': 'judi', 'script': 'server_judi', 'model_id': model, 'model': model,
                                'prompt_tokens': int(usage.get('prompt_tokens') or 0),
                                'completion_tokens': int(usage.get('completion_tokens') or 0), 'ok': ok}) + '\n')
    except OSError:
        pass


def _urai_json(teks):
    teks = re.sub(r'^```(?:json)?\s*|\s*```$', '', (teks or '').strip())
    m = re.search(r'\{.*\}', teks, re.S)
    return json.loads(m.group(0) if m else teks)


def nilai_ai(bukti, ai_model, host):
    endpoint, kunci, model = ai_model['endpoint'], ai_model['api_key'], ai_model['model']
    badan = json.dumps({'model': model, 'temperature': 0, 'max_tokens': 3500,
                        'messages': [{'role': 'system', 'content': SISTEM}, {'role': 'user', 'content': bukti}]}).encode()
    galat = None
    for _ in range(2):
        req = urllib.request.Request(f'{endpoint}/chat/completions', data=badan, headers={
            'Content-Type': 'application/json', 'Authorization': f'Bearer {kunci}', 'User-Agent': 'Mozilla/5.0 VelocityDashboard/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.loads(r.read())
            _catat_token(model, j.get('usage') or {}, True, host)
            d = _urai_json(j['choices'][0]['message'].get('content'))
            jenis = d.get('jenis') if d.get('jenis') in ('situs_judi', 'diretas', 'berita', 'aman') else 'aman'
            per = [x for x in (d.get('temuan') or []) if isinstance(x, dict) and isinstance(x.get('path'), str)][:MAKS_TEMUAN_AI]
            return {'jenis': jenis, 'yakin': max(0, min(100, int(d.get('yakin') or 0))), 'alasan': str(d.get('alasan') or '')[:300],
                    'karantina': [str(p) for p in (d.get('karantina') or []) if isinstance(p, str)][:50],
                    'temuan': [{'path': x['path'], 'putusan': x.get('putusan'), 'saran': x.get('saran'),
                                'yakin': max(0, min(100, int(x.get('yakin') or 0))), 'alasan': str(x.get('alasan') or '')[:200]}
                               for x in per]}
        except (OSError, ValueError, KeyError, IndexError, TypeError) as e:
            galat = str(e)[:200]
    raise RuntimeError(f'ai_gagal: {galat}')


def susun_bukti(user, temuan, b):
    """Teks bukti satu akun untuk AI (dari agen bukti_judi + temuan scan)."""
    baris = [f"Akun hosting: {user}. Domain: {', '.join(b.get('domain') or []) or '-'}", '']
    for w in b.get('web') or []:
        baris.append(f"== Beranda {w['domain']} (HTTP {w.get('kode')}{', alih ke ' + w['alih'] if w.get('alih') else ''})")
        baris.append(f"Versi browser — judul: {w.get('judul') or '-'}\n{w.get('teks') or '(kosong)'}")
        if w.get('beda_bot'):
            baris.append(f"Versi Googlebot (BERBEDA) — judul: {w.get('judul_bot') or '-'}\n{w.get('teks_bot') or '(kosong)'}")
        else:
            baris.append('Versi Googlebot: sama dengan browser.')
        if w.get('alih_hp'):
            baris.append(f"HP dari Google dialihkan ke: {w['alih_hp']}")
        for x in w.get('sumber') or []:
            baris.append(f"Sumber kemungkinan (scan penuh wp-content): {x['path']} [{', '.join(x['tanda'])}] {x.get('bukti') or ''}")
        baris.append('')
    baris.append('== Temuan scanner (tanda tangan regex):')
    potong = {x['path']: x.get('potongan') or '' for x in b.get('berkas') or []}
    for t in temuan[:MAKS_TEMUAN_AI]:
        baris.append(f"- {t['path']} [{', '.join(x['id'] for x in t['tanda'])}] {'; '.join(x.get('bukti') or '' for x in t['tanda'])[:200]}")
        if potong.get(t['path']):
            baris.append(f"  isi: {potong[t['path']]}")
        if t.get('db'):  # entri DB: judul + jenis supaya AI bisa membedakan berita penindakan judi vs spam sisipan
            baris.append(f"  entri DB {t['db'].get('jenis') or ''}: judul \"{t['db'].get('judul') or ''}\"")
    if len(temuan) > MAKS_TEMUAN_AI:
        baris.append(f'… dan {len(temuan) - MAKS_TEMUAN_AI} temuan lain (tidak perlu dinilai)')
    return '\n'.join(baris)[:14000]


# ---------- Keputusan ----------

def putuskan(ai, temuan, b, st, sudah_suspend):
    """Rencana aksi dari penilaian AI + bukti skrip. AI saja tidak cukup untuk suspend."""
    ada_cloak = any(TANDA_CLOAK.search(x['id']) for t in temuan for x in t['tanda'])
    ada_virus = any(t.get('tingkat') == 'virus' for t in temuan)
    browser_judi = any(w.get('judi_browser', 0) >= 3 for w in b.get('web') or [])
    if ai['jenis'] == 'situs_judi':
        alasan_tolak = ([] if ai['yakin'] >= YAKIN_SUSPEND else [f"yakin {ai['yakin']} < {YAKIN_SUSPEND}"]) + \
                       ([] if ada_virus else ['tanpa tanda tingkat virus']) + \
                       (['ada tanda cloaking/alih (pola situs diretas)'] if ada_cloak else []) + \
                       ([] if browser_judi else ['beranda versi pengunjung bukan halaman judi']) + \
                       (['akun sudah tersuspend'] if b.get('suspended') else []) + \
                       ([f"batas {st['maks_suspend']} suspend per malam tercapai"] if sudah_suspend >= st['maks_suspend'] else [])
        if not alasan_tolak:
            return {'aksi': 'suspend', 'catatan': ''}
        return {'aksi': 'laporan', 'catatan': 'tidak disuspend: ' + '; '.join(alasan_tolak)}
    if ai['jenis'] == 'diretas':
        web = b.get('web') or []
        sumber = {x['path'] for w in web for x in w.get('sumber') or [] if x['path'].startswith('/home/')}
        boleh = {t['path'] for t in temuan if t.get('tingkat') == 'virus' and t['path'].startswith('/home/') and '#' not in t['path']} | sumber
        pilih = [p for p in ai['karantina'] if p in boleh and not BERKAS_INTI.search(p)]
        sisa = sorted(boleh - set(pilih))
        catatan = f"{len(sisa)} berkas lain perlu dibersihkan manual: {', '.join(_pendek(p) for p in sisa[:3])}" if sisa else ''
        if any('#' in t['path'] for t in temuan):
            if web and not any(w.get('judi_sembunyi') or w.get('judi_browser', 0) >= 3 or w.get('judi_bot', 0) >= 3 for w in web):
                catatan = (catatan + '; ' if catatan else '') + 'beranda sudah bersih saat dicek ulang'
            elif not sumber:
                catatan = (catatan + '; ' if catatan else '') + 'beranda masih berisi judi, sumber tak ketemu di wp-content — cek DB/opsi/widget'
        return {'aksi': 'karantina' if pilih else 'laporan', 'berkas': pilih[:20], 'catatan': catatan}
    return {'aksi': 'laporan', 'catatan': ''}


def _judi(t):
    return any(TANDA_JUDI.search(x['id']) for x in t.get('tanda') or [])


def _pendek(path):
    # /home/u/domains/d/public_html/wp-content/plugins/x/y.php → plugins/x/y.php
    return re.sub(r'^/home/[^/]+/domains/[^/]+/public_html/(?:wp-content/)?', '', path)


def _cocok_putih(user, domain, putih):
    return user.lower() in putih or any(d.lower() in putih or d.lower().removeprefix('www.') in putih for d in domain)


def proses(job, srv, oleh=OLEH):
    """Nilai temuan judi satu job scan. Aman dipanggil dari thread scan (galat ditelan & dicatat)."""
    host = srv['host']
    with _kunci:
        if host in _jalan:
            return {'error': 'sedang_berjalan'}
        _jalan.add(host)
    try:
        return _proses(job, srv, oleh)
    except Exception as e:  # jangan sampai mematikan thread scan
        _catat({'jenis_catat': 'galat', 'host': host, 'server': srv['name'], 'scan': job.get('id'), 'alasan': str(e)[:300]})
        return {'error': str(e)[:200]}
    finally:
        with _kunci:
            _jalan.discard(host)
            _henti.discard(host)
            _kemajuan.pop(host, None)


def _proses(job, srv, oleh):
    host = srv['host']
    st = setelan_server(host)
    ai_model = model_ai()
    model = ai_model['model']
    key = _ssh_key_file()
    dinilai = analisis_baca().get(host) or {}
    per_sha = _per_sha(analisis_baca())
    per_akun, salin, tunda, dikirim = {}, {}, [], set()
    for t in job.get('temuan') or []:
        if t.get('aman') or t.get('kini'):
            continue
        # Temuan bukan judi yang isinya sudah pernah dinilai tidak dikirim lagi (hemat token)
        lama = dinilai.get(t['path'])
        if not _judi(t) and lama and lama.get('sha256') == t.get('sha256'):
            continue
        # Isi sama (sha256) = putusan sama di semua akun & server: salin, atau tunggu hasil berkas kembarnya di run ini
        sha = t.get('sha256')
        if not _judi(t) and sha and '#' not in t['path']:
            if sha in per_sha:
                salin[t['path']] = _salin(per_sha[sha], t)
                continue
            if sha in dikirim:
                tunda.append(t)
                continue
            dikirim.add(sha)
        per_akun.setdefault(t.get('user') or '-', []).append(t)
    _analisis_simpan(host, salin)
    putih = {x.lower() for x in st['daftar_putih']}
    hasil = []
    suspend_malam = sum(1 for d in daftar(host, 500) if d.get('dijalankan') == 'suspend' and d.get('ok')
                        and time.strftime('%Y-%m-%d', time.localtime(d['t'])) == time.strftime('%Y-%m-%d'))
    # Akun judi dulu (dasar suspend/karantina otomatis), lalu akun dengan temuan virus terbanyak
    urut = sorted(per_akun.items(), key=lambda kv: (not any(_judi(t) for t in kv[1]),
                                                     -sum(t.get('tingkat') == 'virus' for t in kv[1]), kv[0]))
    dihentikan = None
    for i, (user, temuan) in enumerate(urut):
        if host in _henti:
            dihentikan = f'dihentikan di akun {i + 1}/{len(urut)}'
            break
        _kemajuan[host] = {'ke': i + 1, 'dari': len(urut), 'user': user, 'mulai': _kemajuan.get(host, {}).get('mulai') or int(time.time()), 'oleh': oleh}
        temuan = sorted(temuan, key=lambda t: (not _judi(t), t.get('tingkat') != 'virus'))
        ada_judi = any(_judi(t) for t in temuan)
        dasar = {'jenis_catat': 'nilai', 'host': host, 'server': srv['name'], 'scan': job.get('id'), 'user': user,
                 'mode': st['mode'], 'oleh': oleh, 'temuan': len(temuan), 'judi': ada_judi,
                 'tanda': sorted({x['id'] for t in temuan for x in t['tanda']})}
        b = _agen(srv, key, {'aksi': 'bukti_judi', 'user': user, 'paths': [t['path'] for t in temuan if '#' not in t['path']][:MAKS_TEMUAN_AI],
                             'domains': sorted({t['web']['domain'] for t in temuan if t.get('web')})}, 180)
        if not b.get('ok'):
            hasil.append({**dasar, 'aksi': 'laporan', 'catatan': f"bukti gagal diambil: {b.get('error')}"})
            continue
        dasar['domain'] = b.get('domain') or []
        if _cocok_putih(user, dasar['domain'], putih):
            hasil.append({**dasar, 'aksi': 'dilewati', 'catatan': 'daftar putih'})
            continue
        # Akun tersuspend tetap dinilai (saran per berkas); putuskan() menolak suspend ulang
        try:
            ai = nilai_ai(susun_bukti(user, temuan, b), ai_model, host)
        except RuntimeError as e:
            hasil.append({**dasar, 'aksi': 'laporan', 'catatan': str(e)})
            continue
        per = _per_temuan(ai, temuan, user, model)
        _analisis_simpan(host, per)
        # Temuan di luar 15 pertama / yang tak dijawab AI: dinilai bertahap, MAKS_TEMUAN_AI per panggilan
        sisa = [t for t in temuan if t['path'] not in per]
        while sisa and host not in _henti:
            batch, sisa = sisa[:MAKS_TEMUAN_AI], sisa[MAKS_TEMUAN_AI:]
            # Isi berkas batch ini harus diambil ulang: b hanya memuat 15 path pertama
            bb = _agen(srv, key, {'aksi': 'bukti_judi', 'user': user, 'hanya_berkas': True,
                                  'paths': [t['path'] for t in batch if '#' not in t['path']]}, 180)
            try:
                tambahan = _per_temuan(nilai_ai(susun_bukti(user, batch, {**b, 'berkas': bb.get('berkas') or []}), ai_model, host), batch, user, model)
            except RuntimeError:
                break
            per.update(tambahan)
            _analisis_simpan(host, tambahan)
        ai = {k: v for k, v in ai.items() if k != 'temuan'}
        # Akun tanpa judi: saran saja, tidak pernah ada aksi otomatis
        rencana = putuskan(ai, temuan, b, st, suspend_malam) if ada_judi else {'aksi': 'laporan', 'catatan': 'analisis saja (bukan judi)'}
        d = {**dasar, 'model': model, 'ai': ai, **rencana, 'suspended_awal': bool(b.get('suspended')),
             'analisis': {k: sum(1 for x in per.values() if x['putusan'] == k) for k in PUTUSAN}}
        if st['mode'] == 'otomatis' and rencana['aksi'] in ('suspend', 'karantina'):
            d.update(_jalankan(srv, key, user, rencana, ai, oleh))
            if d.get('dijalankan') == 'suspend' and d.get('ok'):
                suspend_malam += 1
        elif rencana['aksi'] == 'suspend':
            suspend_malam += 1  # mode laporan: hitung juga supaya rencana sama dengan yang akan terjadi
        hasil.append(d)
    if tunda:
        per_sha = _per_sha(analisis_baca())
        _analisis_simpan(host, {t['path']: _salin(per_sha[t['sha256']], t) for t in tunda if t['sha256'] in per_sha})
    for d in hasil:
        _catat(d)
    _catat({'jenis_catat': 'ringkas', 'host': host, 'server': srv['name'], 'scan': job.get('id'), 'mode': st['mode'], 'oleh': oleh,
            'akun': len(per_akun), 'alasan': ', '.join(f"{a} {sum(1 for d in hasil if d['aksi'] == a)}"
                                                         for a in ('suspend', 'karantina', 'laporan', 'dilewati')
                                                         if any(d['aksi'] == a for d in hasil)) + (f' · {dihentikan}' if dihentikan else '')
                                                         or 'tanpa temuan baru'})
    if hasil:
        _notif(srv, st, hasil)
    return {'ok': True, 'akun': len(per_akun), 'hasil': hasil}


def _jalankan(srv, key, user, rencana, ai, oleh):
    if rencana['aksi'] == 'suspend':
        r = _agen(srv, key, {'aksi': 'suspend', 'user': user}, 90)
        return {'dijalankan': 'suspend', 'ok': bool(r.get('ok')), 'error': r.get('error')}
    hasil = []
    for p in rencana['berkas']:
        r = _agen(srv, key, {'aksi': 'karantina', 'path': p, 'oleh': oleh, 'alasan': f"Judi AI: {ai['alasan']}"[:200]}, 60)
        hasil.append({'path': p, 'ok': bool(r.get('ok')), 'id': r.get('id'), 'error': r.get('error')})
    return {'dijalankan': 'karantina', 'ok': all(h['ok'] for h in hasil), 'hasil_karantina': hasil}


JENIS_LABEL = {'situs_judi': 'situs judi', 'diretas': 'diretas', 'berita': 'berita', 'aman': 'aman'}


def _notif(srv, st, hasil):
    if not _kirim_tg:
        return
    penting = [d for d in hasil if d.get('judi', True) and (d['aksi'] in ('suspend', 'karantina') or (d.get('ai') or {}).get('jenis') in ('situs_judi', 'diretas'))]
    jumlah = {k: sum((d.get('analisis') or {}).get(k, 0) for d in hasil) for k in PUTUSAN}
    if not penting and not jumlah['berbahaya']:
        return
    otomatis = st['mode'] == 'otomatis'
    baris = [f"🤖 <b>VelocityGuard · Analisis AI {html.escape(srv['name'])}</b> — judi mode {'OTOMATIS' if otomatis else 'laporan (tanpa aksi)'}",
             f"{sum(jumlah.values())} temuan dinilai: {jumlah['berbahaya']} berbahaya, {jumlah['positif_palsu']} positif palsu, "
             f"{jumlah['cek_manual']} cek manual — saran ada di daftar scan."]
    baris += ['', f"https://dash.velocity.ai.id/server/antivirus?s={urllib.parse.quote(srv['name'])}&tab=analisis-ai"]
    _kirim_tg('\n'.join(baris))


# ---------- API dashboard ----------

def nilai_mulai(payload, scan_detail):
    """Nilai ulang job scan tertentu (uji/manual). scan_detail = installer_status.antivirus_scan_detail."""
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    job = scan_detail(str(payload.get('scan') or ''))
    if job.get('error') or job.get('host') != srv['host'] or job.get('status') != 'selesai':
        return {'error': 'scan_tidak_ada'}, 400
    if srv['host'] in _jalan:
        return {'error': 'sedang_berjalan'}, 409
    threading.Thread(target=proses, args=(job, srv, oleh), daemon=True).start()
    return {'ok': True}, 200


def bersihkan_riwayat(payload):
    """Kosongkan riwayat penilaian satu server di tab: baris server itu dipindah ke KEPUTUSAN_ARSIP (tidak dihapus).
    Saran AI per berkas (ANALISIS) tidak ikut."""
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    if srv['host'] in _jalan:
        return {'error': 'sedang_berjalan'}, 409
    with _kunci:
        try:
            baris = KEPUTUSAN.read_text().splitlines()
        except OSError:
            baris = []
        pindah, sisa = [], []
        for b in baris:
            try:
                (pindah if json.loads(b).get('host') == srv['host'] else sisa).append(b)
            except ValueError:
                sisa.append(b)
        if pindah:
            with KEPUTUSAN_ARSIP.open('a') as f:
                f.write('\n'.join(pindah) + '\n')
            tmp = KEPUTUSAN.with_suffix('.tmp')
            tmp.write_text(''.join(b + '\n' for b in sisa))
            tmp.replace(KEPUTUSAN)
    _catat({'jenis_catat': 'setelan', 'host': srv['host'], 'server': srv['name'], 'oleh': oleh,
            'alasan': f'riwayat dibersihkan ({len(pindah)} baris dipindah ke arsip)'})
    return {'ok': True, 'dipindah': len(pindah)}, 200


def henti(payload):
    """Hentikan penilaian yang berjalan sesudah akun saat ini selesai; hasil akun yang sudah dinilai tetap tersimpan."""
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    host = payload.get('server')
    if host not in _jalan:
        return {'error': 'tidak_berjalan'}, 200
    _henti.add(host)
    srv = next((s for s in _daftar_server() if s['host'] == host), {'name': host})
    _catat({'jenis_catat': 'setelan', 'host': host, 'server': srv['name'], 'oleh': oleh, 'alasan': 'penilaian dihentikan'})
    return {'ok': True}, 200


def aksi(payload):
    """Suspend/unsuspend akun manual dari tab Judi AI (mis. membatalkan suspend otomatis)."""
    oleh = re.sub(r'[^\w .-]', '', str(payload.get('oleh') or ''))[:40].strip()
    if not oleh:
        return {'error': 'invalid_oleh'}, 400
    if payload.get('aksi') not in ('suspend', 'unsuspend'):
        return {'error': 'aksi_tidak_dikenal'}, 400
    srv = next((s for s in _daftar_server() if s['host'] == payload.get('server')), None)
    if not srv:
        return {'error': 'server_tidak_dikenal'}, 400
    user = str(payload.get('user') or '')
    if not re.fullmatch(r'[a-z0-9_][a-z0-9_.-]{0,31}', user):
        return {'error': 'akun_tidak_dikenal'}, 400
    r = _agen(srv, _ssh_key_file(), {'aksi': payload['aksi'], 'user': user}, 90)
    _catat({'jenis_catat': 'manual', 'host': srv['host'], 'server': srv['name'], 'user': user, 'oleh': oleh,
            'dijalankan': payload['aksi'], 'ok': bool(r.get('ok')), 'error': r.get('error'),
            'alasan': str(payload.get('alasan') or '')[:200]})
    return r, 200
