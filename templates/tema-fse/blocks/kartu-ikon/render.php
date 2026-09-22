<?php

/**
 * Kartu Ikon: ikon + judul + isi (+ tautan), semua disunting langsung di editor.
 *
 * Pengganti blok "Kontak Publik" yang isinya tersembunyi di Data Situs (permintaan user
 * 2026-09-19: blok harus bisa diubah di tempat seperti Beaver Builder/Elementor).
 * `sumber` (alamat|wa|telp|email) hanya cadangan: dipakai bila isi dikosongkan.
 * `tampilan`: "kartu" (bertumpuk, untuk grid) atau "baris" (ikon kecil di kiri, footer).
 */

defined('ABSPATH') || exit;

$ikon = sanitize_key($attributes['ikon'] ?? 'telepon');
$judul = trim((string) ($attributes['judul'] ?? ''));
$isi = trim((string) ($attributes['isi'] ?? ''));
$tautan = trim((string) ($attributes['tautan'] ?? ''));
$sumber = (string) ($attributes['sumber'] ?? '');

if ($isi === '' && $sumber !== '') {
    list($isi_data, $tautan_data) = velocity_fse_kontak_sumber($sumber);
    $isi = esc_html($isi_data);
    if ($tautan === '') {
        $tautan = $tautan_data;
    }
}
if ($isi === '' && $judul === '') {
    return; // kartu tanpa isi (mis. data situs kosong) tidak ditampilkan sama sekali
}

$baris = ($attributes['tampilan'] ?? 'kartu') === 'baris';
$kelas = ($baris ? 'vf-kartu-ikon vf-kartu-ikon--baris' : 'vf-kartu-ikon vf-kontak-kartu__item')
    . ' vf-kontak-kartu__item--' . $ikon;
$isi_html = wp_kses_post($isi);
if ($tautan !== '') {
    $baru = !empty($attributes['tabBaru']) || strpos($tautan, 'https://wa.me/') === 0;
    $isi_html = sprintf('<a href="%s"%s>%s</a>', esc_url($tautan),
        $baru ? ' target="_blank" rel="noopener"' : '', $isi_html);
}
?>
<div <?php echo get_block_wrapper_attributes(array('class' => $kelas)); ?>>
	<span class="vf-kontak-kartu__ikon"><?php echo velocity_fse_ikon_svg($ikon); // phpcs:ignore -- SVG dari pustaka tema ?></span>
	<?php if ($baris) : ?><span class="vf-kartu-ikon__teks"><?php endif; ?>
	<?php if ($judul !== '') : ?><span class="vf-kontak-kartu__judul"><?php echo wp_kses_post($judul); ?></span><?php endif; ?>
	<?php if ($isi_html !== '') : ?><span class="vf-kontak-kartu__isi"><?php echo $isi_html; // phpcs:ignore -- disaring wp_kses_post ?></span><?php endif; ?>
	<?php if ($baris) : ?></span><?php endif; ?>
</div>
