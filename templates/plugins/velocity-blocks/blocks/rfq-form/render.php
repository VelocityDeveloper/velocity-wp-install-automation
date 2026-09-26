<?php
/** vb/rfq-form — form pemesanan / permintaan penawaran. Pengolah kiriman: inc/rfq.php. */
$status = isset( $_GET['rfq'] ) ? sanitize_key( wp_unslash( $_GET['rfq'] ) ) : ''; // phpcs:ignore
$pilih  = isset( $_GET['product'] ) ? sanitize_text_field( wp_unslash( $_GET['product'] ) ) : ''; // phpcs:ignore
$gagal  = array(
	'kurang'        => 'Mohon lengkapi kolom bertanda * dengan alamat email yang benar.',
	'kedaluwarsa'   => 'Sesi form sudah kedaluwarsa. Silakan kirim ulang.',
	'captcha'       => 'Kode captcha belum benar. Silakan coba lagi.',
	'terlalu_cepat' => 'Pesan Anda baru saja terkirim. Mohon tunggu satu menit sebelum mengirim lagi.',
);
$halaman = get_permalink() ? get_permalink() : home_url( '/' );
$pilihan = vb_rfq_pilihan();
echo '<div ' . get_block_wrapper_attributes( array( 'class' => 'vb-rfq', 'id' => 'rfq' ) ) . '>'; // phpcs:ignore
if ( 'terkirim' === $status ) :
	?>
	<div class="vb-rfq__ok" role="status">
		<?php echo vb_ikon( 'circle-check', 'vb-ikon vb-rfq__ok-icon' ); // phpcs:ignore ?>
		<h3>Terima kasih — pesan Anda sudah terkirim.</h3>
		<p>Kami akan menghubungi Anda melalui email atau WhatsApp. Ingin lebih cepat? Kirim pesan langsung lewat WhatsApp.</p>
		<div class="vb-row vb-justify-left vb-gap-sm">
			<a class="vb-btn vb-btn--outline vb-btn--md" href="<?php echo esc_url( remove_query_arg( 'rfq' ) ); ?>#rfq"><span class="vb-btn__text">Kirim pesan lagi</span></a>
			<a class="vb-btn vb-btn--whatsapp vb-btn--md" href="<?php echo esc_url( vb_wa_link() ); ?>" target="_blank" rel="noopener"><?php echo vb_ikon( 'whatsapp', 'vb-ikon vb-btn__icon' ); // phpcs:ignore ?><span class="vb-btn__text">WhatsApp</span></a>
		</div>
	</div>
<?php else : ?>
	<form class="vb-rfq__form" method="post" action="<?php echo esc_url( $halaman ); ?>#rfq">
		<?php if ( isset( $gagal[ $status ] ) ) : ?>
			<div class="vb-rfq__err" role="alert"><?php echo esc_html( $gagal[ $status ] ); ?></div>
		<?php endif; ?>
		<div class="vb-rfq__grid">
			<?php foreach ( vb_rfq_kolom() as $nama => $k ) :
				$ekstra = $k[3];
				$attr   = ' name="' . esc_attr( $nama ) . '" id="vb-rfq-' . esc_attr( $nama ) . '"';
				$attr  .= $k[2] ? ' required' : '';
				$attr  .= isset( $ekstra['autocomplete'] ) ? ' autocomplete="' . esc_attr( $ekstra['autocomplete'] ) . '"' : '';
				$attr  .= isset( $ekstra['placeholder'] ) ? ' placeholder="' . esc_attr( $ekstra['placeholder'] ) . '"' : '';
				?>
				<p class="vb-rfq__field<?php echo ! empty( $ekstra['span'] ) ? ' vb-rfq__field--span' : ''; ?>">
					<label for="vb-rfq-<?php echo esc_attr( $nama ); ?>"><?php echo esc_html( $k[0] ); ?><?php echo $k[2] ? ' <span aria-hidden="true">*</span>' : ''; ?></label>
					<?php if ( 'textarea' === $k[1] ) : ?>
						<textarea rows="4"<?php echo $attr; // phpcs:ignore ?>></textarea>
					<?php elseif ( 'pilihan' === $k[1] && $pilihan ) : ?>
						<select<?php echo $attr; // phpcs:ignore ?>>
							<option value="">— Pilih layanan —</option>
							<?php foreach ( $pilihan as $t ) : ?>
								<option value="<?php echo esc_attr( $t ); ?>"<?php selected( $pilih, $t ); ?>><?php echo esc_html( $t ); ?></option>
							<?php endforeach; ?>
							<option value="Lainnya / belum tahu">Lainnya / belum tahu</option>
						</select>
					<?php else : ?>
						<input type="<?php echo esc_attr( 'pilihan' === $k[1] ? 'text' : $k[1] ); ?>"<?php echo $attr; // phpcs:ignore ?> />
					<?php endif; ?>
				</p>
			<?php endforeach; ?>
			<?php
			$captcha = vb_rfq_captcha();
			if ( '' !== trim( $captcha ) ) :
				?>
				<div class="vb-rfq__field vb-rfq__field--span vb-rfq__captcha"><?php echo $captcha; // phpcs:ignore ?></div>
			<?php endif; ?>
		</div>
		<p class="vb-rfq__trap" aria-hidden="true"><label>Website<input type="text" name="vb_website" tabindex="-1" autocomplete="off" /></label></p>
		<input type="hidden" name="vb_kembali" value="<?php echo esc_url( $halaman ); ?>" />
		<?php wp_nonce_field( 'vb_rfq', 'vb_nonce' ); ?>
		<button class="vb-btn vb-btn--accent vb-btn--lg" type="submit" name="vb_rfq" value="1"><span class="vb-btn__text"><?php echo esc_html( $attributes['buttonText'] ?? 'Kirim Pesan' ); ?></span><?php echo vb_ikon( 'send', 'vb-ikon vb-btn__icon' ); // phpcs:ignore ?></button>
	</form>
<?php
endif;
echo '</div>';
