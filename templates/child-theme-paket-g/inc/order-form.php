<?php

/**
 * Form pemesanan → email.
 *
 * Permintaan klien di FORM ISIAN: "Sediakan form pemesanan yang ketika di isi
 * datanya akan masuk ke email". Selain dikirim ke email, setiap pemesanan juga
 * disimpan sebagai post privat `{{PREFIX}}_pemesanan` — kalau pengiriman email gagal
 * (antrean mail server penuh, alamat ditolak), datanya tidak ikut hilang.
 */

defined('ABSPATH') || exit;

if (!function_exists('{{PREFIX}}_form_fields')) {
    function {{PREFIX}}_form_fields()
    {
        return array(
            'nama'     => array('label' => 'Nama Lengkap', 'type' => 'text', 'wajib' => true, 'autocomplete' => 'name'),
            'wa'       => array('label' => 'Nomor WhatsApp', 'type' => 'tel', 'wajib' => true, 'autocomplete' => 'tel'),
            'email'    => array('label' => 'Email', 'type' => 'email', 'wajib' => false, 'autocomplete' => 'email'),
            'jenis'    => array('label' => 'Jenis Pekerjaan', 'type' => 'select', 'wajib' => true, 'opsi' => array(
                'Renovasi Rumah/Kantor', 'Interior & Furnitur', 'Bangun Baru', 'Desain & Konsultasi', 'Lainnya',
            )),
            'lokasi'   => array('label' => 'Lokasi Proyek', 'type' => 'text', 'wajib' => true, 'placeholder' => 'Contoh: Bintaro, Tangerang Selatan'),
            'luas'     => array('label' => 'Perkiraan Luas', 'type' => 'text', 'wajib' => false, 'placeholder' => 'Contoh: 90 m²'),
            'anggaran' => array('label' => 'Perkiraan Anggaran', 'type' => 'select', 'wajib' => false, 'opsi' => array(
                'Belum ditentukan', 'Di bawah 50 juta', '50 - 150 juta', '150 - 500 juta', 'Di atas 500 juta',
            )),
            'pesan'    => array('label' => 'Kebutuhan Anda', 'type' => 'textarea', 'wajib' => false, 'placeholder' => 'Ceritakan singkat kondisi bangunan dan yang ingin dikerjakan.'),
        );
    }
}

if (!function_exists('{{PREFIX}}_daftar_pemesanan')) {
    /** Tipe post privat untuk arsip pemesanan yang masuk. */
    function {{PREFIX}}_daftar_pemesanan()
    {
        register_post_type('{{PREFIX}}_pemesanan', array(
            'labels' => array(
                'name' => 'Pemesanan',
                'singular_name' => 'Pemesanan',
                'menu_name' => 'Pemesanan',
            ),
            'public' => false,
            'show_ui' => true,
            'show_in_menu' => true,
            'menu_icon' => 'dashicons-clipboard',
            'menu_position' => 26,
            'supports' => array('title', 'editor'),
            'capability_type' => 'post',
            'map_meta_cap' => true,
            'capabilities' => array('create_posts' => 'do_not_allow'),
            'exclude_from_search' => true,
            'has_archive' => false,
            'rewrite' => false,
        ));
    }
    add_action('init', '{{PREFIX}}_daftar_pemesanan');
}

if (!function_exists('{{PREFIX}}_form_nilai')) {
    /** Nilai satu field dari $_POST, sudah dibersihkan sesuai tipenya. */
    function {{PREFIX}}_form_nilai($name, $field)
    {
        $raw = isset($_POST['{{PREFIX}}'][$name]) ? wp_unslash($_POST['{{PREFIX}}'][$name]) : '';
        if ($field['type'] === 'email') {
            return sanitize_email($raw);
        }
        if ($field['type'] === 'textarea') {
            return sanitize_textarea_field($raw);
        }
        $value = sanitize_text_field($raw);
        if ($field['type'] === 'select' && !in_array($value, $field['opsi'], true)) {
            return '';
        }
        return $value;
    }
}

if (!function_exists('{{PREFIX}}_form_proses')) {
    /**
     * Pola Post/Redirect/Get: hasilnya dibawa lewat query arg supaya me-refresh
     * halaman tidak mengirim ulang pemesanan yang sama.
     */
    function {{PREFIX}}_form_proses()
    {
        if (empty($_POST['{{PREFIX}}_form_pemesanan'])) {
            return;
        }
        $kembali = wp_get_referer() ?: home_url('/');
        // Honeypot: diisi bot, tidak pernah diisi manusia (disembunyikan CSS).
        if (!empty($_POST['{{PREFIX}}_website'])) {
            wp_safe_redirect(add_query_arg('pesan', 'terkirim', $kembali) . '#pemesanan');
            exit;
        }
        if (!isset($_POST['{{PREFIX}}_nonce']) || !wp_verify_nonce(wp_unslash($_POST['{{PREFIX}}_nonce']), '{{PREFIX}}_pemesanan')) {
            wp_safe_redirect(add_query_arg('pesan', 'kedaluwarsa', $kembali) . '#pemesanan');
            exit;
        }
        // Satu IP maksimal 1 kirim per menit — menahan banjir kiriman otomatis.
        $ip = isset($_SERVER['REMOTE_ADDR']) ? sanitize_text_field(wp_unslash($_SERVER['REMOTE_ADDR'])) : '';
        $kunci = '{{PREFIX}}_kirim_' . md5($ip);
        if ($ip && get_transient($kunci)) {
            wp_safe_redirect(add_query_arg('pesan', 'terlalu_cepat', $kembali) . '#pemesanan');
            exit;
        }

        $fields = {{PREFIX}}_form_fields();
        $nilai = array();
        foreach ($fields as $name => $field) {
            $nilai[$name] = {{PREFIX}}_form_nilai($name, $field);
            if (!empty($field['wajib']) && $nilai[$name] === '') {
                wp_safe_redirect(add_query_arg('pesan', 'kurang', $kembali) . '#pemesanan');
                exit;
            }
        }
        if ($nilai['email'] !== '' && !is_email($nilai['email'])) {
            wp_safe_redirect(add_query_arg('pesan', 'email', $kembali) . '#pemesanan');
            exit;
        }
        set_transient($kunci, 1, MINUTE_IN_SECONDS);

        $baris = array();
        foreach ($fields as $name => $field) {
            $baris[] = $field['label'] . ': ' . ($nilai[$name] !== '' ? $nilai[$name] : '-');
        }
        $isi = implode("\n", $baris);

        // Arsip dulu, baru kirim: kalau mail server bermasalah, data tetap ada.
        wp_insert_post(array(
            'post_type'    => '{{PREFIX}}_pemesanan',
            'post_status'  => 'private',
            'post_title'   => sprintf('%s — %s (%s)', $nilai['nama'], $nilai['jenis'], $nilai['lokasi']),
            'post_content' => $isi,
        ));

        $situs = wp_parse_url(home_url(), PHP_URL_HOST);
        $headers = array(
            'Content-Type: text/plain; charset=UTF-8',
            // From wajib memakai domain situs sendiri, kalau tidak Gmail menolaknya.
            sprintf('From: %s <noreply@%s>', get_bloginfo('name'), $situs),
        );
        if ($nilai['email'] !== '') {
            $headers[] = 'Reply-To: ' . $nilai['nama'] . ' <' . $nilai['email'] . '>';
        }
        $terkirim = wp_mail(
            {{PREFIX}}_data('email'),
            'Pemesanan baru dari website: ' . $nilai['nama'],
            "Pemesanan baru masuk dari " . home_url('/') . "\n\n" . $isi . "\n\n"
                . "Balas langsung ke WhatsApp: https://wa.me/" . preg_replace('/^0/', '62', preg_replace('/\D/', '', $nilai['wa'])) . "\n",
            $headers
        );

        wp_safe_redirect(add_query_arg('pesan', $terkirim ? 'terkirim' : 'tersimpan', $kembali) . '#pemesanan');
        exit;
    }
    add_action('template_redirect', '{{PREFIX}}_form_proses');
}

if (!function_exists('{{PREFIX}}_form_notifikasi')) {
    function {{PREFIX}}_form_notifikasi()
    {
        $pesan = isset($_GET['pesan']) ? sanitize_key($_GET['pesan']) : '';
        $teks = array(
            'terkirim'      => array('ok', 'Terima kasih. Pemesanan Anda sudah kami terima dan akan segera dihubungi.'),
            'tersimpan'     => array('ok', 'Terima kasih. Pemesanan Anda tersimpan. Bila ingin lebih cepat, hubungi kami langsung via WhatsApp.'),
            'kurang'        => array('gagal', 'Mohon lengkapi nama, nomor WhatsApp, jenis pekerjaan, dan lokasi proyek.'),
            'email'         => array('gagal', 'Alamat email belum benar. Periksa kembali atau kosongkan saja.'),
            'kedaluwarsa'   => array('gagal', 'Halaman terlalu lama dibuka. Silakan kirim ulang formulirnya.'),
            'terlalu_cepat' => array('gagal', 'Pemesanan Anda barusan sudah terkirim. Tunggu sebentar sebelum mengirim lagi.'),
        );
        if (!isset($teks[$pesan])) {
            return;
        }
        printf('<p class="{{PREFIX}}-notif {{PREFIX}}-notif--%s" role="status">%s</p>',
            esc_attr($teks[$pesan][0]), esc_html($teks[$pesan][1]));
    }
}

if (!function_exists('{{PREFIX}}_form_render')) {
    function {{PREFIX}}_form_render()
    {
        $fields = {{PREFIX}}_form_fields();
        ob_start();
        ?>
        <form class="{{PREFIX}}-form" method="post" action="<?php echo esc_url(home_url(add_query_arg(array()))); ?>#pemesanan">
            <?php {{PREFIX}}_form_notifikasi(); ?>
            <?php foreach ($fields as $name => $field) :
                $id = '{{PREFIX}}-' . $name;
                $lebar = in_array($name, array('pesan'), true) ? ' {{PREFIX}}-form__baris--penuh' : ''; ?>
                <p class="{{PREFIX}}-form__baris<?php echo esc_attr($lebar); ?>">
                    <label for="<?php echo esc_attr($id); ?>">
                        <?php echo esc_html($field['label']); ?>
                        <?php if (!empty($field['wajib'])) : ?><span aria-hidden="true">*</span><?php endif; ?>
                    </label>
                    <?php if ($field['type'] === 'select') : ?>
                        <select id="<?php echo esc_attr($id); ?>" name="{{PREFIX}}[<?php echo esc_attr($name); ?>]" <?php echo !empty($field['wajib']) ? 'required' : ''; ?>>
                            <?php foreach ($field['opsi'] as $opsi) : ?>
                                <option value="<?php echo esc_attr($opsi); ?>"><?php echo esc_html($opsi); ?></option>
                            <?php endforeach; ?>
                        </select>
                    <?php elseif ($field['type'] === 'textarea') : ?>
                        <textarea id="<?php echo esc_attr($id); ?>" name="{{PREFIX}}[<?php echo esc_attr($name); ?>]" rows="4"
                            placeholder="<?php echo esc_attr(isset($field['placeholder']) ? $field['placeholder'] : ''); ?>"></textarea>
                    <?php else : ?>
                        <input type="<?php echo esc_attr($field['type']); ?>" id="<?php echo esc_attr($id); ?>"
                            name="{{PREFIX}}[<?php echo esc_attr($name); ?>]"
                            placeholder="<?php echo esc_attr(isset($field['placeholder']) ? $field['placeholder'] : ''); ?>"
                            autocomplete="<?php echo esc_attr(isset($field['autocomplete']) ? $field['autocomplete'] : 'off'); ?>"
                            <?php echo !empty($field['wajib']) ? 'required' : ''; ?> />
                    <?php endif; ?>
                </p>
            <?php endforeach; ?>
            <p class="{{PREFIX}}-form__jebakan" aria-hidden="true">
                <label for="{{PREFIX}}-website">Website</label>
                <input type="text" id="{{PREFIX}}-website" name="{{PREFIX}}_website" tabindex="-1" autocomplete="off" />
            </p>
            <?php wp_nonce_field('{{PREFIX}}_pemesanan', '{{PREFIX}}_nonce'); ?>
            <p class="{{PREFIX}}-form__kirim">
                <button type="submit" name="{{PREFIX}}_form_pemesanan" value="1" class="{{PREFIX}}-btn {{PREFIX}}-btn--utama">Kirim Pemesanan</button>
                <a class="{{PREFIX}}-btn {{PREFIX}}-btn--garis" href="<?php echo esc_url({{PREFIX}}_wa_link()); ?>" target="_blank" rel="noopener nofollow">Atau chat WhatsApp</a>
            </p>
            <p class="{{PREFIX}}-form__catatan">Data Anda hanya dipakai untuk menindaklanjuti permintaan ini.</p>
        </form>
        <?php
        return ob_get_clean();
    }
}
