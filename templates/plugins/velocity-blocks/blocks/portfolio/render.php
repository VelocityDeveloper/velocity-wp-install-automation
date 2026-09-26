<?php
/**
 * vb/portfolio — daftar karya CPT vb_portofolio.
 *   grid     : kartu foto + judul + ringkasan (+ tautan)
 *   carousel : kartu yang sama di wadah geser (mesin vb-carousel di view.js)
 *   tiles    : ubin foto rapat tanpa teks (judul muncul saat disorot), cocok untuk arsip
 *   slider   : satu foto besar per tampilan, bergeser otomatis (hero beranda)
 * Filter kategori (opsional) bekerja di peramban tanpa memuat ulang halaman.
 */
$a      = $attributes;
$layout = in_array( $a['layout'] ?? 'grid', array( 'grid', 'carousel', 'tiles', 'slider' ), true ) ? $a['layout'] : 'grid';
$geser  = in_array( $layout, array( 'carousel', 'slider' ), true );
$jumlah = (int) ( $a['count'] ?? 9 );
$args   = array(
	'post_type'      => 'vb_portofolio',
	'posts_per_page' => $jumlah > 0 ? $jumlah : -1,
	// "terbaru" = karya yang paling akhir ditambahkan tampil lebih dulu.
	'orderby'        => 'terbaru' === ( $a['orderBy'] ?? 'urutan' ) ? array( 'date' => 'DESC', 'ID' => 'DESC' ) : array( 'menu_order' => 'ASC', 'date' => 'DESC' ),
	'no_found_rows'  => true,
);
if ( is_singular( 'vb_portofolio' ) ) {
	$args['post__not_in'] = array( get_queried_object_id() ); // "Karya lainnya" tanpa karya yang sedang dibuka.
}
if ( ! empty( $a['category'] ) ) {
	$args['tax_query'] = array( array( 'taxonomy' => 'vb_kategori_porto', 'field' => 'slug', 'terms' => array_map( 'trim', explode( ',', $a['category'] ) ) ) ); // phpcs:ignore
}
// Arsip & kategori memakai kueri halaman itu sendiri (paginasi & filter URL tetap jalan).
$kueri = ( is_post_type_archive( 'vb_portofolio' ) || is_tax( 'vb_kategori_porto' ) ) && empty( $a['category'] ) && $jumlah <= 0
	? $GLOBALS['wp_query']
	: new WP_Query( $args );

if ( ! $kueri->have_posts() ) {
	if ( is_admin() || ( defined( 'REST_REQUEST' ) && REST_REQUEST ) ) {
		echo '<p ' . get_block_wrapper_attributes( array( 'class' => 'vb-porto vb-porto--kosong' ) ) . '>Belum ada portofolio. Tambahkan lewat menu Portofolio.</p>'; // phpcs:ignore
	}
	return;
}

$ke_situs = 'situs' === ( $a['linkTo'] ?? 'detail' );
$label    = trim( (string) ( $a['linkLabel'] ?? '' ) );
$rasio    = preg_replace( '#[^0-9/.]#', '', $a['ratio'] ?? '16/10' );
$item     = array();
$semua    = array();
while ( $kueri->have_posts() ) {
	$kueri->the_post();
	$d     = vb_data_porto( get_the_ID() );
	$tuju  = $ke_situs && $d['url'] ? $d['url'] : $d['link'];
	$tab   = $ke_situs && $d['url'];
	$slug  = array();
	foreach ( $d['kategori'] as $t ) {
		$slug[]              = $t->slug;
		$semua[ $t->slug ] = $t->name;
	}
	$gbr = $d['gambar'] ? wp_get_attachment_image( $d['gambar'], 'large', false, array(
		'class'   => 'vb-porto__img',
		'alt'     => $d['judul'],
		'sizes'   => 'slider' === $layout ? '(max-width: 1024px) 100vw, 50vw' : ( 'tiles' === $layout ? '(max-width: 600px) 100vw, 34vw' : '(max-width: 600px) 100vw, 420px' ),
		'loading' => 'slider' === $layout && ! $item ? 'eager' : 'lazy',
	) ) : '<span class="vb-porto__img vb-porto__img--kosong"></span>';
	$html  = '<article class="vb-porto__item" data-kat="' . esc_attr( implode( ' ', $slug ) ) . '">';
	$foto_saja = in_array( $layout, array( 'tiles', 'slider' ), true );
	$html .= '<a class="vb-porto__media"' . vb_atribut_tautan( $tuju, $tab ) . ( $foto_saja ? ' aria-label="' . esc_attr( $d['judul'] ) . '"' : ' tabindex="-1" aria-hidden="true"' ) . '>' . $gbr;
	if ( $foto_saja ) {
		$html .= '<span class="vb-porto__cap"><strong>' . esc_html( $d['judul'] ) . '</strong>' . ( $d['kategori'] ? '<span>' . esc_html( $d['kategori'][0]->name ) . '</span>' : '' ) . '</span>';
	}
	$html .= '</a>';
	if ( ! $foto_saja ) {
		$html .= '<div class="vb-porto__body"><h3 class="vb-porto__title"><a' . vb_atribut_tautan( $tuju, $tab ) . '>' . esc_html( $d['judul'] ) . '</a></h3>';
		if ( ! empty( $a['showExcerpt'] ) && $d['ringkas'] ) {
			$html .= '<p class="vb-porto__text">' . esc_html( $d['ringkas'] ) . '</p>';
		}
		if ( $label ) {
			$html .= '<a class="vb-porto__link"' . vb_atribut_tautan( $tuju, $tab ) . '>' . esc_html( $label ) . vb_ikon( 'arrow-right', 'vb-ikon vb-ikon--kecil' ) . '</a>';
		}
		$html .= '</div>';
	}
	$item[] = $html . '</article>';
}
wp_reset_postdata();

$gaya = sprintf(
	'--vb-cols:%1$d;--vb-cols-t:%2$d;--vb-cols-m:%3$d;--vb-pv:%1$d;--vb-pv-t:%2$d;--vb-pv-m:%3$d;--vb-ratio:%4$s;',
	max( 1, min( 6, (int) ( $a['columns'] ?? 3 ) ) ),
	max( 1, min( 4, (int) ( $a['columnsTablet'] ?? 2 ) ) ),
	max( 1, min( 2, (int) ( $a['columnsMobile'] ?? 1 ) ) ),
	esc_attr( $rasio ? $rasio : '16/10' )
);
$kelas = trim( 'vb-porto vb-porto--' . $layout . ' ' . vb_kelas_align( $a ) );
$attr  = array( 'class' => $kelas, 'style' => $gaya );
if ( $geser ) {
	$attr['class']               .= ' vb-carousel vb-carousel--auto';
	$attr['data-vb-autoplay']     = ! empty( $a['autoplay'] ) ? max( 3, (int) ( $a['interval'] ?? 5 ) ) : 0;
	$attr['data-vb-sebutan']      = 'Portofolio';
	$attr['aria-roledescription'] = 'carousel';
	$attr['aria-label']           = 'Portofolio';
}
echo '<div ' . get_block_wrapper_attributes( $attr ) . '>'; // phpcs:ignore

if ( ! empty( $a['showFilter'] ) && count( $semua ) > 1 && ! $geser ) {
	asort( $semua );
	echo '<div class="vb-porto__filter" role="toolbar" aria-label="Saring portofolio">';
	echo '<button type="button" class="vb-porto__tombol is-aktif" data-kat="*" aria-pressed="true">' . esc_html( $a['filterAll'] ?? 'Semua' ) . '</button>';
	foreach ( $semua as $slug => $nama ) {
		echo '<button type="button" class="vb-porto__tombol" data-kat="' . esc_attr( $slug ) . '" aria-pressed="false">' . esc_html( $nama ) . '</button>';
	}
	echo '</div>';
}

if ( $geser ) {
	echo '<div class="vb-carousel__track" tabindex="0">' . implode( '', $item ) . '</div>'; // phpcs:ignore
	if ( count( $item ) > 1 ) {
		echo '<div class="vb-carousel__nav"><div class="vb-carousel__dots" role="tablist" aria-label="Pilih tampilan"></div></div>';
	}
} else {
	echo '<div class="vb-porto__grid">' . implode( '', $item ) . '</div>'; // phpcs:ignore
}
echo '</div>';
