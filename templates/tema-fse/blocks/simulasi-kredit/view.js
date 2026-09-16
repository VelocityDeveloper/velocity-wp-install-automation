/**
 * Simulasi kredit: hitung di peramban, tanpa request ke server.
 * Bunga flat — cara hitung yang dipakai simulasi dealer di Indonesia.
 */
( function () {
	var rupiah = function ( n ) {
		if ( ! isFinite( n ) || n <= 0 ) {
			return '—';
		}
		return 'Rp ' + Math.round( n ).toString().replace( /\B(?=(\d{3})+(?!\d))/g, '.' );
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
		var dp = ambil( 'dp' );
		var tenor = ambil( 'tenor' );
		var bunga = ambil( 'bunga' );
		var wa = ambil( 'wa' );
		var waDasar = wa ? wa.getAttribute( 'href' ) : '';

		var hitung = function () {
			var h = parseFloat( harga.value ) || 0;
			var persenDp = Math.min( 90, Math.max( 0, parseFloat( dp.value ) || 0 ) );
			var bulan = parseInt( tenor.value, 10 ) || 12;
			var persenBunga = Math.max( 0, parseFloat( bunga.value ) || 0 );
			var nilaiDp = h * persenDp / 100;
			var pokok = h - nilaiDp;
			var totalBunga = pokok * ( persenBunga / 100 ) * ( bulan / 12 );
			var cicilan = bulan > 0 ? ( pokok + totalBunga ) / bulan : 0;

			ambil( 'cicilan' ).textContent = rupiah( cicilan );
			ambil( 'dp-nilai' ).textContent = rupiah( nilaiDp );
			ambil( 'pokok' ).textContent = rupiah( pokok );
			ambil( 'bunga-nilai' ).textContent = rupiah( totalBunga );
			ambil( 'total' ).textContent = rupiah( nilaiDp + pokok + totalBunga );

			if ( wa && waDasar ) {
				var nama = pilihUnit && unit[ pilihUnit.value ] ? unit[ pilihUnit.value ].nama : 'unit XPENG';
				var pesan = 'Halo, saya ingin simulasi kredit ' + nama + '. Harga ' + rupiah( h ) +
					', uang muka ' + persenDp + '% (' + rupiah( nilaiDp ) + '), tenor ' + bulan +
					' bulan, estimasi cicilan ' + rupiah( cicilan ) + ' per bulan.';
				wa.setAttribute( 'href', waDasar.split( '?' )[ 0 ] + '?text=' + encodeURIComponent( pesan ) );
			}
		};

		if ( pilihUnit ) {
			pilihUnit.addEventListener( 'change', function () {
				var u = unit[ pilihUnit.value ];
				if ( u ) {
					harga.value = u.harga;
				}
				hitung();
			} );
		}
		[ harga, dp, tenor, bunga ].forEach( function ( el ) {
			el.addEventListener( 'input', hitung );
			el.addEventListener( 'change', hitung );
		} );
		wadah.querySelector( '.vf-kredit__form' ).addEventListener( 'submit', function ( e ) {
			e.preventDefault();
			hitung();
		} );
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
