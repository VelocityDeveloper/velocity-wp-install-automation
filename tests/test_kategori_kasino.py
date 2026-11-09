"""Pilih kategori kosong bernama kasino. python3 tests/test_kategori_kasino.py"""
import importlib.util
from pathlib import Path

sp = importlib.util.spec_from_file_location('agen', Path(__file__).resolve().parent.parent / 'scripts' / 'server_antivirus_agent.py')
a = importlib.util.module_from_spec(sp)
sp.loader.exec_module(a)

baris = [[b'9', b'1xbet-brazil', b'1xbet Brazil'], [b'17', b'mostbet-az-90', b'Mostbet AZ'], [b'14', b'1win-brasil', b'1win Brasil'],
         [b'26', b'1winrussia', b'1winrussia'], [b'2', b'berita-daerah', b'Berita Daerah'], [b'3', b'olahraga', b'Olahraga'], [b'4', b'uncategorized', b'Uncategorized'],
         [b'x', b'1xbet', b'bukan id'], [b'5']]
assert [b[0] for b in a.kategori_kasino(baris)] == [b'9', b'17', b'14', b'26']
assert 'count = 0' in a.sql_kategori('wp_') and 'term_relationships' in a.sql_kategori('wp_')
print('ok')
