<?php
/** vb/heading — label kecil + judul + subjudul. */
$a     = $attributes;
$level = max( 1, min( 6, (int) ( $a['level'] ?? 2 ) ) );
$kelas = 'vb-heading vb-align-' . sanitize_html_class( $a['align'] ?? 'left' ) . ' vb-size-' . sanitize_html_class( $a['size'] ?? 'lg' );
echo '<div ' . get_block_wrapper_attributes( array( 'class' => $kelas ) ) . '>'; // phpcs:ignore
if ( ! empty( $a['pill'] ) ) {
	echo '<p class="vb-heading__pill"><span>' . wp_kses_post( $a['pill'] ) . '</span></p>';
}
if ( ! empty( $a['eyebrow'] ) ) {
	echo '<p class="vb-heading__eyebrow">' . wp_kses_post( $a['eyebrow'] ) . '</p>';
}
if ( ! empty( $a['title'] ) ) {
	printf( '<h%1$d class="vb-heading__title">%2$s</h%1$d>', $level, wp_kses_post( $a['title'] ) ); // phpcs:ignore
}
if ( ! empty( $a['divider'] ) ) {
	echo '<span class="vb-heading__divider" aria-hidden="true"></span>';
}
if ( ! empty( $a['subtitle'] ) ) {
	echo '<p class="vb-heading__subtitle">' . wp_kses_post( $a['subtitle'] ) . '</p>';
}
echo '</div>';
