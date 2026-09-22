<?php

/** Formulir kiriman pengunjung; logika di inc/form.php. */

defined('ABSPATH') || exit;
?>
<div <?php echo get_block_wrapper_attributes(); ?>>
	<?php
	// Form Contact Form 7 bawaan situs (inc/cf7.php) menggantikan form tema bila ada.
	$cf7 = velocity_fse_cf7_shortcode();
	echo $cf7 !== '' ? $cf7 : velocity_fse_form_render(); // phpcs:ignore -- di-escape di dalam fungsi
	?>
</div>
