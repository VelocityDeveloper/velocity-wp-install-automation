<?php

/** "© 2026 Nama Situs." — kredit "Design by Velocity Developer" ditulis di parts/footer.html. */

defined('ABSPATH') || exit;
?>
<p <?php echo get_block_wrapper_attributes(); ?>>&copy; <?php echo esc_html(wp_date('Y')); ?> <?php echo esc_html(velocity_fse_situs('nama')); ?>.</p>
