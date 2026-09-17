/**
 * Menu HP gaya klinik: submenu di overlay tertutup dulu, dibuka lewat tombol panah.
 * Handler bawaan core/navigation dilewati (capture) supaya tidak ikut membuka/menutup.
 */
(function () {
	'use strict';
	document.addEventListener('click', function (e) {
		var tombol = e.target.closest('.wp-block-navigation__responsive-container.is-menu-open .wp-block-navigation-submenu__toggle');
		if (!tombol) {
			return;
		}
		e.preventDefault();
		e.stopImmediatePropagation();
		var item = tombol.closest('.wp-block-navigation-item.has-child');
		var buka = !item.classList.contains('vf-sub-buka');
		item.classList.toggle('vf-sub-buka', buka);
		tombol.setAttribute('aria-expanded', buka ? 'true' : 'false');
	}, true);
})();
