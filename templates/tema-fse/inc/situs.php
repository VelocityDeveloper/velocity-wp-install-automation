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
