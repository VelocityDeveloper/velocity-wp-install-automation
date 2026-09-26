<?php
/**
 * Modul berita: pola seksi siap sisip (Pembuka, Seksi Rubrik, Berita Terbaru + Samping,
 * Grid Berita) yang tersusun dari blok Velocity. Setelah disisipkan semua bagian jadi blok
 * biasa: tinggal pilih kategori di sidebar, ketik judul, atur tautan, drag/salin/hapus.
 */

defined( 'ABSPATH' ) || exit;

/** Markup satu blok (anak = null → blok dinamis tanpa isi). */
function vb_pola_blok( $nama, $attrs = array(), $anak = null ) {
	$json = $attrs ? ' ' . wp_json_encode( $attrs, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) : '';
	if ( null === $anak ) {
		return "<!-- wp:{$nama}{$json} /-->";
	}
	return "<!-- wp:{$nama}{$json} -->\n" . implode( "\n", (array) $anak ) . "\n<!-- /wp:{$nama} -->";
}

function vb_pola_seksi( $anak ) {
	return vb_pola_blok( 'vb/section', array( 'align' => 'full', 'bg' => 'none', 'padding' => 'xs', 'width' => 'wide' ), $anak );
}

function vb_pola_kotak_daftar( $judul, $posts, $url = '' ) {
	$kepala = array( 'title' => $judul, 'size' => 'sm', 'level' => 3 );
	if ( $url ) {
		$kepala['url'] = $url;
	}
	return vb_pola_blok( 'vb/box', array(), array( vb_pola_blok( 'vb/news-heading', $kepala ), vb_pola_blok( 'vb/posts', $posts ) ) );
}

/** Pembuka: berita utama besar + dua berita di bawahnya | kotak Terpopuler. */
function vb_pola_pembuka() {
	$kiri = vb_pola_blok( 'vb/box', array( 'boxStyle' => 'plain', 'padding' => 'none', 'gap' => 'md', 'fill' => false ), array(
		vb_pola_blok( 'vb/posts', array( 'layout' => 'overlay', 'count' => 1, 'imageHeight' => 440, 'titleSize' => 'xl' ) ),
		vb_pola_blok( 'vb/posts', array( 'layout' => 'overlay', 'count' => 2, 'offset' => 1, 'columns' => 2, 'columnsTablet' => 2, 'imageHeight' => 240 ) ),
	) );
	$kanan = vb_pola_kotak_daftar( 'Terpopuler', array( 'layout' => 'list', 'count' => 5, 'orderBy' => 'popular' ) );
	return vb_pola_seksi( vb_pola_blok( 'vb/grid', array( 'columns' => 2, 'columnsTablet' => 1, 'columnsMobile' => 1, 'gap' => 'md', 'ratio' => '2-1' ), array( $kiri, $kanan ) ) );
}

/** Satu rubrik: judul + Lihat Lainnya, lalu foto berlapis | Terpopuler | Terbaru. */
function vb_pola_rubrik( $kategori = 0, $nama = 'Nama Rubrik', $url = '' ) {
	$kepala = array( 'title' => $nama );
	if ( $url ) {
		$kepala['url'] = $url;
	}
	$grid = vb_pola_blok( 'vb/grid', array( 'columns' => 3, 'columnsTablet' => 2, 'columnsMobile' => 1, 'gap' => 'md' ), array(
		vb_pola_blok( 'vb/posts', array( 'layout' => 'overlay', 'count' => 1, 'category' => (int) $kategori, 'fill' => true, 'imageHeight' => 380 ) ),
		vb_pola_kotak_daftar( 'Terpopuler ' . $nama, array( 'layout' => 'list', 'count' => 4, 'category' => (int) $kategori, 'orderBy' => 'popular' ) ),
		vb_pola_kotak_daftar( 'Terbaru ' . $nama, array( 'layout' => 'list', 'count' => 4, 'category' => (int) $kategori, 'offset' => 1 ) ),
	) );
	return vb_pola_seksi( array( vb_pola_blok( 'vb/news-heading', $kepala ), $grid ) );
}

/** Berita terbaru (daftar + ringkasan) | kolom samping berisi kotak-kotak rubrik. */
function vb_pola_terbaru( $url = '', $samping = array() ) {
	if ( ! $samping ) {
		$samping = array( array( 0, 'Pilihan Redaksi' ), array( 0, 'Rubrik Lain' ) );
	}
	$kepala = array( 'title' => 'Berita Terbaru' );
	if ( $url ) {
		$kepala['url'] = $url;
	}
	$kotak = array();
	foreach ( $samping as $s ) {
		$kotak[] = vb_pola_kotak_daftar( $s[1], array( 'layout' => 'list', 'count' => 3, 'category' => (int) $s[0] ), $s[2] ?? '' );
	}
	$kanan = vb_pola_blok( 'vb/box', array( 'boxStyle' => 'plain', 'padding' => 'none', 'gap' => 'lg', 'fill' => false ), $kotak );
	$kiri  = vb_pola_blok( 'vb/box', array( 'fill' => false ), array( vb_pola_blok( 'vb/posts', array( 'layout' => 'excerpt', 'count' => 8 ) ) ) );
	return vb_pola_seksi( array(
		vb_pola_blok( 'vb/news-heading', $kepala ),
		vb_pola_blok( 'vb/grid', array( 'columns' => 2, 'columnsTablet' => 1, 'columnsMobile' => 1, 'gap' => 'lg', 'ratio' => '2-1', 'valign' => 'start' ), array( $kiri, $kanan ) ),
	) );
}

function vb_pola_grid_berita() {
	return vb_pola_seksi( array(
		vb_pola_blok( 'vb/news-heading', array( 'title' => 'Nama Rubrik' ) ),
		vb_pola_blok( 'vb/posts', array( 'layout' => 'grid', 'count' => 6, 'columns' => 3, 'columnsTablet' => 2, 'columnsMobile' => 1, 'gap' => 'md' ) ),
	) );
}

add_action( 'init', function () {
	register_block_pattern_category( 'vb-berita', array( 'label' => 'Velocity Blocks — Berita' ) );
	$pola = array(
		'pembuka' => array( 'Berita: Pembuka (utama + terpopuler)', vb_pola_pembuka() ),
		'rubrik'  => array( 'Berita: Seksi Rubrik (foto | terpopuler | terbaru)', vb_pola_rubrik() ),
		'terbaru' => array( 'Berita: Terbaru + Kolom Samping', vb_pola_terbaru() ),
		'grid'    => array( 'Berita: Grid Kartu per Rubrik', vb_pola_grid_berita() ),
	);
	foreach ( $pola as $slug => $p ) {
		register_block_pattern( 'velocity-blocks/berita-' . $slug, array(
			'title'      => $p[0],
			'categories' => array( 'vb-berita' ),
			'content'    => $p[1],
		) );
	}
}, 20 );
