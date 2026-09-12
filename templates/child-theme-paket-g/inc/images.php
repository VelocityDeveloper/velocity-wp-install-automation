<?php

/**
 * Peta gambar desain → Media Library.
 *
 * Opsi `{{PREFIX}}_images` berisi {kunci: ID attachment}, diisi saat deploy. Mengganti
 * foto cukup lewat Media Library (ganti berkas di ID yang sama) atau dengan
 * memperbarui opsi ini — tidak perlu menyentuh kode tema.
 */

defined('ABSPATH') || exit;

if (!function_exists('{{PREFIX}}_image_id')) {
    function {{PREFIX}}_image_id($key)
    {
        $map = get_option('{{PREFIX}}_images');
        return is_array($map) && !empty($map[$key]) ? (int) $map[$key] : 0;
    }
}

if (!function_exists('{{PREFIX}}_image_url')) {
    function {{PREFIX}}_image_url($key, $size = 'large')
    {
        $id = {{PREFIX}}_image_id($key);
        if (!$id) {
            return '';
        }
        $url = wp_get_attachment_image_url($id, $size);
        return $url ?: '';
    }
}

if (!function_exists('{{PREFIX}}_figure')) {
    /**
     * Gambar dengan rasio tetap. Kalau fotonya belum ada, yang tampil blok
     * bertekstur — bukan <img> rusak — sehingga tata letak tidak berubah saat
     * foto asli klien nanti dipasang.
     */
    function {{PREFIX}}_figure($key, $alt = '', $class = '', $size = 'large')
    {
        $id = {{PREFIX}}_image_id($key);
        $class = trim('{{PREFIX}}-figure ' . $class);
        if (!$id) {
            printf('<div class="%s {{PREFIX}}-figure--kosong" role="img" aria-label="%s"><span>%s</span></div>',
                esc_attr($class), esc_attr($alt ?: 'Foto menyusul'), esc_html($alt ?: 'Foto menyusul'));
            return;
        }
        printf('<div class="%s">%s</div>', esc_attr($class), wp_get_attachment_image($id, $size, false, array(
            'alt' => $alt,
            'loading' => 'lazy',
            'decoding' => 'async',
        )));
    }
}
