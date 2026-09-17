<?php

/**
 * Pustaka komponen referensi (rencana referensi VERSI 5, 2026-09-17).
 *
 * Token baru dari scripts/fse-apply (opsi velocity_fse_desain): font menu, bentuk tombol,
 * bingkai & jarak kartu, lebar wadah, dan header melayang. Semua aturan CSS-nya ada di
 * assets/css/referensi-komponen.css di balik body.vf-ref-v5, sehingga situs berreferensi
 * yang dibangun sebelum versi ini tidak berubah tampilannya.
 */

defined('ABSPATH') || exit;

function velocity_fse_ref_v5()
{
    $desain = velocity_fse_desain();
    return $desain && (int) ($desain['referensi_versi'] ?? 0) >= 5 ? $desain : array();
}

add_filter('body_class', function ($kelas) {
    $desain = velocity_fse_ref_v5();
    if (!$desain) {
        return $kelas;
    }
    $kelas[] = 'vf-ref-v5';
    if (!empty($desain['terapkan_header']) && !empty($desain['header_melayang'])) {
        $kelas[] = 'vf-ref-melayang';
    }
    if ((float) ($desain['wadah'] ?? 0) >= 0.5 || (int) ($desain['wadah_px'] ?? 0) >= 600) {
        $kelas[] = 'vf-ref-lebar';
    }
    return $kelas;
}, 20);

add_action('wp_enqueue_scripts', function () {
    if (!velocity_fse_desain()) {
        return;
    }
    wp_enqueue_style('velocity-fse-referensi-komponen', get_theme_file_uri('assets/css/referensi-komponen.css'),
        array('velocity-fse'), VELOCITY_FSE_VERSI);
    // Akordeon tahapan/FAQ: satu terbuka dalam satu kelompok, seperti web referensi.
    wp_add_inline_script('velocity-fse-slider', "document.addEventListener('toggle',function(e){var d=e.target;"
        . "if(!d.matches||!d.matches('details.vf-akordeon')||!d.open)return;"
        . "d.parentElement.querySelectorAll(':scope>details.vf-akordeon[open]').forEach(function(x){if(x!==d)x.open=false;});},true);");

    $desain = velocity_fse_ref_v5();
    if (!$desain) {
        return;
    }
    $var = '';
    $menu = velocity_fse_nama_font($desain['font_menu'] ?? '');
    if ($menu !== '') {
        $var .= "--vf-font-menu:'" . $menu . "',var(--vf-font-teks,sans-serif);";
    }
    $pad = (array) ($desain['tombol_padding'] ?? array());
    if (count($pad) === 2 && (int) $pad[0] > 0) {
        $var .= '--vf-tombol-pad-y:' . min(30, (int) $pad[0]) . 'px;--vf-tombol-pad-x:' . min(60, (int) $pad[1]) . 'px;';
    }
    if ((int) ($desain['tombol_tebal'] ?? 0) >= 300) {
        $var .= '--vf-tombol-tebal:' . min(900, (int) $desain['tombol_tebal']) . ';';
    }
    if ((float) ($desain['tombol_ukuran'] ?? 0) >= 11) {
        $var .= '--vf-tombol-ukuran:' . min(22, round((float) $desain['tombol_ukuran'], 1)) . 'px;';
    }
    if ((float) ($desain['kartu_border'] ?? 0) > 0) {
        $var .= '--vf-kartu-border:' . min(6, (float) $desain['kartu_border']) . 'px;';
        if (preg_match('/^#[0-9a-f]{6}$/i', (string) ($desain['kartu_border_warna'] ?? ''))) {
            $var .= '--vf-kartu-border-warna:' . $desain['kartu_border_warna'] . ';';
        }
    }
    if ((int) ($desain['kartu_padding'] ?? 0) > 0) {
        $var .= '--vf-kartu-pad:' . min(60, (int) $desain['kartu_padding']) . 'px;';
    }
    if ((int) ($desain['kartu_jarak'] ?? 0) > 0) {
        $var .= '--vf-kartu-jarak:' . min(60, (int) $desain['kartu_jarak']) . 'px;';
    }
    // Wadah tetap (px) atau cair (persen, boleh berbatas) — diukur di dua lebar layar.
    if ((int) ($desain['wadah_px'] ?? 0) >= 600) {
        $var .= '--vf-wadah:' . min(1600, (int) $desain['wadah_px']) . 'px;';
    } elseif ((float) ($desain['wadah'] ?? 0) >= 0.5) {
        $var .= '--vf-wadah-persen:' . round(min(0.98, (float) $desain['wadah']) * 100, 1) . '%;';
        if ((int) ($desain['wadah_maks'] ?? 0) >= 600) {
            $var .= '--vf-wadah-maks:' . min(1920, (int) $desain['wadah_maks']) . 'px;';
        }
    }
    $m = (array) ($desain['header_melayang'] ?? array());
    if ($m) {
        $var .= '--vf-melayang-lebar:' . max(60, min(97, (int) ($m['lebar'] ?? 90))) . '%;';
        $var .= '--vf-melayang-atas:' . max(0, min(40, (int) ($m['atas'] ?? 15))) . 'px;';
        $var .= '--vf-melayang-tinggi:' . max(40, min(140, (int) ($m['tinggi'] ?? 56))) . 'px;';
        $var .= '--vf-melayang-radius:' . max(0, min(40, (int) ($m['radius'] ?? 7))) . 'px;';
        if (preg_match('/^#[0-9a-f]{6}$/i', (string) ($m['latar'] ?? ''))) {
            $var .= '--vf-melayang-latar:' . $m['latar'] . ';';
        }
    }
    if ($var !== '') {
        wp_add_inline_style('velocity-fse-referensi-komponen', 'body.vf-ref-v5{' . $var . '}');
    }
}, 20);
