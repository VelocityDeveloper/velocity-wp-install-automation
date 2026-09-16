<?php

/** Pilihan warna unit mobil (Data Unit → Pilihan Warna). */

defined('ABSPATH') || exit;

$post_id = !empty($block->context['postId']) ? (int) $block->context['postId'] : (int) get_the_ID();
$warna = $post_id ? velocity_fse_mobil_daftar($post_id, 'vfse_mobil_warna', array('nama', 'hex')) : array();
if (!$warna) {
    return;
}
?>
<ul <?php echo get_block_wrapper_attributes(array('class' => 'vf-warna')); ?>>
	<?php foreach ($warna as $w) : ?>
		<li class="vf-warna__item">
			<span class="vf-warna__bulat" style="background:<?php echo esc_attr(preg_match('/^#[0-9a-fA-F]{3,8}$/', $w['hex']) ? $w['hex'] : '#c9ced6'); ?>"></span>
			<?php echo esc_html($w['nama']); ?>
		</li>
	<?php endforeach; ?>
</ul>
