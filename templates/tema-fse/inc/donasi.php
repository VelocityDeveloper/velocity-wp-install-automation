<?php

/**
 * Plugin Velocity Donasi (CPT `donasi`, arsip /donasi/) di tema blok (permintaan user 2026-10-16).
 *
 * Plugin memuat Bootstrap 5 dari CDN di SEMUA halaman bila tema induk `velocity` tidak terpasang
 * (Paket G tidak memasangnya): reboot Bootstrap menimpa tipografi & tautan desain FSE. Bootstrap
 * dibiarkan hanya di halaman yang memakai UI plugin (detail program, arsip, halaman ber-shortcode
 * donasi), dan dimuat SEBELUM global styles & style.css tema supaya desain tetap menang.
 *
 * Kartu program di Query Loop: grup ber-kelas `vf-donasi-kartu` di dalam post-template diganti
 * kartu bergaya tema (foto, judul, progres, tombol). Shortcode [velocity-donasi-loop] tidak dipakai
 * di template karena template blok menjalankan do_shortcode SEBELUM blok dirender (semua kartu
 * jadi program yang sama) dan markupnya butuh Bootstrap.
 */

defined('ABSPATH') || exit;

function velocity_fse_donasi_aktif()
{
    return post_type_exists('donasi') && function_exists('get_total_donasi_masuk');
}

function velocity_fse_halaman_donasi()
{
    if (is_singular('donasi') || is_post_type_archive('donasi') || is_tax('kategori-donasi')) {
        return true;
    }
    $p = get_queried_object();
    return is_singular() && $p instanceof WP_Post
        && preg_match('/\[(halaman-donatur|bank-donasi|velocity-(donasi-[a-z]+|progress-donasi|daftar-donatur|update-donasi))\b/', $p->post_content);
}

add_action('wp_enqueue_scripts', function () {
    if (!wp_style_is('vdonasi-bootstrap-style') && !wp_script_is('vdonasi-bootstrap-js')) {
        return;
    }
    if (!velocity_fse_halaman_donasi()) {
        wp_dequeue_style('vdonasi-bootstrap-style');
        wp_dequeue_script('vdonasi-bootstrap-js');
        return;
    }
    foreach (array('global-styles', 'velocity-fse') as $handle) {
        $gaya = wp_styles()->query($handle);
        if ($gaya && !in_array('vdonasi-bootstrap-style', $gaya->deps, true)) {
            $gaya->deps[] = 'vdonasi-bootstrap-style';
        }
    }
}, 100);

function velocity_fse_kartu_donasi($id)
{
    $target = (float) get_post_meta($id, 'target', true);
    $masuk = (float) get_total_donasi_masuk($id);
    $persen = $target > 0 ? min(100, $masuk / $target * 100) : 0;
    $rp = function ($n) {
        return 'Rp' . number_format($n, 0, ',', '.');
    };
    $url = get_permalink($id);
    $html = '<div class="vf-donasi-kartu">';
    if (has_post_thumbnail($id)) {
        $html .= '<a class="vf-donasi-kartu__foto" href="' . esc_url($url) . '">'
            . get_the_post_thumbnail($id, 'medium_large', array('loading' => 'lazy')) . '</a>';
    }
    $html .= '<div class="vf-donasi-kartu__isi">';
    $html .= '<h3 class="vf-donasi-kartu__judul"><a href="' . esc_url($url) . '">' . esc_html(get_the_title($id)) . '</a></h3>';
    $html .= '<div class="vf-donasi-kartu__progres" role="progressbar" aria-valuenow="' . round($persen)
        . '" aria-valuemin="0" aria-valuemax="100"><span style="width:' . round($persen, 1) . '%"></span></div>';
    $html .= '<p class="vf-donasi-kartu__angka"><strong>' . esc_html($rp($masuk)) . '</strong> '
        . ($target > 0 ? 'terkumpul dari ' . esc_html($rp($target)) : 'terkumpul') . '</p>';
    $akhir = get_post_meta($id, 'tanggal_berakhir', true);
    if ($akhir) {
        $html .= '<p class="vf-donasi-kartu__akhir">Berakhir ' . esc_html(date_i18n('j F Y', strtotime($akhir))) . '</p>';
    }
    $html .= '<a class="wp-element-button vf-donasi-kartu__tombol" href="' . esc_url($url) . '">Donasi Sekarang</a>';
    return $html . '</div></div>';
}

add_filter('render_block_core/group', function ($isi, $blok) {
    $kelas = isset($blok['attrs']['className']) ? (string) $blok['attrs']['className'] : '';
    if (!preg_match('/(^|\s)vf-donasi-kartu(\s|$)/', $kelas) || !velocity_fse_donasi_aktif() || get_post_type() !== 'donasi') {
        return $isi;
    }
    return velocity_fse_kartu_donasi(get_the_ID());
}, 10, 2);
