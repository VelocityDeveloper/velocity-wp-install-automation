<?php
/**
 * vb/rentals — kartu unit dari CPT vb_sewa (menu Scooter).
 * Tombol membuka WhatsApp dengan pesan berisi nama unit ({nama} diganti judul unit).
 */
$a     = $attributes;
$unit  = function_exists( 'vb_daftar_sewa' ) ? vb_daftar_sewa( (int) ( $a['count'] ?? 0 ) ) : array();
$gaya  = sprintf(
	'--vb-cols:%d;--vb-cols-t:%d;--vb-cols-m:%d;--vb-rasio:%s;',
	max( 1, min( 6, (int) ( $a['columns'] ?? 4 ) ) ),
	max( 1, min( 4, (int) ( $a['columnsTablet'] ?? 2 ) ) ),
	max( 1, min( 2, (int) ( $a['columnsMobile'] ?? 1 ) ) ),
	preg_match( '#^\d+/\d+$#', $a['ratio'] ?? '' ) ? $a['ratio'] : '4/3'
);
echo '<div ' . get_block_wrapper_attributes( array( 'class' => 'vb-rentals ' . vb_kelas_align( $a ), 'style' => $gaya ) ) . '>'; // phpcs:ignore
if ( ! $unit ) {
	echo '<p class="vb-kosong">Belum ada unit. Tambahkan lewat menu Scooter (Sewa) di wp-admin.</p>';
}
foreach ( $unit as $p ) {
	$nama   = get_the_title( $p );
	$harga  = trim( (string) get_post_meta( $p->ID, 'vb_harga', true ) );
	$satuan = trim( (string) get_post_meta( $p->ID, 'vb_satuan', true ) );
	$merek  = trim( (string) get_post_meta( $p->ID, 'vb_merek', true ) );
	$pesan  = trim( (string) get_post_meta( $p->ID, 'vb_pesan', true ) );
	$pesan  = $pesan ? $pesan : str_replace( '{nama}', $nama, (string) ( $a['waMessage'] ?? '' ) );
	$foto   = get_the_post_thumbnail( $p, 'medium_large', array( 'class' => 'vb-rent__img', 'alt' => $nama, 'sizes' => '(max-width: 600px) 90vw, 300px' ) );
	echo '<article class="vb-rent">';
	echo '<div class="vb-rent__media">' . ( $foto ? $foto : '<span class="vb-rent__img vb-rent__img--kosong">' . vb_ikon( 'motorbike', 'vb-ikon' ) . '</span>' ); // phpcs:ignore
	if ( '' !== $harga ) {
		printf( '<p class="vb-rent__harga"><span class="vb-rent__angka">%s</span>%s</p>', esc_html( $harga ), $satuan ? '<span class="vb-rent__satuan">' . esc_html( $satuan ) . '</span>' : '' ); // phpcs:ignore
	} else {
		printf( '<p class="vb-rent__harga vb-rent__harga--tanya"><span class="vb-rent__angka">%s</span></p>', esc_html( $a['emptyPrice'] ?? '' ) );
	}
	echo '</div><div class="vb-rent__body">';
	echo '<h3 class="vb-rent__title">' . esc_html( $nama ) . '</h3>';
	if ( $merek ) {
		echo '<p class="vb-rent__merek">' . esc_html( $merek ) . '</p>';
	}
	if ( ! empty( $a['buttonText'] ) ) {
		printf(
			'<a class="vb-btn vb-btn--primary vb-btn--sm vb-rent__btn" href="%s" target="_blank" rel="noopener">%s<span class="vb-btn__text">%s</span></a>',
			esc_url( vb_wa_link( $pesan ) ), vb_ikon( 'whatsapp', 'vb-ikon vb-btn__icon' ), esc_html( $a['buttonText'] ) // phpcs:ignore
		);
	}
	echo '</div></article>';
}
echo '</div>';
