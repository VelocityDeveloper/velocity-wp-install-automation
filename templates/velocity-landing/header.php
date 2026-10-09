<?php
/**
 * Header: tanpa menu di beranda (sesuai desain landing), bilah logo + WhatsApp di halaman lain.
 * Pembungkus #page & #wrapper-content mengikuti induk karena page.php induk memakainya.
 *
 * @package velocity-landing
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
	<?php wp_body_open(); ?>
	<div class="site" id="page">
		<?php if (!is_front_page()) : ?>
			<header class="vlp-atas">
				<div class="vlp-wadah vlp-atas-isi">
					<a class="vlp-atas-logo" href="<?php echo esc_url(home_url('/')); ?>">
						<?php
						$logo = vlp_img(vlp_mod('footer', 'logo'), get_bloginfo('name'), '', 'medium', '200px');
						echo $logo ? $logo : '<span class="vlp-atas-nama">' . esc_html(get_bloginfo('name')) . '</span>';
						?>
					</a>
					<a class="vlp-tombol" href="<?php echo esc_url(vlp_wa_url()); ?>"<?php echo vlp_target(); ?>><i class="fa-brands fa-whatsapp" aria-hidden="true"></i> WhatsApp</a>
				</div>
			</header>
		<?php endif; ?>
		<div id="wrapper-content">
