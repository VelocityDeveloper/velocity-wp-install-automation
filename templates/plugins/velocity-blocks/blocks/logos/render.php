<?php
/**
 * vb/logos — deretan logo berjalan (marquee CSS). Isi digandakan (aria-hidden) supaya putaran
 * mulus; animasi mati bila pengunjung memilih "kurangi gerakan" atau opsi animate dimatikan.
 */
$a    = $attributes;
$gaya = sprintf( '--vb-logo-dur:%ds;--vb-logo-h:%dpx;', max( 10, min( 120, (int) ( $a['speed'] ?? 35 ) ) ), max( 32, min( 160, (int) ( $a['logoHeight'] ?? 72 ) ) ) );
$kelas = 'vb-logos vb-logos--' . sanitize_html_class( $a['cardStyle'] ?? 'card' ) . ( empty( $a['showLabel'] ) ? ' vb-logos--tanpa-label' : '' ) . ( empty( $a['animate'] ) ? ' vb-logos--diam' : '' ) . ' ' . vb_kelas_align( $a );
$salin = preg_replace( '/\sid="[^"]*"/', '', $content );
$salin = str_replace( '<figure class="vb-logos__item', '<figure aria-hidden="true" class="vb-logos__item', $salin );
$salin = preg_replace( '/<a /', '<a tabindex="-1" ', $salin );
echo '<div ' . get_block_wrapper_attributes( array( 'class' => $kelas, 'style' => $gaya ) ) . '>'; // phpcs:ignore
echo '<div class="vb-logos__track"><div class="vb-logos__set">' . $content . '</div>'; // phpcs:ignore
if ( ! empty( $a['animate'] ) ) {
	echo '<div class="vb-logos__set" aria-hidden="true">' . $salin . '</div>'; // phpcs:ignore
}
echo '</div></div>';
