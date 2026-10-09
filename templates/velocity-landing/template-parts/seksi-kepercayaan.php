<?php
/**
 * Seksi 10: kotak kepercayaan.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
?>
<section id="vlp-kepercayaan" class="vlp-seksi vlp-kepercayaan">
	<div class="vlp-wadah">
		<div class="vlp-kartu vlp-kartu--gradasi vlp-kepercayaan-kotak">
			<div class="vlp-kepercayaan-gambar">
				<?php echo vlp_img(vlp_mod('kepercayaan', 'gambar'), vlp_mod('kepercayaan', 'judul'), '', 'medium_large', '(max-width: 781px) 60vw, 343px'); ?>
			</div>
			<div class="vlp-kepercayaan-teks">
				<h2 class="vlp-judul vlp-judul--besar"><?php echo vlp_judul(vlp_mod('kepercayaan', 'judul')); ?></h2>
				<div class="vlp-kartu-teks vlp-kartu-teks--kecil"><?php echo vlp_paragraf(vlp_mod('kepercayaan', 'teks')); ?></div>
			</div>
		</div>
	</div>
</section>
