<?php
/**
 * Seksi 3: solusi.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
?>
<section id="vlp-solusi" class="vlp-seksi vlp-solusi vlp-cahaya vlp-cahaya--kanan">
	<div class="vlp-wadah vlp-dua-kolom vlp-dua-kolom--gambar-kanan">
		<div class="vlp-kolom-teks">
			<h2 class="vlp-judul"><?php echo vlp_judul(vlp_mod('solusi', 'judul')); ?></h2>
			<div class="vlp-teks"><?php echo vlp_paragraf(vlp_mod('solusi', 'teks')); ?></div>
		</div>
		<div class="vlp-kolom-gambar">
			<?php echo vlp_img(vlp_mod('solusi', 'gambar'), vlp_mod('solusi', 'judul'), 'vlp-foto', 'large', '(max-width: 781px) 100vw, 510px'); ?>
		</div>
	</div>
</section>
