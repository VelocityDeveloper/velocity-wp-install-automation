<?php
/**
 * Plugin Name: VD Store Harga Reseller
 * Description: Dua harga per produk VD Store — harga eceran untuk semua pembeli, harga reseller khusus akun berperan "Reseller". Reseller otomatis melihat & membayar harga reseller di katalog, halaman produk, keranjang, kupon, dan checkout.
 * Version: 1.1.0
 * Author: Velocity Developer
 * Requires Plugins: vd-store
 *
 * VD Store (1.4.16) tidak punya filter harga: tampilan dan perhitungan (keranjang, kupon, checkout)
 * membaca meta _store_price, _store_sale_price, dan _store_advanced_options. Untuk user berperan
 * reseller, plugin ini mengganti nilai meta itu di front-end & REST (bukan wp-admin, supaya
 * form edit produk tetap menyimpan harga eceran). Order tersimpan dengan harga reseller.
 *
 * Data per produk: meta _vd_reseller (JSON) {"*": 85000} atau {"1 kg": 25000, "5 kg": 110000}
 * Kunci = label pilihan harga (_store_advanced_options), nilainya harga akhir reseller; "*" = harga dasar.
 * Mode pilihan "absolute": harga label menggantikan harga pilihan. Mode "adjustment" (tambahan harga,
 * bawaan VD Store): "*" jadi harga dasar, label yang diisi diubah jadi selisih terhadap dasar itu,
 * label yang kosong tetap memakai tambahan harga eceran.
 * Akun reseller: wp-admin → Pengguna → ubah Peran jadi "Reseller".
 */

defined('ABSPATH') || exit;

const VD_RESELLER_META = '_vd_reseller';
const VD_RESELLER_ROLE = 'reseller';

add_action('init', function () {
    if (!get_role(VD_RESELLER_ROLE)) {
        add_role(VD_RESELLER_ROLE, 'Reseller', array('read' => true));
    }
});

/** Harga reseller produk {label: harga}, atau array kosong. */
function vd_reseller_data($product_id)
{
    $raw = get_post_meta((int) $product_id, VD_RESELLER_META, true);
    $data = is_array($raw) ? $raw : json_decode((string) $raw, true);
    $hasil = array();
    foreach ((array) $data as $label => $harga) {
        if (is_numeric($harga) && $harga > 0) {
            $hasil[(string) $label] = (float) $harga;
        }
    }
    return $hasil;
}

/** Mode harga pilihan VD Store: 'absolute' atau 'adjustment' (bawaan). */
function vd_reseller_mode($product_id)
{
    return get_post_meta((int) $product_id, '_store_option_price_mode', true) === 'absolute' ? 'absolute' : 'adjustment';
}

/** User yang sedang login berperan reseller (admin tidak termasuk). */
function vd_reseller_aktif()
{
    if (!is_user_logged_in()) {
        return false;
    }
    $user = wp_get_current_user();
    return in_array(VD_RESELLER_ROLE, (array) $user->roles, true);
}

function vd_reseller_filter_meta($nilai, $object_id, $meta_key, $single)
{
    // get_metadata() mengambil elemen [0] dari nilai filter bila $single — nilai selalu dibungkus array.
    static $sibuk = false;
    if ($sibuk || !in_array($meta_key, array('_store_price', '_store_sale_price', '_store_advanced_options'), true)
        || (is_admin() && !wp_doing_ajax()) || get_post_type($object_id) !== 'store_product' || !vd_reseller_aktif()) {
        return $nilai;
    }
    $sibuk = true;
    $harga = vd_reseller_data($object_id);
    $opsi = $meta_key === '_store_advanced_options' ? get_post_meta((int) $object_id, '_store_advanced_options', true) : null;
    $mode = vd_reseller_mode($object_id);
    $sibuk = false;
    if (!$harga) {
        return $nilai;
    }
    if ($meta_key === '_store_sale_price') {
        return array(''); // harga coret eceran tidak berlaku untuk reseller
    }
    $dasar = isset($harga['*']) ? $harga['*'] : min($harga);
    if ($meta_key === '_store_price') {
        return array($dasar);
    }
    if (!is_array($opsi)) {
        return $nilai;
    }
    foreach ($opsi as $i => $row) {
        $label = is_array($row) ? (string) ($row['label'] ?? '') : '';
        if ($label !== '' && isset($harga[$label]) && $label !== '*') {
            $opsi[$i]['price'] = $mode === 'absolute' ? $harga[$label] : max(0, $harga[$label] - $dasar);
            unset($opsi[$i]['amount']);
        }
    }
    return array($opsi);
}
add_filter('get_post_metadata', 'vd_reseller_filter_meta', 10, 4);

/** HTML tabel Harga Eceran vs Reseller (kosong bila produk tanpa harga reseller). */
function vd_reseller_tabel($product_id)
{
    $reseller = vd_reseller_data($product_id);
    if (!$reseller) {
        return '';
    }
    remove_filter('get_post_metadata', 'vd_reseller_filter_meta', 10);
    $opsi = get_post_meta((int) $product_id, '_store_advanced_options', true);
    $nama = (string) get_post_meta((int) $product_id, '_store_option2_name', true);
    $biasa = (float) get_post_meta((int) $product_id, '_store_price', true);
    $diskon = (float) get_post_meta((int) $product_id, '_store_sale_price', true);
    $dasar_eceran = ($diskon > 0 && $diskon < $biasa) ? $diskon : $biasa;
    $absolut = vd_reseller_mode($product_id) === 'absolute';
    $dasar_reseller = isset($reseller['*']) ? $reseller['*'] : min($reseller);
    $eceran = array();
    $tambahan = array();
    if (is_array($opsi) && $opsi) {
        foreach ($opsi as $row) {
            if (is_array($row) && isset($row['label'])) {
                $n = (float) ($row['price'] ?? ($row['amount'] ?? 0));
                $eceran[(string) $row['label']] = $absolut ? $n : $dasar_eceran + $n;
                $tambahan[(string) $row['label']] = $n;
            }
        }
    } else {
        $eceran['*'] = $dasar_eceran;
    }
    add_filter('get_post_metadata', 'vd_reseller_filter_meta', 10, 4);
    $rp = static function ($n) {
        return 'Rp ' . number_format((float) $n, 0, ',', '.');
    };
    $aktif = vd_reseller_aktif();
    ob_start();
    echo '<div class="vd-reseller"><h3 class="vd-reseller__judul">Harga Eceran &amp; Reseller</h3>';
    echo '<p class="vd-reseller__catatan">' . ($aktif
        ? 'Anda masuk sebagai <strong>Reseller</strong> — harga reseller otomatis dipakai di keranjang &amp; checkout.'
        : 'Harga eceran berlaku untuk semua pembeli. Harga reseller khusus akun reseller terdaftar — <a href="' . esc_url(wp_login_url(get_permalink($product_id))) . '">masuk sebagai reseller</a>.')
        . '</p><div class="vd-reseller__gulir"><table class="vd-reseller__tabel"><thead><tr>';
    $ada_label = !isset($eceran['*']);
    if ($ada_label) {
        echo '<th>' . esc_html($nama !== '' ? $nama : 'Pilihan') . '</th>';
    }
    echo '<th>Harga Eceran</th><th>Harga Reseller</th></tr></thead><tbody>';
    foreach ($eceran as $label => $h) {
        $r = $reseller[$label] ?? ($absolut ? ($reseller['*'] ?? 0) : $dasar_reseller + ($tambahan[$label] ?? 0));
        echo '<tr>' . ($ada_label ? '<th scope="row">' . esc_html($label) . '</th>' : '') . '<td>' . esc_html($rp($h)) . '</td><td>'
            . ($r <= 0 ? '-' : ($aktif ? '<strong>' . esc_html($rp($r)) . '</strong>' : '<span class="vd-reseller__kunci">Khusus reseller</span>'))
            . '</td></tr>';
    }
    echo '</tbody></table></div></div>';
    return ob_get_clean();
}

// Tampil sekali per halaman produk: tepat di bawah [wp_store_price] utama (tema toko), atau sebelum deskripsi (template bawaan VD Store).
function vd_reseller_cetak_sekali($product_id)
{
    static $sudah = false;
    if ($sudah || !is_singular('store_product') || (int) $product_id !== (int) get_queried_object_id()) {
        return '';
    }
    $sudah = true;
    return vd_reseller_tabel($product_id);
}
add_filter('do_shortcode_tag', function ($out, $tag, $attr) {
    if ($tag !== 'wp_store_price' || !in_the_loop()) {
        return $out;
    }
    $id = !empty($attr['id']) ? (int) $attr['id'] : get_the_ID();
    return $out . vd_reseller_cetak_sekali($id);
}, 10, 3);
add_action('wp_store_single_before_description', function ($product_id) {
    echo vd_reseller_cetak_sekali($product_id); // phpcs:ignore WordPress.Security.EscapeOutput -- di-escape di vd_reseller_tabel()
});
add_shortcode('vd_store_reseller_harga', function ($attr) {
    return vd_reseller_tabel(!empty($attr['id']) ? (int) $attr['id'] : get_the_ID());
});

add_action('wp_enqueue_scripts', function () {
    if (!is_singular('store_product')) {
        return;
    }
    wp_register_style('vd-reseller', false, array(), '1.1.0');
    wp_enqueue_style('vd-reseller');
    wp_add_inline_style('vd-reseller', '.vd-reseller{box-sizing:border-box;width:100%;max-width:calc(100vw - 2.5rem);margin:1.5rem 0;padding:1rem 1.1rem;border:1px solid #e3e6ec;border-radius:12px;background:#f7f8fa}'
        . '.vd-reseller__judul{margin:0 0 .3rem;font-size:1.05rem}.vd-reseller__catatan{margin:0 0 .7rem;font-size:.85rem;opacity:.85}'
        . '.vd-reseller__gulir{overflow-x:auto}.vd-reseller__tabel{width:100%;border-collapse:collapse;font-size:.9rem;white-space:nowrap}'
        . '.vd-reseller__tabel th,.vd-reseller__tabel td{padding:.45rem .6rem;border-bottom:1px solid #e3e6ec;text-align:left}'
        . '.vd-reseller__tabel thead th{font-weight:700;background:#fff}.vd-reseller__kunci{font-size:.8rem;opacity:.7}'
        . '@media (max-width:480px){.vd-reseller{padding:.8rem}.vd-reseller__tabel{white-space:normal;font-size:.85rem}.vd-reseller__tabel th,.vd-reseller__tabel td{padding:.4rem .3rem}}');
});

// Kotak sunting di wp-admin → Produk.
add_action('add_meta_boxes_store_product', function () {
    add_meta_box('vd-reseller', 'Harga Reseller', function ($post) {
        $harga = vd_reseller_data($post->ID);
        $opsi = get_post_meta($post->ID, '_store_advanced_options', true);
        $teks = '*=' . (isset($harga['*']) ? (0 + $harga['*']) : '') . "\n";
        if (is_array($opsi) && $opsi) {
            foreach ($opsi as $row) {
                $label = is_array($row) ? (string) ($row['label'] ?? '') : '';
                if ($label !== '') {
                    $teks .= $label . '=' . (isset($harga[$label]) ? (0 + $harga[$label]) : '') . "\n";
                }
            }
        }
        wp_nonce_field('vd_reseller_simpan', 'vd_reseller_nonce');
        echo '<p>Satu baris per pilihan harga: <code>label=harga reseller</code> (label sama persis dengan "Daftar Pilihan dan Harga"). '
            . '<code>*</code> = harga dasar reseller (produk tanpa pilihan cukup baris ini). Isi harga akhir yang dibayar reseller; label kosong = ikut harga dasar reseller + tambahan harga pilihan. Semua kosong = reseller membayar harga eceran.</p>';
        echo '<textarea name="vd_reseller" rows="6" style="width:100%;font-family:monospace">' . esc_textarea(rtrim($teks)) . '</textarea>';
    }, 'store_product', 'normal', 'default');
});

add_action('save_post_store_product', function ($post_id) {
    if (!isset($_POST['vd_reseller_nonce']) || !wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['vd_reseller_nonce'])), 'vd_reseller_simpan')
        || (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) || !current_user_can('edit_post', $post_id)) {
        return;
    }
    $harga = array();
    foreach (preg_split('/\r\n|\r|\n/', (string) wp_unslash($_POST['vd_reseller'] ?? '')) as $b) {
        if (strpos($b, '=') === false) {
            continue;
        }
        list($k, $v) = array_map('trim', explode('=', $b, 2));
        $v = (float) preg_replace('/[^0-9]/', '', $v);
        if ($k !== '' && $v > 0) {
            $harga[sanitize_text_field($k)] = $v;
        }
    }
    $harga ? update_post_meta($post_id, VD_RESELLER_META, wp_json_encode($harga)) : delete_post_meta($post_id, VD_RESELLER_META);
}, 30);
