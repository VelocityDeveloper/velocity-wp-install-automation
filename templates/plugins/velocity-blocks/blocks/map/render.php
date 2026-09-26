<?php
/** vb/map — Google Maps sematan. */
$cari = trim( (string) ( $attributes['query'] ?? '' ) );
$cari = $cari ? $cari : vb_data( 'peta' );
if ( ! $cari ) {
	$b    = vb_kontak_pertama( 'alamat' );
	$cari = $b ? $b['isi'] : '';
}
if ( ! $cari ) {
	echo '<div ' . get_block_wrapper_attributes( array( 'class' => 'vb-kosong' ) ) . '>Peta: isi "Pencarian Google Maps" di Tampilan → Data Situs.</div>'; // phpcs:ignore
	return;
}
printf(
	'<div %s><iframe title="Map" src="%s" style="height:%dpx" loading="lazy" referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe></div>',
	get_block_wrapper_attributes( array( 'class' => 'vb-map' ) ), // phpcs:ignore
	esc_url( 'https://www.google.com/maps?q=' . rawurlencode( $cari ) . '&output=embed' ),
	max( 200, min( 800, (int) ( $attributes['height'] ?? 380 ) ) )
);
