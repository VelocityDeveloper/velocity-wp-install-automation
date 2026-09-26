<?php
/**
 * Data identitas situs (Tampilan → Data Situs, opsi `vb_situs`).
 *
 * Dipakai blok Kontak, Media Sosial, Tombol (varian WhatsApp), Peta, dan Form RFQ, jadi
 * nomor/email cukup diubah di satu tempat. Kontak & media sosial berupa daftar: baris bisa
 * ditambah, dihapus, dan diurutkan. Isian awal situs ditulis skrip pemasangan ke opsi.
 */

defined( 'ABSPATH' ) || exit;

/** Kolom tunggal. Kolom kosong memakai isian bawaan. */
function vb_kolom_situs() {
	return array(
		'nama'     => array( 'Nama perusahaan / merek', 'text', get_bloginfo( 'name' ) ),
		'slogan'   => array( 'Slogan', 'text', get_bloginfo( 'description' ) ),
		'wa'       => array( 'Nomor WhatsApp tombol (format 62…)', 'text', '' ),
		'wa_pesan' => array( 'Pesan awal WhatsApp', 'text', 'Halo, saya ingin bertanya tentang layanan Anda.' ),
		'peta'     => array( 'Pencarian Google Maps (alamat/koordinat)', 'text', '' ),
	);
}

/** Jenis baris kontak: label bawaan + ikon. */
function vb_jenis_kontak() {
	return array(
		'alamat'   => array( 'Alamat', 'map-pin' ),
		'whatsapp' => array( 'WhatsApp', 'whatsapp' ),
		'telepon'  => array( 'Telepon', 'phone' ),
		'email'    => array( 'Email', 'mail' ),
		'jam'      => array( 'Jam Operasional', 'clock' ),
		'website'  => array( 'Website', 'globe' ),
		'lainnya'  => array( 'Lainnya', 'info' ),
	);
}

/** Platform media sosial = layanan blok core/social-link (ikon bawaan WordPress). */
function vb_platform_sosmed() {
	return array(
		'facebook'  => 'Facebook',
		'instagram' => 'Instagram',
		'x'         => 'X (Twitter)',
		'linkedin'  => 'LinkedIn',
		'youtube'   => 'YouTube',
		'tiktok'    => 'TikTok',
		'threads'   => 'Threads',
		'whatsapp'  => 'WhatsApp',
		'telegram'  => 'Telegram',
		'pinterest' => 'Pinterest',
	);
}

/** Sebelum diisi: tautan umum platform (aturan Velocity: ikon selalu ada sampai klien memberi akun). */
function vb_daftar_bawaan() {
	return array(
		'kontak'  => array(),
		'layanan' => array(),
		'sosmed' => array(
			array( 'platform' => 'facebook', 'url' => 'https://www.facebook.com/' ),
			array( 'platform' => 'instagram', 'url' => 'https://www.instagram.com/' ),
			array( 'platform' => 'x', 'url' => 'https://x.com/' ),
			array( 'platform' => 'youtube', 'url' => 'https://www.youtube.com/' ),
			array( 'platform' => 'tiktok', 'url' => 'https://www.tiktok.com/' ),
		),
	);
}

function vb_opsi_situs() {
	$opsi = get_option( 'vb_situs', array() );
	return is_array( $opsi ) ? $opsi : array();
}

/** Daftar `kontak` / `sosmed`. Belum pernah disimpan → bawaan; disimpan kosong → kosong. */
function vb_daftar( $nama ) {
	$opsi = vb_opsi_situs();
	if ( isset( $opsi[ $nama ] ) && is_array( $opsi[ $nama ] ) ) {
		return $opsi[ $nama ];
	}
	$bawaan = vb_daftar_bawaan();
	return $bawaan[ $nama ] ?? array();
}

/** Baris kontak pertama berjenis tertentu (null bila tak ada). */
function vb_kontak_pertama( $jenis ) {
	foreach ( vb_daftar( 'kontak' ) as $baris ) {
		if ( in_array( $baris['jenis'], (array) $jenis, true ) ) {
			return $baris;
		}
	}
	return null;
}

function vb_data( $kunci ) {
	// Kunci lama → baris pertama daftar kontak.
	$dari_daftar = array(
		'alamat' => 'alamat',
		'email'  => 'email',
		'jam'    => 'jam',
		'telp'   => array( 'whatsapp', 'telepon' ),
	);
	if ( isset( $dari_daftar[ $kunci ] ) ) {
		$baris = vb_kontak_pertama( $dari_daftar[ $kunci ] );
		return $baris ? $baris['isi'] : '';
	}
	$opsi  = vb_opsi_situs();
	$kolom = vb_kolom_situs();
	if ( isset( $opsi[ $kunci ] ) && is_string( $opsi[ $kunci ] ) && '' !== trim( $opsi[ $kunci ] ) ) {
		return trim( $opsi[ $kunci ] );
	}
	if ( 'wa' === $kunci ) {
		// Kolom WA kosong → baris kontak WhatsApp pertama.
		$baris = vb_kontak_pertama( 'whatsapp' );
		if ( $baris ) {
			return vb_nomor_wa( $baris['isi'] );
		}
	}
	return isset( $kolom[ $kunci ] ) ? $kolom[ $kunci ][2] : '';
}

/** Tautan satu baris kontak (null = teks biasa). */
function vb_tautan_kontak( $baris ) {
	switch ( $baris['jenis'] ) {
		case 'whatsapp':
			return vb_wa_link( '', $baris['isi'] );
		case 'telepon':
			return 'tel:+' . vb_nomor_wa( $baris['isi'] );
		case 'email':
			return 'mailto:' . antispambot( $baris['isi'] );
		case 'website':
			return preg_match( '#^https?://#i', $baris['isi'] ) ? $baris['isi'] : 'https://' . $baris['isi'];
		case 'alamat':
			return 'https://www.google.com/maps/search/?api=1&query=' . rawurlencode( $baris['isi'] );
	}
	return null;
}

/** 0812… / +62 812… → 62812… */
function vb_nomor_wa( $nomor ) {
	$nomor = preg_replace( '/\D/', '', (string) $nomor );
	return preg_replace( '/^0/', '62', $nomor );
}

/** Tautan WhatsApp dengan pesan awal. Tanpa nomor → mailto. */
function vb_wa_link( $pesan = '', $nomor = '' ) {
	$nomor = vb_nomor_wa( $nomor ? $nomor : vb_data( 'wa' ) );
	if ( ! $nomor ) {
		return 'mailto:' . vb_data( 'email' );
	}
	return 'https://wa.me/' . $nomor . '?text=' . rawurlencode( $pesan ? $pesan : vb_data( 'wa_pesan' ) );
}

add_action( 'admin_menu', function () {
	add_theme_page( 'Data Situs', 'Data Situs', 'edit_theme_options', 'vb-situs', 'vb_halaman_situs' );
} );

add_action( 'admin_init', function () {
	register_setting( 'vb_situs', 'vb_situs', array(
		'type'              => 'array',
		'sanitize_callback' => 'vb_bersihkan_situs',
	) );
} );

function vb_bersihkan_situs( $masuk ) {
	$masuk  = is_array( $masuk ) ? $masuk : array();
	$bersih = array();
	foreach ( vb_kolom_situs() as $k => $kolom ) {
		$bersih[ $k ] = sanitize_text_field( (string) ( $masuk[ $k ] ?? '' ) );
	}
	$bersih['kontak'] = array();
	foreach ( (array) ( $masuk['kontak'] ?? array() ) as $baris ) {
		$jenis = sanitize_key( $baris['jenis'] ?? '' );
		$isi   = trim( sanitize_textarea_field( (string) ( $baris['isi'] ?? '' ) ) );
		if ( 'email' === $jenis ) {
			$isi = sanitize_email( $isi );
		}
		if ( ! isset( vb_jenis_kontak()[ $jenis ] ) || '' === $isi ) {
			continue;
		}
		$bersih['kontak'][] = array(
			'jenis' => $jenis,
			'label' => sanitize_text_field( (string) ( $baris['label'] ?? '' ) ),
			'isi'   => $isi,
		);
	}
	$bersih['layanan'] = array();
	foreach ( (array) ( $masuk['layanan'] ?? array() ) as $baris ) {
		$nama = trim( sanitize_text_field( (string) ( $baris['nama'] ?? '' ) ) );
		if ( '' !== $nama ) {
			$bersih['layanan'][] = array( 'nama' => $nama );
		}
	}
	$bersih['sosmed'] = array();
	foreach ( (array) ( $masuk['sosmed'] ?? array() ) as $baris ) {
		$platform = sanitize_key( $baris['platform'] ?? '' );
		$url      = trim( (string) ( $baris['url'] ?? '' ) );
		if ( $url && ! preg_match( '#^https?://#i', $url ) ) {
			$url = 'https://' . ltrim( $url, '/' );
		}
		$url = esc_url_raw( $url );
		if ( isset( vb_platform_sosmed()[ $platform ] ) && $url ) {
			$bersih['sosmed'][] = array( 'platform' => $platform, 'url' => $url );
		}
	}
	return $bersih;
}

function vb_pilihan( $nama, $pilihan, $nilai ) {
	$html = '<select name="' . esc_attr( $nama ) . '">';
	foreach ( $pilihan as $k => $label ) {
		$html .= sprintf( '<option value="%s"%s>%s</option>', esc_attr( $k ), selected( $nilai, $k, false ), esc_html( $label ) );
	}
	return $html . '</select>';
}

function vb_tombol_baris() {
	return '<td class="vb-aksi"><button type="button" class="button vb-naik" title="Naik">↑</button> '
		. '<button type="button" class="button vb-turun" title="Turun">↓</button> '
		. '<button type="button" class="button vb-hapus" title="Hapus baris"><svg class="vb-hapus__ikon" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true" focusable="false"><path fill="currentColor" d="M9 3h6l1 2h4v2H4V5h4l1-2Zm-3 6h12l-1 12H7L6 9Zm4 2v8h2v-8h-2Zm4 0v8h2v-8h-2Z"/></svg><span>Hapus</span></button></td>';
}

function vb_baris_kontak( $i, $baris ) {
	$nama = 'vb_situs[kontak][' . $i . ']';
	return '<tr>'
		. '<td>' . vb_pilihan( $nama . '[jenis]', wp_list_pluck( vb_jenis_kontak(), 0 ), $baris['jenis'] ) . '</td>'
		. '<td><input type="text" class="regular-text" name="' . esc_attr( $nama . '[label]' ) . '" value="' . esc_attr( $baris['label'] ) . '" placeholder="Kosong = nama jenis" /></td>'
		. '<td><textarea class="large-text" rows="2" name="' . esc_attr( $nama . '[isi]' ) . '">' . esc_textarea( $baris['isi'] ) . '</textarea></td>'
		. vb_tombol_baris()
		. '</tr>';
}

function vb_baris_layanan( $i, $baris ) {
	$nama = 'vb_situs[layanan][' . $i . ']';
	return '<tr>'
		. '<td><input type="text" class="large-text" name="' . esc_attr( $nama . '[nama]' ) . '" value="' . esc_attr( $baris['nama'] ) . '" placeholder="mis. Pembuatan Website Company Profile" /></td>'
		. vb_tombol_baris()
		. '</tr>';
}

function vb_baris_sosmed( $i, $baris ) {
	$nama = 'vb_situs[sosmed][' . $i . ']';
	return '<tr>'
		. '<td>' . vb_pilihan( $nama . '[platform]', vb_platform_sosmed(), $baris['platform'] ) . '</td>'
		. '<td><input type="url" class="large-text" name="' . esc_attr( $nama . '[url]' ) . '" value="' . esc_attr( $baris['url'] ) . '" placeholder="https://…" /></td>'
		. vb_tombol_baris()
		. '</tr>';
}

function vb_halaman_situs() {
	$opsi = vb_opsi_situs();
	?>
	<style>
		.vb-daftar td { vertical-align: middle; }
		.vb-aksi { white-space: nowrap; text-align: right; }
		.vb-aksi .button { display: inline-flex; align-items: center; justify-content: center; gap: 4px; box-sizing: border-box; height: 32px; min-height: 32px; padding-top: 0; padding-bottom: 0; line-height: 1; vertical-align: middle; }
		.vb-aksi .vb-naik, .vb-aksi .vb-turun { min-width: 32px; padding: 0 8px; }
		.vb-aksi .vb-hapus { color: #b32d2e; border-color: #b32d2e; background: #fff; }
		.vb-aksi .vb-hapus:hover, .vb-aksi .vb-hapus:focus { color: #fff; border-color: #b32d2e; background: #b32d2e; box-shadow: none; }
		.vb-aksi .vb-hapus { gap: 6px; line-height: 1; }
		.vb-aksi .vb-hapus__ikon { display: block; flex: none; }
	</style>
	<div class="wrap">
		<h1>Data Situs</h1>
		<p>Dipakai blok Velocity Blocks: Kontak, Media Sosial, Tombol WhatsApp, Peta, dan Form Pemesanan (email tujuan = baris email pertama).</p>
		<form method="post" action="options.php">
			<?php settings_fields( 'vb_situs' ); ?>
			<h2>Identitas</h2>
			<p>Kolom kosong memakai isian bawaan tema (tertera sebagai contoh di kolom).</p>
			<table class="form-table" role="presentation">
				<?php foreach ( vb_kolom_situs() as $k => $kolom ) : ?>
					<tr>
						<th scope="row"><label for="vb-<?php echo esc_attr( $k ); ?>"><?php echo esc_html( $kolom[0] ); ?></label></th>
						<td><input class="regular-text" type="text" id="vb-<?php echo esc_attr( $k ); ?>" name="vb_situs[<?php echo esc_attr( $k ); ?>]" value="<?php echo esc_attr( is_string( $opsi[ $k ] ?? null ) ? $opsi[ $k ] : '' ); ?>" placeholder="<?php echo esc_attr( $kolom[2] ); ?>" /></td>
					</tr>
				<?php endforeach; ?>
			</table>

			<h2>Kontak</h2>
			<p>Tampil di blok Kontak (footer, halaman Contact) sesuai urutan. Label boleh diganti, mis. "Head Office", "Factory". Nomor WhatsApp/Telepon ditulis bebas (0812… atau +62…), tautannya dibuat otomatis. Baris yang isinya kosong dibuang saat disimpan.</p>
			<table class="widefat striped vb-daftar" data-daftar="kontak">
				<thead><tr><th style="width:160px">Jenis</th><th style="width:28%">Label</th><th>Isi</th><th style="width:200px"></th></tr></thead>
				<tbody>
					<?php
					foreach ( array_values( vb_daftar( 'kontak' ) ) as $i => $baris ) {
						echo vb_baris_kontak( $i, $baris ); // phpcs:ignore -- di-escape di fungsi.
					}
					?>
				</tbody>
			</table>
			<p><button type="button" class="button vb-tambah" data-untuk="kontak">+ Tambah kontak</button></p>

			<h2>Pilihan Layanan (form pemesanan)</h2>
			<p>Isi pilihan pada kolom "Layanan yang diminati" di blok Form Pemesanan. Kosong = pengunjung mengetik sendiri.</p>
			<table class="widefat striped vb-daftar" data-daftar="layanan">
				<thead><tr><th>Nama layanan</th><th style="width:200px"></th></tr></thead>
				<tbody>
					<?php
					foreach ( array_values( vb_daftar( 'layanan' ) ) as $i => $baris ) {
						echo vb_baris_layanan( $i, $baris ); // phpcs:ignore -- di-escape di fungsi.
					}
					?>
				</tbody>
			</table>
			<p><button type="button" class="button vb-tambah" data-untuk="layanan">+ Tambah layanan</button></p>

			<h2>Media Sosial</h2>
			<p>Ikon tampil di halaman Kontak dan footer sesuai urutan, dibuka di tab baru.</p>
			<table class="widefat striped vb-daftar" data-daftar="sosmed">
				<thead><tr><th style="width:160px">Platform</th><th>URL</th><th style="width:200px"></th></tr></thead>
				<tbody>
					<?php
					foreach ( array_values( vb_daftar( 'sosmed' ) ) as $i => $baris ) {
						echo vb_baris_sosmed( $i, $baris ); // phpcs:ignore -- di-escape di fungsi.
					}
					?>
				</tbody>
			</table>
			<p><button type="button" class="button vb-tambah" data-untuk="sosmed">+ Tambah media sosial</button></p>

			<template id="vb-baris-kontak"><?php echo vb_baris_kontak( '__i__', array( 'jenis' => 'telepon', 'label' => '', 'isi' => '' ) ); // phpcs:ignore ?></template>
			<template id="vb-baris-layanan"><?php echo vb_baris_layanan( '__i__', array( 'nama' => '' ) ); // phpcs:ignore ?></template>
			<template id="vb-baris-sosmed"><?php echo vb_baris_sosmed( '__i__', array( 'platform' => 'facebook', 'url' => '' ) ); // phpcs:ignore ?></template>
			<?php submit_button(); ?>
		</form>
	</div>
	<script>
	( function () {
		var urut = Date.now();
		document.querySelectorAll( '.vb-tambah' ).forEach( function ( tombol ) {
			tombol.addEventListener( 'click', function () {
				var tpl = document.getElementById( 'vb-baris-' + tombol.dataset.untuk ).innerHTML.replace( /__i__/g, urut++ );
				document.querySelector( '.vb-daftar[data-daftar="' + tombol.dataset.untuk + '"] tbody' ).insertAdjacentHTML( 'beforeend', tpl );
			} );
		} );
		document.querySelectorAll( '.vb-daftar' ).forEach( function ( tabel ) {
			tabel.addEventListener( 'click', function ( e ) {
				var tombol = e.target.closest( 'button' );
				var tr = e.target.closest( 'tr' );
				if ( ! tombol || ! tr ) {
					return;
				}
				if ( tombol.classList.contains( 'vb-hapus' ) ) {
					tr.remove();
				} else if ( tombol.classList.contains( 'vb-naik' ) && tr.previousElementSibling ) {
					tr.parentNode.insertBefore( tr, tr.previousElementSibling );
				} else if ( tombol.classList.contains( 'vb-turun' ) && tr.nextElementSibling ) {
					tr.parentNode.insertBefore( tr.nextElementSibling, tr );
				}
			} );
		} );
	} )();
	</script>
	<?php
}
