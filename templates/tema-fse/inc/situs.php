<?php

/**
 * Data situs (opsi `velocity_situs`) dan fungsi bantu tampilan.
 *
 * Opsi ditulis scripts/fse-apply dari FORM ISIAN klien dan disunting PM di
 * Tampilan → Data Situs. Installer hanya menimpanya selama belum pernah
 * disunting (dicocokkan lewat opsi `velocity_situs_md5`).
 */

defined('ABSPATH') || exit;

// Product katalog custom: bukan WooCommerce, supaya data produk terpisah dari post berita.
add_action('init', function () {
    // Situs toko online: produk milik VD Store (`store_product` + `store_product_cat`, arsip /produk/).
    // CPT `product` di sini hanya menambah menu "Produk" kedua di wp-admin yang tidak dipakai
    // katalog, keranjang, maupun checkout (kopibalidewiseri.com 2026-09-23).
    if (velocity_fse_vd_store()) {
        global $wpdb;
        if (!(int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'product'")) {
            return;
        }
    }
    // Situs yang memakai CPT `produk` (inc/produk.php) tidak perlu CPT `product` bawaan:
    // dua menu "Produk" di wp-admin hanya membingungkan pemilik situs. Kalau terlanjur ada
    // isinya, CPT ini tetap didaftarkan supaya datanya tidak hilang dari wp-admin.
    if (function_exists('velocity_fse_cpt_produk') && velocity_fse_cpt_produk()) {
        global $wpdb;
        if (!(int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'product'")) {
            return;
        }
    }
    // Data Situs `katalog_produk` = false: situs tanpa katalog (medikaklinikteknologi.com) tidak
    // menampilkan menu Produk. Tetap didaftarkan selama masih ada isi product apa pun.
    if (velocity_fse_situs('katalog_produk') === false) {
        global $wpdb;
        $ada = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'product'");
        if (!$ada) {
            return;
        }
    }
    register_post_type('product', array(
        'labels' => array(
            'name' => 'Produk', 'singular_name' => 'Produk', 'add_new_item' => 'Tambah Produk',
            'edit_item' => 'Edit Produk', 'new_item' => 'Produk Baru', 'view_item' => 'Lihat Produk',
        ),
        'public' => true, 'show_in_rest' => true, 'has_archive' => true,
        'rewrite' => array('slug' => 'products', 'with_front' => false),
        'menu_icon' => 'dashicons-products',
        'supports' => array('title', 'editor', 'thumbnail', 'excerpt'),
    ));
    register_taxonomy('category-product', array('product'), array(
        'labels' => array('name' => 'Kategori Produk', 'singular_name' => 'Kategori Produk'),
        'public' => true, 'show_in_rest' => true, 'hierarchical' => true,
        'rewrite' => array('slug' => 'category-product', 'with_front' => false),
    ));
});

/**
 * Plugin VD Store aktif. Dicek lewat konstanta plugin, bukan post_type_exists('store_product'),
 * supaya tidak bergantung urutan hook `init` (VD Store mendaftarkan CPT-nya di prioritas yang sama).
 */
function velocity_fse_vd_store()
{
    return defined('WP_STORE_VERSION');
}

/** Kunci yang boleh tampil ke pengunjung (Block Bindings `velocity/situs`). */
function velocity_fse_kunci_publik()
{
    return array('nama', 'slogan', 'tentang', 'email_publik', 'telp', 'alamat', 'area');
}

function velocity_fse_situs($kunci = null)
{
    $data = get_option('velocity_situs');
    $data = is_array($data) ? $data : array();
    if ($kunci === null) {
        return $data;
    }
    if ($kunci === 'nama' && empty($data['nama'])) {
        return get_bloginfo('name');
    }
    return isset($data[$kunci]) ? $data[$kunci] : '';
}

function velocity_fse_jenis_berita()
{
    return velocity_fse_situs('jenis') === 'berita';
}

/** Tanggal berbahasa Indonesia; situs terpasang berbahasa Inggris menulis "Monday". */
function velocity_fse_tanggal_id($waktu, $dengan_hari = false)
{
    $hari = array('Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu');
    $bulan = array(1 => 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus',
        'September', 'Oktober', 'November', 'Desember');
    $teks = gmdate('j', $waktu) . ' ' . $bulan[(int) gmdate('n', $waktu)] . ' ' . gmdate('Y', $waktu);
    return $dengan_hari ? $hari[(int) gmdate('w', $waktu)] . ', ' . $teks : $teks;
}

/** Tautan WhatsApp ke nomor publik; '' kalau klien tidak memberi nomor untuk web. */
function velocity_fse_wa_link($pesan = '')
{
    $nomor = preg_replace('/\D/', '', (string) velocity_fse_situs('wa'));
    if ($nomor === '') {
        return '';
    }
    // wa.me hanya menerima format internasional: 0811… (penulisan klien) → 62811….
    $nomor = preg_replace('/^0/', '62', $nomor);
    $pesan = $pesan !== '' ? $pesan : sprintf('Halo %s, saya ingin bertanya.', velocity_fse_situs('nama'));
    return 'https://wa.me/' . $nomor . '?text=' . rawurlencode($pesan);
}

// Blok tanggal bawaan mengikuti bahasa situs; klien Indonesia sering terpasang
// dengan en_US sehingga tertulis "September 14, 2026" / "14 August 2026".
add_filter('render_block_core/post-date', function ($html) {
    if (strpos((string) get_locale(), 'id') === 0) {
        return $html;
    }
    return strtr($html, array(
        'January' => 'Januari', 'February' => 'Februari', 'March' => 'Maret', 'May' => 'Mei',
        'June' => 'Juni', 'July' => 'Juli', 'August' => 'Agustus', 'October' => 'Oktober',
        'December' => 'Desember',
    ));
});

// Caption foto utama tampil di halaman artikel (wajib di semua situs, 2026-09-14):
// core/post-featured-image tidak pernah mencetak caption. Kartu di Query Loop tidak diberi.
// Konteks queryId tidak sampai ke blok foto di dalam post-template (caption sempat tampil di
// 26 kartu beranda), jadi yang dicocokkan: foto milik tulisan yang sedang dibuka.
add_filter('render_block_core/post-featured-image', function ($html, $blok, $instans) {
    if ($html === '' || !is_singular()) {
        return $html;
    }
    $post_id = !empty($instans->context['postId']) ? (int) $instans->context['postId'] : get_the_ID();
    if ($post_id !== (int) get_queried_object_id()) {
        return $html;
    }
    $caption = (string) wp_get_attachment_caption((int) get_post_thumbnail_id($post_id));
    if ($caption === '' || strpos($html, '<figcaption') !== false) {
        return $html;
    }
    $caption = '<figcaption class="wp-element-caption">' . esc_html($caption) . '</figcaption>';
    return preg_replace('~</figure>\s*$~', $caption . '</figure>', $html, 1);
}, 10, 3);

// Judul arsip tanpa awalan "Category:" / "Kategori:".
add_filter('get_the_archive_title_prefix', '__return_empty_string');

// Arsip rubrik situs bergaya "sorotan" memakai templates/archive-sorotan.html (tanpa kolom
// samping, kartu foto selebar layar + grid 4 kolom) — mengikuti arsip rubrik referensi
// klien anaksegalabangsa.com. Situs bergaya klasik tetap archive.html.
foreach (array('category', 'tag', 'taxonomy') as $jenis_arsip) {
    add_filter($jenis_arsip . '_template_hierarchy', function ($templat) {
        if (velocity_fse_situs('gaya') === 'sorotan') {
            array_unshift($templat, 'archive-sorotan');
        }
        return $templat;
    });
}

// Artikel situs bergaya "sorotan": templates/single-sorotan.html (foto 16:9 di atas,
// kolom isi 60% + kolom tulisan lain 40%) — mengikuti halaman artikel referensi klien.
add_filter('single_template_hierarchy', function ($templat) {
    if (velocity_fse_situs('gaya') === 'sorotan' && is_singular('post')) {
        array_unshift($templat, 'single-sorotan');
    }
    return $templat;
});

// 13 = 1 kartu selebar layar + 3 baris grid 4 kolom.
add_action('pre_get_posts', function ($q) {
    if (!is_admin() && $q->is_main_query() && ($q->is_category() || $q->is_tag() || $q->is_tax())
        && velocity_fse_situs('gaya') === 'sorotan') {
        $q->set('posts_per_page', 13);
    }
});


/**
 * Tombol ajakan header & tautan bawaan "/hubungi-kami/" mengikuti Data Situs
 * `tombol_header` = [label, path] bila situs memakai halaman kontak lain
 * (medikaklinikteknologi.com: "Start Your Clinic" → /contact/).
 */
add_filter('render_block_core/button', function ($html) {
    $atur = velocity_fse_situs('tombol_header');
    if (!is_array($atur) || empty($atur[0]) || empty($atur[1]) || strpos($html, 'href="/hubungi-kami/"') === false) {
        return $html;
    }
    return str_replace(
        array('href="/hubungi-kami/"', '>Hubungi Kami</a>'),
        array('href="' . esc_url(home_url((string) $atur[1])) . '"', '>' . esc_html((string) $atur[0]) . '</a>'),
        $html
    );
});

/**
 * Tautan bawaan template ke halaman standar (mis. "Selengkapnya →" /tentang-kami/ di kolom
 * samping) dialihkan lewat Data Situs `ganti_tautan` = {"/tentang-kami/": "/about/"} untuk
 * situs yang memakai halaman menu klien sendiri.
 */
add_filter('render_block_core/paragraph', function ($html) {
    $peta = velocity_fse_situs('ganti_tautan');
    if (!is_array($peta) || strpos($html, 'href="/') === false) {
        return $html;
    }
    foreach ($peta as $dari => $ke) {
        $html = str_replace('href="' . $dari . '"', 'href="' . esc_url(home_url((string) $ke)) . '"', $html);
    }
    return $html;
});

/** Hasil pencarian gaya klinik: halaman (tanpa kategori) tetap berlabel seperti kartu artikel. */
add_filter('render_block_core/post-terms', function ($html, $block, $instance) {
    if (trim(wp_strip_all_tags($html)) !== '' || !is_search() || velocity_fse_situs('gaya') !== 'klinik') {
        return $html;
    }
    $id = isset($instance->context['postId']) ? (int) $instance->context['postId'] : 0;
    if (!$id || get_post_type($id) !== 'page') {
        return $html;
    }
    return '<div class="wp-block-post-terms vf-label vf-label--halaman"><span>Halaman</span></div>';
}, 10, 3);

/**
 * Data Situs `logo_footer` = true: nama situs di footer diganti logo situs (logo bertulisan nama
 * perusahaan, jadi teks nama tidak diulang). Logo diberi alas putih lewat CSS .vf-footer__logo.
 */
add_filter('render_block_core/site-title', function ($html, $block) {
    $kelas = isset($block['attrs']['className']) ? (string) $block['attrs']['className'] : '';
    if (strpos($kelas, 'vf-footer__nama') === false || velocity_fse_situs('logo_footer') !== true) {
        return $html;
    }
    $id = (int) get_option('site_logo');
    $gambar = $id ? wp_get_attachment_image($id, 'medium', false, array(
        'class' => 'vf-footer__logo-img', 'alt' => velocity_fse_situs('nama'), 'loading' => 'lazy',
    )) : '';
    if ($gambar === '') {
        return $html;
    }
    return sprintf('<p class="vf-footer__logo"><a href="%s" rel="home">%s</a></p>', esc_url(home_url('/')), $gambar);
}, 10, 2);

/**
 * Data Situs `tautan_legal` = [[label, path], ...]: tautan Privacy Policy / Terms di kanan
 * baris bawah footer. Isi lama (hak cipta + kredit) dibungkus .vf-footer__kiri supaya di HP
 * urutannya bisa dibalik utuh. Tautan ke halaman yang belum terbit tidak dicetak.
 */
add_filter('render_block_core/group', function ($html, $block) {
    $kelas = isset($block['attrs']['className']) ? (string) $block['attrs']['className'] : '';
    $daftar = velocity_fse_situs('tautan_legal');
    if (strpos($kelas, 'vf-footer__bawah') === false || !is_array($daftar)) {
        return $html;
    }
    $tautan = array();
    foreach ($daftar as $t) {
        if (!is_array($t) || count($t) !== 2) {
            continue;
        }
        $hal = get_page_by_path(trim((string) $t[1], '/'));
        if (!$hal || $hal->post_status !== 'publish') {
            continue;
        }
        $tautan[] = sprintf('<a href="%s">%s</a>', esc_url(get_permalink($hal)), esc_html((string) $t[0]));
    }
    $buka = strpos($html, '>');
    $tutup = strrpos($html, '</div>');
    if (!$tautan || $buka === false || $tutup === false) {
        return $html;
    }
    return substr($html, 0, $buka + 1)
        . '<div class="vf-footer__kiri">' . substr($html, $buka + 1, $tutup - $buka - 1) . '</div>'
        . '<p class="vf-footer__legal">' . implode('<span aria-hidden="true">|</span>', $tautan) . '</p>'
        . substr($html, $tutup);
}, 10, 2);

/**
 * Ikon sosmed installer (.vf-sosmed) dibuka di tab baru — semua gaya (klinik sejak 2026-09-16,
 * semua situs sejak 2026-09-17, yukpergimancing.com). Markup baru memakai atribut openInNewTab;
 * filter ini menutup konten/halaman lama yang dibuat sebelum atribut itu ada.
 */
add_filter('render_block_core/social-links', function ($html, $block) {
    $kelas = isset($block['attrs']['className']) ? (string) $block['attrs']['className'] : '';
    if (strpos($kelas, 'vf-sosmed') === false) {
        return $html;
    }
    return preg_replace('/<a (?![^>]*\btarget=)([^>]*class="wp-block-social-link-anchor")/',
        '<a target="_blank" rel="noopener noreferrer" $1', $html);
}, 10, 2);
