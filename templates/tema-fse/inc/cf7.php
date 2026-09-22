<?php

/**
 * Formulir situs lewat Contact Form 7 (keputusan user 2026-09-19): kolom bisa ditambah,
 * diubah, dan dihapus sendiri di menu Contact, captcha tetap milik velocity-addons.
 *
 * - velocity_fse_cf7_pastikan(): membuat satu form bawaan dari kolom yang sama dengan
 *   form lama (velocity_fse_form_kolom) — dipanggil fse-apply, yang lalu menaruh blok
 *   Contact Form 7 di halaman.
 * - Blok lama velocity/form-kirim ikut menampilkan form CF7 ini kalau ada.
 * - velocity-addons hanya MENAMPILKAN tag [velocity_captcha] di CF7, tidak memeriksanya;
 *   pemeriksaannya ada di sini (filter wpcf7_validate).
 * - Kiriman tetap diarsipkan ke Pesan Masuk (velocity_pesan), jadi data tidak hilang
 *   kalau mail server menolak.
 */

defined('ABSPATH') || exit;

const VELOCITY_FSE_CF7_OPSI = 'velocity_fse_cf7_form';
const VELOCITY_FSE_CF7_CAPTCHA = 'vf-captcha';

// Markup form ditulis sendiri (grid .vf-form), jadi <p>/<br> otomatis CF7 hanya merusaknya.
add_filter('wpcf7_autop_or_not', '__return_false');

/** Isi tab "Form" CF7 dari kolom form tema. */
function velocity_fse_cf7_isi_form()
{
    $baris = array();
    foreach (velocity_fse_form_kolom() as $nama => $k) {
        $id = 'vf-' . $nama;
        $tipe = $k['type'] . (!empty($k['wajib']) ? '*' : '');
        $opsi = array($id, 'id:' . $id);
        if (!empty($k['autocomplete'])) {
            $opsi[] = 'autocomplete:' . $k['autocomplete'];
        }
        if ($k['type'] === 'textarea') {
            $opsi[] = '40x4';
        }
        $tag = '[' . $tipe . ' ' . implode(' ', $opsi);
        if ($k['type'] === 'select') {
            foreach ($k['opsi'] as $o) {
                $tag .= ' "' . str_replace('"', "'", $o) . '"';
            }
        } elseif (!empty($k['placeholder'])) {
            $tag .= ' placeholder "' . str_replace('"', "'", $k['placeholder']) . '"';
        }
        $tag .= ']';
        $label = esc_html($k['label']) . (!empty($k['wajib']) ? ' <span aria-hidden="true">*</span>' : '');
        $bantuan = !empty($k['catatan']) ? "\n" . '<small class="vf-form__bantuan">' . esc_html($k['catatan']) . '</small>' : '';
        $baris[] = sprintf('<p class="vf-form__baris%s"><label for="%s">%s</label>%s' . "\n" . '%s</p>',
            $k['type'] === 'textarea' ? ' vf-form__penuh' : '', $id, $label, $bantuan, $tag);
    }
    $baris[] = '<div class="vf-form__penuh">[velocity_captcha]</div>';
    $kirim = '[submit class:wp-element-button "' . str_replace('"', "'", velocity_fse_form_tombol()) . '"]';
    $wa = velocity_fse_wa_link();
    if ($wa) {
        $kirim .= "\n" . '<a href="' . esc_url($wa) . '" target="_blank" rel="noopener nofollow">Atau chat WhatsApp</a>';
    }
    $baris[] = '<p class="vf-form__kirim vf-form__penuh">' . $kirim . '</p>';
    $baris[] = '<p class="vf-form__catatan vf-form__penuh">Data Anda hanya dipakai untuk menindaklanjuti pesan ini.</p>';
    return '<div class="vf-form">' . "\n" . implode("\n\n", $baris) . "\n" . '</div>';
}

/** Tab "Mail" CF7: ke email situs, From domain sendiri (Gmail menolak From domain lain). */
function velocity_fse_cf7_mail()
{
    $host = wp_parse_url(home_url(), PHP_URL_HOST);
    $isi = array();
    foreach (velocity_fse_form_kolom() as $nama => $k) {
        $isi[] = $k['label'] . ': [vf-' . $nama . ']';
    }
    return array(
        'active'             => true,
        'recipient'          => velocity_fse_situs('email') ? velocity_fse_situs('email') : get_option('admin_email'),
        'sender'             => '[_site_title] <noreply@' . $host . '>',
        'subject'            => 'Pesan baru dari website: [vf-nama]',
        'additional_headers' => 'Reply-To: [vf-email]',
        'body'               => "Pesan baru masuk dari [_site_url]\n\n" . implode("\n", $isi) . "\n",
        'attachments'        => '',
        'use_html'           => false,
        'exclude_blank'      => false,
    );
}

/**
 * Form bawaan situs: dibuat sekali, lalu milik klien (tidak ditimpa lagi).
 * Hasil: id, hash, title — bahan blok contact-form-7/contact-form-selector.
 */
function velocity_fse_cf7_pastikan()
{
    if (!class_exists('WPCF7_ContactForm')) {
        return null;
    }
    $id = (int) get_option(VELOCITY_FSE_CF7_OPSI);
    $form = $id ? wpcf7_contact_form($id) : null;
    if (!$form) {
        $form = WPCF7_ContactForm::get_template(array('title' => 'Formulir ' . get_bloginfo('name')));
        $form->set_properties(array('form' => velocity_fse_cf7_isi_form(), 'mail' => velocity_fse_cf7_mail()));
        $id = (int) $form->save();
        if (!$id) {
            return null;
        }
        update_option(VELOCITY_FSE_CF7_OPSI, $id, false);
        $form = wpcf7_contact_form($id);
        update_post_meta($id, '_velocity_fse_md5', md5((string) $form->prop('form')));
    }
    return array('id' => (int) $form->id(), 'hash' => (string) $form->hash(), 'title' => (string) $form->title());
}

/** Shortcode form bawaan (untuk blok lama velocity/form-kirim); kosong kalau belum ada. */
function velocity_fse_cf7_shortcode()
{
    $id = (int) get_option(VELOCITY_FSE_CF7_OPSI);
    if (!$id || !function_exists('wpcf7_contact_form') || !($form = wpcf7_contact_form($id))) {
        return '';
    }
    return do_shortcode('[contact-form-7 id="' . esc_attr($form->hash()) . '" title="' . esc_attr($form->title()) . '"]');
}

// Tag [velocity_captcha] didaftar ulang (setelah velocity-addons) supaya dibungkus
// .wpcf7-form-control-wrap: di situlah CF7 menaruh pesan "captcha salah".
// wpcf7_add_form_tag() tidak menimpa tag yang sudah ada, jadi milik plugin dilepas dulu.
add_action('wpcf7_init', function () {
    if (!function_exists('velocity_fse_captcha')) {
        return;
    }
    wpcf7_remove_form_tag('velocity_captcha');
    wpcf7_add_form_tag('velocity_captcha', function () {
        $captcha = velocity_fse_captcha();
        if (trim($captcha) === '') {
            return '';
        }
        return '<span class="wpcf7-form-control-wrap" data-name="' . VELOCITY_FSE_CF7_CAPTCHA . '">' . $captcha . '</span>';
    });
}, 20);

add_filter('wpcf7_validate', function ($result, $tags) {
    $ada = false;
    foreach ((array) $tags as $tag) {
        if (isset($tag->type) && $tag->type === 'velocity_captcha') {
            $ada = true;
            break;
        }
    }
    // verify() sudah lolos sendiri kalau captcha dimatikan atau pengunjung login.
    if (!$ada || !class_exists('Velocity_Addons_Captcha')) {
        return $result;
    }
    $captcha = new Velocity_Addons_Captcha();
    $hasil = $captcha->verify(isset($_POST['g-recaptcha-response']) ? (string) wp_unslash($_POST['g-recaptcha-response']) : null);
    if (empty($hasil['success'])) {
        $result->invalidate(array('type' => 'velocity_captcha', 'name' => VELOCITY_FSE_CF7_CAPTCHA),
            apply_filters('velocity_fse_cf7_pesan_captcha', 'Kode captcha belum benar. Silakan ulangi.'));
    }
    return $result;
}, 20, 2);

// Kode captcha gambar sekali pakai: sesudah tiap kiriman gambarnya diganti dan isiannya dikosongkan.
add_action('wp_enqueue_scripts', function () {
    wp_add_inline_script('contact-form-7', "document.addEventListener('wpcf7submit',function(e){"
        . "e.target.querySelectorAll('[data-name=\"" . VELOCITY_FSE_CF7_CAPTCHA . "\"]').forEach(function(w){"
        . "var i=w.querySelector('img');if(i){i.src=i.src.split('&r=')[0]+'&r='+Date.now();}"
        . "var t=w.querySelector('input[name=\"vd_captcha_input\"]');if(t){t.value='';}"
        . "if(window.grecaptcha&&w.querySelector('[id^=\"grr\"]')){try{grecaptcha.reset();}catch(x){}}});});");
}, 20);

// Arsip ke Pesan Masuk sebelum email dikirim.
add_action('wpcf7_before_send_mail', function ($form, &$batal, $kiriman) {
    if (!$kiriman || !post_type_exists('velocity_pesan')) {
        return;
    }
    $label = array();
    if (preg_match_all('/<label for="([^"]+)">(.*?)<\/label>/s', (string) $form->prop('form'), $m, PREG_SET_ORDER)) {
        foreach ($m as $l) {
            $label[$l[1]] = trim(wp_strip_all_tags($l[2]), " *\t\n");
        }
    }
    $baris = array();
    $nama = '';
    foreach ((array) $kiriman->get_posted_data() as $k => $v) {
        if ($k === '' || $k[0] === '_' || strpos($k, 'vd_captcha') === 0 || $k === 'g-recaptcha-response') {
            continue;
        }
        $v = is_array($v) ? implode(', ', $v) : (string) $v;
        $nama = $nama === '' && $v !== '' ? $v : $nama;
        $baris[] = (isset($label[$k]) ? $label[$k] : $k) . ': ' . ($v !== '' ? $v : '-');
    }
    wp_insert_post(array(
        'post_type'    => 'velocity_pesan',
        'post_status'  => 'private',
        'post_title'   => sprintf('%s — %s', $nama !== '' ? $nama : 'Pesan', $form->title()),
        'post_content' => implode("\n", $baris),
    ));
}, 10, 3);
