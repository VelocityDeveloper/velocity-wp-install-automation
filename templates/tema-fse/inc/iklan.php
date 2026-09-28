<?php

/**
 * Tampilan → Iklan: gambar, tautan & tampil/sembunyi tiap slot blok velocity/iklan
 * (permintaan user 2026-09-28). Slot disisipkan installer/agen di beranda, arsip, dan artikel
 * portal berita; gambarnya diganti di sini tanpa menyunting template.
 */

defined('ABSPATH') || exit;

function velocity_fse_slot_iklan()
{
    return array(
        'atas'    => 'Di bawah header (semua halaman yang memakainya)',
        'sela-1'  => 'Sela beranda 1',
        'sela-2'  => 'Sela beranda 2',
        'sela-3'  => 'Sela beranda 3',
        'sela-4'  => 'Sela beranda 4',
        'arsip'   => 'Daftar tulisan (rubrik, tag, pencarian)',
        'artikel' => 'Di dalam artikel (sesudah isi)',
        'samping' => 'Kolom samping',
    );
}

function velocity_fse_iklan($slot)
{
    $semua = get_option('velocity_iklan', array());
    $atur = is_array($semua) && isset($semua[$slot]) && is_array($semua[$slot]) ? $semua[$slot] : array();
    return array(
        'gambar'   => isset($atur['gambar']) ? (int) $atur['gambar'] : 0,
        'url'      => isset($atur['url']) ? (string) $atur['url'] : '',
        'alt'      => isset($atur['alt']) ? (string) $atur['alt'] : '',
        'sembunyi' => !empty($atur['sembunyi']),
    );
}

add_action('admin_menu', function () {
    add_theme_page('Iklan', 'Iklan', 'edit_theme_options', 'velocity-iklan', 'velocity_fse_halaman_iklan');
});

add_action('admin_init', function () {
    register_setting('velocity_iklan', 'velocity_iklan', array(
        'type'              => 'array',
        'sanitize_callback' => function ($masuk) {
            $hasil = array();
            foreach (array_keys(velocity_fse_slot_iklan()) as $slot) {
                $m = isset($masuk[$slot]) && is_array($masuk[$slot]) ? wp_unslash($masuk[$slot]) : array();
                $hasil[$slot] = array(
                    'gambar'   => isset($m['gambar']) ? absint($m['gambar']) : 0,
                    'url'      => isset($m['url']) ? esc_url_raw(trim((string) $m['url'])) : '',
                    'alt'      => isset($m['alt']) ? sanitize_text_field($m['alt']) : '',
                    'sembunyi' => !empty($m['sembunyi']),
                );
            }
            return $hasil;
        },
    ));
});

add_action('admin_enqueue_scripts', function ($hook) {
    if ($hook === 'appearance_page_velocity-iklan') {
        wp_enqueue_media();
    }
});

function velocity_fse_halaman_iklan()
{
    ?>
    <div class="wrap">
        <h1>Iklan</h1>
        <p>Ganti gambar tiap slot iklan di sini. Slot tanpa gambar tampil sebagai kotak &ldquo;Ruang Iklan&rdquo; yang tertaut ke halaman Hubungi Kami; centang &ldquo;Sembunyikan&rdquo; untuk tidak menampilkannya sama sekali. Posisi slot diatur di Tampilan &rarr; Editor (blok &ldquo;Iklan&rdquo;).</p>
        <form method="post" action="options.php">
            <?php settings_fields('velocity_iklan'); ?>
            <table class="form-table" role="presentation">
                <?php foreach (velocity_fse_slot_iklan() as $slot => $label) :
                    $atur = velocity_fse_iklan($slot);
                    $nama = 'velocity_iklan[' . $slot . ']';
                    $pratinjau = $atur['gambar'] ? wp_get_attachment_image_url($atur['gambar'], 'medium') : ''; ?>
                    <tr class="vf-slot-iklan">
                        <th scope="row"><?php echo esc_html($label); ?><br><code><?php echo esc_html($slot); ?></code></th>
                        <td>
                            <p><img class="vf-slot-iklan__pratinjau" src="<?php echo esc_url($pratinjau); ?>" alt="" style="max-width:320px;height:auto;<?php echo $pratinjau ? '' : 'display:none;'; ?>"></p>
                            <input type="hidden" class="vf-slot-iklan__id" name="<?php echo esc_attr($nama); ?>[gambar]" value="<?php echo esc_attr($atur['gambar'] ?: ''); ?>">
                            <button type="button" class="button vf-slot-iklan__pilih">Pilih / ganti gambar</button>
                            <button type="button" class="button-link-delete vf-slot-iklan__hapus"<?php echo $atur['gambar'] ? '' : ' style="display:none"'; ?>>Hapus gambar</button>
                            <p><label>Tautan (kosong = Hubungi Kami)<br><input type="url" class="regular-text" name="<?php echo esc_attr($nama); ?>[url]" value="<?php echo esc_attr($atur['url']); ?>" placeholder="https://"></label></p>
                            <p><label>Teks alternatif gambar<br><input type="text" class="regular-text" name="<?php echo esc_attr($nama); ?>[alt]" value="<?php echo esc_attr($atur['alt']); ?>"></label></p>
                            <p><label><input type="checkbox" name="<?php echo esc_attr($nama); ?>[sembunyi]" value="1" <?php checked($atur['sembunyi']); ?>> Sembunyikan slot ini</label></p>
                        </td>
                    </tr>
                <?php endforeach; ?>
            </table>
            <?php submit_button(); ?>
        </form>
    </div>
    <script>
    document.querySelectorAll('.vf-slot-iklan').forEach(function (baris) {
        var id = baris.querySelector('.vf-slot-iklan__id');
        var img = baris.querySelector('.vf-slot-iklan__pratinjau');
        var hapus = baris.querySelector('.vf-slot-iklan__hapus');
        baris.querySelector('.vf-slot-iklan__pilih').addEventListener('click', function () {
            var bingkai = wp.media({ title: 'Gambar iklan', library: { type: 'image' }, multiple: false });
            bingkai.on('select', function () {
                var a = bingkai.state().get('selection').first().toJSON();
                id.value = a.id;
                img.src = (a.sizes && a.sizes.medium ? a.sizes.medium.url : a.url);
                img.style.display = '';
                hapus.style.display = '';
            });
            bingkai.open();
        });
        hapus.addEventListener('click', function () {
            id.value = '';
            img.style.display = 'none';
            hapus.style.display = 'none';
        });
    });
    </script>
    <?php
}
