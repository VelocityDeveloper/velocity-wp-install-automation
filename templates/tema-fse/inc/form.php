<?php

/**
 * Formulir kiriman pengunjung → email (blok velocity/form-kirim).
 *
 * Situs perusahaan: form pemesanan ("datanya masuk ke email", permintaan tetap
 * Paket G). Portal berita: "Kirim Pesan ke Redaksi". Setiap kiriman juga
 * disimpan sebagai post privat `velocity_pesan`, jadi data tidak hilang kalau
 * mail server menolak.
 *
 * Penyaring spam: captcha velocity-addons, honeypot, nonce, dan batas satu
 * kiriman per menit per IP (sama dengan child theme Paket G sebelumnya).
 */

defined('ABSPATH') || exit;

/**
 * Captcha velocity-addons.
 *
 * JEBAKAN: plugin versi 1.6.x hanya mendaftarkan shortcode `[velocity_recaptcha]`
 * (untuk form login), bukan `[velocity_captcha]`. `do_shortcode()` mengembalikan
 * teks aslinya ketika tag tidak terdaftar, sehingga "[velocity_captcha]" sempat
 * tercetak mentah di halaman Hubungi Kami. Jadi: pakai shortcode hanya kalau
 * benar-benar terdaftar, lalu kelas captcha plugin (dibuat baru — plugin memuat
 * kelasnya di dalam method sehingga tidak pernah jadi global), lalu menyerah.
 */
function velocity_fse_captcha()
{
    if (shortcode_exists('velocity_captcha')) {
        return do_shortcode('[velocity_captcha]');
    }
    if (!class_exists('Velocity_Addons_Captcha')) {
        return '';
    }
    $captcha = new Velocity_Addons_Captcha();
    if (method_exists($captcha, 'isActive') && !$captcha->isActive()) {
        return '';
    }
    if (!method_exists($captcha, 'display')) {
        return '';
    }
    ob_start();
    $captcha->display();
    return (string) ob_get_clean();
}


function velocity_fse_form_kolom()
{
    $berita = velocity_fse_jenis_berita();
    $layanan = array();
    foreach ((array) velocity_fse_situs('layanan') as $l) {
        if (!empty($l['judul'])) {
            $layanan[] = (string) $l['judul'];
        }
    }
    $kolom = array(
        'nama'   => array('label' => 'Nama Lengkap', 'type' => 'text', 'wajib' => true, 'autocomplete' => 'name'),
        'wa'     => array('label' => 'Nomor WhatsApp', 'type' => 'tel', 'wajib' => true, 'autocomplete' => 'tel'),
        'email'  => array('label' => 'Email', 'type' => 'email', 'wajib' => false, 'autocomplete' => 'email'),
        'jenis'  => $berita
            ? array('label' => 'Keperluan', 'type' => 'select', 'wajib' => true,
                'opsi' => array('Kirim Berita / Informasi', 'Pemasangan Iklan', 'Kerja Sama', 'Lainnya'))
            : array('label' => 'Layanan yang Dibutuhkan', 'type' => 'select', 'wajib' => true,
                'opsi' => array_merge($layanan ? $layanan : array('Konsultasi'), array('Lainnya'))),
        'lokasi' => array('label' => 'Kota / Lokasi', 'type' => 'text', 'wajib' => !$berita,
            'placeholder' => 'Contoh: ' . (velocity_fse_situs('area') ? velocity_fse_situs('area') : 'Jakarta')),
        'pesan'  => array('label' => $berita ? 'Pesan' : 'Kebutuhan Anda', 'type' => 'textarea', 'wajib' => $berita,
            'placeholder' => $berita ? 'Tulis pesan atau informasi untuk redaksi.' : 'Ceritakan singkat kebutuhan Anda.'),
    );
    // Kolom versi klien dari Data Situs (kunci `form`, ditulis installer dari company profile):
    // urutan, label, pilihan, dan catatan mengikuti klien. Kunci yang dipakai pengolah
    // kiriman (nama, wa, email, jenis) selalu ada.
    $atur = velocity_fse_situs('form');
    if (is_array($atur) && !empty($atur['kolom']) && is_array($atur['kolom'])) {
        $boleh = array_flip(array('label', 'type', 'wajib', 'placeholder', 'opsi', 'autocomplete', 'catatan'));
        $baru = array();
        foreach ($atur['kolom'] as $nama => $ubah) {
            $nama = sanitize_key($nama);
            $dasar = isset($kolom[$nama]) ? $kolom[$nama] : array('label' => $nama, 'type' => 'text', 'wajib' => false);
            $k = array_merge($dasar, array_intersect_key((array) $ubah, $boleh));
            if (!in_array($k['type'], array('text', 'tel', 'email', 'select', 'textarea'), true)
                || ($k['type'] === 'select' && empty($k['opsi']))) {
                $k = $dasar;
            }
            $baru[$nama] = $k;
        }
        foreach (array('nama', 'wa', 'email', 'jenis') as $perlu) {
            if (!isset($baru[$perlu])) {
                $baru[$perlu] = $kolom[$perlu];
            }
        }
        $kolom = $baru;
    }
    return apply_filters('velocity_fse_form_kolom', $kolom);
}

function velocity_fse_form_tombol()
{
    $atur = velocity_fse_situs('form');
    if (is_array($atur) && !empty($atur['tombol'])) {
        return (string) $atur['tombol'];
    }
    return (velocity_fse_jenis_berita() || velocity_fse_dealer()) ? 'Kirim Pesan' : 'Kirim Pemesanan';
}

add_action('init', function () {
    // Sejak formulir situs memakai Contact Form 7 (keputusan user 2026-09-19), pesan tidak lagi
    // masuk ke CPT ini. Menu "Pesan Masuk" yang selalu kosong hanya menambah kebingungan, jadi
    // CPT-nya dilewati kalau CF7 yang dipakai DAN belum ada satu pun pesan tersimpan.
    if (defined('VELOCITY_FSE_CF7_OPSI') && (int) get_option(VELOCITY_FSE_CF7_OPSI)) {
        global $wpdb;
        if (!(int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts} WHERE post_type = 'velocity_pesan'")) {
            return;
        }
    }
    register_post_type('velocity_pesan', array(
        'labels'              => array('name' => 'Pesan Masuk', 'singular_name' => 'Pesan', 'menu_name' => 'Pesan Masuk'),
        'public'              => false,
        'show_ui'             => true,
        'show_in_menu'        => true,
        'menu_icon'           => 'dashicons-email-alt',
        'menu_position'       => 26,
        'supports'            => array('title', 'editor'),
        'capability_type'     => 'post',
        'map_meta_cap'        => true,
        'capabilities'        => array('create_posts' => 'do_not_allow'),
        'exclude_from_search' => true,
        'rewrite'             => false,
    ));
});

function velocity_fse_form_nilai($nama, $kolom)
{
    $mentah = isset($_POST['vf'][$nama]) ? wp_unslash($_POST['vf'][$nama]) : '';
    if ($kolom['type'] === 'email') {
        return sanitize_email($mentah);
    }
    if ($kolom['type'] === 'textarea') {
        return sanitize_textarea_field($mentah);
    }
    $nilai = sanitize_text_field($mentah);
    return ($kolom['type'] === 'select' && !in_array($nilai, $kolom['opsi'], true)) ? '' : $nilai;
}

/** Post/Redirect/Get: me-refresh halaman tidak mengirim ulang kiriman yang sama. */
add_action('template_redirect', function () {
    if (empty($_POST['vf_form_kirim'])) {
        return;
    }
    // wp_get_referer() kosong bila referer = URL yang sedang diminta (form dikirim ke
    // halamannya sendiri), sehingga pengunjung terlempar ke beranda
    // (jasakontraktorindo.com 2026-09-17). Referer mentah divalidasi sendiri.
    $kembali = wp_validate_redirect(remove_query_arg('pesan', strtok((string) wp_get_raw_referer(), '#')), home_url('/'));
    $ke = function ($pesan) use ($kembali) {
        wp_safe_redirect(add_query_arg('pesan', $pesan, $kembali) . '#formulir');
        exit;
    };
    // Honeypot: diisi bot, tidak pernah diisi manusia (disembunyikan CSS).
    if (!empty($_POST['vf_website'])) {
        $ke('terkirim');
    }
    if (!isset($_POST['vf_nonce']) || !wp_verify_nonce(wp_unslash($_POST['vf_nonce']), 'velocity_fse_form')) {
        $ke('kedaluwarsa');
    }
    // Captcha velocity-addons. Kelasnya dimuat plugin lewat require_once di dalam
    // method sehingga objek plugin tidak pernah global — dibuat sendiri di sini.
    // verify() sudah lolos sendiri kalau captcha dimatikan atau pengunjung login.
    if (class_exists('Velocity_Addons_Captcha')) {
        $captcha = new Velocity_Addons_Captcha();
        $hasil = $captcha->verify();
        if (empty($hasil['success'])) {
            $ke('captcha');
        }
    }
    $ip = isset($_SERVER['REMOTE_ADDR']) ? sanitize_text_field(wp_unslash($_SERVER['REMOTE_ADDR'])) : '';
    $kunci = 'vf_kirim_' . md5($ip);
    if ($ip && get_transient($kunci)) {
        $ke('terlalu_cepat');
    }

    $kolom = velocity_fse_form_kolom();
    $nilai = array();
    foreach ($kolom as $nama => $k) {
        $nilai[$nama] = velocity_fse_form_nilai($nama, $k);
        if (!empty($k['wajib']) && $nilai[$nama] === '') {
            $ke('kurang');
        }
    }
    if ($nilai['email'] !== '' && !is_email($nilai['email'])) {
        $ke('email');
    }
    set_transient($kunci, 1, MINUTE_IN_SECONDS);

    $baris = array();
    foreach ($kolom as $nama => $k) {
        $baris[] = $k['label'] . ': ' . ($nilai[$nama] !== '' ? $nilai[$nama] : '-');
    }
    $isi = implode("\n", $baris);

    // Arsip dulu, baru kirim: kalau mail server bermasalah, data tetap ada.
    wp_insert_post(array(
        'post_type'    => 'velocity_pesan',
        'post_status'  => 'private',
        'post_title'   => sprintf('%s — %s', $nilai['nama'], $nilai['jenis']),
        'post_content' => $isi,
    ));

    $host = wp_parse_url(home_url(), PHP_URL_HOST);
    $header = array(
        'Content-Type: text/plain; charset=UTF-8',
        // From wajib memakai domain situs sendiri, kalau tidak Gmail menolaknya.
        sprintf('From: %s <noreply@%s>', get_bloginfo('name'), $host),
    );
    if ($nilai['email'] !== '') {
        $header[] = 'Reply-To: ' . $nilai['nama'] . ' <' . $nilai['email'] . '>';
    }
    $penerima = velocity_fse_situs('email') ? velocity_fse_situs('email') : get_option('admin_email');
    $terkirim = wp_mail(
        $penerima,
        'Pesan baru dari website: ' . $nilai['nama'],
        'Pesan baru masuk dari ' . home_url('/') . "\n\n" . $isi . "\n\n"
            . 'Balas langsung ke WhatsApp: https://wa.me/' . preg_replace('/^0/', '62', preg_replace('/\D/', '', $nilai['wa'])) . "\n",
        $header
    );
    $ke($terkirim ? 'terkirim' : 'tersimpan');
});

function velocity_fse_form_render()
{
    $teks = array(
        'terkirim'      => array('ok', 'Terima kasih. Pesan Anda sudah kami terima dan akan segera ditindaklanjuti.'),
        'tersimpan'     => array('ok', 'Terima kasih. Pesan Anda tersimpan dan akan segera kami tindak lanjuti.'),
        'kurang'        => array('gagal', 'Mohon lengkapi semua kolom bertanda *.'),
        'email'         => array('gagal', 'Alamat email belum benar. Periksa kembali atau kosongkan saja.'),
        'kedaluwarsa'   => array('gagal', 'Halaman terlalu lama dibuka. Silakan kirim ulang formulirnya.'),
        'captcha'       => array('gagal', 'Verifikasi captcha belum benar. Silakan ulangi.'),
        'terlalu_cepat' => array('gagal', 'Pesan Anda barusan sudah terkirim. Tunggu sebentar sebelum mengirim lagi.'),
    );
    $pesan = isset($_GET['pesan']) ? sanitize_key(wp_unslash($_GET['pesan'])) : '';
    $wa = velocity_fse_wa_link();
    ob_start();
    ?>
    <form class="vf-form" id="formulir" method="post" action="<?php echo esc_url(get_permalink() ? get_permalink() : home_url('/')); ?>#formulir">
        <?php if (isset($teks[$pesan])) : ?>
            <p class="vf-notif vf-notif--<?php echo esc_attr($teks[$pesan][0]); ?> vf-form__penuh" role="status"><?php echo esc_html($teks[$pesan][1]); ?></p>
        <?php endif; ?>
        <?php foreach (velocity_fse_form_kolom() as $nama => $k) :
            $id = 'vf-' . $nama;
            $wajib = !empty($k['wajib']);
            $ph = isset($k['placeholder']) ? $k['placeholder'] : ''; ?>
            <p class="vf-form__baris<?php echo $k['type'] === 'textarea' ? ' vf-form__penuh' : ''; ?>">
                <label for="<?php echo esc_attr($id); ?>"><?php echo esc_html($k['label']); ?><?php if ($wajib) : ?> <span aria-hidden="true">*</span><?php endif; ?></label>
                <?php if (!empty($k['catatan'])) : ?>
                    <small class="vf-form__bantuan"><?php echo esc_html($k['catatan']); ?></small>
                <?php endif; ?>
                <?php if ($k['type'] === 'select') : ?>
                    <select id="<?php echo esc_attr($id); ?>" name="vf[<?php echo esc_attr($nama); ?>]"<?php echo $wajib ? ' required' : ''; ?>>
                        <?php foreach ($k['opsi'] as $opsi) : ?>
                            <option value="<?php echo esc_attr($opsi); ?>"><?php echo esc_html($opsi); ?></option>
                        <?php endforeach; ?>
                    </select>
                <?php elseif ($k['type'] === 'textarea') : ?>
                    <textarea id="<?php echo esc_attr($id); ?>" name="vf[<?php echo esc_attr($nama); ?>]" rows="4" placeholder="<?php echo esc_attr($ph); ?>"<?php echo $wajib ? ' required' : ''; ?>></textarea>
                <?php else : ?>
                    <input type="<?php echo esc_attr($k['type']); ?>" id="<?php echo esc_attr($id); ?>" name="vf[<?php echo esc_attr($nama); ?>]" placeholder="<?php echo esc_attr($ph); ?>" autocomplete="<?php echo esc_attr(isset($k['autocomplete']) ? $k['autocomplete'] : 'off'); ?>"<?php echo $wajib ? ' required' : ''; ?> />
                <?php endif; ?>
            </p>
        <?php endforeach; ?>
        <?php
        // Captcha milik velocity-addons (penyedia & pengaturannya di wp-admin);
        // kosong kalau dimatikan, dan form tetap dijaga honeypot + nonce + batas kirim.
        $captcha = velocity_fse_captcha();
        if (trim($captcha) !== '') : ?>
            <div class="vf-form__penuh"><?php echo $captcha; ?></div>
        <?php endif; ?>
        <p class="vf-form__jebakan" aria-hidden="true">
            <label for="vf-website">Website</label>
            <input type="text" id="vf-website" name="vf_website" tabindex="-1" autocomplete="off" />
        </p>
        <?php wp_nonce_field('velocity_fse_form', 'vf_nonce'); ?>
        <p class="vf-form__kirim vf-form__penuh">
            <button type="submit" name="vf_form_kirim" value="1" class="wp-element-button"><?php echo esc_html(velocity_fse_form_tombol()); ?></button>
            <?php if ($wa) : ?>
                <a href="<?php echo esc_url($wa); ?>" target="_blank" rel="noopener nofollow">Atau chat WhatsApp</a>
            <?php endif; ?>
        </p>
        <p class="vf-form__catatan vf-form__penuh">Data Anda hanya dipakai untuk menindaklanjuti pesan ini.</p>
    </form>
    <?php
    return ob_get_clean();
}
