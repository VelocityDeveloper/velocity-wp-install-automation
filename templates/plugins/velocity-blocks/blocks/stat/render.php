<?php
/** vb/stat — angka + label. */
$a = $attributes;
echo '<div ' . get_block_wrapper_attributes( array( 'class' => 'vb-stat' ) ) . '>'; // phpcs:ignore
echo vb_ikon( $a['icon'] ?? '', 'vb-ikon vb-stat__icon' ); // phpcs:ignore
echo '<p class="vb-stat__value">' . wp_kses_post( $a['value'] ?? '' ) . '</p>';
echo '<p class="vb-stat__label">' . wp_kses_post( $a['label'] ?? '' ) . '</p>';
echo '</div>';
