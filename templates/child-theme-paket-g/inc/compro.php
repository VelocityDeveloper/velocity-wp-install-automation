<?php

/**
 * Tampilan bergaya company profile (compro) klien.
 *
 * Aktif bila inc/theme-data.php berisi 'seksi' hasil scripts/compro-klien.
 * Beranda disusun mengikuti URUTAN halaman company profile, dan tiap bagian
 * meniru pola halamannya: judul huruf besar di tengah bergaris bawah dengan tab
 * nomor di kanan, latar warna halaman compro, teks kiri + foto kanan, deret foto,
 * daftar customer dua kolom, ikon target, dan pita kaki hitam bersudut aksen.
 *
 * Bagian berisi data lengkap (struktur organisasi, informasi perusahaan,
 * legalitas) tampil di halaman Tentang Kami, bukan di beranda. Situs tanpa
 * company profile tetap memakai susunan bawaan front-page.php.
 *
 * Fungsi bantu sengaja tinggal di berkas ini, BUKAN di theme-data.php:
 * theme-data milik situs kadang dipertahankan saat template diperbarui, dan
 * helper yang tinggal di sana ikut tertinggal — jasakontraktorindo.com sempat
 * HTTP 500 karena itu.
 */

defined('ABSPATH') || exit;

if (!function_exists('{{PREFIX}}_gaya_compro')) {
    function {{PREFIX}}_gaya_compro()
    {
        return {{PREFIX}}_data('gaya') === 'compro' && (array) {{PREFIX}}_data('seksi');
    }
}

if (!function_exists('{{PREFIX}}_ada_wa')) {
    /** Tombol WhatsApp hanya tampil kalau nomor publiknya ada (tanpa nomor, tautannya jatuh ke mailto). */
    function {{PREFIX}}_ada_wa()
    {
        return preg_replace('/\D/', '', (string) {{PREFIX}}_data('wa')) !== '';
    }
}

if (!function_exists('{{PREFIX}}_tautan_hubungi')) {
    /** WhatsApp kalau ada; kalau tidak, halaman Hubungi Kami atau seksi kontak beranda. */
    function {{PREFIX}}_tautan_hubungi()
    {
        if ({{PREFIX}}_ada_wa()) {
            return {{PREFIX}}_wa_link();
        }
        $halaman = get_page_by_path('hubungi-kami');
        return $halaman ? get_permalink($halaman) : home_url('/#kontak');
    }
}

if (!function_exists('{{PREFIX}}_seksi_foto')) {
    /** ID foto satu bagian compro (opsi `{{PREFIX}}_seksi_foto`, diisi scripts/paket-g-foto). */
    function {{PREFIX}}_seksi_foto($kunci)
    {
        $peta = get_option('{{PREFIX}}_seksi_foto');
        if (!is_array($peta) || empty($peta[$kunci])) {
            return array();
        }
        return array_values(array_filter(array_map('intval', (array) $peta[$kunci])));
    }
}

if (!function_exists('{{PREFIX}}_potongan')) {
    /** Foto potongan produk berlatar transparan: ditampilkan utuh (contain), bukan dipotong. */
    function {{PREFIX}}_potongan($id)
    {
        $daftar = get_option('{{PREFIX}}_foto_potongan');
        return $id && is_array($daftar) && in_array((int) $id, array_map('intval', $daftar), true);
    }
}

if (!function_exists('{{PREFIX}}_figure_id')) {
    function {{PREFIX}}_figure_id($id, $alt = '', $class = '', $size = 'large')
    {
        if (!$id) {
            return '';
        }
        $img = wp_get_attachment_image($id, $size, false, array('alt' => $alt, 'loading' => 'lazy', 'decoding' => 'async'));
        if (!$img) {
            return '';
        }
        $class = trim('{{PREFIX}}-figure ' . $class . ({{PREFIX}}_potongan($id) ? ' {{PREFIX}}-figure--potongan' : ''));
        return sprintf('<div class="%s">%s</div>', esc_attr($class), $img);
    }
}

if (!function_exists('{{PREFIX}}_kop')) {
    /** Judul bagian gaya compro: huruf besar di tengah, garis bawah, tab nomor di kanan atas. */
    function {{PREFIX}}_kop($judul, $nomor = 0)
    {
        $tab = $nomor ? sprintf('<span class="{{PREFIX}}-kop__tab" aria-hidden="true">%02d</span>', $nomor) : '';
        return sprintf('%s<header class="{{PREFIX}}-kop"><h2 class="{{PREFIX}}-kop__judul">%s</h2></header>',
            $tab, esc_html($judul));
    }
}

if (!function_exists('{{PREFIX}}_foto_grid')) {
    /** Deret foto seperti halaman foto compro; $batas > 0 menampilkan sebagian + tautan ke Galeri. */
    function {{PREFIX}}_foto_grid($ids, $judul = '', $batas = 0)
    {
        $ids = array_values((array) $ids);
        if (!$ids) {
            return '';
        }
        $tampil = $batas ? array_slice($ids, 0, $batas) : $ids;
        // Bagian yang mayoritas fotonya tegak (gambar teknik) memakai kotak tegak
        // supaya gambarnya tidak terpotong habis.
        $tegak = 0;
        foreach ($tampil as $id) {
            $meta = wp_get_attachment_metadata($id);
            if (!empty($meta['width']) && !empty($meta['height']) && $meta['height'] > $meta['width'] * 1.15) {
                $tegak++;
            }
        }
        $kelas = $tegak * 2 > count($tampil) ? ' {{PREFIX}}-foto-grid--tegak' : '';
        ob_start(); ?>
        <div class="{{PREFIX}}-foto-grid<?php echo esc_attr($kelas); ?>">
            <?php foreach ($tampil as $i => $id) : ?>
                <figure class="{{PREFIX}}-foto-grid__item">
                    <?php echo {{PREFIX}}_figure_id($id, $judul ? $judul . ' ' . ($i + 1) : '', '', 'medium_large'); ?>
                </figure>
            <?php endforeach; ?>
        </div>
        <?php $galeri = get_page_by_path('galeri'); ?>
        <?php if ($batas && count($ids) > $batas && $galeri) : ?>
            <p class="{{PREFIX}}-foto-grid__lagi">
                <a class="{{PREFIX}}-btn {{PREFIX}}-btn--garis" href="<?php echo esc_url(get_permalink($galeri)); ?>">Lihat semua <?php echo (int) count($ids); ?> foto</a>
            </p>
        <?php endif;
        return ob_get_clean();
    }
}

if (!function_exists('{{PREFIX}}_ikon_target')) {
    function {{PREFIX}}_ikon_target($teks)
    {
        $t = strtolower((string) $teks);
        foreach (array('mitra' => array('mitra', 'kerja sama', 'kerjasama'), 'grafik' => array('pasar', 'ekspansi', 'tumbuh', 'omzet'),
            'bintang' => array('puas', 'pelanggan', 'kualitas')) as $ikon => $kata) {
            foreach ($kata as $k) {
                if (strpos($t, $k) !== false) {
                    return $ikon;
                }
            }
        }
        return 'cek';
    }
}

if (!function_exists('{{PREFIX}}_compro_sampul')) {
    /** Hero meniru sampul compro: nama + subjudul, judul besar huruf kapital, slogan, foto sampul. */
    function {{PREFIX}}_compro_sampul()
    {
        $nama = {{PREFIX}}_data('nama');
        $hero = {{PREFIX}}_image_id('hero');
        $profil = get_page_by_path('tentang-kami');
        ob_start(); ?>
        <section class="{{PREFIX}}-sampul" id="beranda">
            <div class="{{PREFIX}}-wrap {{PREFIX}}-sampul__grid<?php echo $hero ? '' : ' {{PREFIX}}-sampul__grid--tunggal'; ?>">
                <div class="{{PREFIX}}-sampul__teks">
                    <p class="{{PREFIX}}-sampul__nama"><?php echo esc_html($nama); ?></p>
                    <?php if ({{PREFIX}}_data('subjudul')) : ?>
                        <p class="{{PREFIX}}-sampul__sub"><?php echo esc_html({{PREFIX}}_data('subjudul')); ?></p>
                    <?php endif; ?>
                    <h1 class="{{PREFIX}}-sampul__judul"><?php echo esc_html({{PREFIX}}_data('hero_judul') ?: $nama); ?></h1>
                    <?php if ({{PREFIX}}_data('slogan')) : ?>
                        <p class="{{PREFIX}}-sampul__slogan"><?php echo esc_html({{PREFIX}}_data('slogan')); ?></p>
                    <?php endif; ?>
                    <p class="{{PREFIX}}-sampul__isi"><?php echo esc_html({{PREFIX}}_data('hero_teks')); ?></p>
                    <p class="{{PREFIX}}-hero__aksi">
                        <a class="{{PREFIX}}-btn {{PREFIX}}-btn--utama" href="#pemesanan">Ajukan Pemesanan</a>
                        <?php if ({{PREFIX}}_ada_wa()) : ?>
                            <a class="{{PREFIX}}-btn {{PREFIX}}-btn--garis" href="<?php echo esc_url({{PREFIX}}_wa_link()); ?>" target="_blank" rel="noopener nofollow">Konsultasi via WhatsApp</a>
                        <?php elseif ($profil) : ?>
                            <a class="{{PREFIX}}-btn {{PREFIX}}-btn--garis" href="<?php echo esc_url(get_permalink($profil)); ?>">Profil Perusahaan</a>
                        <?php endif; ?>
                    </p>
                </div>
                <?php if ($hero) : ?>
                    <div class="{{PREFIX}}-sampul__media"><?php echo {{PREFIX}}_figure_id($hero, $nama, '', 'large'); ?></div>
                <?php endif; ?>
            </div>
        </section>
        <?php return ob_get_clean();
    }
}

if (!function_exists('{{PREFIX}}_compro_prakata')) {
    /** Sambutan perusahaan disalin dari halaman prakata compro, lengkap dengan penanda tangan. */
    function {{PREFIX}}_compro_prakata()
    {
        $p = (array) {{PREFIX}}_data('prakata');
        $paragraf = isset($p['paragraf']) ? array_filter((array) $p['paragraf']) : array();
        if (!$paragraf) {
            return '';
        }
        ob_start(); ?>
        <div class="{{PREFIX}}-prakata">
            <?php foreach ($paragraf as $teks) : ?>
                <p><?php echo esc_html($teks); ?></p>
            <?php endforeach; ?>
            <div class="{{PREFIX}}-prakata__tanda">
                <?php if (!empty($p['salam'])) : ?><p><?php echo esc_html($p['salam']); ?></p><?php endif; ?>
                <p class="{{PREFIX}}-prakata__perusahaan"><?php echo esc_html(!empty($p['perusahaan']) ? $p['perusahaan'] : {{PREFIX}}_data('nama')); ?></p>
                <?php if (!empty($p['nama'])) : ?><p class="{{PREFIX}}-prakata__nama"><?php echo esc_html($p['nama']); ?></p><?php endif; ?>
                <?php if (!empty($p['jabatan'])) : ?><p class="{{PREFIX}}-prakata__jabatan"><?php echo esc_html($p['jabatan']); ?></p><?php endif; ?>
            </div>
        </div>
        <?php return ob_get_clean();
    }
}

if (!function_exists('{{PREFIX}}_compro_visimisi')) {
    /** Visi, misi, dan motto: teks kiri + foto kanan seperti halaman compro. */
    function {{PREFIX}}_compro_visimisi()
    {
        $visi = trim((string) {{PREFIX}}_data('visi'));
        $misi = array_filter((array) {{PREFIX}}_data('misi'));
        $moto = trim((string) {{PREFIX}}_data('moto'));
        if ($visi === '' && !$misi && $moto === '') {
            return '';
        }
        $foto = {{PREFIX}}_seksi_foto('visimisi');
        ob_start(); ?>
        <div class="{{PREFIX}}-vm<?php echo $foto ? '' : ' {{PREFIX}}-vm--tunggal'; ?>">
            <div class="{{PREFIX}}-vm__teks">
                <?php if ($visi !== '') : ?>
                    <div class="{{PREFIX}}-vm__blok">
                        <h3 class="{{PREFIX}}-vm__label">Visi</h3>
                        <p><?php echo esc_html($visi); ?></p>
                    </div>
                <?php endif; ?>
                <?php if ($misi) : ?>
                    <div class="{{PREFIX}}-vm__blok">
                        <h3 class="{{PREFIX}}-vm__label">Misi</h3>
                        <?php if (count($misi) === 1) : ?>
                            <p><?php echo esc_html(reset($misi)); ?></p>
                        <?php else : ?>
                            <ul class="{{PREFIX}}-daftar-cek">
                                <?php foreach ($misi as $m) : ?>
                                    <li><?php echo {{PREFIX}}_ikon('cek') . esc_html($m); ?></li>
                                <?php endforeach; ?>
                            </ul>
                        <?php endif; ?>
                    </div>
                <?php endif; ?>
                <?php if ($moto !== '') : ?>
                    <p class="{{PREFIX}}-vm__moto"><span class="{{PREFIX}}-vm__label">Motto</span> <?php echo esc_html($moto); ?></p>
                <?php endif; ?>
            </div>
            <?php if ($foto) : ?>
                <div class="{{PREFIX}}-vm__media"><?php echo {{PREFIX}}_figure_id($foto[0], 'Visi dan misi ' . {{PREFIX}}_data('nama')); ?></div>
            <?php endif; ?>
        </div>
        <?php return ob_get_clean();
    }
}

if (!function_exists('{{PREFIX}}_compro_target')) {
    /** Target pencapaian sebagai ikon dalam kotak, dengan foto pita di bawahnya bila ada. */
    function {{PREFIX}}_compro_target()
    {
        $target = array_filter((array) {{PREFIX}}_data('target'));
        $banner = {{PREFIX}}_seksi_foto('target');
        if (!$target && !$banner) {
            return '';
        }
        ob_start(); ?>
        <?php if ($target) : ?>
            <div class="{{PREFIX}}-target">
                <?php foreach ($target as $t) : ?>
                    <div class="{{PREFIX}}-target__item">
                        <span class="{{PREFIX}}-target__ikon"><?php echo {{PREFIX}}_ikon({{PREFIX}}_ikon_target($t)); ?></span>
                        <p><?php echo esc_html($t); ?></p>
                    </div>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>
        <?php if ($banner) : ?>
            <div class="{{PREFIX}}-target__banner"><?php echo wp_get_attachment_image($banner[0], 'full', false, array('alt' => '', 'loading' => 'lazy')); ?></div>
        <?php endif;
        return ob_get_clean();
    }
}

if (!function_exists('{{PREFIX}}_compro_bagian')) {
    function {{PREFIX}}_compro_bagian($id, $judul, $isi, $nomor, $latar)
    {
        return sprintf('<section class="{{PREFIX}}-seksi%s" id="%s"><div class="{{PREFIX}}-wrap {{PREFIX}}-wrap--kop">%s%s</div></section>',
            $latar ? ' {{PREFIX}}-seksi--latar' : '', esc_attr($id), {{PREFIX}}_kop($judul, $nomor), $isi);
    }
}

if (!function_exists('{{PREFIX}}_beranda_compro')) {
    /** Beranda berurutan sesuai halaman company profile, lalu Pemesanan & Kontak. */
    function {{PREFIX}}_beranda_compro()
    {
        $nomor = 0;
        echo '<main id="main" class="{{PREFIX}}-beranda {{PREFIX}}-beranda--compro" role="main">';
        foreach ((array) {{PREFIX}}_data('seksi') as $s) {
            $jenis = isset($s['jenis']) ? (string) $s['jenis'] : '';
            $judul = !empty($s['judul']) ? (string) $s['judul'] : '';
            $kunci = !empty($s['kunci']) ? (string) $s['kunci'] : $jenis;
            if ($jenis === 'sampul') {
                echo {{PREFIX}}_compro_sampul();
                continue;
            }
            switch ($jenis) {
                case 'prakata':
                    $isi = {{PREFIX}}_compro_prakata();
                    break;
                case 'visimisi':
                    $isi = {{PREFIX}}_compro_visimisi();
                    break;
                case 'layanan':
                    $isi = (array) {{PREFIX}}_data('layanan') ? {{PREFIX}}_render_layanan() : '';
                    break;
                case 'foto':
                    $isi = {{PREFIX}}_foto_grid({{PREFIX}}_seksi_foto($kunci), $judul, 8);
                    break;
                case 'customer':
                    $isi = {{PREFIX}}_render_customer(false);
                    break;
                case 'target':
                    $isi = {{PREFIX}}_compro_target();
                    break;
                default:
                    // Struktur, informasi perusahaan, legalitas → halaman Tentang Kami.
                    $isi = '';
            }
            if (trim((string) $isi) === '') {
                continue;
            }
            $nomor++;
            echo {{PREFIX}}_compro_bagian($kunci, $judul ?: ucfirst($jenis), $isi, $nomor, $nomor % 2 === 1);
        }

        $nomor++;
        ob_start(); ?>
        <div class="{{PREFIX}}-duo {{PREFIX}}-duo--form">
            <div class="{{PREFIX}}-duo__teks">
                <h3 class="{{PREFIX}}-pemesanan__judul"><?php echo esc_html({{PREFIX}}_judul('pemesanan', 'Ajukan Pemesanan')); ?></h3>
                <p><?php echo esc_html({{PREFIX}}_judul('pemesanan_sub', 'Isi formulir ini dan permintaan Anda langsung masuk ke email kami.')); ?></p>
                <ul class="{{PREFIX}}-daftar-cek">
                    <?php foreach ((array) {{PREFIX}}_data('hero_poin') as $poin) : ?>
                        <li><?php echo {{PREFIX}}_ikon('cek') . esc_html($poin); ?></li>
                    <?php endforeach; ?>
                </ul>
            </div>
            <div class="{{PREFIX}}-duo__media"><?php echo {{PREFIX}}_form_render(); ?></div>
        </div>
        <?php
        echo {{PREFIX}}_compro_bagian('pemesanan', 'Pemesanan', ob_get_clean(), $nomor, $nomor % 2 === 1);
        $nomor++;
        echo {{PREFIX}}_compro_bagian('kontak', 'Kontak Kami', {{PREFIX}}_render_kontak(), $nomor, $nomor % 2 === 1);
        echo '</main>';
    }
}
