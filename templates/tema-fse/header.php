<?php
/**
 * Header untuk halaman yang dirender plugin lewat get_header() (VD Store: arsip, kategori,
 * detail produk). Tema blok tanpa berkas ini membuat WordPress memakai header theme-compat
 * lama: judul situs polos tanpa header/footer tema (yukpergimancing.com/produk/, 2026-09-17).
 *
 * Template part blok dirender SEBELUM wp_head supaya CSS & skrip bloknya ikut dimuat di <head>.
 */

defined('ABSPATH') || exit;

$GLOBALS['velocity_fse_footer_html'] = do_blocks('<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->');
$velocity_fse_header_html = do_blocks('<!-- wp:template-part {"slug":"header","tagName":"header"} /-->');
?><!doctype html>
<html <?php language_attributes(); ?>>
<head>
<meta charset="<?php bloginfo('charset'); ?>">
<meta name="viewport" content="width=device-width, initial-scale=1">
<?php wp_head(); ?>
</head>
<body <?php body_class('vf-halaman-plugin'); ?>>
<?php wp_body_open(); ?>
<div class="wp-site-blocks">
<?php echo $velocity_fse_header_html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
<?php if (!empty($GLOBALS['velocity_fse_judul_pita'])) : ?>
<div class="wp-block-group vf-judul-halaman vf-judul-halaman--plugin has-latar-background-color has-background"><h1 class="wp-block-post-title"><?php echo esc_html($GLOBALS['velocity_fse_judul_pita']); ?></h1></div>
<?php endif; ?>
<main class="vf-halaman-plugin__isi">
