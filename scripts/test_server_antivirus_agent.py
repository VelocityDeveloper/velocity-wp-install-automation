#!/usr/bin/env python3
"""Self-check tanda wp2shell (22 Okt 2026): potongan sampel karantina khankimi/bayarlis terdeteksi, kode sah tidak."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server_antivirus_agent as ag  # noqa: E402


def tanda(nama, isi):
    return {t['id'] for t in ag.periksa('/home/u/domains/d/public_html/' + nama, ag.ekstensi(os.path.basename(nama)), isi)}


KENA = [
    ('3PJcpMFsD8B.php', b'<?php\n$h= \t\tfunction ($c) {\r\n    EVAL \t\t($c);\r\n};', 'VD.PHP.EvalClosure'),
    ('x/index.php', b"<?php define('O0O0O0', 'O0O00O');$GLOBALS[O0O0O0] = explode('|H|Z|8', 'ini_set|H|Z|8eval');", 'VD.PHP.GlobalsExplode'),
    ('wp-content/index.php', b'<?php\n$O00OO_0_O_=urldecode("%6E1%7A%62");$O000OOO___=$O00OO_0_O_{38};', 'VD.PHP.VariabelO0'),
    ('p/c.php', b"<?php $op=array('mv'=>strrev('elif_dedaolpu_evom'),'rm'=>strrev('knilnu'));", 'VD.PHP.StrrevFungsi'),
    ('ngji/index.php', b"<?php $A=['7068705f756e616d65','6368646972','66696c655f6765745f636f6e74656e7473','6261736536345f6465636f6465','756e6c696e6b','6d6b646972'];", 'VD.Webshell.HexNama'),
    ('SvVZ6/index.php', b"<?php $d = openssl_decrypt($e, 'AES-128-ECB', $k, 0);\neval('?>' . $d);", 'VD.PHP.EvalDekripsi'),
    ('index.php__01bd3b5', b"<?php $params['referer'] = $r; $params['agent'] = $a; $c = @gzuncompress(base64_decode($c)); echo $c;", 'VD.SEO.PintuTDS'),
    ('wp-content/.htaccess', b'<FilesMatch ".*\\.(py|exe|phtml|php|PHP|Php|php5|suspected)$">\n Require all denied\n</FilesMatch>', 'VD.Htaccess.KunciShell'),
    ('.htaccess', b'<FilesMatch "^(about.php|index.php|lock360.php|admin.php)$">\n Allow from all\n</FilesMatch>', 'VD.Htaccess.KunciShell'),
    ('wp-content/plugins/wp2shell_fc6a5c1c/a.php', b"<?php\n/*\nPlugin Name: wp2shell\n*/ echo 'WP2SHELL::' . shell_exec($c);", 'VD.W2S.Penanda'),
    ('wp-content/mu-plugins/hostinger-cache.php', b"<?php define('FM_CACHE_IDX_MARKER', 'FM_CACHE_IDX_INJECT');", 'VD.W2S.Penanda'),
    ('wp-content/mu-plugins/wp-fastest-cache.php', b"<?php add_action( 'pre_user_query', function ( $q ) { global $wpdb; $q->query_where .= \" AND user_login NOT LIKE '\" . $wpdb->esc_like( 'wp_' ) . \"%'\"; } );", 'VD.WP.SembunyiAdmin'),
    ('p/update-checker.php', b"<?php $_w=str_split('file_put_contents',1);$_w=implode('',$_w);", 'VD.Webshell.StrSplit'),
    ('wp-content/mu-plugins/cloudflare-v2-23.php', b"<?php if (!function_exists('lf_sync_mu_plugin_copy')) { function lf_sync_mu_plugin_copy() {} }", 'VD.WP.PintuBelakangMU'),
    ('wp-content/mu-plugins/compat-loader.php', b"<?php $ids = $wpdb->get_col(\"SELECT u.ID FROM u WHERE m.meta_value LIKE '%administrator%'\"); wp_set_current_user($i); wp_set_auth_cookie($i, true);", 'VD.WP.LoginAdminAcak'),
    ('wp-content/mu-plugins/site-compat-layer.php', b"<?php $u = sanitize_user($_GET['user'], true); $p = wp_unslash($_GET['pass']); $id = wp_create_user($u, $p, $e);", 'VD.WP.BuatUserGet'),
    ('wp-content/mu-plugins/index.php', b'<?php $__map = [];' + b''.join(b'$__map["k%d"] = "x";' % i for i in range(25)) + b' eval($__code);', 'VD.PHP.PetaEval'),
]
for nama, isi, harap in KENA:
    assert harap in tanda(nama, isi), (nama, harap, tanda(nama, isi))

AMAN = [
    ('wp-content/plugins/x/a.php', b"<?php $f = function ($x) { return eval_helper($x); }; $GLOBALS['wp_filter'] = explode(',', $s);"),
    ('wp-content/plugins/x/b.php', b"<?php $hash = '7068705f'; $s = strrev($nama); $p = str_split($teks, 1);"),
    ('.htaccess', b'<FilesMatch "\\.(?i:php[0-9]?|phtml|phar)$">\n    Require all denied\n</FilesMatch>'),
    ('wp-content/plugins/x/c.php', b"<?php $like = $wpdb->esc_like( 'wp_' ) . '%'; $wpdb->query( \"DELETE FROM $wpdb->options WHERE option_name LIKE '$like'\" );"),
]
for nama, isi in AMAN:
    assert not tanda(nama, isi), (nama, tanda(nama, isi))
assert ag.ekstensi('index.php__01bd3b5') == 'php' and ag.ekstensi('.htaccess') == 'htaccess'
print('ok: %d sampel kena, %d sampel aman' % (len(KENA), len(AMAN)))
