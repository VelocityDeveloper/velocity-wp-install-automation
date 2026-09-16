<?php

/**
 * Kartu satu unit mobil — bentuknya mengikuti referensi desain klien: kolom kiri
 * (nama, pita tenaga/torsi/jarak, pilihan warna, harga, tombol) dan foto unit di
 * kolom kanan dengan nama model sebagai latar.
 *
 * Datanya dari Data Unit (meta CPT mobil), jadi PM mengubah angka di wp-admin
 * tanpa menyentuh tema.
 */

defined('ABSPATH') || exit;

$post_id = !empty($block->context['postId']) ? (int) $block->context['postId'] : (int) get_the_ID();
if (!$post_id || get_post_type($post_id) !== 'mobil') {
    return;
}
$m = velocity_fse_mobil($post_id);
$ringkas = array_filter(array(
    'Max Power'    => $m['daya'],
    'Torque'       => $m['torsi'],
    'Jarak Tempuh' => $m['jarak'],
));
$test_drive = get_page_by_path('test-drive');
$url_test_drive = (string) ($attributes['tombolTestDrive'] ?? '');
if ($url_test_drive === '') {
    $url_test_drive = $test_drive ? get_permalink($test_drive) : velocity_fse_wa_link(sprintf('Halo, saya ingin test drive %s.', $m['nama']));
}
$foto = get_the_post_thumbnail($post_id, 'large', array('alt' => esc_attr($m['nama']), 'loading' => 'lazy'));
?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-mobil')); ?>>
	<div class="vf-mobil__isi">
		<h3 class="vf-mobil__nama"><a href="<?php echo esc_url($m['url']); ?>"><?php echo esc_html($m['nama']); ?></a></h3>

		<?php if ($ringkas) : ?>
			<div class="vf-mobil__ringkas">
				<?php foreach ($ringkas as $label => $nilai) : ?>
					<div class="vf-mobil__angka">
						<span class="vf-mobil__label"><?php echo esc_html($label); ?></span>
						<strong><?php echo esc_html($nilai); ?></strong>
					</div>
				<?php endforeach; ?>
			</div>
		<?php endif; ?>

		<?php if ($m['warna']) : ?>
			<ul class="vf-warna">
				<?php foreach ($m['warna'] as $w) : ?>
					<li class="vf-warna__item">
						<span class="vf-warna__bulat" style="background:<?php echo esc_attr(preg_match('/^#[0-9a-fA-F]{3,8}$/', $w['hex']) ? $w['hex'] : '#c9ced6'); ?>"></span>
						<?php echo esc_html($w['nama']); ?>
					</li>
				<?php endforeach; ?>
			</ul>
		<?php endif; ?>

		<p class="vf-mobil__harga"><?php echo esc_html(velocity_fse_mobil_harga_teks($m)); ?></p>

		<div class="vf-mobil__tombol">
			<a class="wp-element-button vf-tombol" href="<?php echo esc_url($m['url']); ?>">Spesifikasi</a>
			<?php if ($url_test_drive !== '') : ?>
				<a class="vf-tombol vf-tombol--garis" href="<?php echo esc_url($url_test_drive); ?>">Test Drive</a>
			<?php endif; ?>
		</div>
	</div>

	<div class="vf-mobil__foto">
		<?php if ($foto) : ?>
			<a href="<?php echo esc_url($m['url']); ?>"><?php echo $foto; // phpcs:ignore -- keluaran WordPress ?></a>
		<?php endif; ?>
	</div>
</div>
