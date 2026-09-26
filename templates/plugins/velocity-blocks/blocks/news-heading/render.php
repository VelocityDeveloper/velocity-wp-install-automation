<?php
/** vb/news-heading — judul rubrik + ikon opsional + tautan "Lihat Lainnya". */
$a     = $attributes;
$level = max( 2, min( 4, (int) ( $a['level'] ?? 2 ) ) );
$kelas = 'vb-nhead vb-nhead--' . sanitize_html_class( $a['headStyle'] ?? 'bar' ) . ' vb-nhead--' . sanitize_html_class( $a['size'] ?? 'md' );
$ikon  = ! empty( $a['icon'] ) ? vb_ikon( $a['icon'], 'vb-ikon vb-nhead__ikon' ) : '';
echo '<div ' . get_block_wrapper_attributes( array( 'class' => $kelas ) ) . '>'; // phpcs:ignore
printf( '<h%1$d class="vb-nhead__title">%2$s<span>%3$s</span></h%1$d>', $level, $ikon, wp_kses_post( $a['title'] ?? '' ) ); // phpcs:ignore
if ( ! empty( $a['url'] ) && ! empty( $a['linkLabel'] ) ) {
	printf(
		'<a class="vb-nhead__more" href="%s"%s>%s%s</a>',
		esc_url( $a['url'] ),
		! empty( $a['newTab'] ) ? ' target="_blank" rel="noopener"' : '',
		wp_kses_post( $a['linkLabel'] ),
		vb_ikon( 'arrow-right', 'vb-ikon vb-ikon--kecil' ) // phpcs:ignore
	);
}
echo '</div>';
