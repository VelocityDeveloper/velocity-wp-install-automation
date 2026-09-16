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
 * Pemakaian: referensi-desain.js <url> <keluaran.json> [potret.png]
 * Modul dari VELOCITY_BLOCKVAL (bawaan /var/lib/velocity/tools/blockval).
 * Kode keluar: 0 berhasil, 1 gagal, 3 playwright-core belum terpasang.
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
const [url, keluaran, potret] = process.argv.slice(2);
if (!url || !keluaran) {
  console.log('usage: referensi-desain.js <url> <keluaran.json> [potret.png]');
  process.exit(1);
}
const chrome = process.env.VELOCITY_CHROME
  || fs.readdirSync('/root/.cache/ms-playwright').filter((d) => d.startsWith('chromium-')).sort().reverse()
    .map((d) => `/root/.cache/ms-playwright/${d}/chrome-linux64/chrome`).find((p) => fs.existsSync(p));

// Dijalankan di dalam halaman. Tidak boleh memakai apa pun dari luar fungsi ini.
function ukur() {
  const vw = document.documentElement.clientWidth;
  const rgba = (s) => {
    const m = String(s || '').match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?/);
    return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
  };
  const hex = (c) => '#' + c.slice(0, 3).map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');
  const lum = (c) => 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  const tampak = (el) => {
    const r = el.getBoundingClientRect();
    const g = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && g.display !== 'none' && g.visibility !== 'hidden' && +g.opacity > 0.05;
  };
  const kotak = (el) => {
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height) };
  };
  // Warna latar efektif: naik ke induk sampai ketemu latar tidak transparan.
  const latar = (el) => {
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const c = rgba(getComputedStyle(e).backgroundColor);
      if (c && c[3] > 0.5) return c;
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
    return false;
  };
  const teks = (el) => (el.innerText || '').replace(/\s+/g, ' ').trim();

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
    const tautan = [...header.querySelectorAll('nav a, [class*="menu" i] a')].filter(tampak).map(kotak);
    const tengahMenu = tautan.length ? tautan.reduce((s, t) => s + t.x + t.w / 2, 0) / tautan.length : 0;
    const tombol = [...header.querySelectorAll('a, button')].filter(tampak).some((a) => {
      const c = rgba(getComputedStyle(a).backgroundColor);
      return c && c[3] > 0.5 && Math.abs(lum(c) - lum(latar(header))) > 40 && kotak(a).w < 320;
    });
    infoHeader = {
      tinggi: kh.h,
      latar: hex(latar(header)),
      gelap: lum(latar(header)) < 110,
      transparan_di_atas_hero: (rgba(g.backgroundColor) || [0, 0, 0, 0])[3] < 0.1 && kh.y < 10,
      lengket: ['fixed', 'sticky'].includes(g.position)
        || [...header.querySelectorAll('*')].slice(0, 30).some((e) => ['fixed', 'sticky'].includes(getComputedStyle(e).position)),
      logo_posisi: logo ? (Math.abs(logo.x + logo.w / 2 - vw / 2) < vw * 0.12 ? 'tengah' : 'kiri') : '',
      menu_posisi: !tautan.length ? '' : tengahMenu > vw * 0.6 ? 'kanan' : tengahMenu > vw * 0.4 ? 'tengah' : 'kiri',
      jumlah_menu: tautan.length,
      tombol_ajakan: tombol,
      huruf_menu_kapital: tautan.length ? getComputedStyle(header.querySelector('nav a, [class*="menu" i] a') || header).textTransform === 'uppercase' : false,
    };
  }
  const topbar = [...document.querySelectorAll('body *')].find((e) => {
    if (!tampak(e) || (header && (header.contains(e) || e.contains(header)))) return false;
    const k = kotak(e);
    return k.y < 10 && k.w >= vw * 0.9 && k.h >= 20 && k.h <= 56 && teks(e).length > 5;
  });

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
    const anak = [...el.children].filter((c) => tampak(c) && kotak(c).w >= vw * 0.8 && kotak(c).h >= 40);
    const tinggiAnak = anak.reduce((s, c) => s + kotak(c).h, 0);
    const bertumpuk = anak.length >= 2 && tinggiAnak >= k.h * 0.6;
    if (bertumpuk || (anak.length === 1 && kotak(anak[0]).h >= k.h * 0.9)) {
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
        const g = getComputedStyle(anak[0]);
        const bg = rgba(g.backgroundColor);
        terbaik = {
          n: anak.length, kolom,
          radius: parseFloat(g.borderTopLeftRadius) || 0,
          bayangan: g.boxShadow !== 'none',
          berbingkai: (bg && bg[3] > 0.5 && Math.abs(lum(bg) - lum(latar(induk))) > 8) || parseFloat(g.borderTopWidth) > 0,
          foto: anak.filter((c) => [...c.querySelectorAll('img')].some((i) => tampak(i) && kotak(i).w >= 100)).length,
          ikon: anak.filter((c) => [...c.querySelectorAll('svg, i[class], img')].some((i) => tampak(i) && kotak(i).w < 100 && kotak(i).w >= 16)).length,
          rata_teks: getComputedStyle(anak[0]).textAlign,
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
      return a.length === 2 && Math.abs(kotak(a[0]).y - kotak(a[1]).y) < 40;
    });
    return {
      urutan: i, y: k.y, tinggi: k.h,
      latar: hex(bl), luminansi: Math.round(lum(bl)), foto_latar: fotoLatar,
      judul: judul.slice(0, 4).map((h) => teks(h).slice(0, 90)),
      judul_utama: utama ? Object.assign({ teks: teks(utama).slice(0, 90), tag: utama.tagName.toLowerCase() }, judulGaya(utama)) : null,
      kata: kataTeks, foto: foto.length, angka_besar: angka, tombol: tombol.length,
      form: !!el.querySelector('form input:not([type=hidden]), form textarea'),
      peta: !!el.querySelector('iframe[src*="google.com/maps"], iframe[src*="maps.google"]'),
      video: !!el.querySelector('video, iframe[src*="youtube"]'),
      akordeon: !!el.querySelector('details, [class*="accordion" i], [class*="faq" i], [class*="toggle" i]'),
      slider: !!el.querySelector('[class*="swiper" i], [class*="slick" i], [class*="carousel" i], [class*="owl-" i], [class*="slider" i]'),
      berdampingan, kartu: grupKartu(el),
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
    infoFooter = { latar: hex(latar(footer)), gelap: lum(latar(footer)) < 110, kolom: kolomFooter, tinggi: kotak(footer).h };
  }
  return {
    url: location.href, judul_halaman: document.title, lebar_layar: vw,
    header: infoHeader, topbar: !!topbar,
    seksi: hasilSeksi,
    font: {
      teks: gBody.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
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
    } : null,
    warna_merek: Object.entries(warna).sort((a, b) => b[1] - a[1]).slice(0, 5).map((w) => w[0]),
    lebar_isi: lebarIsi,
    footer: infoFooter,
  };
}

(async () => {
  const browser = await chromium.launch({ executablePath: chrome, args: ['--no-sandbox'] });
  // Situs referensi berat tidak boleh menahan installer.
  const berhenti = setTimeout(() => { console.log('referensi:timeout'); process.exit(1); }, 170000);
  try {
    const page = await browser.newPage({
      viewport: { width: 1366, height: 900 },
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    });
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {});
    await page.waitForTimeout(2500);
    for (let i = 0; i < 30; i += 1) {
      await page.mouse.wheel(0, 900);
      await page.waitForTimeout(200);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(1500);
    const data = await page.evaluate(ukur);
    fs.writeFileSync(keluaran, JSON.stringify(data, null, 1));
    if (potret) await page.screenshot({ path: potret, fullPage: true, timeout: 60000 }).catch(() => {});
    console.log(`referensi:ok:${data.seksi.length}_seksi`);
    clearTimeout(berhenti);
    await browser.close();
    process.exit(0);
  } catch (e) {
    console.log(`referensi:gagal:${e.message.split('\n')[0]}`);
    process.exit(1);
  }
})();
