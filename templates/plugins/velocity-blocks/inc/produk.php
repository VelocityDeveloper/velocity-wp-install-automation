<?php
/**
 * Katalog produk: CPT `vb_produk` + taksonomi `vb_kategori`, dengan kotak "Detail Produk"
 * bawaan plugin ini (tanpa plugin Meta Box; format meta sama dengan versi Meta Box sebelumnya).
 *
 * Meta (satu baris meta per kunci):
 *   vb_varian        array teks              — bentuk/grade yang tersedia ("Loose Pure", "80–85%")
 *   vb_spesifikasi   array {label, nilai}    — baris parameter → nilai ("Moisture" → "< 6%")
 *   vb_kegunaan      teks                    — kegunaan / aplikasi
 * Ikon kategori (untuk tab katalog): term meta `vb_ikon` (nama ikon pustaka).
 */

defined( 'ABSPATH' ) || exit;

add_action( 'init', function () {
	register_post_type( 'vb_produk', array(
		'labels'       => array(
			'name'          => 'Produk',
			'singular_name' => 'Produk',
			'add_new_item'  => 'Tambah Produk',
			'edit_item'     => 'Edit Produk',
			'all_items'     => 'Semua Produk',
			'search_items'  => 'Cari Produk',
		),
		'public'       => true,
		'show_in_rest' => true,
		'has_archive'  => 'products',
		'rewrite'      => array( 'slug' => 'product', 'with_front' => false ),
		'menu_icon'    => 'dashicons-carrot',
		'menu_position' => 21,
		'supports'     => array( 'title', 'editor', 'thumbnail', 'excerpt', 'page-attributes' ),
	) );
	register_taxonomy( 'vb_kategori', 'vb_produk', array(
		'labels'            => array(
			'name'          => 'Kategori Produk',
			'singular_name' => 'Kategori Produk',
			'add_new_item'  => 'Tambah Kategori',
		),
		'hierarchical'      => true,
		'show_in_rest'      => true,
		'show_admin_column' => true,
		'rewrite'           => array( 'slug' => 'product-category', 'with_front' => false ),
	) );
	foreach ( array( 'vb_kegunaan' ) as $kunci ) {
		register_post_meta( 'vb_produk', $kunci, array( 'show_in_rest' => true, 'single' => true, 'type' => 'string' ) );
	}
	register_term_meta( 'vb_kategori', 'vb_ikon', array( 'show_in_rest' => true, 'single' => true, 'type' => 'string' ) );
} );

/** Urutan katalog: menu_order lalu judul (klien mengatur lewat kolom "Urutan"). */
add_action( 'pre_get_posts', function ( $q ) {
	if ( is_admin() || ! $q->is_main_query() ) {
		return;
	}
	if ( $q->is_post_type_archive( 'vb_produk' ) || $q->is_tax( 'vb_kategori' ) ) {
		$q->set( 'orderby', array( 'menu_order' => 'ASC', 'title' => 'ASC' ) );
		$q->set( 'posts_per_page', 24 );
	}
} );

/** Kotak "Detail Produk" di layar edit produk. */
add_action( 'add_meta_boxes_vb_produk', function () {
	add_meta_box( 'vb-detail-produk', 'Detail Produk', 'vb_kotak_detail_produk', 'vb_produk', 'normal', 'high' );
} );

function vb_kotak_detail_produk( $post ) {
	$varian = array_values( array_filter( (array) get_post_meta( $post->ID, 'vb_varian', true ), 'strlen' ) );
	$spek   = array_values( array_filter( (array) get_post_meta( $post->ID, 'vb_spesifikasi', true ), 'is_array' ) );
	$guna   = (string) get_post_meta( $post->ID, 'vb_kegunaan', true );
	wp_nonce_field( 'vb_detail_produk', 'vb_detail_nonce' );
	$aksi = '<td class="vb-dp-aksi"><button type="button" class="button vb-dp-naik" title="Naik" aria-label="Naik">↑</button> <button type="button" class="button vb-dp-turun" title="Turun" aria-label="Turun">↓</button> <button type="button" class="button-link-delete vb-dp-hapus">Hapus</button></td>';
	$baris_varian = function ( $v ) use ( $aksi ) {
		return '<tr><td><input type="text" class="widefat" name="vb_varian[]" value="' . esc_attr( $v ) . '" placeholder="mis. 5 kg compressed block / Grade AA" /></td>' . $aksi . '</tr>';
	};
	$baris_spek = function ( $b ) use ( $aksi ) {
		return '<tr><td><input type="text" class="widefat" name="vb_spek_label[]" value="' . esc_attr( $b['label'] ?? '' ) . '" placeholder="Parameter, mis. Moisture" /></td>'
			. '<td><input type="text" class="widefat" name="vb_spek_nilai[]" value="' . esc_attr( $b['nilai'] ?? '' ) . '" placeholder="Nilai, mis. &lt; 6%" /></td>' . $aksi . '</tr>';
	};
	?>
	<div class="vb-dp">
		<h4>Varian / grade / bentuk</h4>
		<p class="description">Satu varian per baris. Tampil sebagai "Available forms &amp; grades" di halaman produk.</p>
		<table class="widefat striped vb-dp-tabel" data-jenis="varian"><tbody>
			<?php foreach ( $varian as $v ) { echo $baris_varian( $v ); } // phpcs:ignore -- di-escape di fungsi. ?>
		</tbody></table>
		<p><button type="button" class="button vb-dp-tambah" data-jenis="varian">+ Tambah varian</button></p>

		<h4>Spesifikasi</h4>
		<p class="description">Baris parameter → nilai. Tampil sebagai tabel "Specifications". Kosongkan bila tidak ada data (jangan mengarang angka).</p>
		<table class="widefat striped vb-dp-tabel" data-jenis="spek"><tbody>
			<?php foreach ( $spek as $b ) { echo $baris_spek( $b ); } // phpcs:ignore ?>
		</tbody></table>
		<p><button type="button" class="button vb-dp-tambah" data-jenis="spek">+ Tambah baris spesifikasi</button></p>

		<h4><label for="vb-kegunaan">Kegunaan / aplikasi</label></h4>
		<textarea id="vb-kegunaan" class="widefat" rows="3" name="vb_kegunaan"><?php echo esc_textarea( $guna ); ?></textarea>

		<template id="vb-dp-varian"><?php echo $baris_varian( '' ); // phpcs:ignore ?></template>
		<template id="vb-dp-spek"><?php echo $baris_spek( array() ); // phpcs:ignore ?></template>
	</div>
	<style>.vb-dp h4{margin:18px 0 4px}.vb-dp h4:first-child{margin-top:6px}.vb-dp-tabel td{vertical-align:middle}.vb-dp-aksi{width:150px;white-space:nowrap;text-align:right}.vb-dp-tabel:empty,.vb-dp-tabel tbody:empty{display:none}</style>
	<script>
	( function () {
		var kotak = document.querySelector( '.vb-dp' );
		kotak.addEventListener( 'click', function ( e ) {
			var t = e.target, tr = t.closest( 'tr' );
			if ( t.classList.contains( 'vb-dp-tambah' ) ) {
				var tb = kotak.querySelector( '.vb-dp-tabel[data-jenis="' + t.dataset.jenis + '"] tbody' );
				tb.insertAdjacentHTML( 'beforeend', document.getElementById( 'vb-dp-' + t.dataset.jenis ).innerHTML );
				tb.lastElementChild.querySelector( 'input' ).focus();
			} else if ( tr && t.classList.contains( 'vb-dp-hapus' ) ) {
				tr.remove();
			} else if ( tr && t.classList.contains( 'vb-dp-naik' ) && tr.previousElementSibling ) {
				tr.parentNode.insertBefore( tr, tr.previousElementSibling );
			} else if ( tr && t.classList.contains( 'vb-dp-turun' ) && tr.nextElementSibling ) {
				tr.parentNode.insertBefore( tr.nextElementSibling, tr );
			}
		} );
	}() );
	</script>
	<?php
}

/**
 * Teks isian: sanitize_text_field mengubah "<" yang bukan tag menjadi &lt; (wp_pre_kses_less_than),
 * sehingga nilai seperti "< 6%" tersimpan sebagai entity dan tercetak mentah di halaman produk.
 * Entity dikembalikan ke karakter aslinya setelah dibersihkan.
 */
function vb_teks_isian( $nilai, $panjang = false ) {
	$bersih = $panjang ? sanitize_textarea_field( $nilai ) : sanitize_text_field( $nilai );
	return trim( html_entity_decode( $bersih, ENT_QUOTES, 'UTF-8' ) );
}

/** Simpan Detail Produk. Format sama dengan versi Meta Box: array teks, array {label, nilai}, teks. */
add_action( 'save_post_vb_produk', function ( $post_id ) {
	if ( ! isset( $_POST['vb_detail_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['vb_detail_nonce'] ) ), 'vb_detail_produk' ) ) {
		return;
	}
	if ( ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) || wp_is_post_revision( $post_id ) || ! current_user_can( 'edit_post', $post_id ) ) {
		return;
	}
	$varian = array_values( array_filter( array_map( 'vb_teks_isian', (array) wp_unslash( $_POST['vb_varian'] ?? array() ) ), 'strlen' ) ); // phpcs:ignore
	$label  = array_map( 'vb_teks_isian', (array) wp_unslash( $_POST['vb_spek_label'] ?? array() ) ); // phpcs:ignore
	$nilai  = array_map( 'vb_teks_isian', (array) wp_unslash( $_POST['vb_spek_nilai'] ?? array() ) ); // phpcs:ignore
	$spek   = array();
	foreach ( $label as $i => $l ) {
		$n = $nilai[ $i ] ?? '';
		if ( '' !== $l || '' !== $n ) {
			$spek[] = array( 'label' => $l, 'nilai' => $n );
		}
	}
	$guna = vb_teks_isian( wp_unslash( $_POST['vb_kegunaan'] ?? '' ), true ); // phpcs:ignore
	foreach ( array( 'vb_varian' => $varian, 'vb_spesifikasi' => $spek, 'vb_kegunaan' => $guna ) as $k => $v ) {
		if ( array() === $v || '' === $v ) {
			delete_post_meta( $post_id, $k );
		} else {
			update_post_meta( $post_id, $k, $v );
		}
	}
} );

/** Ikon kategori di layar edit kategori (tanpa Meta Box term meta berbayar). */
add_action( 'vb_kategori_edit_form_fields', function ( $term ) {
	$nilai = get_term_meta( $term->term_id, 'vb_ikon', true );
	echo '<tr class="form-field"><th scope="row"><label for="vb-ikon">Ikon (untuk tab katalog)</label></th><td><select name="vb_ikon" id="vb-ikon"><option value="">— tanpa ikon —</option>';
	foreach ( array_keys( vb_daftar_ikon() ) as $nama ) {
		printf( '<option value="%1$s"%2$s>%1$s</option>', esc_attr( $nama ), selected( $nilai, $nama, false ) );
	}
	echo '</select><p class="description">Nama ikon pustaka Velocity Blocks.</p></td></tr>';
} );
add_action( 'edited_vb_kategori', function ( $term_id ) {
	if ( isset( $_POST['vb_ikon'] ) && current_user_can( 'manage_categories' ) ) { // phpcs:ignore -- nonce dicek layar edit term.
		update_term_meta( $term_id, 'vb_ikon', sanitize_key( wp_unslash( $_POST['vb_ikon'] ) ) ); // phpcs:ignore
	}
} );

/** Nilai meta produk. */
function vb_meta_produk( $kunci, $post_id = null ) {
	return get_post_meta( $post_id ? $post_id : get_the_ID(), $kunci, true );
}
