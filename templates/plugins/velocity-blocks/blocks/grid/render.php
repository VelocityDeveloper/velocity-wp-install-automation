<?php
/** vb/grid — kolom responsif. */
$a    = $attributes;
$gaya = sprintf(
	'--vb-cols:%d;--vb-cols-t:%d;--vb-cols-m:%d;',
	max( 1, min( 8, (int) ( $a['columns'] ?? 3 ) ) ),
	max( 1, min( 6, (int) ( $a['columnsTablet'] ?? 2 ) ) ),
	max( 1, min( 4, (int) ( $a['columnsMobile'] ?? 1 ) ) )
);
$kelas = 'vb-grid vb-gap-' . sanitize_html_class( $a['gap'] ?? 'md' ) . ' vb-items-' . sanitize_html_class( $a['valign'] ?? 'stretch' );
if ( ! empty( $a['ratio'] ) ) {
	$kelas .= ' vb-ratio-' . sanitize_html_class( $a['ratio'] );
}
printf( '<div %s>%s</div>', get_block_wrapper_attributes( array( 'class' => $kelas, 'style' => $gaya ) ), $content ); // phpcs:ignore
