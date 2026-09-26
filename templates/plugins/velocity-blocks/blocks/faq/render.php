<?php
/**
 * vb/faq — akordeon <details> (tetap jalan tanpa JS). singleOpen = satu terbuka (view.js).
 * schema = cetak JSON-LD FAQPage dari isi item.
 */
$a     = $attributes;
$items = isset( $block->parsed_block['innerBlocks'] ) ? $block->parsed_block['innerBlocks'] : array();
if ( ! empty( $a['openFirst'] ) ) {
	$content = preg_replace( '/<details class="vb-faq__item/', '<details open class="vb-faq__item', $content, 1 );
}
echo '<div ' . get_block_wrapper_attributes( array( 'class' => 'vb-faq vb-faq--' . sanitize_html_class( $a['style'] ?? 'card' ), 'data-vb-single' => ! empty( $a['singleOpen'] ) ? '1' : '0' ) ) . '>'; // phpcs:ignore
echo $content; // phpcs:ignore
echo '</div>';
if ( ! empty( $a['schema'] ) && $items ) {
	$tanya = array();
	foreach ( $items as $it ) {
		$q = trim( wp_strip_all_tags( $it['attrs']['question'] ?? '' ) );
		$j = trim( wp_strip_all_tags( $it['attrs']['answer'] ?? '' ) );
		if ( $q && $j ) {
			$tanya[] = array( '@type' => 'Question', 'name' => $q, 'acceptedAnswer' => array( '@type' => 'Answer', 'text' => $j ) );
		}
	}
	if ( $tanya ) {
		echo '<script type="application/ld+json">' . wp_json_encode( array( '@context' => 'https://schema.org', '@type' => 'FAQPage', 'mainEntity' => $tanya ), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE ) . '</script>';
	}
}
