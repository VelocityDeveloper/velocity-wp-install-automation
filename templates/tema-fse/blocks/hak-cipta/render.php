<?php

/**
 * Baris hak cipta. Teksnya disunting langsung di editor (atribut `teks`, permintaan user
 * 2026-09-19); {tahun} dan {situs} diganti saat tampil supaya tahun tetap otomatis.
 * Kredit "Design by Velocity Developer" ditulis di parts/footer.html.
 */

defined('ABSPATH') || exit;

$teks = trim((string) ($attributes['teks'] ?? ''));
if ($teks === '') {
    $teks = '&copy; {tahun} {situs}.';
}
$teks = strtr(wp_kses_post($teks), array(
    '{tahun}' => esc_html(wp_date('Y')),
    '{situs}' => esc_html(velocity_fse_situs('nama')),
));
?>
<p <?php echo get_block_wrapper_attributes(); ?>><?php echo $teks; // phpcs:ignore -- disaring wp_kses_post ?></p>
