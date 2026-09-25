// Bagan alur installer ala n8n — satu sumber untuk dashboard lama (/installer/) dan Vue (/v2/installer).
// Dimuat sebagai <script src="/installer/alur.js">; memasang window.AlurInstaller = { render, segmenRun }.
// Kelas CSS (.alur-kanvas, .node, .edge, .flow-meta, ...) disediakan halaman pemakainya.
(function () {
  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
    // ---------- bagan alur installer ala n8n ----------
    // Kanvas simpul langkah (kotak) dan simpul pengecekan (belah ketupat) dengan garis bercabang
    // berlabel, mengikuti percabangan scripts/installer-runner: mode run (dry run / apply / finish),
    // cek paket (Paket G & Portal Berita Custom ke referensi desain + tema FSE; Toko Online Custom
    // ke VD Store dulu, lalu referensi desain + tema FSE; Paket E ke child theme baku velocity-pakete; Paket F dan paket
    // lain ke child theme referensi form; toko online biasa ke child theme lalu VD Store), WordPress
    // baru, paket custom, dan masa pembelajaran maintenance. Status dibaca dari penanda log run
    // terakhir; cabang dari mode run & paket manifest.
    //
    // ATURAN TETAP (permintaan user 2026-09-16): setiap penambahan atau perubahan alur di
    // scripts/installer-runner — langkah baru, cabang paket baru, urutan yang bergeser — WAJIB
    // langsung disusulkan ke SIMPUL + GARIS + konteksRun di bawah, dalam perubahan yang sama.
    // Bagan ini yang dibaca PM/webmaster; alur yang tidak tergambar = alur yang tidak terlihat.
    function tanpaDry(c) { return c.mode === null ? null : c.mode !== 'dry-run'; }
    function hanyaMode(m) { return c => (c.mode === null ? null : c.mode === m); }
    function dan(...nilai) { return nilai.some(x => x === false) ? false : nilai.some(x => x === null) ? null : true; }
    const CHILD_THEME = /child_theme:(?!skipped_fse)/;
    const SELESAI_AGEN = /desain_claude: (sesuai|belum_mirip|ditolak|lewati|gagal)/;
    // Jejak run yang desainnya diambil alih agen Claude (lihat agen_langsung & audit_kemiripan di runner).
    const AMBIL_ALIH_AGEN = /fse_cek: dilewati:agen_claude|desain (langsung )?diambil alih agen Claude/;
    function hasilAgen(t) {
      const m = /desain_claude: (\S+).*?skor=(\d+)->(\d+) menit=([\d.]+)/.exec(t);
      if (m) return (m[1] === 'sesuai' ? 'mirip' : m[1].startsWith('ditolak') ? 'ditolak (skor turun), kembali ke generator'
        : 'belum mirip') + ': skor ' + m[2] + '→' + m[3] + ', ' + m[4] + ' menit';
      const l = /desain_claude: (lewati|gagal):(\S+)/.exec(t);
      return l ? l[1] + ': ' + l[2] : null;
    }
    // Langkah Tema FSE: hasil agen tahap tema, atau keterangan run lama (agen hanya di akhir).
    function hasilTemaAgen(t) {
      const m = /desain_claude_tema: (\S+).*?skor=(\d+)->(\d+) menit=([\d.]+)/.exec(t);
      if (m) return 'agen Claude: ' + (m[1] === 'sesuai' ? 'mirip' : m[1].startsWith('ditolak') ? 'ditolak, dasar generator'
        : 'belum mirip') + ', skor ' + m[2] + '→' + m[3] + ', ' + m[4] + ' menit';
      const l = /desain_claude_tema: (lewati|gagal):(\S+)/.exec(t);
      if (l) return 'agen Claude ' + l[1] + ': ' + l[2] + ' (dasar generator)';
      if (/Paket custom: tema FSE oleh agen Claude/.test(t)) return 'agen Claude selesai';
      return AMBIL_ALIH_AGEN.test(t) ? 'titik awal, desain akhir oleh agen Claude' : null;
    }
    function hasilSsl(t) {
      const m = /^ssl: (terbit|sudah_ada|dilewati|gagal):?(.*)$/m.exec(t);
      if (!m) return null;
      const ket = (m[2] || '').trim();
      if (m[1] === 'terbit') return 'sertifikat terbit' + (ket ? ', berlaku s/d ' + ket : '');
      if (m[1] === 'sudah_ada') return 'sertifikat sudah ada' + (ket ? ', s/d ' + ket : '');
      if (m[1] === 'gagal') return 'gagal: ' + (ket || 'tanpa alasan');
      return 'dilewati: ' + (ket.startsWith('dns_belum_mengarah') ? 'DNS belum mengarah ke server'
        : ket === 'staging' ? 'staging' : ket === 'domain_tidak_ada_di_da' ? 'domain belum ada di panel' : ket);
    }
    function hasilChild(teks) {
      const m = /child_theme:(matched|generated|not_found|no_ref|api_error|download_failed|error):([^:\n]*)/.exec(teks);
      if (!m) return null;
      // Referensi web luar (2026-09-23): tema yang dipakai web itu, dari `child_theme_ref_tema:`.
      const t = /child_theme_ref_tema:(\S+)/.exec(teks);
      return {
        matched: 'referensi ' + m[2] + (t ? ' (' + t[1] + ')' : '') + ' terpasang', generated: 'child theme digenerate',
        not_found: t ? 'tema ' + t[1] + ' (web ' + m[2] + ') belum ada di API'
          : 'referensi ' + (m[2] || '-') + ' tidak ada di API', no_ref: 'form tanpa referensi desain',
        api_error: 'API tema gagal', download_failed: 'unduhan tema gagal', error: 'pencocokan gagal',
      }[m[1]];
    }
    // Langkah "baca referensi desain" (scripts/referensi_desain.py) menutup keluarannya dengan
    // `referensi: ada:<url> (diukur|tembolok)` | `referensi: tidak_ada` | `referensi: gagal:<alasan>`.
    function hasilReferensi(teks) {
      const m = /referensi: (?:ada:(\S+) \(([a-z]+)\)|(tidak_ada)|gagal:(\S+))/.exec(teks);
      if (!m) return null;
      if (m[1]) return (m[2] === 'tembolok' ? 'sudah diukur: ' : 'diukur: ') + m[1].replace(/^https?:\/\//, '').replace(/\/$/, '');
      return m[3] ? 'form tanpa website contoh' : 'pengukuran gagal: ' + m[4];
    }
    // Keterangan simpul audit kemiripan (log fse-audit-kemiripan + putaran generate ulang).
    function hasilMirip(t) {
      if (/kemiripan: tidak_ada_referensi/.test(t)) return 'tanpa referensi';
      const g = /kemiripan: gagal:(\S+)/.exec(t);
      if (g) return 'tidak bisa diperiksa: ' + g[1];
      // Hasil audit TERAKHIR (sesudah generate ulang) yang ditampilkan.
      const semua = [...t.matchAll(/kemiripan: header=(\d+) footer=(\d+) beranda=(\d+)/g)];
      const skor = semua[semua.length - 1];
      const angka = skor ? 'header ' + skor[1] + ' · footer ' + skor[2] + ' · beranda ' + skor[3] : '';
      const ulang = (t.match(/tema & halaman FSE digenerate ulang/g) || []).length;
      const kali = ulang ? ' setelah ' + (ulang + 1) + 'x generate' : '';
      const akhir = [...t.matchAll(/kemiripan: (sesuai|belum_mirip:\S+)/g)].pop();
      if (!akhir) return null;
      if (akhir[1] === 'sesuai') return 'mirip' + kali + (angka ? ': ' + angka : '');
      return 'belum mirip' + kali + ' (' + akhir[1].slice(12).replace(/halaman_/g, '') + '), rincian dikirim'
        + (angka ? ': ' + angka : '');
    }
    // Paket F saat ini diperlakukan sama dengan paket lain (child theme dari referensi form);
    // child theme khusus per website Paket F belum diotomatiskan.
    const SIMPUL = [
      { id: 'validasi', kol: 0, jalur: 1, nama: 'Validasi manifest', mulai: /\] RUNNING: VALIDATING/, selesai: /\] RUNNING: RUNNING_INSTALLER/,
        gagal: /\] FAILED: manifest_missing/, aktif: () => true },
      // Form klien dibaca agen Claude Code (keputusan user 2026-09-25, scripts/baca-form-claude): isian klien
      // dipisah dari teks template, hasil disimpan per isi form & dipakai semua langkah sesudahnya.
      { id: 'bacaForm', kol: 1, jalur: 1, nama: 'Baca form klien', ket0: 'dikerjakan agen Claude',
        mulai: /\] Baca form klien \(agen Claude\)/, selesai: /\] Baca form klien \(agen Claude\): form_claude: (baru|tetap|tanpa_form|lewati)/,
        gagal: /\] Baca form klien \(agen Claude\): form_claude: gagal/,
        ketHasil: t => { const m = /form_claude: (baru|tetap|tanpa_form|lewati|gagal)(?: nama='([^']*)')?/.exec(t);
          return !m ? null : m[1] === 'baru' ? 'dibaca agen Claude' + (m[2] ? ': ' + m[2] : '')
            : m[1] === 'tetap' ? 'hasil baca agen Claude (form tidak berubah)'
            : m[1] === 'tanpa_form' ? 'form tidak ada'
            : m[1] === 'lewati' ? 'dimatikan, pakai pengurai pola' : 'gagal, pakai pengurai pola'; },
        aktif: () => true },
      { id: 'mode', kol: 2, jalur: 1, cek: true, nama: 'Mode run?', mulai: /\] RUNNING: VALIDATING/, aktif: () => true,
        ket: c => ({ 'dry-run': 'dry run', apply: 'apply', finish: 'finish' }[c.mode] || 'menunggu') },
      { id: 'terpasang', kol: 3, jalur: 0, nama: 'WordPress sudah ada', ket0: 'mode finish, tanpa install', mulai: /\] RUNNING: RUNNING_INSTALLER/,
        selesai: /http_check:/, aktif: hanyaMode('finish') },
      { id: 'install', kol: 3, jalur: 1, nama: 'Install WordPress', ket0: 'paket terbaru (API/GitHub), SSH, database, core, plugin', mulai: /\] RUNNING: RUNNING_INSTALLER/,
        selesai: /install_complete|http_check:/, gagal: /remote_failed/, aktif: hanyaMode('apply') },
      { id: 'server', kol: 3, jalur: 3, nama: 'Cek server tujuan', ket0: 'SSH, akun DA, folder domain', mulai: /\] RUNNING: RUNNING_INSTALLER/,
        selesai: /"dry_run":"ok"|\] SUCCESS: DRY_RUN_OK/, gagal: /remote_not_ready|"status":"error"/,
        ketHasil: t => (/"dry_run":"ok"/.test(t) ? 'server tujuan siap' : null), aktif: hanyaMode('dry-run') },
      { id: 'dryselesai', kol: 4, jalur: 3, nama: 'Selesai dry run', mulai: /\] (SUCCESS|FAILED): /, selesai: /\] SUCCESS: DRY_RUN_OK/,
        gagal: /\] FAILED: /, aktif: hanyaMode('dry-run') },
      { id: 'http', kol: 4, jalur: 1, nama: 'Cek HTTP situs', ket0: 'aset inti WordPress', mulai: /http_check:/, selesai: /http_check: 200/,
        gagal: /http_check: (?!200)\d+/, aktif: tanpaDry },
      // Sertifikat SSL (permintaan user 2026-09-23, scripts/site-ssl): diterbitkan lewat
      // letsencrypt.sh DirectAdmin sebelum tema/konten/QA. DNS belum mengarah ke server =
      // dilewati dengan catatan, bukan gagal.
      { id: 'ssl', kol: 5, jalur: 1, nama: 'Terbitkan SSL', ket0: 'Let\'s Encrypt lewat DirectAdmin',
        mulai: /\] Terbitkan SSL$/, selesai: /^ssl: (terbit|sudah_ada|dilewati|gagal)/,
        gagal: /^ssl: gagal/, ketHasil: hasilSsl, aktif: tanpaDry },
      { id: 'paket', kol: 6, jalur: 1, cek: true, nama: 'Cek paket', mulai: /http_check: 200/, aktif: tanpaDry,
        ket: (c, row) => row.paket || 'paket tidak terbaca' },
      // Sebelum tema FSE digenerate, referensi desain dari form dibaca & diukur dulu (paket_g_tema
      // di installer-runner): hasilnya (fse-rencana/<domain>/desain-referensi.json) jadi acuan utama
      // tata letak & gaya beranda, jadi langkah ini berdiri sendiri di bagan.
      { id: 'referensi', kol: 8, jalur: 0, nama: 'Baca referensi', ket0: 'ukur DOM, menu & wadah — bahan agen Claude',
        mulai: /Paket custom: cek referensi desain di form/, selesai: /referensi: (ada:|tidak_ada|gagal:)/,
        gagal: /referensi: gagal:/, ketHasil: hasilReferensi, aktif: c => dan(tanpaDry(c), c.custom) },
      // Keputusan user 2026-09-21: DESAIN_CLAUDE=1 + referensi ada -> langkah ini dikerjakan agen
      // Claude (desain-claude --tahap=tema): fse-apply --tema memasang dasar velocity-fse + palet,
      // lalu agen menyusun header, footer & CSS dari referensi. Selesai = baris akhir
      // `desain_claude_tema:`; tanpa agen, selesai saat gerbang "Sesuai referensi?" mulai.
      { id: 'fse', kol: 9, jalur: 0, nama: 'Tema FSE', ket0: 'referensi ada: agen Claude; lainnya velocity-fse',
        mulai: /Paket custom: (tema FSE|tema dilewati)/,
        selesai: /desain_claude_tema: (sesuai|belum_mirip|ditolak|lewati|gagal)|tema dilewati/,
        lewati: /Paket custom: tema dilewati/, ketHasil: hasilTemaAgen,
        aktif: c => dan(tanpaDry(c), c.custom) },
      // Gerbang sebelum konten AI (keputusan user 2026-09-16): hasil langkah tema dibandingkan dengan
      // rencana referensi desain klien (scripts/fse-cek-referensi). Belum sesuai -> balik ke langkah
      // tema (maks FSE_CEK_MAKS percobaan), sesuai -> lanjut. Log: `fse_cek: sesuai|belum_sesuai:...`.
      { id: 'cekTema', kol: 10, jalur: 0, cek: true, nama: 'Sesuai referensi?', mulai: /fse_cek: |tema dilewati/,
        aktif: c => dan(tanpaDry(c), c.custom),
        ket: (c, row) => {
          const t = (row.log || []).join('\n');
          if (/fse_cek: dilewati:agen_claude \(tema disusun/.test(t)) return 'diaudit agen Claude';
          if (/fse_cek: dilewati:agen_claude/.test(t)) return 'dilewati: agen Claude';
          if (/fse_cek: sesuai/.test(t)) return 'ya';
          if (/fse_cek: masih belum sesuai/.test(t)) return 'lanjut dengan catatan';
          if (/fse_cek: tidak_ada_referensi/.test(t)) return 'tanpa referensi';
          if (/fse_cek: belum_sesuai/.test(t)) return 'belum, tema diulang';
          if (/fse_cek: (gagal|tidak bisa)/.test(t)) return 'tidak bisa diperiksa';
          return 'menunggu';
        } },
      { id: 'childF', kol: 8, jalur: 1, nama: 'Child theme Paket F', ket0: 'referensi form (demo / web luar) lewat API tema', mulai: CHILD_THEME,
        selesai: CHILD_THEME, ketHasil: hasilChild, aktif: c => dan(tanpaDry(c), c.f) },
      { id: 'childToko', kol: 8, jalur: 4, nama: 'Child theme toko', ket0: 'Toko Online Biasa: referensi form (demo / web luar) lewat API tema', mulai: CHILD_THEME,
        selesai: CHILD_THEME, ketHasil: hasilChild, aktif: c => dan(tanpaDry(c), c.tokoBiasa) },
      // Paket E: temanya ditentukan paketnya sendiri (velocity-pakete), bukan referensi di form,
      // dan sudah aktif sebelum konten AI ditulis (keputusan user 2026-09-16).
      { id: 'childE', kol: 8, jalur: 2, nama: 'Child theme Paket E', ket0: 'velocity-pakete dari API tema', mulai: CHILD_THEME,
        selesai: CHILD_THEME, ketHasil: hasilChild, aktif: c => dan(tanpaDry(c), c.e) },
      { id: 'childLain', kol: 8, jalur: 3, nama: 'Tema velocity', ket0: 'child theme bila referensi (demo / web luar) ada di API', mulai: CHILD_THEME,
        selesai: CHILD_THEME, ketHasil: hasilChild, aktif: c => dan(tanpaDry(c), c.custom === null ? null : !(c.custom || c.f || c.e || c.toko)) },
      // VD Store (keputusan user 2026-09-17): Toko Online Custom memasang & mengatur VD Store DULU,
      // baru referensi desain + tema FSE; toko biasa: child theme -> VD Store -> konten AI, tanpa FSE.
      // Dua simpul berpenanda log sama, dibedakan cabang paketnya. Simpul toko custom di baris -1
      // supaya garis Paket G / Portal ke "Baca referensi" tidak menembus kotak.
      { id: 'vdstoreCustom', kol: 7, jalur: -1, nama: 'VD Store', ket0: 'plugin, pengaturan, VD Ongkir & halaman toko', mulai: /\] VD Store$/,
        selesai: /vd_store: (selesai|gagal)|VD Store settings/, gagal: /vd_store: gagal/,
        ketHasil: t => (/halaman_toko:(Halaman berhasil|Semua halaman)/.test(t)
          ? 'plugin, pengaturan & halaman toko siap' + (/origin:api_lookup/.test(t) ? ', asal kirim terisi' : /origin:tidak_ditemukan/.test(t) ? ', asal kirim belum' : '')
          : /vd_store: selesai/.test(t) ? 'plugin terpasang' : null), aktif: c => dan(tanpaDry(c), c.tokoCustom) },
      { id: 'vdstore', kol: 9, jalur: 4, nama: 'VD Store', ket0: 'plugin, pengaturan, VD Ongkir & halaman toko', mulai: /\] VD Store$/,
        selesai: /vd_store: (selesai|gagal)|VD Store settings/, gagal: /vd_store: gagal/,
        ketHasil: t => (/halaman_toko:(Halaman berhasil|Semua halaman)/.test(t)
          ? 'plugin, pengaturan & halaman toko siap' + (/origin:api_lookup/.test(t) ? ', asal kirim terisi' : /origin:tidak_ditemukan/.test(t) ? ', asal kirim belum' : '')
          : /vd_store: selesai/.test(t) ? 'plugin terpasang' : null), aktif: c => dan(tanpaDry(c), c.tokoBiasa) },
      // Toko Online biasa (2026-09-23, scripts/toko-biasa): menu toko sesudah halaman VD Store digenerate,
      // produk dari folder produk klien (atau 5 contoh) sesudah finishing. Situs lama dilewati.
      { id: 'menuToko', kol: 10, jalur: 4, nama: 'Menu toko', ket0: 'Beranda, Produk, Pricelist, Keranjang, Cek Ongkir, Tracking, Berita',
        mulai: /\] Toko biasa: menu toko/, selesai: /menu: (tersusun|dibiarkan)|toko: dilewati/,
        ketHasil: t => { const m = /menu: tersusun:(\d+)/.exec(t); return m ? m[1] + ' item menu'
          : /menu: dibiarkan/.test(t) ? 'dibiarkan: sudah disunting' : /toko: dilewati:situs_sudah_terpasang/.test(t) ? 'dilewati: situs lama' : null; },
        aktif: c => dan(tanpaDry(c), c.tokoBiasa) },
      { id: 'produkToko', kol: 13, jalur: 4, nama: 'Produk toko', ket0: 'folder produk → store_product (gambar < 100 KB), atau 5 contoh',
        mulai: /\] Toko biasa: produk/, selesai: /produk: (dibuat|contoh_sudah_ada|contoh_dilewati|dilewati)|toko: dilewati/,
        ketHasil: t => { const s = /toko: produk: sumber=(folder|contoh) jumlah=(\d+)/.exec(t);
          if (/toko: dilewati:situs_sudah_terpasang/.test(t)) return 'dilewati: situs lama';
          return s ? (s[1] === 'folder' ? s[2] + ' produk dari folder klien' : s[2] + ' produk contoh') : null; },
        aktif: c => dan(tanpaDry(c), c.tokoBiasa) },
      // Paket biasa (child theme klasik, 2026-09-17): isi contoh terstruktur (scripts/paket-g-konten)
      // sebelum konten AI — layanannya jadi kategori artikel dan isi beranda/Layanan.
      { id: 'isiKlasik', kol: 10, jalur: 3, nama: 'Isi contoh', ket0: 'hero, layanan, profil',
        mulai: /\] Isi contoh \(tema klasik\)/, selesai: /konten: (isi contoh dibuat|memakai isi contoh|isi tersimpan|gagal)/,
        gagal: /konten: gagal/, ketHasil: t => { const m = /konten: isi contoh dibuat \(([^)]*)\)/.exec(t); return m ? m[1] : null; },
        aktif: c => dan(tanpaDry(c), c.custom === null ? null : !c.custom) },
      { id: 'konten', kol: 11, jalur: 1, nama: 'Konten AI', ket0: 'halaman & artikel', mulai: /Starting AI content generation/,
        selesai: /AI content generation completed/, aktif: tanpaDry },
      { id: 'finishing', kol: 12, jalur: 1, nama: 'Finishing', ket0: 'logo (gambar lepas dipastikan Claude), favicon, WhatsApp, peta, galeri popup, whitelist IP kantor', mulai: /\] Finishing: aset/,
        selesai: /finish_done/, aktif: tanpaDry },
      { id: 'baru', kol: 13, jalur: 1, cek: true, nama: 'WordPress baru?', mulai: /finish_done/, aktif: tanpaDry,
        ket: c => (c.installBaru === null ? 'menunggu' : c.installBaru ? 'ya' : 'tidak') },
      { id: 'bersih', kol: 14, jalur: 2, nama: 'Bersih-bersih', ket0: 'tema & plugin bawaan', mulai: /\] Bersihkan tema & plugin bawaan/,
        selesai: /cleanup_done/, aktif: c => dan(tanpaDry(c), c.installBaru) },
      { id: 'isi', kol: 15, jalur: 1, cek: true, nama: 'Paket custom?', mulai: /finish_done/, aktif: tanpaDry,
        ket: c => (c.custom === null ? 'paket tidak terbaca' : c.custom ? 'ya: G / Portal / Toko Online Custom' : 'tidak') },
      { id: 'fotoSlot', kol: 16, jalur: 0, nama: 'Foto slot desain', ket0: 'hero, tentang, layanan, galeri',
        mulai: /Paket custom: foto per slot desain/, aktif: c => dan(tanpaDry(c), c.custom) },
      { id: 'dealerUnit', kol: 17, jalur: 0, nama: 'Unit mobil & foto dealer', ket0: 'CPT mobil, foto seksi',
        mulai: /Paket custom: unit mobil & foto dealer/, selesai: /dealer: unit_terbit=/,
        ketHasil: t => { const m = /dealer: unit_terbit=(\d+)/.exec(t); return m ? m[1] + ' unit terbit' : null; },
        aktif: c => dan(tanpaDry(c), c.custom, c.dealer) },
      { id: 'klinikFoto', kol: 17, jalur: 2, nama: 'Foto seksi klinik', ket0: 'dari mockup klien',
        mulai: /Paket custom: foto seksi klinik/, selesai: /klinik: foto_di_media=|klinik: data_tidak_ada/,
        ketHasil: t => { const m = t.match(/klinik: slot:/g); return m ? m.length + ' slot foto' : null; },
        aktif: c => dan(tanpaDry(c), c.custom, c.klinik) },
      // Paket biasa: tampilan child theme klasik (scripts/theme-paket-biasa) lalu foto utama artikel.
      // Portal berita biasa: beranda = tulisan terbaru (desain index.php tema), menu Home + kategori,
      // blok berita per kategori (theme-paket-biasa, 2026-09-18).
      { id: 'tampilan', kol: 16, jalur: 2, nama: 'Tampilan tema klasik', ket0: 'beranda, layanan, kontak, widget; berita: menu kategori',
        mulai: /\] Tampilan tema klasik/, selesai: /tampilan: (selesai|dilewati)/, gagal: /tampilan: gagal/,
        ketHasil: t => (/tampilan: berita_beranda_tulisan_terbaru|tampilan: beranda_tema_berita/.test(t) ? 'beranda berita + menu kategori'
          : /tampilan: beranda_diisi/.test(t) ? 'beranda terisi'
          : (/tampilan: beranda_tema_belum_didukung:(\S+)/.exec(t) || [])[1] ? 'beranda: tema belum didukung' : null),
        aktif: c => dan(tanpaDry(c), c.custom === null ? null : !c.custom) },
      // Child theme tour: plugin velocity-tour-travel + post paket-tour dari dokumen klien (scripts/paket-tour).
      { id: 'paketTour', kol: 18, jalur: 2, nama: 'Paket tour', ket0: 'plugin tour + CPT paket-tour',
        mulai: /\] Paket tour$/, selesai: /paket_tour: (selesai|dilewati)/, gagal: /paket_tour: (gagal|ai_gagal|plugin_gagal|plugin_tidak|cpt_tidak)/,
        ketHasil: t => { if (/paket_tour: dilewati/.test(t)) return 'dilewati (bukan tema tour)';
          const m = /paket_tour: paket baru=(\d+) diperbarui=(\d+)/.exec(t);
          return m ? (+m[1] + +m[2]) + ' paket' : null; },
        aktif: c => dan(tanpaDry(c), c.custom === null ? null : !c.custom) },
      { id: 'fotoKlasik', kol: 19, jalur: 2, nama: 'Foto utama artikel', ket0: 'Pexels/Openverse, sisa: foto klien/sampul',
        mulai: /\] Foto utama artikel$/, selesai: /foto_artikel: \d+\/\d+ diisi/,
        ketHasil: t => {
          const bank = /foto: (\d+)\/(\d+) artikel diberi foto utama/.exec(t);
          const sisa = /foto_artikel: (\d+)\/(\d+) diisi/.exec(t);
          if (!bank && !sisa) return null;
          return (bank ? bank[1] + ' foto bank' : '0 foto bank') + (sisa ? ' + ' + sisa[1] + ' foto klien/sampul' : '');
        },
        aktif: c => dan(tanpaDry(c), c.custom === null ? null : !c.custom) },
      { id: 'halaman', kol: 18, jalur: 0, nama: 'Halaman blok & menu', ket0: 'beranda + halaman dari menu referensi', mulai: /Paket custom: halaman blok & menu/,
        // Halaman susunan agen (fse-rencana/<domain>/claude/<slug>.html) menimpa hasil generator di
        // fse-apply --isi (log `fse: halaman_claude:<slug>`).
        ketHasil: t => { const m = t.match(/fse: halaman_claude:/g);
          return m ? m.length + ' halaman dari agen Claude'
            : AMBIL_ALIH_AGEN.test(t) ? 'titik awal, halaman akhir oleh agen Claude' : null; },
        aktif: c => dan(tanpaDry(c), c.custom) },
      { id: 'fotoArtikel', kol: 19, jalur: 0, nama: 'Foto utama artikel', ket0: 'Pexels, sisa: foto klien/sampul', mulai: /Paket custom: foto utama artikel/,
        selesai: /foto_artikel: \d+\/\d+ diisi/,
        ketHasil: t => {
          const bank = /foto: (\d+)\/(\d+) artikel diberi foto utama/.exec(t);
          const sisa = /foto_artikel: (\d+)\/(\d+) diisi/.exec(t);
          if (!bank && !sisa) return null;
          return (bank ? bank[1] + ' foto Pexels/bank' : '0 foto bank') + (sisa ? ' + ' + sisa[1] + ' foto klien/sampul' : '');
        },
        aktif: c => dan(tanpaDry(c), c.custom) },
      { id: 'visual', kol: 20, jalur: 0, nama: 'Cek visual', ket0: 'desktop & HP + banding referensi ke Telegram', mulai: /Paket custom: cek visual/,
        selesai: /visual: folder=/, aktif: c => dan(tanpaDry(c), c.custom, c.agenLangsung === null ? null : !c.agenLangsung) },
      // Audit kemiripan (permintaan user 2026-09-17, scripts/fse-audit-kemiripan): tampilan situs jadi
      // diukur dengan pengukur referensi lalu dinilai per bagian (header, footer, beranda per seksi,
      // gaya, halaman dalam). Belum mirip -> dilaporkan "perlu dicek" di Telegram, alur tetap lanjut.
      // Belum mirip -> tema + halaman FSE digenerate ulang lalu diaudit lagi (installer-runner
      // audit_kemiripan, maks FSE_MIRIP_MAKS, berhenti kalau skor tidak naik); sisa beda dikirim
      // sebagai daftar "perlu diperbaiki" di laporan Telegram.
      { id: 'mirip', kol: 21, jalur: 0, cek: true, nama: 'Mirip referensi?', ket0: 'header, footer, beranda per seksi',
        mulai: /Paket custom: audit kemiripan/, selesai: /kemiripan: (sesuai|belum_mirip:|tidak_ada_referensi|gagal:)/,
        ket: (c, row) => hasilMirip(segmenRun(row).join('\n')) || 'menunggu',
        aktif: c => dan(tanpaDry(c), c.custom, c.agenLangsung === null ? null : !c.agenLangsung) },
      // Agen desain Claude (keputusan user 2026-09-18, scripts/desain-claude, DESAIN_CLAUDE=1): situs yang
      // belum mirip dikerjakan Claude Code — baca referensi, susun halaman/header/footer/CSS, audit & ulangi
      // sendiri; skor turun dibanding generator -> hasilnya dicabut. Sejak 2026-09-19 paket custom yang
      // punya referensi langsung ke agen sesudah foto artikel (agen_langsung di runner): gerbang tema &
      // audit kemiripan dilewati, cek visual dijalankan sesudah agen.
      { id: 'agenClaude', kol: 22, jalur: 0, nama: 'Agen desain Claude', ket0: 'desain + audit + ulang sendiri',
        mulai: /belum mirip, desain diambil alih agen Claude|desain_claude: audit awal/, selesai: SELESAI_AGEN,
        gagal: /desain_claude: gagal/, ketHasil: hasilAgen,
        aktif: c => dan(tanpaDry(c), c.custom, c.agenClaude, c.agenLangsung === null ? null : !c.agenLangsung) },
      // Jalur agen langsung (keputusan user 2026-09-19, agen_langsung di runner): referensi ada +
      // DESAIN_CLAUDE=1 -> sesudah foto artikel agen Claude langsung mengambil alih (gerbang tema &
      // audit kemiripan dilewati), lalu cek visual desain akhir. Lajur 1 sendiri supaya tidak
      // menumpang simpul jalur lama.
      { id: 'agenLangsung', kol: 20, jalur: 1, nama: 'Agen desain Claude', ket0: 'langsung dari referensi: desain + audit sendiri',
        mulai: /desain langsung diambil alih agen Claude/, selesai: SELESAI_AGEN,
        gagal: /desain_claude: gagal/, ketHasil: hasilAgen, aktif: c => dan(tanpaDry(c), c.custom, c.agenLangsung) },
      { id: 'visualAkhir', kol: 21, jalur: 1, nama: 'Cek visual', ket0: 'desain akhir agen, desktop & HP ke Telegram',
        mulai: /Paket custom: cek visual/, selesai: /visual: folder=/, aktif: c => dan(tanpaDry(c), c.custom, c.agenLangsung) },
      // Agen permintaan form (keputusan user 2026-09-24, scripts/permintaan-claude, PERMINTAAN_CLAUDE=1):
      // pesan tambahan di form klien dikerjakan Claude sebagai user situs sebelum pemeriksaan akhir.
      { id: 'permintaan', kol: 23, jalur: 1, nama: 'Permintaan form', ket0: 'pesan tambahan klien, dikerjakan agen Claude',
        mulai: /\] Permintaan form klien \(agen Claude\)/, selesai: /^permintaan_claude: (selesai \d|sebagian:|lewati:)/m,
        gagal: /^permintaan_claude: gagal:/m,
        ketHasil: t => { let m = /^permintaan_claude: selesai (\d+)\/\d+ butir/m.exec(t);
          if (m) return m[1] + ' butir dikerjakan';
          if ((m = /^permintaan_claude: sebagian:(\d+\/\d+)/m.exec(t))) return 'sebagian ' + m[1] + ', sisa perlu dicek';
          if ((m = /^permintaan_claude: (lewati|gagal):(\S+)/m.exec(t))) return (m[1] === 'lewati' ? 'dilewati: ' : 'gagal: ') + m[2].replace(/_/g, ' ');
          return null; },
        aktif: c => dan(tanpaDry(c), c.permintaanClaude) },
      // + permintaan klien di FORM 5 pesan tambahan (scripts/permintaan-form, keputusan user 2026-09-24):
      // belum ditandai selesai = "perlu dicek" berisi permintaannya.
      { id: 'qa', kol: 24, jalur: 1, nama: 'Pemeriksaan akhir', ket0: 'SSL, menu, konten, permintaan form', mulai: /qa_result:/, selesai: /qa_result:/,
        ketHasil: t => (/permintaan_form: belum_dikerjakan/.test(t) ? 'permintaan form klien belum dikerjakan'
          : /permintaan_form: sudah_dikerjakan/.test(t) ? 'permintaan form klien sudah dikerjakan' : null), aktif: tanpaDry },
      { id: 'maint', kol: 25, jalur: 1, cek: true, nama: 'Masa pembelajaran?', mulai: /qa_result:/, aktif: tanpaDry,
        ket: c => (c.mode === 'finish' ? 'mode finish, tanpa maintenance'
          : c.maintLewat !== null ? (c.maintLewat ? 'ya' : 'tidak') : c.custom === null ? 'menunggu' : c.custom ? 'ya: paket custom' : 'tidak') },
      { id: 'maintLewat', kol: 26, jalur: 0, nama: 'Tanpa maintenance', ket0: 'situs dibiarkan terbuka', mulai: /maintenance_dilewati/,
        selesai: /maintenance_dilewati/, aktif: c => dan(hanyaMode('apply')(c), c.maintLewat ?? c.custom) },
      { id: 'maintOn', kol: 26, jalur: 2, nama: 'Maintenance mode', ket0: 'halaman perawatan', mulai: /\] Maintenance mode/,
        selesai: /maintenance: maintenance_(enabled|active|skip)/,
        aktif: c => dan(hanyaMode('apply')(c), (c.maintLewat ?? c.custom) === null ? null : !(c.maintLewat ?? c.custom)) },
      { id: 'selesai', kol: 27, jalur: 1, nama: 'Selesai', mulai: /\] (SUCCESS|FAILED): /, selesai: /\] SUCCESS: /, gagal: /\] FAILED: /, aktif: tanpaDry },
      // Trap EXIT runner (juga saat run gagal): berkas milik root dari WP-CLI dikembalikan ke user situs,
      // supaya pasang plugin/tema dari wp-admin tidak gagal (scripts/pemilik_wp.py, 2026-09-18).
      { id: 'pemilik', kol: 28, jalur: 1, nama: 'Kepemilikan wp-content', ket0: 'chown ke user situs',
        mulai: /\] Kepemilikan wp-content/, selesai: /pemilik: (wp_content_dirapikan|sudah_benar|dilewati)/,
        gagal: /pemilik: (gagal|chown_gagal)/,
        ketHasil: t => {
          // Skrip langkah juga mencetak "pemilik:"; yang dibaca hanya hasil trap akhir run.
          t = t.slice(Math.max(0, t.lastIndexOf('] Kepemilikan wp-content')));
          const m = /pemilik: wp_content_dirapikan:[^:]+:[^:]+:(\d+)/.exec(t);
          return m ? m[1] + ' berkas dirapikan' : /pemilik: sudah_benar/.test(t) ? 'sudah sesuai' : null;
        },
        aktif: tanpaDry },
    ];
    // [dari, ke, label, syarat]. Tanpa syarat: garis dari simpul pengecekan aktif kalau tujuannya
    // dilalui; garis biasa aktif kalau kedua ujungnya dilalui.
    const GARIS = [
      ['validasi', 'bacaForm'], ['bacaForm', 'mode'],
      ['mode', 'terpasang', 'finish'], ['mode', 'install', 'apply'], ['mode', 'server', 'dry run'],
      ['terpasang', 'http'], ['install', 'http'], ['server', 'dryselesai'],
      ['http', 'ssl'], ['ssl', 'paket'],
      ['paket', 'referensi', 'G / Portal', c => dan(tanpaDry(c), c.custom === null ? null : c.custom && !c.toko)],
      ['paket', 'vdstoreCustom', 'Toko Online Custom'], ['vdstoreCustom', 'referensi'],
      ['paket', 'childF', 'Paket F'], ['paket', 'childE', 'Paket E'],
      ['paket', 'childToko', 'Toko Online Biasa'], ['paket', 'childLain', 'lainnya'],
      ['referensi', 'fse'], ['fse', 'cekTema'],
      // Belum sesuai referensi: kembali ke langkah tema sebelum konten AI ditulis.
      ['cekTema', 'fse', 'belum, ulangi tema'],
      // Semua paket custom lanjut ke konten (VD Store toko custom sudah terpasang sebelum tema).
      ['cekTema', 'konten', 'sesuai', c => dan(tanpaDry(c), c.custom)],
      ['childF', 'isiKlasik'], ['childE', 'isiKlasik'], ['childToko', 'vdstore'], ['childLain', 'isiKlasik'],
      ['vdstore', 'menuToko'], ['menuToko', 'isiKlasik'],
      ['isiKlasik', 'konten'],
      ['konten', 'finishing'],
      ['finishing', 'baru', '', c => dan(tanpaDry(c), c.tokoBiasa === null ? null : !c.tokoBiasa)],
      ['finishing', 'produkToko', 'toko biasa', c => dan(tanpaDry(c), c.tokoBiasa)], ['produkToko', 'baru'],
      ['baru', 'bersih', 'ya'], ['bersih', 'isi'], ['baru', 'isi', 'tidak', c => dan(tanpaDry(c), c.installBaru === null ? null : !c.installBaru)],
      ['isi', 'fotoSlot', 'ya'],
      ['fotoSlot', 'dealerUnit', 'dealer mobil', c => dan(tanpaDry(c), c.custom, c.dealer)],
      ['dealerUnit', 'halaman'],
      ['fotoSlot', 'klinikFoto', 'gaya klinik', c => dan(tanpaDry(c), c.custom, c.klinik)],
      ['klinikFoto', 'halaman'],
      ['fotoSlot', 'halaman', '', c => dan(tanpaDry(c), c.custom,
        c.dealer === null || c.klinik === null ? null : !c.dealer && !c.klinik)],
      ['halaman', 'fotoArtikel'],
      ['fotoArtikel', 'visual', '', c => dan(tanpaDry(c), c.custom, c.agenLangsung === null ? null : !c.agenLangsung)],
      // Referensi ada + DESAIN_CLAUDE=1: agen Claude langsung, lalu cek visual desain akhir, lalu QA.
      ['fotoArtikel', 'agenLangsung', 'referensi ada', c => dan(tanpaDry(c), c.custom, c.agenLangsung)],
      ['agenLangsung', 'visualAkhir'], ['visualAkhir', 'permintaan'],
      ['visual', 'mirip'],
      // Belum mirip: kembali ke tema FSE (generate ulang tema + halaman), lalu diaudit lagi.
      ['mirip', 'fse', 'belum mirip, generate ulang', c => dan(tanpaDry(c), c.custom, c.miripUlang)],
      ['mirip', 'agenClaude', 'belum mirip, agen Claude', c => dan(tanpaDry(c), c.custom, c.agenClaude, c.agenLangsung === null ? null : !c.agenLangsung)],
      ['agenClaude', 'permintaan'],
      ['mirip', 'permintaan', 'mirip / dilaporkan'],
      ['isi', 'tampilan', 'tidak'], ['tampilan', 'paketTour'], ['paketTour', 'fotoKlasik'], ['fotoKlasik', 'permintaan'],
      ['permintaan', 'qa'], ['qa', 'maint'], ['maint', 'maintLewat', 'ya'], ['maint', 'maintOn', 'tidak'],
      ['maint', 'selesai', 'finish', hanyaMode('finish')], ['maintLewat', 'selesai'], ['maintOn', 'selesai'],
      ['selesai', 'pemilik'],
    ];
    const IKON_ALUR = { selesai: '✓', berjalan: '●', gagal: '✗', dilewati: '-', menunggu: '○', cabang: '·' };
    const WAKTU_LOG = /^\[(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d)\]/;

    function segmenRun(row) {
      const log = (row && row.log) || [];
      for (let i = log.length - 1; i >= 0; i--) {
        if (/\] RUNNING: VALIDATING/.test(log[i])) return log.slice(i);
      }
      return row && row.status === 'RUNNING' ? log : [];
    }
    function waktuDi(baris, i) {
      for (let j = Math.min(i, baris.length - 1); j >= 0; j--) {
        const m = WAKTU_LOG.exec(baris[j]);
        if (m) return new Date(m[1]);
      }
      return null;
    }
    function lamanya(ms) {
      const s = Math.max(0, Math.round(ms / 1000));
      if (s < 60) return s + ' dtk';
      const m = Math.floor(s / 60);
      return m < 60 ? m + ' mnt ' + (s % 60) + ' dtk' : Math.floor(m / 60) + ' j ' + (m % 60) + ' mnt';
    }

    // Mode & paket menentukan cabang. Log baru memuat baris "Mode run: <mode> | paket: <paket>"
    // (installer-runner); log lama ditebak dari penandanya. null = belum diketahui.
    function konteksRun(row, teks) {
      const paket = String(row.paket || (/\] Mode run: [a-z-]+ \| paket: (.*)$/m.exec(teks) || [])[1] || '').toLowerCase().replace(/\s+/g, '');
      let mode = (/\] Mode run: ([a-z-]+)/.exec(teks) || [])[1] || null;
      if (!mode) {
        // remote_not_ready hanya keluar dari pengecekan server dry run (log lama tanpa "Mode run").
        if (/"status":"dry-run"|\] SUCCESS: DRY_RUN_OK|remote_not_ready|"remote_check"/.test(teks)) mode = 'dry-run';
        else if (/install_complete|Transferring package|child_theme:|WordPress downloaded/.test(teks)) mode = 'apply';
        else if (/http_check:/.test(teks)) mode = 'finish';
      }
      const lewatFinishing = /cleanup_done|Paket custom: foto per slot|qa_result:|\] (SUCCESS|FAILED): /.test(teks);
      const custom = paket ? ['paketg', 'paketportalberitacustom', 'pakettokoonlinecustom'].includes(paket) : null;
      const toko = paket ? paket.includes('tokoonline') : null;
      return {
        mode,
        custom,
        f: paket ? paket === 'paketf' : null,
        // Paket E punya child theme baku (velocity-pakete), tidak lewat referensi form.
        e: paket ? paket === 'pakete' : null,
        toko,
        // Toko Online Custom: VD Store dulu, lalu referensi desain & tema FSE. Toko online biasa:
        // child theme dari referensi form, lalu VD Store, lalu konten AI (tanpa FSE).
        tokoCustom: paket ? custom && toko : null,
        tokoBiasa: paket ? toko && !custom : null,
        installBaru: /\] Bersihkan tema & plugin bawaan/.test(teks) ? true : lewatFinishing ? false : null,
        maintLewat: /maintenance_dilewati/.test(teks) ? true : /\] Maintenance mode/.test(teks) ? false : null,
        // Situs dealer mobil (manifest gaya_beranda=dealer): unit CPT mobil + foto seksinya
        // dipasang sebelum halaman blok. Runner hanya mencetak barisnya untuk situs dealer.
        dealer: /Paket custom: unit mobil & foto dealer/.test(teks) ? true
          : /Paket custom: halaman blok & menu/.test(teks) ? false : null,
        // Gaya klinik (manifest gaya_beranda=klinik): foto seksi dari mockup klien ke slot.
        klinik: /Paket custom: foto seksi klinik/.test(teks) ? true
          : /Paket custom: halaman blok & menu/.test(teks) ? false : null,
        // Audit kemiripan menyatakan belum mirip dan tema + halaman FSE digenerate ulang.
        miripUlang: /tema & halaman FSE digenerate ulang/.test(teks),
        // Belum mirip dan DESAIN_CLAUDE=1: agen Claude mengambil alih (bukan generate ulang).
        agenClaude: /desain (langsung )?diambil alih agen Claude|desain_claude: audit awal/.test(teks),
        // Referensi ada + DESAIN_CLAUDE=1 (2026-09-19): agen langsung, tanpa gerbang tema & audit.
        // Saklar PERMINTAAN_CLAUDE: runner hanya mencetak barisnya kalau agen permintaan dijalankan.
        permintaanClaude: /\] Permintaan form klien \(agen Claude\)/.test(teks) ? true : /qa_result:/.test(teks) ? false : null,
        agenLangsung: /fse_cek: dilewati:agen_claude|desain langsung diambil alih agen Claude/.test(teks) ? true
          : /fse_cek: (sesuai|belum|masih|tidak|gagal)|Paket custom: audit kemiripan/.test(teks) ? false : null,
      };
    }

    function hitungAlur(row) {
      const baris = segmenRun(row);
      const teks = baris.join('\n');
      const c = konteksRun(row, teks);
      const jalan = row.status === 'RUNNING';
      const gagalRun = /FAILED|error/i.test(row.status || '');
      const cari = (re, dari = 0) => { if (!re) return -1; for (let i = dari; i < baris.length; i++) if (re.test(baris[i])) return i; return -1; };
      const simpul = SIMPUL.map(s => ({ ...s, aktifNilai: s.aktif(c), iMulai: cari(s.mulai) }));
      const dilalui = simpul.filter(s => s.aktifNilai !== false && s.iMulai >= 0);
      const iTerakhir = Math.max(-1, ...dilalui.map(s => s.iMulai));
      simpul.forEach(s => {
        s.lama = null;
        if (s.aktifNilai === false) { s.status = 'cabang'; return; }
        if (s.iMulai < 0) {
          const terlewati = !jalan || dilalui.some(x => x.kol > s.kol);
          s.status = baris.length && terlewati ? 'dilewati' : 'menunggu';
          return;
        }
        const berikut = dilalui.filter(x => x.iMulai > s.iMulai).sort((p, q) => p.iMulai - q.iMulai)[0];
        const iSelesai = cari(s.selesai, s.iMulai);
        if (s.gagal && cari(s.gagal, s.iMulai) >= 0) s.status = 'gagal';
        else if (s.lewati && s.lewati.test(teks)) s.status = 'dilewati';
        else if (s.cek || iSelesai >= 0 || berikut) s.status = 'selesai';
        else if (jalan) s.status = 'berjalan';
        else s.status = gagalRun && s.iMulai === iTerakhir ? 'gagal' : 'selesai';
        // Durasi = sampai langkah berikutnya mulai. Penanda selesai sering tanpa cap waktu
        // ("fse: tema_siap", "qa_result"), jadi cap waktunya sama dengan saat mulai.
        if (!s.cek && s.id !== 'selesai') {
          const tMulai = waktuDi(baris, s.iMulai);
          const tAkhir = s.status === 'berjalan' ? new Date() : waktuDi(baris, berikut ? berikut.iMulai : baris.length - 1);
          const lama = tMulai && tAkhir ? tAkhir - tMulai : null;
          s.lama = lama === null || lama < 1000 ? null : lama;
        }
      });
      const tAwal = waktuDi(baris, 0);
      const tUjung = jalan ? new Date() : waktuDi(baris, baris.length - 1);
      const terakhirLog = [...baris].reverse().find(b => b.trim()) || '';
      return { simpul, baris, teks, c, jalan, gagalRun, lama: tAwal && tUjung ? tUjung - tAwal : null,
               logTerakhir: terakhirLog.replace(WAKTU_LOG, '').trim() };
    }

    function teksSub(s, a, row) {
      if (s.status === 'cabang') return 'tidak dilalui';
      if (s.cek) return s.ket(a.c, row);
      if (s.status === 'menunggu') return s.ket0 || 'menunggu';
      if (s.status === 'dilewati') return 'dilewati';
      // Alasan langkah itu sendiri (mis. "pengukuran gagal: ...") lebih tepat daripada stage run,
      // yang bisa berbunyi COMPLETE padahal langkah ini yang gagal.
      if (s.status === 'gagal') return (s.ketHasil && s.ketHasil(a.teks)) || 'gagal' + (row.stage && !a.jalan ? ': ' + row.stage : '');
      if (s.status === 'berjalan') return 'berjalan ' + (s.lama !== null ? lamanya(s.lama) : '');
      const hasil = s.ketHasil ? s.ketHasil(a.teks) : null;
      return hasil || 'selesai' + (s.lama !== null ? ', ' + lamanya(s.lama) : '');
    }

    // Baris bisa negatif (VD Store toko custom di atas baris paket custom).
    const JALUR_MIN = Math.min(...SIMPUL.map(s => s.jalur));
    const UKURAN = { lebar: 188, tinggi: 74, cek: 96, jarak: 44, jalur: 108, tepi: 22, ketupat: 38 };
    function tataLetak() {
      const kolom = Math.max(...SIMPUL.map(s => s.kol)) + 1;
      const lebarKol = Array.from({ length: kolom }, (_, k) => (SIMPUL.some(s => s.kol === k && !s.cek) ? UKURAN.lebar : UKURAN.cek));
      const x = [];
      let pos = UKURAN.tepi;
      lebarKol.forEach((l, k) => { x[k] = pos; pos += l + UKURAN.jarak; });
      const jalurMaks = Math.max(...SIMPUL.map(s => s.jalur));
      return { x, lebarKol, lebar: pos - UKURAN.jarak + UKURAN.tepi, tinggi: UKURAN.tepi * 2 + (jalurMaks - JALUR_MIN) * UKURAN.jalur + UKURAN.tinggi + 20 };
    }
    function jangkar(s, t) {
      const cy = UKURAN.tepi + (s.jalur - JALUR_MIN) * UKURAN.jalur + UKURAN.tinggi / 2;
      const x0 = t.x[s.kol], w = t.lebarKol[s.kol];
      if (!s.cek) return { cy, masuk: [x0, cy], keluar: [x0 + w, cy] };
      const r = UKURAN.ketupat * Math.SQRT2 / 2;
      return { cy, masuk: [x0 + w / 2 - r, cy], keluar: [x0 + w / 2 + r, cy] };
    }
    function titikKurva(p, t) {
      const u = 1 - t;
      return [0, 1].map(i => u * u * u * p[0][i] + 3 * u * u * t * p[1][i] + 3 * u * t * t * p[2][i] + t * t * t * p[3][i]);
    }

    function renderAlur(wadah, row, opsi = {}) {
      const kanvasLama = wadah.querySelector('.alur-kanvas');
      const gulirLama = kanvasLama ? kanvasLama.scrollLeft : null;
      wadah._row = row;
      const a = hitungAlur(row);
      const t = tataLetak();
      const peta = Object.fromEntries(a.simpul.map(s => [s.id, s]));
      const langkah = a.simpul.filter(s => !s.cek && s.status !== 'cabang' && s.status !== 'dilewati');
      const beres = langkah.filter(s => s.status === 'selesai').length;
      const kelasStatus = !a.baris.length ? '' : a.jalan ? 'run' : a.gagalRun ? 'err' : 'ok';
      const namaMode = { 'dry-run': 'dry run', apply: 'apply', finish: 'finish' }[a.c.mode];
      const meta = `<div class="flow-meta"><strong>${esc(row.domain || '-')}</strong>`
        + (row.status ? `<span class="${kelasStatus}">${esc(row.status)}${row.stage ? ' / ' + esc(row.stage) : ''}</span>` : '')
        + (namaMode ? `<span class="chip">mode ${esc(namaMode)}</span>` : '')
        + (row.paket ? `<span class="chip">${esc(row.paket)}</span>` : '')
        + (a.baris.length ? `<span>${beres}/${langkah.length} langkah</span>` : '')
        + (a.lama !== null ? `<span>${a.jalan ? 'berjalan' : 'durasi'} ${lamanya(a.lama)}</span>` : '')
        + (opsi.galat ? `<span class="err">gagal memperbarui: ${esc(opsi.galat)}</span>` : '')
        + (opsi.tutup ? `<button class="action" type="button" data-tutup="${esc(row.domain)}">[ tutup ]</button>` : '')
        + '</div>';
      const logBaris = a.jalan && a.logTerakhir ? `<p class="flow-log">log terakhir: ${esc(a.logTerakhir.slice(0, 160))}</p>` : '';
      const catatan = a.baris.length ? ''
        : `<p class="flow-catatan">${opsi.templat ? 'Belum ada run installer tercatat. Bagan menampilkan seluruh alur installer.'
          : 'Belum ada run installer tercatat untuk domain ini. Cabang paket dibaca dari manifest.'}</p>`;

      let garis = '';
      for (const [dari, ke, label, syarat] of GARIS) {
        const s = peta[dari], u = peta[ke];
        const aktif = syarat ? syarat(a.c) : s.cek ? u.aktifNilai : dan(s.aktifNilai, u.aktifNilai);
        const kelas = aktif === false || u.status === 'cabang' ? 'cabang'
          : u.status === 'berjalan' ? 'berjalan' : u.status === 'gagal' ? 'gagal'
          : s.status === 'selesai' && (u.status === 'selesai' || u.status === 'dilewati') ? 'selesai' : '';
        const p1 = jangkar(s, t).keluar, p2 = jangkar(u, t).masuk, dx = Math.max(22, (p2[0] - p1[0]) / 2);
        const kurva = [p1, [p1[0] + dx, p1[1]], [p2[0] - dx, p2[1]], p2];
        garis += `<path class="edge ${kelas}" d="M${kurva[0]} C${kurva[1]} ${kurva[2]} ${kurva[3]}"/>`;
        if (label) {
          // 62% panjang garis: di celah antar kolom, tidak menimpa nama simpul pengecekan di bawah ketupat.
          const q = titikKurva(kurva, 0.62);
          garis += `<text class="edge-label${kelas === 'cabang' ? '' : ' aktif'}" x="${q[0].toFixed(1)}" y="${(q[1] - 6).toFixed(1)}" text-anchor="middle">${esc(label)}</text>`;
        }
      }
      const simpulHtml = a.simpul.map(s => {
        const j = jangkar(s, t), w = t.lebarKol[s.kol];
        const sub = teksSub(s, a, row);
        const label = `${s.nama}: ${s.status === 'cabang' ? 'tidak dilalui' : s.status}${sub ? ', ' + sub : ''}`;
        if (s.cek) {
          return `<li class="node-cek ${s.status}" data-simpul="${s.id}" style="left:${t.x[s.kol]}px;top:${j.cy - UKURAN.ketupat / 2 - 8}px;width:${w}px" aria-label="${esc(label)}">`
            + `<span class="ketupat"><span class="node-ikon" aria-hidden="true">${IKON_ALUR[s.status]}</span></span>`
            + `<span class="cek-nama">${esc(s.nama)}</span><span class="cek-ket">${esc(sub)}</span></li>`;
        }
        return `<li class="node ${s.status}" data-simpul="${s.id}" style="left:${t.x[s.kol]}px;top:${j.cy - UKURAN.tinggi / 2}px;width:${w}px" aria-label="${esc(label)}">`
          + `<div class="node-top"><span class="node-ikon" aria-hidden="true">${IKON_ALUR[s.status]}</span><span class="node-nama">${esc(s.nama)}</span></div>`
          + `<div class="node-sub" title="${esc(sub)}">${esc(sub)}</div></li>`;
      }).join('');

      wadah.innerHTML = meta + logBaris + catatan
        + `<div class="alur-kanvas" tabindex="0" role="group" aria-label="Bagan alur installer ${esc(row.domain || '')}. Geser ke samping untuk melihat semua langkah.">`
        + `<div class="alur-isi" style="width:${t.lebar}px;height:${t.tinggi}px"><svg width="${t.lebar}" height="${t.tinggi}" aria-hidden="true">${garis}</svg>`
        + `<ol class="alur-simpul">${simpulHtml}</ol></div></div>`
        + '<p class="flow-legenda"><span>✓ selesai</span><span>● berjalan</span><span>✗ gagal</span><span>- dilewati</span>'
        + '<span>· tidak dilalui (cabang lain)</span><span>geser bagan ke samping untuk langkah berikutnya</span></p>';
      const kanvas = wadah.querySelector('.alur-kanvas');
      pasangGeser(kanvas);
      // Gulir ke langkah yang sedang aktif; posisi geser pengguna dipertahankan selama langkah aktifnya sama.
      const fokus = a.simpul.find(s => s.status === 'berjalan') || a.simpul.find(s => s.status === 'gagal')
        || a.simpul.filter(s => s.status === 'selesai' && !s.cek).sort((p, q) => q.kol - p.kol)[0] || a.simpul[0];
      if (gulirLama !== null && wadah._fokus === fokus.id) kanvas.scrollLeft = gulirLama;
      else kanvas.scrollLeft = Math.max(0, t.x[fokus.kol] + t.lebarKol[fokus.kol] / 2 - kanvas.clientWidth / 2);
      wadah._fokus = fokus.id;
    }

    // Geser kanvas dengan mouse seperti n8n; sentuhan & tombol panah memakai gulir bawaan.
    function pasangGeser(kanvas) {
      let awal = null;
      kanvas.addEventListener('pointerdown', e => {
        if (e.pointerType !== 'mouse' || e.button !== 0) return;
        awal = { x: e.clientX, gulir: kanvas.scrollLeft };
        kanvas.classList.add('geser');
        kanvas.setPointerCapture(e.pointerId);
      });
      kanvas.addEventListener('pointermove', e => { if (awal) kanvas.scrollLeft = awal.gulir - (e.clientX - awal.x); });
      const lepas = () => { awal = null; kanvas.classList.remove('geser'); };
      kanvas.addEventListener('pointerup', lepas);
      kanvas.addEventListener('pointercancel', lepas);
    }
  window.AlurInstaller = { render: renderAlur, segmenRun };
})();
