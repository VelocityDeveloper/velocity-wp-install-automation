<?php
/** vb/box — kotak wadah. $content = blok di dalamnya. */
$a     = $attributes;
$kelas = 'vb-box vb-box--' . sanitize_html_class( $a['boxStyle'] ?? 'shadow' ) . ' vb-boxpad-' . sanitize_html_class( $a['padding'] ?? 'md' ) . ' vb-gap-' . sanitize_html_class( $a['gap'] ?? 'sm' );
if ( ! empty( $a['fill'] ) ) {
	$kelas .= ' vb-box--fill';
}
printf( '<div %s>%s</div>', get_block_wrapper_attributes( array( 'class' => $kelas ) ), $content ); // phpcs:ignore
