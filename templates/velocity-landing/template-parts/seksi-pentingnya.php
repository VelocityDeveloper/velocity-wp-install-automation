<?php
/**
 * Seksi 4: mengapa penting.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
?>
<section id="vlp-pentingnya" class="vlp-seksi vlp-pentingnya">
	<div class="vlp-wadah vlp-dua-kolom">
		<div class="vlp-kolom-gambar">
			<?php echo vlp_img(vlp_mod('pentingnya', 'gambar'), vlp_mod('pentingnya', 'judul'), 'vlp-foto', 'large', '(max-width: 781px) 100vw, 510px'); ?>
		</div>
		<div class="vlp-kolom-teks">
			<h2 class="vlp-judul"><?php echo vlp_judul(vlp_mod('pentingnya', 'judul')); ?></h2>
			<div class="vlp-teks"><?php echo vlp_paragraf(vlp_mod('pentingnya', 'teks')); ?></div>
		</div>
	</div>
</section>
