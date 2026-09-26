<?php
/**
 * vb/testimonials — carousel testimoni (scroll-snap + assets/view.js).
 * Tanpa JS tetap bisa digeser dengan jari/scroll mendatar.
 */
$a     = $attributes;
$jml   = isset( $block->parsed_block['innerBlocks'] ) ? count( $block->parsed_block['innerBlocks'] ) : 0;
$gaya  = sprintf(
	'--vb-pv:%d;--vb-pv-t:%d;--vb-pv-m:%d;',
	max( 1, min( 5, (int) ( $a['perView'] ?? 3 ) ) ),
	max( 1, min( 4, (int) ( $a['perViewTablet'] ?? 2 ) ) ),
	max( 1, min( 2, (int) ( $a['perViewMobile'] ?? 1 ) ) )
);
$attr = array(
	'class'              => 'vb-testi vb-testi--' . sanitize_html_class( $a['cardStyle'] ?? 'dark' ),
	'style'              => $gaya,
	'data-vb-autoplay'   => ! empty( $a['autoplay'] ) ? max( 3, (int) ( $a['interval'] ?? 6 ) ) : 0,
	'aria-roledescription' => 'carousel',
	'aria-label'         => 'Testimonials',
);
echo '<div ' . get_block_wrapper_attributes( $attr ) . '>'; // phpcs:ignore
echo '<div class="vb-testi__track" tabindex="0">' . $content . '</div>'; // phpcs:ignore
if ( $jml > 1 && ( ! empty( $a['showArrows'] ) || ! empty( $a['showDots'] ) ) ) {
	echo '<div class="vb-testi__nav">';
	if ( ! empty( $a['showArrows'] ) ) {
		echo '<button type="button" class="vb-testi__arrow vb-testi__prev" aria-label="Previous testimonial">' . vb_ikon( 'chevron-right', 'vb-ikon' ) . '</button>'; // phpcs:ignore
	}
	if ( ! empty( $a['showDots'] ) ) {
		echo '<div class="vb-testi__dots" role="tablist" aria-label="Choose testimonial"></div>';
	}
	if ( ! empty( $a['showArrows'] ) ) {
		echo '<button type="button" class="vb-testi__arrow vb-testi__next" aria-label="Next testimonial">' . vb_ikon( 'chevron-right', 'vb-ikon' ) . '</button>'; // phpcs:ignore
	}
	echo '</div>';
}
echo '</div>';
