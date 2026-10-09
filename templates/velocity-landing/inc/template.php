<?php
/**
 * Helper tampilan landing page.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;

/**
 * Nilai field dari Customizer, jatuh ke nilai bawaan skema.
 */
function vlp_mod($seksi, $field)
{
	$skema = vlp_skema();
	$bawaan = isset($skema[$seksi]['fields'][$field]['default']) ? $skema[$seksi]['fields'][$field]['default'] : '';
	return get_theme_mod('vlp_' . $seksi . '_' . $field, $bawaan);
}

/**
 * Tautan WhatsApp dari nomor & pesan di "Umum & Warna".
 */
function vlp_wa_url()
{
	$nomor = preg_replace('/\D/', '', (string) vlp_mod('umum', 'wa_nomor'));
	if (0 === strpos($nomor, '0')) {
		$nomor = '62' . substr($nomor, 1);
	}
	$url = 'https://wa.me/' . $nomor;
	$pesan = trim((string) vlp_mod('umum', 'wa_pesan'));
	return $pesan ? $url . '?text=' . rawurlencode($pesan) : $url;
}

/**
 * Tautan tombol: kosong = WhatsApp.
 */
function vlp_link($url)
{
	$url = trim((string) $url);
	return '' === $url ? vlp_wa_url() : $url;
}

/**
 * Atribut target untuk tautan tombol.
 */
function vlp_target()
{
	return vlp_mod('umum', 'tab_baru') ? ' target="_blank" rel="noopener"' : '';
}

/**
 * Teks panjang → paragraf. Baris kosong memisahkan paragraf.
 */
function vlp_paragraf($teks)
{
	return wpautop(wp_kses_post((string) $teks));
}

/**
 * Teks satu baris per butir → array butir tidak kosong.
 */
function vlp_baris($teks)
{
	return array_values(array_filter(array_map('trim', preg_split('/\R/', (string) $teks))));
}

/**
 * Judul dengan baris baru diizinkan.
 */
function vlp_judul($teks)
{
	return nl2br(wp_kses_post(trim((string) $teks)), false);
}

/**
 * Gambar: lampiran media → wp_get_attachment_image (srcset); gambar bawaan tema → <img> biasa.
 */
function vlp_img($url, $alt = '', $class = '', $ukuran = 'large', $sizes = '')
{
	$url = trim((string) $url);
	if ('' === $url) {
		return '';
	}
	$attr = array('class' => $class, 'alt' => wp_strip_all_tags($alt), 'loading' => 'lazy', 'decoding' => 'async');
	if ($sizes) {
		$attr['sizes'] = $sizes;
	}
	$id = attachment_url_to_postid($url);
	if ($id) {
		return wp_get_attachment_image($id, $ukuran, false, $attr);
	}
	$dimensi = '';
	$tema = get_stylesheet_directory_uri();
	if (0 === strpos($url, $tema)) {
		$berkas = get_stylesheet_directory() . substr($url, strlen($tema));
		$info = is_readable($berkas) ? @getimagesize($berkas) : false;
		if ($info) {
			$dimensi = sprintf(' width="%d" height="%d"', $info[0], $info[1]);
		}
	}
	return sprintf(
		'<img src="%s" alt="%s" class="%s"%s loading="lazy" decoding="async">',
		esc_url($url),
		esc_attr($attr['alt']),
		esc_attr($class),
		$dimensi
	);
}

/**
 * Ikon Font Awesome.
 */
function vlp_ikon($kelas, $tambahan = '')
{
	$kelas = trim((string) $kelas);
	return $kelas ? '<i class="' . esc_attr($kelas . ' ' . $tambahan) . '" aria-hidden="true"></i>' : '';
}

/**
 * Item berulang yang terisi (kunci pertama dipakai sebagai penentu tampil).
 */
function vlp_item($seksi, $penentu)
{
	$skema = vlp_skema();
	$u = $skema[$seksi]['ulang'];
	$hasil = array();
	for ($n = 1; $n <= $u['jumlah']; $n++) {
		$item = array();
		foreach (array_keys($u['fields']) as $f) {
			$item[$f] = vlp_mod($seksi, 'item' . $n . '_' . $f);
		}
		if ('' !== trim((string) $item[$penentu])) {
			$hasil[] = $item;
		}
	}
	return $hasil;
}

/**
 * Item repeater (JSON di theme_mod, atau array bawaan skema). Item tanpa satu pun isi dibuang.
 */
function vlp_repeater($seksi, $field)
{
	$nilai = vlp_mod($seksi, $field);
	if (is_string($nilai)) {
		$nilai = json_decode($nilai, true);
	}
	if (!is_array($nilai)) {
		return array();
	}
	$skema = vlp_skema();
	$kunci = array_keys($skema[$seksi]['fields'][$field]['fields']);
	$hasil = array();
	foreach ($nilai as $item) {
		if (!is_array($item)) {
			continue;
		}
		$rapi = array();
		foreach ($kunci as $k) {
			$rapi[$k] = isset($item[$k]) ? (string) $item[$k] : '';
		}
		if (implode('', array_map('trim', $rapi)) !== '') {
			$hasil[] = $rapi;
		}
	}
	return $hasil;
}

/**
 * Tampilkan satu seksi. Seksi tersembunyi tetap meninggalkan penanda kosong di pratinjau
 * Customizer supaya selective refresh bisa memunculkannya lagi.
 */
function vlp_seksi($id)
{
	$skema = vlp_skema();
	if (!isset($skema[$id])) {
		return;
	}
	if (isset($skema[$id]['fields']['tampil']) && !vlp_mod($id, 'tampil')) {
		if (is_customize_preview()) {
			echo '<div id="vlp-' . esc_attr($id) . '" class="vlp-tersembunyi"></div>';
		}
		return;
	}
	get_template_part('template-parts/seksi', $id);
}

/**
 * Variabel CSS dari warna & font Customizer.
 */
function vlp_css_variabel()
{
	$w = array(
		'latar'  => vlp_mod('umum', 'warna_latar'),
		'teks'   => vlp_mod('umum', 'warna_teks'),
		'utama'  => vlp_mod('umum', 'warna_utama'),
		'aksen'  => vlp_mod('umum', 'warna_aksen'),
		'sorot'  => vlp_mod('umum', 'warna_sorot'),
		'cahaya' => vlp_mod('umum', 'warna_cahaya'),
		'footer' => vlp_mod('umum', 'warna_footer'),
	);
	$css = ':root{';
	foreach ($w as $k => $v) {
		$css .= '--vlp-' . $k . ':' . (sanitize_hex_color($v) ?: '#000') . ';';
	}
	$css .= '--vlp-font:"' . esc_attr(vlp_mod('umum', 'font')) . '",system-ui,sans-serif;}';
	return $css;
}

/**
 * Tautan media sosial footer yang terisi: [jaringan => [url, kelas ikon, nama]].
 */
function vlp_sosmed()
{
	$daftar = array(
		'facebook'  => array('fa-brands fa-facebook', 'Facebook'),
		'instagram' => array('fa-brands fa-instagram', 'Instagram'),
		'x'         => array('fa-brands fa-x-twitter', 'X'),
		'youtube'   => array('fa-brands fa-youtube', 'YouTube'),
		'tiktok'    => array('fa-brands fa-tiktok', 'TikTok'),
		'linkedin'  => array('fa-brands fa-linkedin', 'LinkedIn'),
	);
	$hasil = array();
	foreach ($daftar as $k => $v) {
		$url = trim((string) vlp_mod('footer', $k));
		if ($url) {
			$hasil[$k] = array($url, $v[0], $v[1]);
		}
	}
	return $hasil;
}
