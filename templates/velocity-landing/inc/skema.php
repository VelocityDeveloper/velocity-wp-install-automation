<?php
/**
 * Skema isi landing page: satu sumber untuk kontrol Customizer, nilai bawaan,
 * dan daftar setting per seksi (selective refresh).
 *
 * Kunci theme_mod = vlp_{seksi}_{field}. Isi bawaan = isi lp.velocitydeveloper.com
 * (landing catering) supaya tema langsung tampil lengkap sesudah diaktifkan.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;

/**
 * URL gambar bawaan di folder tema.
 */
function vlp_aset($berkas)
{
	return get_stylesheet_directory_uri() . '/assets/img/' . $berkas;
}

/**
 * Daftar seksi beranda sesuai urutan tampil. Seksi `umum` dan `footer` tidak ikut urutan.
 */
function vlp_urutan()
{
	return array('hero', 'masalah', 'solusi', 'pentingnya', 'layanan', 'keunggulan', 'mengapa', 'paket', 'jenis', 'kepercayaan', 'faq');
}

/**
 * Skema lengkap. Tiap field: type (text|textarea|image|url|color|checkbox|select|ikon|repeater),
 * label, default, description (opsional), choices (select). Repeater menyimpan JSON daftar item
 * (bisa ditambah/dihapus/diurutkan); `fields` = field per item, `default` = array item.
 */
function vlp_skema()
{
	static $skema = null;
	if (null !== $skema) {
		return $skema;
	}

	$tampil = array('type' => 'checkbox', 'label' => 'Tampilkan seksi ini', 'default' => true);
	$link_wa = 'Kosongkan agar tombol membuka WhatsApp (nomor di "Umum & Warna").';

	$skema = array(
		'umum' => array(
			'title'  => 'Umum & Warna',
			'fields' => array(
				'wa_nomor'    => array('type' => 'text', 'label' => 'Nomor WhatsApp', 'default' => '628123456789', 'description' => 'Format internasional tanpa + atau spasi, mis. 6281234567890.'),
				'wa_pesan'    => array('type' => 'textarea', 'label' => 'Pesan awal WhatsApp', 'default' => '', 'description' => 'Opsional. Teks yang otomatis terisi saat pengunjung membuka WhatsApp.'),
				'tab_baru'    => array('type' => 'checkbox', 'label' => 'Buka tautan tombol di tab baru', 'default' => true),
				'font'        => array('type' => 'select', 'label' => 'Font', 'default' => 'Montserrat', 'choices' => array(
					'Montserrat'        => 'Montserrat',
					'Poppins'           => 'Poppins',
					'Plus Jakarta Sans' => 'Plus Jakarta Sans',
					'Inter'             => 'Inter',
					'Nunito'            => 'Nunito',
					'Open Sans'         => 'Open Sans',
				)),
				'warna_latar'  => array('type' => 'color', 'label' => 'Warna latar', 'default' => '#191919'),
				'warna_teks'   => array('type' => 'color', 'label' => 'Warna teks', 'default' => '#ffffff'),
				'warna_utama'  => array('type' => 'color', 'label' => 'Warna utama (kartu & tombol)', 'default' => '#4b125e'),
				'warna_aksen'  => array('type' => 'color', 'label' => 'Warna aksen (ikon, garis, tombol paket)', 'default' => '#aa3acf'),
				'warna_sorot'  => array('type' => 'color', 'label' => 'Warna cahaya kartu', 'default' => '#67008a'),
				'warna_cahaya' => array('type' => 'color', 'label' => 'Warna cahaya kedua (latar)', 'default' => '#c5c73e'),
				'warna_footer' => array('type' => 'color', 'label' => 'Warna latar footer', 'default' => '#000000'),
				'efek_cahaya'  => array('type' => 'checkbox', 'label' => 'Tampilkan efek cahaya di latar', 'default' => true),
			),
		),

		'hero' => array(
			'title'  => '1. Pembuka (Hero)',
			'fields' => array(
				'tampil'       => $tampil,
				'judul'        => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Mau mengadakan acara tapi tidak punya waktu untuk persiapan makanan?'),
				'teks'         => array('type' => 'textarea', 'label' => 'Teks', 'default' => 'Melayani catering harian, nasi box kantor, acara keluarga, pengajian, rapat, hingga berbagai event khusus dengan pilihan menu yang variatif, higienis, dan diolah menggunakan bahan-bahan berkualitas. Setiap hidangan disiapkan dengan proses memasak yang bersih dan terjaga agar menghasilkan cita rasa lezat serta aman dikonsumsi oleh semua kalangan. Kami juga menyediakan pilihan paket yang fleksibel dan dapat disesuaikan dengan kebutuhan jumlah porsi maupun jenis menu, sehingga cocok untuk kebutuhan pribadi, instansi, maupun kegiatan berskala besar dengan harga yang tetap terjangkau.'),
				'tombol_label' => array('type' => 'text', 'label' => 'Tulisan tombol', 'default' => 'Pesan Sekarang', 'description' => 'Kosongkan untuk menyembunyikan tombol.'),
				'tombol_link'  => array('type' => 'url', 'label' => 'Tautan tombol', 'default' => '', 'description' => $link_wa),
				'gambar'       => array('type' => 'image', 'label' => 'Gambar', 'default' => vlp_aset('hero.webp')),
			),
		),

		'masalah' => array(
			'title'  => '2. Masalah Pelanggan',
			'fields' => array(
				'tampil' => $tampil,
				'gambar' => array('type' => 'image', 'label' => 'Gambar', 'default' => vlp_aset('masalah.webp')),
				'judul'  => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Apakah Anda Mengalami Hal Berikut Ini?'),
				'ikon'   => array('type' => 'ikon', 'label' => 'Ikon butir', 'default' => 'fa-solid fa-face-surprise'),
				'butir'  => array('type' => 'textarea', 'label' => 'Daftar masalah', 'description' => 'Satu butir per baris.', 'default' => "Sering bingung mencari catering yang tepat waktu untuk kebutuhan kantor atau rapat?\nKhawatir kualitas rasa dan kebersihan makanan tidak sesuai harapan?\nButuh paket nasi box praktis dengan menu lengkap dan harga terjangkau?"),
			),
		),

		'solusi' => array(
			'title'  => '3. Solusi',
			'fields' => array(
				'tampil' => $tampil,
				'judul'  => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Masih Bingung Mencari Catering yang Tepat untuk Kebutuhan Acara Anda?'),
				'teks'   => array('type' => 'textarea', 'label' => 'Teks', 'description' => 'Pisahkan paragraf dengan satu baris kosong.', 'default' => "Banyak pelanggan sudah merencanakan acara dengan baik, tetapi sering mengalami kesulitan menemukan layanan catering yang rasanya enak, higienis, dan tepat waktu. Tidak jarang makanan datang terlambat, menu tidak sesuai harapan, atau pilihan paket kurang fleksibel dengan kebutuhan acara.\n\nDi sinilah layanan catering yang profesional menjadi penting. Kami hadir membantu menyediakan pilihan menu yang lengkap, proses pemesanan yang mudah, serta pelayanan yang tepat waktu sehingga Anda bisa fokus menjalankan acara tanpa repot memikirkan konsumsi. Dengan pilihan paket yang fleksibel dan harga terjangkau, kebutuhan makan harian maupun acara khusus dapat terpenuhi dengan lebih praktis dan nyaman."),
				'gambar' => array('type' => 'image', 'label' => 'Gambar', 'default' => vlp_aset('solusi.webp')),
			),
		),

		'pentingnya' => array(
			'title'  => '4. Mengapa Penting',
			'fields' => array(
				'tampil' => $tampil,
				'gambar' => array('type' => 'image', 'label' => 'Gambar', 'default' => vlp_aset('pentingnya.webp')),
				'judul'  => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Menentukan Catering yang Tepat Sangat Berpengaruh pada Kelancaran Acara Anda'),
				'teks'   => array('type' => 'textarea', 'label' => 'Teks', 'description' => 'Pisahkan paragraf dengan satu baris kosong.', 'default' => "Dalam setiap kegiatan, konsumsi menjadi salah satu faktor penting yang mempengaruhi kenyamanan peserta. Menu yang sesuai, rasa yang konsisten, serta penyajian yang rapi akan memberikan kesan positif bagi tamu maupun peserta acara. Karena itu, memilih layanan catering tidak bisa dilakukan secara asal.\n\nKami membantu menyediakan berbagai pilihan menu yang dapat disesuaikan dengan kebutuhan acara harian maupun kegiatan khusus. Proses pengolahan dilakukan dengan memperhatikan kebersihan dan kualitas bahan, serta didukung pengiriman yang tepat waktu agar konsumsi dapat tersaji dengan baik. Dengan layanan yang praktis dan fleksibel, kebutuhan makan untuk kantor, keluarga, maupun kegiatan lainnya dapat dipersiapkan dengan lebih mudah dan nyaman."),
			),
		),

		'layanan' => array(
			'title'  => '5. Layanan Utama',
			'fields' => array(
				'tampil' => $tampil,
				'judul'  => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Layanan Catering Profesional dengan Menu Berkualitas untuk Mendukung Berbagai Kebutuhan Acara Anda'),
				'gambar' => array('type' => 'image', 'label' => 'Gambar', 'default' => vlp_aset('layanan.webp')),
				'teks'   => array('type' => 'textarea', 'label' => 'Teks', 'description' => 'Pisahkan paragraf dengan satu baris kosong.', 'default' => "Kami menghadirkan layanan catering yang dirancang untuk membantu memenuhi kebutuhan konsumsi secara praktis, higienis, dan tepat waktu untuk berbagai jenis kegiatan. Mulai dari catering harian karyawan, nasi box untuk rapat kantor, acara keluarga, pengajian, kegiatan sekolah, hingga event khusus lainnya, setiap pesanan dipersiapkan dengan perhatian penuh terhadap kualitas rasa, kebersihan proses pengolahan, serta kerapihan penyajian.\n\nSetiap menu diolah menggunakan bahan pilihan yang segar dan diproses dengan standar kebersihan yang baik agar menghasilkan hidangan yang lezat dan aman dikonsumsi oleh semua kalangan. Kami juga menyediakan pilihan paket yang fleksibel sehingga pelanggan dapat menyesuaikan menu sesuai kebutuhan acara, jumlah porsi, serta anggaran yang tersedia tanpa mengurangi kualitas layanan.\n\nDengan pengalaman dalam melayani berbagai kebutuhan konsumsi pelanggan, kami berkomitmen memberikan pelayanan terbaik mulai dari proses pemesanan hingga pengiriman makanan ke lokasi acara. Kami percaya bahwa konsumsi yang berkualitas akan membantu menciptakan suasana acara yang lebih nyaman, berkesan, dan berjalan dengan lancar sesuai harapan."),
			),
		),

		'keunggulan' => array(
			'title'  => '6. Keunggulan',
			'fields' => array(
				'tampil' => $tampil,
				'judul'  => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Inilah Keunggulan Layanan Catering yang Kami Tawarkan'),
			),
			'ulang'  => array(
				'jumlah' => 9,
				'label'  => 'Kartu',
				'fields' => array(
					'ikon'  => array('type' => 'ikon', 'label' => 'Ikon'),
					'judul' => array('type' => 'text', 'label' => 'Judul', 'description' => 'Kosongkan judul untuk menyembunyikan kartu.'),
					'teks'  => array('type' => 'textarea', 'label' => 'Teks'),
				),
				'default' => array(
					array('fa-solid fa-utensils', 'Menu Fresh dan Berkualitas', 'Setiap makanan disiapkan menggunakan bahan pilihan yang segar agar menghasilkan rasa yang lezat dan kualitas yang terjaga.'),
					array('fa-solid fa-hand-sparkles', 'Proses Masak Higienis', 'Seluruh menu diolah dengan memperhatikan kebersihan selama proses persiapan hingga penyajian agar aman dikonsumsi.'),
					array('fa-solid fa-file-signature', 'Pilihan Paket Fleksibel', 'Tersedia berbagai pilihan paket nasi box dan catering harian yang dapat disesuaikan dengan kebutuhan acara Anda.'),
					array('fa-solid fa-truck-fast', 'Pengiriman Tepat Waktu', 'Pesanan dipersiapkan dan dikirim sesuai jadwal agar konsumsi siap disajikan saat acara berlangsung.'),
					array('fa-solid fa-users', 'Cocok untuk Berbagai Acara', 'Melayani kebutuhan konsumsi untuk rapat, pengajian, acara keluarga, sekolah, hingga kegiatan instansi.'),
					array('fa-solid fa-money-bill-1', 'Harga Terjangkau', 'Kami menyediakan pilihan paket dengan harga yang bersahabat tanpa mengurangi kualitas rasa dan pelayanan.'),
					array('fa-solid fa-list-check', 'Menu Variatif', 'Pilihan menu beragam sehingga pelanggan dapat menyesuaikan dengan selera dan kebutuhan acara.'),
					array('fa-brands fa-whatsapp', 'Pemesanan Mudah dan Praktis', 'Proses pemesanan dapat dilakukan dengan cepat melalui WhatsApp sehingga lebih nyaman dan efisien.'),
					array('fa-solid fa-chalkboard-user', 'Pelayanan Ramah dan Responsif', 'Kami siap membantu memberikan informasi menu dan paket terbaik sesuai kebutuhan Anda.'),
				),
			),
		),

		'mengapa' => array(
			'title'  => '7. Mengapa Memilih Kami',
			'fields' => array(
				'tampil'  => $tampil,
				'judul'   => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Mengapa Memilih Catering Kami?'),
				'butir'   => array('type' => 'textarea', 'label' => 'Daftar alasan', 'description' => 'Satu butir per baris.', 'default' => "Menu selalu fresh dan dimasak setiap hari\nBahan berkualitas dan higienis\nHarga paket terjangkau dan fleksibel\nBisa pesan harian maupun acara khusus\nGratis konsultasi menu sesuai kebutuhan"),
				'gambar1' => array('type' => 'image', 'label' => 'Gambar belakang (kanan atas)', 'default' => vlp_aset('mengapa-1.webp')),
				'gambar2' => array('type' => 'image', 'label' => 'Gambar depan (kiri bawah)', 'default' => vlp_aset('mengapa-2.webp')),
			),
		),

		'paket' => array(
			'title'  => '8. Paket Harga',
			'fields' => array(
				'tampil'    => $tampil,
				'judul'     => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Paket Harga Catering yang Kami Tawarkan'),
				'deskripsi' => array('type' => 'textarea', 'label' => 'Deskripsi', 'default' => 'Kami menghadirkan beberapa paket catering yang fleksibel dan dapat disesuaikan dengan kebutuhan Anda. Baik untuk acara sederhana sampai acara pernikahan.'),
				'ikon'      => array('type' => 'ikon', 'label' => 'Ikon daftar isi paket', 'default' => 'fa-solid fa-check'),
			),
			'ulang'  => array(
				'jumlah' => 3,
				'label'  => 'Paket',
				'fields' => array(
					'nama'         => array('type' => 'text', 'label' => 'Nama paket', 'description' => 'Kosongkan nama untuk menyembunyikan paket.'),
					'label'        => array('type' => 'text', 'label' => 'Label kecil'),
					'harga'        => array('type' => 'text', 'label' => 'Harga'),
					'tombol_label' => array('type' => 'text', 'label' => 'Tulisan tombol'),
					'tombol_link'  => array('type' => 'url', 'label' => 'Tautan tombol', 'description' => $link_wa),
					'fitur'        => array('type' => 'textarea', 'label' => 'Isi paket', 'description' => 'Satu butir per baris.'),
				),
				'default' => array(
					array('Paket Basic', '( Hemat )', 'Mulai dari Rp 25.000 / porsi', 'Pilih Paket', '', "Nasi\n1 Lauk utama (ayam/ikan)\nSayur\nSambal + Kerupuk\nAir Mineral\nCocok acara kecil/sederhana"),
					array('Paket Standard', '( Best Seller )', 'Mulai dari Rp 45.000 / porsi', 'Pilih Paket', '', "Nasi\n2 Lauk utama (ayam+sapi/ikan)\nSayur\nSambal + Kerupuk\nAir Mineral / Teh\nCocok untuk mayoritas acara"),
					array('Paket Premium', '( Eksklusif )', 'Mulai dari Rp 70.000 / porsi', 'Pilih Paket', '', "Nasi\n3 Lauk (ayam+sapi+seafood)\nSayur Premium\nDessert\nMinuman Lengkap\nCocok untuk wedding / event besar"),
				),
			),
		),

		'jenis' => array(
			'title'  => '9. Jenis Layanan',
			'fields' => array(
				'tampil'    => $tampil,
				'judul'     => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Beberapa Jenis Layanan Catering yang Kami Sediakan'),
				'deskripsi' => array('type' => 'textarea', 'label' => 'Deskripsi', 'default' => 'Kami melayani berbagai kebutuhan konsumsi mulai dari catering harian hingga acara khusus dengan pilihan menu yang dapat disesuaikan. Berikut beberapa layanan catering yang sering dipesan pelanggan kami.'),
				'items'     => array(
					'type'        => 'repeater',
					'label'       => 'Daftar layanan',
					'description' => 'Klik judul untuk membuka, seret ikon ☰ untuk mengubah urutan.',
					'item_label'  => 'Layanan',
					'fields'      => array(
						'gambar' => array('type' => 'image', 'label' => 'Gambar'),
						'judul'  => array('type' => 'text', 'label' => 'Judul'),
						'teks'   => array('type' => 'textarea', 'label' => 'Teks'),
					),
					'default'     => array(
						array('gambar' => vlp_aset('jenis-1.webp'), 'judul' => 'Catering Harian Karyawan', 'teks' => 'Menu makan harian praktis dan bergizi untuk kebutuhan kantor atau instansi dengan pilihan menu yang bervariasi setiap hari.'),
						array('gambar' => vlp_aset('jenis-2.webp'), 'judul' => 'Nasi Box Rapat dan Meeting', 'teks' => 'Pilihan nasi box lengkap dan praktis untuk kebutuhan rapat kantor, seminar, maupun kegiatan resmi lainnya.'),
						array('gambar' => vlp_aset('jenis-3.webp'), 'judul' => 'Catering Acara Keluarga', 'teks' => 'Melayani konsumsi untuk acara keluarga seperti syukuran, arisan, ulang tahun, dan kegiatan rumah tangga lainnya.'),
						array('gambar' => vlp_aset('jenis-4.webp'), 'judul' => 'Catering Pengajian dan Komunitas', 'teks' => 'Paket konsumsi praktis dan ekonomis untuk kegiatan pengajian, kegiatan sosial, dan acara lingkungan.'),
						array('gambar' => vlp_aset('jenis-5.webp'), 'judul' => 'Snack Box Acara', 'teks' => 'Pilihan snack box untuk kegiatan rapat, seminar, pelatihan, maupun kegiatan sekolah dan instansi.'),
						array('gambar' => vlp_aset('jenis-6.webp'), 'judul' => 'Catering Event dan Kegiatan Khusus', 'teks' => 'Layanan catering untuk berbagai kegiatan khusus seperti gathering, pelatihan, acara kantor, dan event komunitas.'),
					),
				),
			),
		),

		'kepercayaan' => array(
			'title'  => '10. Kepercayaan',
			'fields' => array(
				'tampil' => $tampil,
				'gambar' => array('type' => 'image', 'label' => 'Gambar / ikon', 'default' => vlp_aset('kepercayaan.png')),
				'judul'  => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Kepercayaan Pelanggan adalah Prioritas Kami'),
				'teks'   => array('type' => 'textarea', 'label' => 'Teks', 'description' => 'Pisahkan paragraf dengan satu baris kosong.', 'default' => "Kami berkomitmen menghadirkan layanan catering yang mengutamakan kualitas rasa, kebersihan, dan ketepatan waktu dalam setiap pesanan. Setiap menu dipersiapkan menggunakan bahan pilihan yang segar dan diolah dengan proses yang higienis agar menghasilkan hidangan yang lezat serta aman dikonsumsi untuk berbagai kebutuhan acara.\n\nLayanan kami telah digunakan untuk berbagai kebutuhan seperti catering harian karyawan, nasi box rapat, acara keluarga, pengajian, kegiatan sekolah, hingga event komunitas. Dengan pilihan paket yang fleksibel dan proses pemesanan yang mudah, kami siap membantu memenuhi kebutuhan konsumsi Anda secara praktis, nyaman, dan terpercaya."),
			),
		),

		'faq' => array(
			'title'  => '11. Tanya Jawab (FAQ)',
			'fields' => array(
				'tampil'    => $tampil,
				'judul'     => array('type' => 'textarea', 'label' => 'Judul', 'default' => 'Hal yang Sering Ditanyakan Tentang Jasa Catering Kami'),
				'deskripsi' => array('type' => 'textarea', 'label' => 'Deskripsi', 'default' => 'Berikut beberapa pertanyaan yang paling sering ditanyakan oleh calon pembeli sebelum memesan catering kami. Bagian ini membantu Anda memahami proses, fasilitas, dan layanan yang akan Anda dapatkan.'),
			),
			'ulang'  => array(
				'jumlah' => 10,
				'label'  => 'Pertanyaan',
				'fields' => array(
					'tanya' => array('type' => 'text', 'label' => 'Pertanyaan', 'description' => 'Kosongkan pertanyaan untuk menyembunyikannya.'),
					'jawab' => array('type' => 'textarea', 'label' => 'Jawaban'),
				),
				'default' => array(
					array('Apakah bisa pesan dalam jumlah sedikit?', 'Ya, kami melayani pemesanan mulai dari jumlah tertentu sesuai jenis paket. Silakan hubungi kami untuk informasi minimal pemesanan.'),
					array('Apakah bisa memilih menu sendiri?', 'Tentu. Kami menyediakan beberapa pilihan paket menu dan juga melayani penyesuaian menu sesuai kebutuhan acara Anda.'),
					array('Berapa minimal pemesanan catering?', 'Minimal pemesanan menyesuaikan jenis paket yang dipilih. Untuk informasi detail silakan hubungi kami melalui WhatsApp.'),
					array('Apakah bisa pesan mendadak?', 'Kami menyarankan pemesanan dilakukan lebih awal agar persiapan maksimal, namun untuk kebutuhan mendesak tetap bisa dikonsultasikan terlebih dahulu.'),
					array('Apakah tersedia layanan antar ke lokasi acara?', 'Ya, kami menyediakan layanan pengantaran langsung ke lokasi acara sesuai area layanan kami.'),
					array('Apakah makanan dijamin higienis?', 'Semua menu diproses menggunakan bahan berkualitas dan diolah dengan standar kebersihan yang baik agar aman dan nyaman dikonsumsi.'),
					array('Apakah melayani catering harian kantor?', 'Ya, kami melayani catering harian untuk karyawan kantor dengan pilihan menu yang bervariasi.'),
					array('Apakah bisa request waktu pengiriman tertentu?', 'Bisa. Waktu pengiriman dapat disesuaikan dengan jadwal acara agar makanan tiba tepat waktu.'),
					array('Apakah harga sudah termasuk air minum dan kemasan?', 'Isi paket menyesuaikan pilihan menu yang dipilih. Detail paket dapat dikonsultasikan saat pemesanan.'),
					array('Bagaimana cara melakukan pemesanan?', 'Pemesanan dapat dilakukan dengan mudah melalui WhatsApp dengan menyampaikan jumlah pesanan, tanggal acara, dan pilihan paket menu.'),
				),
			),
		),

		'footer' => array(
			'title'  => '12. Footer',
			'fields' => array(
				'logo'          => array('type' => 'image', 'label' => 'Logo', 'default' => vlp_aset('logo.webp'), 'description' => 'Kosongkan untuk menampilkan nama situs sebagai teks.'),
				'alamat'        => array('type' => 'textarea', 'label' => 'Alamat', 'default' => 'Kebonagung RT 04/ RW 01, Jarum, Bayat, Klaten, Jawa Tengah. Kode Pos: 57462'),
				'telepon'       => array('type' => 'text', 'label' => 'Telepon', 'default' => '', 'description' => 'Opsional. Kosongkan bila sama dengan WhatsApp.'),
				'email'         => array('type' => 'text', 'label' => 'Email', 'default' => ''),
				'tentang_judul' => array('type' => 'text', 'label' => 'Judul kolom tentang', 'default' => 'Tentang Catering Klaten'),
				'tentang_teks'  => array('type' => 'textarea', 'label' => 'Teks kolom tentang', 'default' => 'Kami menyediakan layanan catering untuk kebutuhan harian, kantor, sekolah, acara keluarga, hingga event besar dengan menu higienis, lezat, dan berkualitas. Tersedia pilihan paket fleksibel sesuai kebutuhan dan anggaran Anda.'),
				'link_judul'    => array('type' => 'text', 'label' => 'Judul kolom tautan', 'default' => 'Link', 'description' => 'Isi tautan diatur di Menu → lokasi "Footer Landing". Tanpa menu: WhatsApp + Kebijakan Privasi.'),
				'sosmed_judul'  => array('type' => 'text', 'label' => 'Judul media sosial', 'default' => 'Ikuti Kami', 'description' => 'Ikon tampil di bawah kolom tautan. Kosongkan tautan untuk menyembunyikan ikonnya.'),
				'facebook'      => array('type' => 'url', 'label' => 'Facebook', 'default' => 'https://www.facebook.com/'),
				'instagram'     => array('type' => 'url', 'label' => 'Instagram', 'default' => 'https://www.instagram.com/'),
				'x'             => array('type' => 'url', 'label' => 'X (Twitter)', 'default' => 'https://x.com/'),
				'youtube'       => array('type' => 'url', 'label' => 'YouTube', 'default' => 'https://www.youtube.com/'),
				'tiktok'        => array('type' => 'url', 'label' => 'TikTok', 'default' => 'https://www.tiktok.com/'),
				'linkedin'      => array('type' => 'url', 'label' => 'LinkedIn', 'default' => ''),
				'statistik'       => array('type' => 'checkbox', 'label' => 'Tampilkan statistik pengunjung', 'default' => true, 'description' => 'Butuh plugin Velocity Addons (shortcode [velocity-statistics]).'),
				'statistik_judul' => array('type' => 'text', 'label' => 'Judul kolom statistik', 'default' => 'Statistik Pengunjung'),
				'hak_cipta'     => array('type' => 'text', 'label' => 'Teks hak cipta', 'default' => '© {tahun} {situs}. All Rights Reserved.', 'description' => '{tahun} dan {situs} diganti otomatis.'),
				'kredit'        => array('type' => 'textarea', 'label' => 'Teks kredit', 'default' => 'Design by <a href="https://velocitydeveloper.com/" target="_blank" rel="noopener">Velocity Developer</a>', 'description' => 'Boleh memuat tautan HTML. Kosongkan untuk menyembunyikan.'),
			),
		),
	);

	// Field berulang dijabarkan menjadi item{n}_{field} dengan nilai bawaan per item.
	foreach ($skema as $id => $seksi) {
		if (empty($seksi['ulang'])) {
			continue;
		}
		$u = $seksi['ulang'];
		for ($n = 1; $n <= $u['jumlah']; $n++) {
			$nilai = isset($u['default'][$n - 1]) ? $u['default'][$n - 1] : array();
			$i = 0;
			foreach ($u['fields'] as $f => $def) {
				$def['label'] = $u['label'] . ' ' . $n . ': ' . $def['label'];
				$def['default'] = isset($nilai[$i]) ? $nilai[$i] : '';
				$skema[$id]['fields']['item' . $n . '_' . $f] = $def;
				$i++;
			}
		}
	}

	return $skema;
}
