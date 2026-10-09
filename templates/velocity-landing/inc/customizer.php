<?php
/**
 * Customizer: panel "Landing Page" dibangun dari vlp_skema().
 *
 * Tiap seksi beranda punya partial selective refresh (#vlp-{seksi}) sehingga perubahan
 * teks/gambar langsung tampil di pratinjau tanpa memuat ulang halaman, lengkap dengan
 * ikon pensil untuk melompat ke kontrolnya. Warna diperbarui langsung lewat JS.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;

/**
 * Sanitasi per jenis field.
 */
function vlp_sanitize_callback($type)
{
	switch ($type) {
		case 'checkbox':
			return 'vlp_sanitize_checkbox';
		case 'color':
			return 'sanitize_hex_color';
		case 'url':
		case 'image':
			return 'esc_url_raw';
		case 'textarea':
			return 'wp_kses_post';
		case 'ikon':
			return 'vlp_sanitize_ikon';
		case 'select':
			return 'vlp_sanitize_select';
		case 'repeater':
			return 'vlp_sanitize_repeater';
		default:
			return 'sanitize_text_field';
	}
}

function vlp_sanitize_checkbox($nilai)
{
	return (bool) $nilai;
}

function vlp_sanitize_ikon($nilai)
{
	return trim(preg_replace('/[^a-z0-9\- ]/', '', strtolower((string) $nilai)));
}

function vlp_sanitize_select($nilai, $setting)
{
	$kontrol = $setting->manager->get_control($setting->id);
	$pilihan = $kontrol ? $kontrol->choices : array();
	return isset($pilihan[$nilai]) ? $nilai : $setting->default;
}

/**
 * Repeater: JSON daftar item. Tiap nilai disanitasi menurut jenis field-nya di skema.
 */
function vlp_sanitize_repeater($nilai, $setting)
{
	$data = is_string($nilai) ? json_decode(wp_unslash($nilai), true) : $nilai;
	if (!is_array($data)) {
		return $setting->default;
	}
	$fields = array();
	if (preg_match('/^vlp_([a-z]+)_(.+)$/', $setting->id, $m)) {
		$skema = vlp_skema();
		$fields = isset($skema[$m[1]]['fields'][$m[2]]['fields']) ? $skema[$m[1]]['fields'][$m[2]]['fields'] : array();
	}
	$hasil = array();
	foreach ($data as $item) {
		if (!is_array($item)) {
			continue;
		}
		$rapi = array();
		foreach ($fields as $f => $def) {
			$v = isset($item[$f]) ? (string) $item[$f] : '';
			switch ($def['type']) {
				case 'image':
				case 'url':
					$v = esc_url_raw($v);
					break;
				case 'textarea':
					$v = wp_kses_post($v);
					break;
				case 'ikon':
					$v = vlp_sanitize_ikon($v);
					break;
				default:
					$v = sanitize_text_field($v);
			}
			$rapi[$f] = $v;
		}
		$hasil[] = $rapi;
	}
	return wp_json_encode($hasil);
}

add_action('customize_register', 'vlp_customize_register', 20);

function vlp_customize_register($wp_customize)
{
	require_once get_stylesheet_directory() . '/inc/class-vlp-repeater-control.php';

	$wp_customize->add_panel('vlp_landing', array(
		'title'       => 'Landing Page',
		'description' => 'Semua isi beranda landing page. Klik ikon pensil di pratinjau untuk langsung ke pengaturan bagian itu.',
		'priority'    => 25,
	));

	$prioritas = 10;
	foreach (vlp_skema() as $id => $seksi) {
		$wp_customize->add_section('vlp_' . $id, array(
			'title'    => $seksi['title'],
			'panel'    => 'vlp_landing',
			'priority' => $prioritas,
		));
		$prioritas += 10;

		$kunci_seksi = array();
		foreach ($seksi['fields'] as $f => $def) {
			$kunci = 'vlp_' . $id . '_' . $f;
			$kunci_seksi[] = $kunci;

			// Warna diperbarui langsung (JS); nomor WA, font & tab baru memengaruhi banyak seksi → muat ulang.
			if ('color' === $def['type'] || 'efek_cahaya' === $f) {
				$transport = 'postMessage';
			} elseif ('umum' === $id) {
				$transport = 'refresh';
			} else {
				$transport = 'postMessage';
			}

			$wp_customize->add_setting($kunci, array(
				'default'           => 'repeater' === $def['type'] ? wp_json_encode($def['default']) : $def['default'],
				'transport'         => $transport,
				'sanitize_callback' => vlp_sanitize_callback($def['type']),
			));

			$args = array(
				'label'       => $def['label'],
				'section'     => 'vlp_' . $id,
				'description' => isset($def['description']) ? $def['description'] : '',
			);

			switch ($def['type']) {
				case 'image':
					$wp_customize->add_control(new WP_Customize_Image_Control($wp_customize, $kunci, $args));
					break;
				case 'color':
					$wp_customize->add_control(new WP_Customize_Color_Control($wp_customize, $kunci, $args));
					break;
				case 'ikon':
					$args['type'] = 'text';
					$args['description'] = 'Kelas ikon Font Awesome 6, mis. <code>fa-solid fa-star</code>. Cari di <a href="https://fontawesome.com/search?o=r&m=free" target="_blank" rel="noopener">fontawesome.com</a>.';
					$wp_customize->add_control($kunci, $args);
					break;
				case 'repeater':
					$args['vlp_fields'] = $def['fields'];
					$args['vlp_item_label'] = $def['item_label'];
					$wp_customize->add_control(new VLP_Repeater_Control($wp_customize, $kunci, $args));
					break;
				case 'select':
					$args['type'] = 'select';
					$args['choices'] = $def['choices'];
					$wp_customize->add_control($kunci, $args);
					break;
				default:
					$args['type'] = $def['type'];
					$wp_customize->add_control($kunci, $args);
			}
		}

		// Seksi beranda & footer: selective refresh. Warna/umum tidak butuh partial.
		if ('umum' !== $id && isset($wp_customize->selective_refresh)) {
			$wp_customize->selective_refresh->add_partial('vlp_partial_' . $id, array(
				'selector'            => '#vlp-' . $id,
				'settings'            => $kunci_seksi,
				'container_inclusive' => true,
				'render_callback'     => function () use ($id) {
					vlp_seksi($id);
				},
				'fallback_refresh'    => true,
			));
		}
	}
}

/**
 * Skrip & gaya kontrol repeater di panel Customizer.
 */
add_action('customize_controls_enqueue_scripts', function () {
	wp_enqueue_media();
	wp_enqueue_style('vlp-customize-repeater', get_stylesheet_directory_uri() . '/assets/css/customize-repeater.css', array(), VLP_VERSI);
	wp_enqueue_script('vlp-customize-repeater', get_stylesheet_directory_uri() . '/assets/js/customize-repeater.js', array('customize-controls', 'jquery', 'jquery-ui-sortable'), VLP_VERSI, true);
});

/**
 * Pratinjau warna langsung + efek cahaya.
 */
add_action('customize_preview_init', function () {
	wp_enqueue_script(
		'vlp-customize-preview',
		get_stylesheet_directory_uri() . '/assets/js/customize-preview.js',
		array('customize-preview', 'jquery'),
		VLP_VERSI,
		true
	);
});
