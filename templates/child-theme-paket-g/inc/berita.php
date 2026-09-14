<?php

/**
 * Tampilan portal berita (Paket Portal Berita Custom).
 *
 * Keputusan user 2026-09-14: portal berita custom dikerjakan dengan alur yang
 * sama seperti Paket G (desain custom per project), tetapi hasilnya portal
 * berita — bukan web company profile. Aktif bila theme-data berisi
 * 'jenis' => 'berita'. Rubrik diambil dari susunan menu FORM ISIAN klien dan
 * menjadi kategori WordPress dengan slug yang sama (dibuat scripts/paket-g-setup).
 *
 * Fungsi bantu tinggal di berkas template ini, bukan di theme-data.php (lihat
 * catatan di inc/compro.php).
 */

defined('ABSPATH') || exit;

if (!function_exists('{{PREFIX}}_jenis_berita')) {
    function {{PREFIX}}_jenis_berita()
    {
        return {{PREFIX}}_data('jenis') === 'berita';
    }
}

if (!function_exists('{{PREFIX}}_hari_ini')) {
    function {{PREFIX}}_hari_ini()
    {
        return {{PREFIX}}_tanggal_id(current_time('timestamp'), true);
    }
}

if (!function_exists('{{PREFIX}}_tanggal_id')) {
    /** Tanggal berbahasa Indonesia; situs terpasang dengan bahasa Inggris menulis "Monday". */
    function {{PREFIX}}_tanggal_id($waktu, $dengan_hari = false)
    {
        $hari = array('Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu');
        $bulan = array(1 => 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli', 'Agustus',
            'September', 'Oktober', 'November', 'Desember');
        $teks = gmdate('j', $waktu) . ' ' . $bulan[(int) gmdate('n', $waktu)] . ' ' . gmdate('Y', $waktu);
        return $dengan_hari ? $hari[(int) gmdate('w', $waktu)] . ', ' . $teks : $teks;
    }
}

if (!function_exists('{{PREFIX}}_rubrik')) {
    /** Rubrik dari theme-data beserta kategori WordPress-nya (dicocokkan lewat slug, lalu nama). */
    function {{PREFIX}}_rubrik()
    {
        static $hasil = null;
        if ($hasil !== null) {
            return $hasil;
        }
        $hasil = array();
        foreach ((array) {{PREFIX}}_data('rubrik') as $r) {
            if (empty($r['judul'])) {
                continue;
            }
            $term = !empty($r['slug']) ? get_term_by('slug', $r['slug'], 'category') : false;
            if (!$term) {
                $term = get_term_by('name', $r['judul'], 'category');
            }
            $hasil[] = array(
                'judul' => (string) $r['judul'],
                'teks'  => isset($r['teks']) ? (string) $r['teks'] : '',
                'term'  => $term ? $term : null,
                'url'   => $term ? get_category_link($term->term_id) : '',
            );
        }
        return $hasil;
    }
}

if (!function_exists('{{PREFIX}}_berita_query')) {
    function {{PREFIX}}_berita_query($args = array())
    {
        return new WP_Query(array_merge(array(
            'post_type'           => 'post',
            'post_status'         => 'publish',
            'ignore_sticky_posts' => true,
            'no_found_rows'       => true,
            'posts_per_page'      => 5,
        ), $args));
    }
}

if (!function_exists('{{PREFIX}}_berita_kategori')) {
    /** array(nama, url) kategori pertama artikel. */
    function {{PREFIX}}_berita_kategori($post_id)
    {
        $kategori = get_the_category($post_id);
        if (!$kategori) {
            return array('', '');
        }
        return array($kategori[0]->name, get_category_link($kategori[0]->term_id));
    }
}

if (!function_exists('{{PREFIX}}_berita_tanggal')) {
    function {{PREFIX}}_berita_tanggal($post_id)
    {
        // get_post_time(..., false) = waktu lokal situs dalam detik; dibaca gmdate apa adanya.
        return {{PREFIX}}_tanggal_id((int) get_post_time('U', false, $post_id));
    }
}

if (!function_exists('{{PREFIX}}_berita_kartu')) {
    /**
     * Satu berita. $gaya: utama (foto besar, judul di atas foto), kartu (foto di
     * atas), daftar (foto kecil di kiri), lebar (daftar arsip dengan ringkasan).
     */
    function {{PREFIX}}_berita_kartu($post_id, $gaya = 'kartu')
    {
        list($kat, $kat_url) = {{PREFIX}}_berita_kategori($post_id);
        $url = get_permalink($post_id);
        $foto = has_post_thumbnail($post_id);
        $ukuran = in_array($gaya, array('utama', 'lebar'), true) ? 'large' : 'medium_large';
        ob_start(); ?>
        <article class="{{PREFIX}}-berita {{PREFIX}}-berita--<?php echo esc_attr($gaya); ?>">
            <a class="{{PREFIX}}-berita__foto<?php echo $foto ? '' : ' {{PREFIX}}-berita__foto--kosong'; ?>" href="<?php echo esc_url($url); ?>" tabindex="-1" aria-hidden="true">
                <?php if ($foto) : ?>
                    <?php echo get_the_post_thumbnail($post_id, $ukuran, array('loading' => $gaya === 'utama' ? 'eager' : 'lazy', 'alt' => '')); ?>
                <?php else : ?>
                    <span><?php echo esc_html($kat ? $kat : {{PREFIX}}_data('nama')); ?></span>
                <?php endif; ?>
            </a>
            <div class="{{PREFIX}}-berita__teks">
                <?php if ($kat && $gaya !== 'daftar') : ?>
                    <a class="{{PREFIX}}-label" href="<?php echo esc_url($kat_url); ?>"><?php echo esc_html($kat); ?></a>
                <?php endif; ?>
                <h3 class="{{PREFIX}}-berita__judul"><a href="<?php echo esc_url($url); ?>"><?php echo esc_html(get_the_title($post_id)); ?></a></h3>
                <p class="{{PREFIX}}-berita__meta"><time datetime="<?php echo esc_attr(get_post_time('c', false, $post_id)); ?>"><?php echo esc_html({{PREFIX}}_berita_tanggal($post_id)); ?></time></p>
                <?php if (in_array($gaya, array('utama', 'lebar'), true)) : ?>
                    <p class="{{PREFIX}}-berita__ringkas"><?php echo esc_html(wp_trim_words(get_the_excerpt($post_id), 26)); ?></p>
                <?php endif; ?>
            </div>
        </article>
        <?php return ob_get_clean();
    }
}

if (!function_exists('{{PREFIX}}_berita_sidebar')) {
    /** Kolom samping: terpopuler, daftar rubrik, dan sekilas tentang media. */
    function {{PREFIX}}_berita_sidebar()
    {
        $populer = {{PREFIX}}_berita_query(array('posts_per_page' => 5, 'orderby' => array('comment_count' => 'DESC', 'date' => 'DESC')));
        $rubrik = array_filter({{PREFIX}}_rubrik(), function ($r) {
            return !empty($r['term']);
        });
        $redaksi = get_page_by_path('redaksi');
        ob_start(); ?>
        <?php if ($populer->have_posts()) : ?>
            <section class="{{PREFIX}}-kotak">
                <header class="{{PREFIX}}-rubrik-bar"><h2>Terpopuler</h2></header>
                <ol class="{{PREFIX}}-populer">
                    <?php foreach ($populer->posts as $p) : ?>
                        <li><a href="<?php echo esc_url(get_permalink($p)); ?>"><?php echo esc_html(get_the_title($p)); ?></a></li>
                    <?php endforeach; ?>
                </ol>
            </section>
        <?php endif; ?>
        <?php if ($rubrik) : ?>
            <section class="{{PREFIX}}-kotak">
                <header class="{{PREFIX}}-rubrik-bar"><h2>Rubrik</h2></header>
                <ul class="{{PREFIX}}-daftar-rubrik">
                    <?php foreach ($rubrik as $r) : ?>
                        <li><a href="<?php echo esc_url($r['url']); ?>"><span><?php echo esc_html($r['judul']); ?></span><span><?php echo (int) $r['term']->count; ?></span></a></li>
                    <?php endforeach; ?>
                </ul>
            </section>
        <?php endif; ?>
        <?php if ({{PREFIX}}_data('tentang')) : ?>
            <section class="{{PREFIX}}-kotak">
                <header class="{{PREFIX}}-rubrik-bar"><h2>Tentang Kami</h2></header>
                <p class="{{PREFIX}}-kotak__teks"><?php echo esc_html(wp_trim_words({{PREFIX}}_data('tentang'), 40)); ?></p>
                <?php if ($redaksi) : ?>
                    <a class="{{PREFIX}}-tautan" href="<?php echo esc_url(get_permalink($redaksi)); ?>">Redaksi →</a>
                <?php endif; ?>
            </section>
        <?php endif;
        return ob_get_clean();
    }
}

if (!function_exists('{{PREFIX}}_beranda_berita')) {
    /** Beranda portal: berita utama + 4 terbaru, berita terbaru, lalu satu blok per rubrik. */
    function {{PREFIX}}_beranda_berita()
    {
        $terbaru = {{PREFIX}}_berita_query(array('posts_per_page' => 11));
        $ids = wp_list_pluck($terbaru->posts, 'ID');
        echo '<main id="main" class="{{PREFIX}}-beranda {{PREFIX}}-beranda--berita" role="main">';
        echo '<h1 class="{{PREFIX}}-layar-baca">' . esc_html({{PREFIX}}_data('nama')) . '</h1>';
        if (!$ids) {
            echo '<div class="{{PREFIX}}-wrap {{PREFIX}}-berita-tata"><p>Belum ada berita yang terbit.</p></div></main>';
            return;
        }
        $arsip = (int) get_option('page_for_posts');
        ?>
        <section class="{{PREFIX}}-berita-utama">
            <div class="{{PREFIX}}-wrap {{PREFIX}}-berita-utama__grid">
                <?php echo {{PREFIX}}_berita_kartu($ids[0], 'utama'); ?>
                <div class="{{PREFIX}}-berita-tumpuk">
                    <?php foreach (array_slice($ids, 1, 4) as $id) {
                        echo {{PREFIX}}_berita_kartu($id, 'daftar');
                    } ?>
                </div>
            </div>
        </section>
        <div class="{{PREFIX}}-wrap {{PREFIX}}-berita-tata">
            <div class="{{PREFIX}}-berita-isi">
                <?php $lanjut = array_slice($ids, 5, 6); ?>
                <?php if ($lanjut) : ?>
                    <section class="{{PREFIX}}-rubrik-blok">
                        <header class="{{PREFIX}}-rubrik-bar">
                            <h2><?php echo esc_html({{PREFIX}}_judul('terbaru', 'Berita Terbaru')); ?></h2>
                            <?php if ($arsip) : ?><a href="<?php echo esc_url(get_permalink($arsip)); ?>">Indeks berita →</a><?php endif; ?>
                        </header>
                        <div class="{{PREFIX}}-berita-grid">
                            <?php foreach ($lanjut as $id) {
                                echo {{PREFIX}}_berita_kartu($id, 'kartu');
                            } ?>
                        </div>
                    </section>
                <?php endif; ?>
                <?php foreach ({{PREFIX}}_rubrik() as $r) :
                    if (empty($r['term'])) {
                        continue;
                    }
                    $q = {{PREFIX}}_berita_query(array('posts_per_page' => 4, 'cat' => (int) $r['term']->term_id));
                    $p = wp_list_pluck($q->posts, 'ID');
                    if (!$p) {
                        continue;
                    } ?>
                    <section class="{{PREFIX}}-rubrik-blok" id="rubrik-<?php echo esc_attr($r['term']->slug); ?>">
                        <header class="{{PREFIX}}-rubrik-bar">
                            <h2><?php echo esc_html($r['judul']); ?></h2>
                            <a href="<?php echo esc_url($r['url']); ?>">Lihat semua →</a>
                        </header>
                        <div class="{{PREFIX}}-rubrik-blok__grid">
                            <?php echo {{PREFIX}}_berita_kartu($p[0], 'kartu'); ?>
                            <div class="{{PREFIX}}-berita-tumpuk">
                                <?php foreach (array_slice($p, 1) as $id) {
                                    echo {{PREFIX}}_berita_kartu($id, 'daftar');
                                } ?>
                            </div>
                        </div>
                    </section>
                <?php endforeach; ?>
            </div>
            <aside class="{{PREFIX}}-berita-samping" aria-label="Kolom samping"><?php echo {{PREFIX}}_berita_sidebar(); ?></aside>
        </div>
        <?php
        echo '</main>';
    }
}

if (!function_exists('{{PREFIX}}_render_redaksi')) {
    /**
     * Halaman Redaksi: identitas media, pedoman redaksi, dan kontak publik.
     * Nama awak redaksi TIDAK dikarang — dilengkapi PM bila klien mengirimnya.
     */
    function {{PREFIX}}_render_redaksi()
    {
        $email = trim((string) {{PREFIX}}_data('email_publik'));
        $pedoman = array_filter((array) {{PREFIX}}_data('redaksi'));
        $kontak = get_page_by_path('hubungi-kami');
        ob_start(); ?>
        <div class="{{PREFIX}}-redaksi">
            <p class="{{PREFIX}}-redaksi__nama"><?php echo esc_html({{PREFIX}}_data('nama')); ?></p>
            <?php if ({{PREFIX}}_data('slogan')) : ?>
                <p class="{{PREFIX}}-redaksi__slogan"><?php echo esc_html({{PREFIX}}_data('slogan')); ?></p>
            <?php endif; ?>
            <?php if ({{PREFIX}}_data('tentang')) : ?>
                <p><?php echo esc_html({{PREFIX}}_data('tentang')); ?></p>
            <?php endif; ?>
            <?php if ($pedoman) : ?>
                <h2>Pedoman Redaksi</h2>
                <?php foreach ($pedoman as $paragraf) : ?>
                    <p><?php echo esc_html($paragraf); ?></p>
                <?php endforeach; ?>
            <?php endif; ?>
            <h2>Kontak Redaksi</h2>
            <ul class="{{PREFIX}}-redaksi__kontak">
                <?php if ($email !== '') : ?>
                    <li>Email: <a href="mailto:<?php echo esc_attr($email); ?>"><?php echo esc_html($email); ?></a></li>
                <?php endif; ?>
                <?php if ({{PREFIX}}_data('area')) : ?>
                    <li>Wilayah liputan: <?php echo esc_html({{PREFIX}}_data('area')); ?></li>
                <?php endif; ?>
                <?php if ($kontak) : ?>
                    <li><a href="<?php echo esc_url(get_permalink($kontak)); ?>">Kirim pesan ke redaksi</a></li>
                <?php endif; ?>
            </ul>
        </div>
        <?php return ob_get_clean();
    }
    add_shortcode('{{PREFIX}}_redaksi', '{{PREFIX}}_render_redaksi');
}
