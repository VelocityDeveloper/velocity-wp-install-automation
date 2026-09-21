<?php
/**
 * Plugin Name: Velocity Galeri Popup
 * Description: Foto galeri bisa diklik → popup (lightbox) dengan tombol Previous/Next antar-foto dalam satu galeri. Berlaku untuk blok Galeri (termasuk yang ditambah klien di editor) dan shortcode [gallery] tema klasik. Dipasang installer (site-finish) dan ditimpa setiap finishing.
 */
defined('ABSPATH') || exit;

/**
 * Lightbox bawaan core (WP 6.9+/7.x) sudah punya navigasi Previous/Next antar-gambar dalam satu
 * core/gallery (konteks galleryId), tapi hanya aktif bila tiap core/image di dalamnya ber-atribut
 * lightbox.enabled dan tidak bertautan. Filter ini menyalakannya saat render untuk semua gambar
 * galeri; markup tersimpan tidak berubah. Lightbox yang sengaja dimatikan di editor dan tautan
 * khusus (custom URL) dihormati; tautan ke file/lampiran diganti popup.
 */
function velocity_galeri_popup_gambar(array $img) {
    if (($img['blockName'] ?? '') !== 'core/image') {
        return $img;
    }
    $a = $img['attrs'] ?? array();
    if (isset($a['lightbox']['enabled']) && !$a['lightbox']['enabled']) {
        return $img;
    }
    $tujuan = $a['linkDestination'] ?? 'none';
    if ('custom' === $tujuan || !empty($a['href']) && !in_array($tujuan, array('media', 'attachment'), true)) {
        return $img;
    }
    if (in_array($tujuan, array('media', 'attachment'), true)) {
        // Buang <a> pembungkus gambar supaya klik membuka popup, bukan halaman file.
        $buang = function ($html) {
            return is_string($html) ? preg_replace('#<a\b[^>]*>\s*(<img\b[^>]*>)\s*</a>#i', '$1', $html) : $html;
        };
        $img['innerHTML']    = $buang($img['innerHTML'] ?? '');
        $img['innerContent'] = array_map($buang, $img['innerContent'] ?? array());
        unset($a['href'], $a['linkTarget'], $a['rel'], $a['linkClass']);
        $a['linkDestination'] = 'none';
    }
    $a['lightbox'] = array('enabled' => true);
    $img['attrs']  = $a;
    return $img;
}

add_filter('render_block_data', function ($blok) {
    if (($blok['blockName'] ?? '') !== 'core/gallery' || empty($blok['innerBlocks'])) {
        return $blok;
    }
    $blok['innerBlocks'] = array_map('velocity_galeri_popup_gambar', $blok['innerBlocks']);
    return $blok;
}, 5);

/**
 * Shortcode [gallery] (tema klasik, halaman Galeri buatan installer) dirender sebagai blok
 * Galeri core ber-lightbox, jadi popup & tombol Previous/Next sama dengan situs FSE.
 * Galeri tanpa ids (lampiran post) memakai lampiran gambar post itu.
 */
add_filter('post_gallery', function ($keluaran, $attr) {
    if ('' !== $keluaran || !function_exists('do_blocks')) {
        return $keluaran;
    }
    $attr  = (array) $attr;
    $ids   = array();
    if (!empty($attr['ids'])) {
        $ids = array_filter(array_map('absint', explode(',', (string) $attr['ids'])));
    } elseif (!empty($attr['include'])) {
        $ids = array_filter(array_map('absint', explode(',', (string) $attr['include'])));
    } else {
        $ids = get_posts(array('post_parent' => get_the_ID(), 'post_type' => 'attachment', 'post_mime_type' => 'image', 'numberposts' => -1, 'orderby' => 'menu_order ID', 'order' => 'ASC', 'fields' => 'ids'));
    }
    $ids = array_values(array_filter($ids, 'wp_attachment_is_image'));
    if (!$ids) {
        return $keluaran;
    }
    $kolom = max(1, min(8, (int) ($attr['columns'] ?? 3)));
    $ukuran = 'large';
    $isi   = '';
    foreach ($ids as $id) {
        $src = wp_get_attachment_image_url($id, $ukuran);
        if (!$src) {
            continue;
        }
        $alt = trim((string) get_post_meta($id, '_wp_attachment_image_alt', true));
        $cap = trim((string) wp_get_attachment_caption($id));
        $at  = array('id' => $id, 'sizeSlug' => $ukuran, 'linkDestination' => 'none', 'lightbox' => array('enabled' => true));
        $isi .= '<!-- wp:image ' . wp_json_encode($at) . ' --><figure class="wp-block-image size-' . $ukuran . '"><img src="' . esc_url($src) . '" alt="' . esc_attr($alt) . '" class="wp-image-' . $id . '"/>'
            . ($cap ? '<figcaption class="wp-element-caption">' . esc_html($cap) . '</figcaption>' : '') . '</figure><!-- /wp:image -->';
    }
    if ('' === $isi) {
        return $keluaran;
    }
    $galeri = '<!-- wp:gallery {"columns":' . $kolom . ',"linkTo":"none","className":"velocity-galeri-popup"} --><figure class="wp-block-gallery has-nested-images columns-' . $kolom . ' is-cropped velocity-galeri-popup">'
        . $isi . '</figure><!-- /wp:gallery -->';
    return do_blocks($galeri);
}, 10, 2);

/** Popup berlatar gelap dengan tombol putih bulat (bawaan core: latar = warna latar tema, sering putih). */
add_action('wp_head', function () {
    echo '<style id="velocity-galeri-popup">'
        . '.wp-lightbox-overlay .scrim{background-color:rgb(12,12,12)!important}.wp-lightbox-overlay.active .scrim{opacity:.95!important}'
        . '.wp-lightbox-overlay .wp-lightbox-close-button,.wp-lightbox-overlay .wp-lightbox-navigation-button{fill:#fff!important;color:#fff!important}'
        . '.wp-lightbox-overlay .wp-lightbox-navigation-button{background:rgba(255,255,255,.14)!important;border-radius:50%!important;width:46px;height:46px;display:inline-flex;align-items:center;justify-content:center;padding:0!important}'
        . '.wp-lightbox-overlay .wp-lightbox-navigation-button:hover{background:rgba(255,255,255,.28)!important}'
        . '.wp-lightbox-overlay .wp-lightbox-navigation-button[hidden]{display:none!important}'
        . '.wp-lightbox-container .lightbox-trigger{opacity:1}'
        . '.wp-block-gallery .wp-lightbox-container img{cursor:zoom-in}'
        . '</style>';
}, 99);
