<?php

/**
 * Header desain custom.
 *
 * Menggantikan header tema induk supaya susunannya mengikuti referensi klien:
 * logo di kiri, menu utama, lalu tombol ajakan + nomor telepon di kanan. Di HP
 * menu jadi panel geser dengan tombol sendiri (tanpa Bootstrap), karena klien
 * Paket G umumnya meminta tampilan HP yang lebih rapi.
 *
 * Pembungkus `.site` dan `#wrapper-content` tetap dipakai seperti tema induk —
 * footer.php menutup keduanya, dan template bawaan induk mengandalkan strukturnya.
 */

defined('ABSPATH') || exit;
?>
<!DOCTYPE html>
<html <?php language_attributes(); ?>>

<head>
	<meta charset="<?php bloginfo('charset'); ?>">
	<meta name="viewport" content="width=device-width, initial-scale=1">
	<?php wp_head(); ?>
</head>

<body <?php body_class(); ?>>
	<?php do_action('wp_body_open'); ?>

	<a class="{{PREFIX}}-lewati" href="#main">Lewati ke isi</a>

	<div class="site" id="page">

		<?php if ({{PREFIX}}_jenis_berita()) : ?>
			<?php // Portal berita: baris tanggal hari ini + slogan media di atas header. ?>
			<div class="{{PREFIX}}-topbar">
				<div class="{{PREFIX}}-wrap {{PREFIX}}-topbar__isi">
					<span><?php echo esc_html({{PREFIX}}_hari_ini()); ?></span>
					<?php if ({{PREFIX}}_data('slogan')) : ?>
						<span class="{{PREFIX}}-topbar__slogan"><?php echo esc_html({{PREFIX}}_data('slogan')); ?></span>
					<?php endif; ?>
				</div>
			</div>
		<?php endif; ?>

		<header class="{{PREFIX}}-header" id="{{PREFIX}}-header">
			<div class="{{PREFIX}}-wrap {{PREFIX}}-header__bar">

				<div class="{{PREFIX}}-header__merek">
					<?php if (has_custom_logo()) : ?>
						<?php the_custom_logo(); ?>
						<?php if ({{PREFIX}}_gaya_compro()) : ?>
							<?php // Kepala halaman compro: nama merah + subjudul di sebelah logo. ?>
							<a class="{{PREFIX}}-header__identitas" href="<?php echo esc_url(home_url('/')); ?>" rel="home">
								<span class="{{PREFIX}}-header__nama-compro"><?php echo esc_html({{PREFIX}}_data('nama')); ?></span>
								<?php if ({{PREFIX}}_data('subjudul')) : ?>
									<span class="{{PREFIX}}-header__sub"><?php echo esc_html({{PREFIX}}_data('subjudul')); ?></span>
								<?php endif; ?>
							</a>
						<?php endif; ?>
					<?php else : ?>
						<a class="{{PREFIX}}-header__nama" href="<?php echo esc_url(home_url('/')); ?>" rel="home">
							<?php bloginfo('name'); ?>
						</a>
					<?php endif; ?>
				</div>

				<button class="{{PREFIX}}-header__tombol" type="button" aria-expanded="false"
					aria-controls="{{PREFIX}}-menu" aria-label="Buka menu">
					<span></span><span></span><span></span>
				</button>

				<div class="{{PREFIX}}-header__panel" id="{{PREFIX}}-menu">
					<?php
					wp_nav_menu(array(
						'theme_location' => 'primary',
						'container'      => 'nav',
						'container_class' => '{{PREFIX}}-nav',
						'menu_class'     => '{{PREFIX}}-nav__daftar',
						'depth'          => 2,
						'fallback_cb'    => false,
					));
					?>
					<div class="{{PREFIX}}-header__aksi">
						<?php // Tombol ini sudah membuka WhatsApp ke nomor yang sama, jadi
						      // nomornya tidak perlu ditulis lagi di sebelahnya. ?>
						<?php // Tanpa nomor WhatsApp publik, tombol menuju halaman kontak (bukan mailto). ?>
						<a class="{{PREFIX}}-btn {{PREFIX}}-btn--utama" href="<?php echo esc_url({{PREFIX}}_tautan_hubungi()); ?>"
							<?php echo {{PREFIX}}_ada_wa() ? 'target="_blank" rel="noopener nofollow"' : ''; ?>>Hubungi Kami</a>
					</div>
				</div>

			</div>
		</header>

		<div id="wrapper-content">
			<?php do_action('justg_before_wrapper_content'); ?>
