#!/usr/bin/env python3
"""Self-check server_lonjakan_agent: baseline normal tidak memicu, botnet /page/N memicu dengan template benar."""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server_lonjakan_agent as ag  # noqa: E402

d = tempfile.mkdtemp()
ag.LOG_DIR, ag.STATE = d, os.path.join(d, 'state', 'state.json')
LOG = os.path.join(d, 'contoh.com.log')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/141.0 Safari/537.36'


def tulis(baris):
    with open(LOG, 'a') as f:
        f.write(''.join(baris))


def baris(ip, url, ref='-', status=200):
    return f'{ip} - - [19/Oct/2026:14:00:00 +0700] "GET {url} HTTP/2" {status} 100 "{ref}" "{UA}"\n'


def putaran(n_baris):
    tulis(n_baris)
    with open(ag.STATE) as f:  # mundurkan waktu putaran lalu 300 dtk (tanpa menunggu)
        st = json.load(f)
    st['t'] -= 300
    with open(ag.STATE, 'w') as f:
        json.dump(st, f)
    return ag.periksa({'kali': 5, 'min_per_menit': 30})


tulis([baris('1.1.1.1', '/')])
assert ag.periksa({})['pertama']
for i in range(8):  # normal: ±10/mnt + aset statis yang tak dihitung
    h = putaran([baris(f'10.0.0.{j}', f'/2021/06/18/artikel-ke-{j}-panjang-sekali/') for j in range(50)]
                + [baris('10.0.0.1', '/wp-content/themes/x/style.css')] * 200)
    assert not h['lonjakan'], h
serangan = [baris(f'50.{j // 250}.{j % 250}.9', f'/2021/06/18/baru-bertugas-ipda-jhonson/page/{1000 + j}/',
                  ref=f'https://contoh.com/2021/06/18/baru-bertugas-ipda-jhonson/page/{1000 + j}/') for j in range(3000)]
h = putaran(serangan + [baris('10.0.0.2', '/')] * 50)
assert len(h['lonjakan']) == 1, h
l = h['lonjakan'][0]
t = l['template'][0]
assert l['domain'] == 'contoh.com' and l['kali'] >= 5, l
assert t['template'] == '/{n}/{n}/{n}/{slug}/page/{n}/' and t['hit'] == 3000 and t['ip_unik'] == 3000, t
assert t['referer_diri'] == 3000 and t['maks_per_ip'] == 1, t
assert ag.template('/x/page/12/tel:18000') == '/x/page/{n}/tel:{n}'
assert ag.template('/wp-json/oembed/1.0/embed?format=xml&url=https%3A') == '/wp-json/oembed/{n}.{n}/embed?format&url'
# baseline tak ikut melonjak → putaran berikut dengan serangan sama tetap terdeteksi
assert putaran(serangan)['lonjakan']
print('ok')
