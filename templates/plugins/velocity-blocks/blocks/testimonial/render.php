<?php
/** vb/testimonial — satu kartu testimoni. Tanpa foto = inisial nama. */
$a      = $attributes;
$nama   = trim( wp_strip_all_tags( $a['name'] ?? '' ) );
$bintang = max( 0, min( 5, (int) ( $a['rating'] ?? 5 ) ) );
$inisial = '';
foreach ( array_slice( preg_split( '/\s+/', $nama ), 0, 2 ) as $kata ) {
	$inisial .= mb_strtoupper( mb_substr( $kata, 0, 1 ) );
}
echo '<figure ' . get_block_wrapper_attributes( array( 'class' => 'vb-testi__item' ) ) . '>'; // phpcs:ignore
echo '<span class="vb-testi__mark" aria-hidden="true">&ldquo;</span>';
if ( $bintang ) {
	printf( '<p class="vb-testi__stars" aria-label="%1$d out of 5 stars">%2$s</p>', $bintang, str_repeat( '★', $bintang ) . '<span class="vb-testi__stars-off">' . str_repeat( '★', 5 - $bintang ) . '</span>' ); // phpcs:ignore
}
echo '<blockquote class="vb-testi__quote">' . wp_kses_post( $a['quote'] ?? '' ) . '</blockquote>';
echo '<figcaption class="vb-testi__who">';
if ( ! empty( $a['photoId'] ) && wp_attachment_is_image( (int) $a['photoId'] ) ) {
	echo wp_get_attachment_image( (int) $a['photoId'], 'thumbnail', false, array( 'class' => 'vb-testi__avatar', 'alt' => $nama ) );
} elseif ( ! empty( $a['photoUrl'] ) ) {
	echo '<img class="vb-testi__avatar" src="' . esc_url( $a['photoUrl'] ) . '" alt="' . esc_attr( $nama ) . '" loading="lazy" />';
} else {
	echo '<span class="vb-testi__avatar vb-testi__avatar--inisial" aria-hidden="true">' . esc_html( $inisial ) . '</span>';
}
echo '<span class="vb-testi__meta"><strong class="vb-testi__name">' . wp_kses_post( $a['name'] ?? '' ) . '</strong>';
if ( ! empty( $a['role'] ) ) {
	echo '<span class="vb-testi__role">' . wp_kses_post( $a['role'] ) . '</span>';
}
echo '</span></figcaption></figure>';
