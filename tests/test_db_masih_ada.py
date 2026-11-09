"""Temuan DB yang dibersihkan manual terbaca hilang; galat DB tidak terbaca bersih. python3 tests/test_db_masih_ada.py"""
import importlib.util
import tempfile
from pathlib import Path

sp = importlib.util.spec_from_file_location('agen', Path(__file__).resolve().parent.parent / 'scripts' / 'server_antivirus_agent.py')
a = importlib.util.module_from_spec(sp)
sp.loader.exec_module(a)

with tempfile.TemporaryDirectory() as d:
    Path(d, 'wp-config.php').write_text("x")
    a.wp_kredensial = lambda _: {'prefix': 'wp_'}
    a.periksa_db = lambda teks: [1] if b'judi' in teks else []
    tabel = {}

    def mysql(k, sql):
        if tabel.get('galat'):
            raise RuntimeError('db mati')
        for kunci, baris in tabel.items():
            if kunci in sql:
                return baris
        return []
    a.mysql_baris = mysql
    tidak_tahu = {'ada': True, 'tanda': None}
    hilang = {'ada': False}
    cek = lambda s: a.db_masih_ada(d + '#db:' + s, {})

    assert cek('wp_options:x') == hilang, 'opsi sudah hilang'
    tabel['option_name = 0x'] = [[b'bersih']]
    assert cek('wp_options:x') == hilang, 'isi opsi sudah bersih'
    tabel['option_name = 0x'] = [[b'judi']]
    assert cek('wp_options:x') == tidak_tahu, 'isi masih berbahaya'
    tabel.clear()
    assert cek('wp_posts:5') == hilang, 'pos dihapus/dibuang'
    tabel['`wp_posts` WHERE ID'] = [[b'judul', b'judi online']]
    assert cek('wp_posts:5') == tidak_tahu, 'pos masih berisi judi'
    tabel.clear()
    tabel['TRIGGERS'] = [[b'opsi', b'wp_user_scopes_crc32', b'x']]
    assert cek('wp_options:wp_user_scopes_crc32') == tidak_tahu, 'IOC masih ada'
    tabel.clear()
    assert cek('wp_options:wp_user_scopes_crc32') == hilang, 'IOC sudah dihapus'
    assert cek('wp_usermeta:1:app:x') == hilang, 'app password dicabut'
    assert cek('lain_options:x') == tidak_tahu, 'prefix beda: tidak bisa dinilai'
    tabel['galat'] = True
    for s in ('wp_options:x', 'wp_posts:5', 'wp_usermeta:1:app:x'):
        assert cek(s) == tidak_tahu, 'galat DB bukan berarti bersih'
    assert a.db_masih_ada('/tidak/ada#db:wp_options:x', {}) == hilang, 'WordPress sudah tidak ada'

with tempfile.TemporaryDirectory() as d:
    Path(d, 'wp-config.php').write_text("x")
    panggil = []

    def mati(k, sql):
        panggil.append(sql)
        raise RuntimeError('menggantung')
    a.mysql_baris = mati
    c = {}
    assert a.db_masih_ada(d + '#db:wp_options:x', c)['ada'] and a.db_masih_ada(d + '#db:wp_options:y', c)['ada']
    assert len(panggil) == 1, 'DB menggantung hanya ditunggu sekali per situs'
print('ok')
