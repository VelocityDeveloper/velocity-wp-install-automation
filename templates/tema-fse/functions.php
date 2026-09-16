<?php

/**
 * Velocity FSE — block theme bawaan installer untuk paket desain custom.
 *
 * Keputusan user 2026-09-14: desain custom dibangun sebagai block theme, bukan
 * child theme klasik, supaya bagian dinamis bisa disunting PM/klien dari
 * wp-admin. Kerangka (templates/, parts/, patterns/) sama untuk semua klien;
 * isi khas klien tinggal di database:
 *
 *   isi halaman (Beranda, Redaksi, Hubungi Kami, …)  -> post_content berupa blok
 *   menu                                              -> post wp_navigation
 *   palet warna                                       -> wp_global_styles
 *   nama, slogan, kontak publik                       -> opsi `velocity_situs`
 *                                                        (Tampilan → Data Situs)
 *
 * Karena itu memperbarui tema tidak pernah menimpa suntingan orang. Semuanya
 * dipasang & diisi oleh scripts/fse-apply di installer.
 */

defined('ABSPATH') || exit;

define('VELOCITY_FSE_VERSI', (string) wp_get_theme('velocity-fse')->get('Version'));

require get_theme_file_path('inc/situs.php');
require get_theme_file_path('inc/form.php');
require get_theme_file_path('inc/pengaturan.php');
require get_theme_file_path('inc/dealer.php');

add_action('after_setup_theme', function () {
    add_theme_support('wp-block-styles');
    add_theme_support('editor-styles');
    add_editor_style('style.css');
});

add_action('wp_enqueue_scripts', function () {
    wp_enqueue_style('velocity-fse', get_stylesheet_uri(), array(), VELOCITY_FSE_VERSI);
    // Font mengikuti referensi desain klien (scripts/fse-apply mengisi font_teks/font_judul
    // dengan slug fontFamilies di theme.json).
    $css = '';
    foreach (array('font_teks' => '--vf-font-teks', 'font_judul' => '--vf-font-judul') as $kunci => $var) {
        $font = sanitize_key((string) velocity_fse_situs($kunci));
        if ($font !== '') {
            $css .= $var . ':var(--wp--preset--font-family--' . $font . ');';
        }
    }
    if ($css !== '') {
        wp_add_inline_style('velocity-fse', 'body{' . $css . '}');
    }
    // Desain mengikuti referensi web klien (keputusan user 2026-09-15; opsi velocity_fse_desain
    // ditulis scripts/fse-apply): font referensi dari Google Fonts, radius tombol & kartu,
    // ketebalan judul. Warna tetap dari palet klien.
    $desain = velocity_fse_desain();
    if ($desain) {
        $keluarga = array();
        foreach ((array) ($desain['font_google'] ?? array()) as $nama) {
            $nama = velocity_fse_nama_font($nama);
            if ($nama !== '') {
                $keluarga[] = 'family=' . str_replace(' ', '+', $nama) . ':wght@400;500;600;700;800';
            }
        }
        if ($keluarga) {
            wp_enqueue_style('velocity-fse-font-referensi', 'https://fonts.googleapis.com/css2?' . implode('&', array_unique($keluarga)) . '&display=swap', array(), null);
        }
        $var = '';
        $teks = velocity_fse_nama_font($desain['font_teks'] ?? '');
        $judul = velocity_fse_nama_font($desain['font_judul'] ?? '');
        if ($teks !== '') {
            $var .= "--vf-font-teks:'" . $teks . "',-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;";
        }
        if ($judul !== '') {
            $var .= "--vf-font-judul:'" . $judul . "'," . (!empty($desain['serif_judul']) ? 'Georgia,serif' : "-apple-system,'Segoe UI',Arial,sans-serif") . ';';
        }
        $var .= '--vf-tombol-radius:' . min(999, max(0, (int) ($desain['tombol_radius'] ?? 6))) . 'px;';
        $var .= '--vf-kartu-radius:' . min(40, max(0, (int) ($desain['kartu_radius'] ?? 12))) . 'px;';
        $var .= '--vf-judul-tebal:' . min(900, max(300, (int) ($desain['judul_tebal'] ?? 700))) . ';';
        wp_add_inline_style('velocity-fse', 'body.vf-ref{' . $var . '}');
    }
});

/** Token desain referensi klien, atau array kosong kalau situs tanpa referensi. */
function velocity_fse_desain() {
    $desain = get_option('velocity_fse_desain', array());
    return (is_array($desain) && !empty($desain['url'])) ? $desain : array();
}

function velocity_fse_nama_font($nama) {
    return trim(preg_replace('/[^A-Za-z0-9 ]/', '', (string) $nama));
}

add_action('init', function () {
    // Blok dinamis tema dirender PHP; skrip editor ini hanya menampilkan
    // pratinjaunya (ServerSideRender) supaya tidak muncul "blok tidak didukung".
    wp_register_script(
        'velocity-fse-blok',
        get_theme_file_uri('assets/js/editor.js'),
        array('wp-blocks', 'wp-element', 'wp-server-side-render', 'wp-block-editor'),
        VELOCITY_FSE_VERSI,
        true
    );
    foreach ((array) glob(get_theme_file_path('blocks/*/block.json')) as $berkas) {
        register_block_type(dirname($berkas));
    }

    register_block_pattern_category('velocity', array('label' => 'Velocity'));

    // Data identitas dipakai di banyak tempat (footer, kolom samping): diikat ke
    // opsi, bukan diketik ulang. Nilainya disunting di Tampilan → Data Situs.
    if (function_exists('register_block_bindings_source')) {
        register_block_bindings_source('velocity/situs', array(
            'label'              => 'Data Situs',
            'get_value_callback' => function ($args) {
                $kunci = isset($args['key']) ? (string) $args['key'] : '';
                return in_array($kunci, velocity_fse_kunci_publik(), true) ? (string) velocity_fse_situs($kunci) : null;
            },
        ));
    }
});

add_filter('body_class', function ($kelas) {
    $kelas[] = velocity_fse_jenis_berita() ? 'vf-berita' : 'vf-perusahaan';
    // Gaya tampilan dari referensi desain klien: klasik | sorotan (lihat style.css).
    $gaya = (string) velocity_fse_situs('gaya');
    $kelas[] = 'vf-gaya-' . sanitize_html_class($gaya !== '' ? $gaya : 'klasik');
    // Header, footer, tombol & kartu mengikuti referensi web klien (lihat style.css "vf-ref").
    $desain = velocity_fse_desain();
    if ($desain) {
        $kelas[] = 'vf-ref';
        if (!empty($desain['terapkan_header'])) {
            $kelas[] = !empty($desain['header_gelap']) ? 'vf-header-gelap' : 'vf-header-terang';
            $kelas[] = 'vf-logo-' . (($desain['logo_posisi'] ?? '') === 'tengah' ? 'tengah' : 'kiri');
            $menu = (string) ($desain['menu_posisi'] ?? '');
            $kelas[] = 'vf-menu-' . (in_array($menu, array('kiri', 'tengah', 'kanan'), true) ? $menu : 'kanan');
            $kelas[] = !empty($desain['footer_gelap']) ? 'vf-footer-gelap' : 'vf-footer-terang';
            foreach (array('header_lengket' => 'vf-header-lengket', 'menu_kapital' => 'vf-menu-kapital') as $k => $c) {
                if (!empty($desain[$k])) { $kelas[] = $c; }
            }
            if (empty($desain['header_ajakan'])) { $kelas[] = 'vf-tanpa-ajakan'; }
            if (empty($desain['topbar'])) { $kelas[] = 'vf-tanpa-topbar'; }
        }
        foreach (array('tombol_kapital' => 'vf-tombol-kapital', 'judul_kapital' => 'vf-judul-kapital', 'kartu_bayangan' => 'vf-kartu-bayangan') as $k => $c) {
            if (!empty($desain[$k])) { $kelas[] = $c; }
        }
    }
    return $kelas;
});
