<?php
/**
 * Beranda landing page: seksi-seksi dari Customizer (Tampilan → Sesuaikan → Landing Page).
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;

get_header();
echo '<main id="vlp-beranda" class="vlp-beranda">';
foreach (vlp_urutan() as $id) {
	vlp_seksi($id);
}
echo '</main>';
get_footer();
