<?php
/**
 * Carousel kategori VD Store versi slide per ubin + berulang (user 2026-09-17, yukpergimancing.com).
 * Dipakai lewat filter wp_store_locate_template di inc/referensi.php. Variabel dari
 * Shortcode::render_taxonomies_carousel(): $pages (item dikelompokkan), $columns, $image_size.
 */

defined('ABSPATH') || exit;

$items = array();
foreach ((array) ($pages ?? array()) as $page) {
    foreach ((array) $page as $item) {
        $items[] = $item;
    }
}
if (!$items) {
    return;
}
$kolom = max(1, (int) ($columns ?? 4));
$geser = count($items) > $kolom;
?>
<section class="wps-taxonomy-carousel vf-kategori-slide" data-wps-carousel="1"
    data-cell-align="left"
    data-contain="<?php echo $geser ? 'false' : 'true'; ?>"
    data-wrap-around="<?php echo $geser ? 'true' : 'false'; ?>"
    data-page-dots="false"
    data-prev-next-buttons="<?php echo $geser ? 'true' : 'false'; ?>"
    data-lazy-load="0"
    data-autoplay="0"
    data-pause-on-hover="true"
    data-draggable="<?php echo $geser ? 'true' : 'false'; ?>"
    data-group-cells="0"
    style="--wps-taxonomy-columns: <?php echo (int) $kolom; ?>;">
    <div class="main-carousel">
        <?php foreach ($items as $item) : ?>
            <div class="carousel-cell vf-kategori-slide__sel">
                <a class="wps-taxonomy-carousel__item" href="<?php echo esc_url($item['url']); ?>">
                    <span class="wps-taxonomy-carousel__image">
                        <?php if (!empty($item['image_id'])) : ?>
                            <?php echo wp_get_attachment_image((int) $item['image_id'], $image_size ?? 'large', false, array(
                                'class' => 'wps-taxonomy-carousel__image-file',
                                'loading' => 'lazy',
                                'decoding' => 'async',
                                'alt' => $item['name'],
                            )); // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>
                        <?php else : ?>
                            <span class="wps-taxonomy-carousel__placeholder" aria-hidden="true"><?php echo esc_html($item['initial']); ?></span>
                        <?php endif; ?>
                    </span>
                    <span class="wps-taxonomy-carousel__name"><?php echo esc_html($item['name']); ?></span>
                </a>
            </div>
        <?php endforeach; ?>
    </div>
</section>
