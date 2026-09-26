<?php
/** vb/contact-info — daftar kontak Data Situs. `show` kosong = semua jenis. */
$a     = $attributes;
$jenis = vb_jenis_kontak();
$tampil = array_filter( (array) ( $a['show'] ?? array() ) );
$baris = array_filter( vb_daftar( 'kontak' ), function ( $b ) use ( $tampil ) {
	return ! $tampil || in_array( $b['jenis'], $tampil, true );
} );
$maks = (int) ( $a['perJenis'] ?? 0 );
if ( $maks > 0 ) {
	$hitung = array();
	$baris  = array_filter( $baris, function ( $b ) use ( &$hitung, $maks ) {
		$hitung[ $b['jenis'] ] = ( $hitung[ $b['jenis'] ] ?? 0 ) + 1;
		return $hitung[ $b['jenis'] ] <= $maks;
	} );
}
echo '<ul ' . get_block_wrapper_attributes( array( 'class' => 'vb-contact vb-contact--' . sanitize_html_class( $a['layout'] ?? 'list' ) ) ) . '>'; // phpcs:ignore
if ( ! $baris ) {
	echo '<li class="vb-kosong">Isi kontak di Tampilan → Data Situs.</li>';
}
foreach ( $baris as $b ) {
	$label = $b['label'] ? $b['label'] : ( $jenis[ $b['jenis'] ][0] ?? '' );
	$isi   = nl2br( esc_html( 'email' === $b['jenis'] ? antispambot( $b['isi'] ) : $b['isi'] ) );
	$url   = vb_tautan_kontak( $b );
	$baru  = in_array( $b['jenis'], array( 'whatsapp', 'website', 'alamat' ), true );
	echo '<li class="vb-contact__item vb-contact--' . esc_attr( $b['jenis'] ) . '">';
	echo vb_ikon( $jenis[ $b['jenis'] ][1] ?? 'info', 'vb-ikon vb-contact__icon' ); // phpcs:ignore
	echo '<div class="vb-contact__body">';
	if ( ! empty( $a['showLabel'] ) && $label ) {
		echo '<span class="vb-contact__label">' . esc_html( $label ) . '</span>';
	}
	echo $url ? '<a class="vb-contact__value"' . vb_atribut_tautan( $url, $baru ) . '>' . $isi . '</a>' : '<span class="vb-contact__value">' . $isi . '</span>'; // phpcs:ignore
	echo '</div></li>';
}
echo '</ul>';
