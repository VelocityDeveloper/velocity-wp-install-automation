<?php
/**
 * Plugin Name: Velocity Blocks
 * Description: Pustaka blok siap pakai ala page builder: seksi, judul, kotak ikon, grid, wadah geser, tombol, statistik, langkah, kartu, kartu paket, portofolio, katalog produk, daftar sewa + form booking WhatsApp, remah halaman, kontak, form pemesanan, serta blok portal berita (Judul Rubrik, Daftar Berita, Kotak) + pola seksi berita. Semua isi diedit langsung di kanvas (ketik teks, pilih ikon, atur tautan), blok bisa di-drag, disalin, dan dihapus.
 * Version: 1.9.1
 * Requires at least: 6.6
 * Requires PHP: 7.4
 * Author: Velocity Developer
 * Author URI: https://velocitydeveloper.com
 * Text Domain: velocity-blocks
 */

defined( 'ABSPATH' ) || exit;

define( 'VB_VERSI', '1.9.1' );
define( 'VB_DIR', plugin_dir_path( __FILE__ ) );
define( 'VB_URL', plugin_dir_url( __FILE__ ) );

/**
 * Modul opsional. Situs yang tidak berjualan barang tidak perlu katalog produk, jadi
 * modulnya dimatikan lewat opsi `vb_modul` (array kunci => 0/1) dan blok katalognya
 * tidak ikut didaftarkan. Belum pernah disetel = semua modul menyala.
 */
function vb_modul( $nama ) {
	$opsi = get_option( 'vb_modul', array() );
	return ! is_array( $opsi ) || ! isset( $opsi[ $nama ] ) ? true : (bool) $opsi[ $nama ];
}

/** Blok yang ikut mati bila modulnya dimatikan. */
function vb_blok_modul() {
	return array(
		'products'        => 'produk',
		'product-details' => 'produk',
		'rfq-form'        => 'rfq',
		'portfolio'       => 'portofolio',
		'rentals'         => 'sewa',
		'booking-form'    => 'sewa',
		'posts'           => 'berita',
		'news-heading'    => 'berita',
	);
}

require VB_DIR . 'inc/ikon.php';
require VB_DIR . 'inc/situs.php';
if ( vb_modul( 'produk' ) ) {
	require VB_DIR . 'inc/produk.php';
}
if ( vb_modul( 'rfq' ) ) {
	require VB_DIR . 'inc/rfq.php';
}
if ( vb_modul( 'portofolio' ) ) {
	require VB_DIR . 'inc/portofolio.php';
}
if ( vb_modul( 'sewa' ) ) {
	require VB_DIR . 'inc/sewa.php';
}
if ( vb_modul( 'berita' ) ) {
	require VB_DIR . 'inc/berita.php';
}

add_action( 'init', function () {
	wp_register_style( 'vb-blok', VB_URL . 'assets/blok.css', array(), VB_VERSI );
	wp_register_script( 'vb-view', VB_URL . 'assets/view.js', array(), VB_VERSI, array( 'strategy' => 'defer', 'in_footer' => true ) );
	wp_register_script(
		'vb-editor',
		VB_URL . 'assets/editor.js',
		array( 'wp-blocks', 'wp-block-editor', 'wp-components', 'wp-element', 'wp-i18n', 'wp-data', 'wp-rich-text', 'wp-server-side-render', 'wp-compose' ),
		VB_VERSI,
		true
	);
	wp_add_inline_script(
		'vb-editor',
		'window.vbData=' . wp_json_encode( array(
			'ikon'     => vb_daftar_ikon(),
			'kategori' => vb_kategori_ikon(),
			'wa'       => vb_data( 'wa' ),
			'modul'    => array( 'produk' => vb_modul( 'produk' ), 'rfq' => vb_modul( 'rfq' ), 'portofolio' => vb_modul( 'portofolio' ), 'sewa' => vb_modul( 'sewa' ), 'berita' => vb_modul( 'berita' ) ),
		) ) . ';',
		'before'
	);
	wp_register_style( 'vb-editor', VB_URL . 'assets/editor.css', array(), VB_VERSI );

	$modul_blok = vb_blok_modul();
	foreach ( glob( VB_DIR . 'blocks/*/block.json' ) as $berkas ) {
		$nama = basename( dirname( $berkas ) );
		if ( isset( $modul_blok[ $nama ] ) && ! vb_modul( $modul_blok[ $nama ] ) ) {
			continue;
		}
		register_block_type( dirname( $berkas ) );
	}
	register_block_pattern_category( 'velocity-blocks', array( 'label' => 'Velocity Blocks — Seksi' ) );
} );

/**
 * Warna & font blok mengikuti preset tema aktif (palet velocity-fse, atau slug umum
 * tema lain), jadi ganti warna di Styles ikut mengubah blok. Slug yang tidak ada di
 * palet dilewati dan tetap memakai warna bawaan blok.css. CSS situs yang menyetel
 * --vb-* sendiri (mis. di body) tetap menang.
 */
function vb_css_preset() {
	$palet = wp_get_global_settings( array( 'color', 'palette', 'theme' ) );
	$ada   = array();
	foreach ( is_array( $palet ) ? $palet : array() as $w ) {
		if ( ! empty( $w['slug'] ) ) {
			$ada[ $w['slug'] ] = true;
		}
	}
	$peta = array(
		'--vb-primary'     => array( 'primary', 'contrast' ),
		'--vb-primary-2'   => array( 'primary-gelap', 'primary' ),
		'--vb-deep'        => array( 'primary-gelap', 'primary' ),
		'--vb-accent'      => array( 'aksen', 'accent', 'secondary' ),
		'--vb-accent-2'    => array( 'aksen-teks', 'aksen', 'accent' ),
		'--vb-accent-text' => array( 'aksen-teks', 'aksen', 'accent' ),
		'--vb-on-accent'   => array( 'di-aksen', 'base' ),
		'--vb-heading'     => array( 'ink', 'contrast' ),
		'--vb-text'        => array( 'teks', 'contrast' ),
		'--vb-muted'       => array( 'abu' ),
		'--vb-line'        => array( 'garis' ),
		'--vb-soft'        => array( 'latar', 'base-2' ),
		'--vb-grey'        => array( 'latar', 'base-2' ),
		'--vb-white'       => array( 'putih', 'base' ),
	);
	$css = '';
	foreach ( $peta as $var => $calon ) {
		foreach ( $calon as $slug ) {
			if ( isset( $ada[ $slug ] ) ) {
				$css .= $var . ':var(--wp--preset--color--' . $slug . ');';
				break;
			}
		}
	}
	$font = wp_get_global_styles( array( 'elements', 'heading', 'typography', 'fontFamily' ) );
	if ( is_string( $font ) && preg_match( '/^var:preset\|font-family\|([a-z0-9-]+)$/', $font, $m ) ) {
		$css .= '--vb-font-head:var(--wp--preset--font-family--' . $m[1] . ');';
	}
	return $css ? ':root{' . $css . '}' : '';
}

add_action( 'init', function () {
	$css = vb_css_preset();
	if ( $css ) {
		wp_add_inline_style( 'vb-blok', $css );
	}
}, 99 );

/** Kategori blok sendiri di inserter supaya mudah dicari klien. */
add_filter( 'block_categories_all', function ( $kategori ) {
	array_unshift( $kategori, array( 'slug' => 'velocity-blocks', 'title' => 'Velocity Blocks', 'icon' => null ) );
	return $kategori;
} );

/**
 * Kelas lebar (alignfull/alignwide) untuk blok dinamis: dukungan `align` hanya dicetak
 * otomatis oleh save() di klien, blok ber-render PHP harus menambahkannya sendiri.
 */
function vb_kelas_align( $attributes ) {
	return empty( $attributes['align'] ) ? '' : 'align' . sanitize_html_class( $attributes['align'] );
}
