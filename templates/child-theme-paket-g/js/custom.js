/**
 * Interaksi kecil desain {{DOMAIN}}.
 * Tanpa pustaka tambahan: tema induk sudah memuat Bootstrap untuk menu.
 */
(function () {
  'use strict';

  // Menu HP: panel geser milik sendiri, tidak bergantung Bootstrap tema induk.
  var tombol = document.querySelector('.{{PREFIX}}-header__tombol');
  var panel = document.getElementById('{{PREFIX}}-menu');
  var header = document.getElementById('{{PREFIX}}-header');
  if (tombol && panel) {
    var setel = function (buka) {
      tombol.setAttribute('aria-expanded', buka ? 'true' : 'false');
      tombol.setAttribute('aria-label', buka ? 'Tutup menu' : 'Buka menu');
      panel.classList.toggle('is-buka', buka);
      document.body.classList.toggle('{{PREFIX}}-menu-terbuka', buka);
    };
    tombol.addEventListener('click', function () {
      setel(tombol.getAttribute('aria-expanded') !== 'true');
    });
    // Menutup sendiri setelah memilih menu atau menekan Esc.
    panel.addEventListener('click', function (e) {
      if (e.target.closest('a')) { setel(false); }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { setel(false); }
    });
    window.addEventListener('resize', function () {
      if (window.innerWidth >= 992) { setel(false); }
    });
  }

  // Header mengecil setelah halaman digulir, supaya isi lebih lega di HP.
  if (header) {
    var gulir = function () {
      header.classList.toggle('is-gulir', window.pageYOffset > 24);
    };
    gulir();
    window.addEventListener('scroll', gulir, { passive: true });
  }

  // Tautan #pemesanan dari hero/menu: geser halus dan hitung tinggi header lengket.
  document.addEventListener('click', function (e) {
    var tautan = e.target.closest('a[href^="#"]');
    if (!tautan) { return; }
    var id = tautan.getAttribute('href');
    if (id.length < 2) { return; }
    var target = document.querySelector(id);
    if (!target) { return; }
    e.preventDefault();
    var nav = document.getElementById('{{PREFIX}}-header');
    var offset = nav ? nav.offsetHeight : 0;
    var atas = target.getBoundingClientRect().top + window.pageYOffset - offset;
    window.scrollTo({ top: atas, behavior: 'smooth' });
    if (history.replaceState) { history.replaceState(null, '', id); }
  });

  // Setelah form dikirim, bawa pengunjung ke notifikasinya.
  if (window.location.search.indexOf('pesan=') !== -1) {
    var notif = document.querySelector('.{{PREFIX}}-notif');
    if (notif) {
      notif.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }
})();
