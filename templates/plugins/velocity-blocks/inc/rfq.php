<?php
/**
 * Form pemesanan / permintaan penawaran (blok vb/rfq-form).
 *
 * Kiriman dikirim ke email Kontak Situs (cadangan: admin_email) dan
 * disimpan sebagai post privat `vb_inquiry`, jadi data tidak hilang bila email gagal.
 * Penjaga spam: nonce, honeypot, captcha velocity-addons (bila aktif), 1 kiriman/menit per IP.
 *
 * Pilihan pada kolom "Layanan yang diminati" diambil dari Data Situs → Pilihan Layanan;
 * bila kosong dan modul katalog menyala, dipakai judul produk; bila dua-duanya kosong,
 * kolomnya jadi isian teks biasa.
 */

defined( 'ABSPATH' ) || exit;

function vb_rfq_kolom() {
	/**
	 * Kolom form: nama => array( label, jenis, wajib, ekstra ).
	 * Jenis `pilihan` = dropdown dari vb_rfq_pilihan(). Tema boleh mengubah lewat filter.
	 */
	return apply_filters( 'vb_rfq_kolom', array(
		'name'     => array( 'Nama lengkap', 'text', true, array( 'autocomplete' => 'name' ) ),
		'company'  => array( 'Nama usaha / instansi', 'text', false, array( 'autocomplete' => 'organization' ) ),
		'email'    => array( 'Email', 'email', true, array( 'autocomplete' => 'email' ) ),
		'whatsapp' => array( 'Nomor WhatsApp', 'tel', true, array( 'autocomplete' => 'tel', 'placeholder' => 'mis. 0812…' ) ),
		'product'  => array( 'Layanan yang diminati', 'pilihan', true, array( 'span' => true ) ),
		'domain'   => array( 'Nama domain yang diinginkan', 'text', false, array( 'placeholder' => 'mis. namabisnisanda.com' ) ),
		'message'  => array( 'Kebutuhan Anda', 'textarea', false, array( 'placeholder' => 'Ceritakan singkat kebutuhan website atau konten digital Anda', 'span' => true ) ),
	) );
}

/** Pilihan dropdown kolom `pilihan`: daftar layanan Data Situs, cadangan judul produk. */
function vb_rfq_pilihan() {
	$pilihan = wp_list_pluck( vb_daftar( 'layanan' ), 'nama' );
	if ( $pilihan ) {
		return $pilihan;
	}
	if ( ! post_type_exists( 'vb_produk' ) ) {
		return array();
	}
	$produk = get_posts( array( 'post_type' => 'vb_produk', 'posts_per_page' => 100, 'orderby' => array( 'menu_order' => 'ASC', 'title' => 'ASC' ), 'no_found_rows' => true ) );
	return array_map( 'get_the_title', $produk );
}

add_action( 'init', function () {
	register_post_type( 'vb_inquiry', array(
		'label'           => 'Pemesanan Masuk',
		'show_in_menu'    => post_type_exists( 'vb_produk' ) ? 'edit.php?post_type=vb_produk' : true,
		'public'          => false,
		'show_ui'         => true,
		'menu_icon'       => 'dashicons-email-alt',
		'supports'        => array( 'title', 'editor' ),
		'capability_type' => 'post',
		'capabilities'    => array( 'create_posts' => 'do_not_allow' ),
		'map_meta_cap'    => true,
	) );
} );

function vb_rfq_captcha() {
	if ( shortcode_exists( 'velocity_captcha' ) ) {
		return vb_rfq_bahasa( do_shortcode( '[velocity_captcha]' ) );
	}
	if ( ! class_exists( 'Velocity_Addons_Captcha' ) ) {
		return '';
	}
	$captcha = new Velocity_Addons_Captcha();
	if ( method_exists( $captcha, 'isActive' ) && ! $captcha->isActive() ) {
		return '';
	}
	if ( ! method_exists( $captcha, 'display' ) ) {
		return '';
	}
	ob_start();
	$captcha->display();
	return vb_rfq_bahasa( (string) ob_get_clean() );
}

add_action( 'template_redirect', function () {
	if ( empty( $_POST['vb_rfq'] ) ) {
		return;
	}
	// Halaman asal dikirim form sendiri: wp_get_referer() kosong bila form dikirim ke halamannya sendiri.
	$kembali = isset( $_POST['vb_kembali'] ) ? esc_url_raw( wp_unslash( $_POST['vb_kembali'] ) ) : '';
	$kembali = wp_validate_redirect( $kembali, home_url( '/' ) );
	$kembali = remove_query_arg( 'rfq', strtok( $kembali, '#' ) );
	$ke      = function ( $status ) use ( $kembali ) {
		wp_safe_redirect( add_query_arg( 'rfq', $status, $kembali ) . '#rfq' );
		exit;
	};

	if ( ! isset( $_POST['vb_nonce'] ) || ! wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['vb_nonce'] ) ), 'vb_rfq' ) ) {
		$ke( 'kedaluwarsa' );
	}
	if ( ! empty( $_POST['vb_website'] ) ) {
		$ke( 'terkirim' );
	}
	if ( class_exists( 'Velocity_Addons_Captcha' ) ) {
		$captcha = new Velocity_Addons_Captcha();
		if ( method_exists( $captcha, 'verify' ) ) {
			$hasil = $captcha->verify();
			if ( empty( $hasil['success'] ) ) {
				$ke( 'captcha' );
			}
		}
	}
	$ip    = isset( $_SERVER['REMOTE_ADDR'] ) ? sanitize_text_field( wp_unslash( $_SERVER['REMOTE_ADDR'] ) ) : '';
	$kunci = 'vb_rfq_' . md5( $ip );
	if ( $ip && get_transient( $kunci ) ) {
		$ke( 'terlalu_cepat' );
	}

	$nilai = array();
	foreach ( vb_rfq_kolom() as $nama => $k ) {
		$mentah = isset( $_POST[ $nama ] ) ? wp_unslash( $_POST[ $nama ] ) : '';
		if ( 'email' === $k[1] ) {
			$nilai[ $nama ] = sanitize_email( $mentah );
		} elseif ( 'textarea' === $k[1] ) {
			$nilai[ $nama ] = sanitize_textarea_field( $mentah );
		} else {
			$nilai[ $nama ] = sanitize_text_field( $mentah );
		}
		if ( $k[2] && '' === $nilai[ $nama ] ) {
			$ke( 'kurang' );
		}
	}
	if ( ! is_email( $nilai['email'] ) ) {
		$ke( 'kurang' );
	}

	$baris = array( 'PEMESANAN / PERMINTAAN PENAWARAN', 'Halaman: ' . $kembali );
	foreach ( vb_rfq_kolom() as $nama => $k ) {
		$baris[] = $k[0] . ': ' . ( '' !== $nilai[ $nama ] ? $nilai[ $nama ] : '-' );
	}
	$teks = implode( "\n", $baris );

	wp_insert_post( array(
		'post_type'    => 'vb_inquiry',
		'post_status'  => 'private',
		'post_title'   => sprintf( 'Pemesanan: %s — %s', vb_rfq_nilai( $nilai, 'product' ), vb_rfq_nilai( $nilai, 'name' ) ),
		'post_content' => $teks,
	) );

	$tujuan = vb_data( 'email' ) ? vb_data( 'email' ) : get_option( 'admin_email' );
	wp_mail(
		$tujuan,
		'[Pemesanan] ' . vb_rfq_nilai( $nilai, 'product' ) . ' — ' . vb_rfq_nilai( $nilai, 'name' ),
		$teks,
		array( 'Reply-To: ' . $nilai['name'] . ' <' . $nilai['email'] . '>' )
	);
	if ( $ip ) {
		set_transient( $kunci, 1, MINUTE_IN_SECONDS );
	}
	$ke( 'terkirim' );
} );

/**
 * Teks captcha mengikuti bahasa isi situs, bukan locale WordPress: instalasi Velocity
 * memakai WordPress en_US walau situsnya berbahasa Indonesia, sehingga teks bawaan
 * velocity-addons ("Enter the code") perlu dikembalikan ke bahasa Indonesia.
 * Situs berbahasa Inggris mematikannya lewat filter `vb_rfq_bahasa_situs`.
 */
function vb_rfq_bahasa( $html ) {
	if ( 'id' !== apply_filters( 'vb_rfq_bahasa_situs', 'id' ) ) {
		return $html;
	}
	return strtr( $html, array( 'Enter the code' => 'Masukkan kode', 'Refresh' => 'Muat ulang', 'Reload' => 'Muat ulang' ) );
}

/** Nilai kolom yang wajib ada saat merangkai judul/subjek tidak selalu terisi. */
function vb_rfq_nilai( $nilai, $kunci ) {
	return isset( $nilai[ $kunci ] ) && '' !== $nilai[ $kunci ] ? $nilai[ $kunci ] : '-';
}
