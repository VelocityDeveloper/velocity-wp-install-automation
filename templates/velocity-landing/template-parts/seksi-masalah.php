<?php
/**
 * Seksi 2: masalah pelanggan.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
$ikon = vlp_mod('masalah', 'ikon');
?>
<section id="vlp-masalah" class="vlp-seksi vlp-masalah vlp-cahaya vlp-cahaya--kiri vlp-cahaya--kedua">
	<div class="vlp-wadah vlp-dua-kolom">
		<div class="vlp-kolom-gambar">
			<?php echo vlp_img(vlp_mod('masalah', 'gambar'), vlp_mod('masalah', 'judul'), 'vlp-foto', 'large', '(max-width: 781px) 100vw, 510px'); ?>
		</div>
		<div class="vlp-kolom-teks">
			<h2 class="vlp-judul"><?php echo vlp_judul(vlp_mod('masalah', 'judul')); ?></h2>
			<ul class="vlp-masalah-daftar">
				<?php foreach (vlp_baris(vlp_mod('masalah', 'butir')) as $butir) : ?>
					<li><?php echo vlp_ikon($ikon, 'vlp-masalah-ikon'); ?><span><?php echo esc_html($butir); ?></span></li>
				<?php endforeach; ?>
			</ul>
		</div>
	</div>
</section>
