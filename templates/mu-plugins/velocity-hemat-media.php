<?php
/**
 * Plugin Name: Velocity Hemat Media
 * Description: Paket hosting kecil (150 MB): tanpa ukuran turunan 1536/2048 px, foto asli diperkecil ke maks 1600 px.
 * Dipasang 2026-09-24 (cahayaratupetir.com: kuota 150 MB penuh — inti WordPress ±100 MB, satu foto artikel 10,6 MB).
 */
add_filter('intermediate_image_sizes_advanced', function ($s) { unset($s['1536x1536'], $s['2048x2048']); return $s; });
add_filter('big_image_size_threshold', function () { return 1600; });
add_filter('jpeg_quality', function () { return 80; });
add_filter('wp_editor_set_quality', function () { return 80; });
