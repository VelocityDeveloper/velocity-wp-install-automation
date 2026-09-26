<?php
/** vb/icon-box — ikon + judul + teks + tautan. */
$a     = $attributes;
$kelas = sprintf(
	'vb-iconbox vb-layout-%s vb-box-%s vb-ikonstyle-%s vb-align-%s',
	sanitize_html_class( $a['layout'] ?? 'top' ),
	sanitize_html_class( $a['boxStyle'] ?? 'card' ),
	sanitize_html_class( $a['iconStyle'] ?? 'soft' ),
	sanitize_html_class( $a['align'] ?? 'left' )
);
$url = $a['url'] ?? '';
echo '<div ' . get_block_wrapper_attributes( array( 'class' => $kelas ) ) . '>'; // phpcs:ignore
echo vb_ikon( $a['icon'] ?? '', 'vb-ikon vb-iconbox__icon', $a['iconUrl'] ?? '' ); // phpcs:ignore -- SVG pustaka.
echo '<div class="vb-iconbox__body">';
if ( ! empty( $a['title'] ) ) {
	$judul = wp_kses_post( $a['title'] );
	if ( $url && empty( $a['linkLabel'] ) ) {
		$judul = '<a' . vb_atribut_tautan( $url, ! empty( $a['newTab'] ) ) . '>' . $judul . '</a>';
	}
	echo '<h3 class="vb-iconbox__title">' . $judul . '</h3>'; // phpcs:ignore
}
if ( ! empty( $a['text'] ) ) {
	echo '<p class="vb-iconbox__text">' . wp_kses_post( $a['text'] ) . '</p>';
}
if ( $url && ! empty( $a['linkLabel'] ) ) {
	echo '<a class="vb-iconbox__link"' . vb_atribut_tautan( $url, ! empty( $a['newTab'] ) ) . '>' . wp_kses_post( $a['linkLabel'] ) . vb_ikon( 'arrow-right', 'vb-ikon vb-ikon--kecil' ) . '</a>'; // phpcs:ignore
}
echo '</div></div>';
