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
  function semua() {
    document.querySelectorAll('.vf-ref-slider').forEach(pasang);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', semua);
  } else {
    semua();
  }
})();
