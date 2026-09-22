<?php

/**
 * Deret geser (carousel). Isinya blok Gambar biasa (InnerBlocks) supaya pemilik situs
 * bisa menambah/mengganti/mengurutkan gambar lewat editor seperti blok lain — sebelumnya
 * deret ini hanya grup berkelas sehingga sulit dikenali & disunting (user 2026-09-18).
 *
 * `tampilan`: "logo" (kotak logo putih) atau "foto" (kartu foto berketerangan).
 * Panah geser dipasang assets/js/slider.js lewat kelas .vf-logo-geser.
 */

defined('ABSPATH') || exit;

$isi = trim((string) ($content ?? ''));
if ($isi === '') {
    return;
}
$tampilan = ($attributes['tampilan'] ?? 'logo') === 'foto' ? 'foto' : 'logo';
$kelas = 'vf-klien vf-logo-geser' . ($tampilan === 'foto' ? ' vf-geser-foto' : ' vf-klien--logo');
?>
<div <?php echo get_block_wrapper_attributes(array('class' => $kelas)); ?>>
	<?php echo $isi; // phpcs:ignore -- markup blok anak, sudah dirender core ?>
</div>
