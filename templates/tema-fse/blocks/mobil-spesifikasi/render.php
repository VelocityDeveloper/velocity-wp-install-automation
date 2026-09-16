<?php

/**
 * Tabel spesifikasi unit mobil. Tiga angka utama selalu ikut supaya halaman
 * spesifikasi tidak kosong walau baris Spesifikasi belum diisi PM.
 */

defined('ABSPATH') || exit;

$post_id = !empty($block->context['postId']) ? (int) $block->context['postId'] : (int) get_the_ID();
if (!$post_id || get_post_type($post_id) !== 'mobil') {
    return;
}
$m = velocity_fse_mobil($post_id);
$baris = array();
foreach (array('Max Power' => $m['daya'], 'Torque' => $m['torsi'], 'Jarak Tempuh' => $m['jarak']) as $label => $nilai) {
    if ($nilai !== '') {
        $baris[] = array($label, $nilai);
    }
}
foreach ($m['spek'] as $s) {
    $baris[] = array($s['label'], $s['nilai']);
}
$baris[] = array('Harga', velocity_fse_mobil_harga_teks($m));
?>
<table <?php echo get_block_wrapper_attributes(array('class' => 'vf-spek')); ?>>
	<tbody>
		<?php foreach ($baris as $b) : ?>
			<tr>
				<th scope="row"><?php echo esc_html($b[0]); ?></th>
				<td><?php echo esc_html($b[1] !== '' ? $b[1] : '—'); ?></td>
			</tr>
		<?php endforeach; ?>
	</tbody>
</table>
