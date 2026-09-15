<?php

/** Formulir kiriman pengunjung; logika di inc/form.php. */

defined('ABSPATH') || exit;
?>
<div <?php echo get_block_wrapper_attributes(); ?>>
	<?php echo velocity_fse_form_render(); // phpcs:ignore -- di-escape di dalam fungsi ?>
</div>
