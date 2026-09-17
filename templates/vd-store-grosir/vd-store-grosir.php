<?php
/**
 * Plugin Name: VD Store Harga Grosir
 * Description: Harga bertingkat per jumlah beli (grosir) untuk produk VD Store — mis. beli 1 = 34.000, beli 3 = 31.500/pcs, beli 5 = 29.000/pcs, per ukuran. Dihitung otomatis di keranjang, kupon, dan checkout; tabel harga tampil di halaman produk.
 * Version: 1.0.1
 * Author: Velocity Developer
 * Requires Plugins: vd-store
 *
 * VD Store (1.4.12) tidak punya filter harga: keranjang, kupon, dan checkout semuanya
 * memanggil ProductData::resolve_price_with_options(), yang membaca meta _store_price dan
 * _store_advanced_options. Plugin ini mengganti nilai kedua meta itu HANYA selama request
 * REST wp-store/v1 (keranjang/kupon/checkout/ongkir) sesuai jumlah beli di keranjang, jadi
 * total order, kupon, dan riwayat order memakai harga yang sama. Di halaman lain harga
 * tetap harga beli 1.
 *
 * Data per produk: meta _vd_grosir (JSON)
 *   {"jumlah":[1,3,5], "harga":{"210":[34000,31500,29000], ...}, "per_warna":false}
 * Kunci harga = label pilihan harga (_store_advanced_options). Produk tanpa pilihan harga
 * memakai kunci "*". per_warna=true: jumlah dihitung per ukuran+warna ("bukan campur warna").
 */

defined('ABSPATH') || exit;

const VD_GROSIR_META = '_vd_grosir';

/** Data grosir produk yang valid, atau null. */
function vd_grosir_data($product_id)
{
    $raw = get_post_meta((int) $product_id, VD_GROSIR_META, true);
    $data = is_array($raw) ? $raw : json_decode((string) $raw, true);
    if (!is_array($data) || empty($data['jumlah']) || empty($data['harga']) || !is_array($data['harga'])) {
        return null;
    }
    $jumlah = array_values(array_map('intval', (array) $data['jumlah']));
    $harga = array();
    foreach ($data['harga'] as $label => $baris) {
        $baris = array_values(array_map('floatval', (array) $baris));
        if (count($baris) === count($jumlah)) {
            $harga[(string) $label] = $baris;
        }
    }
    if (!$harga) {
        return null;
    }
    return array('jumlah' => $jumlah, 'harga' => $harga, 'per_warna' => !empty($data['per_warna']));
}

/** Harga satuan untuk jumlah $qty. */
function vd_grosir_harga($baris, $jumlah, $qty)
{
    $harga = $baris[0];
    foreach ($jumlah as $i => $min) {
        if ($qty >= $min) {
            $harga = $baris[$i];
        }
    }
    return $harga;
}

/** Request REST VD Store yang menghitung harga keranjang (bukan daftar produk). */
function vd_grosir_konteks_aktif()
{
    static $aktif = null;
    if ($aktif !== null) {
        return $aktif;
    }
    if (!defined('REST_REQUEST') || !REST_REQUEST) {
        return false; // belum diketahui (sebelum dispatch REST) — jangan dicache
    }
    $rute = '';
    if (!empty($GLOBALS['wp']->query_vars['rest_route'])) {
        $rute = (string) $GLOBALS['wp']->query_vars['rest_route'];
    } elseif (isset($_SERVER['REQUEST_URI'])) {
        $path = (string) wp_parse_url((string) wp_unslash($_SERVER['REQUEST_URI']), PHP_URL_PATH);
        $awal = rest_get_url_prefix();
        $pos = strpos($path, '/' . $awal . '/');
        $rute = $pos !== false ? substr($path, $pos + strlen($awal) + 1) : '';
    }
    $aktif = (bool) preg_match('#^/wp-store/v1/(cart|checkout|coupons|shipping|rajaongkir|direct)#', $rute);
    return $aktif;
}

/** Baris keranjang yang sedang dihitung: isi body request (checkout/kupon) atau keranjang tersimpan. */
function vd_grosir_baris_keranjang()
{
    static $body = false;
    if ($body === false) {
        $body = json_decode((string) file_get_contents('php://input'), true);
    }
    if (is_array($body) && !empty($body['items']) && is_array($body['items'])) {
        return $body['items'];
    }
    if (!class_exists('\WpStore\Domain\Cart\CartService')) {
        return array();
    }
    $service = new \WpStore\Domain\Cart\CartService();
    return (array) $service->get_raw_items();
}

/** Jumlah beli per [kunci harga] untuk satu produk (per_warna: jumlah terkecil antar-warna). */
function vd_grosir_jumlah_produk($product_id, $grosir)
{
    $nama_harga = (string) get_post_meta((int) $product_id, '_store_option2_name', true);
    $nama_warna = (string) get_post_meta((int) $product_id, '_store_option_name', true);
    $per_label = array();
    foreach (vd_grosir_baris_keranjang() as $row) {
        $pid = (int) ($row['id'] ?? ($row['product_id'] ?? 0));
        if ($pid !== (int) $product_id) {
            continue;
        }
        $opts = $row['opts'] ?? ($row['options'] ?? array());
        $opts = is_array($opts) ? $opts : array();
        $label = ($nama_harga !== '' && isset($opts[$nama_harga])) ? (string) $opts[$nama_harga] : '*';
        $warna = ($nama_warna !== '' && isset($opts[$nama_warna])) ? (string) $opts[$nama_warna] : '';
        $per_label[$label][$warna] = ($per_label[$label][$warna] ?? 0) + max(0, (int) ($row['qty'] ?? 0));
    }
    $hasil = array();
    foreach ($per_label as $label => $warna) {
        $hasil[$label] = $grosir['per_warna'] ? min($warna) : array_sum($warna);
    }
    return $hasil;
}

function vd_grosir_filter_meta($nilai, $object_id, $meta_key, $single)
{
    // get_metadata() mengambil elemen [0] dari nilai filter bila $single — nilai selalu dibungkus array.
    static $sibuk = false;
    if ($sibuk || !in_array($meta_key, array('_store_price', '_store_advanced_options'), true)
        || get_post_type($object_id) !== 'store_product' || !vd_grosir_konteks_aktif()) {
        return $nilai;
    }
    $sibuk = true;
    $grosir = vd_grosir_data($object_id);
    $sibuk = false;
    if (!$grosir) {
        return $nilai;
    }
    $sibuk = true;
    $jumlah = vd_grosir_jumlah_produk($object_id, $grosir);
    $sibuk = false;
    if ($meta_key === '_store_price') {
        if (!isset($grosir['harga']['*'])) {
            return $nilai;
        }
        return array(vd_grosir_harga($grosir['harga']['*'], $grosir['jumlah'], $jumlah['*'] ?? 1));
    }
    $sibuk = true;
    $opsi = get_post_meta((int) $object_id, '_store_advanced_options', true);
    $sibuk = false;
    if (!is_array($opsi)) {
        return $nilai;
    }
    foreach ($opsi as $i => $row) {
        $label = is_array($row) ? (string) ($row['label'] ?? '') : '';
        if ($label !== '' && isset($grosir['harga'][$label])) {
            $opsi[$i]['price'] = vd_grosir_harga($grosir['harga'][$label], $grosir['jumlah'], $jumlah[$label] ?? 1);
            unset($opsi[$i]['amount']);
        }
    }
    return array($opsi);
}
add_filter('get_post_metadata', 'vd_grosir_filter_meta', 10, 4);

// Tabel harga grosir di halaman produk.
add_action('wp_store_single_after_summary', function ($product_id) {
    $grosir = vd_grosir_data($product_id);
    if (!$grosir) {
        return;
    }
    $nama = (string) get_post_meta((int) $product_id, '_store_option2_name', true);
    $satuan = (string) get_post_meta((int) $product_id, '_vd_grosir_satuan', true) ?: 'pcs';
    $rp = static function ($n) {
        return 'Rp ' . number_format((float) $n, 0, ',', '.');
    };
    echo '<div class="vd-grosir"><h3 class="vd-grosir__judul">Harga Grosir</h3>';
    echo '<p class="vd-grosir__catatan">Harga per ' . esc_html($satuan) . ' otomatis turun sesuai jumlah beli'
        . ($grosir['per_warna'] ? ' (dihitung per ukuran &amp; warna, bukan campur)' : (count($grosir['harga']) > 1 ? ' (dihitung per ukuran, bukan campur ukuran)' : ''))
        . '.</p><div class="vd-grosir__gulir"><table class="vd-grosir__tabel"><thead><tr>';
    if (!isset($grosir['harga']['*']) || count($grosir['harga']) > 1) {
        echo '<th>' . esc_html($nama !== '' ? $nama : 'Pilihan') . '</th>';
    }
    foreach ($grosir['jumlah'] as $j) {
        echo '<th>Beli ' . ($j > 1 ? '≥ ' : '') . (int) $j . ' ' . esc_html($satuan) . '</th>';
    }
    echo '</tr></thead><tbody>';
    foreach ($grosir['harga'] as $label => $baris) {
        echo '<tr>';
        if ($label !== '*' || count($grosir['harga']) > 1) {
            echo '<th scope="row">' . esc_html($label) . '</th>';
        }
        foreach ($baris as $h) {
            echo '<td>' . esc_html($rp($h)) . '</td>';
        }
        echo '</tr>';
    }
    echo '</tbody></table></div></div>';
});

add_action('wp_enqueue_scripts', function () {
    if (!is_singular('store_product')) {
        return;
    }
    wp_register_style('vd-grosir', false, array(), '1.0.1');
    wp_enqueue_style('vd-grosir');
    wp_add_inline_style('vd-grosir', '.vd-grosir{box-sizing:border-box;width:100%;max-width:calc(100vw - 2.5rem);margin:1.5rem 0;padding:1rem 1.1rem;border:1px solid #e3e6ec;border-radius:12px;background:#f7f8fa}'
        . '.vd-grosir__judul{margin:0 0 .3rem;font-size:1.05rem}.vd-grosir__catatan{margin:0 0 .7rem;font-size:.85rem;opacity:.8}'
        . '.vd-grosir__gulir{overflow-x:auto}.vd-grosir__tabel{width:100%;border-collapse:collapse;font-size:.9rem;white-space:nowrap}'
        . '.vd-grosir__tabel th,.vd-grosir__tabel td{padding:.45rem .6rem;border-bottom:1px solid #e3e6ec;text-align:left}'
        . '.vd-grosir__tabel thead th{font-weight:700;background:#fff}');
});

// Kotak sunting di wp-admin → Produk.
add_action('add_meta_boxes_store_product', function () {
    add_meta_box('vd-grosir', 'Harga Grosir (per jumlah beli)', function ($post) {
        $g = vd_grosir_data($post->ID);
        $teks = '';
        if ($g) {
            $teks = 'jumlah=' . implode(',', $g['jumlah']) . "\n";
            foreach ($g['harga'] as $label => $baris) {
                $teks .= $label . '=' . implode(',', array_map(static function ($n) {
                    return (string) (0 + $n);
                }, $baris)) . "\n";
            }
        }
        wp_nonce_field('vd_grosir_simpan', 'vd_grosir_nonce');
        echo '<p>Baris pertama <code>jumlah=1,3,5</code>. Baris berikutnya <code>ukuran=harga beli 1,harga beli 3,harga beli 5</code>'
            . ' — ukuran sama persis dengan label di "Daftar Pilihan dan Harga". Produk tanpa pilihan ukuran: <code>*=19000,18000,17000</code>.'
            . ' Saat disimpan, harga beli 1 ikut mengisi Daftar Pilihan dan Harga Regular.</p>';
        echo '<textarea name="vd_grosir" rows="8" style="width:100%;font-family:monospace">' . esc_textarea($teks) . '</textarea>';
        echo '<p><label><input type="checkbox" name="vd_grosir_per_warna" value="1" ' . checked($g && $g['per_warna'], true, false)
            . '> Jumlah dihitung per warna (bukan campur warna)</label></p>';
        $satuan = (string) get_post_meta($post->ID, '_vd_grosir_satuan', true);
        echo '<p><label>Satuan <input type="text" name="vd_grosir_satuan" value="' . esc_attr($satuan ?: 'pcs') . '" style="width:8em"></label></p>';
    }, 'store_product', 'normal', 'default');
});

add_action('save_post_store_product', function ($post_id) {
    if (!isset($_POST['vd_grosir_nonce']) || !wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['vd_grosir_nonce'])), 'vd_grosir_simpan')
        || (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) || !current_user_can('edit_post', $post_id)) {
        return;
    }
    $baris = preg_split('/\r\n|\r|\n/', (string) wp_unslash($_POST['vd_grosir'] ?? ''));
    $jumlah = array();
    $harga = array();
    foreach ($baris as $b) {
        if (strpos($b, '=') === false) {
            continue;
        }
        list($k, $v) = array_map('trim', explode('=', $b, 2));
        $angka = array_map(static function ($x) {
            return (float) preg_replace('/[^0-9.]/', '', str_replace('.', '', trim($x)));
        }, explode(',', $v));
        if (strtolower($k) === 'jumlah') {
            $jumlah = array_map('intval', $angka);
        } elseif ($k !== '') {
            $harga[sanitize_text_field($k)] = $angka;
        }
    }
    if (!$jumlah || !$harga) {
        delete_post_meta($post_id, VD_GROSIR_META);
        return;
    }
    update_post_meta($post_id, VD_GROSIR_META, wp_json_encode(array(
        'jumlah' => $jumlah, 'harga' => $harga, 'per_warna' => !empty($_POST['vd_grosir_per_warna']),
    )));
    update_post_meta($post_id, '_vd_grosir_satuan', sanitize_text_field(wp_unslash($_POST['vd_grosir_satuan'] ?? 'pcs')));
    vd_grosir_sinkron($post_id);
}, 30);

/** Harga beli 1 → _store_price (termurah) & _store_advanced_options (Harga Tetap). */
function vd_grosir_sinkron($post_id)
{
    $g = vd_grosir_data($post_id);
    if (!$g) {
        return;
    }
    $satu = array_map(static function ($b) {
        return $b[0];
    }, $g['harga']);
    update_post_meta($post_id, '_store_price', min($satu));
    if (isset($g['harga']['*']) && count($g['harga']) === 1) {
        return;
    }
    $opsi = array();
    foreach ($g['harga'] as $label => $b) {
        $opsi[] = array('label' => (string) $label, 'price' => (float) $b[0]);
    }
    update_post_meta($post_id, '_store_advanced_options', $opsi);
    update_post_meta($post_id, '_store_option_price_mode', 'absolute');
}
