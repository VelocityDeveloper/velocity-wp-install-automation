<?php
/** Penutup header.php: template part footer blok (sudah dirender di header.php). */

defined('ABSPATH') || exit;
?>
</main>
<?php echo $GLOBALS['velocity_fse_footer_html'] ?? do_blocks('<!-- wp:template-part {"slug":"footer","tagName":"footer"} /-->'); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
</div>
<?php wp_footer(); ?>
</body>
</html>
