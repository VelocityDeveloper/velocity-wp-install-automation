<?php
/** vb/step — satu langkah. */
$a = $attributes;
echo '<li ' . get_block_wrapper_attributes( array( 'class' => 'vb-step' ) ) . '>'; // phpcs:ignore
echo '<span class="vb-step__num" aria-hidden="true">' . vb_ikon( $a['icon'] ?? '', 'vb-ikon' ) . '</span>'; // phpcs:ignore
echo '<h3 class="vb-step__title">' . wp_kses_post( $a['title'] ?? '' ) . '</h3>';
if ( ! empty( $a['text'] ) ) {
	echo '<p class="vb-step__text">' . wp_kses_post( $a['text'] ) . '</p>';
}
echo '</li>';
