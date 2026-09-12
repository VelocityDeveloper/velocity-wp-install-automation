<?php

/**
 * Satu-satunya tempat mengubah isi desain.
 *
 * Nama, kontak, dan alamat diisi otomatis dari FORM ISIAN klien saat child theme
 * dibuat. Bagian di bawahnya (layanan, produk, keunggulan, alur, galeri) adalah
 * isian awal yang wajar untuk situs perusahaan — WAJIB disunting bersama klien,
 * jangan diterbitkan apa adanya.
 */

defined('ABSPATH') || exit;

if (!function_exists('{{PREFIX}}_data')) {
    function {{PREFIX}}_data($key = null)
    {
        static $data = null;
        if ($data === null) {
            $data = array(
                // --- diisi dari form klien ---
                'nama'        => '{{NAMA}}',
                'wa'          => '{{WA}}',
                'telp'        => '{{TELP}}',
                'email'       => '{{EMAIL}}',
                'alamat'      => '{{ALAMAT}}',
                'area'        => '{{AREA}}',
                'hero_judul'  => '{{NAMA}}',
                'hero_teks'   => 'Sampaikan kebutuhan Anda dan tim kami akan menindaklanjutinya. Konsultasi awal tanpa biaya.',
                'hero_poin'   => array('Ditangani tim sendiri', 'Penawaran tertulis sebelum pengerjaan', 'Area layanan {{AREA}}'),

                // --- isian awal, wajib direvisi bersama klien ---
                'layanan' => array(
                    array(
                        'slug' => 'satu',
                        'judul' => 'Layanan Utama',
                        'teks' => 'Jelaskan layanan utama perusahaan di sini, beserta manfaat yang didapat pelanggan.',
                        'rincian' => array('Rincian pertama', 'Rincian kedua', 'Rincian ketiga'),
                    ),
                    array(
                        'slug' => 'dua',
                        'judul' => 'Layanan Kedua',
                        'teks' => 'Jelaskan layanan kedua di sini.',
                        'rincian' => array('Rincian pertama', 'Rincian kedua', 'Rincian ketiga'),
                    ),
                    array(
                        'slug' => 'tiga',
                        'judul' => 'Layanan Ketiga',
                        'teks' => 'Jelaskan layanan ketiga di sini.',
                        'rincian' => array('Rincian pertama', 'Rincian kedua', 'Rincian ketiga'),
                    ),
                    array(
                        'slug' => 'empat',
                        'judul' => 'Layanan Keempat',
                        'teks' => 'Jelaskan layanan keempat di sini.',
                        'rincian' => array('Rincian pertama', 'Rincian kedua', 'Rincian ketiga'),
                    ),
                ),
                'produk' => array(
                    array('slug' => 'produk-1', 'judul' => 'Produk Pertama', 'teks' => 'Keterangan singkat produk.'),
                    array('slug' => 'produk-2', 'judul' => 'Produk Kedua', 'teks' => 'Keterangan singkat produk.'),
                    array('slug' => 'produk-3', 'judul' => 'Produk Ketiga', 'teks' => 'Keterangan singkat produk.'),
                    array('slug' => 'produk-4', 'judul' => 'Produk Keempat', 'teks' => 'Keterangan singkat produk.'),
                ),
                'keunggulan' => array(
                    array('ikon' => 'area', 'judul' => 'Area Layanan Jelas', 'teks' => 'Melayani wilayah {{AREA}}.'),
                    array('ikon' => 'satu', 'judul' => 'Satu Pintu', 'teks' => 'Kebutuhan Anda ditangani satu tim dari awal sampai selesai.'),
                    array('ikon' => 'rab', 'judul' => 'Lingkup & Biaya Tertulis', 'teks' => 'Ruang lingkup dan biaya disepakati sebelum pengerjaan.'),
                    array('ikon' => 'chat', 'judul' => 'Konsultasi Dulu', 'teks' => 'Sampaikan rencana Anda lewat WhatsApp atau form pemesanan.'),
                ),
                'alur' => array(
                    array('judul' => 'Konsultasi', 'teks' => 'Ceritakan kebutuhan dan perkiraan anggaran Anda.'),
                    array('judul' => 'Peninjauan', 'teks' => 'Kebutuhan diperiksa agar penawarannya tepat.'),
                    array('judul' => 'Penawaran', 'teks' => 'Ruang lingkup dan rincian biaya disusun tertulis.'),
                    array('judul' => 'Pengerjaan', 'teks' => 'Pekerjaan berjalan dengan perkembangan yang dilaporkan.'),
                    array('judul' => 'Serah Terima', 'teks' => 'Pemeriksaan akhir bersama sebelum pekerjaan ditutup.'),
                ),
                'galeri' => array(
                    array('slug' => 'galeri-1', 'judul' => 'Dokumentasi 1'),
                    array('slug' => 'galeri-2', 'judul' => 'Dokumentasi 2'),
                    array('slug' => 'galeri-3', 'judul' => 'Dokumentasi 3'),
                    array('slug' => 'galeri-4', 'judul' => 'Dokumentasi 4'),
                    array('slug' => 'galeri-5', 'judul' => 'Dokumentasi 5'),
                    array('slug' => 'galeri-6', 'judul' => 'Dokumentasi 6'),
                ),
            );
            $data = apply_filters('{{PREFIX}}_data', $data);
        }
        if ($key === null) {
            return $data;
        }
        return isset($data[$key]) ? $data[$key] : '';
    }
}

if (!function_exists('{{PREFIX}}_wa_link')) {
    /** Tautan WhatsApp dengan pesan awal yang sudah terisi. */
    function {{PREFIX}}_wa_link($pesan = '')
    {
        $nomor = preg_replace('/\D/', '', {{PREFIX}}_data('wa'));
        if (!$nomor) {
            return 'mailto:' . {{PREFIX}}_data('email');
        }
        $pesan = $pesan ?: 'Halo ' . {{PREFIX}}_data('nama') . ', saya ingin bertanya.';
        return 'https://wa.me/' . $nomor . '?text=' . rawurlencode($pesan);
    }
}
