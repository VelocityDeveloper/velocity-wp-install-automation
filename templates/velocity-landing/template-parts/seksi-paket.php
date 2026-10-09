<?php
/**
 * Seksi 8: paket harga.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
$ikon = vlp_mod('paket', 'ikon');
?>
<section id="vlp-paket" class="vlp-seksi vlp-paket">
	<div class="vlp-wadah">
		<h2 class="vlp-judul vlp-judul--tengah"><?php echo vlp_judul(vlp_mod('paket', 'judul')); ?></h2>
		<div class="vlp-teks vlp-teks--tengah vlp-pengantar"><?php echo vlp_paragraf(vlp_mod('paket', 'deskripsi')); ?></div>
		<div class="vlp-grid vlp-grid--3">
			<?php foreach (vlp_item('paket', 'nama') as $item) : ?>
				<div class="vlp-kartu vlp-kartu--paket">
					<h3 class="vlp-paket-nama"><?php echo esc_html($item['nama']); ?></h3>
					<?php if ($item['label']) : ?>
						<p class="vlp-paket-label"><?php echo esc_html($item['label']); ?></p>
					<?php endif; ?>
					<?php if ($item['harga']) : ?>
						<p class="vlp-paket-harga"><?php echo esc_html($item['harga']); ?></p>
					<?php endif; ?>
					<?php if ($item['tombol_label']) : ?>
						<a class="vlp-tombol vlp-tombol--aksen" href="<?php echo esc_url(vlp_link($item['tombol_link'])); ?>"<?php echo vlp_target(); ?>><?php echo esc_html($item['tombol_label']); ?></a>
					<?php endif; ?>
					<ul class="vlp-paket-fitur">
						<?php foreach (vlp_baris($item['fitur']) as $fitur) : ?>
							<li><span class="vlp-cek"><?php echo vlp_ikon($ikon); ?></span><span><?php echo esc_html($fitur); ?></span></li>
						<?php endforeach; ?>
					</ul>
				</div>
			<?php endforeach; ?>
		</div>
	</div>
</section>
