<?php

/**
 * Beranda desain custom.
 *
 * Susunan seksi mengikuti pola situs referensi yang diminta klien, tetapi
 * urutan, isi, dan warnanya dibedakan sesuai catatan klien ("web dibuat agak
 * beda dari web contoh"). Isi teks diambil dari inc/theme-data.php.
 */

defined('ABSPATH') || exit;

get_header();

$hero = {{PREFIX}}_image_url('hero', 'full');
$nama = {{PREFIX}}_data('nama');
?>

<main id="main" class="{{PREFIX}}-beranda" role="main">

    <section class="{{PREFIX}}-hero<?php echo $hero ? '' : ' {{PREFIX}}-hero--polos'; ?>"
        <?php if ($hero) : ?>style="background-image:linear-gradient(180deg,rgba(20,33,61,.82),rgba(20,33,61,.94)),url('<?php echo esc_url($hero); ?>')"<?php endif; ?>>
        <div class="{{PREFIX}}-wrap {{PREFIX}}-hero__isi">
            <p class="{{PREFIX}}-hero__label"><?php echo esc_html({{PREFIX}}_data('area')); ?> · Renovasi · Interior</p>
            <h1 class="{{PREFIX}}-hero__judul"><?php echo esc_html({{PREFIX}}_data('hero_judul')); ?></h1>
            <p class="{{PREFIX}}-hero__teks"><?php echo esc_html({{PREFIX}}_data('hero_teks')); ?></p>
            <ul class="{{PREFIX}}-hero__poin">
                <?php foreach ({{PREFIX}}_data('hero_poin') as $poin) : ?>
                    <li><?php echo {{PREFIX}}_ikon('cek') . esc_html($poin); ?></li>
                <?php endforeach; ?>
            </ul>
            <p class="{{PREFIX}}-hero__aksi">
                <a class="{{PREFIX}}-btn {{PREFIX}}-btn--utama" href="#pemesanan">Ajukan Pemesanan</a>
                <a class="{{PREFIX}}-btn {{PREFIX}}-btn--terang" href="<?php echo esc_url({{PREFIX}}_wa_link()); ?>" target="_blank" rel="noopener nofollow">Konsultasi via WhatsApp</a>
            </p>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi" id="layanan">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi">
                <p class="{{PREFIX}}-judul-seksi__label">Layanan</p>
                <h2>Pekerjaan yang Kami Tangani</h2>
                <p class="{{PREFIX}}-judul-seksi__teks">Renovasi dan interior dikerjakan satu tim, dari perencanaan sampai serah terima.</p>
            </header>
            <?php echo {{PREFIX}}_render_layanan(); ?>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi {{PREFIX}}-seksi--gelap" id="keunggulan">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi {{PREFIX}}-judul-seksi--terang">
                <p class="{{PREFIX}}-judul-seksi__label">Kenapa Kami</p>
                <h2>Cara Kerja yang Jelas Sejak Awal</h2>
            </header>
            <div class="{{PREFIX}}-kartu-grid {{PREFIX}}-kartu-grid--4">
                <?php foreach ({{PREFIX}}_data('keunggulan') as $k) : ?>
                    <article class="{{PREFIX}}-poin">
                        <?php echo {{PREFIX}}_ikon($k['ikon']); ?>
                        <h3 class="{{PREFIX}}-poin__judul"><?php echo esc_html($k['judul']); ?></h3>
                        <p class="{{PREFIX}}-poin__teks"><?php echo esc_html($k['teks']); ?></p>
                    </article>
                <?php endforeach; ?>
            </div>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi" id="tentang">
        <div class="{{PREFIX}}-wrap {{PREFIX}}-duo">
            <div class="{{PREFIX}}-duo__media">
                <?php {{PREFIX}}_figure('tentang', 'Pekerjaan renovasi ' . $nama, '{{PREFIX}}-figure--tinggi'); ?>
            </div>
            <div class="{{PREFIX}}-duo__teks">
                <p class="{{PREFIX}}-judul-seksi__label">Tentang Kami</p>
                <h2>Satu Tim untuk Renovasi dan Interior Anda</h2>
                <?php
                // Isi halaman "Beranda" tetap ditampilkan di sini supaya teks yang
                // disunting lewat WordPress ikut tampil; judul H1-nya dibuang
                // karena beranda sudah punya judul utama di hero.
                $isi = get_post_field('post_content', get_the_ID());
                $isi = preg_replace('#<h1\b[^>]*>.*?</h1>#is', '', (string) $isi);
                echo wp_kses_post(apply_filters('the_content', $isi));
                ?>
                <?php
                // Kalau halaman profil dihapus/diganti slug, tombolnya ikut hilang
                // daripada menaut ke beranda sendiri.
                $profil = get_page_by_path('tentang-kami');
                if ($profil) : ?>
                    <p class="{{PREFIX}}-hero__aksi">
                        <a class="{{PREFIX}}-btn {{PREFIX}}-btn--utama" href="<?php echo esc_url(get_permalink($profil)); ?>">Profil Lengkap</a>
                    </p>
                <?php endif; ?>
            </div>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi {{PREFIX}}-seksi--abu" id="galeri">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi">
                <p class="{{PREFIX}}-judul-seksi__label">Galeri</p>
                <h2>Gaya Pengerjaan &amp; Hasil Akhir</h2>
                <p class="{{PREFIX}}-judul-seksi__teks">Gambaran ruang yang bisa dikerjakan. Foto proyek klien menyusul.</p>
            </header>
            <?php echo {{PREFIX}}_render_galeri(); ?>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi" id="produk">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi">
                <p class="{{PREFIX}}-judul-seksi__label">Produk</p>
                <h2>Pekerjaan Interior yang Sering Diminta</h2>
            </header>
            <?php echo {{PREFIX}}_render_produk(); ?>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi {{PREFIX}}-seksi--abu" id="alur">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi">
                <p class="{{PREFIX}}-judul-seksi__label">Alur Kerja</p>
                <h2>Lima Langkah dari Rencana ke Serah Terima</h2>
            </header>
            <?php echo {{PREFIX}}_render_alur(); ?>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi {{PREFIX}}-seksi--gelap" id="pemesanan">
        <div class="{{PREFIX}}-wrap {{PREFIX}}-duo {{PREFIX}}-duo--form">
            <div class="{{PREFIX}}-duo__teks">
                <p class="{{PREFIX}}-judul-seksi__label">Pemesanan</p>
                <h2 class="{{PREFIX}}-terang">Ceritakan Rencana Anda</h2>
                <p class="{{PREFIX}}-terang-teks">Isi formulir ini dan permintaan Anda langsung masuk ke email kami. Ingin lebih cepat? Hubungi WhatsApp <?php echo esc_html({{PREFIX}}_data('telp')); ?>.</p>
                <ul class="{{PREFIX}}-daftar-cek {{PREFIX}}-daftar-cek--terang">
                    <li><?php echo {{PREFIX}}_ikon('cek'); ?>Konsultasi awal tanpa biaya</li>
                    <li><?php echo {{PREFIX}}_ikon('cek'); ?>Survei lokasi untuk area <?php echo esc_html({{PREFIX}}_data('area')); ?></li>
                    <li><?php echo {{PREFIX}}_ikon('cek'); ?>Penawaran tertulis sebelum pengerjaan</li>
                </ul>
            </div>
            <div class="{{PREFIX}}-duo__media">
                <?php echo {{PREFIX}}_form_render(); ?>
            </div>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi" id="kontak">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi">
                <p class="{{PREFIX}}-judul-seksi__label">Kontak</p>
                <h2>Hubungi <?php echo esc_html($nama); ?></h2>
            </header>
            <?php echo {{PREFIX}}_render_kontak(); ?>
        </div>
    </section>

</main>

<?php
get_footer();
