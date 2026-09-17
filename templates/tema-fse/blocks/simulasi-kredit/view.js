/**
 * Simulasi kredit: hitung di peramban, tanpa request ke server.
 * Bunga flat — cara hitung yang dipakai simulasi dealer di Indonesia.
 *
 * Tipe mobil dipilih dari Data Unit. Unit yang harganya belum dipastikan tidak
 * dikarang angkanya: kolom harga dibuka supaya pengunjung mengisi sendiri.
 */
( function () {
	var rupiah = function ( n ) {
		if ( ! isFinite( n ) || n <= 0 ) {
			return '—';
		}
		return 'Rp ' + Math.round( n ).toString().replace( /\B(?=(\d{3})+(?!\d))/g, '.' );
	};
	var angka = function ( n, desimal ) {
		return n.toFixed( desimal || 0 ).replace( '.', ',' );
	};

	var siapkan = function ( wadah ) {
		var ambil = function ( nama ) {
			return wadah.querySelector( '[data-vf="' + nama + '"]' );
		};
		var unit = [];
		try {
			unit = JSON.parse( wadah.getAttribute( 'data-unit' ) || '[]' );
		} catch ( e ) {
			unit = [];
		}
		var pilihUnit = ambil( 'unit' );
		var harga = ambil( 'harga' );
		var barisHarga = ambil( 'baris-harga' );
		var catatanHarga = ambil( 'catatan-harga' );
		var dp = ambil( 'dp' );
		var bunga = ambil( 'bunga' );
		var wa = ambil( 'wa' );
		var waDasar = wa ? wa.getAttribute( 'href' ) : '';
		var tenorList = Array.prototype.slice.call( wadah.querySelectorAll( '[data-vf="tenor"]' ) );

		var tenorTerpilih = function () {
			var dipilih = tenorList.filter( function ( el ) { return el.checked; } )[ 0 ];
			return dipilih ? parseInt( dipilih.value, 10 ) : 36;
		};

		var unitTerpilih = function () {
			return pilihUnit && unit[ pilihUnit.value ] ? unit[ pilihUnit.value ] : null;
		};

		var pakaiUnit = function () {
			var u = unitTerpilih();
			if ( u && u.harga > 0 ) {
				harga.value = u.harga;
				if ( barisHarga ) {
					barisHarga.hidden = true;
				}
				catatanHarga.textContent = '* Estimasi ' + ( u.catatan || 'harga OTR' ) +
					', dapat berubah sewaktu-waktu.';
			} else {
				if ( barisHarga ) {
					barisHarga.hidden = false;
				}
				catatanHarga.textContent = u
					? '* Harga ' + u.nama + ' belum dipastikan — isi harga perkiraan untuk melihat estimasi cicilan.'
					: '* Isi harga unit untuk melihat estimasi cicilan.';
			}
		};

		var hitung = function () {
			var h = parseFloat( harga.value ) || 0;
			var persenDp = Math.min( 90, Math.max( 0, parseFloat( dp.value ) || 0 ) );
			var bulan = tenorTerpilih();
			var persenBunga = Math.max( 0, parseFloat( bunga.value ) || 0 );
			var nilaiDp = h * persenDp / 100;
			var pokok = h - nilaiDp;
			var totalBunga = pokok * ( persenBunga / 100 ) * ( bulan / 12 );
			var cicilan = bulan > 0 ? ( pokok + totalBunga ) / bulan : 0;

			ambil( 'dp-persen' ).textContent = angka( persenDp ) + '%';
			ambil( 'bunga-persen' ).textContent = angka( persenBunga, 1 ) + '%';
			// Tanpa harga, tanda "—" saja terlihat seperti garis nyasar: beri arahan singkat.
			ambil( 'cicilan' ).textContent = h > 0 ? rupiah( cicilan ) : 'Rp —';
			ambil( 'ringkas' ).textContent = h > 0
				? 'untuk tenor ' + ( bulan / 12 ) + ' tahun · bunga ' + angka( persenBunga, 1 ) + '%/tahun'
				: 'Pilih tipe mobil atau isi harga unit untuk melihat estimasi.';
			ambil( 'bar' ).style.width = persenDp + '%';
			ambil( 'dp-bar' ).textContent = angka( persenDp ) + '%';
			ambil( 'harga-nilai' ).textContent = rupiah( h );
			ambil( 'dp-nilai' ).textContent = rupiah( nilaiDp );
			ambil( 'pokok' ).textContent = rupiah( pokok );
			ambil( 'bunga-nilai' ).textContent = rupiah( totalBunga );
			ambil( 'total' ).textContent = rupiah( nilaiDp + pokok + totalBunga );

			if ( wa && waDasar ) {
				var u = unitTerpilih();
				var nama = u ? u.nama : 'unit yang saya minati';
				var pesan = 'Halo, saya ingin ajukan simulasi kredit ' + nama + '. Harga ' + rupiah( h ) +
					', uang muka ' + angka( persenDp ) + '% (' + rupiah( nilaiDp ) + '), tenor ' + ( bulan / 12 ) +
					' tahun, estimasi cicilan ' + rupiah( cicilan ) + ' per bulan.';
				wa.setAttribute( 'href', waDasar.split( '?' )[ 0 ] + '?text=' + encodeURIComponent( pesan ) );
			}
		};

		if ( pilihUnit ) {
			pilihUnit.addEventListener( 'change', function () {
				pakaiUnit();
				hitung();
			} );
		}
		[ harga, dp, bunga ].forEach( function ( el ) {
			if ( ! el ) {
				return;
			}
			el.addEventListener( 'input', hitung );
			el.addEventListener( 'change', hitung );
		} );
		tenorList.forEach( function ( el ) {
			el.addEventListener( 'change', hitung );
		} );

		pakaiUnit();
		hitung();
	};

	var mulai = function () {
		Array.prototype.forEach.call( document.querySelectorAll( '.vf-kredit[data-unit]' ), siapkan );
	};
	if ( document.readyState === 'loading' ) {
		document.addEventListener( 'DOMContentLoaded', mulai );
	} else {
		mulai();
	}
} )();
