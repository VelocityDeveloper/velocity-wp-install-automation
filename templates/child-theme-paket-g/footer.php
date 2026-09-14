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

<?php if ({{PREFIX}}_gaya_compro()) : ?>
<?php // Kaki halaman compro: identitas di latar halaman, lalu pita hitam berisi slogan dengan sudut aksen berikon kontak. ?>
<footer class="{{PREFIX}}-footer {{PREFIX}}-footer--compro">
	<div class="{{PREFIX}}-wrap {{PREFIX}}-footer__grid">
		<div class="{{PREFIX}}-footer__kolom">
			<p class="{{PREFIX}}-footer__nama"><?php echo esc_html({{PREFIX}}_data('nama')); ?></p>
			<?php if ({{PREFIX}}_data('subjudul')) : ?>
				<p class="{{PREFIX}}-footer__sub"><?php echo esc_html({{PREFIX}}_data('subjudul')); ?></p>
			<?php endif; ?>
			<p class="{{PREFIX}}-footer__teks"><?php echo esc_html({{PREFIX}}_data('alamat')); ?></p>
		</div>
		<div class="{{PREFIX}}-footer__kolom">
			<p class="{{PREFIX}}-footer__judul">Layanan</p>
			<ul class="{{PREFIX}}-footer__daftar">
				<?php foreach ((array) {{PREFIX}}_data('layanan') as $layanan) : ?>
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
	</div>
	<div class="{{PREFIX}}-pita">
		<div class="{{PREFIX}}-wrap {{PREFIX}}-pita__isi">
			<div>
				<p class="{{PREFIX}}-pita__slogan"><?php echo esc_html({{PREFIX}}_data('slogan') ?: {{PREFIX}}_data('nama')); ?></p>
				<p class="{{PREFIX}}-pita__hak">&copy; <?php echo esc_html(date_i18n('Y')); ?> <?php echo esc_html({{PREFIX}}_data('nama')); ?></p>
			</div>
			<div class="{{PREFIX}}-pita__kontak">
				<?php if ({{PREFIX}}_ada_wa()) : ?>
					<a href="<?php echo esc_url({{PREFIX}}_wa_link()); ?>" target="_blank" rel="noopener nofollow"><?php echo {{PREFIX}}_ikon('telepon'); ?><?php echo esc_html({{PREFIX}}_data('telp')); ?></a>
				<?php endif; ?>
				<?php $email_publik = trim((string) {{PREFIX}}_data('email_publik')); ?>
				<?php if ($email_publik !== '') : ?>
					<a href="mailto:<?php echo esc_attr($email_publik); ?>"><?php echo {{PREFIX}}_ikon('surel'); ?><?php echo esc_html($email_publik); ?></a>
				<?php endif; ?>
			</div>
		</div>
	</div>
</footer>
<?php else : ?>
<footer class="{{PREFIX}}-footer">
	<div class="{{PREFIX}}-wrap {{PREFIX}}-footer__grid">

		<div class="{{PREFIX}}-footer__kolom">
			<p class="{{PREFIX}}-footer__nama"><?php echo esc_html({{PREFIX}}_data('nama')); ?></p>
			<?php if (trim((string) {{PREFIX}}_data('alamat'), ' -') !== '') : ?>
				<p class="{{PREFIX}}-footer__teks"><?php echo esc_html({{PREFIX}}_data('alamat')); ?></p>
			<?php endif; ?>
			<?php if ({{PREFIX}}_jenis_berita()) : ?>
				<p class="{{PREFIX}}-footer__teks"><?php echo esc_html({{PREFIX}}_data('slogan')); ?></p>
			<?php else : ?>
				<p class="{{PREFIX}}-footer__teks">Area layanan: <?php echo esc_html({{PREFIX}}_data('area')); ?></p>
			<?php endif; ?>
		</div>

		<div class="{{PREFIX}}-footer__kolom">
			<?php if ({{PREFIX}}_jenis_berita()) : ?>
				<p class="{{PREFIX}}-footer__judul">Rubrik</p>
				<ul class="{{PREFIX}}-footer__daftar">
					<?php foreach ({{PREFIX}}_rubrik() as $r) : ?>
						<li><?php if ($r['url']) : ?><a href="<?php echo esc_url($r['url']); ?>"><?php echo esc_html($r['judul']); ?></a><?php else : echo esc_html($r['judul']); endif; ?></li>
					<?php endforeach; ?>
				</ul>
			<?php else : ?>
				<p class="{{PREFIX}}-footer__judul">Layanan</p>
				<ul class="{{PREFIX}}-footer__daftar">
					<?php foreach ((array) {{PREFIX}}_data('layanan') as $layanan) : ?>
						<li><?php echo esc_html($layanan['judul']); ?></li>
					<?php endforeach; ?>
				</ul>
			<?php endif; ?>
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

		<?php
		// Hanya kontak publik yang benar-benar ada; kontak pribadi pemilik dari
		// biodata form tidak pernah ditampilkan. Tanpa kontak & tanpa halaman
		// pemesanan, kolomnya tidak dicetak (dulu judul "Kontak" tampil kosong).
		$telp = trim((string) {{PREFIX}}_data('telp'));
		$email_publik = trim((string) {{PREFIX}}_data('email_publik'));
		$pemesanan = get_page_by_path('pemesanan');
		?>
		<?php if (($telp !== '' && $telp !== '-') || $email_publik !== '' || $pemesanan) : ?>
		<div class="{{PREFIX}}-footer__kolom">
			<p class="{{PREFIX}}-footer__judul">Kontak</p>
			<?php if (($telp !== '' && $telp !== '-') || $email_publik !== '') : ?>
				<p class="{{PREFIX}}-footer__teks">
					<?php if ($telp !== '' && $telp !== '-') : ?>
						<a href="<?php echo esc_url({{PREFIX}}_wa_link()); ?>" target="_blank" rel="noopener nofollow">
							<?php echo esc_html($telp); ?> (WhatsApp)
						</a><br />
					<?php endif; ?>
					<?php if ($email_publik !== '') : ?>
						<a href="mailto:<?php echo esc_attr($email_publik); ?>"><?php echo esc_html($email_publik); ?></a>
					<?php endif; ?>
				</p>
			<?php endif; ?>
			<?php if ($pemesanan) : ?>
				<p class="{{PREFIX}}-footer__teks">
					<a class="{{PREFIX}}-btn {{PREFIX}}-btn--utama {{PREFIX}}-btn--kecil"
						href="<?php echo esc_url(get_permalink($pemesanan)); ?>">Ajukan Pemesanan</a>
				</p>
			<?php endif; ?>
		</div>
		<?php endif; ?>

	</div>

	<div class="{{PREFIX}}-footer__bawah">
		<div class="{{PREFIX}}-wrap">
			<p>&copy; <?php echo esc_html(date_i18n('Y')); ?> <?php echo esc_html({{PREFIX}}_data('nama')); ?>. Seluruh hak cipta dilindungi.</p>
		</div>
	</div>
</footer>
<?php endif; ?>

</div><!-- #page -->

<?php wp_footer(); ?>

</body>

</html>
