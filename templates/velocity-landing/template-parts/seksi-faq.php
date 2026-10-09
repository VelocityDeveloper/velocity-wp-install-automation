<?php
/**
 * Seksi 11: tanya jawab, dua kolom <details>.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
$item = vlp_item('faq', 'tanya');
$kolom = array_chunk($item, max(1, (int) ceil(count($item) / 2)));
?>
<section id="vlp-faq" class="vlp-seksi vlp-faq">
	<div class="vlp-wadah">
		<h2 class="vlp-judul vlp-judul--tengah"><?php echo vlp_judul(vlp_mod('faq', 'judul')); ?></h2>
		<div class="vlp-teks vlp-teks--tengah vlp-pengantar"><?php echo vlp_paragraf(vlp_mod('faq', 'deskripsi')); ?></div>
		<div class="vlp-faq-grid">
			<?php foreach ($kolom as $isi) : ?>
				<div class="vlp-faq-kolom">
					<?php foreach ($isi as $tj) : ?>
						<details class="vlp-faq-item">
							<summary><?php echo esc_html($tj['tanya']); ?></summary>
							<div class="vlp-faq-jawab"><?php echo vlp_paragraf($tj['jawab']); ?></div>
						</details>
					<?php endforeach; ?>
				</div>
			<?php endforeach; ?>
		</div>
	</div>
</section>
