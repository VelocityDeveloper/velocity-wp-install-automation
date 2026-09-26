<?php
/** vb/row — deret mendatar. */
$a     = $attributes;
$kelas = sprintf( 'vb-row vb-justify-%s vb-gap-%s vb-items-%s', sanitize_html_class( $a['justify'] ?? 'left' ), sanitize_html_class( $a['gap'] ?? 'sm' ), sanitize_html_class( $a['valign'] ?? 'center' ) );
printf( '<div %s>%s</div>', get_block_wrapper_attributes( array( 'class' => $kelas ) ), $content ); // phpcs:ignore
