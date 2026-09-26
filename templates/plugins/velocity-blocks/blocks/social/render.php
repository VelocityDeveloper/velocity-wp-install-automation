<?php
/** vb/social — ikon sosmed Data Situs (ikon bawaan core/social-link), tab baru. */
$a    = $attributes;
$nama = vb_platform_sosmed();
echo '<ul ' . get_block_wrapper_attributes( array( 'class' => 'vb-social vb-social--' . sanitize_html_class( $a['size'] ?? 'md' ) . ' vb-justify-' . sanitize_html_class( $a['justify'] ?? 'left' ) ) ) . '>'; // phpcs:ignore
foreach ( vb_daftar( 'sosmed' ) as $b ) {
	$ikon = function_exists( 'block_core_social_link_get_icon' ) ? block_core_social_link_get_icon( $b['platform'] ) : '';
	printf(
		'<li><a href="%s" target="_blank" rel="noopener" aria-label="%s">%s</a></li>',
		esc_url( $b['url'] ),
		esc_attr( $nama[ $b['platform'] ] ?? $b['platform'] ),
		$ikon // phpcs:ignore -- SVG core.
	);
}
echo '</ul>';
