<?php
/**
 * Seksi 9: jenis layanan (kartu berfoto).
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
?>
<section id="vlp-jenis" class="vlp-seksi vlp-jenis">
	<div class="vlp-wadah">
		<h2 class="vlp-judul vlp-judul--tengah"><?php echo vlp_judul(vlp_mod('jenis', 'judul')); ?></h2>
		<div class="vlp-teks vlp-teks--tengah vlp-pengantar"><?php echo vlp_paragraf(vlp_mod('jenis', 'deskripsi')); ?></div>
		<div class="vlp-grid vlp-grid--3 vlp-jenis-grid">
			<?php foreach (vlp_repeater('jenis', 'items') as $item) : ?>
				<div class="vlp-kartu vlp-kartu--foto">
					<?php echo vlp_img($item['gambar'], $item['judul'], 'vlp-kartu-foto', 'medium_large', '(max-width: 781px) 100vw, 343px'); ?>
					<div class="vlp-kartu-isi">
						<?php if ($item['judul']) : ?>
							<h3 class="vlp-kartu-judul vlp-kartu-judul--kecil"><?php echo esc_html($item['judul']); ?></h3>
						<?php endif; ?>
						<div class="vlp-kartu-teks vlp-kartu-teks--kecil"><?php echo vlp_paragraf($item['teks']); ?></div>
					</div>
				</div>
			<?php endforeach; ?>
		</div>
	</div>
</section>
