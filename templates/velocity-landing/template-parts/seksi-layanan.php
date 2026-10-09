<?php
/**
 * Seksi 5: layanan utama (judul, foto lebar, teks rata tengah).
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
?>
<section id="vlp-layanan" class="vlp-seksi vlp-layanan vlp-cahaya vlp-cahaya--kanan-bawah vlp-cahaya--lembut">
	<div class="vlp-wadah vlp-tengah">
		<h2 class="vlp-judul vlp-judul--tengah"><?php echo vlp_judul(vlp_mod('layanan', 'judul')); ?></h2>
		<?php echo vlp_img(vlp_mod('layanan', 'gambar'), vlp_mod('layanan', 'judul'), 'vlp-foto-lebar', 'large', '(max-width: 981px) 100vw, 940px'); ?>
		<div class="vlp-teks vlp-teks--tengah"><?php echo vlp_paragraf(vlp_mod('layanan', 'teks')); ?></div>
	</div>
</section>
