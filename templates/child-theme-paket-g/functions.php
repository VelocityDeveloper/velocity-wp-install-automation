<?php

/**
 * {{THEME_NAME}} — child theme desain custom.
 *
 * Dibuat untuk {{DOMAIN}} (Paket G). Desain mengikuti referensi
 * yang diminta klien di FORM ISIAN (kontraktorhijau.com) dengan susunan dan
 * warna yang dibedakan: palet navy + amber, dan tata letak yang disusun ulang
 * untuk layar HP lebih dulu.
 */

if (!defined('ABSPATH')) {
    exit;
}

define('{{PREFIX_UPPER}}_VERSION', '1.1.0');

foreach (array('theme-data.php', 'images.php', 'order-form.php', 'shortcodes.php') as ${{PREFIX}}_file) {
    require_once get_stylesheet_directory() . '/inc/' . ${{PREFIX}}_file;
}
unset(${{PREFIX}}_file);

if (!function_exists('{{PREFIX}}_enqueue')) {
    /**
     * Prioritas 20: tema induk memuat theme.min.css di prioritas 10, jadi CSS
     * desain ini harus menyusul supaya tidak tertimpa.
     */
    function {{PREFIX}}_enqueue()
    {
        $dir = get_stylesheet_directory();
        $uri = get_stylesheet_directory_uri();
        $theme = wp_get_theme();

        // Font desain; stack sistem tetap jadi cadangan di css/custom.css.
        wp_enqueue_style(
            '{{PREFIX}}-font',
            'https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap',
            array(),
            null
        );
        wp_enqueue_style(
            'parent-style',
            get_template_directory_uri() . '/style.css',
            array(),
            $theme->parent() ? $theme->parent()->get('Version') : null
        );
        wp_enqueue_style(
            'custom-style',
            $uri . '/css/custom.css',
            array('parent-style'),
            file_exists($dir . '/css/custom.css') ? filemtime($dir . '/css/custom.css') : {{PREFIX_UPPER}}_VERSION
        );
        wp_enqueue_script(
            '{{PREFIX}}-scripts',
            $uri . '/js/custom.js',
            array(),
            file_exists($dir . '/js/custom.js') ? filemtime($dir . '/js/custom.js') : {{PREFIX_UPPER}}_VERSION,
            true
        );
    }
    add_action('wp_enqueue_scripts', '{{PREFIX}}_enqueue', 20);
}

if (!function_exists('{{PREFIX}}_setup')) {
    function {{PREFIX}}_setup()
    {
        add_theme_support('post-thumbnails');
        add_theme_support('title-tag');
        add_theme_support('html5', array('search-form', 'gallery', 'caption', 'style', 'script'));
    }
    add_action('after_setup_theme', '{{PREFIX}}_setup');
}

if (!function_exists('{{PREFIX}}_body_class')) {
    /** Penanda supaya CSS desain ini tidak bocor ke halaman admin/plugin lain. */
    function {{PREFIX}}_body_class($classes)
    {
        $classes[] = '{{PREFIX}}';
        return $classes;
    }
    add_filter('body_class', '{{PREFIX}}_body_class');
}

if (!function_exists('{{PREFIX}}_buang_widget')) {
    /**
     * Desain ini tidak memakai widget: header, footer, dan sidebar semuanya
     * template sendiri. Area widget bawaan tema induk dilepas supaya tidak ada
     * kotak widget nyasar di halaman dan tidak membingungkan PM di wp-admin.
     *
     * Instance widget bawaan WordPress yang sudah terlanjur ada di basis data
     * dibersihkan installer sekali saat pemasangan (lihat site-finish --widget).
     */
    function {{PREFIX}}_buang_widget()
    {
        global $wp_registered_sidebars;
        foreach (array_keys((array) $wp_registered_sidebars) as $id) {
            unregister_sidebar($id);
        }
    }
    // Prioritas besar: tema induk mendaftarkan sidebar-nya di widgets_init juga.
    add_action('widgets_init', '{{PREFIX}}_buang_widget', 99);
}

/**
 * Tombol WhatsApp mengambang TIDAK dibuat di sini.
 *
 * Plugin velocity-addons sudah menyediakannya (Velocity_Addons_Floating_Whatsapp,
 * hook wp_footer) lengkap dengan halaman pengaturannya di wp-admin: nomor,
 * daftar kontak, teks tombol, pesan awal, dan posisi kiri/kanan. Nomornya diisi
 * installer lewat site-finish dari "Kontak utk di web" di form klien.
 *
 * Membuat tombol sendiri di tema hanya menghasilkan dua tombol menumpuk dan
 * satu di antaranya tidak bisa diatur PM lewat wp-admin.
 */
