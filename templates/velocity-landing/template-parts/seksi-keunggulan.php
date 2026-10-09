<?php
/**
 * Seksi 6: kartu keunggulan berikon.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
?>
<section id="vlp-keunggulan" class="vlp-seksi vlp-keunggulan vlp-cahaya vlp-cahaya--kiri vlp-cahaya--kedua vlp-cahaya-ganda">
	<div class="vlp-wadah">
		<h2 class="vlp-judul vlp-judul--tengah"><?php echo vlp_judul(vlp_mod('keunggulan', 'judul')); ?></h2>
		<div class="vlp-grid vlp-grid--3">
			<?php foreach (vlp_item('keunggulan', 'judul') as $item) : ?>
				<div class="vlp-kartu vlp-kartu--ikon">
					<?php if ($item['ikon']) : ?>
						<span class="vlp-kotak-ikon"><?php echo vlp_ikon($item['ikon']); ?></span>
					<?php endif; ?>
					<h3 class="vlp-kartu-judul"><?php echo esc_html($item['judul']); ?></h3>
					<div class="vlp-kartu-teks"><?php echo vlp_paragraf($item['teks']); ?></div>
				</div>
			<?php endforeach; ?>
		</div>
	</div>
</section>
