<?php

/**
 * Pustaka ikon untuk blok yang disunting langsung di editor (Kartu Ikon, dst.).
 *
 * Satu sumber untuk PHP (render) dan editor (dikirim ke window.vfIkon), supaya ikon yang
 * dipilih klien di toolbar sama persis dengan yang tampil di situs. Semua path untuk
 * viewBox 0 0 24 24, digambar dengan fill (tanpa berkas/huruf ikon tambahan).
 */

defined('ABSPATH') || exit;

function velocity_fse_ikon_daftar()
{
    return array(
        'alamat' => array('Alamat / Lokasi', 'M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z'),
        'whatsapp' => array('WhatsApp', 'M12 3.5a8.4 8.4 0 0 0-7.2 12.7L3.5 21l4.9-1.3A8.4 8.4 0 1 0 12 3.5Zm4.9 11.9c-.2.6-1.2 1.1-1.7 1.2-.4 0-1 .1-1.6-.1-.4-.1-.9-.3-1.5-.6-2.6-1.1-4.3-3.8-4.4-4-.1-.2-1-1.4-1-2.6s.6-1.8.8-2.1c.2-.2.5-.3.6-.3h.5c.2 0 .4 0 .6.4l.8 1.9c.1.1.1.3 0 .5l-.3.4-.4.4c-.1.1-.3.3-.1.6.1.3.6 1.1 1.4 1.8 1 .9 1.8 1.1 2 1.3.3.1.4.1.6-.1l.8-1c.2-.2.4-.2.6-.1l1.8.9c.3.1.4.2.5.3 0 .1 0 .5-.1 1.1Z'),
        'telepon' => array('Telepon', 'M6.6 3h3l1.5 3.7-2 1.3a12 12 0 0 0 5 5l1.3-2 3.7 1.5v3c0 .8-.7 1.5-1.5 1.5A15.5 15.5 0 0 1 5 5.5C5 4.7 5.7 4 6.6 4V3Z'),
        'email' => array('Email', 'M4 5h16c.6 0 1 .4 1 1v12c0 .6-.4 1-1 1H4a1 1 0 0 1-1-1V6c0-.6.4-1 1-1Zm8 7.2 7-4.4V6.6l-7 4.4-7-4.4v1.2l7 4.4Z'),
        'jam' => array('Jam Buka', 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm1 10.4 3.2 1.9-.8 1.3L11 13V6.5h2v5.9Z'),
        'web' => array('Website', 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm6.9 6h-3a15 15 0 0 0-1.3-4 8 8 0 0 1 4.3 4ZM12 4c.8 1.1 1.5 2.5 1.9 4h-3.8c.4-1.5 1.1-2.9 1.9-4ZM4.3 14a8 8 0 0 1 0-4h3.4a16 16 0 0 0 0 4H4.3Zm.8 2h3a15 15 0 0 0 1.3 4 8 8 0 0 1-4.3-4Zm3-8h-3a8 8 0 0 1 4.3-4 15 15 0 0 0-1.3 4ZM12 20c-.8-1.1-1.5-2.5-1.9-4h3.8c-.4 1.5-1.1 2.9-1.9 4Zm2.3-6H9.7a14 14 0 0 1 0-4h4.6a14 14 0 0 1 0 4Zm.3 6a15 15 0 0 0 1.3-4h3a8 8 0 0 1-4.3 4Zm1.7-6a16 16 0 0 0 0-4h3.4a8 8 0 0 1 0 4h-3.4Z'),
        'facebook' => array('Facebook', 'M13.5 9H15V6.5h-1.7c-2 0-3.3 1.2-3.3 3.3V11H8v2.5h2V21h2.6v-7.5h1.9l.4-2.5h-2.3V9.9c0-.6.2-.9.8-.9Z'),
        'instagram' => array('Instagram', 'M12 7.3a4.7 4.7 0 1 0 0 9.4 4.7 4.7 0 0 0 0-9.4Zm0 7.7a3 3 0 1 1 0-6 3 3 0 0 1 0 6Zm6-7.9a1.1 1.1 0 1 1-2.2 0 1.1 1.1 0 0 1 2.2 0ZM21 8c-.1-1.5-.4-2.8-1.5-3.9S17.5 2.7 16 2.6C14.5 2.5 9.5 2.5 8 2.6 6.5 2.7 5.2 3 4.1 4.1S2.7 6.5 2.6 8c-.1 1.5-.1 6.5 0 8 .1 1.5.4 2.8 1.5 3.9s2.4 1.4 3.9 1.5c1.5.1 6.5.1 8 0 1.5-.1 2.8-.4 3.9-1.5s1.4-2.4 1.5-3.9c.1-1.5.1-6.5 0-8Zm-2 9.6a3 3 0 0 1-1.7 1.7c-1.2.5-4 .4-5.3.4s-4.1.1-5.3-.4a3 3 0 0 1-1.7-1.7c-.5-1.2-.4-4-.4-5.3s-.1-4.1.4-5.3a3 3 0 0 1 1.7-1.7c1.2-.5 4-.4 5.3-.4s4.1-.1 5.3.4a3 3 0 0 1 1.7 1.7c.5 1.2.4 4 .4 5.3s.1 4.1-.4 5.3Z'),
        'linkedin' => array('LinkedIn', 'M6.9 8.6H4.3V20h2.6V8.6ZM5.6 4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3ZM20 13.6c0-3-1.6-4.4-3.8-4.4-1.7 0-2.5.9-2.9 1.6V8.6H10.7c0 .7 0 11.4 0 11.4h2.6v-6.4c0-.3 0-.7.1-.9.3-.7.9-1.4 1.9-1.4 1.3 0 1.9.9 1.9 2.4V20H20v-6.4Z'),
        'youtube' => array('YouTube', 'M21.6 7.2a2.5 2.5 0 0 0-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4A2.5 2.5 0 0 0 2.4 7.2 26 26 0 0 0 2 12a26 26 0 0 0 .4 4.8 2.5 2.5 0 0 0 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4a2.5 2.5 0 0 0 1.8-1.8A26 26 0 0 0 22 12a26 26 0 0 0-.4-4.8ZM10 15V9l5.2 3L10 15Z'),
        'tiktok' => array('TikTok', 'M16.6 5.8A4.3 4.3 0 0 1 15.5 3h-3.1v12.4a2.6 2.6 0 1 1-1.8-2.5V9.7a5.8 5.8 0 1 0 4.9 5.7V9.1a7.4 7.4 0 0 0 4.3 1.4V7.4a4.3 4.3 0 0 1-3.2-1.6Z'),
        'x' => array('X / Twitter', 'M17.5 3h2.8l-6.1 7 7.2 11h-5.6l-4.4-6.4L6.3 21H3.5l6.6-7.5L3.2 3h5.7l4 5.9L17.5 3Zm-1 16h1.6L8.1 4.7H6.4L16.5 19Z'),
        'pesan' => array('Pesan / Chat', 'M4 5h16c.6 0 1 .4 1 1v10c0 .6-.4 1-1 1H8l-4 4V6c0-.6.4-1 1-1Z'),
        'kantor' => array('Kantor / Gedung', 'M4 21V4c0-.6.4-1 1-1h9c.6 0 1 .4 1 1v4h4c.6 0 1 .4 1 1v12h-7v-4h-2v4H4Zm3-14v2h2V7H7Zm4 0v2h2V7h-2Zm-4 4v2h2v-2H7Zm4 0v2h2v-2h-2Zm6 0v2h2v-2h-2Zm0 4v2h2v-2h-2ZM7 15v2h2v-2H7Z'),
    );
}

/** <svg> satu ikon; ikon tak dikenal jatuh ke "pesan". */
function velocity_fse_ikon_svg($slug)
{
    $daftar = velocity_fse_ikon_daftar();
    $path = isset($daftar[$slug]) ? $daftar[$slug][1] : $daftar['pesan'][1];
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="' . esc_attr($path) . '"/></svg>';
}

/**
 * Nilai kontak dari Data Situs untuk blok yang isinya dikosongkan (atribut `sumber`).
 * [teks tampil, tautan] — tautan otomatis: wa.me, tel:, mailto:, Google Maps.
 */
function velocity_fse_kontak_sumber($sumber)
{
    $angka = function ($s) {
        $d = preg_replace('/\D/', '', (string) $s);
        return $d === '' ? '' : preg_replace('/^0/', '62', $d);
    };
    switch ($sumber) {
        case 'alamat':
            $a = (string) velocity_fse_situs('alamat');
            return array($a, $a !== '' ? 'https://www.google.com/maps/search/?api=1&query=' . rawurlencode($a) : '');
        case 'wa':
            $w = (string) velocity_fse_situs('wa');
            return array($w, $w !== '' ? 'https://wa.me/' . $angka($w) : '');
        case 'telp':
            $t = (string) velocity_fse_situs('telp');
            // Telepon yang sama dengan nomor WhatsApp tidak ditampilkan dua kali.
            if ($t === '' || $angka($t) === $angka(velocity_fse_situs('wa'))) {
                return array('', '');
            }
            return array($t, 'tel:' . preg_replace('/[^0-9+]/', '', $t));
        case 'email':
            $e = (string) velocity_fse_situs('email_publik');
            return array($e, $e !== '' ? 'mailto:' . $e : '');
    }
    return array('', '');
}

// Daftar ikon + nilai Data Situs untuk editor: pratinjau ikon di toolbar dan teks abu-abu
// (placeholder) saat isi kartu dikosongkan.
add_action('enqueue_block_editor_assets', function () {
    $ikon = array();
    foreach (velocity_fse_ikon_daftar() as $slug => $d) {
        $ikon[] = array('slug' => $slug, 'label' => $d[0], 'path' => $d[1]);
    }
    $situs = array();
    foreach (array('alamat', 'wa', 'telp', 'email') as $s) {
        $situs[$s] = velocity_fse_kontak_sumber($s)[0];
    }
    wp_add_inline_script('velocity-fse-blok',
        'window.vfIkon=' . wp_json_encode($ikon) . ';window.vfSitus=' . wp_json_encode($situs) . ';', 'before');
});
