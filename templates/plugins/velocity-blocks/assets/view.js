/* Velocity Blocks — tab katalog produk. Tanpa JS semua panel tampil berurutan. */
( function () {
	document.querySelectorAll( '.vb-products--tabs' ).forEach( function ( wadah ) {
		var tab = wadah.querySelectorAll( '.vb-tab' );
		var panel = wadah.querySelectorAll( '.vb-tabpanel' );
		wadah.classList.add( 'vb-js' );
		function pilih( i, fokus ) {
			tab.forEach( function ( t, j ) {
				t.setAttribute( 'aria-selected', i === j ? 'true' : 'false' );
				t.tabIndex = i === j ? 0 : -1;
				panel[ j ].hidden = i !== j;
			} );
			if ( fokus ) {
				tab[ i ].focus();
			}
		}
		tab.forEach( function ( t, i ) {
			t.addEventListener( 'click', function () {
				pilih( i );
			} );
			t.addEventListener( 'keydown', function ( e ) {
				if ( e.key === 'ArrowRight' || e.key === 'ArrowLeft' ) {
					e.preventDefault();
					pilih( ( i + ( e.key === 'ArrowRight' ? 1 : tab.length - 1 ) ) % tab.length, true );
				}
			} );
		} );
		pilih( 0 );
	} );
}() );

/* Velocity Blocks — carousel (testimoni & wadah Geser): scroll-snap, panah, titik, geser otomatis. */
( function () {
	var hemat = window.matchMedia && window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches;
	document.querySelectorAll( '.vb-testi, .vb-carousel' ).forEach( function ( w ) {
		// Satu mesin untuk dua blok: kelas dasarnya dibaca dari elemennya sendiri.
		var dasar = w.classList.contains( 'vb-carousel' ) ? '.vb-carousel' : '.vb-testi';
		var sebutan = w.getAttribute( 'data-vb-sebutan' ) || 'Slide';
		var track = w.querySelector( dasar + '__track' );
		var item = track ? track.children : [];
		if ( ! track || item.length < 2 ) {
			return;
		}
		var prev = w.querySelector( dasar + '__prev' );
		var next = w.querySelector( dasar + '__next' );
		var dots = w.querySelector( dasar + '__dots' );
		var langkah = function () {
			return item[ 1 ].offsetLeft - item[ 0 ].offsetLeft;
		};
		var perLayar = function () {
			return Math.max( 1, Math.round( track.clientWidth / langkah() ) );
		};
		var halaman = function () {
			return Math.max( 1, item.length - perLayar() + 1 );
		};
		var kini = function () {
			return Math.round( track.scrollLeft / langkah() );
		};
		var ke = function ( i ) {
			var n = halaman();
			i = ( ( i % n ) + n ) % n;
			track.scrollTo( { left: i * langkah(), behavior: hemat ? 'auto' : 'smooth' } );
		};
		var bangunTitik = function () {
			if ( ! dots ) {
				return;
			}
			dots.innerHTML = '';
			var n = halaman();
			if ( n < 2 ) {
				return;
			}
			for ( var i = 0; i < n; i++ ) {
				var b = document.createElement( 'button' );
				b.type = 'button';
				b.className = dasar.slice( 1 ) + '__dot';
				b.setAttribute( 'role', 'tab' );
				b.setAttribute( 'aria-label', sebutan + ' ' + ( i + 1 ) );
				b.addEventListener( 'click', ke.bind( null, i ) );
				dots.appendChild( b );
			}
		};
		var segarkan = function () {
			var i = kini();
			var n = halaman();
			if ( dots ) {
				Array.prototype.forEach.call( dots.children, function ( d, j ) {
					d.setAttribute( 'aria-selected', i === j ? 'true' : 'false' );
				} );
			}
			var nav = w.querySelector( dasar + '__nav' );
			if ( nav ) {
				nav.hidden = n < 2;
			}
			if ( prev ) {
				prev.disabled = n < 2;
			}
			if ( next ) {
				next.disabled = n < 2;
			}
		};
		if ( prev ) {
			prev.addEventListener( 'click', function () {
				ke( kini() - 1 );
			} );
		}
		if ( next ) {
			next.addEventListener( 'click', function () {
				ke( kini() + 1 );
			} );
		}
		var tunda;
		track.addEventListener( 'scroll', function () {
			clearTimeout( tunda );
			tunda = setTimeout( segarkan, 80 );
		}, { passive: true } );
		window.addEventListener( 'resize', function () {
			bangunTitik();
			segarkan();
		} );
		bangunTitik();
		segarkan();

		var detik = parseInt( w.getAttribute( 'data-vb-autoplay' ), 10 ) || 0;
		if ( detik && ! hemat ) {
			var jeda = false;
			[ 'mouseenter', 'focusin', 'touchstart' ].forEach( function ( e ) {
				w.addEventListener( e, function () {
					jeda = true;
				}, { passive: true } );
			} );
			[ 'mouseleave', 'focusout' ].forEach( function ( e ) {
				w.addEventListener( e, function () {
					jeda = false;
				} );
			} );
			setInterval( function () {
				if ( ! jeda && ! document.hidden ) {
					ke( kini() + 1 );
				}
			}, detik * 1000 );
		}
	} );
}() );

/* Velocity Blocks — FAQ: hanya satu jawaban terbuka bila data-vb-single="1". */
( function () {
	document.querySelectorAll( '.vb-faq[data-vb-single="1"]' ).forEach( function ( w ) {
		var item = w.querySelectorAll( 'details.vb-faq__item' );
		item.forEach( function ( d ) {
			d.addEventListener( 'toggle', function () {
				if ( d.open ) {
					item.forEach( function ( lain ) {
						if ( lain !== d ) {
							lain.open = false;
						}
					} );
				}
			} );
		} );
	} );
}() );

/* Velocity Blocks — saring portofolio per kategori (tanpa JS semua karya tetap tampil). */
( function () {
	document.querySelectorAll( '.vb-porto' ).forEach( function ( w ) {
		var tombol = w.querySelectorAll( '.vb-porto__tombol' );
		var item = w.querySelectorAll( '.vb-porto__item' );
		tombol.forEach( function ( t ) {
			t.addEventListener( 'click', function () {
				var kat = t.getAttribute( 'data-kat' );
				tombol.forEach( function ( lain ) {
					var aktif = lain === t;
					lain.classList.toggle( 'is-aktif', aktif );
					lain.setAttribute( 'aria-pressed', aktif ? 'true' : 'false' );
				} );
				item.forEach( function ( i ) {
					var cocok = kat === '*' || ( ' ' + i.getAttribute( 'data-kat' ) + ' ' ).indexOf( ' ' + kat + ' ' ) !== -1;
					i.hidden = ! cocok;
				} );
			} );
		} );
	} );

	/* Form booking WhatsApp: susun pesan dari isian lalu buka wa.me di tab baru. */
	document.querySelectorAll( '.vb-book' ).forEach( function ( w ) {
		var form = w.querySelector( 'form' );
		if ( ! form ) {
			return;
		}
		form.addEventListener( 'submit', function ( e ) {
			e.preventDefault();
			var baris = [ w.getAttribute( 'data-vb-intro' ) || '' ];
			form.querySelectorAll( '[data-vb-label]' ).forEach( function ( f ) {
				var nilai = f.value;
				if ( f.type === 'date' && nilai ) {
					var t = nilai.split( '-' );
					nilai = t[ 2 ] + '/' + t[ 1 ] + '/' + t[ 0 ];
				}
				if ( nilai ) {
					baris.push( f.getAttribute( 'data-vb-label' ) + ': ' + nilai );
				}
			} );
			var url = 'https://wa.me/' + ( w.getAttribute( 'data-vb-wa' ) || '' ) + '?text=' + encodeURIComponent( baris.filter( Boolean ).join( '\n' ) );
			window.open( url, '_blank', 'noopener' );
		} );
	} );
}() );
