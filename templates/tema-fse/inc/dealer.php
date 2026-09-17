<?php

/**
 * Situs dealer mobil (gaya beranda "dealer", mis. xpengjakartaindonesia.com).
 *
 * Data unit mobil adalah data berstruktur, jadi tinggal di CPT sendiri dengan
 * meta-nya (konvensi user 2026-09-14) — bukan kartu statis di halaman. Field
 * disunting PM lewat plugin Meta Box; tanpa plugin itu nilainya tetap terbaca
 * (post meta biasa) dan hanya UI-nya yang tidak tampil.
 *
 * Yang khas dealer: spesifikasi, pilihan warna, harga OTR, dan simulasi kredit.
 * Semuanya dirender blok dinamis tema supaya bisa dipakai di template maupun di
 * isi halaman, dan tetap satu sumber data.
 */

defined('ABSPATH') || exit;

/** Situs dealer? Gaya beranda ditulis scripts/fse-apply ke opsi velocity_situs. */
function velocity_fse_dealer()
{
    return velocity_fse_situs('gaya') === 'dealer';
}

/** Prefix meta unit mobil. */
const VELOCITY_FSE_MOBIL_META = array(
    'daya'          => 'vfse_mobil_daya',
    'torsi'         => 'vfse_mobil_torsi',
    'jarak'         => 'vfse_mobil_jarak',
    'harga'         => 'vfse_mobil_harga',
    'harga_catatan' => 'vfse_mobil_harga_catatan',
    'urut'          => 'vfse_mobil_urut',
);

add_action('init', function () {
    if (!velocity_fse_dealer()) {
        return;
    }
    register_post_type('mobil', array(
        'labels' => array(
            'name' => 'Model Unit', 'singular_name' => 'Model Unit', 'menu_name' => 'Model Unit',
            'add_new_item' => 'Tambah Model Unit', 'edit_item' => 'Edit Model Unit',
            'new_item' => 'Model Unit Baru', 'view_item' => 'Lihat Model Unit',
            'search_items' => 'Cari Model Unit', 'not_found' => 'Belum ada model unit.',
        ),
        'public' => true, 'show_in_rest' => true, 'has_archive' => true,
        'rewrite' => array('slug' => 'model-unit', 'with_front' => false),
        'menu_icon' => 'dashicons-car',
        'menu_position' => 5,
        'supports' => array('title', 'editor', 'thumbnail', 'excerpt', 'page-attributes'),
    ));

    foreach (VELOCITY_FSE_MOBIL_META as $meta) {
        register_post_meta('mobil', $meta, array(
            'show_in_rest' => true,
            'single'       => true,
            'type'         => in_array($meta, array('vfse_mobil_harga', 'vfse_mobil_urut'), true) ? 'number' : 'string',
            'auth_callback' => function () {
                return current_user_can('edit_posts');
            },
        ));
    }
});

// Arsip model unit: unit terlama di atas kalau PM mengisi urutan, judul kalau tidak.
add_action('pre_get_posts', function ($q) {
    if (is_admin() || !$q->is_main_query() || !velocity_fse_dealer()) {
        return;
    }
    if ($q->is_post_type_archive('mobil')) {
        $q->set('posts_per_page', 12);
        $q->set('orderby', array('menu_order' => 'ASC', 'date' => 'ASC'));
    }
});

// Pencarian yang dibatasi ke model unit tetap memakai tampilan arsipnya (aturan
// user 2026-09-14), bukan search.html.
add_filter('search_template_hierarchy', function ($templat) {
    if (!velocity_fse_dealer()) {
        return $templat;
    }
    $jenis = get_query_var('post_type');
    $jenis = is_array($jenis) ? $jenis : array_filter(array($jenis));
    if ($jenis && $jenis !== array('any') && !array_diff($jenis, array('mobil'))) {
        array_unshift($templat, 'archive-mobil');
    }
    return $templat;
});

// "Model Unit Lainnya" di halaman unit: buang unit yang sedang dibuka. Query Loop
// tidak punya opsi "kecuali tulisan ini", jadi exclude diisi saat render.
add_filter('query_loop_block_query_vars', function ($vars, $block) {
    if (is_singular('mobil') && ($vars['post_type'] ?? '') === 'mobil' && empty($vars['post__not_in'])) {
        $vars['post__not_in'] = array((int) get_queried_object_id());
    }
    return $vars;
}, 10, 2);

// Arsip tulisan & kategori situs dealer memakai templates/archive-dealer.html
// (pita judul + pengantar tengah + grid tiga kartu berbadge tanggal) — mengikuti
// tampilan halaman artikel referensi klien. Halaman tulisan (page_for_posts) ikut.
foreach (array('home', 'category', 'tag', 'taxonomy', 'archive', 'author', 'date') as $jenis_arsip) {
    add_filter($jenis_arsip . '_template_hierarchy', function ($templat) {
        if (velocity_fse_dealer()) {
            array_unshift($templat, 'archive-dealer');
        }
        return $templat;
    });
}

// Halaman biasa situs dealer memakai templates/page-dealer.html: pita judul gelap
// (judul + slogan + tombol ajakan) seperti halaman referensi klien.
add_filter('page_template_hierarchy', function ($templat) {
    // Halaman yang templatnya dipilih sendiri di editor (mis. "Halaman lebar") tidak diambil alih.
    $pilihan = get_page_template_slug(get_queried_object_id());
    if (velocity_fse_dealer() && !$pilihan) {
        array_unshift($templat, 'page-dealer');
    }
    return $templat;
});

// Arsip model unit punya templatnya sendiri: jangan tertimpa archive-dealer.
add_filter('archive_template_hierarchy', function ($templat) {
    if (velocity_fse_dealer() && is_post_type_archive('mobil')) {
        return array_values(array_diff($templat, array('archive-dealer')));
    }
    return $templat;
}, 11);

/** Meta satu unit mobil, sudah dinormalkan untuk ditampilkan. */
function velocity_fse_mobil($post_id = 0)
{
    $post_id = $post_id ? (int) $post_id : (int) get_the_ID();
    $ambil = function ($kunci) use ($post_id) {
        return trim((string) get_post_meta($post_id, VELOCITY_FSE_MOBIL_META[$kunci], true));
    };
    $harga = $ambil('harga');
    return array(
        'id'            => $post_id,
        'nama'          => get_the_title($post_id),
        'url'           => get_permalink($post_id),
        'daya'          => $ambil('daya'),
        'torsi'         => $ambil('torsi'),
        'jarak'         => $ambil('jarak'),
        'harga'         => $harga === '' ? 0 : (float) $harga,
        'harga_catatan' => $ambil('harga_catatan'),
        'warna'         => velocity_fse_mobil_daftar($post_id, 'vfse_mobil_warna', array('nama', 'hex')),
        'spek'          => velocity_fse_mobil_daftar($post_id, 'vfse_mobil_spek', array('label', 'nilai')),
    );
}

/**
 * Daftar berulang (warna, spesifikasi) dari field Meta Box `fieldset_text` + clone.
 *
 * Plugin gratis menyimpannya sebagai SATU meta berisi array klon; kalau field
 * ditulis lewat WP-CLI bentuknya bisa juga satu baris meta per klon. Keduanya
 * diterima supaya data tidak hilang tergantung cara pengisiannya.
 */
function velocity_fse_mobil_daftar($post_id, $meta, $kolom)
{
    $mentah = get_post_meta((int) $post_id, $meta, true);
    if (!is_array($mentah) || !$mentah) {
        $mentah = get_post_meta((int) $post_id, $meta, false);
    }
    $hasil = array();
    foreach ((array) $mentah as $baris) {
        if (!is_array($baris)) {
            continue;
        }
        $isi = array();
        foreach ($kolom as $k) {
            $isi[$k] = trim((string) ($baris[$k] ?? ''));
        }
        if ($isi[$kolom[0]] !== '') {
            $hasil[] = $isi;
        }
    }
    return $hasil;
}

/** "Rp 695.000.000". number_format_i18n memberi koma di situs ber-locale en_US. */
function velocity_fse_rupiah($angka)
{
    return 'Rp ' . number_format((float) $angka, 0, ',', '.');
}

/** Harga siap tampil; unit tanpa harga tidak boleh dikarang angkanya. */
function velocity_fse_mobil_harga_teks($mobil)
{
    if (empty($mobil['harga'])) {
        return 'Hubungi kami untuk harga OTR';
    }
    $catatan = $mobil['harga_catatan'] !== '' ? ' – ' . $mobil['harga_catatan'] : '';
    return velocity_fse_rupiah($mobil['harga']) . $catatan;
}

/** Semua unit mobil terbit, urut menu_order lalu tanggal. */
function velocity_fse_mobil_semua($jumlah = 12)
{
    if (!velocity_fse_dealer()) {
        return array();
    }
    $posts = get_posts(array(
        'post_type' => 'mobil', 'post_status' => 'publish', 'numberposts' => (int) $jumlah,
        'orderby' => array('menu_order' => 'ASC', 'date' => 'ASC'),
    ));
    return array_map('velocity_fse_mobil', wp_list_pluck($posts, 'ID'));
}

// Formulir kiriman di situs dealer menanyakan keperluan & model yang diminati,
// bukan "Layanan yang Dibutuhkan" bawaan situs jasa.
add_filter('velocity_fse_form_kolom', function ($kolom) {
    if (!velocity_fse_dealer()) {
        return $kolom;
    }
    $model = array();
    foreach (velocity_fse_mobil_semua(20) as $m) {
        $model[] = $m['nama'];
    }
    $kolom['jenis'] = array(
        'label' => 'Keperluan', 'type' => 'select', 'wajib' => true,
        'opsi'  => array('Test Drive', 'Simulasi Kredit', 'Informasi Harga & Promo', 'Ketersediaan Unit', 'Lainnya'),
    );
    if ($model) {
        $sisipkan = array('model' => array(
            'label' => 'Model yang Diminati', 'type' => 'select', 'wajib' => false,
            'opsi'  => array_merge($model, array('Belum menentukan')),
        ));
        // Model tampil setelah keperluan, sebelum kota.
        $urut = array();
        foreach ($kolom as $nama => $isi) {
            $urut[$nama] = $isi;
            if ($nama === 'jenis') {
                $urut += $sisipkan;
            }
        }
        $kolom = $urut;
    }
    return $kolom;
}, 10);

// Field Meta Box: UI paling mudah untuk PM (konvensi user 2026-09-14). Field
// `group` butuh ekstensi berbayar, jadi daftar berulang memakai fieldset_text + clone.
add_filter('rwmb_meta_boxes', function ($boxes) {
    if (!velocity_fse_dealer()) {
        return $boxes;
    }
    $boxes[] = array(
        'title'      => 'Data Unit',
        'post_types' => array('mobil'),
        'context'    => 'normal',
        'priority'   => 'high',
        'fields'     => array(
            array('id' => 'vfse_mobil_daya', 'name' => 'Max Power', 'type' => 'text', 'placeholder' => '190 kW'),
            array('id' => 'vfse_mobil_torsi', 'name' => 'Torque', 'type' => 'text', 'placeholder' => '440 Nm'),
            array('id' => 'vfse_mobil_jarak', 'name' => 'Jarak Tempuh', 'type' => 'text', 'placeholder' => '435 km'),
            array('id' => 'vfse_mobil_harga', 'name' => 'Harga (angka saja)', 'type' => 'number', 'min' => 0, 'step' => 1000000,
                'desc' => 'Kosongkan kalau harga belum dipastikan — situs akan menulis "Hubungi kami untuk harga OTR".'),
            array('id' => 'vfse_mobil_harga_catatan', 'name' => 'Catatan harga', 'type' => 'text', 'placeholder' => 'OTR Jakarta'),
            array('id' => 'vfse_mobil_warna', 'name' => 'Pilihan Warna', 'type' => 'fieldset_text', 'clone' => true,
                'sort_clone' => true, 'options' => array('nama' => 'Nama warna', 'hex' => 'Kode warna (#rrggbb)')),
            array('id' => 'vfse_mobil_spek', 'name' => 'Spesifikasi', 'type' => 'fieldset_text', 'clone' => true,
                'sort_clone' => true, 'options' => array('label' => 'Bagian', 'nilai' => 'Keterangan')),
            array('id' => 'vfse_mobil_urut', 'name' => 'Urutan tampil', 'type' => 'number', 'min' => 0,
                'desc' => 'Dipakai kalau kolom "Urutan" WordPress tidak diisi.'),
        ),
    );
    return $boxes;
});

// Meta Box belum aktif: PM tetap bisa mengisi lewat kotak sederhana ini, dan
// data yang sudah ada tidak hilang. Field sama, nilai sama.
add_action('add_meta_boxes', function () {
    if (!velocity_fse_dealer() || class_exists('RWMB_Loader')) {
        return;
    }
    add_meta_box('vfse-mobil', 'Data Unit', function ($post) {
        wp_nonce_field('vfse_mobil', 'vfse_mobil_nonce');
        $baris = array(
            'vfse_mobil_daya' => array('Max Power', '190 kW'),
            'vfse_mobil_torsi' => array('Torque', '440 Nm'),
            'vfse_mobil_jarak' => array('Jarak Tempuh', '435 km'),
            'vfse_mobil_harga' => array('Harga (angka saja)', '695000000'),
            'vfse_mobil_harga_catatan' => array('Catatan harga', 'OTR Jakarta'),
        );
        echo '<p><em>Plugin Meta Box belum aktif; pilihan warna & spesifikasi disunting setelah plugin dipasang.</em></p>';
        foreach ($baris as $meta => $label) {
            printf('<p><label style="display:block;font-weight:600">%s</label><input type="text" name="%s" value="%s" placeholder="%s" class="widefat"></p>',
                esc_html($label[0]), esc_attr($meta), esc_attr((string) get_post_meta($post->ID, $meta, true)), esc_attr($label[1]));
        }
    }, 'mobil', 'normal', 'high');
});

add_action('save_post_mobil', function ($post_id) {
    if (!isset($_POST['vfse_mobil_nonce']) || !wp_verify_nonce($_POST['vfse_mobil_nonce'], 'vfse_mobil')
        || !current_user_can('edit_post', $post_id)) {
        return;
    }
    foreach (array('vfse_mobil_daya', 'vfse_mobil_torsi', 'vfse_mobil_jarak', 'vfse_mobil_harga', 'vfse_mobil_harga_catatan') as $meta) {
        if (isset($_POST[$meta])) {
            update_post_meta($post_id, $meta, sanitize_text_field(wp_unslash($_POST[$meta])));
        }
    }
});
