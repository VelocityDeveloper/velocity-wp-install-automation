<?php
/**
 * Pustaka ikon blok (Lucide, lisensi ISC) — satu berkas assets/ikon.json dipakai
 * pemilih ikon di editor dan render PHP, jadi ikon di kanvas = ikon di situs.
 */

defined( 'ABSPATH' ) || exit;

function vb_daftar_ikon() {
	static $ikon = null;
	if ( null === $ikon ) {
		$json = file_get_contents( VB_DIR . 'assets/ikon.json' ); // phpcs:ignore -- berkas lokal plugin.
		$ikon = json_decode( (string) $json, true );
		$ikon = is_array( $ikon ) ? $ikon : array();
	}
	return $ikon;
}

/** Kelompok untuk tab pemilih ikon. Ikon yang tak tercantum masuk "Lainnya". */
function vb_kategori_ikon() {
	return array(
		'Pertanian & Alam' => array( 'leaf', 'sprout', 'wheat', 'trees', 'tree-palm', 'flower-2', 'apple', 'cherry', 'citrus', 'coffee', 'bean', 'nut', 'egg', 'droplet', 'droplets', 'flame', 'sun', 'wind', 'recycle' ),
		'Ekspor & Logistik' => array( 'globe', 'earth', 'map', 'map-pin', 'navigation', 'ship', 'anchor', 'container', 'truck', 'plane', 'package', 'package-check', 'boxes', 'warehouse', 'factory', 'building-2', 'store' ),
		'Kualitas & Dokumen' => array( 'award', 'badge-check', 'medal', 'trophy', 'star', 'shield', 'shield-check', 'file-badge', 'file-text', 'file-check', 'clipboard-check', 'scroll', 'stamp', 'scale', 'ruler', 'thermometer', 'microscope', 'flask-conical', 'search', 'check', 'circle-check', 'list-checks' ),
		'Bisnis' => array( 'handshake', 'users', 'user', 'user-check', 'target', 'trending-up', 'chart-column', 'piggy-bank', 'dollar-sign', 'coins', 'banknote', 'wallet', 'credit-card', 'briefcase', 'percent', 'tag', 'tags', 'gift', 'shopping-cart', 'shopping-bag', 'lightbulb', 'rocket', 'sparkles', 'zap', 'heart', 'hand-heart' ),
		'Website & Digital' => array( 'code', 'code-xml', 'file-code', 'monitor', 'laptop', 'smartphone', 'tablet', 'layout-dashboard', 'layout-grid', 'layout-template', 'panels-top-left', 'pen-tool', 'palette', 'type', 'sliders-horizontal', 'mouse-pointer-click', 'eye', 'pencil', 'megaphone', 'share-2', 'server', 'database', 'cloud', 'refresh-cw', 'bar-chart-3' ),
		'Transportasi & Wisata' => array( 'motorbike', 'bike', 'car', 'car-front', 'bus', 'fuel', 'route', 'compass', 'map-pinned', 'mountain', 'waves', 'sunset', 'tree-palm', 'tent-tree', 'umbrella', 'luggage', 'ticket', 'calendar-check', 'hand-coins', 'badge-dollar-sign', 'hard-hat', 'plane', 'truck', 'map', 'map-pin' ),
		'Kontak & Umum' => array( 'phone', 'phone-call', 'mail', 'message-circle', 'whatsapp', 'send', 'headphones', 'clock', 'calendar', 'timer', 'info', 'circle-help', 'house', 'link', 'external-link', 'download', 'upload', 'arrow-right', 'arrow-up-right', 'chevron-right', 'plus', 'minus', 'layers', 'grid-3x3', 'image', 'camera', 'video', 'play', 'quote', 'book-open', 'newspaper', 'graduation-cap', 'settings', 'wrench', 'hammer', 'lock', 'key', 'gauge' ),
	);
}

/**
 * SVG ikon. `$gambar` (URL) menang bila diisi — klien boleh mengunggah ikon sendiri.
 */
function vb_ikon( $nama, $kelas = 'vb-ikon', $gambar = '' ) {
	if ( $gambar ) {
		return sprintf( '<span class="%s vb-ikon--gambar"><img src="%s" alt="" loading="lazy" decoding="async" /></span>', esc_attr( $kelas ), esc_url( $gambar ) );
	}
	$ikon = vb_daftar_ikon();
	if ( ! $nama || ! isset( $ikon[ $nama ] ) ) {
		return '';
	}
	return sprintf(
		'<span class="%s" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" focusable="false">%s</svg></span>',
		esc_attr( $kelas ),
		$ikon[ $nama ] // Isi berkas plugin sendiri, bukan masukan pengguna.
	);
}

/** Atribut tautan standar blok: url, tab baru, rel. */
function vb_atribut_tautan( $url, $tab_baru = false ) {
	$html = ' href="' . esc_url( $url ) . '"';
	if ( $tab_baru ) {
		$html .= ' target="_blank" rel="noopener"';
	}
	return $html;
}
