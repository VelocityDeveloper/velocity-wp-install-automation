/**
 * Kontrol repeater Customizer: item berkelompok (buka/tutup), tambah, hapus, seret untuk
 * mengurutkan, gambar dari pustaka media. Nilai = JSON array item di setting kontrol.
 */
(function ($, api) {
	'use strict';

	function esc(teks) {
		return $('<div>').text(teks == null ? '' : String(teks)).html();
	}

	api.controlConstructor.vlp_repeater = api.Control.extend({
		ready: function () {
			var kontrol = this;
			kontrol.fields = kontrol.params.vlpFields || {};
			kontrol.sebutan = kontrol.params.vlpItemLabel || 'Item';
			kontrol.daftar = kontrol.container.find('.vlp-repeater-daftar');

			kontrol.items = kontrol.baca();
			kontrol.gambarUlang();

			kontrol.container.on('click', '.vlp-repeater-tambah', function () {
				var baru = {};
				$.each(kontrol.fields, function (k) { baru[k] = ''; });
				kontrol.items.push(baru);
				kontrol.simpan();
				kontrol.gambarUlang(kontrol.items.length - 1);
			});

			kontrol.daftar.on('click', '.vlp-rep-kepala', function (e) {
				if ($(e.target).closest('.vlp-rep-geser').length) {
					return;
				}
				$(this).closest('.vlp-rep-item').toggleClass('terbuka');
			});

			kontrol.daftar.on('input change', '[data-kunci]', function () {
				var $el = $(this);
				var i = $el.closest('.vlp-rep-item').index();
				kontrol.items[i][$el.data('kunci')] = $el.val();
				kontrol.perbaruiJudul(i);
				kontrol.simpan();
			});

			kontrol.daftar.on('click', '.vlp-rep-hapus', function () {
				var i = $(this).closest('.vlp-rep-item').index();
				var nama = kontrol.items[i].judul || (kontrol.sebutan + ' ' + (i + 1));
				if (!window.confirm('Hapus "' + nama + '"?')) {
					return;
				}
				kontrol.items.splice(i, 1);
				kontrol.simpan();
				kontrol.gambarUlang();
			});

			kontrol.daftar.on('click', '.vlp-rep-duplikat', function () {
				var i = $(this).closest('.vlp-rep-item').index();
				kontrol.items.splice(i + 1, 0, $.extend({}, kontrol.items[i]));
				kontrol.simpan();
				kontrol.gambarUlang(i + 1);
			});

			kontrol.daftar.on('click', '.vlp-rep-pilih-gambar', function () {
				var $item = $(this).closest('.vlp-rep-item');
				var kunci = $(this).data('untuk');
				var bingkai = wp.media({
					title: 'Pilih gambar',
					button: { text: 'Gunakan gambar ini' },
					library: { type: 'image' },
					multiple: false
				});
				bingkai.on('select', function () {
					var lampiran = bingkai.state().get('selection').first().toJSON();
					$item.find('[data-kunci="' + kunci + '"]').val(lampiran.url).trigger('change');
					$item.find('.vlp-rep-pratinjau[data-untuk="' + kunci + '"]').html('<img src="' + esc(lampiran.url) + '" alt="">');
				});
				bingkai.open();
			});

			kontrol.daftar.on('click', '.vlp-rep-hapus-gambar', function () {
				var $item = $(this).closest('.vlp-rep-item');
				var kunci = $(this).data('untuk');
				$item.find('[data-kunci="' + kunci + '"]').val('').trigger('change');
				$item.find('.vlp-rep-pratinjau[data-untuk="' + kunci + '"]').html('<span>Belum ada gambar</span>');
			});

			kontrol.daftar.sortable({
				handle: '.vlp-rep-geser',
				axis: 'y',
				start: function (e, ui) { ui.item.data('awal', ui.item.index()); },
				update: function (e, ui) {
					var dari = ui.item.data('awal');
					var ke = ui.item.index();
					var pindah = kontrol.items.splice(dari, 1)[0];
					kontrol.items.splice(ke, 0, pindah);
					kontrol.simpan();
					kontrol.daftar.children().each(function (i) { kontrol.perbaruiJudul(i); });
				}
			});
		},

		baca: function () {
			try {
				var data = JSON.parse(this.setting.get() || '[]');
				return $.isArray(data) ? data : [];
			} catch (e) {
				return [];
			}
		},

		simpan: function () {
			this.setting.set(JSON.stringify(this.items));
		},

		judulItem: function (i) {
			var item = this.items[i] || {};
			var nama = item.judul || item.nama || item.tanya || '';
			return this.sebutan + ' ' + (i + 1) + (nama ? ': ' + nama : '');
		},

		perbaruiJudul: function (i) {
			this.daftar.children().eq(i).find('.vlp-rep-judul').text(this.judulItem(i));
		},

		gambarUlang: function (buka) {
			var kontrol = this;
			kontrol.daftar.empty();
			$.each(kontrol.items, function (i, item) {
				var isi = '';
				$.each(kontrol.fields, function (kunci, def) {
					var nilai = item[kunci] || '';
					var id = kontrol.id + '-' + i + '-' + kunci;
					isi += '<div class="vlp-rep-field">';
					isi += '<label for="' + id + '">' + esc(def.label) + '</label>';
					if (def.type === 'image') {
						isi += '<div class="vlp-rep-pratinjau" data-untuk="' + kunci + '">' +
							(nilai ? '<img src="' + esc(nilai) + '" alt="">' : '<span>Belum ada gambar</span>') + '</div>';
						isi += '<input type="hidden" id="' + id + '" data-kunci="' + kunci + '" value="' + esc(nilai) + '">';
						isi += '<button type="button" class="button vlp-rep-pilih-gambar" data-untuk="' + kunci + '">Pilih gambar</button> ';
						isi += '<button type="button" class="button-link vlp-rep-hapus-gambar" data-untuk="' + kunci + '">Hapus</button>';
					} else if (def.type === 'textarea') {
						isi += '<textarea id="' + id + '" rows="4" data-kunci="' + kunci + '">' + esc(nilai) + '</textarea>';
					} else {
						isi += '<input type="' + (def.type === 'url' ? 'url' : 'text') + '" id="' + id + '" data-kunci="' + kunci + '" value="' + esc(nilai) + '">';
					}
					isi += '</div>';
				});
				kontrol.daftar.append(
					'<li class="vlp-rep-item' + (i === buka ? ' terbuka' : '') + '">' +
						'<div class="vlp-rep-kepala">' +
							'<span class="vlp-rep-geser dashicons dashicons-menu" title="Seret untuk mengurutkan"></span>' +
							'<span class="vlp-rep-judul"></span>' +
							'<span class="vlp-rep-panah dashicons dashicons-arrow-down-alt2" aria-hidden="true"></span>' +
						'</div>' +
						'<div class="vlp-rep-isi">' + isi +
							'<div class="vlp-rep-aksi">' +
								'<button type="button" class="button-link vlp-rep-duplikat">Duplikat</button>' +
								'<button type="button" class="button-link button-link-delete vlp-rep-hapus">Hapus ' + esc(kontrol.sebutan) + '</button>' +
							'</div>' +
						'</div>' +
					'</li>'
				);
				kontrol.perbaruiJudul(i);
			});
		}
	});
})(jQuery, wp.customize);
