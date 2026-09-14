<?php

/**
 * Arsip & indeks berita (rubrik, tag, halaman Berita).
 *
 * Portal berita memakai daftar berita + kolom samping. Situs non-berita tetap
 * memakai archive.php tema induk (home.php memakai index.php induk).
 */

defined('ABSPATH') || exit;

if (!function_exists('{{PREFIX}}_jenis_berita') || !{{PREFIX}}_jenis_berita()) {
    require get_template_directory() . (is_home() ? '/index.php' : '/archive.php');
    return;
}

get_header();

if (is_home()) {
    $arsip = (int) get_option('page_for_posts');
    $judul = $arsip ? get_the_title($arsip) : 'Indeks Berita';
} elseif (is_category() || is_tag()) {
    $judul = single_term_title('', false);
} else {
    $judul = wp_strip_all_tags(get_the_archive_title());
}
$deskripsi = is_category() ? wp_strip_all_tags(category_description()) : '';
?>

<main id="main" class="{{PREFIX}}-wrap {{PREFIX}}-berita-tata {{PREFIX}}-berita-arsip" role="main">
    <div class="{{PREFIX}}-berita-isi">
        <header class="{{PREFIX}}-rubrik-bar {{PREFIX}}-rubrik-bar--besar"><h1><?php echo esc_html($judul); ?></h1></header>
        <?php if ($deskripsi !== '') : ?>
            <p class="{{PREFIX}}-berita-arsip__teks"><?php echo esc_html($deskripsi); ?></p>
        <?php endif; ?>
        <?php if (have_posts()) : ?>
            <div class="{{PREFIX}}-berita-daftar">
                <?php while (have_posts()) {
                    the_post();
                    echo {{PREFIX}}_berita_kartu(get_the_ID(), 'lebar');
                } ?>
            </div>
            <?php the_posts_pagination(array('mid_size' => 1, 'prev_text' => '← Sebelumnya', 'next_text' => 'Berikutnya →')); ?>
        <?php else : ?>
            <p>Belum ada berita di sini.</p>
        <?php endif; ?>
    </div>
    <aside class="{{PREFIX}}-berita-samping" aria-label="Kolom samping"><?php echo {{PREFIX}}_berita_sidebar(); ?></aside>
</main>

<?php
get_footer();
