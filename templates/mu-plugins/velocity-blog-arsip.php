<?php
/**
 * Plugin Name: Velocity - Halaman Berita pakai tampilan arsip
 * Description: Child theme klasik Velocity memakai index.php sebagai tampilan beranda tanpa home.php — bertanda "Home Template" (mis. velocity-property1) atau tidak (mis. velocity-toko12, beranda katalog) — sehingga Posts page (Berita) ikut tampil seperti beranda. Halaman itu diarahkan ke archive.php dan judulnya diisi.
 */
defined('ABSPATH') || exit;

function velocity_blog_arsip_home_template($file)
{
	if (!is_file($file)) {
		return false;
	}
	return (bool) preg_match('/Template Name:\s*Home Template/i', (string) file_get_contents($file, false, null, 0, 600));
}

// Template beranda tema: bertanda Home Template, atau index.php tema itu sendiri (tema tanpa home.php).
function velocity_blog_arsip_tampilan_beranda($file)
{
	return velocity_blog_arsip_home_template($file)
		|| (basename((string) $file) === 'index.php' && in_array(wp_normalize_path(dirname((string) $file)), array(wp_normalize_path(get_stylesheet_directory()), wp_normalize_path(get_template_directory())), true));
}

add_filter('template_include', function ($template) {
	if (!is_home() || is_front_page() || !velocity_blog_arsip_tampilan_beranda($template)) {
		return $template;
	}
	$arsip = locate_template(['archive.php']);
	if ($arsip && !velocity_blog_arsip_home_template($arsip)) {
		$GLOBALS['velocity_blog_arsip_aktif'] = true;
		return $arsip;
	}
	return $template;
}, 99);

add_filter('get_the_archive_title', function ($title) {
	if (!empty($GLOBALS['velocity_blog_arsip_aktif'])) {
		$judul = get_the_title((int) get_option('page_for_posts'));
		return $judul !== '' ? $judul : $title;
	}
	return $title;
});

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
