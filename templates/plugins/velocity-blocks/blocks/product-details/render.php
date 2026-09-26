<?php
/** vb/product-details — isi meta produk yang sedang dibuka. */
$post_id = isset( $block->context['postId'] ) ? (int) $block->context['postId'] : get_the_ID();
if ( ! $post_id || 'vb_produk' !== get_post_type( $post_id ) ) {
	if ( defined( 'REST_REQUEST' ) && REST_REQUEST ) {
		echo '<div class="vb-kosong">Detail Produk: tampil di halaman produk (varian, spesifikasi, kegunaan).</div>';
	}
	return;
}
$varian = array_filter( (array) vb_meta_produk( 'vb_varian', $post_id ) );
$spek   = array_filter( (array) vb_meta_produk( 'vb_spesifikasi', $post_id ), function ( $b ) {
	return is_array( $b ) && ( ! empty( $b['label'] ) || ! empty( $b['nilai'] ) );
} );
$guna   = trim( (string) vb_meta_produk( 'vb_kegunaan', $post_id ) );
$judul  = get_the_title( $post_id );
$rfq    = add_query_arg( 'product', rawurlencode( $judul ), home_url( $attributes['rfqUrl'] ?? '/contact/#rfq' ) );
$pesan  = sprintf( 'Hello, I would like to request a quotation for %s.', $judul );

echo '<div ' . get_block_wrapper_attributes( array( 'class' => 'vb-pdetail' ) ) . '>'; // phpcs:ignore
if ( $varian ) {
	echo '<div class="vb-pdetail__part"><h2 class="vb-pdetail__h">Available forms &amp; grades</h2><ul class="vb-pdetail__chips">';
	foreach ( $varian as $v ) {
		echo '<li>' . vb_ikon( 'circle-check', 'vb-ikon' ) . esc_html( $v ) . '</li>'; // phpcs:ignore
	}
	echo '</ul></div>';
}
if ( $spek ) {
	echo '<div class="vb-pdetail__part"><h2 class="vb-pdetail__h">Specifications</h2><table class="vb-pdetail__spec"><tbody>';
	foreach ( $spek as $b ) {
		printf( '<tr><th scope="row">%s</th><td>%s</td></tr>', esc_html( $b['label'] ?? '' ), esc_html( $b['nilai'] ?? '' ) );
	}
	echo '</tbody></table></div>';
}
if ( $guna ) {
	echo '<div class="vb-pdetail__part"><h2 class="vb-pdetail__h">Applications</h2><p>' . esc_html( $guna ) . '</p></div>';
}
echo '<div class="vb-row vb-justify-left vb-gap-sm vb-items-center vb-pdetail__cta">';
printf( '<a class="vb-btn vb-btn--accent vb-btn--md" href="%s">%s<span class="vb-btn__text">Request a Quote</span></a>', esc_url( $rfq ), vb_ikon( 'file-text', 'vb-ikon vb-btn__icon' ) ); // phpcs:ignore
printf( '<a class="vb-btn vb-btn--whatsapp vb-btn--md" href="%s" target="_blank" rel="noopener">%s<span class="vb-btn__text">Ask via WhatsApp</span></a>', esc_url( vb_wa_link( $pesan ) ), vb_ikon( 'whatsapp', 'vb-ikon vb-btn__icon' ) ); // phpcs:ignore
echo '</div></div>';
