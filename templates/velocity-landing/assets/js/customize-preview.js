/**
 * Pratinjau Customizer: warna & efek cahaya berubah langsung tanpa memuat ulang.
 */
(function (api) {
	var warna = ['latar', 'teks', 'utama', 'aksen', 'sorot', 'cahaya', 'footer'];
	warna.forEach(function (k) {
		api('vlp_umum_warna_' + k, function (setting) {
			setting.bind(function (nilai) {
				document.documentElement.style.setProperty('--vlp-' + k, nilai);
			});
		});
	});
	api('vlp_umum_efek_cahaya', function (setting) {
		setting.bind(function (nilai) {
			document.body.classList.toggle('vlp-tanpa-cahaya', !nilai);
		});
	});
})(wp.customize);
