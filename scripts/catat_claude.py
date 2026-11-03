"""Catat pemakaian satu panggilan `claude -p --output-format json` yang tanpa transkrip
(--no-session-persistence) ke usage.jsonl. claude-pakai & token_alur membacanya untuk halaman Token Usage.
Tidak boleh menggagalkan pemanggil.

Baris masuk ke project lewat `domain`: slug project-NNN (Laravel) atau domain situs (WordPress). Bila pemanggil
tidak menyebutnya, dipakai domain proses installer (VELOCITY_DOMAIN / manifest <domain>.txt); di luar installer
jatuh ke nama skrip (pemakaian non-project)."""
import fcntl
import json
import os
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


class HitungUsage:
    """Jumlahkan usage dari event `assistant` stream-json, sebagai cadangan bila proses mati (timeout, limit)
    sebelum event `result` terkirim. Tanpa ini seluruh token run itu hilang dari catatan.
    Satu respons API bisa muncul di beberapa event (satu per blok isi), jadi dihitung sekali per message.id."""

    def __init__(self):
        self.per_id = {}

    def tambah(self, pesan):
        u = pesan.get('usage') if isinstance(pesan, dict) else None
        if isinstance(u, dict) and pesan.get('id'):
            self.per_id[pesan['id']] = (pesan.get('model') or '?', u)

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
