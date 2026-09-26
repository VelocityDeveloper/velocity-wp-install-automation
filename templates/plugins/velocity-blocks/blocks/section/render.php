<?php
/** vb/section — wadah seksi. $content = blok di dalamnya. */
$a      = $attributes;
$bg     = sanitize_html_class( $a['bg'] ?? 'none' );
$gelap  = in_array( $bg, array( 'dark', 'primary' ), true ) || ! empty( $a['bgUrl'] );
$tone   = $a['tone'] ?? 'auto';
$gelap  = 'auto' === $tone ? $gelap : ( 'light' === $tone );
$kelas  = array(
	'vb-section',
	'vb-bg-' . $bg,
	'vb-pad-' . sanitize_html_class( $a['padding'] ?? 'lg' ),
	'vb-valign-' . sanitize_html_class( $a['valign'] ?? 'center' ),
	$gelap ? 'vb-tone-light' : 'vb-tone-dark',
	vb_kelas_align( $a ),
);
$gaya = '';
if ( 'custom' === $bg && ! empty( $a['bgColor'] ) ) {
	$gaya .= 'background-color:' . esc_attr( $a['bgColor'] ) . ';';
}
if ( ! empty( $a['minHeight'] ) ) {
	$gaya .= 'min-height:' . (int) $a['minHeight'] . 'vh;';
}
$latar = '';
if ( ! empty( $a['bgUrl'] ) ) {
	$kelas[] = 'vb-has-media';
	$alt     = '';
	$latar  .= sprintf(
		'<img class="vb-section__media" src="%s" alt="%s" loading="%s" decoding="async" />',
		esc_url( $a['bgUrl'] ),
		esc_attr( $alt ),
		! empty( $a['minHeight'] ) ? 'eager' : 'lazy'
	);
	$latar  .= sprintf(
		'<span class="vb-section__overlay vb-overlay-%s" style="opacity:%s" aria-hidden="true"></span>',
		sanitize_html_class( $a['overlayType'] ?? 'solid' ),
		esc_attr( max( 0, min( 100, (int) ( $a['overlay'] ?? 60 ) ) ) / 100 )
	);
}
$wrapper = get_block_wrapper_attributes( array( 'class' => implode( ' ', array_filter( $kelas ) ), 'style' => $gaya ) );
printf(
	'<section %s>%s<div class="vb-section__inner vb-w-%s">%s</div></section>',
	$wrapper, // phpcs:ignore -- dari get_block_wrapper_attributes.
	$latar, // phpcs:ignore -- di-escape di atas.
	esc_attr( sanitize_html_class( $a['width'] ?? 'wide' ) ),
	$content // phpcs:ignore -- isi blok dalam.
);
