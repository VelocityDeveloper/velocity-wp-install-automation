<?php
/**
 * Portofolio: CPT `vb_portofolio` + taxonomy `vb_kategori_porto`.
 *
 * Satu entri = satu karya: judul (nama klien/situs), foto utama (tangkapan layar),
 * ringkasan (keterangan singkat), kategori, dan kotak "Detail Portofolio" berisi
 * alamat situs & layanan yang dikerjakan. Ditampilkan blok vb/portfolio (grid,
 * carousel, atau ubin dengan filter kategori) dan arsip /portofolio/.
 *
 * Meta: vb_url (URL situs), vb_layanan (teks). Keduanya tampil di REST untuk
 * Block Bindings / editor.
 */

defined( 'ABSPATH' ) || exit;

add_action( 'init', function () {
	register_post_type( 'vb_portofolio', array(
		'labels'        => array(
			'name'               => 'Portofolio',
			'singular_name'      => 'Portofolio',
			'add_new'            => 'Tambah Portofolio',
			'add_new_item'       => 'Tambah Portofolio',
			'edit_item'          => 'Edit Portofolio',
			'all_items'          => 'Semua Portofolio',
			'search_items'       => 'Cari Portofolio',
			'not_found'          => 'Belum ada portofolio',
			'featured_image'     => 'Tangkapan layar / foto karya',
			'set_featured_image' => 'Pilih tangkapan layar',
		),
		'public'        => true,
		'show_in_rest'  => true,
		'has_archive'   => 'portofolio',
		'rewrite'       => array( 'slug' => 'portofolio', 'with_front' => false ),
		'menu_icon'     => 'dashicons-portfolio',
		'menu_position' => 21,
		'supports'      => array( 'title', 'editor', 'thumbnail', 'excerpt', 'page-attributes' ),
	) );
	register_taxonomy( 'vb_kategori_porto', 'vb_portofolio', array(
		'labels'            => array(
			'name'          => 'Kategori Portofolio',
			'singular_name' => 'Kategori Portofolio',
			'add_new_item'  => 'Tambah Kategori',
			'search_items'  => 'Cari Kategori',
		),
		'hierarchical'      => true,
		'show_in_rest'      => true,
		'show_admin_column' => true,
		'rewrite'           => array( 'slug' => 'kategori-portofolio', 'with_front' => false ),
	) );
	foreach ( array( 'vb_url', 'vb_layanan' ) as $kunci ) {
		register_post_meta( 'vb_portofolio', $kunci, array( 'show_in_rest' => true, 'single' => true, 'type' => 'string' ) );
	}
} );

/** Urutan arsip: kolom "Urutan" lalu terbaru, 24 per halaman. */
add_action( 'pre_get_posts', function ( $q ) {
	if ( is_admin() || ! $q->is_main_query() ) {
		return;
	}
	if ( $q->is_post_type_archive( 'vb_portofolio' ) || $q->is_tax( 'vb_kategori_porto' ) ) {
		$q->set( 'orderby', array( 'menu_order' => 'ASC', 'date' => 'DESC' ) );
		$q->set( 'posts_per_page', 48 );
	}
} );

/** Kotak "Detail Portofolio". */
add_action( 'add_meta_boxes_vb_portofolio', function () {
	add_meta_box( 'vb-detail-porto', 'Detail Portofolio', 'vb_kotak_detail_porto', 'vb_portofolio', 'normal', 'high' );
} );

function vb_kotak_detail_porto( $post ) {
	wp_nonce_field( 'vb_detail_porto', 'vb_porto_nonce' );
	$url     = (string) get_post_meta( $post->ID, 'vb_url', true );
	$layanan = (string) get_post_meta( $post->ID, 'vb_layanan', true );
	?>
	<p><label for="vb-url"><strong>Alamat situs</strong></label><br />
		<input type="url" id="vb-url" class="widefat" name="vb_url" value="<?php echo esc_attr( $url ); ?>" placeholder="https://contoh.com/" />
		<span class="description">Tombol "Kunjungi situs" membuka alamat ini di tab baru. Kosongkan bila karya bukan situs.</span></p>
	<p><label for="vb-layanan"><strong>Layanan yang dikerjakan</strong></label><br />
		<input type="text" id="vb-layanan" class="widefat" name="vb_layanan" value="<?php echo esc_attr( $layanan ); ?>" placeholder="mis. Website company profile, konten halaman" /></p>
	<p class="description">Foto karya = <em>Gambar unggulan</em>; keterangan singkat = <em>Ringkasan (excerpt)</em>; kelompok = <em>Kategori Portofolio</em>.</p>
	<?php
}

add_action( 'save_post_vb_portofolio', function ( $post_id ) {
	if ( ! isset( $_POST['vb_porto_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['vb_porto_nonce'] ) ), 'vb_detail_porto' ) ) {
		return;
	}
	if ( ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) || wp_is_post_revision( $post_id ) || ! current_user_can( 'edit_post', $post_id ) ) {
		return;
	}
	$nilai = array(
		'vb_url'     => esc_url_raw( trim( (string) wp_unslash( $_POST['vb_url'] ?? '' ) ) ), // phpcs:ignore
		'vb_layanan' => sanitize_text_field( wp_unslash( $_POST['vb_layanan'] ?? '' ) ), // phpcs:ignore
	);
	foreach ( $nilai as $k => $v ) {
		if ( '' === $v ) {
			delete_post_meta( $post_id, $k );
		} else {
			update_post_meta( $post_id, $k, $v );
		}
	}
} );

/** Kolom gambar di daftar admin supaya klien mudah mengenali karya. */
add_filter( 'manage_vb_portofolio_posts_columns', function ( $kolom ) {
	return array_slice( $kolom, 0, 1, true ) + array( 'vb_foto' => 'Foto' ) + array_slice( $kolom, 1, null, true );
} );
add_action( 'manage_vb_portofolio_posts_custom_column', function ( $kolom, $post_id ) {
	if ( 'vb_foto' === $kolom ) {
		echo get_the_post_thumbnail( $post_id, array( 80, 50 ), array( 'style' => 'width:80px;height:50px;object-fit:cover;border-radius:4px' ) );
	}
}, 10, 2 );

/**
 * Data satu karya untuk render blok / template.
 * @return array{judul:string,url:string,link:string,ringkas:string,kategori:array,gambar:int}
 */
function vb_data_porto( $post ) {
	$post  = get_post( $post );
	$terms = get_the_terms( $post, 'vb_kategori_porto' );
	return array(
		'judul'    => get_the_title( $post ),
		'url'      => (string) get_post_meta( $post->ID, 'vb_url', true ),
		'link'     => get_permalink( $post ),
		'ringkas'  => has_excerpt( $post ) ? get_the_excerpt( $post ) : '',
		'layanan'  => (string) get_post_meta( $post->ID, 'vb_layanan', true ),
		'kategori' => $terms && ! is_wp_error( $terms ) ? $terms : array(),
		'gambar'   => (int) get_post_thumbnail_id( $post ),
	);
}
