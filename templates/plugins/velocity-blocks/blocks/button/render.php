<?php
/** vb/button — tombol berikon. Varian whatsapp tanpa URL = nomor Data Situs. */
$a       = $attributes;
$varian  = sanitize_html_class( $a['variant'] ?? 'primary' );
$url     = trim( (string) ( $a['url'] ?? '' ) );
$tab     = ! empty( $a['newTab'] );
if ( 'whatsapp' === $varian && ( '' === $url || 0 === strpos( $url, 'https://wa.me' ) ) ) {
	$url = vb_wa_link( $a['waMessage'] ?? '' );
	$tab = true;
}
$ikon  = $a['icon'] ?? '';
if ( 'whatsapp' === $varian && ! $ikon ) {
	$ikon = 'whatsapp';
}
$ikon  = vb_ikon( $ikon, 'vb-ikon vb-btn__icon' );
$teks  = '<span class="vb-btn__text">' . wp_kses_post( $a['text'] ?? '' ) . '</span>';
$isi   = 'after' === ( $a['iconPos'] ?? 'before' ) ? $teks . $ikon : $ikon . $teks;
$kelas = 'vb-btn vb-btn--' . $varian . ' vb-btn--' . sanitize_html_class( $a['size'] ?? 'md' );
$wrap  = get_block_wrapper_attributes( array( 'class' => 'vb-btn-wrap' ) );
if ( $url ) {
	printf( '<div %s><a class="%s"%s>%s</a></div>', $wrap, esc_attr( $kelas ), vb_atribut_tautan( $url, $tab ), $isi ); // phpcs:ignore
} else {
	printf( '<div %s><span class="%s">%s</span></div>', $wrap, esc_attr( $kelas ), $isi ); // phpcs:ignore
}
