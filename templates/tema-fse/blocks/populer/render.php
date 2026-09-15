<?php

/** Daftar bernomor tulisan terpopuler. Query Loop bawaan tidak bisa mengurutkan per komentar. */

defined('ABSPATH') || exit;

$populer = new WP_Query(array(
    'post_type'           => 'post',
    'post_status'         => 'publish',
    'posts_per_page'      => 5,
    'ignore_sticky_posts' => true,
    'no_found_rows'       => true,
    'orderby'             => array('comment_count' => 'DESC', 'date' => 'DESC'),
));
if (!$populer->have_posts()) {
    return;
}
?>
<ol <?php echo get_block_wrapper_attributes(array('class' => 'vf-populer')); ?>>
	<?php foreach ($populer->posts as $tulisan) : ?>
		<li><a href="<?php echo esc_url(get_permalink($tulisan)); ?>"><?php echo esc_html(get_the_title($tulisan)); ?></a></li>
	<?php endforeach; ?>
</ol>
