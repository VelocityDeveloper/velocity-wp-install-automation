<?php
/** vb/card — kartu gambar. */
$a     = $attributes;
$url   = $a['url'] ?? '';
$tab   = ! empty( $a['newTab'] );
$kelas = 'vb-card vb-card--' . sanitize_html_class( $a['cardStyle'] ?? 'below' );
$gbr   = '';
if ( ! empty( $a['imageId'] ) && wp_attachment_is_image( (int) $a['imageId'] ) ) {
	$gbr = wp_get_attachment_image( (int) $a['imageId'], 'large', false, array( 'class' => 'vb-card__img', 'alt' => wp_strip_all_tags( $a['title'] ?? '' ), 'sizes' => '(max-width: 600px) 100vw, 400px' ) );
} elseif ( ! empty( $a['imageUrl'] ) ) {
	$gbr = '<img class="vb-card__img" src="' . esc_url( $a['imageUrl'] ) . '" alt="' . esc_attr( wp_strip_all_tags( $a['title'] ?? '' ) ) . '" loading="lazy" />';
}
echo '<div ' . get_block_wrapper_attributes( array( 'class' => $kelas, 'style' => '--vb-ratio:' . esc_attr( preg_replace( '#[^0-9/.]#', '', $a['ratio'] ?? '4/3' ) ) ) ) . '>'; // phpcs:ignore
echo '<div class="vb-card__media">' . ( $url ? '<a' . vb_atribut_tautan( $url, $tab ) . ' tabindex="-1" aria-hidden="true">' . $gbr . '</a>' : $gbr ) . '</div>'; // phpcs:ignore
echo '<div class="vb-card__body">';
if ( ! empty( $a['title'] ) ) {
	$judul = wp_kses_post( $a['title'] );
	echo '<h3 class="vb-card__title">' . ( $url ? '<a' . vb_atribut_tautan( $url, $tab ) . '>' . $judul . '</a>' : $judul ) . '</h3>'; // phpcs:ignore
}
if ( ! empty( $a['text'] ) ) {
	echo '<p class="vb-card__text">' . wp_kses_post( $a['text'] ) . '</p>';
}
if ( $url && ! empty( $a['linkLabel'] ) ) {
	echo '<a class="vb-card__link"' . vb_atribut_tautan( $url, $tab ) . '>' . wp_kses_post( $a['linkLabel'] ) . vb_ikon( 'arrow-right', 'vb-ikon vb-ikon--kecil' ) . '</a>'; // phpcs:ignore
}
echo '</div></div>';
