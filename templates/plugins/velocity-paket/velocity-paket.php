<?php
/**
 * Plugin Name: Velocity Paket
 * Description: Daftar paket/produk berharga sebagai post type sendiri (harga, kelengkapan, kategori) dengan field Meta Box. Tampilkan dengan shortcode [velocity_paket] atau arsip /paket/.
 * Version: 1.0.1
 * Author: Velocity Developer
 * Requires Plugins: meta-box
 *
 * Dibuat 2026-09-24 untuk cahayaratupetir.com (paket penangkal petir dari FORM 5 pesan tambahan klien).
 * Data berstruktur = CPT + Meta Box (aturan user 2026-09-14), bukan kartu statis di isi halaman.
 */
if (!defined('ABSPATH')) { exit; }

add_action('init', function () {
    register_post_type('paket', array(
        'labels' => array(
            'name' => 'Paket', 'singular_name' => 'Paket', 'add_new' => 'Tambah Paket', 'add_new_item' => 'Tambah Paket Baru',
            'edit_item' => 'Ubah Paket', 'all_items' => 'Semua Paket', 'search_items' => 'Cari Paket', 'menu_name' => 'Paket',
        ),
        'public' => true, 'has_archive' => true, 'show_in_rest' => true, 'menu_icon' => 'dashicons-products',
        'rewrite' => array('slug' => 'paket'), 'supports' => array('title', 'editor', 'thumbnail', 'excerpt', 'page-attributes'),
    ));
    register_taxonomy('kategori-paket', 'paket', array(
        'labels' => array('name' => 'Kategori Paket', 'singular_name' => 'Kategori Paket'),
        'hierarchical' => true, 'show_in_rest' => true, 'show_admin_column' => true, 'rewrite' => array('slug' => 'kategori-paket'),
    ));
});

// Field lewat plugin Meta Box (metabox.io).
add_filter('rwmb_meta_boxes', function ($boxes) {
    $boxes[] = array(
        'title' => 'Detail Paket', 'post_types' => array('paket'), 'context' => 'normal',
        'fields' => array(
            array('id' => 'vp_harga', 'name' => 'Harga (Rp)', 'type' => 'number', 'min' => 0, 'step' => 1000),
            array('id' => 'vp_keterangan_harga', 'name' => 'Keterangan harga', 'type' => 'text', 'desc' => 'Mis. "+ pasang", "mulai dari".'),
            array('id' => 'vp_kelengkapan', 'name' => 'Kelengkapan', 'type' => 'text', 'clone' => true, 'sort_clone' => true, 'add_button' => '+ Tambah item'),
            array('id' => 'vp_tombol', 'name' => 'Tulisan tombol', 'type' => 'text', 'std' => 'Order via WhatsApp'),
        ),
    );
    return $boxes;
});

function velocity_paket_meta($id, $kunci) {
    // Meta Box menyimpan field clone sebagai satu nilai berisi array, jadi get_post_meta single.
    return function_exists('rwmb_meta') ? rwmb_meta($kunci, array(), $id) : get_post_meta($id, $kunci, true);
}

function velocity_paket_harga($id) {
    $harga = (int) velocity_paket_meta($id, 'vp_harga');
    if (!$harga) { return ''; }
    $ket = trim((string) velocity_paket_meta($id, 'vp_keterangan_harga'));
    return 'Rp ' . number_format($harga, 0, ',', '.') . ($ket ? ' <small>' . esc_html($ket) . '</small>' : '');
}

function velocity_paket_tombol($id) {
    // Nomor WA: opsi velocity-addons (tema klasik), lalu data situs tema FSE (velocity_situs).
    $wa = (string) get_option('nomor_whatsapp');
    if (!$wa) {
        $situs = (array) get_option('velocity_situs', array());
        $wa = (string) (!empty($situs['wa']) ? $situs['wa'] : (!empty($situs['telp']) ? $situs['telp'] : ''));
    }
    $wa = preg_replace('/\D/', '', $wa);
    if (strpos($wa, '0') === 0) { $wa = '62' . substr($wa, 1); }
    $label = trim((string) velocity_paket_meta($id, 'vp_tombol')) ?: 'Order via WhatsApp';
    $url = $wa ? 'https://wa.me/' . $wa . '?text=' . rawurlencode('Halo, saya ingin order ' . get_the_title($id) . '.')
        : (get_permalink(get_page_by_path('hubungi-kami')) ?: home_url('/'));
    return '<a class="vp-tombol" href="' . esc_url($url) . '" target="_blank" rel="noopener">' . esc_html($label) . '</a>';
}

function velocity_paket_kelengkapan($id) {
    $item = array_filter(array_map('trim', (array) velocity_paket_meta($id, 'vp_kelengkapan')));
    if (!$item) { return ''; }
    return '<ul class="vp-kelengkapan">' . implode('', array_map(function ($x) { return '<li>' . esc_html($x) . '</li>'; }, $item)) . '</ul>';
}

function velocity_paket_kartu($id) {
    $foto = get_the_post_thumbnail($id, 'medium_large', array('class' => 'vp-foto', 'loading' => 'lazy'));
    return '<article class="vp-kartu">'
        . ($foto ? '<a class="vp-foto-wrap" href="' . esc_url(get_permalink($id)) . '">' . $foto . '</a>' : '')
        . '<div class="vp-isi"><h3 class="vp-judul"><a href="' . esc_url(get_permalink($id)) . '">' . esc_html(get_the_title($id)) . '</a></h3>'
        . '<div class="vp-harga">' . velocity_paket_harga($id) . '</div>'
        . velocity_paket_kelengkapan($id) . velocity_paket_tombol($id) . '</div></article>';
}

// [velocity_paket kategori="slug" kelompok="1"] — grid kartu, dikelompokkan per kategori.
add_shortcode('velocity_paket', function ($atts) {
    $a = shortcode_atts(array('kategori' => '', 'kelompok' => '1'), $atts);
    $kategori = $a['kategori'] ? array_filter(array(get_term_by('slug', $a['kategori'], 'kategori-paket')))
        : get_terms(array('taxonomy' => 'kategori-paket', 'hide_empty' => true, 'orderby' => 'term_order'));
    $kelompok = $a['kelompok'] !== '0' && $kategori && !is_wp_error($kategori);
    $blok = $kelompok ? $kategori : array(null);
    $out = '';
    foreach ($blok as $term) {
        $q = array('post_type' => 'paket', 'posts_per_page' => -1, 'orderby' => array('menu_order' => 'ASC', 'date' => 'ASC'), 'no_found_rows' => true);
        if ($term) { $q['tax_query'] = array(array('taxonomy' => 'kategori-paket', 'terms' => $term->term_id)); }
        $ids = get_posts($q + array('fields' => 'ids'));
        if (!$ids) { continue; }
        $out .= ($term ? '<h2 class="vp-kategori">' . esc_html($term->name) . '</h2>' : '')
            . '<div class="vp-grid">' . implode('', array_map('velocity_paket_kartu', $ids)) . '</div>';
    }
    return $out ? '<div class="vp-daftar">' . $out . '</div>' : '';
});

// Halaman satu paket & arsip memakai template tema: harga, kelengkapan, tombol ditambahkan ke isi.
add_filter('the_content', function ($isi) {
    if (!is_singular('paket') || !in_the_loop() || !is_main_query()) { return $isi; }
    $id = get_the_ID();
    return '<div class="vp-detail"><div class="vp-harga">' . velocity_paket_harga($id) . '</div>'
        . velocity_paket_kelengkapan($id) . velocity_paket_tombol($id) . '</div>' . $isi;
});

add_action('wp_enqueue_scripts', function () {
    $css = '.vp-kategori{margin:2rem 0 1rem;font-size:1.35rem}'
        . '.vp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:1.25rem;margin-bottom:1.5rem}'
        . '.vp-kartu{display:flex;flex-direction:column;border:1px solid rgba(0,0,0,.1);border-radius:8px;overflow:hidden;background:#fff}'
        . '.vp-foto-wrap{display:block;aspect-ratio:3/4;overflow:hidden;background:#f3f4f6}'
        . '.vp-foto{width:100%;height:100%;object-fit:cover;display:block}'
        . '.vp-isi{display:flex;flex-direction:column;flex:1;padding:1rem}'
        . '.vp-judul{font-size:1rem;line-height:1.35;margin:0 0 .4rem}.vp-judul a{color:inherit;text-decoration:none}'
        . '.vp-harga{font-weight:700;font-size:1.1rem;color:var(--bs-primary,#1e73be);margin-bottom:.6rem}.vp-harga small{font-weight:400;font-size:.8rem;color:#666}'
        . '.vp-kelengkapan{font-size:.85rem;padding-left:1.1rem;margin:0 0 1rem;flex:1}.vp-kelengkapan li{margin-bottom:.2rem}'
        . '.vp-tombol{display:inline-block;text-align:center;padding:.55rem .9rem;border-radius:6px;background:#25d366;color:#fff!important;text-decoration:none;font-weight:600}'
        . '.vp-tombol:hover{filter:brightness(.95)}.vp-detail{margin-bottom:1.5rem}.vp-detail .vp-tombol{margin-top:.25rem}';
    wp_register_style('velocity-paket', false);
    wp_enqueue_style('velocity-paket');
    wp_add_inline_style('velocity-paket', $css);
});

register_activation_hook(__FILE__, function () { do_action('init'); flush_rewrite_rules(false); });
