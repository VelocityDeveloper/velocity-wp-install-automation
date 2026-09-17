<?php

/**
 * Kontak publik. Hanya kontak "untuk di web" (Data Situs) yang tampil — WA &
 * email biodata pemilik di FORM ISIAN tidak pernah masuk ke opsi ini.
 */

defined('ABSPATH') || exit;

$alamat = (string) velocity_fse_situs('alamat');
$telp = (string) velocity_fse_situs('telp');
$email = (string) velocity_fse_situs('email_publik');
$wa = velocity_fse_wa_link();

$baris = array();
if ($alamat !== '') {
    $baris[] = array('Alamat', esc_html($alamat));
}
if ($wa !== '') {
    $baris[] = array('WhatsApp', sprintf('<a href="%s" target="_blank" rel="noopener nofollow">%s</a>',
        esc_url($wa), esc_html($telp !== '' ? $telp : 'Chat WhatsApp')));
} elseif ($telp !== '') {
    $baris[] = array('Telepon', esc_html($telp));
}
if ($email !== '') {
    $baris[] = array('Email', sprintf('<a href="mailto:%1$s">%1$s</a>', esc_html($email)));
}
if (!$baris && function_exists('velocity_fse_toko') && velocity_fse_toko()) {
    // Toko tanpa kontak publik dan tanpa formulir di Hubungi Kami (yukpergimancing.com):
    // arahkan ke katalog, bukan ke formulir yang tidak ada.
    $kontak_hal = get_page_by_path('hubungi-kami');
    $arsip = get_post_type_archive_link('store_product');
    if ($arsip && (!$kontak_hal || !has_block('velocity/form-kirim', $kontak_hal))) {
        $baris[] = array('Belanja', sprintf('<a href="%s">Pesan langsung lewat katalog produk</a>', esc_url($arsip)));
    }
}
if (!$baris) {
    // Tanpa kontak publik: arahkan ke formulir, jangan menampilkan kotak kosong.
    $halaman = get_page_by_path('hubungi-kami');
    if (!$halaman) {
        return;
    }
    $baris[] = array('Pesan', sprintf('<a href="%s">Kirim pesan lewat formulir</a>', esc_url(get_permalink($halaman))));
}
?>
<ul <?php echo get_block_wrapper_attributes(array('class' => 'vf-kontak')); ?>>
	<?php foreach ($baris as $b) : ?>
		<li><span><?php echo esc_html($b[0]); ?></span><?php echo $b[1]; // phpcs:ignore -- sudah di-escape di atas ?></li>
	<?php endforeach; ?>
</ul>
