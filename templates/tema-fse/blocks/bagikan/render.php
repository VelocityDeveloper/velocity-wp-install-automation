<?php

/**
 * Tautan bagikan artikel (Facebook, X, LinkedIn, WhatsApp, email).
 *
 * Dipakai di baris meta halaman artikel (templates/single.html). Semua tautan
 * dibuka di tab baru dan tidak memuat skrip pihak ketiga — hanya URL berbagi
 * resmi masing-masing layanan, jadi tidak ada pelacak yang ikut terpasang.
 */

defined('ABSPATH') || exit;

$id = get_the_ID();
if (!$id) {
    return;
}
$url = get_permalink($id);
$judul = get_the_title($id);
if (!$url) {
    return;
}
$u = rawurlencode($url);
$j = rawurlencode($judul);

// Ikon digambar sebagai SVG inline: tidak ada berkas tambahan yang harus dimuat.
$ikon = array(
    'facebook' => 'M13.5 9H15V6.5h-1.7c-2 0-3.3 1.2-3.3 3.3V11H8v2.5h2V21h2.6v-7.5h1.9l.4-2.5h-2.3V9.9c0-.6.2-.9.8-.9Z',
    'x' => 'M17.5 3h2.8l-6.1 7 7.2 11h-5.6l-4.4-6.4L6.3 21H3.5l6.6-7.5L3.2 3h5.7l4 5.9L17.5 3Zm-1 16h1.6L8.1 4.7H6.4L16.5 19Z',
    'linkedin' => 'M6.9 8.6H4.3V20h2.6V8.6ZM5.6 4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3ZM20 13.6c0-3-1.6-4.4-3.8-4.4-1.7 0-2.5.9-2.9 1.6V8.6H10.7c0 .7 0 11.4 0 11.4h2.6v-6.4c0-.3 0-.7.1-.9.3-.7.9-1.4 1.9-1.4 1.3 0 1.9.9 1.9 2.4V20H20v-6.4Z',
    'whatsapp' => 'M12 3.5a8.4 8.4 0 0 0-7.2 12.7L3.5 21l4.9-1.3A8.4 8.4 0 1 0 12 3.5Zm4.9 11.9c-.2.6-1.2 1.1-1.7 1.2-.4 0-1 .1-1.6-.1-.4-.1-.9-.3-1.5-.6-2.6-1.1-4.3-3.8-4.4-4-.1-.2-1-1.4-1-2.6s.6-1.8.8-2.1c.2-.2.5-.3.6-.3h.5c.2 0 .4 0 .6.4l.8 1.9c.1.1.1.3 0 .5l-.3.4-.4.4c-.1.1-.3.3-.1.6.1.3.6 1.1 1.4 1.8 1 .9 1.8 1.1 2 1.3.3.1.4.1.6-.1l.8-1c.2-.2.4-.2.6-.1l1.8.9c.3.1.4.2.5.3 0 .1 0 .5-.1 1.1Z',
    'email' => 'M4 5h16c.6 0 1 .4 1 1v12c0 .6-.4 1-1 1H4a1 1 0 0 1-1-1V6c0-.6.4-1 1-1Zm8 7.2 7-4.4V6.6l-7 4.4-7-4.4v1.2l7 4.4Z',
);
$tautan = array(
    array('facebook', 'Bagikan ke Facebook', 'https://www.facebook.com/sharer/sharer.php?u=' . $u),
    array('x', 'Bagikan ke X', 'https://twitter.com/intent/tweet?url=' . $u . '&text=' . $j),
    array('linkedin', 'Bagikan ke LinkedIn', 'https://www.linkedin.com/sharing/share-offsite/?url=' . $u),
    array('whatsapp', 'Bagikan lewat WhatsApp', 'https://wa.me/?text=' . $j . '%20' . $u),
    array('email', 'Kirim lewat email', 'mailto:?subject=' . $j . '&body=' . $u),
);
?>
<div <?php echo get_block_wrapper_attributes(array('class' => 'vf-bagikan')); ?>>
	<span class="vf-bagikan__label"><?php echo esc_html__('Bagikan', 'velocity-fse'); ?></span>
	<?php foreach ($tautan as $t) : ?>
		<a class="vf-bagikan__ikon vf-bagikan__ikon--<?php echo esc_attr($t[0]); ?>"
			href="<?php echo esc_url($t[2]); ?>"
			aria-label="<?php echo esc_attr($t[1]); ?>"
			<?php echo $t[0] === 'email' ? '' : 'target="_blank" rel="noopener nofollow"'; ?>>
			<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="<?php echo esc_attr($ikon[$t[0]]); ?>"/></svg>
		</a>
	<?php endforeach; ?>
</div>
