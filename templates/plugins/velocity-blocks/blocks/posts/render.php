<?php
/** vb/posts — daftar berita (tampilan berlapis/baris/daftar/grid) dari kategori pilihan. */
$a      = $attributes;
$layout = in_array( $a['layout'] ?? '', array( 'overlay', 'list', 'excerpt', 'grid' ), true ) ? $a['layout'] : 'overlay';
$args   = array(
	'post_type'           => 'post',
	'post_status'         => 'publish',
	'posts_per_page'      => max( 1, min( 24, (int) ( $a['count'] ?? 4 ) ) ),
	'offset'              => max( 0, (int) ( $a['offset'] ?? 0 ) ),
	'ignore_sticky_posts' => true,
	'no_found_rows'       => true,
);
if ( ! empty( $a['category'] ) ) {
	$args['cat'] = (int) $a['category'];
}
$urut = $a['orderBy'] ?? 'date';
if ( 'popular' === $urut ) {
	// Jumlah dibaca dari velocity-addons (meta `hit`); berita tanpa hitungan tetap ikut di belakang.
	$args['meta_query'] = array( // phpcs:ignore
		'relation' => 'OR',
		'hit'      => array( 'key' => 'hit', 'type' => 'NUMERIC' ),
		array( 'key' => 'hit', 'compare' => 'NOT EXISTS' ),
	);
	$args['orderby'] = array( 'hit' => 'DESC', 'date' => 'DESC' );
} elseif ( 'comment_count' === $urut ) {
	$args['orderby'] = array( 'comment_count' => 'DESC', 'date' => 'DESC' );
} elseif ( 'rand' === $urut ) {
	$args['orderby'] = 'rand';
}
if ( ! empty( $a['excludeCurrent'] ) && is_singular() ) {
	$args['post__not_in'] = array( get_queried_object_id() );
}
$q = new WP_Query( $args );

$kelas = array( 'vb-posts', 'vb-posts--' . $layout, 'vb-gap-' . sanitize_html_class( $a['gap'] ?? 'md' ), 'vb-judul-' . sanitize_html_class( $a['titleSize'] ?? 'md' ), vb_kelas_align( $a ) );
if ( 'list' === $layout ) {
	$kelas[] = 'vb-posts--foto-' . sanitize_html_class( $a['thumbPos'] ?? 'right' );
}
if ( ! empty( $a['fill'] ) ) {
	$kelas[] = 'vb-posts--fill';
}
$gaya = sprintf(
	'--vb-cols:%d;--vb-cols-t:%d;--vb-cols-m:%d;--vb-post-h:%dpx;',
	max( 1, min( 6, (int) ( $a['columns'] ?? 1 ) ) ),
	max( 1, min( 4, (int) ( $a['columnsTablet'] ?? 1 ) ) ),
	max( 1, min( 3, (int) ( $a['columnsMobile'] ?? 1 ) ) ),
	max( 160, min( 900, (int) ( $a['imageHeight'] ?? 420 ) ) )
);
$ukuran = array( 'overlay' => 'large', 'list' => 'thumbnail', 'excerpt' => 'medium', 'grid' => 'medium_large' );

echo '<div ' . get_block_wrapper_attributes( array( 'class' => trim( implode( ' ', array_filter( $kelas ) ) ), 'style' => $gaya ) ) . '>'; // phpcs:ignore
if ( ! $q->have_posts() ) {
	echo '<p class="vb-posts__kosong">' . esc_html( $a['emptyText'] ?? '' ) . '</p>';
}
while ( $q->have_posts() ) {
	$q->the_post();
	$tautan = get_permalink();
	$judul  = get_the_title();
	$foto   = has_post_thumbnail()
		? get_the_post_thumbnail( null, $ukuran[ $layout ], array( 'class' => 'vb-post__foto', 'loading' => 'lazy', 'alt' => esc_attr( wp_strip_all_tags( $judul ) ) ) )
		: '<span class="vb-post__foto vb-post__foto--kosong"></span>';
	$kat    = '';
	if ( ! empty( $a['showCategory'] ) && in_array( $layout, array( 'overlay', 'grid' ), true ) ) {
		$daftar = get_the_category();
		if ( $daftar ) {
			$kat = '<a class="vb-post__kat" href="' . esc_url( get_category_link( $daftar[0] ) ) . '">' . esc_html( $daftar[0]->name ) . '</a>';
		}
	}
	$meta = ! empty( $a['showDate'] ) ? '<p class="vb-post__meta"><time datetime="' . esc_attr( get_the_date( 'c' ) ) . '">' . esc_html( get_the_date() ) . '</time></p>' : '';
	$ring = '';
	if ( ! empty( $a['showExcerpt'] ) && in_array( $layout, array( 'excerpt', 'grid' ), true ) ) {
		$ring = '<p class="vb-post__ringkas">' . esc_html( wp_trim_words( get_the_excerpt(), max( 5, (int) ( $a['excerptLength'] ?? 24 ) ), '…' ) ) . '</p>';
	}
	$h = sprintf( '<h3 class="vb-post__title"><a href="%s">%s</a></h3>', esc_url( $tautan ), wp_kses_post( $judul ) );
	printf(
		'<article class="vb-post"><a class="vb-post__img" href="%1$s" tabindex="-1" aria-hidden="true">%2$s</a><div class="vb-post__body">%3$s%4$s%5$s%6$s</div></article>',
		esc_url( $tautan ),
		$foto, // phpcs:ignore
		$kat, // phpcs:ignore
		$h, // phpcs:ignore
		$meta, // phpcs:ignore
		$ring // phpcs:ignore
	);
}
wp_reset_postdata();
echo '</div>';
