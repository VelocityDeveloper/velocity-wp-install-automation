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
require get_theme_file_path('inc/ikon.php');
require get_theme_file_path('inc/form.php');
require get_theme_file_path('inc/cf7.php');
require get_theme_file_path('inc/pengaturan.php');
require get_theme_file_path('inc/dealer.php');
require get_theme_file_path('inc/produk.php');
require get_theme_file_path('inc/referensi.php');

add_action('after_setup_theme', function () {
    add_theme_support('wp-block-styles');
    add_theme_support('editor-styles');
    add_editor_style('style.css');
});

add_action('wp_enqueue_scripts', function () {
    wp_enqueue_style('velocity-fse', get_stylesheet_uri(), array(), VELOCITY_FSE_VERSI);
    if (velocity_fse_situs('gaya') === 'klinik') {
        wp_enqueue_script('velocity-fse-menu-hp', get_theme_file_uri('assets/js/menu-hp.js'), array(), VELOCITY_FSE_VERSI,
            array('in_footer' => true, 'strategy' => 'defer'));
    }
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
        array('wp-blocks', 'wp-element', 'wp-server-side-render', 'wp-block-editor', 'wp-components'),
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
            // Token referensi 2026-09-17 (rencana VERSI 3, yukpergimancing.com): topbar gelap,
            // menu berwarna, keranjang di header, footer 5 kolom + pita hak cipta.
            foreach (array('topbar_gelap' => 'vf-topbar-gelap', 'menu_berwarna' => 'vf-menu-berwarna',
                'footer_pita' => 'vf-footer-pita') as $k => $c) {
                if (!empty($desain[$k])) { $kelas[] = $c; }
            }
            if (!empty($desain['header_keranjang']) && velocity_fse_toko()) { $kelas[] = 'vf-header-keranjang'; }
            // Token rencana VERSI 4 (2026-09-17, centralimpex.com): kotak cari, logo & baris hak
            // cipta footer, judul kolom footer, banner judul halaman dalam.
            if (!empty($desain['header_tanpa_garis'])) { $kelas[] = 'vf-header-tanpa-garis'; }
            if (!empty($desain['wadah_tetap'])) { $kelas[] = 'vf-wadah-tetap'; }
            if (!empty($desain['tanpa_cari'])) { $kelas[] = 'vf-tanpa-cari'; }
            if (!empty($desain['footer_logo'])) { $kelas[] = 'vf-footer-logo'; }
            $bawah = (string) ($desain['footer_bawah_rata'] ?? '');
            if (in_array($bawah, array('terbelah', 'tengah'), true)) { $kelas[] = 'vf-hak-cipta-' . $bawah; }
            if (array_key_exists('footer_judul_kapital', $desain) && empty($desain['footer_judul_kapital'])) {
                $kelas[] = 'vf-footer-judul-biasa';
            }
            $banner = (string) ($desain['banner_latar'] ?? '');
            if (in_array($banner, array('gelap', 'aksen', 'foto', 'abu', 'terang'), true)) {
                $kelas[] = 'vf-banner-' . $banner;
                $kelas[] = 'vf-banner-' . (($desain['banner_rata'] ?? '') === 'tengah' ? 'tengah' : 'kiri');
                $tinggi = (string) ($desain['banner_tinggi'] ?? '');
                if (in_array($tinggi, array('tinggi', 'sedang'), true)) { $kelas[] = 'vf-banner-' . $tinggi; }
            }
            if ((int) ($desain['footer_kolom'] ?? 0) >= 5 && velocity_fse_toko()) { $kelas[] = 'vf-footer-5'; }
        }
        // Aksen klien berwarna netral (abu) tidak cukup kontras sebagai tombol: tombol memakai warna utama.
        if (($desain['tombol_warna'] ?? '') === 'primary') { $kelas[] = 'vf-tombol-primary'; }
        foreach (array('tombol_kapital' => 'vf-tombol-kapital', 'judul_kapital' => 'vf-judul-kapital', 'kartu_bayangan' => 'vf-kartu-bayangan') as $k => $c) {
            if (!empty($desain[$k])) { $kelas[] = $c; }
        }
        // Versi aturan tampilan (manifest `velocity_palet_versi`). Aturan baru dipasang
        // di balik kelas ini supaya situs yang sudah jadi tidak ikut berubah.
        if ((int) ($desain['tampilan_versi'] ?? 1) >= 2) { $kelas[] = 'vf-tampilan-2'; }
    }
    return $kelas;
});

// Logo situs di kolom pertama footer bila referensinya berlogo (token footer_logo).
add_filter('render_block_core/site-title', function ($html, $blok) {
    $desain = velocity_fse_desain();
    if (empty($desain['footer_logo']) || strpos((string) ($blok['attrs']['className'] ?? ''), 'vf-footer__nama') === false) {
        return $html;
    }
    $logo = (int) get_theme_mod('custom_logo');
    $gambar = $logo ? wp_get_attachment_image($logo, 'medium', false, array('class' => 'vf-footer__logo-img', 'alt' => get_bloginfo('name'))) : '';
    return $gambar ? '<a class="vf-footer__logo" href="' . esc_url(home_url('/')) . '">' . $gambar . '</a>' : $html;
}, 10, 2);

// Banner judul halaman dalam mengikuti referensi (token banner_*): foto latar dari slot hero
// dan breadcrumb "Beranda / Judul" bila referensinya memakai keduanya.
add_filter('render_block_core/group', function ($html, $blok) {
    if (strpos((string) ($blok['attrs']['className'] ?? ''), 'vf-judul-halaman') === false || is_front_page()) {
        return $html;
    }
    $desain = velocity_fse_desain();
    if (($desain['banner_latar'] ?? '') === 'foto') {
        $slot = (array) get_option('vfse_images', array());
        $url = !empty($slot['hero']) ? wp_get_attachment_image_url((int) $slot['hero'], 'large') : '';
        if ($url) {
            $var = '--vf-banner-foto:url(' . esc_url($url) . ');';
            // Atribut style yang sudah ada (padding) dipertahankan: style kedua diabaikan browser.
            $html = preg_match('/(class="wp-block-group vf-judul-halaman[^"]*"\s+style=")/', $html)
                ? preg_replace('/(class="wp-block-group vf-judul-halaman[^"]*"\s+style=")/', '$1' . $var, $html, 1)
                : preg_replace('/class="wp-block-group vf-judul-halaman/', 'style="' . $var . '" $0', $html, 1);
        }
    }
    if (!empty($desain['banner_remah']) && is_singular()) {
        $remah = '<nav class="vf-remah" aria-label="Breadcrumb"><a href="' . esc_url(home_url('/')) . '">Beranda</a>'
            . ' <span aria-hidden="true">/</span> <span>' . esc_html(get_the_title()) . '</span></nav>';
        $html = preg_replace('/<\/div>\s*$/', $remah . '</div>', $html, 1);
    }
    return $html;
}, 10, 2);


// Tautan root-relatif di berkas tema (mis. tombol "Hubungi Kami" di parts/header.html
// href="/hubungi-kami/") menunjuk ke AKAR DOMAIN. Di situs yang dipasang dalam subfolder
// — staging velocitydeveloper.co/<domain> — tautan itu keluar dari situsnya sama sekali
// (solusicerdasconsulting.com, 2026-09-18). Jalur situs ditambahkan saat render.
add_filter('render_block', function ($html) {
    if ($html === '' || strpos($html, 'href="/') === false) {
        return $html;
    }
    $jalur = rtrim((string) wp_parse_url(home_url('/'), PHP_URL_PATH), '/');
    if ($jalur === '') {
        return $html;
    }
    // Hanya jalur dalam situs: "//host" (protokol-relatif) dan jalur yang sudah berawalan
    // jalur situs dibiarkan.
    return preg_replace(
        '#href="/(?!/)(?!' . preg_quote(ltrim($jalur, '/'), '#') . '/)#',
        'href="' . $jalur . '/',
        $html
    );
}, 5);
