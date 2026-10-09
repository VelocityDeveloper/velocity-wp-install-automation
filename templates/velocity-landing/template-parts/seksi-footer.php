<?php
/**
 * Footer landing: logo + kontak, tentang, tautan + media sosial, statistik pengunjung, hak cipta.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;
$hak_cipta = strtr((string) vlp_mod('footer', 'hak_cipta'), array('{tahun}' => wp_date('Y'), '{situs}' => get_bloginfo('name')));
$kredit = trim((string) vlp_mod('footer', 'kredit'));
$sosmed = vlp_sosmed();
$telepon = trim((string) vlp_mod('footer', 'telepon'));
$email = sanitize_email((string) vlp_mod('footer', 'email'));
// Statistik pengunjung velocity-addons: kolom footer berjudul, isi list (aturan installer).
$statistik = vlp_mod('footer', 'statistik') && shortcode_exists('velocity-statistics');
$logo = vlp_img(vlp_mod('footer', 'logo'), get_bloginfo('name'), '', 'medium', '235px');
?>
<footer id="vlp-footer" class="vlp-footer">
	<div class="vlp-wadah vlp-footer-grid<?php echo $statistik ? ' vlp-footer-grid--4' : ''; ?>">
		<div class="vlp-footer-kolom">
			<a class="vlp-footer-logo" href="<?php echo esc_url(home_url('/')); ?>">
				<?php echo $logo ? $logo : '<span class="vlp-footer-nama">' . esc_html(get_bloginfo('name')) . '</span>'; ?>
			</a>
			<div class="vlp-footer-teks"><?php echo vlp_paragraf(vlp_mod('footer', 'alamat')); ?></div>
			<?php if ($telepon || $email) : ?>
				<ul class="vlp-footer-kontak">
					<?php if ($telepon) : ?>
						<li><i class="fa-solid fa-phone" aria-hidden="true"></i><a href="tel:<?php echo esc_attr(preg_replace('/[^0-9+]/', '', $telepon)); ?>"><?php echo esc_html($telepon); ?></a></li>
					<?php endif; ?>
					<?php if ($email) : ?>
						<li><i class="fa-solid fa-envelope" aria-hidden="true"></i><a href="mailto:<?php echo esc_attr($email); ?>"><?php echo esc_html($email); ?></a></li>
					<?php endif; ?>
				</ul>
			<?php endif; ?>
		</div>
		<div class="vlp-footer-kolom">
			<h2 class="vlp-footer-judul"><?php echo esc_html(vlp_mod('footer', 'tentang_judul')); ?></h2>
			<div class="vlp-footer-teks"><?php echo vlp_paragraf(vlp_mod('footer', 'tentang_teks')); ?></div>
		</div>
		<div class="vlp-footer-kolom">
			<h2 class="vlp-footer-judul"><?php echo esc_html(vlp_mod('footer', 'link_judul')); ?></h2>
			<?php
			if (has_nav_menu('vlp_footer')) {
				wp_nav_menu(array('theme_location' => 'vlp_footer', 'container' => false, 'menu_class' => 'vlp-footer-menu', 'depth' => 1));
			} else {
				echo '<ul class="vlp-footer-menu">';
				echo '<li><a href="' . esc_url(vlp_wa_url()) . '" target="_blank" rel="noopener">WhatsApp</a></li>';
				$privasi = get_privacy_policy_url();
				if ($privasi) {
					echo '<li><a href="' . esc_url($privasi) . '">' . esc_html(get_the_title((int) get_option('wp_page_for_privacy_policy'))) . '</a></li>';
				}
				echo '</ul>';
			}
			?>
			<?php if ($sosmed) : ?>
				<h2 class="vlp-footer-judul vlp-footer-judul--sosmed"><?php echo esc_html(vlp_mod('footer', 'sosmed_judul')); ?></h2>
				<ul class="vlp-sosmed">
					<?php foreach ($sosmed as $s) : ?>
						<li><a href="<?php echo esc_url($s[0]); ?>" target="_blank" rel="noopener" aria-label="<?php echo esc_attr($s[2]); ?>"><?php echo vlp_ikon($s[1]); ?></a></li>
					<?php endforeach; ?>
				</ul>
			<?php endif; ?>
		</div>
		<?php if ($statistik) : ?>
			<div class="vlp-footer-kolom vlp-statistik">
				<h2 class="vlp-footer-judul"><?php echo esc_html(vlp_mod('footer', 'statistik_judul')); ?></h2>
				<?php echo do_shortcode('[velocity-statistics style="list"]'); ?>
			</div>
		<?php endif; ?>
	</div>
	<div class="vlp-wadah vlp-footer-bawah">
		<p><?php echo esc_html($hak_cipta); ?></p>
		<?php if ($kredit) : ?>
			<p><?php echo wp_kses_post($kredit); ?></p>
		<?php endif; ?>
	</div>
</footer>
