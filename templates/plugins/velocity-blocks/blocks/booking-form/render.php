<?php
/**
 * vb/booking-form — form singkat yang dikirim sebagai pesan WhatsApp (assets/view.js).
 * Tanpa JS: form GET ke wa.me dengan isian `text` sederhana tetap berfungsi.
 * Pilihan unit = judul unit terbit di menu Scooter (Sewa).
 */
$a     = $attributes;
$nomor = vb_nomor_wa( vb_data( 'wa' ) );
$uid   = wp_unique_id( 'vb-book-' );
$unit  = function_exists( 'vb_daftar_sewa' ) ? vb_daftar_sewa() : array();
$attr  = array(
	'class'          => 'vb-book',
	'data-vb-wa'     => $nomor,
	'data-vb-intro'  => wp_strip_all_tags( $a['intro'] ?? '' ),
);
echo '<div ' . get_block_wrapper_attributes( $attr ) . '>'; // phpcs:ignore
if ( ! empty( $a['title'] ) ) {
	echo '<h3 class="vb-book__title">' . wp_kses_post( $a['title'] ) . '</h3>';
}
printf( '<form class="vb-book__form" action="https://wa.me/%s" method="get" target="_blank">', esc_attr( $nomor ) );
printf(
	'<p class="vb-book__f vb-book__f--full"><label for="%1$s-n">%2$s</label><input id="%1$s-n" type="text" name="nama" required autocomplete="name" placeholder="%3$s" data-vb-label="%4$s" /></p>',
	esc_attr( $uid ), wp_kses_post( $a['labelName'] ?? '' ), esc_attr( $a['placeholderName'] ?? '' ), esc_attr( wp_strip_all_tags( $a['labelName'] ?? '' ) )
);
printf(
	'<p class="vb-book__f"><label for="%1$s-d">%2$s</label><input id="%1$s-d" type="date" name="tanggal" required min="%3$s" data-vb-label="%4$s" /></p>',
	esc_attr( $uid ), wp_kses_post( $a['labelDate'] ?? '' ), esc_attr( wp_date( 'Y-m-d' ) ), esc_attr( wp_strip_all_tags( $a['labelDate'] ?? '' ) )
);
printf( '<p class="vb-book__f"><label for="%1$s-u">%2$s</label><select id="%1$s-u" name="unit" required data-vb-label="%3$s"><option value="">%4$s</option>', esc_attr( $uid ), wp_kses_post( $a['labelUnit'] ?? '' ), esc_attr( wp_strip_all_tags( $a['labelUnit'] ?? '' ) ), esc_html( $a['placeholderUnit'] ?? '' ) );
foreach ( $unit as $p ) {
	$harga = trim( get_post_meta( $p->ID, 'vb_harga', true ) . ' ' . get_post_meta( $p->ID, 'vb_satuan', true ) );
	printf( '<option value="%1$s">%1$s%2$s</option>', esc_attr( get_the_title( $p ) ), $harga ? ' — ' . esc_html( $harga ) : '' );
}
echo '</select></p>';
echo '<input type="hidden" name="text" value="" />';
printf( '<p class="vb-book__f vb-book__f--full"><button type="submit" class="vb-btn vb-btn--primary vb-btn--md vb-book__btn"><span class="vb-btn__text">%s</span></button></p>', esc_html( wp_strip_all_tags( $a['buttonText'] ?? '' ) ) );
echo '</form>';
if ( ! empty( $a['note'] ) ) {
	echo '<p class="vb-book__note">' . wp_kses_post( $a['note'] ) . '</p>';
}
echo '</div>';
