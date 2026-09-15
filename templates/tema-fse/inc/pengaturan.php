<?php

/**
 * Tampilan → Data Situs: satu tempat menyunting identitas yang tampil di
 * header, footer, kolom samping, dan halaman Redaksi/Kontak.
 *
 * Nilai yang diikat Block Bindings tampil read-only di editor; di sinilah
 * nilainya diubah, lalu berubah di semua tempat sekaligus.
 */

defined('ABSPATH') || exit;

function velocity_fse_kolom_pengaturan()
{
    return array(
        'nama'         => array('Nama situs / media', 'text'),
        'slogan'       => array('Slogan', 'text'),
        'tentang'      => array('Tentang (footer & kolom samping)', 'textarea'),
        'email_publik' => array('Email publik', 'email'),
        'wa'           => array('Nomor WhatsApp publik (format 628…)', 'text'),
        'telp'         => array('Telepon (tampilan)', 'text'),
        'alamat'       => array('Alamat publik', 'textarea'),
        'area'         => array('Wilayah / kota', 'text'),
        'email'        => array('Email penerima formulir (tidak ditampilkan)', 'email'),
    );
}

add_action('admin_menu', function () {
    add_theme_page('Data Situs', 'Data Situs', 'edit_theme_options', 'velocity-data-situs', 'velocity_fse_halaman_pengaturan');
});

add_action('admin_init', function () {
    register_setting('velocity_data_situs', 'velocity_situs', array(
        'type'              => 'array',
        'sanitize_callback' => function ($masuk) {
            // Kunci yang tidak ada di form (jenis, rubrik, layanan) dipertahankan.
            $data = velocity_fse_situs();
            foreach (velocity_fse_kolom_pengaturan() as $kunci => $kolom) {
                if (!isset($masuk[$kunci])) {
                    continue;
                }
                $nilai = wp_unslash($masuk[$kunci]);
                $data[$kunci] = $kolom[1] === 'textarea' ? sanitize_textarea_field($nilai)
                    : ($kolom[1] === 'email' ? sanitize_email($nilai) : sanitize_text_field($nilai));
            }
            return $data;
        },
    ));
});

function velocity_fse_halaman_pengaturan()
{
    ?>
    <div class="wrap">
        <h1>Data Situs</h1>
        <p>Data ini tampil di header, footer, kolom samping, dan halaman kontak. Kosongkan kolom yang tidak ingin ditampilkan.</p>
        <form method="post" action="options.php">
            <?php settings_fields('velocity_data_situs'); ?>
            <table class="form-table" role="presentation">
                <?php foreach (velocity_fse_kolom_pengaturan() as $kunci => $kolom) :
                    $id = 'velocity-situs-' . $kunci;
                    $nilai = (string) velocity_fse_situs($kunci); ?>
                    <tr>
                        <th scope="row"><label for="<?php echo esc_attr($id); ?>"><?php echo esc_html($kolom[0]); ?></label></th>
                        <td>
                            <?php if ($kolom[1] === 'textarea') : ?>
                                <textarea id="<?php echo esc_attr($id); ?>" name="velocity_situs[<?php echo esc_attr($kunci); ?>]" rows="4" class="large-text"><?php echo esc_textarea($nilai); ?></textarea>
                            <?php else : ?>
                                <input type="<?php echo esc_attr($kolom[1]); ?>" id="<?php echo esc_attr($id); ?>" name="velocity_situs[<?php echo esc_attr($kunci); ?>]" value="<?php echo esc_attr($nilai); ?>" class="regular-text" />
                            <?php endif; ?>
                        </td>
                    </tr>
                <?php endforeach; ?>
            </table>
            <?php submit_button(); ?>
        </form>
    </div>
    <?php
}
