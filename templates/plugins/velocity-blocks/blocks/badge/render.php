<?php
/** vb/badge — pil berikon. */
$a = $attributes;
printf(
	'<span %s>%s<span>%s</span></span>',
	get_block_wrapper_attributes( array( 'class' => 'vb-badge' ) ), // phpcs:ignore
	vb_ikon( $a['icon'] ?? '', 'vb-ikon' ), // phpcs:ignore
	wp_kses_post( $a['text'] ?? '' )
);
