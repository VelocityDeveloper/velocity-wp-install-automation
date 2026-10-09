<?php
/**
 * Velocity Landing: child theme landing page yang diatur lewat Customizer.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;

define('VLP_VERSI', '1.2.0');

require_once get_stylesheet_directory() . '/inc/skema.php';
require_once get_stylesheet_directory() . '/inc/template.php';
require_once get_stylesheet_directory() . '/inc/customizer.php';

add_action('after_setup_theme', function () {
	register_nav_menus(array('vlp_footer' => 'Footer Landing (kolom tautan)'));
}, 20);

add_action('wp_enqueue_scripts', function () {
	$font = str_replace(' ', '+', (string) vlp_mod('umum', 'font'));
	wp_enqueue_style('vlp-font', 'https://fonts.googleapis.com/css2?family=' . $font . ':wght@400;500;600;700&display=swap', array(), null);
	wp_enqueue_style('vlp-fontawesome', 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css', array(), '6.5.2');
	wp_enqueue_style('vlp-landing', get_stylesheet_directory_uri() . '/assets/css/landing.css', array('justg-styles'), VLP_VERSI);
	wp_add_inline_style('vlp-landing', vlp_css_variabel());
}, 30);

add_action('wp_head', function () {
	echo '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' . "\n";
}, 1);

add_filter('body_class', function ($kelas) {
	$kelas[] = 'vlp';
	if (!vlp_mod('umum', 'efek_cahaya')) {
		$kelas[] = 'vlp-tanpa-cahaya';
	}
	return $kelas;
});

// Halaman dalam (mis. Kebijakan Privasi) tampil satu kolom tanpa sidebar & breadcrumb induk.
add_action('wp', function () {
	remove_action('justg_before_content', 'justg_left_sidebar_check', 9);
	remove_action('justg_after_content', 'justg_right_sidebar_check', 9);
	remove_all_actions('justg_before_title');
});
