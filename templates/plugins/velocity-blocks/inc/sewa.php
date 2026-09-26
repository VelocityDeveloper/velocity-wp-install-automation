<?php
/**
 * Daftar sewa (rental kendaraan / unit): CPT `vb_sewa` dengan kotak "Detail Sewa".
 *
 * Satu unit = satu entri: judul (nama model), gambar unggulan (foto), urutan (kolom "Urutan"),
 * dan meta berikut. Dipakai blok vb/rentals (kartu harga + tombol pesan WhatsApp) dan
 * pilihan unit di blok vb/booking-form.
 *   vb_harga    teks  — harga tampil apa adanya ("Rp 75.000"); kosong = "Tanya admin"
 *   vb_satuan   teks  — satuan kecil di samping harga ("/ hari")
 *   vb_merek    teks  — merek / keterangan kecil di bawah nama ("Honda")
 *   vb_pesan    teks  — pesan WhatsApp khusus unit ini (kosong = pesan bawaan blok)
 * Unit tidak punya halaman sendiri (kartu langsung membuka WhatsApp).
 */

defined( 'ABSPATH' ) || exit;

function vb_meta_sewa() {
	return array(
		'vb_harga'  => array( 'Harga', 'mis. Rp 75.000 — kosongkan untuk "Tanya admin"' ),
		'vb_satuan' => array( 'Satuan harga', 'mis. / hari' ),
		'vb_merek'  => array( 'Merek / keterangan kecil', 'mis. Honda' ),
		'vb_pesan'  => array( 'Pesan WhatsApp khusus (opsional)', 'kosong = "Halo, saya ingin menyewa <nama unit>…"' ),
	);
}

add_action( 'init', function () {
	register_post_type( 'vb_sewa', array(
		'labels'             => array(
			'name'          => 'Scooter',
			'singular_name' => 'Scooter',
			'menu_name'     => 'Scooter (Sewa)',
			'add_new'       => 'Tambah Scooter',
			'add_new_item'  => 'Tambah Scooter',
			'edit_item'     => 'Edit Scooter',
			'all_items'     => 'Semua Scooter',
			'search_items'  => 'Cari Scooter',
		),
		'public'             => false,
		'show_ui'            => true,
		'show_in_rest'       => true,
		'publicly_queryable' => false,
		'exclude_from_search' => true,
		'menu_icon'          => 'dashicons-tag',
		'menu_position'      => 21,
		'supports'           => array( 'title', 'thumbnail', 'page-attributes' ),
	) );
	foreach ( array_keys( vb_meta_sewa() ) as $kunci ) {
		register_post_meta( 'vb_sewa', $kunci, array( 'show_in_rest' => true, 'single' => true, 'type' => 'string' ) );
	}
} );

/** Kolom daftar di wp-admin: foto, harga, merek, urutan. */
add_filter( 'manage_vb_sewa_posts_columns', function ( $kolom ) {
	$baru = array( 'cb' => $kolom['cb'], 'vb_foto' => 'Foto', 'title' => $kolom['title'], 'vb_harga' => 'Harga', 'vb_merek' => 'Merek', 'menu_order' => 'Urutan' );
	return $baru;
} );
add_action( 'manage_vb_sewa_posts_custom_column', function ( $kolom, $id ) {
	if ( 'vb_foto' === $kolom ) {
		echo get_the_post_thumbnail( $id, array( 64, 48 ) ); // phpcs:ignore
	} elseif ( 'menu_order' === $kolom ) {
		echo (int) get_post_field( 'menu_order', $id );
	} elseif ( in_array( $kolom, array( 'vb_harga', 'vb_merek' ), true ) ) {
		echo esc_html( trim( get_post_meta( $id, $kolom, true ) . ' ' . ( 'vb_harga' === $kolom ? get_post_meta( $id, 'vb_satuan', true ) : '' ) ) );
	}
}, 10, 2 );

/** Urutan bawaan daftar admin = kolom Urutan. */
add_action( 'pre_get_posts', function ( $q ) {
	if ( is_admin() && $q->is_main_query() && 'vb_sewa' === $q->get( 'post_type' ) && ! $q->get( 'orderby' ) ) {
		$q->set( 'orderby', array( 'menu_order' => 'ASC', 'title' => 'ASC' ) );
	}
} );

add_filter( 'enter_title_here', function ( $teks, $post ) {
	return 'vb_sewa' === $post->post_type ? 'Nama model, mis. Honda Vario 125cc' : $teks;
}, 10, 2 );

add_action( 'add_meta_boxes_vb_sewa', function () {
	add_meta_box( 'vb-detail-sewa', 'Detail Sewa', 'vb_kotak_detail_sewa', 'vb_sewa', 'normal', 'high' );
} );

function vb_kotak_detail_sewa( $post ) {
	wp_nonce_field( 'vb_detail_sewa', 'vb_sewa_nonce' );
	echo '<table class="form-table" role="presentation"><tbody>';
	foreach ( vb_meta_sewa() as $kunci => $isi ) {
		printf(
			'<tr><th scope="row"><label for="%1$s">%2$s</label></th><td><input type="text" class="regular-text" id="%1$s" name="%1$s" value="%3$s" placeholder="%4$s" /></td></tr>',
			esc_attr( $kunci ), esc_html( $isi[0] ), esc_attr( get_post_meta( $post->ID, $kunci, true ) ), esc_attr( $isi[1] )
		);
	}
	echo '</tbody></table><p class="description">Foto unit = <strong>Gambar unggulan</strong> (kanan). Urutan tampil = kolom <strong>Urutan</strong> di kotak Atribut. Unit yang tidak disewakan lagi cukup dijadikan Draft.</p>';
}

add_action( 'save_post_vb_sewa', function ( $post_id ) {
	if ( ! isset( $_POST['vb_sewa_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['vb_sewa_nonce'] ) ), 'vb_detail_sewa' ) ) {
		return;
	}
	if ( ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) || wp_is_post_revision( $post_id ) || ! current_user_can( 'edit_post', $post_id ) ) {
		return;
	}
	foreach ( array_keys( vb_meta_sewa() ) as $kunci ) {
		$nilai = isset( $_POST[ $kunci ] ) ? vb_teks_sewa( wp_unslash( $_POST[ $kunci ] ) ) : ''; // phpcs:ignore
		if ( '' === $nilai ) {
			delete_post_meta( $post_id, $kunci );
		} else {
			update_post_meta( $post_id, $kunci, $nilai );
		}
	}
} );

/** sanitize_text_field mengubah "<" jadi entity; kembalikan ke karakter asli (sama dengan modul produk). */
function vb_teks_sewa( $nilai ) {
	return trim( html_entity_decode( sanitize_text_field( (string) $nilai ), ENT_QUOTES, 'UTF-8' ) );
}

/** Unit terbit, urut kolom Urutan lalu judul. */
function vb_daftar_sewa( $jumlah = 0 ) {
	return get_posts( array(
		'post_type'      => 'vb_sewa',
		'post_status'    => 'publish',
		'posts_per_page' => $jumlah > 0 ? $jumlah : -1,
		'orderby'        => array( 'menu_order' => 'ASC', 'title' => 'ASC' ),
		'no_found_rows'  => true,
	) );
}
