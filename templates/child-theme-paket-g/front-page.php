<?php

/**
 * Beranda desain custom.
 *
 * Semua teks berasal dari inc/theme-data.php (data klien & isi contoh) — tidak
 * ada kalimat khas satu bidang usaha di template, karena template ini dipakai
 * untuk semua situs Paket G. Seksi data perusahaan hanya tampil kalau datanya ada.
 */

defined('ABSPATH') || exit;

get_header();

$hero = {{PREFIX}}_image_url('hero', 'full');
$nama = {{PREFIX}}_data('nama');
?>

<main id="main" class="{{PREFIX}}-beranda" role="main">

    <section class="{{PREFIX}}-hero<?php echo $hero ? '' : ' {{PREFIX}}-hero--polos'; ?>"
        <?php if ($hero) : ?>style="background-image:linear-gradient(180deg,rgba(var(--{{PREFIX}}-primary-rgb),.82),rgba(var(--{{PREFIX}}-primary-rgb),.94)),url('<?php echo esc_url($hero); ?>')"<?php endif; ?>>
        <div class="{{PREFIX}}-wrap {{PREFIX}}-hero__isi">
            <?php $label = {{PREFIX}}_data('slogan') ?: {{PREFIX}}_data('area'); ?>
            <?php if ($label) : ?>
                <p class="{{PREFIX}}-hero__label"><?php echo esc_html($label); ?></p>
            <?php endif; ?>
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
                <h2><?php echo esc_html({{PREFIX}}_judul('layanan', 'Layanan Kami')); ?></h2>
                <?php if ({{PREFIX}}_judul('layanan_sub')) : ?>
                    <p class="{{PREFIX}}-judul-seksi__teks"><?php echo esc_html({{PREFIX}}_judul('layanan_sub')); ?></p>
                <?php endif; ?>
            </header>
            <?php echo {{PREFIX}}_render_layanan(); ?>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi {{PREFIX}}-seksi--gelap" id="keunggulan">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi {{PREFIX}}-judul-seksi--terang">
                <p class="{{PREFIX}}-judul-seksi__label">Kenapa Kami</p>
                <h2><?php echo esc_html({{PREFIX}}_judul('keunggulan', 'Kenapa Memilih Kami')); ?></h2>
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

    <?php $visimisi = {{PREFIX}}_render_visimisi(); ?>
    <?php if ($visimisi) : ?>
        <section class="{{PREFIX}}-seksi {{PREFIX}}-seksi--abu" id="visi-misi">
            <div class="{{PREFIX}}-wrap">
                <header class="{{PREFIX}}-judul-seksi">
                    <p class="{{PREFIX}}-judul-seksi__label">Visi &amp; Misi</p>
                    <h2><?php echo esc_html({{PREFIX}}_data('slogan') ?: $nama); ?></h2>
                </header>
                <?php echo $visimisi; ?>
            </div>
        </section>
    <?php endif; ?>

    <section class="{{PREFIX}}-seksi" id="tentang">
        <div class="{{PREFIX}}-wrap {{PREFIX}}-duo">
            <div class="{{PREFIX}}-duo__media">
                <?php {{PREFIX}}_figure('tentang', $nama, '{{PREFIX}}-figure--tinggi'); ?>
            </div>
            <div class="{{PREFIX}}-duo__teks">
                <p class="{{PREFIX}}-judul-seksi__label">Tentang Kami</p>
                <h2><?php echo esc_html({{PREFIX}}_judul('tentang', 'Tentang ' . $nama)); ?></h2>
                <?php
                // Isi halaman "Beranda" tetap ditampilkan di sini supaya teks yang
                // disunting lewat WordPress ikut tampil; judul H1-nya dibuang
                // karena beranda sudah punya judul utama di hero. Hanya pembuka
                // sebelum H2 pertama: bagian lanjutannya (layanan, keunggulan,
                // kontak) sudah punya seksi sendiri dan akan tampil dobel.
                $isi = get_post_field('post_content', get_the_ID());
                $isi = preg_replace('#<h1\b[^>]*>.*?</h1>#is', '', (string) $isi);
                $isi = preg_split('#<h2\b#i', $isi)[0];
                $isi = force_balance_tags($isi);
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
                <h2><?php echo esc_html({{PREFIX}}_judul('galeri', 'Galeri')); ?></h2>
                <?php if ({{PREFIX}}_judul('galeri_sub')) : ?>
                    <p class="{{PREFIX}}-judul-seksi__teks"><?php echo esc_html({{PREFIX}}_judul('galeri_sub')); ?></p>
                <?php endif; ?>
            </header>
            <?php echo {{PREFIX}}_render_galeri(); ?>
        </div>
    </section>

    <?php $customer = {{PREFIX}}_render_customer(false); ?>
    <?php if ($customer) : ?>
        <section class="{{PREFIX}}-seksi" id="customer">
            <div class="{{PREFIX}}-wrap">
                <header class="{{PREFIX}}-judul-seksi">
                    <p class="{{PREFIX}}-judul-seksi__label">Customer</p>
                    <h2>Dipercaya oleh</h2>
                </header>
                <?php echo $customer; ?>
            </div>
        </section>
    <?php endif; ?>

    <section class="{{PREFIX}}-seksi" id="produk">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi">
                <p class="{{PREFIX}}-judul-seksi__label">Produk</p>
                <h2><?php echo esc_html({{PREFIX}}_judul('produk', 'Produk Kami')); ?></h2>
            </header>
            <?php echo {{PREFIX}}_render_produk(); ?>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi {{PREFIX}}-seksi--abu" id="alur">
        <div class="{{PREFIX}}-wrap">
            <header class="{{PREFIX}}-judul-seksi">
                <p class="{{PREFIX}}-judul-seksi__label">Alur Kerja</p>
                <h2><?php echo esc_html({{PREFIX}}_judul('alur', 'Alur Kerja Kami')); ?></h2>
            </header>
            <?php echo {{PREFIX}}_render_alur(); ?>
        </div>
    </section>

    <section class="{{PREFIX}}-seksi {{PREFIX}}-seksi--gelap" id="pemesanan">
        <div class="{{PREFIX}}-wrap {{PREFIX}}-duo {{PREFIX}}-duo--form">
            <div class="{{PREFIX}}-duo__teks">
                <p class="{{PREFIX}}-judul-seksi__label">Pemesanan</p>
                <h2 class="{{PREFIX}}-terang"><?php echo esc_html({{PREFIX}}_judul('pemesanan', 'Ajukan Pemesanan')); ?></h2>
                <p class="{{PREFIX}}-terang-teks">
                    <?php echo esc_html({{PREFIX}}_judul('pemesanan_sub', 'Isi formulir ini dan permintaan Anda langsung masuk ke email kami.')); ?>
                    <?php if (trim((string) {{PREFIX}}_data('telp')) !== '') : ?>
                        Ingin lebih cepat? Hubungi WhatsApp <?php echo esc_html({{PREFIX}}_data('telp')); ?>.
                    <?php endif; ?>
                </p>
                <ul class="{{PREFIX}}-daftar-cek {{PREFIX}}-daftar-cek--terang">
                    <?php foreach ((array) {{PREFIX}}_data('hero_poin') as $poin) : ?>
                        <li><?php echo {{PREFIX}}_ikon('cek') . esc_html($poin); ?></li>
                    <?php endforeach; ?>
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
