<?php
/**
 * vb/products — katalog dari CPT vb_produk.
 * layout tabs: tab per kategori (tanpa JS tetap terbaca: semua panel tampil berurutan).
 */
$a      = $attributes;
$jumlah = max( 1, min( 48, (int) ( $a['count'] ?? 8 ) ) );
$kolom  = max( 1, min( 6, (int) ( $a['columns'] ?? 4 ) ) );

if ( ! function_exists( 'vb_kartu_produk' ) ) {
	function vb_kartu_produk( $post, $ringkas ) {
		$url  = get_permalink( $post );
		$foto = get_the_post_thumbnail( $post, 'medium_large', array( 'class' => 'vb-prod__img', 'sizes' => '(max-width: 600px) 50vw, 300px' ) );
		if ( ! $foto ) {
			$foto = '<span class="vb-prod__img vb-prod__img--kosong">' . vb_ikon( 'leaf', 'vb-ikon' ) . '</span>';
		}
		$html  = '<article class="vb-prod"><a class="vb-prod__media" href="' . esc_url( $url ) . '" tabindex="-1" aria-hidden="true">' . $foto . '</a>';
		$html .= '<div class="vb-prod__body"><h3 class="vb-prod__title"><a href="' . esc_url( $url ) . '">' . esc_html( get_the_title( $post ) ) . '</a></h3>';
		if ( $ringkas && has_excerpt( $post ) ) {
			$html .= '<p class="vb-prod__text">' . esc_html( wp_trim_words( get_the_excerpt( $post ), 16 ) ) . '</p>';
		}
		return $html . '</div></article>';
	}
	function vb_query_produk( $term_id, $jumlah ) {
		$args = array(
			'post_type'      => 'vb_produk',
			'posts_per_page' => $jumlah,
			'orderby'        => array( 'menu_order' => 'ASC', 'title' => 'ASC' ),
			'no_found_rows'  => true,
		);
		if ( $term_id ) {
			$args['tax_query'] = array( array( 'taxonomy' => 'vb_kategori', 'terms' => $term_id ) ); // phpcs:ignore
		}
		return get_posts( $args );
	}
}

$ringkas = ! empty( $a['showExcerpt'] );
$gaya    = '--vb-cols:' . $kolom . ';';
$wrapper = get_block_wrapper_attributes( array( 'class' => 'vb-products vb-products--' . sanitize_html_class( $a['layout'] ?? 'tabs' ) . ' ' . vb_kelas_align( $a ), 'style' => $gaya ) );
$semua   = get_post_type_archive_link( 'vb_produk' );

$terms = array();
if ( 'tabs' === ( $a['layout'] ?? 'tabs' ) ) {
	$terms = get_terms( array( 'taxonomy' => 'vb_kategori', 'hide_empty' => true, 'parent' => 0, 'orderby' => 'term_id' ) );
	$terms = is_wp_error( $terms ) ? array() : $terms;
}

echo '<div ' . $wrapper . '>'; // phpcs:ignore
if ( $terms ) {
	$uid = wp_unique_id( 'vb-prod-' );
	echo '<div class="vb-tabs" role="tablist">';
	foreach ( $terms as $i => $t ) {
		printf(
			'<button type="button" class="vb-tab" role="tab" id="%1$s-t%2$d" aria-controls="%1$s-p%2$d" aria-selected="%3$s">%4$s<span>%5$s</span></button>',
			esc_attr( $uid ), (int) $i, 0 === $i ? 'true' : 'false',
			vb_ikon( get_term_meta( $t->term_id, 'vb_ikon', true ), 'vb-ikon' ), // phpcs:ignore
			esc_html( $t->name )
		);
	}
	echo '</div>';
	foreach ( $terms as $i => $t ) {
		printf( '<div class="vb-tabpanel" role="tabpanel" id="%1$s-p%2$d" aria-labelledby="%1$s-t%2$d"%3$s>', esc_attr( $uid ), (int) $i, 0 === $i ? '' : ' data-vb-hidden' );
		printf(
			'<div class="vb-tabpanel__head"><h3>%s</h3><a class="vb-btn vb-btn--outline vb-btn--sm" href="%s"><span class="vb-btn__text">View all</span>%s</a></div>',
			esc_html( $t->name ), esc_url( get_term_link( $t ) ), vb_ikon( 'arrow-right', 'vb-ikon vb-btn__icon' ) // phpcs:ignore
		);
		echo '<div class="vb-prod-grid">';
		foreach ( vb_query_produk( $t->term_id, $jumlah ) as $p ) {
			echo vb_kartu_produk( $p, $ringkas ); // phpcs:ignore
		}
		echo '</div></div>';
	}
} else {
	$term_id = 0;
	if ( ! empty( $a['category'] ) ) {
		$t       = get_term_by( 'slug', $a['category'], 'vb_kategori' );
		$term_id = $t ? $t->term_id : 0;
	}
	$produk = vb_query_produk( $term_id, $jumlah );
	if ( ! $produk ) {
		echo '<p class="vb-kosong">Belum ada produk. Tambahkan lewat menu Produk di wp-admin.</p>';
	}
	echo '<div class="vb-prod-grid">';
	foreach ( $produk as $p ) {
		echo vb_kartu_produk( $p, $ringkas ); // phpcs:ignore
	}
	echo '</div>';
}
if ( ! empty( $a['showViewAll'] ) && $semua ) {
	printf( '<p class="vb-products__all"><a class="vb-btn vb-btn--primary vb-btn--md" href="%s"><span class="vb-btn__text">%s</span>%s</a></p>', esc_url( $semua ), esc_html( $a['viewAllLabel'] ?? 'View all products' ), vb_ikon( 'arrow-right', 'vb-ikon vb-btn__icon' ) ); // phpcs:ignore
}
echo '</div>';
