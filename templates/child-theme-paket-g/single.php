<?php

/**
 * Halaman artikel.
 *
 * Portal berita (inc/berita.php): label rubrik, judul, tanggal, foto utama,
 * isi, bagikan, berita terkait, dan kolom samping. Situs non-berita tetap
 * memakai single.php tema induk.
 */

defined('ABSPATH') || exit;

if (!function_exists('{{PREFIX}}_jenis_berita') || !{{PREFIX}}_jenis_berita()) {
    require get_template_directory() . '/single.php';
    return;
}

get_header();
?>

<main id="main" class="{{PREFIX}}-wrap {{PREFIX}}-berita-tata {{PREFIX}}-berita-tunggal" role="main">
    <div class="{{PREFIX}}-berita-isi">
        <?php while (have_posts()) :
            the_post();
            list($kat, $kat_url) = {{PREFIX}}_berita_kategori(get_the_ID()); ?>
            <article <?php post_class('{{PREFIX}}-artikel'); ?>>
                <nav class="{{PREFIX}}-artikel__jejak" aria-label="Jejak halaman">
                    <a href="<?php echo esc_url(home_url('/')); ?>">Beranda</a>
                    <?php if ($kat) : ?> / <a href="<?php echo esc_url($kat_url); ?>"><?php echo esc_html($kat); ?></a><?php endif; ?>
                </nav>
                <?php if ($kat) : ?>
                    <a class="{{PREFIX}}-label" href="<?php echo esc_url($kat_url); ?>"><?php echo esc_html($kat); ?></a>
                <?php endif; ?>
                <h1 class="{{PREFIX}}-artikel__judul"><?php the_title(); ?></h1>
                <p class="{{PREFIX}}-artikel__meta">
                    Redaksi <?php echo esc_html({{PREFIX}}_data('nama')); ?> ·
                    <time datetime="<?php echo esc_attr(get_the_date('c')); ?>"><?php echo esc_html({{PREFIX}}_berita_tanggal(get_the_ID())); ?></time>
                </p>
                <?php if (has_post_thumbnail()) : ?>
                    <figure class="{{PREFIX}}-artikel__foto"><?php the_post_thumbnail('large', array('loading' => 'eager')); ?></figure>
                <?php endif; ?>
                <div class="{{PREFIX}}-artikel__isi entry-content"><?php the_content(); ?></div>
                <?php if (shortcode_exists('velocity-sharepost')) : ?>
                    <div class="{{PREFIX}}-artikel__bagikan"><?php echo do_shortcode('[velocity-sharepost]'); ?></div>
                <?php endif; ?>
            </article>
            <?php
            $kategori = wp_get_post_categories(get_the_ID());
            $terkait = $kategori ? {{PREFIX}}_berita_query(array(
                'posts_per_page' => 3,
                'category__in'   => $kategori,
                'post__not_in'   => array(get_the_ID()),
            )) : null;
            if ($terkait && $terkait->have_posts()) : ?>
                <section class="{{PREFIX}}-rubrik-blok {{PREFIX}}-terkait">
                    <header class="{{PREFIX}}-rubrik-bar"><h2>Berita Terkait</h2></header>
                    <div class="{{PREFIX}}-berita-grid">
                        <?php foreach ($terkait->posts as $p) {
                            echo {{PREFIX}}_berita_kartu($p->ID, 'kartu');
                        } ?>
                    </div>
                </section>
            <?php endif; ?>
        <?php endwhile; ?>
    </div>
    <aside class="{{PREFIX}}-berita-samping" aria-label="Kolom samping"><?php echo {{PREFIX}}_berita_sidebar(); ?></aside>
</main>

<?php
get_footer();
