<?php
/**
 * Plugin Name: Velocity - Halaman Berita pakai tampilan arsip
 * Description: Child theme klasik Velocity (mis. velocity-property1) memakai index.php sebagai "Home Template" tanpa home.php, sehingga Posts page (Berita) ikut tampil seperti beranda. Halaman itu diarahkan ke archive.php dan judulnya diisi di header.
 */
defined('ABSPATH') || exit;

function velocity_blog_arsip_home_template($file)
{
	if (!is_file($file)) {
		return false;
	}
	return (bool) preg_match('/Template Name:\s*Home Template/i', (string) file_get_contents($file, false, null, 0, 600));
}

add_filter('template_include', function ($template) {
	if (!is_home() || is_front_page() || !velocity_blog_arsip_home_template($template)) {
		return $template;
	}
	$arsip = locate_template(['archive.php']);
	if ($arsip && !velocity_blog_arsip_home_template($arsip)) {
		$GLOBALS['velocity_blog_arsip_aktif'] = true;
		return $arsip;
	}
	return $template;
}, 99);

// velocity_title() child theme tidak menangani is_home(): judul header kosong.
add_action('wp_footer', function () {
	if (empty($GLOBALS['velocity_blog_arsip_aktif'])) {
		return;
	}
	$judul = get_the_title((int) get_option('page_for_posts'));
	if ($judul === '') {
		return;
	}
	?>
	<script>
	(function () {
		var c = document.querySelector('.velocity-page-title .container');
		if (c && !c.textContent.trim()) {
			var h = document.createElement('h1');
			h.className = 'velocity-postheader velocity-judul';
			h.textContent = <?php echo wp_json_encode($judul); ?>;
			c.appendChild(h);
		}
	})();
	</script>
	<?php
});
