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
    $baris[] = array('Alamat', esc_html($alamat), 'alamat');
}
// Dulu baris WhatsApp memakai `telp` sebagai teksnya — benar selama telp memang nomor
// WhatsApp yang sama. Sejak telepon kantor company profile ikut terbaca, keduanya bisa
// berbeda dan nomor kantor sempat tampil berlabel "WhatsApp" padahal tautannya ke nomor
// lain (solusicerdasconsulting.com, 2026-09-18). Nomor berbeda = dua baris.
$nomor_wa = (string) velocity_fse_situs('wa');
$samakan = function ($nilai) {
    $angka = preg_replace('/\D/', '', (string) $nilai);
    return $angka === '' ? '' : preg_replace('/^0/', '62', $angka);
};
$telp_sama_wa = $telp !== '' && $samakan($telp) === $samakan($nomor_wa);
if ($wa !== '') {
    $tampil = $telp_sama_wa ? $telp : ($nomor_wa !== '' ? $nomor_wa : 'Chat WhatsApp');
    $baris[] = array('WhatsApp', sprintf('<a href="%s" target="_blank" rel="noopener nofollow">%s</a>',
        esc_url($wa), esc_html($tampil)), 'whatsapp');
}
if ($telp !== '' && !$telp_sama_wa) {
    $baris[] = array('Telepon', sprintf('<a href="tel:%s">%s</a>',
        esc_attr(preg_replace('/[^0-9+]/', '', $telp)), esc_html($telp)), 'telepon');
}
if ($email !== '') {
    $baris[] = array('Email', sprintf('<a href="mailto:%1$s">%1$s</a>', esc_html($email)), 'email');
}
if (!$baris && function_exists('velocity_fse_toko') && velocity_fse_toko()) {
    // Toko tanpa kontak publik dan tanpa formulir di Hubungi Kami (yukpergimancing.com):
    // arahkan ke katalog, bukan ke formulir yang tidak ada.
    $kontak_hal = get_page_by_path('hubungi-kami');
    $arsip = get_post_type_archive_link('store_product');
    if ($arsip && (!$kontak_hal || !has_block('velocity/form-kirim', $kontak_hal))) {
        $baris[] = array('Belanja', sprintf('<a href="%s">Pesan langsung lewat katalog produk</a>', esc_url($arsip)), 'belanja');
    }
}
if (!$baris) {
    // Tanpa kontak publik: arahkan ke formulir, jangan menampilkan kotak kosong.
    $halaman = get_page_by_path('hubungi-kami');
    if (!$halaman) {
        return;
    }
    $baris[] = array('Pesan', sprintf('<a href="%s">Kirim pesan lewat formulir</a>', esc_url(get_permalink($halaman))), 'pesan');
}

// Atribut `tampilan`: "daftar" (bawaan, dipakai footer) atau "kartu" — satu kartu berikon
// per jenis kontak untuk halaman Hubungi Kami (permintaan user 2026-09-18).
$tampilan = isset($attributes['tampilan']) && $attributes['tampilan'] === 'kartu' ? 'kartu' : 'daftar';
$ikon = array(
    'alamat' => 'M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z',
    'whatsapp' => 'M12 3.5a8.4 8.4 0 0 0-7.2 12.7L3.5 21l4.9-1.3A8.4 8.4 0 1 0 12 3.5Zm4.9 11.9c-.2.6-1.2 1.1-1.7 1.2-.4 0-1 .1-1.6-.1-.4-.1-.9-.3-1.5-.6-2.6-1.1-4.3-3.8-4.4-4-.1-.2-1-1.4-1-2.6s.6-1.8.8-2.1c.2-.2.5-.3.6-.3h.5c.2 0 .4 0 .6.4l.8 1.9c.1.1.1.3 0 .5l-.3.4-.4.4c-.1.1-.3.3-.1.6.1.3.6 1.1 1.4 1.8 1 .9 1.8 1.1 2 1.3.3.1.4.1.6-.1l.8-1c.2-.2.4-.2.6-.1l1.8.9c.3.1.4.2.5.3 0 .1 0 .5-.1 1.1Z',
    'telepon' => 'M6.6 3h3l1.5 3.7-2 1.3a12 12 0 0 0 5 5l1.3-2 3.7 1.5v3c0 .8-.7 1.5-1.5 1.5A15.5 15.5 0 0 1 5 5.5C5 4.7 5.7 4 6.6 4V3Z',
    'email' => 'M4 5h16c.6 0 1 .4 1 1v12c0 .6-.4 1-1 1H4a1 1 0 0 1-1-1V6c0-.6.4-1 1-1Zm8 7.2 7-4.4V6.6l-7 4.4-7-4.4v1.2l7 4.4Z',
    'belanja' => 'M7 4h10l1 4H6l1-4Zm-2 6h14l-1.2 9H6.2L5 10Zm4 2v5h2v-5H9Zm4 0v5h2v-5h-2Z',
    'pesan' => 'M4 5h16c.6 0 1 .4 1 1v10c0 .6-.4 1-1 1H8l-4 4V6c0-.6.4-1 1-1Z',
);
if ($tampilan !== 'kartu') :
?>
<ul <?php echo get_block_wrapper_attributes(array('class' => 'vf-kontak')); ?>>
	<?php foreach ($baris as $b) : ?>
		<li><span><?php echo esc_html($b[0]); ?></span><?php echo $b[1]; // phpcs:ignore -- sudah di-escape di atas ?></li>
	<?php endforeach; ?>
</ul>
<?php else : ?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-kontak-kartu')); ?>>
	<?php foreach ($baris as $b) : $jenis = $b[2] ?? 'pesan'; ?>
		<div class="vf-kontak-kartu__item vf-kontak-kartu__item--<?php echo esc_attr($jenis); ?>">
			<span class="vf-kontak-kartu__ikon" aria-hidden="true">
				<svg viewBox="0 0 24 24" focusable="false"><path d="<?php echo esc_attr($ikon[$jenis] ?? $ikon['pesan']); ?>"/></svg>
			</span>
			<span class="vf-kontak-kartu__judul"><?php echo esc_html($b[0]); ?></span>
			<span class="vf-kontak-kartu__isi"><?php echo $b[1]; // phpcs:ignore -- sudah di-escape di atas ?></span>
		</div>
	<?php endforeach; ?>
</div>
<?php endif;
