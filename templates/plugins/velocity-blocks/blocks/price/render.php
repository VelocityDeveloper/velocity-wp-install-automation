<?php
/**
 * vb/price — kartu paket/layanan. Isi paket (daftar) dan tombol memakai blok anak biasa,
 * supaya klien bisa menambah/menghapus baris tanpa menyentuh kode.
 */
$a     = $attributes;
$kelas = 'vb-price' . ( ! empty( $a['featured'] ) ? ' vb-price--unggulan' : '' );
echo '<div ' . get_block_wrapper_attributes( array( 'class' => $kelas ) ) . '>'; // phpcs:ignore
if ( ! empty( $a['badge'] ) ) {
	echo '<span class="vb-price__badge">' . esc_html( $a['badge'] ) . '</span>';
}
echo '<div class="vb-price__kepala">';
echo vb_ikon( $a['icon'] ?? '', 'vb-ikon vb-price__icon', $a['iconUrl'] ?? '' ); // phpcs:ignore -- SVG pustaka.
if ( ! empty( $a['title'] ) ) {
	echo '<h3 class="vb-price__title">' . wp_kses_post( $a['title'] ) . '</h3>';
}
if ( ! empty( $a['price'] ) ) {
	echo '<p class="vb-price__harga">' . wp_kses_post( $a['price'] ) . '</p>';
}
if ( ! empty( $a['note'] ) ) {
	echo '<p class="vb-price__note">' . wp_kses_post( $a['note'] ) . '</p>';
}
echo '</div>';
echo '<div class="vb-price__isi">' . $content . '</div>'; // phpcs:ignore
echo '</div>';
