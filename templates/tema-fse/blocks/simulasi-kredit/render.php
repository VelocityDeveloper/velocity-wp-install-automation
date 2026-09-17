<?php

/**
 * Simulasi kredit unit mobil (halaman Simulasi Kredit & halaman unit).
 *
 * Bentuknya mengikuti halaman simulasi kredit referensi klien: kolom kiri untuk pilihan
 * (tipe mobil, slider uang muka, slider bunga, tenor berupa tombol pil) dan kolom kanan
 * untuk hasil (cicilan besar, rincian, tombol ajukan).
 *
 * Harga diambil dari Data Unit, jadi angka tidak pernah dikarang di tema: unit yang
 * harganya belum dipastikan tetap bisa dipilih, tetapi pengunjung mengisi harganya
 * sendiri. Bunga & tenor adalah masukan pengunjung — hasilnya estimasi, bukan penawaran.
 */

defined('ABSPATH') || exit;

$unit = array();
foreach (velocity_fse_mobil_semua(20) as $m) {
    $unit[] = array(
        'nama'    => $m['nama'],
        'harga'   => (int) $m['harga'],
        'catatan' => $m['harga_catatan'],
        'label'   => $m['harga'] > 0
            ? $m['nama'] . ' — ' . velocity_fse_rupiah($m['harga'])
            : $m['nama'] . ' — harga menyesuaikan',
    );
}
$bunga = max(0, min(30, (float) ($attributes['bunga'] ?? 6)));
$dp = max(10, min(60, (float) ($attributes['dp'] ?? 20)));
$wa = velocity_fse_wa_link('Halo, saya ingin dibantu simulasi kredit unit ' . velocity_fse_situs('nama') . '.');
$id = 'vf-kredit-' . wp_unique_id();
$tenor_pilihan = array(1, 2, 3, 4, 5);
$tenor_awal = 3;
?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-kredit')); ?> id="<?php echo esc_attr($id); ?>"
	data-unit="<?php echo esc_attr(wp_json_encode($unit)); ?>">
	<div class="vf-kredit__form">
		<?php if ($unit) : ?>
			<p class="vf-kredit__baris">
				<label for="<?php echo esc_attr($id); ?>-unit">Pilih tipe mobil</label>
				<select id="<?php echo esc_attr($id); ?>-unit" data-vf="unit">
					<?php foreach ($unit as $i => $u) : ?>
						<option value="<?php echo esc_attr($i); ?>"><?php echo esc_html($u['label']); ?></option>
					<?php endforeach; ?>
					<option value="lain">Tipe lain / harga sendiri</option>
				</select>
			</p>
		<?php endif; ?>

		<p class="vf-kredit__catatan-harga" data-vf="catatan-harga"></p>

		<p class="vf-kredit__baris" data-vf="baris-harga"<?php echo $unit && $unit[0]['harga'] > 0 ? ' hidden' : ''; ?>>
			<label for="<?php echo esc_attr($id); ?>-harga">Harga unit (Rp)</label>
			<input id="<?php echo esc_attr($id); ?>-harga" data-vf="harga" type="number" inputmode="numeric" min="0" step="1000000"
				value="<?php echo esc_attr($unit && $unit[0]['harga'] > 0 ? $unit[0]['harga'] : ''); ?>" placeholder="Contoh: 700000000">
		</p>

		<div class="vf-kredit__geser">
			<div class="vf-kredit__geser-kepala">
				<label for="<?php echo esc_attr($id); ?>-dp">Uang muka (DP)</label>
				<strong data-vf="dp-persen"><?php echo esc_html($dp); ?>%</strong>
			</div>
			<input id="<?php echo esc_attr($id); ?>-dp" data-vf="dp" type="range" min="10" max="60" step="1"
				value="<?php echo esc_attr($dp); ?>">
			<span class="vf-kredit__petunjuk">Geser untuk mengatur persentase DP, 10%–60%.</span>
		</div>

		<div class="vf-kredit__geser">
			<div class="vf-kredit__geser-kepala">
				<label for="<?php echo esc_attr($id); ?>-bunga">Suku bunga per tahun</label>
				<strong data-vf="bunga-persen"><?php echo esc_html(number_format($bunga, 1, ',', '.')); ?>%</strong>
			</div>
			<input id="<?php echo esc_attr($id); ?>-bunga" data-vf="bunga" type="range" min="0" max="15" step="0.1"
				value="<?php echo esc_attr($bunga); ?>">
			<span class="vf-kredit__petunjuk">Bunga flat tahunan, indikatif — besaran akhir mengikuti perusahaan pembiayaan.</span>
		</div>

		<div class="vf-kredit__tenor">
			<span class="vf-kredit__tenor-label">Tenor pinjaman</span>
			<div class="vf-kredit__tenor-pil" role="radiogroup" aria-label="Tenor pinjaman">
				<?php foreach ($tenor_pilihan as $tahun) : ?>
					<label class="vf-kredit__pil">
						<input type="radio" name="<?php echo esc_attr($id); ?>-tenor" data-vf="tenor"
							value="<?php echo esc_attr($tahun * 12); ?>"<?php echo $tahun === $tenor_awal ? ' checked' : ''; ?>>
						<span><?php echo esc_html($tahun); ?> Th</span>
					</label>
				<?php endforeach; ?>
			</div>
		</div>
	</div>

	<div class="vf-kredit__hasil" data-vf="hasil" aria-live="polite">
		<span class="vf-kredit__label">Estimasi cicilan bulanan</span>
		<strong class="vf-kredit__cicilan" data-vf="cicilan">—</strong>
		<span class="vf-kredit__ringkas" data-vf="ringkas"></span>

		<div class="vf-kredit__bar"><span data-vf="bar"></span></div>
		<div class="vf-kredit__bar-ket">
			<span>DP dibayar di muka</span>
			<span data-vf="dp-bar">—</span>
		</div>

		<ul class="vf-kredit__rincian">
			<li><span>Harga mobil</span><strong data-vf="harga-nilai">—</strong></li>
			<li><span>Uang muka</span><strong data-vf="dp-nilai">—</strong></li>
			<li><span>Jumlah pinjaman</span><strong data-vf="pokok">—</strong></li>
			<li><span>Total bunga</span><strong data-vf="bunga-nilai">—</strong></li>
			<li><span>Total pembayaran</span><strong data-vf="total">—</strong></li>
		</ul>

		<?php if ($wa !== '') : ?>
			<a class="wp-element-button vf-kredit__ajukan" data-vf="wa" href="<?php echo esc_url($wa); ?>" target="_blank" rel="noopener nofollow">Ajukan Simulasi Sekarang</a>
		<?php endif; ?>
		<p class="vf-kredit__catatan">Angka di atas estimasi hitungan bunga flat. Asuransi, biaya administrasi, dan persetujuan akhir mengikuti ketentuan perusahaan pembiayaan.</p>
	</div>
</div>
