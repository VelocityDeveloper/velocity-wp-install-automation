"""Self-check aturan keputusan Judi AI: python3 services/test_server_judi.py"""
import server_judi as J

st = {'maks_suspend': 3}
web_judi, web_normal = {'web': [{'judi_browser': 8}]}, {'web': [{'judi_browser': 0}]}


def T(ids, tk='virus', p='/home/u/domains/a.com/public_html/x.php'):
    return {'path': p, 'tingkat': tk, 'tanda': [{'id': i} for i in ids]}


def ai(j, y=98, k=()):
    return {'jenis': j, 'yakin': y, 'karantina': list(k)}


assert J.putuskan(ai('situs_judi'), [T(['VD.Web.HalamanJudi'])], web_judi, st, 0)['aksi'] == 'suspend'
# Situs korban cloaking tidak boleh disuspend walau AI menilai situs_judi
assert J.putuskan(ai('situs_judi'), [T(['VD.SEO.Cloaking'])], web_judi, st, 0)['aksi'] == 'laporan'
assert J.putuskan(ai('situs_judi'), [T(['VD.Web.HalamanJudi'])], web_normal, st, 0)['aksi'] == 'laporan'
assert J.putuskan(ai('situs_judi', 80), [T(['VD.Web.HalamanJudi'])], web_judi, st, 0)['aksi'] == 'laporan'
assert J.putuskan(ai('situs_judi'), [T(['VD.Web.Judi'], 'curiga')], web_judi, st, 0)['aksi'] == 'laporan'
assert J.putuskan(ai('situs_judi'), [T(['VD.Web.HalamanJudi'])], web_judi, st, 3)['aksi'] == 'laporan'
assert J.putuskan(ai('situs_judi'), [T(['VD.Web.HalamanJudi'])], {**web_judi, 'suspended': True}, st, 0)['aksi'] == 'laporan'
x, idx = '/home/u/domains/a.com/public_html/wp-content/uploads/x.php', '/home/u/domains/a.com/public_html/index.php'
r = J.putuskan(ai('diretas', 95, [x, idx, '/etc/passwd']), [T(['VD.SEO.Cloaking'], p=x), T(['VD.SEO.Cloaking'], p=idx)], web_normal, st, 0)
assert r['aksi'] == 'karantina' and r['berkas'] == [x] and '1 berkas' in r['catatan'], r
assert J.putuskan(ai('berita'), [T(['VD.Web.Judi'], 'curiga')], web_judi, st, 0)['aksi'] == 'laporan'
# Temuan beranda (#web): cek ulang bersih / sumber dari scan penuh wp-content / sumber tak ketemu
w = T(['VD.Web.HalamanJudi'], p='/home/u/domains/a.com/#web')
assert 'sudah bersih' in J.putuskan(ai('diretas', 90), [w], {'web': [{'judi_browser': 0, 'judi_sembunyi': False}]}, st, 0)['catatan']
plg = '/home/u/domains/a.com/public_html/wp-content/plugins/fik/fik.php'
kotor = {'web': [{'judi_browser': 0, 'judi_sembunyi': True, 'sumber': [{'path': plg, 'tanda': ['VD.WP.SuntikRemote']}]}]}
r = J.putuskan(ai('diretas', 90, [plg]), [w], kotor, st, 0)
assert r['aksi'] == 'karantina' and r['berkas'] == [plg], r
r = J.putuskan(ai('diretas', 90), [w], kotor, st, 0)
assert r['aksi'] == 'laporan' and 'plugins/fik/fik.php' in r['catatan'], r
r = J.putuskan(ai('diretas', 90), [w], {'web': [{'judi_sembunyi': True, 'sumber': []}]}, st, 0)
assert 'sumber tak ketemu' in r['catatan'], r
tdb = {**T(['VD.DB.Judi'], 'curiga', '/home/u/domains/a.com/public_html#db:wp_posts:9'), 'db': {'jenis': 'post publish', 'judul': 'Polisi Amankan Pelaku Judi Online'}}
assert 'judul "Polisi Amankan Pelaku Judi Online"' in J.susun_bukti('u', [tdb], {'web': []})
print('ok')
# Analisis AI per temuan: path di luar daftar & putusan asing dibuang, saran asing → cek_manual, sha ikut temuan
tm = [{**T(['VD.PHP.Eval'], p=x), 'sha256': 'abc'}]
per = J._per_temuan({'temuan': [{'path': x, 'putusan': 'berbahaya', 'saran': 'hapus', 'yakin': 90, 'alasan': 'eval'},
                                 {'path': '/etc/passwd', 'putusan': 'berbahaya', 'saran': 'karantina', 'yakin': 90, 'alasan': ''},
                                 {'path': x, 'putusan': 'entah', 'saran': 'karantina', 'yakin': 1, 'alasan': ''}]}, tm, 'u', 'm')
assert list(per) == [x] and per[x]['saran'] == 'cek_manual' and per[x]['sha256'] == 'abc', per
assert J._judi(T(['VD.SEO.Cloaking'])) and not J._judi(T(['VD.PHP.Eval']))
print('analisis OK')
# Isi sama (sha256) → satu putusan untuk semua berkas; koreksi manual menang atas penilaian AI yang lebih baru
data = {'h1': {'/home/a/x.php': {'sha256': 's1', 'putusan': 'berbahaya', 'model': 'medium', 't': 5},
               '/home/b/x.php': {'sha256': 's1', 'putusan': 'positif_palsu', 'model': 'manual', 't': 1},
               '/home/c/y.php': {'sha256': 's2', 'putusan': 'cek_manual', 'model': 'medium', 't': 1}},
        'h2': {'/home/d/y.php': {'sha256': 's2', 'putusan': 'positif_palsu', 'model': 'medium', 't': 9},
               '/home/e/#db:wp_posts:1': {'sha256': 's3', 'putusan': 'berbahaya', 't': 9}}}
ps = J._per_sha(data)
assert ps['s1'][1]['putusan'] == 'positif_palsu' and ps['s2'][0] == '/home/d/y.php' and 's3' not in ps, ps
c = J._salin(ps['s1'], {'user': 'f', 'path': '/home/f/x.php'})
assert c['user'] == 'f' and c['salin_dari'] == '/home/b/x.php' and c['putusan'] == 'positif_palsu', c
