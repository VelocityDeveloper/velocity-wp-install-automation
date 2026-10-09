<?php
/**
 * Seksi 1: pembuka (hero).
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
$label = trim((string) vlp_mod('hero', 'tombol_label'));
?>
<section id="vlp-hero" class="vlp-seksi vlp-hero vlp-cahaya vlp-cahaya--kanan-atas">
	<div class="vlp-wadah vlp-dua-kolom vlp-dua-kolom--gambar-kanan">
		<div class="vlp-kolom-teks">
			<h1 class="vlp-judul vlp-judul--besar"><?php echo vlp_judul(vlp_mod('hero', 'judul')); ?></h1>
			<div class="vlp-teks"><?php echo vlp_paragraf(vlp_mod('hero', 'teks')); ?></div>
			<?php if ($label) : ?>
				<a class="vlp-tombol" href="<?php echo esc_url(vlp_link(vlp_mod('hero', 'tombol_link'))); ?>"<?php echo vlp_target(); ?>><?php echo esc_html($label); ?></a>
			<?php endif; ?>
		</div>
		<div class="vlp-kolom-gambar">
			<?php echo vlp_img(vlp_mod('hero', 'gambar'), vlp_mod('hero', 'judul'), 'vlp-foto', 'large', '(max-width: 781px) 100vw, 510px'); ?>
		</div>
	</div>
</section>
