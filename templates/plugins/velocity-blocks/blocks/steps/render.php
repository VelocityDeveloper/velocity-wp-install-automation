<?php
/** vb/steps — alur bernomor (nomor = counter CSS, ikut urutan drag). */
$jumlah = isset( $block->parsed_block['innerBlocks'] ) ? count( $block->parsed_block['innerBlocks'] ) : 3;
printf(
	'<ol %s>%s</ol>',
	get_block_wrapper_attributes( array( 'class' => 'vb-steps vb-steps--' . sanitize_html_class( $attributes['style'] ?? 'timeline' ), 'style' => '--vb-steps:' . max( 1, $jumlah ) ) ), // phpcs:ignore
	$content // phpcs:ignore
);
