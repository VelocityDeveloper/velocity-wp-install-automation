<?php
/**
 * Seksi 7: alasan memilih + dua foto bertumpuk.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
?>
<section id="vlp-mengapa" class="vlp-seksi vlp-mengapa">
	<div class="vlp-wadah vlp-dua-kolom vlp-dua-kolom--gambar-kanan">
		<div class="vlp-kolom-teks">
			<h2 class="vlp-judul"><?php echo vlp_judul(vlp_mod('mengapa', 'judul')); ?></h2>
			<ul class="vlp-alasan">
				<?php foreach (vlp_baris(vlp_mod('mengapa', 'butir')) as $butir) : ?>
					<li><?php echo esc_html($butir); ?></li>
				<?php endforeach; ?>
			</ul>
		</div>
		<div class="vlp-kolom-gambar">
			<div class="vlp-foto-tumpuk">
				<?php
				echo vlp_img(vlp_mod('mengapa', 'gambar1'), vlp_mod('mengapa', 'judul'), 'vlp-foto vlp-foto-tumpuk__belakang', 'medium_large', '306px');
				echo vlp_img(vlp_mod('mengapa', 'gambar2'), vlp_mod('mengapa', 'judul'), 'vlp-foto vlp-foto-tumpuk__depan', 'medium_large', '306px');
				?>
			</div>
		</div>
	</div>
</section>
