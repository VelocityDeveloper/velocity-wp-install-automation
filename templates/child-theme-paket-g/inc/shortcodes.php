<?php

/**
 * Blok desain yang dipakai ulang di beranda dan halaman dalam.
 *
 * Tiap blok punya fungsi render + shortcode, supaya halaman Layanan/Produk/
 * Galeri/Pemesanan cukup berisi teks pembuka + shortcode dan tetap bisa
 * disunting lewat editor WordPress.
 */

defined('ABSPATH') || exit;

if (!function_exists('{{PREFIX}}_ikon')) {
    /** Ikon garis sederhana; tanpa pustaka ikon eksternal supaya halaman ringan. */
    function {{PREFIX}}_ikon($nama)
    {
        $path = array(
            'area' => '<path d="M12 21s7-5.3 7-11a7 7 0 1 0-14 0c0 5.7 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>',
            'satu' => '<path d="M4 7h16M4 12h16M4 17h10"/>',
            'rab'  => '<path d="M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
            'chat' => '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-5.2A8 8 0 1 1 21 12Z"/>',
            'cek'  => '<path d="m5 13 4 4L19 7"/>',
        );
        if (empty($path[$nama])) {
            return '';
        }
        return '<svg class="{{PREFIX}}-ikon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" '
            . 'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' . $path[$nama] . '</svg>';
    }
}

if (!function_exists('{{PREFIX}}_render_layanan')) {
    function {{PREFIX}}_render_layanan()
    {
        ob_start(); ?>
        <div class="{{PREFIX}}-kartu-grid {{PREFIX}}-kartu-grid--4">
            <?php foreach ({{PREFIX}}_data('layanan') as $l) : ?>
                <article class="{{PREFIX}}-kartu">
                    <?php {{PREFIX}}_figure('layanan-' . $l['slug'], $l['judul'], '{{PREFIX}}-kartu__media', 'medium_large'); ?>
                    <div class="{{PREFIX}}-kartu__isi">
                        <h3 class="{{PREFIX}}-kartu__judul"><?php echo esc_html($l['judul']); ?></h3>
                        <p class="{{PREFIX}}-kartu__teks"><?php echo esc_html($l['teks']); ?></p>
                        <ul class="{{PREFIX}}-daftar-cek">
                            <?php foreach ($l['rincian'] as $r) : ?>
                                <li><?php echo {{PREFIX}}_ikon('cek') . esc_html($r); ?></li>
                            <?php endforeach; ?>
                        </ul>
                        <a class="{{PREFIX}}-tautan" href="<?php echo esc_url({{PREFIX}}_wa_link('Halo, saya ingin konsultasi untuk ' . $l['judul'] . '.')); ?>"
                            target="_blank" rel="noopener nofollow">Tanya layanan ini →</a>
                    </div>
                </article>
            <?php endforeach; ?>
        </div>
        <?php return ob_get_clean();
    }
    add_shortcode('{{PREFIX}}_layanan', '{{PREFIX}}_render_layanan');
}

if (!function_exists('{{PREFIX}}_render_produk')) {
    function {{PREFIX}}_render_produk()
    {
        ob_start(); ?>
        <div class="{{PREFIX}}-kartu-grid {{PREFIX}}-kartu-grid--4">
            <?php foreach ({{PREFIX}}_data('produk') as $p) : ?>
                <article class="{{PREFIX}}-kartu {{PREFIX}}-kartu--rapat">
                    <?php {{PREFIX}}_figure($p['slug'], $p['judul'], '{{PREFIX}}-kartu__media {{PREFIX}}-kartu__media--tinggi', 'medium_large'); ?>
                    <div class="{{PREFIX}}-kartu__isi">
                        <h3 class="{{PREFIX}}-kartu__judul"><?php echo esc_html($p['judul']); ?></h3>
                        <p class="{{PREFIX}}-kartu__teks"><?php echo esc_html($p['teks']); ?></p>
                    </div>
                </article>
            <?php endforeach; ?>
        </div>
        <?php return ob_get_clean();
    }
    add_shortcode('{{PREFIX}}_produk', '{{PREFIX}}_render_produk');
}

if (!function_exists('{{PREFIX}}_render_galeri')) {
    function {{PREFIX}}_render_galeri()
    {
        ob_start(); ?>
        <div class="{{PREFIX}}-galeri">
            <?php foreach ({{PREFIX}}_data('galeri') as $g) : ?>
                <figure class="{{PREFIX}}-galeri__item">
                    <?php {{PREFIX}}_figure($g['slug'], $g['judul'], '{{PREFIX}}-galeri__media', 'large'); ?>
                    <figcaption><?php echo esc_html($g['judul']); ?></figcaption>
                </figure>
            <?php endforeach; ?>
        </div>
        <?php return ob_get_clean();
    }
    add_shortcode('{{PREFIX}}_galeri', '{{PREFIX}}_render_galeri');
}

if (!function_exists('{{PREFIX}}_render_alur')) {
    function {{PREFIX}}_render_alur()
    {
        ob_start(); ?>
        <ol class="{{PREFIX}}-alur">
            <?php foreach ({{PREFIX}}_data('alur') as $i => $a) : ?>
                <li class="{{PREFIX}}-alur__item">
                    <span class="{{PREFIX}}-alur__nomor"><?php echo esc_html(str_pad($i + 1, 2, '0', STR_PAD_LEFT)); ?></span>
                    <h3 class="{{PREFIX}}-alur__judul"><?php echo esc_html($a['judul']); ?></h3>
                    <p class="{{PREFIX}}-alur__teks"><?php echo esc_html($a['teks']); ?></p>
                </li>
            <?php endforeach; ?>
        </ol>
        <?php return ob_get_clean();
    }
    add_shortcode('{{PREFIX}}_alur', '{{PREFIX}}_render_alur');
}

if (!function_exists('{{PREFIX}}_render_pemesanan')) {
    function {{PREFIX}}_render_pemesanan()
    {
        return {{PREFIX}}_form_render();
    }
    add_shortcode('{{PREFIX}}_pemesanan', '{{PREFIX}}_render_pemesanan');
}

if (!function_exists('{{PREFIX}}_render_kontak')) {
    function {{PREFIX}}_render_kontak()
    {
        $alamat = {{PREFIX}}_data('alamat');
        ob_start(); ?>
        <div class="{{PREFIX}}-kontak">
            <ul class="{{PREFIX}}-kontak__daftar">
                <li><span>WhatsApp / Telepon</span><a href="<?php echo esc_url({{PREFIX}}_wa_link()); ?>" target="_blank" rel="noopener nofollow"><?php echo esc_html({{PREFIX}}_data('telp')); ?></a></li>
                <li><span>Email</span><a href="mailto:<?php echo esc_attr({{PREFIX}}_data('email')); ?>"><?php echo esc_html({{PREFIX}}_data('email')); ?></a></li>
                <li><span>Alamat</span><?php echo esc_html($alamat); ?></li>
                <li><span>Area Layanan</span><?php echo esc_html({{PREFIX}}_data('area')); ?></li>
            </ul>
            <div class="{{PREFIX}}-kontak__peta">
                <?php
                // Titik peta hasil scripts/velocity-map (alamat -> kota ->
                // provinsi -> Indonesia), disimpan installer di opsi
                // `velocity_map`. Memakai alamat mentah sebagai query bikin
                // peta tampil kosong kalau alamatnya tidak dikenali.
                $peta = get_option('velocity_map');
                $titik = is_array($peta) && !empty($peta['q']) ? $peta['q'] : $alamat;
                $zoom = is_array($peta) && !empty($peta['zoom']) ? (int) $peta['zoom'] : 15;
                ?>
                <iframe src="https://www.google.com/maps?q=<?php echo rawurlencode($titik); ?>&amp;z=<?php echo esc_attr($zoom); ?>&amp;output=embed"
                    width="100%" height="320" style="border:0" loading="lazy" referrerpolicy="no-referrer-when-downgrade"
                    title="Peta lokasi <?php echo esc_attr({{PREFIX}}_data('nama')); ?>"></iframe>
            </div>
        </div>
        <?php return ob_get_clean();
    }
    add_shortcode('{{PREFIX}}_kontak', '{{PREFIX}}_render_kontak');
}
