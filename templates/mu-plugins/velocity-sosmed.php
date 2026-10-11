<?php
/**
 * Plugin Name: Velocity Sosmed
 * Description: Shortcode [velocity-sosmed] — ikon sosial media dari Customizer tema (Sosial Media), sama dengan ikon header. Dipasang installer (site-finish) dan ditimpa setiap finishing.
 */
defined('ABSPATH') || exit;

// Widget Tentang Kami di footer tema berita (liputara.com, user 2026-10-11): ikon mengikuti isian
// Customizer > Sosial Media, bukan tautan tetap. Tema berita2 menyimpan link_sosmed_<kunci> dan
// header-nya memakai https://<kunci>.com/ bila kosong; bawaan="1" meniru perilaku itu.
add_shortcode('velocity-sosmed', function ($atts) {
    $a = shortcode_atts(['kunci' => 'facebook,twitter,instagram,youtube', 'awalan' => 'link_sosmed_', 'bawaan' => '1'], $atts, 'velocity-sosmed');
    $ikon = ['facebook' => ['facebook', 'Facebook'], 'twitter' => ['twitter-x', 'X'], 'x' => ['twitter-x', 'X'],
             'instagram' => ['instagram', 'Instagram'], 'youtube' => ['youtube', 'YouTube'], 'tiktok' => ['tiktok', 'TikTok'],
             'linkedin' => ['linkedin', 'LinkedIn'], 'whatsapp' => ['whatsapp', 'WhatsApp'], 'telegram' => ['telegram', 'Telegram']];
    $butir = '';
    foreach (array_filter(array_map('trim', explode(',', strtolower($a['kunci'])))) as $k) {
        $opsi = $a['awalan'] . $k;
        $url = function_exists('velocitytheme_option') ? velocitytheme_option($opsi) : get_theme_mod($opsi);
        if (!$url && $a['bawaan'] === '1') { $url = 'https://' . $k . '.com/'; }
        if (!$url) { continue; }
        [$bi, $nama] = $ikon[$k] ?? [$k, ucfirst($k)];
        $butir .= '<li><a href="' . esc_url($url) . '" target="_blank" rel="noopener" aria-label="' . esc_attr($nama) . '">'
                . '<i class="bi bi-' . esc_attr($bi) . '" aria-hidden="true"></i></a></li>';
    }
    return $butir ? '<ul class="vk-sosmed">' . $butir . '</ul>' : '';
});

// Widget Custom HTML tidak menjalankan shortcode di footer tema berita (liputara.com 2026-10-11:
// "[velocity-sosmed]" tampil apa adanya); hanya widget yang memuat shortcode ini yang diproses.
add_filter('widget_custom_html_content', function ($isi) {
    return has_shortcode($isi, 'velocity-sosmed') ? do_shortcode($isi) : $isi;
}, 20);
