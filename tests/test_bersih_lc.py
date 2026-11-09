"""Ubah opsi serialisasi payload wp-locale-perf lewat php CLI. python3 tests/test_bersih_lc.py"""
import importlib.util
import re
from pathlib import Path

sp = importlib.util.spec_from_file_location('agen', Path(__file__).resolve().parent.parent / 'scripts' / 'server_antivirus_agent.py')
a = importlib.util.module_from_spec(sp)
sp.loader.exec_module(a)

cron = (b'a:3:{i:100;a:1:{s:25:"wp_locale_cache_reconcile";a:1:{s:1:"x";a:0:{}}}'
        b'i:200;a:2:{s:25:"wp_locale_cache_reconcile";a:1:{s:1:"y";a:0:{}}s:8:"wp_sah_x";a:1:{s:1:"z";a:0:{}}}s:7:"version";i:2;}')
assert a.php_lc(cron, 'cron') == b'a:2:{i:200;a:1:{s:8:"wp_sah_x";a:1:{s:1:"z";a:0:{}}}s:7:"version";i:2;}'

plug = b'a:3:{i:0;s:18:"wp-locale-perf/a.php";i:1;s:9:"sah/a.php";i:2;s:24:"widget-compat-helper/a.php";}'
plug = re.sub(rb's:\d+:"([^"]+)"', lambda m: b's:%d:"%s"' % (len(m.group(1)), m.group(1)), plug)
assert a.php_lc(plug, 'plugin') == b'a:1:{i:0;s:9:"sah/a.php";}'

role = b'a:2:{s:5:"admin";a:0:{}s:19:"internal_cache_sync";a:0:{}}'
assert a.php_lc(role, 'role') == b'a:1:{s:5:"admin";a:0:{}}'

# Nilai rusak ditolak, bukan ditulis balik; objek tidak ikut hidup
for rusak in (b'bukan serial', b'b:1;'):
    try:
        a.php_lc(rusak, 'cron')
    except RuntimeError:
        continue
    raise AssertionError(rusak)
assert a.php_lc(b'a:1:{s:1:"o";O:8:"stdClass":0:{}}', 'role') == b'a:1:{s:1:"o";O:8:"stdClass":0:{}}'

assert a.RE_LC_ACAK.match(b'_0123456789abcdef0123') and not a.RE_LC_ACAK.match(b'_site_transient_x')
assert a.RE_LC_UTAMA.match(b'_wp_user_scopes_crc32_b') and not a.RE_LC_UTAMA.match(b'wp_user_roles')
print('ok')
