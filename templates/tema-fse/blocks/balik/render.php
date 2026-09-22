<?php

/**
 * Tautan "Kembali" di atas judul artikel.
 *
 * Tujuannya halaman daftar artikel milik situs — bukan jalur tetap "/berita/",
 * karena situs bisa dipasang di subfolder (staging velocitydeveloper.co/<domain>)
 * dan halaman daftarnya bisa bernama lain.
 */

defined('ABSPATH') || exit;

$tujuan = '';
$label = __('Kembali ke Artikel', 'velocity-fse');

$kategori = get_the_category();
if ($kategori && !is_wp_error($kategori)) {
    $tautan = get_category_link($kategori[0]->term_id);
    if ($tautan) {
        $tujuan = $tautan;
        $label = sprintf(__('Kembali ke %s', 'velocity-fse'), $kategori[0]->name);
    }
}
if (!$tujuan) {
    $daftar = (int) get_option('page_for_posts');
    $tujuan = $daftar ? get_permalink($daftar) : get_post_type_archive_link('post');
}
if (!$tujuan) {
    $tujuan = home_url('/');
    $label = __('Kembali ke Beranda', 'velocity-fse');
}
?>
<p <?php echo get_block_wrapper_attributes(array('class' => 'vf-artikel__balik')); ?>>
	<a href="<?php echo esc_url($tujuan); ?>">&larr; <?php echo esc_html($label); ?></a>
</p>
