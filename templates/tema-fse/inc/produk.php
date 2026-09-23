<?php

/**
 * Katalog produk sebagai CPT `produk` + taksonomi `kategori-produk`.
 *
 * Dinyalakan lewat Data Situs `cpt_produk` = true (manifest `cpt_produk=1`), sama seperti
 * gaya dealer: situs yang tidak memakainya tidak melihat menu tambahan di wp-admin.
 * Keputusan user 2026-09-20 (sonarmuda99.com): tiap barang punya halaman sendiri dan
 * pemilik situs bisa menambah barang baru tanpa menyentuh susunan halaman.
 *
 * Arsip CPT dimatikan: daftar produk tetap halaman "Produk" milik installer supaya
 * susunannya (chip penyaring + bar ajakan) bisa diatur seperti halaman lain.
 */

defined('ABSPATH') || exit;

function velocity_fse_cpt_produk()
{
    // Toko VD Store: produk = `store_product`, dan slug /produk/ sudah dipakai arsipnya.
    return velocity_fse_situs('cpt_produk') === true && !velocity_fse_vd_store();
}

add_action('init', function () {
    if (!velocity_fse_cpt_produk()) {
        return;
    }
    register_post_type('produk', array(
        'labels' => array(
            'name' => 'Produk', 'singular_name' => 'Produk', 'menu_name' => 'Produk',
            'add_new_item' => 'Tambah Produk', 'edit_item' => 'Edit Produk',
            'new_item' => 'Produk Baru', 'view_item' => 'Lihat Produk',
            'search_items' => 'Cari Produk', 'not_found' => 'Belum ada produk.',
        ),
        'public' => true, 'show_in_rest' => true, 'has_archive' => false,
        'rewrite' => array('slug' => 'produk', 'with_front' => false),
        'menu_icon' => 'dashicons-archive',
        'menu_position' => 5,
        'supports' => array('title', 'editor', 'thumbnail', 'excerpt', 'page-attributes'),
    ));
    register_taxonomy('kategori-produk', array('produk'), array(
        'labels' => array(
            'name' => 'Kategori Produk', 'singular_name' => 'Kategori Produk',
            'menu_name' => 'Kategori', 'add_new_item' => 'Tambah Kategori',
        ),
        'public' => true, 'show_in_rest' => true, 'hierarchical' => true,
        'rewrite' => array('slug' => 'kategori-produk', 'with_front' => false),
    ));
});

/**
 * Kelas `vf-kat-<slug>` pada tiap item Query Loop produk: dipakai chip penyaring
 * kategori di halaman (assets/js lewat inc/referensi-komponen.php) tanpa AJAX.
 */
add_filter('post_class', function ($kelas, $tambahan, $id) {
    if (!velocity_fse_cpt_produk() || get_post_type($id) !== 'produk') {
        return $kelas;
    }
    foreach (get_the_terms($id, 'kategori-produk') ?: array() as $t) {
        $kelas[] = 'vf-kat-' . $t->slug;
    }
    $kelas[] = 'vc-produk-kartu';
    return $kelas;
}, 10, 3);
