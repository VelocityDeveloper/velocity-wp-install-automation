<?php

/**
 * Bagian tampilan yang mengikuti referensi web klien (body.vf-ref) tetapi butuh PHP:
 * ikon keranjang VD Store di header, kolom kategori produk di footer, dan slider hero.
 *
 * Semuanya dinyalakan token opsi `velocity_fse_desain` (ditulis scripts/fse-apply dari
 * rencana referensi), jadi situs berreferensi lama yang tokennya belum ada tidak berubah.
 * Contoh pertama: yukpergimancing.com (referensi kreditmotor.rmg.asia, 2026-09-17).
 */

defined('ABSPATH') || exit;

/** Situs toko online: produk dari plugin VD Store. */
function velocity_fse_toko()
{
    return post_type_exists('store_product');
}

function velocity_fse_token($kunci)
{
    $desain = velocity_fse_desain();
    return $desain[$kunci] ?? null;
}

// Tombol ajakan header diganti ikon keranjang VD Store (referensi toko menaruh keranjang
// di ujung kanan header, bukan tombol "Hubungi Kami").
add_filter('render_block_core/buttons', function ($html, $blok) {
    $kelas = (string) ($blok['attrs']['className'] ?? '');
    if (strpos($kelas, 'vf-header__aksi') === false || !velocity_fse_token('header_keranjang')
        || !velocity_fse_toko() || !shortcode_exists('wp_store_cart')) {
        return $html;
    }
    $html = '<div class="vf-keranjang">' . velocity_fse_atribut_aman(do_shortcode('[wp_store_cart size="22"]')) . '</div>';
    // Link akun pelanggan (halaman Profil Saya VD Store) di kanan keranjang (user 2026-09-17).
    if (shortcode_exists('wp_store_link_profile')) {
        $html .= '<div class="vf-profil-toko">' . velocity_fse_atribut_aman(do_shortcode('[wp_store_link_profile size="30"]')) . '</div>';
    }
    return $html;
}, 10, 2);

/**
 * Template blok menjalankan wptexturize SESUDAH do_blocks (dan do_shortcode SEBELUMNYA, jadi
 * shortcode mentah dari filter render_block tidak pernah dirender). Atribut Alpine VD Store
 * berisi "=>" : wptexturize menganggap ">" itu akhir tag lalu mengubah kutip atribut jadi
 * kutip miring -> <button> tak tertutup menelan seluruh halaman (yukpergimancing.com 2026-09-17).
 * "<" dan ">" di dalam nilai atribut diganti entitas; peramban & Alpine membacanya sama.
 */
function velocity_fse_atribut_aman($html)
{
    $bagian = preg_split('#(<script\b.*?</script>)#is', (string) $html, -1, PREG_SPLIT_DELIM_CAPTURE);
    foreach ($bagian as $i => $b) {
        if ($i % 2 === 0) {
            $bagian[$i] = preg_replace_callback('/(\s[@:a-zA-Z][\w:.@-]*=)"([^"]*)"/', function ($m) {
                return $m[1] . '"' . str_replace(array('<', '>'), array('&lt;', '&gt;'), $m[2]) . '"';
            }, $b);
        }
    }
    return implode('', $bagian);
}

/** Kolom "Kategori Produk" footer: tautan kategori VD Store. */
function velocity_fse_kolom_kategori()
{
    $terms = get_terms(array('taxonomy' => 'store_product_cat', 'hide_empty' => false, 'number' => 8,
        'orderby' => 'name', 'parent' => 0));
    if (is_wp_error($terms) || !$terms) {
        return '';
    }
    $li = '';
    foreach ($terms as $t) {
        $url = get_term_link($t);
        if (!is_wp_error($url)) {
            $li .= '<li><a href="' . esc_url($url) . '">' . esc_html($t->name) . '</a></li>';
        }
    }
    return '<div class="wp-block-column vf-footer__kategori"><h3 class="wp-block-heading vf-footer__judul">Kategori Produk</h3>'
        . '<ul class="vf-footer__daftar">' . $li . '</ul></div>';
}

// Footer toko 5 kolom mengikuti referensi (kreditmotor.rmg.asia, user 2026-09-17):
// Tentang Kami | Informasi | Kategori Produk | Pengunjung | Kontak Kami.
// Kolom disusun ulang di sini; parts/footer.html tetap dipakai situs lain.
function velocity_fse_kolom_footer($judul, $isi, $kelas = '')
{
    return '<div class="wp-block-column' . ($kelas !== '' ? ' ' . $kelas : '') . '">'
        . '<h3 class="wp-block-heading vf-footer__judul">' . esc_html($judul) . '</h3>' . $isi . '</div>';
}

function velocity_fse_footer_toko()
{
    $kolom = array();
    $tentang = (string) velocity_fse_situs('tentang');
    $kolom[] = velocity_fse_kolom_footer('Tentang Kami',
        $tentang !== '' ? '<p class="vf-footer__teks">' . esc_html($tentang) . '</p>' : '', 'vf-footer__tentang');

    // Informasi: katalog & halaman toko VD Store (Pengaturan > Halaman).
    $set = (array) get_option('wp_store_settings', array());
    $tautan = array();
    $arsip = get_post_type_archive_link('store_product');
    if ($arsip) {
        $tautan[] = array('Produk', $arsip);
    }
    foreach (array('page_catalog' => 'Katalog', 'page_cart' => 'Keranjang', 'page_tracking' => 'Cek Pesanan') as $k => $label) {
        $id = (int) ($set[$k] ?? 0);
        if ($id && get_post_status($id) === 'publish') {
            $tautan[] = array($label, get_permalink($id));
        }
    }
    $li = '';
    foreach ($tautan as $t) {
        $li .= '<li><a href="' . esc_url($t[1]) . '">' . esc_html($t[0]) . '</a></li>';
    }
    $kolom[] = velocity_fse_kolom_footer('Informasi', $li !== '' ? '<ul class="vf-footer__daftar">' . $li . '</ul>' : '');

    $kategori = velocity_fse_kolom_kategori();
    if ($kategori !== '') {
        $kolom[] = $kategori;
    }

    $kolom[] = velocity_fse_kolom_footer('Pengunjung',
        do_shortcode('[velocity-statistics style="list" show="all" with_online="1" label_today_visits="Kunjungan Hari Ini" label_today_visitors="Pengunjung Hari Ini" label_total_visits="Total Kunjungan" label_total_visitors="Total Pengunjung" label_online="Sedang Online"]'),
        'vf-statistik');

    $kontak = render_block(array('blockName' => 'velocity/kontak', 'attrs' => array(), 'innerBlocks' => array(), 'innerHTML' => '', 'innerContent' => array()));
    $sosmed = do_blocks('<!-- wp:social-links {"className":"is-style-logos-only vf-sosmed"} --><ul class="wp-block-social-links is-style-logos-only vf-sosmed">'
        . '<!-- wp:social-link {"url":"https://www.facebook.com/","service":"facebook"} /--><!-- wp:social-link {"url":"https://www.instagram.com/","service":"instagram"} /-->'
        . '<!-- wp:social-link {"url":"https://x.com/","service":"x"} /--><!-- wp:social-link {"url":"https://www.youtube.com/","service":"youtube"} /-->'
        . '<!-- wp:social-link {"url":"https://www.tiktok.com/","service":"tiktok"} /--></ul><!-- /wp:social-links -->');
    $kolom[] = velocity_fse_kolom_footer('Kontak Kami', $kontak . $sosmed, 'vf-footer__kontak');

    return '<div class="wp-block-columns alignwide vf-footer__kolom vf-footer__kolom--toko is-layout-flex wp-block-columns-is-layout-flex">'
        . implode('', $kolom) . '</div>';
}

add_filter('render_block_core/columns', function ($html, $blok) {
    $kelas = (string) ($blok['attrs']['className'] ?? '');
    if (strpos($kelas, 'vf-footer__kolom') === false || (int) velocity_fse_token('footer_kolom') < 5 || !velocity_fse_toko()) {
        return $html;
    }
    return velocity_fse_footer_toko();
}, 10, 2);

// Carousel kategori: satu ubin per geser + berulang, hanya untuk gaya toko referensi.
add_filter('wp_store_locate_template', function ($path, $template) {
    if ($template !== 'components/taxonomy-carousel' || !velocity_fse_token('header_keranjang')) {
        return $path;
    }
    $berkas = get_theme_file_path('inc/vd-store/taxonomy-carousel.php');
    return file_exists($berkas) ? $berkas : $path;
}, 10, 2);

// Halaman berisi shortcode halaman VD Store: jalur klasik (lihat inc/vd-store/halaman-toko.php).
add_filter('template_include', function ($templat) {
    if (!is_page() || is_front_page() || !velocity_fse_toko()) {
        return $templat;
    }
    $post = get_queried_object();
    $isi = $post instanceof WP_Post ? (string) $post->post_content : '';
    if (!preg_match('/\[(?:store_(?:cart|checkout|thanks|tracking|customer_profile)|wp_store_(?:catalog|shipping_checker|profile|cart_page|checkout|thanks|tracking|shop|shop_with_filters|wishlist))\b/', $isi)) {
        return $templat;
    }
    $berkas = get_theme_file_path('inc/vd-store/halaman-toko.php');
    return file_exists($berkas) ? $berkas : $templat;
}, 20);

// Daftar Berita & arsip tulisan gaya toko referensi = kartu artikel beranda (templates/archive-toko.html).
foreach (array('home', 'category', 'tag', 'date', 'author') as $vf_jenis_arsip) {
    add_filter($vf_jenis_arsip . '_template_hierarchy', function ($templat) {
        if (velocity_fse_token('header_keranjang')) {
            array_unshift($templat, 'archive-toko');
        }
        return $templat;
    });
}

add_action('wp_enqueue_scripts', function () {
    // Menu HP akordeon (submenu kategori produk) — skrip yang sama dengan gaya klinik.
    if (velocity_fse_token('header_keranjang') && velocity_fse_situs('gaya') !== 'klinik') {
        wp_enqueue_script('velocity-fse-menu-hp', get_theme_file_uri('assets/js/menu-hp.js'), array(), VELOCITY_FSE_VERSI,
            array('in_footer' => true, 'strategy' => 'defer'));
    }
    if (velocity_fse_desain()) {
        wp_enqueue_script('velocity-fse-slider', get_theme_file_uri('assets/js/slider.js'), array(), VELOCITY_FSE_VERSI,
            array('in_footer' => true, 'strategy' => 'defer'));
    }
});

// Pustaka komponen referensi VERSI 5 (2026-09-17): token & CSS komponen baru.
require_once get_theme_file_path('inc/referensi-komponen.php');
