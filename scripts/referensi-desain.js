#!/usr/bin/env node
/*
 * Ukur desain halaman depan situs referensi klien (Playwright) -> JSON.
 *
 * Keputusan user 2026-09-15: untuk Paket G / paket custom, desain referensi di
 * FORM ISIAN adalah ACUAN UTAMA — tata letak & gaya mengikuti referensi (urutan
 * dan jenis seksi, header, hero, kartu, latar seksi, font, bentuk tombol), konten
 * tetap milik klien. Screenshot saja tidak cukup (dulu hanya terang-gelap hero
 * yang diukur), jadi yang dibaca adalah DOM terender: kotak, warna, font.
 *
 * Permintaan user 2026-09-17: pembacaan diperdalam — header (baris, logo, menu,
 * ajakan, isi topbar), footer (isi tiap kolom, baris hak cipta), tiap seksi (ruang,
 * label kecil di atas judul, sisi foto), banner judul halaman dalam, dan tautan menu
 * supaya halaman dalam referensi ikut diukur. Pengukur yang sama dipakai audit
 * kemiripan (scripts/fse-audit-kemiripan) untuk membaca situs hasil build, jadi
 * keduanya dibandingkan dengan ukuran yang setara.
 *
 * Pemakaian: referensi-desain.js <url> <keluaran.json> [potret.png|-] [<url> <keluaran.json> <potret.png|-> ...]
 *   Beberapa halaman sekaligus memakai satu browser. VELOCITY_UKUR_COOKIE = JSON daftar
 *   cookie Playwright (audit situs yang sedang maintenance); admin bar disembunyikan.
 * Modul dari VELOCITY_BLOCKVAL (bawaan /var/lib/velocity/tools/blockval).
 * Kode keluar: 0 halaman pertama berhasil, 1 gagal, 3 playwright-core belum terpasang.
 * Klasifikasi seksi (hero/layanan/...) dilakukan scripts/referensi_desain.py.
 */
const fs = require('fs');
const path = require('path');

const akar = process.env.VELOCITY_BLOCKVAL || '/var/lib/velocity/tools/blockval';
const modul = path.join(akar, 'node_modules', 'playwright-core');
if (!fs.existsSync(modul)) {
  console.log('referensi:playwright_tidak_ada');
  process.exit(3);
}
const { chromium } = require(modul);
const argumen = process.argv.slice(2);
const tugas = [];
for (let i = 0; i < argumen.length; i += 3) {
  const [u, k, g] = argumen.slice(i, i + 3);
  if (u && k) tugas.push({ url: u, keluaran: k, potret: g && g !== '-' ? g : '' });
}
if (!tugas.length) {
  console.log('usage: referensi-desain.js <url> <keluaran.json> [potret.png|-] [...]');
  process.exit(1);
}
const chrome = process.env.VELOCITY_CHROME
  || fs.readdirSync('/root/.cache/ms-playwright').filter((d) => d.startsWith('chromium-')).sort().reverse()
    .map((d) => `/root/.cache/ms-playwright/${d}/chrome-linux64/chrome`).find((p) => fs.existsSync(p));

// Dijalankan di dalam halaman. Tidak boleh memakai apa pun dari luar fungsi ini.
function ukur() {
  const vw = document.documentElement.clientWidth;
  // Warna CSS modern (oklab/oklch/color()) tidak cocok dengan pola rgb(): tombol
  // "Contact" northseaaconsulting.com berwarna oklab sehingga headernya terbaca tanpa
  // tombol ajakan (2026-09-18). Kanvas menerjemahkan sintaks apa pun ke sRGB.
  let kanvas = null;
  const lewatKanvas = (s) => {
    try {
      if (!kanvas) { kanvas = document.createElement('canvas').getContext('2d', { willReadFrequently: true }); }
      kanvas.clearRect(0, 0, 1, 1);
      kanvas.fillStyle = '#000';
      kanvas.fillStyle = s;
      if (kanvas.fillStyle === '#000' && !/^#0{3,6}$|black/i.test(String(s).trim())) return null;
      kanvas.fillRect(0, 0, 1, 1);
      const d = kanvas.getImageData(0, 0, 1, 1).data;
      return [d[0], d[1], d[2], d[3] / 255];
    } catch (e) { return null; }
  };
  const rgba = (s) => {
    const m = String(s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/);
    if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]];
    const t = String(s || '').trim();
    if (!t || t === 'none' || t === 'transparent') return null;
    return /^(oklab|oklch|lab|lch|color|hwb|hsl|#)/i.test(t) ? lewatKanvas(t) : null;
  };
  const hex = (c) => '#' + c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
  const lum = (c) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  // Tautan menu di dalam `akar`: wadah nav/…menu… harus berada DI DALAM akar. Selektor
  // akar.querySelectorAll('[class*="menu"] a') ikut mencocokkan leluhur di luar akar — <body>
  // tema velocity-fse berkelas vf-menu-tengah/vf-menu-kapital, sehingga logo, kotak cari & email
  // header terhitung menu dan audit header situs FSE selalu salah (ptutamateknikpersada.com 2026-09-18).
  const tautanMenu = (akar, sel = 'a') => [...akar.querySelectorAll(sel)].filter((a) => {
    const wadah = a.closest('nav, [class*="menu" i]');
    return !!wadah && (wadah === akar || akar.contains(wadah));
  });
  const tampak = (el) => {
    const r = el.getBoundingClientRect();
    const g = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && g.display !== 'none' && g.visibility !== 'hidden' && +g.opacity > 0.05;
  };
  const kotak = (el) => {
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) };
  };
  // Warna latar sebuah elemen: background-color, atau warna pertama gradien
  // (hero .vf-hero situs FSE berlatar linear-gradient, background-color transparan).
  const warnaLatar = (e) => {
    const g = getComputedStyle(e);
    const c = rgba(g.backgroundColor);
    if (c && c[3] > 0.5) return c;
    if (/gradient\(/.test(g.backgroundImage)) {
      const w = rgba((g.backgroundImage.match(/rgba?\([^)]*\)/) || [''])[0]);
      if (w && w[3] > 0.5) return w;
    }
    return null;
  };
  // Warna latar efektif: naik ke induk sampai ketemu latar tidak transparan.
  const latar = (el) => {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const c = warnaLatar(e);
      if (c) return c;
    }
    return [255, 255, 255, 1];
  };
  // Foto/video menutupi sebagian besar kotak (latar berfoto / hero slider).
  const berfoto = (el) => {
    const r = el.getBoundingClientRect();
    const luas = r.width * r.height;
    if (/url\(/.test(getComputedStyle(el).backgroundImage)) return true;
    for (const m of el.querySelectorAll('img,video,picture,[style*="background-image"]')) {
      if (!tampak(m)) continue;
      const q = m.getBoundingClientRect();
      const bg = m.matches('[style*="background-image"]') ? /url\(/.test(getComputedStyle(m).backgroundImage) : true;
      if (bg && q.width * q.height >= luas * 0.5) return true;
    }
    // Video latar dari YouTube/Vimeo dipasang sebagai <iframe> (Beaver Builder
    // .fl-row-bg-video): hero northseaaconsulting.com karenanya terbaca "terang".
    // Hanya iframe pemutar video yang dihitung — peta/lampiran tidak.
    for (const f of el.querySelectorAll('iframe')) {
      if (!tampak(f)) continue;
      const src = (f.getAttribute('src') || '') + ' ' + (f.closest('[class]') || { className: '' }).className;
      if (!/youtube|youtu\.be|vimeo|dailymotion|bg-video|video-bg|background-video/i.test(String(src))) continue;
      const q = f.getBoundingClientRect();
      if (q.width * q.height >= luas * 0.5) return true;
    }
    // Foto latar yang dipasang lewat KELAS css (bukan atribut style) tidak tertangkap
    // pemindaian di atas: hero northseaaconsulting.com terbaca "terang" padahal banner
    // berfoto bertulisan putih (2026-09-18).
    for (const d of [...el.querySelectorAll('*')].slice(0, 400)) {
      if (!tampak(d) || !/url\(/.test(getComputedStyle(d).backgroundImage)) continue;
      const q = d.getBoundingClientRect();
      if (q.width * q.height >= luas * 0.5) return true;
    }
    // Page builder (Beaver Builder: .fl-row > .fl-row-content-wrap) memasang foto latar
    // di BARIS pembungkus, sedangkan yang terukur sebagai seksi adalah kotak isinya.
    // Hanya induk sebesar seksi itu sendiri yang dianggap — bukan latar halaman.
    let induk = el.parentElement;
    for (let i = 0; i < 3 && induk && induk !== document.body && induk !== document.documentElement; i++) {
      const q = induk.getBoundingClientRect();
      if (q.height > r.height * 1.6) break;
      if (/url\(/.test(getComputedStyle(induk).backgroundImage)) return true;
      induk = induk.parentElement;
    }
    return false;
  };
  const teks = (el) => (el.innerText || '').replace(/\s+/g, ' ').trim();
  // Latar yang TERLIHAT pada kotak: header blok WordPress transparan dan warnanya ada
  // di grup di dalamnya (.vf-header), jadi naik ke induk saja membaca latar body.
  const latarKotak = (el, kecuali) => {
    const k = kotak(el);
    const sendiri = warnaLatar(el);
    if (sendiri) return sendiri;
    let pilih = null; let luasPilih = 0;
    for (const d of [...el.querySelectorAll('*')].slice(0, 400)) {
      if (kecuali && (d === kecuali || kecuali.contains(d) || d.contains(kecuali))) continue;
      const c = warnaLatar(d);
      if (!c || !tampak(d)) continue;
      const q = kotak(d);
      const luas = q.w * q.h;
      if (luas >= k.w * k.h * 0.45 && luas > luasPilih) { pilih = c; luasPilih = luas; }
    }
    return pilih || latar(el);
  };
  // Tautan/teks yang nyaris tak terlihat di atas latarnya (kontras < 2,2) — dicatat
  // untuk audit: tautan biru tua di footer navy lolos semua pemeriksaan lain.
  const luminRel = (c) => {
    const [r, g, b] = c.slice(0, 3).map((v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const kontrasRendah = (el) => [...el.querySelectorAll('a, p, li, span, h1, h2, h3, h4')].slice(0, 500).filter((e) => {
    if (!tampak(e) || !teks(e) || [...e.children].some((c) => teks(c))) return false;
    const w = rgba(getComputedStyle(e).color);
    if (!w || w[3] < 0.5) return false;
    let bgc = null;
    for (let x = e; x && x.nodeType === 1; x = x.parentElement) {
      if (/url\(/.test(getComputedStyle(x).backgroundImage) || x.matches('.wp-block-cover, [class*="slider" i]')) return false;
      const c = warnaLatar(x);
      if (c) { bgc = c; break; }
    }
    bgc = bgc || [255, 255, 255, 1];
    const [a, b] = [luminRel(w), luminRel(bgc)].sort((m, n) => n - m);
    return (a + 0.05) / (b + 0.05) < 2.2;
  }).map((e) => teks(e).slice(0, 30)).slice(0, 8);
  const host = location.hostname.replace(/^www\./, '');
  const SOSMED = /facebook\.com|instagram\.com|twitter\.com|\/\/(www\.)?x\.com|youtube\.com|tiktok\.com|linkedin\.com|pinterest\./i;
  // Isi baris info (topbar/kolom footer): apa saja yang tampil, bukan teksnya.
  const isiInfo = (el) => {
    const t = teks(el);
    const a = [...el.querySelectorAll('a[href]')].map((x) => x.href || '');
    const isi = [];
    if (a.some((h) => /^tel:|wa\.me|whatsapp/i.test(h)) || /(\+62|\b0)\d[\d\s-]{7,}/.test(t)) isi.push('telepon');
    if (a.some((h) => /^mailto:/i.test(h)) || /[\w.-]+@[\w-]+\.[\w.]+/.test(t)) isi.push('email');
    if (a.some((h) => SOSMED.test(h)) || el.querySelector('[class*="social" i], [class*="sosmed" i]')) isi.push('sosmed');
    if (/\b(jl\.?|jalan|street|road|ruko|kec\.|kab\.|kota)\s/i.test(t)) isi.push('alamat');
    if (/\b\d{1,2}[:.]\d{2}\b|senin|monday|jam (buka|kerja)/i.test(t)) isi.push('jam');
    return isi;
  };

  // ---- header & topbar ----
  const kandidatHeader = [...document.querySelectorAll('header, [class*="header" i], nav')]
    .filter((e) => tampak(e) && kotak(e).y < 260 && kotak(e).w >= vw * 0.8 && kotak(e).h >= 40 && kotak(e).h < 260);
  const header = kandidatHeader.sort((a, b) => kotak(b).h - kotak(a).h)[0] || null;
  let infoHeader = null;
  if (header) {
    const kh = kotak(header);
    const g = getComputedStyle(header);
    const logo = [...header.querySelectorAll('img, svg, [class*="logo" i]')].filter(tampak)
      .map(kotak).sort((a, b) => a.x - b.x)[0];
    const tautan = tautanMenu(header).filter(tampak).map(kotak);
    const tengahMenu = tautan.length ? tautan.reduce((s, t) => s + t.x + t.w / 2, 0) / tautan.length : 0;
    // Ikon keranjang & lencana jumlahnya (kreditmotor.rmg.asia) bukan tombol ajakan.
    const RE_KERANJANG = /cart|keranjang|basket|minicart|badge|count/i;
    const bukanTombol = (a) => {
      const q = kotak(a);
      return q.w < 60 || q.h < 24 || RE_KERANJANG.test(`${a.className} ${a.getAttribute('href') || ''} ${a.parentElement ? a.parentElement.className : ''}`);
    };
    const bg = latarKotak(header);
    const calonTombol = [...header.querySelectorAll('a, button')].filter((a) => tampak(a) && !bukanTombol(a)).filter((a) => {
      // warnaLatar (bukan backgroundColor mentah) supaya tombol bergradien ikut terbaca:
      // pil "Contact" di northseaaconsulting.com transparan menurut backgroundColor,
      // sehingga headernya terbaca tanpa tombol ajakan (2026-09-18).
      const c = warnaLatar(a);
      return c && Math.abs(lum(c) - lum(bg)) > 40 && kotak(a).w < 320;
    });
    const tombol = calonTombol.length > 0;
    const barisMenu = new Set(tautan.map((t) => Math.round(t.y / 12))).size;
    const menuEl = tautanMenu(header).find(tampak) || null;
    const gMenu = menuEl ? getComputedStyle(menuEl) : null;
    const atasMenu = tautan.length ? Math.min(...tautan.map((t) => t.y)) : 0;
    const urutX = tautan.filter((t) => Math.abs(t.y - atasMenu) < 12).sort((a, b) => a.x - b.x);
    const jarak = urutX.slice(1).map((t, i) => t.x - (urutX[i].x + urutX[i].w)).filter((j) => j >= 0 && j < 200);
    const ajakanEl = calonTombol[0];
    // Warna teks menu: berwarna (oranye/biru merek) vs netral (hitam/abu/putih).
    const warnaMenu = gMenu ? rgba(gMenu.color) : null;
    // Slate gelap (#314059, selisih 40) masih netral; oranye/biru merek jauh di atas 60.
    const menuBerwarna = !!warnaMenu && Math.max(...warnaMenu.slice(0, 3)) - Math.min(...warnaMenu.slice(0, 3)) >= 60
      && lum(warnaMenu) > 60;
    const keranjang = [...header.querySelectorAll('a[href], [class]')].slice(0, 400).some((e) => tampak(e)
      && /cart|keranjang|basket/i.test(`${typeof e.className === 'string' ? e.className : ''} ${e.getAttribute('href') || ''}`));
    const garisBawah = [header, ...header.querySelectorAll('*')].slice(0, 40).some((e) => {
      const g2 = getComputedStyle(e);
      return kotak(e).w >= kh.w * 0.8 && (parseFloat(g2.borderBottomWidth) > 0 || g2.boxShadow !== 'none');
    });
    infoHeader = {
      tinggi: kh.h,
      latar: hex(bg),
      gelap: lum(bg) < 110,
      // Logo di baris sendiri di atas menu = header dua baris.
      baris: logo && tautan.length && atasMenu >= logo.y + logo.h - 4 ? 2 : 1,
      baris_menu: barisMenu,
      logo_tinggi: logo ? logo.h : 0,
      logo_lebar: logo ? logo.w : 0,
      menu_ukuran: gMenu ? parseFloat(gMenu.fontSize) : 0,
      menu_tebal: gMenu ? (+gMenu.fontWeight || 400) : 0,
      menu_jarak: jarak.length ? Math.round(jarak.reduce((a, b) => a + b, 0) / jarak.length) : 0,
      cari: [...header.querySelectorAll('input[type="search"], [class*="search" i]')].some(tampak),
      dropdown: !!header.querySelector('li li, .sub-menu, [class*="submenu" i], [class*="dropdown" i]'),
      ajakan: ajakanEl ? {
        teks: teks(ajakanEl).slice(0, 40),
        radius: parseFloat(getComputedStyle(ajakanEl).borderTopLeftRadius) || 0,
        latar: hex(rgba(getComputedStyle(ajakanEl).backgroundColor)),
      } : null,
      garis_bawah: garisBawah,
      menu_berwarna: menuBerwarna,
      menu_warna: warnaMenu ? hex(warnaMenu) : '',
      keranjang,
      kontras_rendah: kontrasRendah(header),
      transparan_di_atas_hero: (rgba(g.backgroundColor) || [0, 0, 0, 0])[3] < 0.1 && kh.y < 10,
      // Header MELAYANG transparan di atas hero lalu berubah jadi bar berlatar saat digulir
      // (habercafeandresto.co.id 2026-09-20): posisinya fixed/absolute sejak di puncak halaman
      // dan latarnya sendiri tembus pandang, jadi hero terlihat sampai ke tepi atas layar.
      transparan: ['fixed', 'absolute'].includes(g.position)
        && (rgba(g.backgroundColor) || [0, 0, 0, 0])[3] < 0.2 && kh.y < 10,
      // Bar header melayang (kontraktorhijau.com): pembungkus transparan berisi kotak berlatar
      // yang lebih sempit dari layar, bersudut, dan berjarak dari tepi atas.
      melayang: (() => {
        if ((rgba(g.backgroundColor) || [0, 0, 0, 0])[3] >= 0.1) {
          // Header terpilih bisa jadi bar itu sendiri (lebih sempit dari layar & berjarak dari atas).
          return kh.w <= vw * 0.97 && kh.y >= 4 && kh.h <= 140 ? { lebar: Math.round((kh.w / vw) * 100), atas: kh.y, tinggi: kh.h,
            radius: parseFloat(g.borderTopLeftRadius) || 0, latar: hex(rgba(g.backgroundColor)), bayangan: g.boxShadow !== 'none' } : null;
        }
        const bar = [...header.querySelectorAll('*')].slice(0, 200).find((e) => {
          const q = kotak(e);
          const ge = getComputedStyle(e);
          return tampak(e) && (rgba(ge.backgroundColor) || [0, 0, 0, 0])[3] > 0.8 && q.w >= vw * 0.6 && q.w <= vw * 0.97
            && q.h >= 40 && q.h <= 140 && e.querySelector('a');
        });
        if (!bar) return null;
        const q = kotak(bar);
        const gb = getComputedStyle(bar);
        return { lebar: Math.round((q.w / vw) * 100), atas: q.y, tinggi: q.h, radius: parseFloat(gb.borderTopLeftRadius) || 0,
                 latar: hex(rgba(gb.backgroundColor)), bayangan: gb.boxShadow !== 'none' };
      })(),
      lengket: ['fixed', 'sticky'].includes(g.position)
        || [...header.querySelectorAll('*')].slice(0, 30).some((e) => ['fixed', 'sticky'].includes(getComputedStyle(e).position)),
      logo_posisi: logo ? (Math.abs(logo.x + logo.w / 2 - vw / 2) < vw * 0.12 ? 'tengah' : 'kiri') : '',
      menu_posisi: !tautan.length ? '' : tengahMenu > vw * 0.6 ? 'kanan' : tengahMenu > vw * 0.4 ? 'tengah' : 'kiri',
      jumlah_menu: tautan.length,
      tombol_ajakan: tombol,
      huruf_menu_kapital: tautan.length ? getComputedStyle(tautanMenu(header).find(tampak) || header).textTransform === 'uppercase' : false,
    };
  }
  // Topbar: baris tipis selebar layar di puncak halaman. Page builder (Beaver Builder,
  // kreditmotor.rmg.asia 2026-09-17) menaruhnya DI DALAM <header>, di atas baris logo —
  // dulu semua isi header dikecualikan sehingga topbar hitamnya tidak terbaca.
  const topbar = [...document.querySelectorAll('body *')].find((e) => {
    if (!tampak(e) || (header && e.contains(header))) return false;
    const k = kotak(e);
    if (header && header.contains(e)) {
      const kh = kotak(header);
      if (e === header || k.y > kh.y + 5 || k.y + k.h > kh.y + kh.h - 30) return false;
    }
    return k.y < 10 && k.w >= vw * 0.9 && k.h >= 20 && k.h <= 56 && teks(e).length > 5;
  });
  // Latar topbar: elemen berlatar di dalamnya (baris pembungkus sering transparan).
  if (infoHeader && topbar && header.contains(topbar)) {
    const bgH = latarKotak(header, topbar);
    infoHeader.tinggi = Math.max(0, infoHeader.tinggi - kotak(topbar).h);
    infoHeader.latar = hex(bgH);
    infoHeader.gelap = lum(bgH) < 110;
    infoHeader.topbar_di_dalam = true;
  }
  if (infoHeader) {
    const isiH = isiInfo(header);
    infoHeader.isi = topbar && header.contains(topbar) ? isiH.filter((x) => !isiInfo(topbar).includes(x)) : isiH;
  }
  const latarTopbar = topbar
    ? ([topbar, ...topbar.querySelectorAll('*')].map((e) => rgba(getComputedStyle(e).backgroundColor))
      .find((c) => c && c[3] > 0.5) || latar(topbar))
    : null;

  // ---- seksi: pecah blok selebar layar yang bertumpuk vertikal ----
  // Footer = blok selebar layar yang menempel di dasar halaman. Kelas "footer" juga
  // dipakai pembungkus seluruh halaman (erhaeschemical.com: 2868px), yang dulu
  // membuat batas bawah seksi berada di atas dan semua seksi terbuang.
  const tinggiDok = document.documentElement.scrollHeight;
  const footer = [...document.querySelectorAll('footer, [class*="footer" i]')]
    .filter((e) => {
      if (!tampak(e)) return false;
      const k = kotak(e);
      return k.w >= vw * 0.8 && k.h >= 60 && k.h <= Math.min(1500, tinggiDok * 0.5) && k.y + k.h >= tinggiDok - 300;
    })
    .sort((a, b) => (b.tagName === 'FOOTER') - (a.tagName === 'FOOTER') || kotak(a).y - kotak(b).y)[0] || null;
  const batasAtas = header ? kotak(header).y + kotak(header).h - 5 : 0;
  const batasBawah = footer ? kotak(footer).y + 5 : document.documentElement.scrollHeight;
  const seksi = [];
  const pecah = (el, dalam) => {
    const k = kotak(el);
    if (dalam > 14 || k.h < 60) return;
    if (header && (el === header || header.contains(el))) return;
    if (footer && (el === footer || footer.contains(el))) return;
    // Header/footer & elemen fixed (header lengket Beaver Builder yang tercatat di tengah
    // halaman, tasseminarpalupi.com 2026-09-17) bukan lapisan seksi: tanpa pengecualian ini
    // pembungkus #page dianggap "saling menimpa" dan seluruh halaman jadi satu seksi.
    const lebar = [...el.children].filter((c) => tampak(c) && kotak(c).w >= vw * 0.8 && kotak(c).h >= 40);
    const bukanSeksi = (c) => (header && (c === header || (c.contains(header) && kotak(c).h < 300)))
      || (footer && c === footer) || ['fixed', 'sticky'].includes(getComputedStyle(c).position);
    const anak = lebar.filter((c) => !bukanSeksi(c));
    // Tinggi pembanding tanpa header/footer yang dikecualikan (body = header + main + footer).
    const kh = { ...k, h: Math.max(1, k.h - lebar.filter(bukanSeksi).reduce((t, c) => t + kotak(c).h, 0)) };
    const tinggiAnak = anak.reduce((s, c) => s + kotak(c).h, 0);
    // Anak yang saling menimpa (core/cover: foto latar + lapisan warna + isi, slider)
    // adalah lapisan satu seksi, bukan seksi yang bertumpuk.
    const urut = anak.map(kotak).sort((a, b) => a.y - b.y);
    const menimpa = urut.slice(1).some((q, i) => q.y < urut[i].y + urut[i].h - 20);
    const bertumpuk = anak.length >= 2 && tinggiAnak >= kh.h * 0.6 && !menimpa;
    if (bertumpuk || (anak.length === 1 && kotak(anak[0]).h >= kh.h * 0.9
        && getComputedStyle(anak[0]).position !== 'absolute')) {
      for (const c of anak) pecah(c, dalam + 1);
      // Isi yang tidak selebar layar di antara anak (mis. judul lepas) diabaikan.
      return;
    }
    if (k.y + k.h <= batasAtas || k.y >= batasBawah || k.h < 100) {
      if (!(header && k.y < batasAtas && k.h >= 300)) return; // hero di bawah header transparan tetap dihitung
    }
    seksi.push(el);
  };
  pecah(document.body, 0);

  const judulGaya = (h) => {
    const g = getComputedStyle(h);
    return { font: g.fontFamily.split(',')[0].replace(/["']/g, '').trim(), ukuran: parseFloat(g.fontSize),
             tebal: +g.fontWeight || 400, kapital: g.textTransform === 'uppercase', rata: g.textAlign };
  };
  // Kelompok kartu: saudara berukuran mirip dalam satu baris.
  const grupKartu = (el) => {
    let terbaik = { n: 0, kolom: 0, radius: 0, bayangan: false, foto: 0, ikon: 0 };
    for (const induk of [el, ...el.querySelectorAll('*')].slice(0, 1500)) {
      const anak = [...induk.children].filter((c) => tampak(c) && kotak(c).w >= 120 && kotak(c).w < vw * 0.6 && kotak(c).h >= 60);
      if (anak.length < 2) continue;
      const lebar = anak.map((c) => kotak(c).w);
      const rata = lebar.reduce((a, b) => a + b, 0) / lebar.length;
      if (lebar.some((w) => Math.abs(w - rata) > rata * 0.15)) continue;
      const baris = new Set(anak.map((c) => Math.round(kotak(c).y / 30)));
      const kolom = Math.round(anak.length / baris.size);
      if (anak.length > terbaik.n && kolom >= 2) {
        // Gaya kartu bisa berada di elemen dalam yang menutupi hampir seluruh kolom
        // (Divi: .et_pb_column polos berisi .et_pb_blurb berbingkai & bersudut).
        const kk = kotak(anak[0]);
        const gayaEl = [anak[0], ...anak[0].querySelectorAll('*')].slice(0, 25).find((e) => {
          const q = kotak(e);
          const ge = getComputedStyle(e);
          return q.w >= kk.w * 0.9 && q.h >= kk.h * 0.8 && (parseFloat(ge.borderTopWidth) > 0
            || parseFloat(ge.borderTopLeftRadius) > 0 || ge.boxShadow !== 'none'
            || ((rgba(ge.backgroundColor) || [0, 0, 0, 0])[3] > 0.5));
        }) || anak[0];
        const g = getComputedStyle(gayaEl);
        const bg = rgba(g.backgroundColor);
        // Kartu-foto (pembungkus tanpa sudut, foto selebar kartu yang membulat).
        const fotoPenuh = [...anak[0].querySelectorAll('img')].find((i) => tampak(i) && kotak(i).w >= kotak(anak[0]).w * 0.8);
        const gf = fotoPenuh ? getComputedStyle(fotoPenuh) : null;
        terbaik = {
          n: anak.length, kolom,
          radius: parseFloat(g.borderTopLeftRadius) || (gf ? parseFloat(gf.borderTopLeftRadius) || 0 : 0),
          bayangan: g.boxShadow !== 'none' || (gf ? gf.boxShadow !== 'none' : false),
          berbingkai: (bg && bg[3] > 0.5 && Math.abs(lum(bg) - lum(latar(induk))) > 8) || parseFloat(g.borderTopWidth) > 0,
          foto: anak.filter((c) => [...c.querySelectorAll('img')].some((i) => tampak(i) && kotak(i).w >= 100)).length,
          ikon: anak.filter((c) => [...c.querySelectorAll('svg, i[class], img')].some((i) => tampak(i) && kotak(i).w < 100 && kotak(i).w >= 16)).length,
          rata_teks: getComputedStyle(anak[0]).textAlign,
          // Kartu yang disorot (paket tengah berlatar warna), tombol di tiap kartu, keterangan foto.
          sorot: (() => {
            const lat = anak.map((c) => {
              const e = [c, ...c.querySelectorAll('*')].slice(0, 25).find((x) => kotak(x).w >= kotak(c).w * 0.9
                && ((rgba(getComputedStyle(x).backgroundColor) || [0, 0, 0, 0])[3] > 0.5));
              return e ? lum(rgba(getComputedStyle(e).backgroundColor)) : 255;
            });
            const beda = lat.map((l, i) => lat.filter((m, j) => j !== i && Math.abs(m - l) > 60).length === lat.length - 1);
            return beda.filter(Boolean).length === 1 ? beda.indexOf(true) : -1;
          })(),
          tombol: anak.filter((c) => [...c.querySelectorAll('a, button')].some((a) => tampak(a) && teks(a)
            && (parseFloat(getComputedStyle(a).paddingTop) >= 4 || ((rgba(getComputedStyle(a).backgroundColor) || [0, 0, 0, 0])[3] > 0.5)))).length,
          keterangan: anak.filter((c) => {
            const im = [...c.querySelectorAll('img')].find((i) => tampak(i) && kotak(i).w >= 100);
            if (!im) return false;
            const bawah = [...c.querySelectorAll('figcaption, h3, h4, p, a')].find((x) => tampak(x) && teks(x) && kotak(x).y >= kotak(im).y + kotak(im).h - 4);
            return !!bawah && teks(c).split(' ').length <= 20;
          }).length,
          border: parseFloat(g.borderTopWidth) || 0,
          border_warna: parseFloat(g.borderTopWidth) ? hex(rgba(g.borderTopColor) || [0, 0, 0]) : '',
          padding: Math.round(parseFloat(g.paddingTop) || 0),
          jarak: anak.length >= 2 ? Math.max(0, Math.round(kotak(anak[1]).x - (kotak(anak[0]).x + kotak(anak[0]).w))) : 0,
        };
      }
    }
    return terbaik;
  };

  const hasilSeksi = seksi.slice(0, 40).map((el, i) => {
    const k = kotak(el);
    const judul = [...el.querySelectorAll('h1,h2,h3,h4')].filter(tampak);
    const utama = judul.sort((a, b) => parseFloat(getComputedStyle(b).fontSize) - parseFloat(getComputedStyle(a).fontSize))[0];
    const foto = [...el.querySelectorAll('img')].filter((m) => tampak(m) && kotak(m).w >= 100);
    const kataTeks = teks(el).split(' ').length;
    const angka = [...el.querySelectorAll('*')].filter((e) => e.children.length === 0 && tampak(e)
      && /^[\d.,+%]{1,8}\+?$/.test(teks(e)) && parseFloat(getComputedStyle(e).fontSize) >= 26).length;
    const tombol = [...el.querySelectorAll('a,button')].filter((a) => {
      if (!tampak(a)) return false;
      const c = rgba(getComputedStyle(a).backgroundColor);
      return (c && c[3] > 0.5) || parseFloat(getComputedStyle(a).borderTopWidth) > 0;
    });
    const bl = latar(el);
    const fotoLatar = berfoto(el);
    // Kolom isi utama: dua blok berdampingan (teks | foto) dalam seksi.
    const berdampingan = [...el.querySelectorAll('*')].slice(0, 800).some((e) => {
      const a = [...e.children].filter((c) => tampak(c) && kotak(c).w >= vw * 0.25 && kotak(c).h >= 120);
      if (a.length !== 2) return false;
      // Kolom yang dirata-tengah vertikal tidak sejajar di atas: cukup saling menimpa
      // secara vertikal dan terpisah secara horizontal (bumiairchemitech.com 2026-09-17).
      const [p, q] = a.map(kotak);
      const tindih = Math.min(p.y + p.h, q.y + q.h) - Math.max(p.y, q.y);
      return tindih >= Math.min(p.h, q.h) * 0.5 && (p.x + p.w <= q.x + 10 || q.x + q.w <= p.x + 10);
    });
    // Label kecil di atas judul utama ("OUR SERVICES", "Tentang Kami").
    let label = null;
    if (utama) {
      const ku = kotak(utama);
      const ukuranJudul = parseFloat(getComputedStyle(utama).fontSize);
      const calon = [...el.querySelectorAll('p, span, div, h5, h6, small, h3, h4')].slice(0, 600).find((e) => {
        if (e === utama || e.contains(utama) || utama.contains(e) || !tampak(e)) return false;
        if ([...e.children].some((c) => teks(c))) return false;
        const q = kotak(e);
        const t = teks(e);
        return t && t.split(' ').length <= 6 && q.y + q.h <= ku.y + 4 && q.y >= ku.y - 110
          && Math.abs((q.x + q.w / 2) - (ku.x + ku.w / 2)) < Math.max(ku.w, 300)
          && parseFloat(getComputedStyle(e).fontSize) <= ukuranJudul * 0.7;
      });
      if (calon) {
        const g = getComputedStyle(calon);
        label = { teks: teks(calon).slice(0, 40), ukuran: parseFloat(g.fontSize),
                  kapital: g.textTransform === 'uppercase' || teks(calon) === teks(calon).toUpperCase() };
      }
    }
    // Sisi foto pada seksi berdampingan (teks | foto).
    let fotoPosisi = '';
    if (berdampingan) {
      const besar = foto.map(kotak).filter((q) => q.w >= vw * 0.2).sort((a, b) => b.w * b.h - a.w * a.h)[0];
      if (besar) fotoPosisi = besar.x + besar.w / 2 < k.x + k.w / 2 ? 'kiri' : 'kanan';
    }
    const isiTampak = [...el.querySelectorAll('h1,h2,h3,h4,p,a,li')].slice(0, 400).filter(tampak).map(kotak);
    return {
      urutan: i, y: k.y, tinggi: k.h,
      ruang_atas: isiTampak.length ? Math.max(0, Math.min(...isiTampak.map((q) => q.y)) - k.y) : 0,
      ruang_bawah: isiTampak.length ? Math.max(0, k.y + k.h - Math.max(...isiTampak.map((q) => q.y + q.h))) : 0,
      lebar_isi: (() => {
        const dalam = isiTampak.filter((q) => q.x >= 0 && q.x + q.w <= vw + 2);
        return dalam.length ? Math.max(...dalam.map((q) => q.x + q.w)) - Math.min(...dalam.map((q) => q.x)) : 0;
      })(),
      label, foto_posisi: fotoPosisi,
      kontras_rendah: kontrasRendah(el),
      latar: hex(bl), luminansi: Math.round(lum(bl)), foto_latar: fotoLatar,
      // Lebar & tepi kiri seksi: membedakan seksi selebar layar dari seksi berwadah
      // tetap (Beaver Builder .fl-row-fixed-width, 1320px di tengah layar 1366).
      lebar: Math.round(kotak(el).w), kiri: Math.round(kotak(el).x),
      // Latar seksi berupa VIDEO (YouTube/Vimeo/<video>) — dibedakan dari foto supaya
      // hero situs klien juga memakai video latar seperti referensi.
      video_latar: [...el.querySelectorAll('video, iframe')].some((v) => {
        if (!tampak(v)) return false;
        const src = (v.getAttribute('src') || '') + ' ' + ((v.closest('[class]') || {}).className || '');
        if (v.tagName === 'IFRAME' && !/youtube|youtu\.be|vimeo|dailymotion|bg-video|video-bg|background-video/i.test(String(src))) return false;
        const q = v.getBoundingClientRect();
        return q.width * q.height >= kotak(el).w * kotak(el).h * 0.5;
      }),
      judul: judul.slice(0, 4).map((h) => teks(h).slice(0, 90)),
      judul_utama: utama ? Object.assign({ teks: teks(utama).slice(0, 90), tag: utama.tagName.toLowerCase() }, judulGaya(utama)) : null,
      kata: kataTeks, foto: foto.length, angka_besar: angka, tombol: tombol.length,
      form: !!el.querySelector('form input:not([type=hidden]), form textarea'),
      peta: !!el.querySelector('iframe[src*="google.com/maps"], iframe[src*="maps.google"]'),
      video: !!el.querySelector('video, iframe[src*="youtube"]'),
      akordeon: !!el.querySelector('details, [class*="accordion" i], [class*="faq" i], [class*="toggle" i]'),
      slider: !!el.querySelector('[class*="swiper" i], [class*="slick" i], [class*="carousel" i], [class*="owl-" i], [class*="slider" i]'),
      berdampingan, kartu: grupKartu(el),
      // Bar putih di dasar hero (kontraktorhijau.com "Konsultasi Gratis").
      bar_bawah: [...el.querySelectorAll('*')].slice(0, 600).some((e) => {
        const q = kotak(e);
        const c = rgba(getComputedStyle(e).backgroundColor);
        return tampak(e) && c && c[3] > 0.8 && lum(c) > 200 && q.w >= vw * 0.45 && q.w <= vw * 0.92 && q.h >= 44 && q.h <= 160
          && q.y + q.h >= k.y + k.h - 170 && q.y > k.y + k.h * 0.5 && !!e.querySelector('a, button');
      }),
      // Isi dibungkus kotak berlatar lain dari seksinya (kotak abu bersudut "tentang").
      kotak_latar: (() => {
        const bs = latar(el);
        const e = [...el.querySelectorAll('*')].slice(0, 300).find((x) => {
          const q = kotak(x);
          const c = rgba(getComputedStyle(x).backgroundColor);
          return tampak(x) && c && c[3] > 0.8 && Math.abs(lum(c) - lum(bs)) > 4 && q.w >= vw * 0.6 && q.w < vw * 0.99 && q.h >= k.h * 0.6;
        });
        return e ? { latar: hex(rgba(getComputedStyle(e).backgroundColor)), radius: parseFloat(getComputedStyle(e).borderTopLeftRadius) || 0 } : null;
      })(),
      kelas: String(el.className || '').slice(0, 120),
    };
  });

  // ---- tipografi, tombol, warna ----
  const gBody = getComputedStyle(document.body);
  const h2 = [...document.querySelectorAll('h2')].find(tampak);
  const h1 = [...document.querySelectorAll('h1')].find(tampak);
  const btn = [...document.querySelectorAll('a, button')].filter(tampak).find((a) => {
    const c = rgba(getComputedStyle(a).backgroundColor);
    return c && c[3] > 0.5 && Math.abs(lum(c) - lum(latar(a.parentElement || a))) > 40 && kotak(a).w < 360 && kotak(a).h < 80;
  });
  const warna = {};
  for (const el of document.querySelectorAll('body *')) {
    const c = rgba(getComputedStyle(el).backgroundColor);
    if (!c || c[3] < 0.5 || !tampak(el)) continue;
    const mx = Math.max(...c.slice(0, 3)); const mn = Math.min(...c.slice(0, 3));
    if (mx - mn < 25) continue; // abu/putih/hitam bukan warna merek
    const k = kotak(el);
    warna[hex(c)] = (warna[hex(c)] || 0) + Math.min(k.w * k.h, vw * 900);
  }
  const lebarIsi = h2 ? kotak(h2.parentElement).w : 0;
  let infoFooter = null;
  if (footer) {
    const kolomFooter = [...footer.querySelectorAll('*')].slice(0, 600).reduce((m, e) => {
      const a = [...e.children].filter((c) => tampak(c) && kotak(c).w >= 120 && kotak(c).h >= 40);
      const sebaris = a.length >= 2 && a.every((c) => Math.abs(kotak(c).y - kotak(a[0]).y) < 30);
      return sebaris ? Math.max(m, a.length) : m;
    }, 1);
    // <footer> transparan dengan warna di baris-baris dalamnya (page builder): pakai latar
    // turunan yang menutupi bagian terluas footer.
    const kf = kotak(footer);
    let latarFooter = rgba(getComputedStyle(footer).backgroundColor);
    if (!latarFooter || latarFooter[3] < 0.5) {
      const luas = {};
      for (const e of [...footer.querySelectorAll('*')].slice(0, 400)) {
        const c = rgba(getComputedStyle(e).backgroundColor);
        const k = kotak(e);
        if (c && c[3] > 0.5 && k.w >= kf.w * 0.8) luas[hex(c)] = { c, n: ((luas[hex(c)] || {}).n || 0) + k.h };
      }
      const terluas = Object.values(luas).sort((a, b) => b.n - a.n)[0];
      latarFooter = terluas && terluas.n >= kf.h * 0.4 ? terluas.c : latar(footer);
    }
    // Kolom footer: baris anak berdampingan yang paling banyak, masing-masing dikenali isinya.
    let wadahKolom = null; let nKolom = 1;
    for (const e of [...footer.querySelectorAll('*')].slice(0, 600)) {
      const a = [...e.children].filter((c) => tampak(c) && kotak(c).w >= 120 && kotak(c).h >= 40);
      // Hanya baris yang mengisi sebagian besar footer (kolom bersarang di dalam satu kolom bukan kolom footer).
      const lebarTotal = a.reduce((t, c) => t + kotak(c).w, 0);
      if (a.length >= 2 && a.every((c) => Math.abs(kotak(c).y - kotak(a[0]).y) < 30) && lebarTotal >= kf.w * 0.55
          && a.length > nKolom) { wadahKolom = e; nKolom = a.length; }
    }
    const jenisKolom = (c) => {
      const jenis = [];
      const t = teks(c);
      const img = [...c.querySelectorAll('img, svg')].filter((m) => tampak(m) && kotak(m).w >= 60);
      if (img.length && img.length < 3 && kotak(img[0]).y - kotak(c).y < 60) jenis.push('logo');
      if (c.querySelector('iframe[src*="map"]')) jenis.push('peta');
      if (c.querySelector('input:not([type=hidden]), textarea')) jenis.push('form');
      if (/pengunjung|visitor|kunjungan|statisti/i.test(t)) jenis.push('statistik');
      const menu = [...c.querySelectorAll('a[href]')].filter((a) => tampak(a) && teks(a)
        && !/^(tel|mailto):/i.test(a.href) && !SOSMED.test(a.href) && !/wa\.me|whatsapp/i.test(a.href));
      if (menu.length >= 3) jenis.push('menu');
      const info = isiInfo(c);
      if (info.some((x) => ['telepon', 'email', 'alamat'].includes(x))) jenis.push('kontak');
      if (info.includes('sosmed')) jenis.push('sosmed');
      if ([...c.querySelectorAll('img')].filter((m) => tampak(m) && kotak(m).w >= 50).length >= 3) jenis.push('galeri');
      if ([...c.querySelectorAll('p, div')].some((p) => ![...p.children].some((x) => teks(x)) && teks(p).split(' ').length >= 12)) jenis.push('tentang');
      return jenis.length ? jenis : ['lain'];
    };
    const kolomRinci = wadahKolom ? [...wadahKolom.children].filter((c) => tampak(c) && kotak(c).w >= 120 && kotak(c).h >= 40).map((c) => {
      const j = [...c.querySelectorAll('h1,h2,h3,h4,h5,h6,strong,.widget-title')].filter(tampak)[0];
      return { lebar: Math.round((kotak(c).w / kotak(wadahKolom).w) * 100), judul: j ? teks(j).slice(0, 40) : '', isi: jenisKolom(c) };
    }) : [];
    // Baris hak cipta: strip bawah footer yang memuat ©/copyright.
    const bawah = [...footer.querySelectorAll('*')].filter((e) => {
      if (!tampak(e)) return false;
      const q = kotak(e);
      return q.w >= kf.w * 0.6 && q.h <= 120 && q.y + q.h >= kf.y + kf.h - 130 && /©|copyright|hak cipta|all rights/i.test(teks(e));
    }).sort((a, b) => kotak(b).w - kotak(a).w)[0];
    let infoBawah = null;
    if (bawah) {
      const kb = kotak(bawah);
      const xs = [...bawah.querySelectorAll('p, span, div, a')]
        .filter((e) => tampak(e) && teks(e) && ![...e.children].some((c) => teks(c))).map(kotak);
      const kiri = xs.some((q) => q.x < kb.x + kb.w * 0.3);
      const kanan = xs.some((q) => q.x + q.w > kb.x + kb.w * 0.7);
      const tengah = xs.length && xs.every((q) => Math.abs(q.x + q.w / 2 - (kb.x + kb.w / 2)) < kb.w * 0.2);
      const cb = latarKotak(bawah);
      infoBawah = { rata: tengah ? 'tengah' : kiri && kanan ? 'terbelah' : 'kiri', latar: hex(cb),
                    beda_latar: Math.abs(lum(cb) - lum(latarFooter)) > 5, tinggi: kb.h };
      // Pita hak cipta: baris bawah berlatar sendiri selebar layar (#1c1c1c di bawah #262626).
      // Warnanya bisa di pembungkus luar maupun di anak pembungkus transparan (Beaver Builder).
      const selebar = (e) => { const c = rgba(getComputedStyle(e).backgroundColor); return c && c[3] > 0.5 && hex(c) === hex(cb) && kotak(e).w >= vw * 0.9; };
      let pita = [bawah, ...bawah.querySelectorAll('*')].slice(0, 60).some(selebar);
      for (let e = bawah.parentElement; !pita && e && e !== footer.parentElement; e = e.parentElement) pita = selebar(e);
      infoBawah.pita = infoBawah.beda_latar && pita;
    }
    const judulF = [...footer.querySelectorAll('h2,h3,h4,h5,.widget-title')].find(tampak);
    infoFooter = {
      latar: hex(latarFooter), gelap: lum(latarFooter) < 110, kolom: wadahKolom ? nKolom : kolomFooter, tinggi: kf.h,
      kolom_rinci: kolomRinci,
      kontras_rendah: kontrasRendah(footer),
      bawah: infoBawah,
      sosmed: isiInfo(footer).includes('sosmed'),
      logo: kolomRinci.some((c) => c.isi.includes('logo')),
      judul_kapital: judulF ? getComputedStyle(judulF).textTransform === 'uppercase' : false,
    };
  }
  // Font teks referensi = yang PALING BANYAK TERLIHAT, bukan default <body>.
  // erhaeschemical.com (2026-09-16) memakai Inter hanya di strip topbar (1 elemen,
  // 0,4% luas teks) sementara 60 elemen lain memakai Poppins — mengambil font <body>
  // membuat situs klien berteks Inter, tidak mirip referensinya.
  function fontTeksDominan() {
    const abaikan = /icon|fontawesome|dashicons|glyph/i;
    const luas = {};
    // Teks badan (p/li/td) didahulukan: judul besar Manrope di kontraktorhijau.com menutupi
    // luas teks Atkinson sehingga font judul terbaca sebagai font teks (2026-09-17).
    const badan = {};
    for (const el of document.querySelectorAll('p, li, td')) {
      const txt = (el.textContent || '').trim();
      if (txt.length < 20 || [...el.children].some((c) => /^(P|DIV|UL|OL)$/.test(c.tagName))) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) continue;
      const nama = getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim();
      if (nama && !abaikan.test(nama)) badan[nama] = (badan[nama] || 0) + Math.round(r.width * r.height);
    }
    const urutBadan = Object.entries(badan).sort((a, b) => b[1] - a[1]);
    if (urutBadan.length && urutBadan[0][1] > 20000) return urutBadan[0][0];
    for (const el of document.querySelectorAll('p, li, a, span, td, h1, h2, h3, h4, h5, h6, button')) {
      const txt = (el.textContent || '').trim();
      if (!txt || txt.length < 3 || el.children.length > 0) continue;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || r.top > document.documentElement.clientHeight * 6) continue;
      const nama = getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim();
      if (!nama || abaikan.test(nama)) continue;
      luas[nama] = (luas[nama] || 0) + Math.round(r.width * r.height);
    }
    const urut = Object.entries(luas).sort((a, b) => b[1] - a[1]);
    return urut.length ? urut[0][0] : gBody.fontFamily.split(',')[0].replace(/["']/g, '').trim();
  }
  return {
    url: location.href, judul_halaman: document.title, lebar_layar: vw,
    header: infoHeader, topbar: !!topbar,
    topbar_info: topbar ? { tinggi: kotak(topbar).h, latar: hex(latarTopbar), gelap: lum(latarTopbar) < 110,
      isi: isiInfo(topbar) } : null,
    // Banner judul di halaman dalam: seksi pertama pendek yang memuat <h1>.
    judul_halaman: (() => {
      const s0 = seksi[0];
      const h = s0 ? ([...s0.querySelectorAll('h1')].find(tampak)
        || [...s0.querySelectorAll('h2, h3')].filter(tampak)
          .sort((a, b) => parseFloat(getComputedStyle(b).fontSize) - parseFloat(getComputedStyle(a).fontSize))[0]) : null;
      if (!h) return null;
      const k0 = kotak(s0);
      if (k0.h > 560) return { ada: false };
      const bl = latarKotak(s0);
      // Posisi TEKS judul, bukan kotaknya: <h1> blok selebar kontainer selalu tampak di tengah.
      const rentang = document.createRange();
      rentang.selectNodeContents(h);
      const rt = rentang.getBoundingClientRect();
      const kh1 = rt.width ? { x: rt.left + scrollX, w: rt.width } : kotak(h);
      return {
        ada: true, tinggi: k0.h, foto_latar: berfoto(s0), latar: hex(bl), luminansi: Math.round(lum(bl)),
        rata: getComputedStyle(h).textAlign === 'center' || Math.abs(kh1.x + kh1.w / 2 - vw / 2) < 30 ? 'tengah' : 'kiri',
        breadcrumb: !!s0.querySelector('[class*="breadcrumb" i], nav[aria-label*="bread" i], [class*="crumb" i]')
          || /(home|beranda)\s*[/»>›|]/i.test(teks(s0)),
        ukuran: parseFloat(getComputedStyle(h).fontSize),
      };
    })(),
    tautan_menu: header ? tautanMenu(header, 'a[href]')
      .filter((a) => tampak(a) && teks(a))
      .map((a) => ({ teks: teks(a).slice(0, 40), url: a.href }))
      .filter((a) => { try { const u = new URL(a.url); return u.hostname.replace(/^www\./, '') === host && !u.hash; } catch (e) { return false; } })
      .slice(0, 30) : [],
    // Pohon menu (termasuk submenu yang tersembunyi sampai di-hover): dasar rencana
    // halaman situs klien — jasakontraktorindo.com 2026-09-17: Layanan▾ (4 jasa), Blog▾, FAQ.
    menu_pohon: (() => {
      if (!header) return [];
      const daftar = [...header.querySelectorAll('nav ul, [class*="menu" i] > ul, ul[class*="menu" i]')]
        .filter((u) => !u.parentElement.closest('li'))
        .sort((a, b) => b.querySelectorAll(':scope > li').length - a.querySelectorAll(':scope > li').length)[0];
      const label = (a) => (a.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40);
      if (!daftar) {
        return [...header.querySelectorAll('nav a[href]')].filter((a) => tampak(a) && label(a))
          .slice(0, 12).map((a) => ({ label: label(a), url: a.href, anak: [] }));
      }
      return [...daftar.querySelectorAll(':scope > li')].slice(0, 14).map((li) => {
        const a = li.querySelector('a');
        return {
          label: a ? label(a) : label(li),
          url: a ? a.href : '',
          anak: [...li.querySelectorAll(':scope li > a')].slice(0, 16).map((x) => ({ label: label(x), url: x.href })),
        };
      }).filter((m) => m.label);
    })(),
    seksi: hasilSeksi,
    font: {
      menu: (() => {
        const a = header && tautanMenu(header).find((x) => tampak(x) && teks(x));
        return a ? getComputedStyle(a).fontFamily.split(',')[0].replace(/["']/g, '').trim() : '';
      })(),
      teks: fontTeksDominan(),
      judul: (h2 || h1) ? getComputedStyle(h2 || h1).fontFamily.split(',')[0].replace(/["']/g, '').trim() : '',
      judul_tebal: (h2 || h1) ? +getComputedStyle(h2 || h1).fontWeight : 0,
      judul_kapital: (h2 || h1) ? getComputedStyle(h2 || h1).textTransform === 'uppercase' : false,
      ukuran_h1: h1 ? parseFloat(getComputedStyle(h1).fontSize) : 0,
      ukuran_h2: h2 ? parseFloat(getComputedStyle(h2).fontSize) : 0,
      google: [...document.querySelectorAll('link[href*="fonts.googleapis.com"]')].map((l) => l.href).slice(0, 4),
    },
    tombol: btn ? {
      radius: parseFloat(getComputedStyle(btn).borderTopLeftRadius) || 0,
      tinggi: kotak(btn).h, latar: hex(rgba(getComputedStyle(btn).backgroundColor)),
      kapital: getComputedStyle(btn).textTransform === 'uppercase',
      padding: [Math.round(parseFloat(getComputedStyle(btn).paddingTop) || 0), Math.round(parseFloat(getComputedStyle(btn).paddingLeft) || 0)],
      tebal: +getComputedStyle(btn).fontWeight || 400,
      ukuran: parseFloat(getComputedStyle(btn).fontSize) || 0,
    } : null,
    warna_merek: Object.entries(warna).sort((a, b) => b[1] - a[1]).slice(0, 5).map((w) => w[0]),
    lebar_isi: lebarIsi,
    footer: infoFooter,
  };
}

(async () => {
  const browser = await chromium.launch({ executablePath: chrome, args: ['--no-sandbox'] });
  // Situs referensi berat tidak boleh menahan installer: batas waktu tumbuh per halaman.
  const berhenti = setTimeout(() => { console.log('referensi:timeout'); process.exit(1); }, 170000 + (tugas.length - 1) * 80000);
  let kode = 1;
  try {
    const context = await browser.newContext({
      viewport: { width: 1366, height: 900 },
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    });
    if (process.env.VELOCITY_UKUR_COOKIE) await context.addCookies(JSON.parse(process.env.VELOCITY_UKUR_COOKIE));
    for (const [i, t] of tugas.entries()) {
      try {
        const page = await context.newPage();
        await page.goto(t.url, { waitUntil: 'domcontentloaded', timeout: i === 0 ? 90000 : 60000 }).catch(() => {});
        // Pemeriksa yang masuk sebagai admin: admin bar tidak boleh menggeser ukuran header.
        await page.addStyleTag({ content: '#wpadminbar{display:none!important}html{margin-top:0!important}' }).catch(() => {});
        await page.waitForTimeout(2500);
        // Gulir pelan sampai dasar (400px/200ms): gulir cepat meninggalkan foto lazy-load kosong.
        const tinggiHal = await page.evaluate(() => document.documentElement.scrollHeight).catch(() => 9000);
        for (let j = 0; j < Math.min(80, Math.ceil(tinggiHal / 400)); j += 1) {
          await page.mouse.wheel(0, 400);
          await page.waitForTimeout(200);
        }
        // Header lengket banyak yang baru berubah fixed setelah digulir (Beaver Builder):
        // periksa selagi halaman masih di bawah.
        const lengket = await page.evaluate(() => scrollY > 400 && [...document.querySelectorAll('header, [class*="header" i]')]
          .some((e) => {
            const r = e.getBoundingClientRect();
            return ['fixed', 'sticky'].includes(getComputedStyle(e).position) && r.top <= 5 && r.bottom > 30
              && r.height < 260 && r.width >= document.documentElement.clientWidth * 0.8;
          }));
        await page.evaluate(() => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo({ top: 0, behavior: 'instant' }); });
        await page.waitForTimeout(1500);
        const data = await page.evaluate(ukur);
        if (data.header && lengket) data.header.lengket = true;
        // Lebar isi di dua lebar layar: sama = wadah px tetap (kreditmotor.rmg.asia 1160px),
        // ikut membesar = wadah persen (kontraktorhijau.com 95%). Satu lebar saja tidak bisa
        // membedakan keduanya (yukpergimancing.com 2026-09-17: 1140/1366 terbaca 83,5%).
        // Lebar kontainer dominan: elemen ber-max-width (bukan 'none') dengan luas terbesar di luar
        // header/footer. Rentang teks/foto terkecoh slider & kolom sempit (kreditmotor.rmg.asia).
        const rentangTeks = () => {
          const vw = window.innerWidth;
          const tinggiDok = document.documentElement.scrollHeight;
          const kecuali = [...document.querySelectorAll('header, footer, [class*="footer" i], [class*="header" i]')]
            .filter((k) => k !== document.body && k.getBoundingClientRect().height < tinggiDok * 0.6);
          const luas = {};
          for (const e of document.querySelectorAll('body div, body section, body main, body article')) {
            const g = getComputedStyle(e);
            if (g.maxWidth === 'none' || !/px|%/.test(g.maxWidth)) continue;
            const r = e.getBoundingClientRect();
            if (r.width < 600 || r.width > vw * 0.99 || r.height < 40 || r.left < 0) continue;
            if (kecuali.some((k) => k.contains(e))) continue;
            const w = Math.round(r.width / 4) * 4;
            luas[w] = (luas[w] || 0) + r.height;
          }
          const urut = Object.entries(luas).sort((x, y) => y[1] - x[1]);
          return urut.length ? +urut[0][0] : 0;
        };
        const lebar1366 = await page.evaluate(rentangTeks).catch(() => 0);
        await page.setViewportSize({ width: 1920, height: 900 });
        await page.waitForTimeout(900);
        const lebar1920 = await page.evaluate(rentangTeks).catch(() => 0);
        await page.setViewportSize({ width: 1366, height: 900 });
        await page.waitForTimeout(700);
        data.lebar_isi_dua = { 1366: lebar1366, 1920: lebar1920 };
        fs.writeFileSync(t.keluaran, JSON.stringify(data, null, 1));
        if (t.potret) await page.screenshot({ path: t.potret, fullPage: true, timeout: 60000 }).catch(() => {});
        console.log(`referensi:ok:${data.seksi.length}_seksi ${t.url}`);
        if (i === 0) kode = 0;
        await page.close();
      } catch (e) {
        console.log(`referensi:gagal:${e.message.split('\n')[0]} ${t.url}`);
      }
    }
  } catch (e) {
    console.log(`referensi:gagal:${e.message.split('\n')[0]}`);
  }
  clearTimeout(berhenti);
  await browser.close();
  process.exit(kode);
})();
