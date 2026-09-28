<?php

/**
 * Slot iklan portal berita (permintaan user 2026-09-28). Gambar, tautan, dan tampil/sembunyi
 * diatur per slot di Tampilan → Iklan (inc/iklan.php); slot tanpa gambar = kotak "Ruang Iklan"
 * yang tertaut ke Hubungi Kami, bukan gambar iklan palsu.
 */

defined('ABSPATH') || exit;

$slot = sanitize_key(isset($attributes['slot']) ? $attributes['slot'] : 'sela-1');
$atur = velocity_fse_iklan($slot);
if (!empty($atur['sembunyi'])) {
    return;
}
$gambar = !empty($atur['gambar']) ? wp_get_attachment_image((int) $atur['gambar'], 'full', false,
    array('class' => 'vf-iklan__gambar', 'loading' => 'lazy', 'alt' => $atur['alt'] !== '' ? $atur['alt'] : 'Iklan')) : '';
$url = $atur['url'] !== '' ? $atur['url'] : home_url('/hubungi-kami/');
$baru = $gambar && $atur['url'] !== '' && strpos($atur['url'], home_url()) !== 0;
?>
<aside <?php echo get_block_wrapper_attributes(array('class' => 'vf-iklan vf-iklan--' . $slot . ($gambar ? '' : ' vf-iklan--kosong'), 'aria-label' => 'Iklan')); ?>>
	<a href="<?php echo esc_url($url); ?>"<?php echo $baru ? ' target="_blank" rel="noopener sponsored"' : ''; ?>>
		<?php if ($gambar) : ?>
			<?php echo $gambar; // phpcs:ignore WordPress.Security.EscapeOutput -- keluaran inti WP. ?>
		<?php else : ?>
			<span class="vf-iklan__label">Ruang Iklan</span>
			<span class="vf-iklan__ajak">Pasang iklan Anda di sini &rarr; Hubungi Kami</span>
		<?php endif; ?>
	</a>
</aside>
