<?php
/** vb/logo-item — satu logo. */
$a     = $attributes;
$label = wp_strip_all_tags( $a['label'] ?? '' );
if ( ! empty( $a['imageId'] ) && wp_attachment_is_image( (int) $a['imageId'] ) ) {
	$img = wp_get_attachment_image( (int) $a['imageId'], 'medium', false, array( 'class' => 'vb-logos__img', 'alt' => $label, 'loading' => 'lazy' ) );
} elseif ( ! empty( $a['imageUrl'] ) ) {
	$img = '<img class="vb-logos__img" src="' . esc_url( $a['imageUrl'] ) . '" alt="' . esc_attr( $label ) . '" loading="lazy" />';
} else {
	$img = '<span class="vb-logos__img vb-logos__img--kosong">' . vb_ikon( 'image', 'vb-ikon' ) . '</span>';
}
$isi = $img . ( $label ? '<figcaption class="vb-logos__label">' . esc_html( $label ) . '</figcaption>' : '' );
if ( ! empty( $a['url'] ) ) {
	$isi = '<a class="vb-logos__link"' . vb_atribut_tautan( $a['url'], ! empty( $a['newTab'] ) ) . '>' . $isi . '</a>';
}
echo '<figure class="vb-logos__item wp-block-vb-logo-item">' . $isi . '</figure>'; // phpcs:ignore
