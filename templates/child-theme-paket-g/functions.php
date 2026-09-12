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

if (!function_exists('{{PREFIX}}_tombol_wa')) {
    /** Tombol WhatsApp mengambang — kontak utama yang diminta klien di form. */
    function {{PREFIX}}_tombol_wa()
    {
        if (is_admin()) {
            return;
        }
        printf(
            '<a class="{{PREFIX}}-wa-float" href="%s" target="_blank" rel="noopener nofollow" aria-label="Hubungi via WhatsApp">'
                . '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2c-1.6 0-3.1-.4-4.4-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.4-.7-1.7-.8-.2-.1-.4-.1-.5.1l-.7.9c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.1-.2 0-.4.1-.5l.4-.5c.1-.2.2-.3.3-.5v-.4l-.7-1.7c-.2-.5-.4-.4-.5-.4h-.5c-.2 0-.5.1-.7.3-.3.3-.9.9-.9 2.1s.9 2.5 1 2.6c.1.2 1.8 2.8 4.4 3.9 1.6.7 2.2.7 3 .6.5-.1 1.4-.6 1.6-1.2.2-.6.2-1.1.1-1.2 0-.1-.2-.2-.4-.3Z"/></svg>'
                . '<span>Konsultasi</span></a>',
            esc_url({{PREFIX}}_wa_link())
        );
    }
    add_action('wp_footer', '{{PREFIX}}_tombol_wa');
}
