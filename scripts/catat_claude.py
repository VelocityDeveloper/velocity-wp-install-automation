"""Catat pemakaian satu panggilan `claude -p --output-format json` yang tanpa transkrip
(--no-session-persistence) ke usage.jsonl. claude-pakai & token_alur membacanya untuk halaman Token Usage.
Tidak boleh menggagalkan pemanggil.

Baris masuk ke project lewat `domain`: slug project-NNN (Laravel) atau domain situs (WordPress). Bila pemanggil
tidak menyebutnya, dipakai domain proses installer (VELOCITY_DOMAIN / manifest <domain>.txt); di luar installer
jatuh ke nama skrip (pemakaian non-project)."""
import fcntl
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

AI_USAGE = '/var/lib/velocity/ai/usage.jsonl'


def domain_proses():
    """Sama dengan domain_proses() di ai-content-generator.py."""
    if os.environ.get('VELOCITY_DOMAIN'):
        return os.environ['VELOCITY_DOMAIN']
    for a in sys.argv[1:]:
        if a.endswith('.txt'):
            return Path(a).stem
    return ''


def _pendek(path, bagian=3):
    return '/'.join(str(path).rstrip('/').split('/')[-bagian:])


# Bash hanya dicatat nama programnya, plus subperintah untuk program di daftar putih (git status, php artisan test,
# alat wp, ...), supaya argumen yang bisa memuat sandi/token (curl -u, sshpass -p, echo, URL) tidak pernah tersimpan
# di usage.jsonl atau tampil di dashboard.
_ALAT_AGEN = {'ambil', 'audit', 'bahan', 'cek', 'mu-plugin', 'pasang', 'php', 'plugin', 'potong', 'potret', 'potret-ref',
              'ukuran', 'unggah', 'wp'}  # subperintah desain-claude-alat & permintaan-claude-alat
_SUBPERINTAH = {
    'git': {'status', 'diff', 'log', 'show', 'add', 'commit', 'clone', 'pull', 'push', 'fetch', 'checkout', 'branch',
            'switch', 'restore', 'stash', 'reset', 'rev-parse', 'ls-files', 'grep', 'blame', 'init', 'tag', 'merge', 'rebase'},
    'npm': {'run', 'install', 'ci', 'test', 'build', 'exec', 'ls', 'audit', 'update', 'uninstall', 'view'},
    'yarn': {'run', 'install', 'add', 'build', 'test', 'dev'}, 'pnpm': {'run', 'install', 'add', 'build', 'test', 'dev', 'exec'},
    'composer': {'install', 'require', 'update', 'dump-autoload', 'remove', 'show', 'run-script', 'test', 'validate'},
    'wp': {'plugin', 'theme', 'user', 'option', 'db', 'post', 'term', 'menu', 'media', 'cache', 'rewrite', 'eval',
           'eval-file', 'core', 'config', 'transient', 'search-replace', 'site', 'widget', 'sidebar', 'block', 'cron'},
    'systemctl': {'status', 'restart', 'start', 'stop', 'reload', 'is-active', 'enable', 'disable', 'list-units'},
    'docker': {'ps', 'logs', 'exec', 'run', 'build', 'compose', 'images', 'pull', 'restart', 'stop', 'start'},
    'desain-claude-alat': _ALAT_AGEN, 'permintaan-claude-alat': _ALAT_AGEN, 'alat': _ALAT_AGEN,
}
_RE_KATA = re.compile(r'^[a-z][a-z0-9._-]{0,23}$')  # nama program


def _program_bash(perintah):
    bagian = [s.strip() for s in re.split(r'&&|\|\||;|\|', perintah)]
    bagian = [s for s in bagian if s and not s.startswith(('cd ', 'export ', 'set ', 'source ', '. '))] or ['']
    kata = bagian[0].split()
    while kata and '=' in kata[0]:  # VAR=nilai di depan perintah
        kata.pop(0)
    nama = [k.rsplit('/', 1)[-1] for k in kata[:3]]
    if not nama or not _RE_KATA.match(nama[0]):
        return '?'
    if nama[0] == 'php' and len(nama) > 1 and nama[1] == 'artisan':
        nama = ['php artisan'] + nama[2:]
    program = nama[0]
    # php artisan: subperintah artisan berbentuk kata:kata (migrate, make:model); selain itu hanya daftar putih
    boleh = len(nama) > 1 and (nama[1] in _SUBPERINTAH.get(program, ()) or (
        program == 'php artisan' and re.fullmatch(r'[a-z]{2,20}(?::[a-z-]{2,20})?', nama[1])))
    if boleh:
        return f'{program} {nama[1]}'
    return program


def _nama_alat(blok):
    """(nama, ringkasan) satu pemanggilan alat. Bash dikelompokkan per program (lihat _program_bash)."""
    nama = str(blok.get('name') or '?')
    x = blok.get('input') if isinstance(blok.get('input'), dict) else {}
    if nama == 'Bash':
        return 'Bash: ' + _program_bash(str(x.get('command') or '')), ''
    if x.get('file_path') or x.get('notebook_path') or x.get('path'):
        return nama, _pendek(x.get('file_path') or x.get('notebook_path') or x.get('path'))
    if x.get('pattern'):
        return nama, str(x['pattern'])[:60]
    if nama.startswith('mcp__'):
        return nama.split('__', 2)[-1], ''
    return nama, ''


class HitungUsage:
    """Jumlahkan usage dari event `assistant` stream-json, sebagai cadangan bila proses mati (timeout, limit)
    sebelum event `result` terkirim. Tanpa ini seluruh token run itu hilang dari catatan.
    Satu respons API bisa muncul di beberapa event (satu per blok isi), jadi dihitung sekali per message.id."""

    def __init__(self):
        self.per_id = {}
        self.alat = {}  # id respons agen utama (urut giliran) -> {id tool_use: (nama alat, ringkasan)}
        self.sub = set()  # id respons subagen (Agent): tidak masuk urutan giliran agen utama

    def tambah(self, pesan, induk=None):
        """induk = parent_tool_use_id event (respons subagen)."""
        u = pesan.get('usage') if isinstance(pesan, dict) else None
        if isinstance(u, dict) and pesan.get('id'):
            i = pesan['id']
            self.per_id[i] = (pesan.get('model') or '?', u)
            if induk:
                self.sub.add(i)
                return
            daftar = self.alat.setdefault(i, {})
            for blok in pesan.get('content') or []:
                if isinstance(blok, dict) and blok.get('type') == 'tool_use':
                    daftar[blok.get('id') or len(daftar)] = _nama_alat(blok)

    def rincian(self, hasil=None):
        """Ke mana token satu run habis, untuk halaman /token/proyek (permintaan user 5 Nov 2026).

        Konteks giliran ke-i dibaca ulang di semua giliran sesudahnya, jadi tambahan konteks di giliran i (hasil alat
        giliran sebelumnya + teks agen) membebani run sebesar tambahan × sisa giliran. Jumlah beban semua bagian +
        output ≈ total token run. Giliran pertama = konteks awal (system prompt, daftar alat, instruksi).
        Output diambil dari modelUsage event result bila ada: output_tokens di event assistant bisa belum final.
        Alat yang dipanggil bersamaan dalam satu giliran berbagi beban giliran berikutnya sama rata."""
        try:
            giliran = []
            for i, daftar in self.alat.items():
                u = self.per_id[i][1]
                konteks = sum(int(u.get(k) or 0) for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
                giliran.append((konteks, int(u.get('output_tokens') or 0), list(daftar.values())))
            if not giliran:
                return {}
            n = len(giliran)
            alat, bagian = {}, []
            kosong = lambda: {'n': 0, 'tambah': 0, 'beban': 0}  # noqa: E731
            for no, (konteks, _, daftar) in enumerate(giliran):
                tambah = konteks if no == 0 else max(0, konteks - giliran[no - 1][0])
                beban = tambah * (n - no)
                sumber = [('Konteks awal', '')] if no == 0 else (giliran[no - 1][2] or [('Teks agen', '')])
                for nama, _ in sumber:
                    a = alat.setdefault(nama, kosong())
                    a['tambah'] += tambah // len(sumber)
                    a['beban'] += beban // len(sumber)
                if no:
                    bagian.append({'giliran': no + 1, 'alat': ', '.join(dict.fromkeys(x for x, _ in sumber)),
                                   'isi': ' · '.join(x for _, x in sumber if x)[:160], 'tambah': tambah, 'beban': beban})
            for _, _, daftar in giliran:
                for nama, _ in daftar:
                    alat.setdefault(nama, kosong())['n'] += 1
            if self.sub:
                a = alat.setdefault('Subagen', kosong())
                a['beban'] += sum(int(self.per_id[i][1].get(k) or 0) for i in self.sub for k in (
                    'input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens'))
                a['n'] = len(self.sub)
            bagian.sort(key=lambda b: -b['beban'])
            return {'giliran': n, 'konteks_awal': giliran[0][0], 'konteks_akhir': giliran[-1][0],
                    'output': sum(int(m.get('outputTokens') or 0) for m in ((hasil or {}).get('modelUsage') or {}).values())
                    or sum(o for _, o, _ in giliran),
                    'alat': dict(sorted(alat.items(), key=lambda kv: -kv[1]['beban'])), 'teratas': bagian[:5]}
        except Exception:
            return {}

    def isi_bila_terputus(self, hasil):
        """Hasil tanpa event `result`: isi modelUsage dari jumlahan & tandai parsial (biaya tidak diketahui = 0)."""
        if hasil.get('modelUsage') or not self.per_id:
            return hasil
        per_model = {}
        for model, u in self.per_id.values():
            m = per_model.setdefault(model, {'inputTokens': 0, 'cacheReadInputTokens': 0, 'cacheCreationInputTokens': 0,
                                             'outputTokens': 0, 'costUSD': 0})
            m['inputTokens'] += int(u.get('input_tokens') or 0)
            m['cacheReadInputTokens'] += int(u.get('cache_read_input_tokens') or 0)
            m['cacheCreationInputTokens'] += int(u.get('cache_creation_input_tokens') or 0)
            m['outputTokens'] += int(u.get('output_tokens') or 0)
        hasil['modelUsage'] = per_model
        hasil['parsial'] = True
        return hasil


def catat_claude(hasil, script, peran, berkas=AI_USAGE, domain=None, run=None, mode=None, tahap=None):
    """hasil = dict keluaran JSON claude; satu baris per model di modelUsage, satu sesi per skrip per hari."""
    try:
        hari = datetime.now().strftime('%Y-%m-%d')
        domain = domain or domain_proses() or script
        for model, x in (hasil.get('modelUsage') or {}).items():
            masuk, baca, buat = (int(x.get(k) or 0) for k in ('inputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens'))
            keluar = int(x.get('outputTokens') or 0)
            baris = {'ts': datetime.utcnow().isoformat(timespec='seconds') + '+00:00', 'domain': domain,
                     'run': run or os.environ.get('VELOCITY_RUN_ID') or f'{script}-{hari}',
                     'mode': mode or os.environ.get('INSTALL_MODE') or 'otomatis', 'peran': peran, 'script': script,
                     'sumber': 'claude', 'model_id': 'claude-code', 'model': model, 'permintaan': 1,
                     'prompt_tokens': masuk + baca + buat, 'completion_tokens': keluar, 'total_tokens': masuk + baca + buat + keluar,
                     'input_tokens': masuk, 'cache_read_tokens': baca, 'cache_creation_tokens': buat,
                     'biaya_usd': round(float(x.get('costUSD') or 0), 4), 'ok': not hasil.get('is_error')}
            if tahap:
                baris['tahap'] = tahap
            with open(berkas, 'a') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(json.dumps(baris, ensure_ascii=False) + '\n')
    except Exception:
        pass
