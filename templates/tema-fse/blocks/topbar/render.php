<?php

/** Baris tipis di atas header: tanggal (portal berita) atau alamat, lalu slogan. */

defined('ABSPATH') || exit;

$kiri = velocity_fse_jenis_berita()
    ? velocity_fse_tanggal_id((int) current_time('timestamp'), true)
    : (string) velocity_fse_situs('alamat');
$kanan = (string) velocity_fse_situs('slogan');

// Topbar gelap referensi (token topbar_gelap): kontak publik di kiri, kolom cari di kanan
// (kreditmotor.rmg.asia: telepon | cari). Kontak hanya dari Data Situs publik.
if (function_exists('velocity_fse_token') && velocity_fse_token('topbar_gelap') && !velocity_fse_jenis_berita()) {
    $kontak = array_filter(array(
        (string) velocity_fse_situs('telp'),
        (string) velocity_fse_situs('email_publik'),
    ));
    $kiri = $kontak ? implode(' · ', $kontak) : ($kanan !== '' ? $kanan : $kiri);
    ?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-topbar vf-topbar--cari')); ?>>
	<div class="vf-topbar__isi">
		<span class="vf-topbar__kiri"><?php echo esc_html($kiri); ?></span>
		<?php if (!velocity_fse_token('tanpa_cari')) : ?>
		<form class="vf-topbar__cari" role="search" method="get" action="<?php echo esc_url(home_url('/')); ?>">
			<label class="screen-reader-text" for="vf-topbar-cari">Cari</label>
			<input id="vf-topbar-cari" type="search" name="s" placeholder="<?php echo esc_attr(velocity_fse_toko() ? 'Cari produk…' : 'Cari…'); ?>" value="<?php echo esc_attr(get_search_query()); ?>">
			<?php if (velocity_fse_toko()) : ?><input type="hidden" name="post_type" value="store_product"><?php endif; ?>
			<button type="submit" aria-label="Cari"><svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path fill="currentColor" d="M10 2a8 8 0 0 1 6.32 12.9l5.39 5.4-1.41 1.4-5.4-5.39A8 8 0 1 1 10 2zm0 2a6 6 0 1 0 0 12 6 6 0 0 0 0-12z"/></svg></button>
		</form>
		<?php elseif ($kanan !== '' && $kanan !== $kiri) : ?>
		<?php // Referensi tanpa kotak cari (centralimpex.com): slogan di kanan seperti topbar referensinya. ?>
		<span class="vf-topbar__kanan"><?php echo esc_html($kanan); ?></span>
		<?php endif; ?>
	</div>
</div>
    <?php
    return;
}

if ($kiri === '' && $kanan === '') {
    return;
}
?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-topbar')); ?>>
	<div class="vf-topbar__isi">
		<span><?php echo esc_html($kiri); ?></span>
		<?php if ($kanan !== '') : ?>
			<span class="vf-topbar__slogan"><?php echo esc_html($kanan); ?></span>
		<?php endif; ?>
	</div>
</div>
