<?php

/**
 * Satu judul untuk semua arsip. Blok query-title bawaan kosong di halaman
 * tulisan (page_for_posts), padahal di situ judul "Berita" paling dibutuhkan.
 */

defined('ABSPATH') || exit;

// Gaya klinik: label kecil + kata kunci sebagai judul + jumlah hasil (kerangka seksi beranda).
if (is_search() && velocity_fse_situs('gaya') === 'klinik') {
    global $wp_query;
    $jumlah = (int) $wp_query->found_posts;
    ?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-cari-judul')); ?>>
	<p class="vf-label-seksi">Hasil Pencarian</p>
	<h1>&ldquo;<?php echo esc_html(get_search_query()); ?>&rdquo;</h1>
	<p class="vf-cari-judul__jumlah"><?php echo esc_html($jumlah ? sprintf('%d hasil ditemukan', $jumlah) : 'Tidak ada hasil yang cocok'); ?></p>
</div>
    <?php
    return;
}

if (is_home()) {
    $halaman = (int) get_option('page_for_posts');
    $judul = $halaman ? get_the_title($halaman) : 'Tulisan Terbaru';
} elseif (is_search()) {
    $judul = sprintf('Hasil pencarian: %s', get_search_query());
} elseif (is_category() || is_tag() || is_tax()) {
    $judul = single_term_title('', false);
} elseif (is_archive()) {
    $judul = wp_strip_all_tags(get_the_archive_title());
} else {
    $judul = get_the_title();
}
?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-rubrik-bar')); ?>>
	<h1><?php echo esc_html($judul); ?></h1>
</div>
