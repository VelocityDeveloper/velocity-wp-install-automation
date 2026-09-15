<?php

/**
 * Satu judul untuk semua arsip. Blok query-title bawaan kosong di halaman
 * tulisan (page_for_posts), padahal di situ judul "Berita" paling dibutuhkan.
 */

defined('ABSPATH') || exit;

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
