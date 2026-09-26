<?php
/** vb/breadcrumb — Beranda › induk › halaman ini (halaman, artikel, arsip, pencarian). */
$a     = $attributes;
$jejak = array( array( $a['homeLabel'] ?? 'Beranda', home_url( '/' ) ) );
$id    = (int) ( $block->context['postId'] ?? 0 );
if ( ! $id && is_singular() ) {
	$id = get_queried_object_id();
}
if ( is_search() ) {
	$jejak[] = array( $a['searchLabel'] ?? 'Pencarian', '' );
} elseif ( is_home() ) {
	$jejak[] = array( get_the_title( (int) get_option( 'page_for_posts' ) ), '' );
} elseif ( is_category() || is_tag() || is_tax() ) {
	$jejak[] = array( single_term_title( '', false ), '' );
} elseif ( $id ) {
	if ( 'post' === get_post_type( $id ) && get_option( 'page_for_posts' ) ) {
		$blog    = (int) get_option( 'page_for_posts' );
		$jejak[] = array( get_the_title( $blog ), get_permalink( $blog ) );
	}
	foreach ( array_reverse( get_post_ancestors( $id ) ) as $induk ) {
		$jejak[] = array( get_the_title( $induk ), get_permalink( $induk ) );
	}
	$jejak[] = array( get_the_title( $id ), '' );
}
$kelas = 'vb-remah' . ( ! empty( $a['uppercase'] ) ? ' vb-remah--kapital' : '' );
echo '<nav ' . get_block_wrapper_attributes( array( 'class' => $kelas, 'aria-label' => 'Breadcrumb' ) ) . '><ol>'; // phpcs:ignore
foreach ( $jejak as $i => $j ) {
	$akhir = count( $jejak ) - 1 === $i;
	echo '<li>' . ( $j[1] && ! $akhir ? '<a href="' . esc_url( $j[1] ) . '">' . esc_html( $j[0] ) . '</a>' : '<span' . ( $akhir ? ' aria-current="page"' : '' ) . '>' . esc_html( $j[0] ) . '</span>' ) . '</li>';
}
echo '</ol></nav>';
