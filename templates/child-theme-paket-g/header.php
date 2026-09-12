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

		<header class="{{PREFIX}}-header" id="{{PREFIX}}-header">
			<div class="{{PREFIX}}-wrap {{PREFIX}}-header__bar">

				<div class="{{PREFIX}}-header__merek">
					<?php if (has_custom_logo()) : ?>
						<?php the_custom_logo(); ?>
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
						<a class="{{PREFIX}}-btn {{PREFIX}}-btn--utama" href="<?php echo esc_url({{PREFIX}}_wa_link()); ?>"
							target="_blank" rel="noopener nofollow">Hubungi Kami</a>
						<a class="{{PREFIX}}-header__telp" href="tel:<?php echo esc_attr(preg_replace('/\D/', '', {{PREFIX}}_data('telp'))); ?>">
							<?php echo esc_html({{PREFIX}}_data('telp')); ?>
						</a>
					</div>
				</div>

			</div>
		</header>

		<div id="wrapper-content">
			<?php do_action('justg_before_wrapper_content'); ?>
