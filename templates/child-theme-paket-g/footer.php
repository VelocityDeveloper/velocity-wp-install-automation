<?php

/**
 * Footer desain custom.
 *
 * Menggantikan footer tema induk (yang isinya area widget + baris hak cipta)
 * dengan susunan yang diminta klien: identitas perusahaan, daftar layanan,
 * kontak, lalu baris hak cipta. Area widget sengaja tidak dipakai — lihat
 * `{{PREFIX}}_buang_widget()` di functions.php.
 */

defined('ABSPATH') || exit;
?>

<?php do_action('justg_after_wrapper_content'); ?>

</div><!-- #wrapper-content -->

<footer class="{{PREFIX}}-footer">
	<div class="{{PREFIX}}-wrap {{PREFIX}}-footer__grid">

		<div class="{{PREFIX}}-footer__kolom">
			<p class="{{PREFIX}}-footer__nama"><?php echo esc_html({{PREFIX}}_data('nama')); ?></p>
			<p class="{{PREFIX}}-footer__teks"><?php echo esc_html({{PREFIX}}_data('alamat')); ?></p>
			<p class="{{PREFIX}}-footer__teks">Area layanan: <?php echo esc_html({{PREFIX}}_data('area')); ?></p>
		</div>

		<div class="{{PREFIX}}-footer__kolom">
			<p class="{{PREFIX}}-footer__judul">Layanan</p>
			<ul class="{{PREFIX}}-footer__daftar">
				<?php foreach ({{PREFIX}}_data('layanan') as $layanan) : ?>
					<li><?php echo esc_html($layanan['judul']); ?></li>
				<?php endforeach; ?>
			</ul>
		</div>

		<div class="{{PREFIX}}-footer__kolom">
			<p class="{{PREFIX}}-footer__judul">Halaman</p>
			<?php
			wp_nav_menu(array(
				'theme_location' => 'primary',
				'container'      => false,
				'menu_class'     => '{{PREFIX}}-footer__daftar',
				'depth'          => 1,
				'fallback_cb'    => false,
			));
			?>
		</div>

		<div class="{{PREFIX}}-footer__kolom">
			<p class="{{PREFIX}}-footer__judul">Kontak</p>
			<p class="{{PREFIX}}-footer__teks">
				<a href="<?php echo esc_url({{PREFIX}}_wa_link()); ?>" target="_blank" rel="noopener nofollow">
					<?php echo esc_html({{PREFIX}}_data('telp')); ?> (WhatsApp)
				</a><br />
				<a href="mailto:<?php echo esc_attr({{PREFIX}}_data('email')); ?>"><?php echo esc_html({{PREFIX}}_data('email')); ?></a>
			</p>
			<?php $pemesanan = get_page_by_path('pemesanan'); ?>
			<?php if ($pemesanan) : ?>
				<p class="{{PREFIX}}-footer__teks">
					<a class="{{PREFIX}}-btn {{PREFIX}}-btn--utama {{PREFIX}}-btn--kecil"
						href="<?php echo esc_url(get_permalink($pemesanan)); ?>">Ajukan Pemesanan</a>
				</p>
			<?php endif; ?>
		</div>

	</div>

	<div class="{{PREFIX}}-footer__bawah">
		<div class="{{PREFIX}}-wrap">
			<p>&copy; <?php echo esc_html(date_i18n('Y')); ?> <?php echo esc_html({{PREFIX}}_data('nama')); ?>. Seluruh hak cipta dilindungi.</p>
		</div>
	</div>
</footer>

</div><!-- #page -->

<?php wp_footer(); ?>

</body>

</html>
