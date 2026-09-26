<?php
/**
 * vb/carousel — wadah geser umum (scroll-snap + assets/view.js), dipakai ulang oleh
 * seksi mana pun: kartu portofolio, kotak ikon, foto. Tanpa JS tetap bisa digeser
 * dengan jari/scroll mendatar, jadi isinya selalu terbaca.
 */
$a    = $attributes;
$jml  = isset( $block->parsed_block['innerBlocks'] ) ? count( $block->parsed_block['innerBlocks'] ) : 0;
$gaya = sprintf(
	'--vb-pv:%d;--vb-pv-t:%d;--vb-pv-m:%d;',
	max( 1, min( 6, (int) ( $a['perView'] ?? 3 ) ) ),
	max( 1, min( 4, (int) ( $a['perViewTablet'] ?? 2 ) ) ),
	max( 1, min( 2, (int) ( $a['perViewMobile'] ?? 1 ) ) )
);
$label = trim( (string) ( $a['label'] ?? '' ) );
$attr  = array(
	'class'                => trim( 'vb-carousel vb-carousel--' . sanitize_html_class( $a['tone'] ?? 'auto' ) . ' ' . vb_kelas_align( $a ) ),
	'style'                => $gaya,
	'data-vb-autoplay'     => ! empty( $a['autoplay'] ) ? max( 3, (int) ( $a['interval'] ?? 6 ) ) : 0,
	'data-vb-sebutan'      => $label ? $label : 'Item',
	'aria-roledescription' => 'carousel',
	'aria-label'           => $label ? $label : 'Geser untuk melihat lainnya',
);
echo '<div ' . get_block_wrapper_attributes( $attr ) . '>'; // phpcs:ignore
echo '<div class="vb-carousel__track" tabindex="0">' . $content . '</div>'; // phpcs:ignore
if ( $jml > 1 && ( ! empty( $a['showArrows'] ) || ! empty( $a['showDots'] ) ) ) {
	echo '<div class="vb-carousel__nav">';
	if ( ! empty( $a['showArrows'] ) ) {
		echo '<button type="button" class="vb-carousel__arrow vb-carousel__prev" aria-label="Sebelumnya">' . vb_ikon( 'chevron-right', 'vb-ikon' ) . '</button>'; // phpcs:ignore
	}
	if ( ! empty( $a['showDots'] ) ) {
		echo '<div class="vb-carousel__dots" role="tablist" aria-label="Pilih tampilan"></div>';
	}
	if ( ! empty( $a['showArrows'] ) ) {
		echo '<button type="button" class="vb-carousel__arrow vb-carousel__next" aria-label="Berikutnya">' . vb_ikon( 'chevron-right', 'vb-ikon' ) . '</button>'; // phpcs:ignore
	}
	echo '</div>';
}
echo '</div>';
