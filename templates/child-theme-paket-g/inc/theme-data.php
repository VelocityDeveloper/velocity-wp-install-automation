<?php

/**
 * Satu-satunya tempat mengubah isi desain.
 *
 * Nama, kontak, dan alamat diambil dari FORM ISIAN klien. Hero, layanan, produk,
 * keunggulan, alur, dan galeri adalah ISI CONTOH yang ditulis dari data klien
 * (scripts/paket-g-konten): fakta dari form & dokumen didahulukan, bagian yang
 * tidak ada datanya diisi contoh yang wajar untuk bidang usahanya. Tetap perlu
 * dikonfirmasi bersama klien saat revisi.
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
                // Penerima form pemesanan — tidak ditampilkan ke pengunjung.
                'email'       => '{{EMAIL}}',
                // Email yang tampil di situs. Kosong kalau form hanya memuat email
                // pribadi pemilik (bagian biodata = data administrasi internal).
                'email_publik' => '{{EMAIL_PUBLIK}}',
                'alamat'      => '{{ALAMAT}}',
                'area'        => '{{AREA}}',
{{DATA_ISI}}
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
