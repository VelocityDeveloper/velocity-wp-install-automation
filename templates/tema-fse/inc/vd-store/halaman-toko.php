<?php
/**
 * Halaman toko VD Store (Katalog, Keranjang, Checkout, Profil Saya, Cek Ongkir, Terima Kasih,
 * Tracking Order) lewat jalur klasik header.php/footer.php.
 *
 * Template blok menjalankan wptexturize lagi atas SELURUH halaman sesudah shortcode dirender;
 * atribut Alpine VD Store (x-if="cart.length > 0", "a && b") rusak jadi kutip miring & entitas,
 * sehingga isi keranjang tidak pernah tampil (yukpergimancing.com 2026-09-17). Di jalur klasik,
 * the_content menjalankan wptexturize SEBELUM do_shortcode, jadi keluaran shortcode utuh.
 */

defined('ABSPATH') || exit;

$GLOBALS['velocity_fse_judul_pita'] = single_post_title('', false);
get_header();
while (have_posts()) {
    the_post();
    echo '<div class="vf-halaman-toko">';
    the_content();
    echo '</div>';
}
get_footer();
