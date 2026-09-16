<?php

/**
 * Simulasi kredit unit mobil (halaman Simulasi Kredit & halaman unit).
 *
 * Harga diambil dari Data Unit, jadi angka tidak pernah dikarang di tema: unit
 * yang harganya belum dipastikan tidak muncul di pilihan, dan pengunjung bisa
 * mengisi harga sendiri. Bunga & tenor adalah masukan pengunjung — hasilnya
 * ditulis sebagai estimasi, bukan penawaran.
 */

defined('ABSPATH') || exit;

$unit = array();
foreach (velocity_fse_mobil_semua(20) as $m) {
    if ($m['harga'] > 0) {
        $unit[] = array('nama' => $m['nama'], 'harga' => (int) $m['harga']);
    }
}
$bunga = max(0, min(30, (float) ($attributes['bunga'] ?? 6)));
$dp = max(0, min(90, (float) ($attributes['dp'] ?? 20)));
$wa = velocity_fse_wa_link('Halo, saya ingin dibantu simulasi kredit unit XPENG.');
$id = 'vf-kredit-' . wp_unique_id();
?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-kredit')); ?> id="<?php echo esc_attr($id); ?>"
	data-unit="<?php echo esc_attr(wp_json_encode($unit)); ?>">
	<form class="vf-kredit__form">
		<?php if ($unit) : ?>
			<p class="vf-kredit__baris">
				<label for="<?php echo esc_attr($id); ?>-unit">Pilih unit</label>
				<select id="<?php echo esc_attr($id); ?>-unit" data-vf="unit">
					<?php foreach ($unit as $i => $u) : ?>
						<option value="<?php echo esc_attr($i); ?>"><?php echo esc_html($u['nama']); ?></option>
					<?php endforeach; ?>
					<option value="lain">Harga lain</option>
				</select>
			</p>
		<?php endif; ?>

		<p class="vf-kredit__baris">
			<label for="<?php echo esc_attr($id); ?>-harga">Harga unit (Rp)</label>
			<input id="<?php echo esc_attr($id); ?>-harga" data-vf="harga" type="number" inputmode="numeric" min="0" step="1000000"
				value="<?php echo esc_attr($unit ? $unit[0]['harga'] : ''); ?>" placeholder="695000000" required>
		</p>

		<p class="vf-kredit__baris">
			<label for="<?php echo esc_attr($id); ?>-dp">Uang muka (%)</label>
			<input id="<?php echo esc_attr($id); ?>-dp" data-vf="dp" type="number" inputmode="numeric" min="0" max="90" step="1"
				value="<?php echo esc_attr($dp); ?>">
		</p>

		<p class="vf-kredit__baris">
			<label for="<?php echo esc_attr($id); ?>-tenor">Tenor</label>
			<select id="<?php echo esc_attr($id); ?>-tenor" data-vf="tenor">
				<?php foreach (array(12, 24, 36, 48, 60) as $bulan) : ?>
					<option value="<?php echo esc_attr($bulan); ?>"<?php echo 36 === $bulan ? ' selected' : ''; ?>>
						<?php echo esc_html($bulan . ' bulan'); ?>
					</option>
				<?php endforeach; ?>
			</select>
		</p>

		<p class="vf-kredit__baris">
			<label for="<?php echo esc_attr($id); ?>-bunga">Bunga per tahun (%)</label>
			<input id="<?php echo esc_attr($id); ?>-bunga" data-vf="bunga" type="number" inputmode="decimal" min="0" max="30" step="0.1"
				value="<?php echo esc_attr($bunga); ?>">
		</p>
	</form>

	<div class="vf-kredit__hasil" data-vf="hasil" aria-live="polite">
		<div class="vf-kredit__cicilan">
			<span class="vf-kredit__label">Estimasi cicilan per bulan</span>
			<strong data-vf="cicilan">—</strong>
		</div>
		<ul class="vf-kredit__rincian">
			<li><span>Uang muka</span><strong data-vf="dp-nilai">—</strong></li>
			<li><span>Pokok pinjaman</span><strong data-vf="pokok">—</strong></li>
			<li><span>Total bunga</span><strong data-vf="bunga-nilai">—</strong></li>
			<li><span>Total pembayaran</span><strong data-vf="total">—</strong></li>
		</ul>
		<p class="vf-kredit__catatan">Angka di atas estimasi hitungan bunga flat. Besaran uang muka, tenor, bunga, asuransi, dan biaya administrasi mengikuti ketentuan perusahaan pembiayaan.</p>
		<?php if ($wa !== '') : ?>
			<p><a class="wp-element-button vf-tombol" data-vf="wa" href="<?php echo esc_url($wa); ?>" target="_blank" rel="noopener nofollow">Konsultasi via WhatsApp</a></p>
		<?php endif; ?>
	</div>
</div>
