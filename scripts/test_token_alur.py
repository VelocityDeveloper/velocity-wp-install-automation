#!/usr/bin/env python3
"""Self-check token_alur & catat_claude: atribusi project/alur, jumlah cocok, usage event saat proses terputus."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catat_claude as C  # noqa: E402
import token_alur as T  # noqa: E402


def baris(**k):
    return json.dumps({'ts': '2026-11-02T01:00:00+00:00', 'ok': True, 'prompt_tokens': 0, 'completion_tokens': 0, **k})


with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    f = d / 'usage.jsonl'
    (d / 'project-001').mkdir()
    (d / 'project-001' / 'proyek.json').write_text('{"judul": "Aplikasi A"}')
    (d / 'project-001' / 'fitur.json').write_text('[{"id": "F02", "judul": "Login"}]')
    f.write_text('\n'.join([
        baris(domain='project-001', peran='laravel_brief', mode='susun', total_tokens=100, input_tokens=10, cache_read_tokens=50,
              cache_creation_tokens=20, completion_tokens=20, sumber='claude', biaya_usd=0.5, model='opus'),
        baris(domain='project-001', peran='laravel_agen', mode='agen', run='laravel-agen-project-001-F10', total_tokens=7, permintaan=3),
        baris(domain='project-001', peran='laravel_agen', mode='agen', run='laravel-agen-project-001-F02', total_tokens=5, ok=False),
        baris(domain='project-001', peran='laravel_kemiripan', mode='kemiripan_app', total_tokens=2),
        baris(domain='klien.com', peran='konten', model_id='m', prompt_tokens=30, completion_tokens=3),
        baris(domain='klien.com', peran='desain_claude', tahap='tema', total_tokens=4),
        baris(domain='klien.com', peran='claude_vision', tahap='cari_logo', total_tokens=1),
        baris(domain='office.velocity.ai.id', peran='office_x', total_tokens=1000),
        baris(domain='agent.velocity.ai.id', peran='agen_x', total_tokens=1000),
        baris(domain='45.126.43.18', peran='judi', total_tokens=1),
        baris(domain='', peran='foto', total_tokens=9),
        baris(domain='klien.com', peran='konten', total_tokens=1, ts='2026-10-01T01:00:00+00:00'),
        baris(domain='Klien.com baru', peran='baca_form', total_tokens=6),
        'bukan json',
    ]) + '\n')

    h = T.rekap(berkas=f, dasar_laravel=d)
    per = {p['id']: p for p in h['proyek']}
    assert set(per) == {'project-001', 'klien.com'}, per.keys()
    p = per['project-001']
    assert p['nama'] == 'Aplikasi A' and p['jenis'] == 'laravel' and p['total'] == 114
    assert [a['kunci'] for a in p['alur']] == ['susun', 'kemiripan_app', 'agen:F02', 'agen:F10']  # F02 sebelum F10
    a = {x['kunci']: x for x in p['alur']}
    assert a['agen:F02']['judul'] == 'Login' and a['agen:F02']['gagal'] == 1 and a['agen:F10']['panggilan'] == 3
    assert (a['susun']['input'], a['susun']['cache_baca'], a['susun']['cache_tulis'], a['susun']['output']) == (10, 50, 20, 20)
    w = per['klien.com']
    assert w['total'] == 33 + 4 + 1 + 1 + 6 and {x['kunci']: x for x in w['alur']}['baca_form']['total'] == 6
    k = {x['kunci']: x for x in w['alur']}
    assert k['konten']['total'] == 34 and k['konten']['input'] == 30  # gateway: prompt = input
    assert 'desain_claude:tema' in k and 'claude_vision:cari_logo' in k
    assert h['di_luar_project']['total'] == 2010 and h['total']['total'] == p['total'] + w['total']
    # jumlah alur = jumlah project
    assert all(sum(a['total'] for a in x['alur']) == x['total'] for x in h['proyek'])
    # saring tanggal (WIB)
    h2 = T.rekap(dari='2026-11-01', berkas=f, dasar_laravel=d)
    assert {x['id']: x for x in h2['proyek']}['klien.com']['total'] == 44
    assert T.rekap(sampai='2026-10-31', berkas=f, dasar_laravel=d)['total']['total'] == 1

    import folder_klien as F
    assert F.domain_folder('/home/On Progress/x.com/x.com baru') == 'x.com'
    assert F.domain_folder('/home/On Progress/x.co.id/redesign x.co.id') == 'x.co.id'
    assert F.domain_folder('/home/On Progress/x.com/baru') == 'x.com'
    assert F.domain_folder('/home/On Progress/x.com') == 'x.com'
    # catat_claude: domain dari pemanggil / env installer / jatuh ke nama skrip
    c = d / 'c.jsonl'
    H = {'modelUsage': {'m': {'inputTokens': 1, 'cacheReadInputTokens': 2, 'cacheCreationInputTokens': 3, 'outputTokens': 4, 'costUSD': 0.1}}}
    os.environ.pop('VELOCITY_DOMAIN', None)
    os.environ.pop('VELOCITY_RUN_ID', None)
    argv, sys.argv = sys.argv, ['x']
    C.catat_claude(H, 'skrip', 'peran', berkas=c)
    C.catat_claude(H, 'laravel-kemiripan', 'laravel_kemiripan', berkas=c, domain='project-001', run='r', mode='kemiripan_app')
    os.environ.update(VELOCITY_DOMAIN='klien.com', VELOCITY_RUN_ID='run-1', INSTALL_MODE='biasa')
    C.catat_claude(H, 'claude-vision', 'claude_vision', berkas=c, tahap='cari_logo')
    sys.argv = argv
    r = [json.loads(x) for x in c.read_text().splitlines()]
    assert r[0]['domain'] == 'skrip' and r[0]['total_tokens'] == 10 and 'tahap' not in r[0]
    assert (r[1]['domain'], r[1]['run'], r[1]['mode']) == ('project-001', 'r', 'kemiripan_app')
    assert (r[2]['domain'], r[2]['run'], r[2]['mode'], r[2]['tahap']) == ('klien.com', 'run-1', 'biasa', 'cari_logo')

    # HitungUsage: id sama sekali saja, result normal tidak ditimpa
    n = C.HitungUsage()
    u = {'input_tokens': 2, 'cache_read_input_tokens': 5, 'cache_creation_input_tokens': 3, 'output_tokens': 4}
    n.tambah({'id': 'a', 'model': 'opus', 'usage': u})
    n.tambah({'id': 'a', 'model': 'opus', 'usage': u})
    n.tambah({'id': 'b', 'model': 'opus', 'usage': u})
    h3 = n.isi_bila_terputus({})
    assert h3['parsial'] and h3['modelUsage']['opus']['outputTokens'] == 8 and h3['modelUsage']['opus']['cacheReadInputTokens'] == 10
    assert 'parsial' not in n.isi_bila_terputus({'modelUsage': {'x': {}}})
    assert C.HitungUsage().isi_bila_terputus({}) == {}
print('OK')
