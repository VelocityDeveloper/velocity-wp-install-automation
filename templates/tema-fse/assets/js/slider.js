/*
 * Slider hero referensi (.vf-ref-slider): beberapa core/cover bertumpuk, satu tampil,
 * berganti otomatis + titik navigasi. Tanpa JS slide pertama saja yang tampil (CSS).
 */
(function () {
  function pasang(slider) {
    var slide = Array.prototype.filter.call(slider.children, function (el) {
      return el.classList.contains('wp-block-cover');
    });
    if (slide.length < 2 || slider.dataset.vfSiap) return;
    slider.dataset.vfSiap = '1';
    var aktif = 0;
    var jeda = null;
    var titik = document.createElement('div');
    titik.className = 'vf-ref-slider__titik';
    slide.forEach(function (s, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-label', 'Slide ' + (i + 1));
      b.addEventListener('click', function () { tampil(i); mulai(); });
      titik.appendChild(b);
    });
    slider.appendChild(titik);
    function tampil(i) {
      aktif = (i + slide.length) % slide.length;
      slide.forEach(function (s, j) { s.classList.toggle('is-aktif', j === aktif); });
      Array.prototype.forEach.call(titik.children, function (b, j) {
        b.classList.toggle('is-aktif', j === aktif);
      });
    }
    function mulai() {
      clearInterval(jeda);
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        jeda = setInterval(function () { tampil(aktif + 1); }, 5000);
      }
    }
    slider.addEventListener('mouseenter', function () { clearInterval(jeda); });
    slider.addEventListener('mouseleave', mulai);
    slider.classList.add('is-js');
    tampil(0);
    mulai();
  }
  /* Carousel logo mitra/klien (.vf-logo-geser): strip geser + tombol panah.
     Tanpa JS strip tetap bisa digeser jari/trackpad (CSS overflow-x). */
  function pasangGeser(strip) {
    if (strip.dataset.vfSiap || strip.children.length < 2) return;
    strip.dataset.vfSiap = '1';
    var bingkai = document.createElement('div');
    bingkai.className = 'vf-logo-geser__bingkai';
    strip.parentNode.insertBefore(bingkai, strip);
    bingkai.appendChild(strip);
    function tombol(arah, label, teks) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'vf-logo-geser__nav vf-logo-geser__nav--' + arah;
      b.setAttribute('aria-label', label);
      b.textContent = teks;
      b.addEventListener('click', function () {
        strip.scrollBy({ left: (arah === 'maju' ? 1 : -1) * strip.clientWidth * 0.8, behavior: 'smooth' });
      });
      bingkai.appendChild(b);
      return b;
    }
    var mundur = tombol('mundur', 'Sebelumnya', '\u2039');
    var maju = tombol('maju', 'Berikutnya', '\u203A');
    function perbarui() {
      var sisa = strip.scrollWidth - strip.clientWidth;
      // Panah yang sedang tidak bisa menggeser TETAP TAMPIL, hanya diredupkan, supaya
      // pengunjung tahu deret ini bisa digeser (permintaan user 2026-09-18).
      mati(mundur, strip.scrollLeft <= 4);
      mati(maju, sisa <= 4 || strip.scrollLeft >= sisa - 4);
    }
    function mati(tombol, ya) {
      tombol.classList.toggle('is-mati', ya);
      tombol.disabled = ya;
      tombol.setAttribute('aria-disabled', ya ? 'true' : 'false');
    }
    strip.addEventListener('scroll', perbarui);
    window.addEventListener('resize', perbarui);
    perbarui();
  }
  function semua() {
    document.querySelectorAll('.vf-ref-slider').forEach(pasang);
    document.querySelectorAll('.vf-logo-geser').forEach(pasangGeser);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', semua);
  } else {
    semua();
  }
})();
