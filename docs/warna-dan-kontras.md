# Memilih warna situs tanpa mengorbankan keterbacaan

Klien menyebut warna dengan kata ("biru", "dibedakan dari web contoh"), bukan
dengan angka. Yang menerjemahkannya jadi palet situs adalah automation, jadi
aturan main di bawah ini ditegakkan mesin — bukan diserahkan ke perasaan.

Alat pemeriksanya: `scripts/cek-warna-tema` (jalankan setiap kali
`templates/child-theme-paket-g/css/custom.css` disunting).

## Aturan pokok

1. **Teks di atas warna tidak pernah dipilih manual.** Generator menghitung
   luminansi relatif WCAG lalu memilih putih atau tinta — mana yang rasionya
   lebih tinggi. Hasilnya jadi token `--<prefix>-di-primary` (teks di atas warna
   utama) dan `--<prefix>-di-aksen` (teks di atas warna aksen).
2. **Ambangnya 4.5:1**, yaitu syarat teks badan WCAG AA. Warna yang tidak
   mencapainya digeser sampai lolos, dan penyesuaiannya dilaporkan
   (`kontras=utama:#707070/#ffffff:5.0(disesuaikan dari #7a7a7a)`).
3. **Turunan warna ikut diperiksa.** `primary-2` dan `primary-3` juga dipakai
   sebagai latar (footer, panel menu, gradasi hero), jadi keduanya diselaraskan
   terhadap warna teks yang sudah dipilih — bukan dibiarkan hasil perhitungan
   gelap/terang mentah.
4. **Warna aksen adalah warna tombol, bukan warna teks di latar terang.** Amber
   `#fca311` bagus sebagai latar tombol (teks gelap di atasnya 8.5:1), tetapi
   jadi teks di atas putih hanya ±2:1. Untuk tautan di latar terang, pakai warna
   utama; aksen dipakai sebagai latar atau untuk teks di atas latar gelap.

## Jebakan yang memakan korban di sini

**Spesifisitas CSS mengalahkan urutan.** Aturan judul global
`body.<prefix> h1..h4 { color: ink }` bernilai (0,1,2), sedangkan aturan
komponen seperti `.<prefix>-hero__judul { color: putih }` hanya (0,1,0). Yang
menang adalah yang global — jadi **seluruh judul di latar gelap, termasuk judul
hero, tampil hitam** walaupun ada aturan putih di bawahnya. Menaruh aturan lebih
akhir di berkas tidak menolong; seri baru diputuskan urutan kalau nilainya sama.

Karena itu semua aturan permukaan gelap memakai awalan `body.<prefix>` (nilainya
jadi (0,2,2)) dan diberi komentar peringatan di CSS-nya. Dan karena "ada aturan
warnanya" ternyata bukan bukti, `cek-warna-tema` menghitung aturan mana yang
benar-benar menang untuk tiap elemen uji.

**Jangan mengandalkan penimpaan satu per satu.** Judul yang ditulis PM
belakangan, atau blok baru di template, tidak akan punya aturan sendiri. Setiap
permukaan gelap karena itu mewarnai *semua* keturunannya:

```css
body.<prefix> .<prefix>-seksi--gelap :is(h1, h2, h3, h4, h5, h6) {
  color: var(--<prefix>-di-primary);
}
```

**Logo bertulisan gelap hilang di header gelap.** Logo contoh dibuat dengan
tulisan tinta agar terbaca di latar terang, sehingga di header berwarna ia perlu
alas putih (`.<prefix>-header__merek img`) — atau pakai berkas `logo-terang`
dari `scripts/velocity-logo`.

## Cara memeriksa

```bash
scripts/cek-warna-tema                              # 4 palet bawaan
scripts/cek-warna-tema --palet "#0b3c5d,#17a2b8"    # palet lain
```

Keluarannya menyebut rasio paling tipis per warna dan, untuk tiap elemen uji,
warna yang benar-benar menang di kaskade. Kode keluar bukan 0 kalau ada yang
gagal, jadi bisa dipasang sebagai penjaga di `deploy.sh`.
