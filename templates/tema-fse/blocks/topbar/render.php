<?php

/** Baris tipis di atas header: tanggal (portal berita) atau alamat, lalu slogan. */

defined('ABSPATH') || exit;

$kiri = velocity_fse_jenis_berita()
    ? velocity_fse_tanggal_id((int) current_time('timestamp'), true)
    : (string) velocity_fse_situs('alamat');
$kanan = (string) velocity_fse_situs('slogan');
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
