/**
 * Velocity Blocks — editor.
 *
 * Tanpa build step (wp.element.createElement). Semua blok dirender PHP (render.php);
 * editor ini menampilkan markup yang sama dengan kelas CSS yang sama, jadi teks diketik
 * langsung di kanvas, ikon dipilih dari toolbar/klik ikon, dan tautan diatur dari tombol
 * tautan di toolbar — seperti page builder. Blok wadah (Seksi, Grid, Baris, Alur Langkah)
 * menyimpan blok anak sehingga bisa di-drag, disalin, dan dihapus bebas.
 */
( function ( wp, data ) {
	'use strict';

	var el = wp.element.createElement;
	var Fragment = wp.element.Fragment;
	var useState = wp.element.useState;
	var be = wp.blockEditor;
	var c = wp.components;
	var useBlockProps = be.useBlockProps;
	var useInnerBlocksProps = be.useInnerBlocksProps;
	var InnerBlocks = be.InnerBlocks;
	var RichText = be.RichText;
	var InspectorControls = be.InspectorControls;
	var BlockControls = be.BlockControls;
	var MediaUpload = be.MediaUpload;
	var MediaUploadCheck = be.MediaUploadCheck;
	var LinkControl = be.LinkControl || be.__experimentalLinkControl;
	var SSR = wp.serverSideRender;
	var ikonData = ( data && data.ikon ) || {};
	var kategoriIkon = ( data && data.kategori ) || {};

	var TEKS = [ 'core/bold', 'core/italic', 'core/link', 'vb/sorot', 'core/strikethrough', 'core/subscript', 'core/superscript' ];
	var TEKS_JUDUL = [ 'core/bold', 'core/italic', 'vb/sorot' ];

	/* ------------------------------------------------------------------ */
	/* Format teks: sorot warna aksen (mis. separuh judul berwarna emas).  */
	/* ------------------------------------------------------------------ */
	wp.richText.registerFormatType( 'vb/sorot', {
		title: 'Warna aksen',
		tagName: 'span',
		className: 'vb-sorot',
		edit: function ( props ) {
			return el( be.RichTextToolbarButton, {
				icon: 'admin-customizer',
				title: 'Warna aksen',
				isActive: props.isActive,
				onClick: function () {
					props.onChange( wp.richText.toggleFormat( props.value, { type: 'vb/sorot' } ) );
				},
			} );
		},
	} );

	/* ------------------------------------------------------------------ */
	/* Komponen bantu                                                      */
	/* ------------------------------------------------------------------ */
	function Ikon( props ) {
		if ( props.url ) {
			return el( 'span', { className: ( props.className || 'vb-ikon' ) + ' vb-ikon--gambar', onClick: props.onClick }, el( 'img', { src: props.url, alt: '' } ) );
		}
		if ( ! props.name || ! ikonData[ props.name ] ) {
			return props.kosong || null;
		}
		return el( 'span', {
			className: props.className || 'vb-ikon',
			onClick: props.onClick,
			dangerouslySetInnerHTML: {
				__html: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">' + ikonData[ props.name ] + '</svg>',
			},
		} );
	}

	/** Modal pemilih ikon: cari + kelompok + grid. */
	function ModalIkon( props ) {
		var s = useState( '' );
		var cari = s[ 0 ];
		var setCari = s[ 1 ];
		var k = useState( 'Semua' );
		var kel = k[ 0 ];
		var setKel = k[ 1 ];
		var semua = Object.keys( ikonData );
		var daftar = kel === 'Semua' ? semua : ( kategoriIkon[ kel ] || [] ).filter( function ( n ) {
			return ikonData[ n ];
		} );
		if ( cari ) {
			var q = cari.toLowerCase();
			daftar = semua.filter( function ( n ) {
				return n.indexOf( q ) !== -1;
			} );
		}
		return el( c.Modal, { title: 'Pilih ikon', onRequestClose: props.onClose, className: 'vb-modal-ikon', size: 'large' },
			el( 'div', { className: 'vb-modal-ikon__atas' },
				el( c.SearchControl, { value: cari, onChange: setCari, placeholder: 'Cari ikon (inggris), mis. ship, leaf, award' } ),
				el( 'div', { className: 'vb-modal-ikon__kel' },
					[ 'Semua' ].concat( Object.keys( kategoriIkon ) ).map( function ( nama ) {
						return el( c.Button, { key: nama, variant: kel === nama && ! cari ? 'primary' : 'secondary', size: 'small', onClick: function () {
							setKel( nama );
							setCari( '' );
						} }, nama );
					} )
				)
			),
			el( 'div', { className: 'vb-modal-ikon__grid' },
				daftar.map( function ( nama ) {
					return el( 'button', {
						key: nama,
						type: 'button',
						className: 'vb-modal-ikon__item' + ( props.value === nama ? ' is-selected' : '' ),
						title: nama,
						onClick: function () {
							props.onChange( nama );
							props.onClose();
						},
					}, el( Ikon, { name: nama } ), el( 'span', null, nama ) );
				} )
			),
			el( 'div', { className: 'vb-modal-ikon__bawah' },
				props.bolehKosong && el( c.Button, { variant: 'tertiary', isDestructive: true, onClick: function () {
					props.onChange( '' );
					props.onClose();
				} }, 'Tanpa ikon' ),
				props.onGambar && el( MediaUploadCheck, null, el( MediaUpload, {
					allowedTypes: [ 'image' ],
					onSelect: function ( m ) {
						props.onGambar( m );
						props.onClose();
					},
					render: function ( o ) {
						return el( c.Button, { variant: 'secondary', onClick: o.open }, 'Unggah ikon sendiri (SVG/PNG)' );
					},
				} ) )
			)
		);
	}

	/**
	 * Kontrol ikon: tombol toolbar + klik ikon di kanvas membuka modal.
	 * Mengembalikan { toolbar, modal, buka } untuk dipasang edit().
	 */
	function useIkon( props, kunci, opsi ) {
		opsi = opsi || {};
		var st = useState( false );
		var terbuka = st[ 0 ];
		var setTerbuka = st[ 1 ];
		var a = props.attributes;
		var toolbar = el( c.ToolbarButton, { icon: 'star-filled', label: 'Pilih ikon', onClick: function () {
			setTerbuka( true );
		} } );
		var modal = terbuka && el( ModalIkon, {
			value: a[ kunci ],
			bolehKosong: opsi.bolehKosong !== false,
			onClose: function () {
				setTerbuka( false );
			},
			onChange: function ( n ) {
				var ubah = {};
				ubah[ kunci ] = n;
				if ( opsi.gambar ) {
					ubah.iconUrl = '';
					ubah.iconId = 0;
				}
				props.setAttributes( ubah );
			},
			onGambar: opsi.gambar ? function ( m ) {
				props.setAttributes( { iconUrl: m.url, iconId: m.id } );
			} : null,
		} );
		return { toolbar: toolbar, modal: modal, buka: function () {
			setTerbuka( true );
		} };
	}

	/** Tombol tautan di toolbar + popover LinkControl (URL, halaman internal, tab baru). */
	function useTautan( props, anchor ) {
		var st = useState( false );
		var terbuka = st[ 0 ];
		var setTerbuka = st[ 1 ];
		var a = props.attributes;
		var toolbar = el( c.ToolbarButton, {
			icon: 'admin-links',
			label: a.url ? 'Ubah tautan' : 'Pasang tautan',
			isPressed: !! a.url,
			onClick: function () {
				setTerbuka( ! terbuka );
			},
		} );
		var popover = terbuka && LinkControl && el( c.Popover, {
			placement: 'bottom',
			anchor: anchor,
			onClose: function () {
				setTerbuka( false );
			},
			focusOnMount: 'firstElement',
			shift: true,
		}, el( LinkControl, {
			value: { url: a.url, opensInNewTab: !! a.newTab },
			onChange: function ( v ) {
				props.setAttributes( { url: v.url || '', newTab: !! v.opensInNewTab } );
			},
			onRemove: function () {
				props.setAttributes( { url: '', newTab: false } );
				setTerbuka( false );
			},
			settings: [ { id: 'opensInNewTab', title: 'Buka di tab baru' } ],
		} ) );
		return { toolbar: toolbar, popover: popover };
	}

	function Pilih( label, nilai, opsi, onChange, help ) {
		return el( c.SelectControl, {
			label: label,
			value: nilai,
			help: help,
			options: Object.keys( opsi ).map( function ( k ) {
				return { value: k, label: opsi[ k ] };
			} ),
			onChange: onChange,
			__nextHasNoMarginBottom: true,
			__next40pxDefaultSize: true,
		} );
	}

	function Setel( props, kunci ) {
		return function ( v ) {
			var ubah = {};
			ubah[ kunci ] = v;
			props.setAttributes( ubah );
		};
	}

	function Panel( judul, anak, terbuka ) {
		var Tumpuk = c.__experimentalVStack || 'div';
		return el( c.PanelBody, { title: judul, initialOpen: terbuka !== false }, el.apply( null, [ Tumpuk, { spacing: 4 } ].concat( anak ) ) );
	}

	var PERATAAN = { left: 'Kiri', center: 'Tengah', right: 'Kanan' };
	var JARAK = { none: 'Tanpa', xs: 'Sangat rapat', sm: 'Rapat', md: 'Sedang', lg: 'Lega', xl: 'Sangat lega' };

	function Toolbar() {
		var anak = Array.prototype.slice.call( arguments );
		return el( BlockControls, { group: 'block' }, el.apply( null, [ c.ToolbarGroup, null ].concat( anak ) ) );
	}

	/* Blok milik modul yang dimatikan tidak didaftarkan server, jadi editor pun melewatinya. */
	var modul = ( data && data.modul ) || {};
	var blokModul = { 'vb/products': 'produk', 'vb/product-details': 'produk', 'vb/rfq-form': 'rfq', 'vb/portfolio': 'portofolio', 'vb/rentals': 'sewa', 'vb/booking-form': 'sewa', 'vb/posts': 'berita', 'vb/news-heading': 'berita' };

	function daftarkan( nama, pengaturan ) {
		if ( blokModul[ nama ] && modul[ blokModul[ nama ] ] === false ) {
			return;
		}
		wp.blocks.registerBlockType( nama, pengaturan );
	}

	/* ------------------------------------------------------------------ */
	/* vb/section                                                          */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/section', {
		edit: function ( props ) {
			var a = props.attributes;
			var set = props.setAttributes;
			var gelap = ( a.bg === 'dark' || a.bg === 'primary' || !! a.bgUrl );
			if ( a.tone !== 'auto' ) {
				gelap = a.tone === 'light';
			}
			var gaya = {};
			if ( a.bg === 'custom' && a.bgColor ) {
				gaya.backgroundColor = a.bgColor;
			}
			if ( a.minHeight ) {
				gaya.minHeight = a.minHeight + 'vh';
			}
			var blockProps = useBlockProps( {
				className: [ 'vb-section', 'vb-bg-' + a.bg, 'vb-pad-' + a.padding, 'vb-valign-' + a.valign, gelap ? 'vb-tone-light' : 'vb-tone-dark', a.bgUrl ? 'vb-has-media' : '' ].join( ' ' ),
				style: gaya,
			} );
			var adaAnak = wp.data.useSelect( function ( s ) {
				return s( 'core/block-editor' ).getBlockCount( props.clientId ) > 0;
			}, [ props.clientId ] );
			var inner = useInnerBlocksProps( { className: 'vb-section__inner vb-w-' + a.width }, {
				renderAppender: adaAnak ? InnerBlocks.DefaultBlockAppender : InnerBlocks.ButtonBlockAppender,
				template: [ [ 'vb/heading' ] ],
			} );
			var gambar = el( MediaUploadCheck, null, el( MediaUpload, {
				allowedTypes: [ 'image' ],
				value: a.bgId,
				onSelect: function ( m ) {
					set( { bgUrl: m.url, bgId: m.id } );
				},
				render: function ( o ) {
					return el( 'div', { className: 'vb-kontrol-gambar' },
						a.bgUrl && el( 'img', { src: a.bgUrl, alt: '' } ),
						el( c.Button, { variant: 'secondary', onClick: o.open }, a.bgUrl ? 'Ganti foto latar' : 'Pilih foto latar' ),
						a.bgUrl && el( c.Button, { variant: 'tertiary', isDestructive: true, onClick: function () {
							set( { bgUrl: '', bgId: 0 } );
						} }, 'Hapus foto' )
					);
				},
			} ) );
			return el( Fragment, null,
				el( InspectorControls, null,
					Panel( 'Latar', [
						Pilih( 'Warna latar', a.bg, { none: 'Transparan', light: 'Putih', soft: 'Krem lembut', muted: 'Abu lembut', dark: 'Gelap (navy)', primary: 'Warna utama', accent: 'Warna aksen', custom: 'Warna lain…' }, Setel( props, 'bg' ) ),
						a.bg === 'custom' && el( c.ColorPalette, { key: 'warna', value: a.bgColor, onChange: Setel( props, 'bgColor' ) } ),
						el( 'div', { key: 'g' }, gambar ),
						a.bgUrl && el( c.RangeControl, { key: 'o', label: 'Gelap overlay (%)', value: a.overlay, min: 0, max: 100, step: 10, onChange: Setel( props, 'overlay' ) } ),
						a.bgUrl && Pilih( 'Jenis overlay', a.overlayType, { solid: 'Rata', gradient: 'Gradasi dari kiri', bottom: 'Gradasi dari bawah' }, Setel( props, 'overlayType' ) ),
						Pilih( 'Warna teks', a.tone, { auto: 'Otomatis', light: 'Terang (untuk latar gelap)', dark: 'Gelap (untuk latar terang)' }, Setel( props, 'tone' ) ),
					] ),
					Panel( 'Tata letak', [
						Pilih( 'Jarak atas-bawah', a.padding, JARAK, Setel( props, 'padding' ) ),
						Pilih( 'Lebar isi', a.width, { narrow: 'Sempit (teks)', content: 'Sedang', wide: 'Lebar', full: 'Penuh layar' }, Setel( props, 'width' ) ),
						el( c.RangeControl, { key: 'mh', label: 'Tinggi minimum (% layar, 0 = otomatis)', value: a.minHeight, min: 0, max: 100, step: 5, onChange: Setel( props, 'minHeight' ) } ),
						a.minHeight > 0 && Pilih( 'Posisi isi', a.valign, { top: 'Atas', center: 'Tengah', bottom: 'Bawah' }, Setel( props, 'valign' ) ),
					] )
				),
				el( 'section', blockProps,
					a.bgUrl && el( 'img', { className: 'vb-section__media', src: a.bgUrl, alt: '' } ),
					a.bgUrl && el( 'span', { className: 'vb-section__overlay vb-overlay-' + a.overlayType, style: { opacity: a.overlay / 100 } } ),
					el( 'div', inner )
				)
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/heading                                                          */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/heading', {
		edit: function ( props ) {
			var a = props.attributes;
			var blockProps = useBlockProps( { className: 'vb-heading vb-align-' + a.align + ' vb-size-' + a.size } );
			return el( Fragment, null,
				el( BlockControls, { group: 'block' },
					el( be.AlignmentControl, { value: a.align, onChange: function ( v ) {
						props.setAttributes( { align: v || 'left' } );
					} } ),
					el( c.ToolbarGroup, null, [ 1, 2, 3, 4 ].map( function ( n ) {
						return el( c.ToolbarButton, { key: n, isPressed: a.level === n, label: 'Judul H' + n, onClick: function () {
							props.setAttributes( { level: n } );
						} }, 'H' + n );
					} ) )
				),
				el( InspectorControls, null, Panel( 'Judul', [
					Pilih( 'Ukuran judul', a.size, { sm: 'Kecil', md: 'Sedang', lg: 'Besar', xl: 'Sangat besar (hero)' }, Setel( props, 'size' ) ),
					el( c.ToggleControl, { key: 'd', label: 'Garis hias di bawah judul', checked: a.divider, onChange: Setel( props, 'divider' ), __nextHasNoMarginBottom: true } ),
					el( 'p', { key: 'tip', className: 'vb-tip' }, 'Tip: blok sebagian teks judul lalu klik ikon kuas di toolbar untuk memberi warna aksen.' ),
				] ) ),
				el( 'div', blockProps,
					( a.pill || props.isSelected ) && el( 'p', { className: 'vb-heading__pill' }, el( RichText, { tagName: 'span', value: a.pill, onChange: Setel( props, 'pill' ), placeholder: 'Label kapsul (opsional)', allowedFormats: [] } ) ),
					( a.eyebrow || props.isSelected ) && el( RichText, { tagName: 'p', className: 'vb-heading__eyebrow', value: a.eyebrow, onChange: Setel( props, 'eyebrow' ), placeholder: 'Label kecil (opsional)', allowedFormats: TEKS_JUDUL } ),
					el( RichText, { tagName: 'h' + a.level, className: 'vb-heading__title', value: a.title, onChange: Setel( props, 'title' ), placeholder: 'Tulis judul…', allowedFormats: TEKS_JUDUL } ),
					a.divider && el( 'span', { className: 'vb-heading__divider' } ),
					( a.subtitle || props.isSelected ) && el( RichText, { tagName: 'p', className: 'vb-heading__subtitle', value: a.subtitle, onChange: Setel( props, 'subtitle' ), placeholder: 'Subjudul / deskripsi singkat (opsional)', allowedFormats: TEKS } )
				)
			);
		},
		save: function () {
			return null;
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/icon-box                                                         */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/icon-box', {
		edit: function ( props ) {
			var a = props.attributes;
			var an = useState( null );
			var blockProps = useBlockProps( {
				ref: an[ 1 ],
				className: 'vb-iconbox vb-layout-' + a.layout + ' vb-box-' + a.boxStyle + ' vb-ikonstyle-' + a.iconStyle + ' vb-align-' + a.align,
			} );
			var ikon = useIkon( props, 'icon', { gambar: true } );
			var tautan = useTautan( props, an[ 0 ] );
			return el( Fragment, null,
				Toolbar( ikon.toolbar, tautan.toolbar ),
				el( InspectorControls, null, Panel( 'Tampilan', [
					Pilih( 'Susunan', a.layout, { top: 'Ikon di atas', left: 'Ikon di kiri' }, Setel( props, 'layout' ) ),
					Pilih( 'Gaya kotak', a.boxStyle, { card: 'Kartu putih', 'card-dark': 'Kartu gelap', outline: 'Garis tepi', plain: 'Polos' }, Setel( props, 'boxStyle' ) ),
					Pilih( 'Gaya ikon', a.iconStyle, { soft: 'Latar lembut', circle: 'Lingkaran aksen', ring: 'Cincin', plain: 'Ikon saja' }, Setel( props, 'iconStyle' ) ),
					Pilih( 'Perataan', a.align, PERATAAN, Setel( props, 'align' ) ),
				] ) ),
				el( 'div', blockProps,
					el( Ikon, { name: a.icon, url: a.iconUrl, className: 'vb-ikon vb-iconbox__icon', onClick: ikon.buka,
						kosong: props.isSelected ? el( 'button', { type: 'button', className: 'vb-ikon vb-iconbox__icon vb-ikon--tambah', onClick: ikon.buka }, '+' ) : null } ),
					el( 'div', { className: 'vb-iconbox__body' },
						el( RichText, { tagName: 'h3', className: 'vb-iconbox__title', value: a.title, onChange: Setel( props, 'title' ), placeholder: 'Judul…', allowedFormats: TEKS_JUDUL } ),
						( a.text || props.isSelected ) && el( RichText, { tagName: 'p', className: 'vb-iconbox__text', value: a.text, onChange: Setel( props, 'text' ), placeholder: 'Teks penjelasan (opsional)', allowedFormats: TEKS } ),
						a.url && ( a.linkLabel || props.isSelected ) && el( 'span', { className: 'vb-iconbox__link' },
							el( RichText, { tagName: 'span', value: a.linkLabel, onChange: Setel( props, 'linkLabel' ), placeholder: 'Teks tautan (kosong = judul jadi tautan)', allowedFormats: [] } ),
							a.linkLabel && el( Ikon, { name: 'arrow-right', className: 'vb-ikon vb-ikon--kecil' } )
						)
					)
				),
				ikon.modal,
				tautan.popover
			);
		},
		save: function () {
			return null;
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/grid & vb/row                                                    */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/grid', {
		edit: function ( props ) {
			var a = props.attributes;
			var blockProps = useBlockProps( {
				className: 'vb-grid vb-gap-' + a.gap + ' vb-items-' + a.valign + ( a.ratio ? ' vb-ratio-' + a.ratio : '' ),
				style: { '--vb-cols': a.columns, '--vb-cols-t': a.columnsTablet, '--vb-cols-m': a.columnsMobile },
			} );
			var inner = useInnerBlocksProps( blockProps, {
				orientation: 'horizontal',
				template: [ [ 'vb/icon-box' ], [ 'vb/icon-box' ], [ 'vb/icon-box' ] ],
				renderAppender: props.isSelected ? InnerBlocks.ButtonBlockAppender : false,
			} );
			return el( Fragment, null,
				el( InspectorControls, null, Panel( 'Kolom', [
					Pilih( 'Lebar kolom (desktop)', a.ratio, { '': 'Sama rata', '2-1': 'Lebar | sempit (2:1)', '1-2': 'Sempit | lebar (1:2)', '3-1': 'Lebar | sempit (3:1)', '1-3': 'Sempit | lebar (1:3)', '1-2-1': 'Sempit | lebar | sempit' }, function ( v ) {
						var ubah = { ratio: v };
						if ( v ) {
							ubah.columns = v.split( '-' ).length;
						}
						props.setAttributes( ubah );
					}, 'Rasio dipakai di layar lebar; tablet & HP mengikuti jumlah kolom di bawah.' ),
					el( c.RangeControl, { key: 'd', label: 'Kolom desktop', value: a.columns, min: 1, max: 8, disabled: !! a.ratio, onChange: Setel( props, 'columns' ) } ),
					el( c.RangeControl, { key: 't', label: 'Kolom tablet', value: a.columnsTablet, min: 1, max: 6, onChange: Setel( props, 'columnsTablet' ) } ),
					el( c.RangeControl, { key: 'm', label: 'Kolom HP', value: a.columnsMobile, min: 1, max: 4, onChange: Setel( props, 'columnsMobile' ) } ),
					Pilih( 'Jarak antar kolom', a.gap, JARAK, Setel( props, 'gap' ) ),
					Pilih( 'Tinggi isi', a.valign, { stretch: 'Sama tinggi', start: 'Rata atas', center: 'Tengah' }, Setel( props, 'valign' ) ),
				] ) ),
				el( 'div', inner )
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	daftarkan( 'vb/row', {
		edit: function ( props ) {
			var a = props.attributes;
			var blockProps = useBlockProps( { className: 'vb-row vb-justify-' + a.justify + ' vb-gap-' + a.gap + ' vb-items-' + a.valign } );
			var inner = useInnerBlocksProps( blockProps, {
				orientation: 'horizontal',
				template: [ [ 'vb/button' ] ],
				renderAppender: props.isSelected ? InnerBlocks.ButtonBlockAppender : false,
			} );
			return el( Fragment, null,
				el( BlockControls, { group: 'block' }, el( be.JustifyContentControl || c.ToolbarGroup, {
					value: a.justify === 'left' ? 'left' : a.justify,
					allowedControls: [ 'left', 'center', 'right', 'space-between' ],
					onChange: function ( v ) {
						props.setAttributes( { justify: v || 'left' } );
					},
				} ) ),
				el( InspectorControls, null, Panel( 'Baris', [
					Pilih( 'Perataan', a.justify, { left: 'Kiri', center: 'Tengah', right: 'Kanan', 'space-between': 'Renggang' }, Setel( props, 'justify' ) ),
					Pilih( 'Jarak', a.gap, JARAK, Setel( props, 'gap' ) ),
				] ) ),
				el( 'div', inner )
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/button                                                           */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/button', {
		edit: function ( props ) {
			var a = props.attributes;
			var an = useState( null );
			var blockProps = useBlockProps( { ref: an[ 1 ], className: 'vb-btn-wrap' } );
			var ikon = useIkon( props, 'icon' );
			var tautan = useTautan( props, an[ 0 ] );
			var namaIkon = a.icon || ( a.variant === 'whatsapp' ? 'whatsapp' : '' );
			var ik = el( Ikon, { name: namaIkon, className: 'vb-ikon vb-btn__icon', onClick: ikon.buka } );
			var teks = el( RichText, { tagName: 'span', className: 'vb-btn__text', value: a.text, onChange: Setel( props, 'text' ), placeholder: 'Teks tombol', allowedFormats: [], withoutInteractiveFormatting: true } );
			return el( Fragment, null,
				Toolbar( ikon.toolbar, tautan.toolbar ),
				el( InspectorControls, null, Panel( 'Tombol', [
					Pilih( 'Gaya', a.variant, { primary: 'Utama (gelap)', accent: 'Aksen (emas)', outline: 'Garis', 'outline-light': 'Garis terang (di latar gelap)', light: 'Putih', whatsapp: 'WhatsApp', link: 'Tautan teks' }, Setel( props, 'variant' ),
						a.variant === 'whatsapp' ? 'Tanpa tautan = otomatis ke nomor WhatsApp di Tampilan → Data Situs.' : undefined ),
					Pilih( 'Ukuran', a.size, { sm: 'Kecil', md: 'Sedang', lg: 'Besar' }, Setel( props, 'size' ) ),
					Pilih( 'Posisi ikon', a.iconPos, { before: 'Sebelum teks', after: 'Sesudah teks' }, Setel( props, 'iconPos' ) ),
					a.variant === 'whatsapp' && el( c.TextareaControl, { key: 'wa', label: 'Pesan awal WhatsApp (opsional)', value: a.waMessage, onChange: Setel( props, 'waMessage' ) } ),
					el( c.TextControl, { key: 'u', label: 'Tautan (URL)', value: a.url, onChange: Setel( props, 'url' ), __nextHasNoMarginBottom: true } ),
				] ) ),
				el( 'div', blockProps,
					el( 'span', { className: 'vb-btn vb-btn--' + a.variant + ' vb-btn--' + a.size },
						a.iconPos === 'after' ? el( Fragment, null, teks, ik ) : el( Fragment, null, ik, teks )
					)
				),
				ikon.modal,
				tautan.popover
			);
		},
		save: function () {
			return null;
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/stat, vb/badge                                                   */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/stat', {
		edit: function ( props ) {
			var a = props.attributes;
			var ikon = useIkon( props, 'icon' );
			return el( Fragment, null,
				Toolbar( ikon.toolbar ),
				el( 'div', useBlockProps( { className: 'vb-stat' } ),
					el( Ikon, { name: a.icon, className: 'vb-ikon vb-stat__icon', onClick: ikon.buka } ),
					el( RichText, { tagName: 'p', className: 'vb-stat__value', value: a.value, onChange: Setel( props, 'value' ), placeholder: '100+', allowedFormats: TEKS_JUDUL } ),
					el( RichText, { tagName: 'p', className: 'vb-stat__label', value: a.label, onChange: Setel( props, 'label' ), placeholder: 'Label', allowedFormats: [] } )
				),
				ikon.modal
			);
		},
		save: function () {
			return null;
		},
	} );

	daftarkan( 'vb/badge', {
		edit: function ( props ) {
			var a = props.attributes;
			var ikon = useIkon( props, 'icon' );
			return el( Fragment, null,
				Toolbar( ikon.toolbar ),
				el( 'span', useBlockProps( { className: 'vb-badge' } ),
					el( Ikon, { name: a.icon, onClick: ikon.buka } ),
					el( RichText, { tagName: 'span', value: a.text, onChange: Setel( props, 'text' ), placeholder: 'Lencana', allowedFormats: [] } )
				),
				ikon.modal
			);
		},
		save: function () {
			return null;
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/steps & vb/step                                                  */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/steps', {
		edit: function ( props ) {
			var jumlah = wp.data.useSelect( function ( s ) {
				return s( 'core/block-editor' ).getBlockCount( props.clientId );
			}, [ props.clientId ] );
			var blockProps = useBlockProps( { className: 'vb-steps vb-steps--' + props.attributes.style, style: { '--vb-steps': Math.max( 1, jumlah ) } } );
			var inner = useInnerBlocksProps( blockProps, {
				allowedBlocks: [ 'vb/step' ],
				orientation: 'horizontal',
				template: [ [ 'vb/step' ], [ 'vb/step' ], [ 'vb/step' ] ],
				renderAppender: props.isSelected ? InnerBlocks.ButtonBlockAppender : false,
			} );
			return el( 'ol', inner );
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	daftarkan( 'vb/step', {
		edit: function ( props ) {
			var a = props.attributes;
			var ikon = useIkon( props, 'icon' );
			return el( Fragment, null,
				Toolbar( ikon.toolbar ),
				el( 'li', useBlockProps( { className: 'vb-step' } ),
					el( 'span', { className: 'vb-step__num', onClick: ikon.buka }, el( Ikon, { name: a.icon } ) ),
					el( RichText, { tagName: 'h3', className: 'vb-step__title', value: a.title, onChange: Setel( props, 'title' ), placeholder: 'Nama langkah', allowedFormats: TEKS_JUDUL } ),
					( a.text || props.isSelected ) && el( RichText, { tagName: 'p', className: 'vb-step__text', value: a.text, onChange: Setel( props, 'text' ), placeholder: 'Penjelasan singkat', allowedFormats: TEKS } )
				),
				ikon.modal
			);
		},
		save: function () {
			return null;
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/card                                                             */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/card', {
		edit: function ( props ) {
			var a = props.attributes;
			var set = props.setAttributes;
			var an = useState( null );
			var blockProps = useBlockProps( { ref: an[ 1 ], className: 'vb-card vb-card--' + a.cardStyle, style: { '--vb-ratio': a.ratio } } );
			var tautan = useTautan( props, an[ 0 ] );
			var pilihGambar = function ( m ) {
				set( { imageUrl: ( m.sizes && m.sizes.large ? m.sizes.large.url : m.url ), imageId: m.id } );
			};
			return el( Fragment, null,
				Toolbar(
					el( MediaUploadCheck, null, el( MediaUpload, { allowedTypes: [ 'image' ], value: a.imageId, onSelect: pilihGambar, render: function ( o ) {
						return el( c.ToolbarButton, { icon: 'format-image', label: a.imageUrl ? 'Ganti gambar' : 'Pilih gambar', onClick: o.open } );
					} } ) ),
					tautan.toolbar
				),
				el( InspectorControls, null, Panel( 'Kartu', [
					Pilih( 'Gaya', a.cardStyle, { below: 'Teks di bawah gambar', overlay: 'Teks di atas gambar' }, Setel( props, 'cardStyle' ) ),
					Pilih( 'Rasio gambar', a.ratio, { '1/1': 'Persegi 1:1', '4/3': '4:3', '3/2': '3:2', '16/9': '16:9', '3/4': 'Potret 3:4' }, Setel( props, 'ratio' ) ),
				] ) ),
				el( 'div', blockProps,
					el( 'div', { className: 'vb-card__media' },
						a.imageUrl ? el( 'img', { className: 'vb-card__img', src: a.imageUrl, alt: '' } ) :
							el( be.MediaPlaceholder, { icon: 'format-image', labels: { title: 'Gambar kartu' }, allowedTypes: [ 'image' ], onSelect: pilihGambar, accept: 'image/*' } )
					),
					el( 'div', { className: 'vb-card__body' },
						el( RichText, { tagName: 'h3', className: 'vb-card__title', value: a.title, onChange: Setel( props, 'title' ), placeholder: 'Judul kartu', allowedFormats: TEKS_JUDUL } ),
						( a.text || props.isSelected ) && el( RichText, { tagName: 'p', className: 'vb-card__text', value: a.text, onChange: Setel( props, 'text' ), placeholder: 'Teks (opsional)', allowedFormats: TEKS } ),
						a.url && ( a.linkLabel || props.isSelected ) && el( RichText, { tagName: 'span', className: 'vb-card__link', value: a.linkLabel, onChange: Setel( props, 'linkLabel' ), placeholder: 'Teks tautan (opsional)', allowedFormats: [] } )
					)
				),
				tautan.popover
			);
		},
		save: function () {
			return null;
		},
	} );


	/* ------------------------------------------------------------------ */
	/* vb/testimonials & vb/testimonial                                    */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/testimonials', {
		edit: function ( props ) {
			var a = props.attributes;
			var blockProps = useBlockProps( {
				className: 'vb-testi vb-testi--' + a.cardStyle + ' vb-testi--editor',
				style: { '--vb-pv': a.perView, '--vb-pv-t': a.perViewTablet, '--vb-pv-m': a.perViewMobile },
			} );
			var inner = useInnerBlocksProps( { className: 'vb-testi__track' }, {
				allowedBlocks: [ 'vb/testimonial' ],
				orientation: 'horizontal',
				template: [ [ 'vb/testimonial' ], [ 'vb/testimonial' ], [ 'vb/testimonial' ] ],
				renderAppender: InnerBlocks.ButtonBlockAppender,
			} );
			return el( Fragment, null,
				el( InspectorControls, null,
					Panel( 'Carousel', [
						el( c.RangeControl, { key: 'd', label: 'Kartu terlihat — desktop', value: a.perView, min: 1, max: 5, onChange: Setel( props, 'perView' ) } ),
						el( c.RangeControl, { key: 't', label: 'Kartu terlihat — tablet', value: a.perViewTablet, min: 1, max: 4, onChange: Setel( props, 'perViewTablet' ) } ),
						el( c.RangeControl, { key: 'm', label: 'Kartu terlihat — HP', value: a.perViewMobile, min: 1, max: 2, onChange: Setel( props, 'perViewMobile' ) } ),
						el( c.ToggleControl, { key: 'ap', label: 'Geser otomatis', checked: a.autoplay, onChange: Setel( props, 'autoplay' ), __nextHasNoMarginBottom: true } ),
						a.autoplay && el( c.RangeControl, { key: 'iv', label: 'Jeda geser (detik)', value: a.interval, min: 3, max: 15, onChange: Setel( props, 'interval' ) } ),
						el( c.ToggleControl, { key: 'ar', label: 'Tombol panah', checked: a.showArrows, onChange: Setel( props, 'showArrows' ), __nextHasNoMarginBottom: true } ),
						el( c.ToggleControl, { key: 'dt', label: 'Titik navigasi', checked: a.showDots, onChange: Setel( props, 'showDots' ), __nextHasNoMarginBottom: true } ),
						Pilih( 'Gaya kartu', a.cardStyle, { dark: 'Gelap (di latar gelap)', light: 'Putih (di latar terang)' }, Setel( props, 'cardStyle' ) ),
						el( 'p', { key: 'tip', className: 'vb-tip' }, 'Di editor semua testimoni tampil berjajar supaya mudah disunting; di situs tampil sebagai carousel. Tambah lewat tombol +, hapus/geser lewat toolbar tiap testimoni.' ),
					] )
				),
				el( 'div', blockProps, el( 'div', inner ) )
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	daftarkan( 'vb/testimonial', {
		edit: function ( props ) {
			var a = props.attributes;
			var set = props.setAttributes;
			var inisial = ( a.name || '' ).replace( /<[^>]+>/g, '' ).trim().split( /\s+/ ).slice( 0, 2 ).map( function ( k ) {
				return k.charAt( 0 ).toUpperCase();
			} ).join( '' );
			var bintang = [ 1, 2, 3, 4, 5 ].map( function ( n ) {
				return el( 'button', { key: n, type: 'button', className: 'vb-testi__star' + ( n <= a.rating ? ' is-on' : '' ), title: n + ' bintang', onClick: function () {
					set( { rating: n === a.rating ? n - 1 : n } );
				} }, '★' );
			} );
			var pilihFoto = function ( m ) {
				set( { photoUrl: m.sizes && m.sizes.thumbnail ? m.sizes.thumbnail.url : m.url, photoId: m.id } );
			};
			return el( Fragment, null,
				Toolbar(
					el( MediaUploadCheck, null, el( MediaUpload, { allowedTypes: [ 'image' ], value: a.photoId, onSelect: pilihFoto, render: function ( o ) {
						return el( c.ToolbarButton, { icon: 'format-image', label: a.photoUrl ? 'Ganti foto' : 'Pasang foto (opsional)', onClick: o.open } );
					} } ) ),
					a.photoUrl && el( c.ToolbarButton, { icon: 'no-alt', label: 'Hapus foto (pakai inisial)', onClick: function () {
						set( { photoUrl: '', photoId: 0 } );
					} } )
				),
				el( 'figure', useBlockProps( { className: 'vb-testi__item' } ),
					el( 'span', { className: 'vb-testi__mark' }, '“' ),
					el( 'p', { className: 'vb-testi__stars vb-testi__stars--edit' }, bintang ),
					el( RichText, { tagName: 'blockquote', className: 'vb-testi__quote', value: a.quote, onChange: Setel( props, 'quote' ), placeholder: 'Tulis kutipan testimoni…', allowedFormats: TEKS_JUDUL } ),
					el( 'figcaption', { className: 'vb-testi__who' },
						a.photoUrl ? el( 'img', { className: 'vb-testi__avatar', src: a.photoUrl, alt: '' } ) :
							el( 'span', { className: 'vb-testi__avatar vb-testi__avatar--inisial' }, inisial || '?' ),
						el( 'span', { className: 'vb-testi__meta' },
							el( RichText, { tagName: 'strong', className: 'vb-testi__name', value: a.name, onChange: Setel( props, 'name' ), placeholder: 'Nama pemberi testimoni', allowedFormats: [] } ),
							el( RichText, { tagName: 'span', className: 'vb-testi__role', value: a.role, onChange: Setel( props, 'role' ), placeholder: 'Jabatan — Kota, Negara', allowedFormats: [] } )
						)
					)
				)
			);
		},
		save: function () {
			return null;
		},
	} );


	/* ------------------------------------------------------------------ */
	/* vb/faq & vb/faq-item                                                */
	/* ------------------------------------------------------------------ */
	/* ------------------------------------------------------------------ */
	/* vb/carousel — wadah geser untuk blok apa pun                        */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/carousel', {
		edit: function ( props ) {
			var a = props.attributes;
			var blockProps = useBlockProps( {
				className: 'vb-carousel vb-carousel--' + a.tone + ' vb-carousel--editor',
				style: { '--vb-pv': a.perView, '--vb-pv-t': a.perViewTablet, '--vb-pv-m': a.perViewMobile },
			} );
			var inner = useInnerBlocksProps( { className: 'vb-carousel__track' }, {
				orientation: 'horizontal',
				template: [ [ 'vb/card' ], [ 'vb/card' ], [ 'vb/card' ] ],
				renderAppender: InnerBlocks.ButtonBlockAppender,
			} );
			return el( Fragment, null,
				el( InspectorControls, null,
					Panel( 'Geser (carousel)', [
						el( c.RangeControl, { key: 'd', label: 'Item terlihat — desktop', value: a.perView, min: 1, max: 6, onChange: Setel( props, 'perView' ) } ),
						el( c.RangeControl, { key: 't', label: 'Item terlihat — tablet', value: a.perViewTablet, min: 1, max: 4, onChange: Setel( props, 'perViewTablet' ) } ),
						el( c.RangeControl, { key: 'm', label: 'Item terlihat — HP', value: a.perViewMobile, min: 1, max: 2, onChange: Setel( props, 'perViewMobile' ) } ),
						el( c.ToggleControl, { key: 'ap', label: 'Geser otomatis', checked: a.autoplay, onChange: Setel( props, 'autoplay' ), __nextHasNoMarginBottom: true } ),
						a.autoplay && el( c.RangeControl, { key: 'iv', label: 'Jeda geser (detik)', value: a.interval, min: 3, max: 15, onChange: Setel( props, 'interval' ) } ),
						el( c.ToggleControl, { key: 'ar', label: 'Tombol panah', checked: a.showArrows, onChange: Setel( props, 'showArrows' ), __nextHasNoMarginBottom: true } ),
						el( c.ToggleControl, { key: 'dt', label: 'Titik navigasi', checked: a.showDots, onChange: Setel( props, 'showDots' ), __nextHasNoMarginBottom: true } ),
						Pilih( 'Warna tombol', a.tone, { auto: 'Ikut latar seksi', light: 'Terang (di latar gelap)', dark: 'Gelap (di latar terang)' }, Setel( props, 'tone' ) ),
						el( c.TextControl, { key: 'lb', label: 'Sebutan isi (untuk pembaca layar)', value: a.label, placeholder: 'mis. Portofolio', onChange: Setel( props, 'label' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
						el( 'p', { key: 'tip', className: 'vb-tip' }, 'Di editor isinya tampil berjajar supaya mudah disunting; di situs jadi carousel yang bisa digeser. Blok apa pun boleh dimasukkan.' ),
					] )
				),
				el( 'div', blockProps, el( 'div', inner ) )
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/price — kartu paket/layanan                                      */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/price', {
		edit: function ( props ) {
			var a = props.attributes;
			var blockProps = useBlockProps( { className: 'vb-price' + ( a.featured ? ' vb-price--unggulan' : '' ) } );
			var ikon = useIkon( props, 'icon', { gambar: true } );
			var inner = useInnerBlocksProps( { className: 'vb-price__isi' }, {
				template: [ [ 'core/list', {}, [ [ 'core/list-item', { content: 'Isi paket' } ] ] ], [ 'vb/button', { text: 'Konsultasi', variant: 'outline' } ] ],
				renderAppender: props.isSelected ? InnerBlocks.ButtonBlockAppender : false,
			} );
			return el( Fragment, null,
				Toolbar( ikon.toolbar ),
				el( InspectorControls, null, Panel( 'Kartu paket', [
					el( c.ToggleControl, { key: 'f', label: 'Tandai sebagai pilihan utama', checked: a.featured, onChange: Setel( props, 'featured' ), __nextHasNoMarginBottom: true } ),
					el( c.TextControl, { key: 'b', label: 'Label kecil (mis. Paling dipilih)', value: a.badge, onChange: Setel( props, 'badge' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
				] ) ),
				el( 'div', blockProps,
					a.badge && el( 'span', { className: 'vb-price__badge' }, a.badge ),
					el( 'div', { className: 'vb-price__kepala' },
						el( Ikon, { name: a.icon, url: a.iconUrl, className: 'vb-ikon vb-price__icon', onClick: ikon.buka,
							kosong: props.isSelected ? el( 'button', { type: 'button', className: 'vb-ikon vb-price__icon vb-ikon--tambah', onClick: ikon.buka }, '+' ) : null } ),
						el( RichText, { tagName: 'h3', className: 'vb-price__title', value: a.title, onChange: Setel( props, 'title' ), placeholder: 'Nama paket', allowedFormats: TEKS_JUDUL } ),
						( a.price || props.isSelected ) && el( RichText, { tagName: 'p', className: 'vb-price__harga', value: a.price, onChange: Setel( props, 'price' ), placeholder: 'Harga / keterangan harga (opsional)', allowedFormats: TEKS_JUDUL } ),
						( a.note || props.isSelected ) && el( RichText, { tagName: 'p', className: 'vb-price__note', value: a.note, onChange: Setel( props, 'note' ), placeholder: 'Keterangan singkat (opsional)', allowedFormats: TEKS } )
					),
					el( 'div', inner )
				),
				ikon.modal
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/faq & vb/faq-item                                                */
	/* ------------------------------------------------------------------ */
	/* ------------------------------------------------------------------ */
	/* vb/carousel — wadah geser untuk blok apa pun                        */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/carousel', {
		edit: function ( props ) {
			var a = props.attributes;
			var blockProps = useBlockProps( {
				className: 'vb-carousel vb-carousel--' + a.tone + ' vb-carousel--editor',
				style: { '--vb-pv': a.perView, '--vb-pv-t': a.perViewTablet, '--vb-pv-m': a.perViewMobile },
			} );
			var inner = useInnerBlocksProps( { className: 'vb-carousel__track' }, {
				orientation: 'horizontal',
				template: [ [ 'vb/card' ], [ 'vb/card' ], [ 'vb/card' ] ],
				renderAppender: InnerBlocks.ButtonBlockAppender,
			} );
			return el( Fragment, null,
				el( InspectorControls, null,
					Panel( 'Geser (carousel)', [
						el( c.RangeControl, { key: 'd', label: 'Item terlihat — desktop', value: a.perView, min: 1, max: 6, onChange: Setel( props, 'perView' ) } ),
						el( c.RangeControl, { key: 't', label: 'Item terlihat — tablet', value: a.perViewTablet, min: 1, max: 4, onChange: Setel( props, 'perViewTablet' ) } ),
						el( c.RangeControl, { key: 'm', label: 'Item terlihat — HP', value: a.perViewMobile, min: 1, max: 2, onChange: Setel( props, 'perViewMobile' ) } ),
						el( c.ToggleControl, { key: 'ap', label: 'Geser otomatis', checked: a.autoplay, onChange: Setel( props, 'autoplay' ), __nextHasNoMarginBottom: true } ),
						a.autoplay && el( c.RangeControl, { key: 'iv', label: 'Jeda geser (detik)', value: a.interval, min: 3, max: 15, onChange: Setel( props, 'interval' ) } ),
						el( c.ToggleControl, { key: 'ar', label: 'Tombol panah', checked: a.showArrows, onChange: Setel( props, 'showArrows' ), __nextHasNoMarginBottom: true } ),
						el( c.ToggleControl, { key: 'dt', label: 'Titik navigasi', checked: a.showDots, onChange: Setel( props, 'showDots' ), __nextHasNoMarginBottom: true } ),
						Pilih( 'Warna tombol', a.tone, { auto: 'Ikut latar seksi', light: 'Terang (di latar gelap)', dark: 'Gelap (di latar terang)' }, Setel( props, 'tone' ) ),
						el( c.TextControl, { key: 'lb', label: 'Sebutan isi (untuk pembaca layar)', value: a.label, placeholder: 'mis. Portofolio', onChange: Setel( props, 'label' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
						el( 'p', { key: 'tip', className: 'vb-tip' }, 'Di editor isinya tampil berjajar supaya mudah disunting; di situs jadi carousel yang bisa digeser. Blok apa pun boleh dimasukkan.' ),
					] )
				),
				el( 'div', blockProps, el( 'div', inner ) )
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	/* ------------------------------------------------------------------ */
	/* vb/price — kartu paket/layanan                                      */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/price', {
		edit: function ( props ) {
			var a = props.attributes;
			var set = props.setAttributes;
			var m = useState( false );
			var modal = m[ 0 ];
			var setModal = m[ 1 ];
			var blockProps = useBlockProps( { className: 'vb-price' + ( a.featured ? ' vb-price--unggulan' : '' ) } );
			var inner = useInnerBlocksProps( { className: 'vb-price__isi' }, {
				template: [ [ 'core/list', {}, [ [ 'core/list-item', { content: 'Isi paket' } ] ] ], [ 'vb/button', { text: 'Konsultasi', variant: 'outline' } ] ],
				renderAppender: props.isSelected ? InnerBlocks.ButtonBlockAppender : false,
			} );
			return el( Fragment, null,
				el( Toolbar(),
					el( c.ToolbarButton, { icon: 'star-filled', label: 'Pilih ikon', onClick: function () {
						setModal( true );
					} } )
				),
				el( InspectorControls, null, Panel( 'Kartu paket', [
					el( c.ToggleControl, { key: 'f', label: 'Tandai sebagai pilihan utama', checked: a.featured, onChange: Setel( props, 'featured' ), __nextHasNoMarginBottom: true } ),
					el( c.TextControl, { key: 'b', label: 'Label kecil (mis. Paling dipilih)', value: a.badge, onChange: Setel( props, 'badge' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
				] ) ),
				modal && el( ModalIkon, { value: a.icon, bolehKosong: true, onClose: function () {
					setModal( false );
				}, onChange: function ( v ) {
					set( { icon: v, iconUrl: '' } );
				}, onUnggah: function ( url ) {
					set( { iconUrl: url, icon: '' } );
				} } ),
				el( 'div', blockProps,
					el( 'div', { className: 'vb-price__kepala' },
						el( Ikon, {
							name: a.icon,
							url: a.iconUrl,
							className: 'vb-ikon vb-price__icon',
							onClick: function () {
								setModal( true );
							},
							kosong: el( 'button', { type: 'button', className: 'vb-ikon--tambah', onClick: function () {
								setModal( true );
							}, title: 'Pilih ikon' }, '+' ),
						} ),
						el( RichText, {
							tagName: 'h3',
							className: 'vb-price__title',
							value: a.title,
							allowedFormats: TEKS_JUDUL,
							placeholder: 'Nama paket',
							onChange: Setel( props, 'title' ),
						} ),
						el( RichText, {
							tagName: 'p',
							className: 'vb-price__harga',
							value: a.price,
							allowedFormats: TEKS_JUDUL,
							placeholder: 'Harga / keterangan harga',
							onChange: Setel( props, 'price' ),
						} ),
						el( RichText, {
							tagName: 'p',
							className: 'vb-price__note',
							value: a.note,
							allowedFormats: TEKS,
							placeholder: 'Keterangan singkat paket',
							onChange: Setel( props, 'note' ),
						} )
					),
					el( 'div', inner )
				)
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	daftarkan( 'vb/faq', {
		edit: function ( props ) {
			var a = props.attributes;
			var inner = useInnerBlocksProps( useBlockProps( { className: 'vb-faq vb-faq--' + a.style + ' vb-faq--editor' } ), {
				allowedBlocks: [ 'vb/faq-item' ],
				template: [ [ 'vb/faq-item' ], [ 'vb/faq-item' ], [ 'vb/faq-item' ] ],
				renderAppender: InnerBlocks.ButtonBlockAppender,
			} );
			return el( Fragment, null,
				el( InspectorControls, null, Panel( 'FAQ', [
					Pilih( 'Gaya', a.style, { card: 'Kartu putih', line: 'Garis pemisah', dark: 'Gelap (di latar gelap)' }, Setel( props, 'style' ) ),
					el( c.ToggleControl, { key: 'o', label: 'Pertanyaan pertama terbuka', checked: a.openFirst, onChange: Setel( props, 'openFirst' ), __nextHasNoMarginBottom: true } ),
					el( c.ToggleControl, { key: 's', label: 'Hanya satu terbuka sekaligus', checked: a.singleOpen, onChange: Setel( props, 'singleOpen' ), __nextHasNoMarginBottom: true } ),
					el( c.ToggleControl, { key: 'j', label: 'Schema FAQ untuk Google', checked: a.schema, onChange: Setel( props, 'schema' ), __nextHasNoMarginBottom: true } ),
					el( 'p', { key: 'tip', className: 'vb-tip' }, 'Di editor semua jawaban terbuka supaya mudah disunting. Tambah pertanyaan lewat tombol di bawah daftar; hapus/geser lewat toolbar tiap pertanyaan.' ),
				] ) ),
				el( 'div', inner )
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	daftarkan( 'vb/faq-item', {
		edit: function ( props ) {
			var a = props.attributes;
			return el( 'div', useBlockProps( { className: 'vb-faq__item is-open' } ),
				el( 'div', { className: 'vb-faq__q' },
					el( RichText, { tagName: 'span', value: a.question, onChange: Setel( props, 'question' ), placeholder: 'Tulis pertanyaan…', allowedFormats: [] } ),
					el( 'span', { className: 'vb-faq__ikon' } )
				),
				el( RichText, { tagName: 'div', className: 'vb-faq__a', value: a.answer, onChange: Setel( props, 'answer' ), placeholder: 'Tulis jawaban…', allowedFormats: TEKS } )
			);
		},
		save: function () {
			return null;
		},
	} );


	/* ------------------------------------------------------------------ */
	/* vb/logos & vb/logo-item                                             */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/logos', {
		edit: function ( props ) {
			var a = props.attributes;
			var inner = useInnerBlocksProps( useBlockProps( {
				className: 'vb-logos vb-logos--' + a.cardStyle + ' vb-logos--editor' + ( a.showLabel ? '' : ' vb-logos--tanpa-label' ),
				style: { '--vb-logo-h': a.logoHeight + 'px' },
			} ), {
				allowedBlocks: [ 'vb/logo-item' ],
				orientation: 'horizontal',
				template: [ [ 'vb/logo-item' ], [ 'vb/logo-item' ], [ 'vb/logo-item' ], [ 'vb/logo-item' ] ],
				renderAppender: InnerBlocks.ButtonBlockAppender,
			} );
			return el( Fragment, null,
				el( InspectorControls, null, Panel( 'Carousel logo', [
					el( c.ToggleControl, { key: 'an', label: 'Berjalan terus (animasi)', checked: a.animate, onChange: Setel( props, 'animate' ), __nextHasNoMarginBottom: true } ),
					a.animate && el( c.RangeControl, { key: 'sp', label: 'Durasi satu putaran (detik, makin besar makin pelan)', value: a.speed, min: 10, max: 120, step: 5, onChange: Setel( props, 'speed' ) } ),
					el( c.RangeControl, { key: 'h', label: 'Tinggi logo (px)', value: a.logoHeight, min: 32, max: 160, step: 4, onChange: Setel( props, 'logoHeight' ) } ),
					el( c.ToggleControl, { key: 'lb', label: 'Tampilkan keterangan', checked: a.showLabel, onChange: Setel( props, 'showLabel' ), __nextHasNoMarginBottom: true } ),
					Pilih( 'Gaya', a.cardStyle, { card: 'Kartu putih', plain: 'Polos' }, Setel( props, 'cardStyle' ) ),
					el( 'p', { key: 'tip', className: 'vb-tip' }, 'Di editor logo tampil berjajar supaya mudah diganti; di situs berjalan terus. Ganti gambar lewat tombol gambar di toolbar tiap logo.' ),
				] ) ),
				el( 'div', inner )
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	daftarkan( 'vb/logo-item', {
		edit: function ( props ) {
			var a = props.attributes;
			var set = props.setAttributes;
			var an = useState( null );
			var tautan = useTautan( props, an[ 0 ] );
			var pilih = function ( m ) {
				set( { imageUrl: m.sizes && m.sizes.medium ? m.sizes.medium.url : m.url, imageId: m.id } );
			};
			return el( Fragment, null,
				Toolbar(
					el( MediaUploadCheck, null, el( MediaUpload, { allowedTypes: [ 'image' ], value: a.imageId, onSelect: pilih, render: function ( o ) {
						return el( c.ToolbarButton, { icon: 'format-image', label: a.imageUrl ? 'Ganti logo' : 'Pilih logo', onClick: o.open } );
					} } ) ),
					tautan.toolbar
				),
				el( 'figure', useBlockProps( { ref: an[ 1 ], className: 'vb-logos__item' } ),
					a.imageUrl ? el( 'img', { className: 'vb-logos__img', src: a.imageUrl, alt: '' } ) :
						el( MediaUploadCheck, null, el( MediaUpload, { allowedTypes: [ 'image' ], onSelect: pilih, render: function ( o ) {
							return el( 'button', { type: 'button', className: 'vb-logos__img vb-logos__img--kosong vb-logos__pilih', onClick: o.open }, '+ Logo' );
						} } ) ),
					el( RichText, { tagName: 'figcaption', className: 'vb-logos__label', value: a.label, onChange: Setel( props, 'label' ), placeholder: 'Keterangan', allowedFormats: [] } )
				),
				tautan.popover
			);
		},
		save: function () {
			return null;
		},
	} );

	/* ------------------------------------------------------------------ */
	/* Blok data (pratinjau server)                                        */
	/* ------------------------------------------------------------------ */
	function pratinjau( nama, panel ) {
		daftarkan( nama, {
			edit: function ( props ) {
				return el( Fragment, null,
					panel && el( InspectorControls, null, panel( props ) ),
					el( 'div', useBlockProps( { className: 'vb-ssr' } ), el( SSR, { block: nama, attributes: props.attributes } ) )
				);
			},
			save: function () {
				return null;
			},
		} );
	}

	var tautanDataSitus = el( 'p', { key: 'ds', className: 'vb-tip' }, 'Isi diambil dari ', el( 'a', { href: 'themes.php?page=vb-situs', target: '_blank' }, 'Tampilan → Data Situs' ), '.' );

	pratinjau( 'vb/products', function ( props ) {
		var a = props.attributes;
		return Panel( 'Katalog', [
			Pilih( 'Tampilan', a.layout, { tabs: 'Tab per kategori', grid: 'Grid' }, Setel( props, 'layout' ) ),
			a.layout === 'grid' && el( c.TextControl, { key: 'k', label: 'Slug kategori (kosong = semua)', value: a.category, onChange: Setel( props, 'category' ), __nextHasNoMarginBottom: true } ),
			el( c.RangeControl, { key: 'n', label: 'Jumlah produk per tab/grid', value: a.count, min: 1, max: 48, onChange: Setel( props, 'count' ) } ),
			el( c.RangeControl, { key: 'c', label: 'Kolom desktop', value: a.columns, min: 2, max: 6, onChange: Setel( props, 'columns' ) } ),
			el( c.ToggleControl, { key: 'e', label: 'Tampilkan ringkasan', checked: a.showExcerpt, onChange: Setel( props, 'showExcerpt' ), __nextHasNoMarginBottom: true } ),
			el( c.ToggleControl, { key: 'v', label: 'Tombol "semua produk"', checked: a.showViewAll, onChange: Setel( props, 'showViewAll' ), __nextHasNoMarginBottom: true } ),
			a.showViewAll && el( c.TextControl, { key: 'vl', label: 'Teks tombol', value: a.viewAllLabel, onChange: Setel( props, 'viewAllLabel' ), __nextHasNoMarginBottom: true } ),
			el( 'p', { key: 'tip', className: 'vb-tip' }, 'Produk & kategori diatur di menu Produk.' ),
		] );
	} );
	pratinjau( 'vb/product-details', null );
	pratinjau( 'vb/portfolio', function ( props ) {
		var a = props.attributes;
		return Panel( 'Portofolio', [
			Pilih( 'Tampilan', a.layout, { grid: 'Grid kartu', carousel: 'Carousel (geser)', slider: 'Slider foto besar', tiles: 'Ubin foto rapat' }, Setel( props, 'layout' ) ),
			Pilih( 'Urutan', a.orderBy, { urutan: 'Kolom "Urutan" di menu Portofolio', terbaru: 'Terbaru lebih dulu' }, Setel( props, 'orderBy' ) ),
			el( c.RangeControl, { key: 'n', label: 'Jumlah karya (0 = semua)', value: a.count, min: 0, max: 60, onChange: Setel( props, 'count' ) } ),
			el( c.RangeControl, { key: 'c', label: 'Kolom desktop', value: a.columns, min: 1, max: 6, onChange: Setel( props, 'columns' ) } ),
			el( c.RangeControl, { key: 't', label: 'Kolom tablet', value: a.columnsTablet, min: 1, max: 4, onChange: Setel( props, 'columnsTablet' ) } ),
			el( c.RangeControl, { key: 'm', label: 'Kolom HP', value: a.columnsMobile, min: 1, max: 2, onChange: Setel( props, 'columnsMobile' ) } ),
			el( c.TextControl, { key: 'k', label: 'Slug kategori (kosong = semua, pisahkan koma)', value: a.category, onChange: Setel( props, 'category' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
			a.layout !== 'carousel' && a.layout !== 'slider' && el( c.ToggleControl, { key: 'f', label: 'Tombol saring kategori', checked: a.showFilter, onChange: Setel( props, 'showFilter' ), __nextHasNoMarginBottom: true } ),
			a.layout !== 'tiles' && a.layout !== 'slider' && el( c.ToggleControl, { key: 'e', label: 'Tampilkan ringkasan', checked: a.showExcerpt, onChange: Setel( props, 'showExcerpt' ), __nextHasNoMarginBottom: true } ),
			Pilih( 'Klik karya membuka', a.linkTo, { detail: 'Halaman detail portofolio', situs: 'Situs klien (tab baru)' }, Setel( props, 'linkTo' ) ),
			a.layout !== 'tiles' && a.layout !== 'slider' && el( c.TextControl, { key: 'l', label: 'Teks tautan (kosong = tanpa tautan)', value: a.linkLabel, onChange: Setel( props, 'linkLabel' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
			( a.layout === 'carousel' || a.layout === 'slider' ) && el( c.ToggleControl, { key: 'a', label: 'Geser otomatis', checked: a.autoplay, onChange: Setel( props, 'autoplay' ), __nextHasNoMarginBottom: true } ),
			( a.layout === 'carousel' || a.layout === 'slider' ) && a.autoplay && el( c.RangeControl, { key: 'iv', label: 'Jeda geser (detik)', value: a.interval, min: 3, max: 15, onChange: Setel( props, 'interval' ) } ),
			Pilih( 'Rasio foto', a.ratio, { '16/10': '16:10', '4/3': '4:3', '1/1': 'Persegi', '3/4': 'Potret' }, Setel( props, 'ratio' ) ),
			el( 'p', { key: 'tip', className: 'vb-tip' }, 'Karya ditambah, diubah, diurutkan, dan dihapus di menu Portofolio (kiri). Foto = gambar unggulan, keterangan = ringkasan.' ),
		] );
	} );
	pratinjau( 'vb/contact-info', function ( props ) {
		var a = props.attributes;
		var jenis = { alamat: 'Alamat', whatsapp: 'WhatsApp', telepon: 'Telepon', email: 'Email', jam: 'Jam', website: 'Website', lainnya: 'Lainnya' };
		return Panel( 'Kontak', [
			Pilih( 'Tampilan', a.layout, { list: 'Daftar', cards: 'Kartu', inline: 'Sebaris' }, Setel( props, 'layout' ) ),
			el( c.ToggleControl, { key: 'l', label: 'Tampilkan label', checked: a.showLabel, onChange: Setel( props, 'showLabel' ), __nextHasNoMarginBottom: true } ),
			el( c.RangeControl, { key: 'pj', label: 'Maks. baris per jenis (0 = semua)', help: 'Mis. 1 = hanya alamat pertama.', value: a.perJenis, min: 0, max: 5, onChange: Setel( props, 'perJenis' ) } ),
			el( 'p', { key: 'j', className: 'vb-tip' }, 'Jenis yang ditampilkan (kosong semua = tampil semua):' ),
			Object.keys( jenis ).map( function ( k ) {
				return el( c.CheckboxControl, { key: 'j' + k, label: jenis[ k ], checked: a.show.indexOf( k ) !== -1, __nextHasNoMarginBottom: true, onChange: function ( on ) {
					var baru = a.show.filter( function ( x ) {
						return x !== k;
					} );
					if ( on ) {
						baru.push( k );
					}
					props.setAttributes( { show: baru } );
				} } );
			} ),
			tautanDataSitus,
		] );
	} );
	pratinjau( 'vb/social', function ( props ) {
		var a = props.attributes;
		return Panel( 'Media sosial', [
			Pilih( 'Ukuran', a.size, { sm: 'Kecil', md: 'Sedang', lg: 'Besar' }, Setel( props, 'size' ) ),
			Pilih( 'Perataan', a.justify, PERATAAN, Setel( props, 'justify' ) ),
			tautanDataSitus,
		] );
	} );
	pratinjau( 'vb/rfq-form', function ( props ) {
		return Panel( 'Form Pemesanan', [
			el( c.TextControl, { key: 't', label: 'Teks tombol kirim', value: props.attributes.buttonText, onChange: Setel( props, 'buttonText' ), __nextHasNoMarginBottom: true } ),
			el( 'p', { key: 'i', className: 'vb-tip' }, 'Kiriman masuk ke email pertama di Data Situs dan tersimpan di menu Pemesanan Masuk. Pilihan layanannya diatur di Tampilan → Data Situs.' ),
		] );
	} );
	pratinjau( 'vb/map', function ( props ) {
		return Panel( 'Peta', [
			el( c.TextControl, { key: 'q', label: 'Alamat / koordinat (kosong = Data Situs)', value: props.attributes.query, onChange: Setel( props, 'query' ), __nextHasNoMarginBottom: true } ),
			el( c.RangeControl, { key: 'h', label: 'Tinggi (px)', value: props.attributes.height, min: 200, max: 800, step: 20, onChange: Setel( props, 'height' ) } ),
		] );
	} );
	/* ------------------------------------------------------------------ */
	/* Modul sewa: daftar unit (pratinjau server), form booking, remah     */
	/* ------------------------------------------------------------------ */
	pratinjau( 'vb/rentals', function ( props ) {
		var a = props.attributes;
		return Panel( 'Daftar sewa', [
			el( c.RangeControl, { key: 'n', label: 'Jumlah unit (0 = semua)', value: a.count, min: 0, max: 48, onChange: Setel( props, 'count' ) } ),
			el( c.RangeControl, { key: 'c', label: 'Kolom desktop', value: a.columns, min: 1, max: 6, onChange: Setel( props, 'columns' ) } ),
			el( c.RangeControl, { key: 't', label: 'Kolom tablet', value: a.columnsTablet, min: 1, max: 4, onChange: Setel( props, 'columnsTablet' ) } ),
			el( c.RangeControl, { key: 'm', label: 'Kolom HP', value: a.columnsMobile, min: 1, max: 2, onChange: Setel( props, 'columnsMobile' ) } ),
			Pilih( 'Rasio foto', a.ratio, { '4/3': '4:3', '16/10': '16:10', '1/1': 'Persegi' }, Setel( props, 'ratio' ) ),
			el( c.TextControl, { key: 'b', label: 'Teks tombol (kosong = tanpa tombol)', value: a.buttonText, onChange: Setel( props, 'buttonText' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
			el( c.TextareaControl, { key: 'w', label: 'Pesan WhatsApp', help: '{nama} diganti nama unit.', value: a.waMessage, onChange: Setel( props, 'waMessage' ), __nextHasNoMarginBottom: true } ),
			el( c.TextControl, { key: 'e', label: 'Teks bila harga kosong', value: a.emptyPrice, onChange: Setel( props, 'emptyPrice' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
			el( 'p', { key: 'tip', className: 'vb-tip' }, 'Unit, foto, harga, dan urutan diatur di ', el( 'a', { href: 'edit.php?post_type=vb_sewa', target: '_blank' }, 'menu Scooter (Sewa)' ), '. Nomor WhatsApp dari Tampilan → Data Situs.' ),
		] );
	} );

	pratinjau( 'vb/breadcrumb', function ( props ) {
		var a = props.attributes;
		return Panel( 'Remah halaman', [
			el( c.TextControl, { key: 'h', label: 'Sebutan beranda', value: a.homeLabel, onChange: Setel( props, 'homeLabel' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
			el( c.TextControl, { key: 's', label: 'Sebutan halaman pencarian', value: a.searchLabel, onChange: Setel( props, 'searchLabel' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
			el( c.ToggleControl, { key: 'u', label: 'Huruf kapital', checked: a.uppercase, onChange: Setel( props, 'uppercase' ), __nextHasNoMarginBottom: true } ),
			el( 'p', { key: 'tip', className: 'vb-tip' }, 'Terisi otomatis dari judul halaman.' ),
		] );
	} );

	daftarkan( 'vb/booking-form', {
		edit: function ( props ) {
			var a = props.attributes;
			function Teks( kunci, tag, kelas, ph ) {
				return el( RichText, { tagName: tag, className: kelas, value: a[ kunci ], onChange: Setel( props, kunci ), placeholder: ph, allowedFormats: TEKS_JUDUL } );
			}
			return el( Fragment, null,
				el( InspectorControls, null, Panel( 'Form booking', [
					el( c.TextControl, { key: 'pn', label: 'Contoh isian nama', value: a.placeholderName, onChange: Setel( props, 'placeholderName' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
					el( c.TextControl, { key: 'pu', label: 'Teks pilihan kosong', value: a.placeholderUnit, onChange: Setel( props, 'placeholderUnit' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
					el( c.TextareaControl, { key: 'i', label: 'Kalimat pembuka pesan WhatsApp', value: a.intro, onChange: Setel( props, 'intro' ), __nextHasNoMarginBottom: true } ),
					el( 'p', { key: 'tip', className: 'vb-tip' }, 'Judul, label, dan tombol diketik langsung di kanvas. Pilihan scooter otomatis dari menu Scooter (Sewa); nomor tujuan dari Tampilan → Data Situs.' ),
				] ) ),
				el( 'div', useBlockProps( { className: 'vb-book' } ),
					Teks( 'title', 'h3', 'vb-book__title', 'Judul form' ),
					el( 'div', { className: 'vb-book__form' },
						el( 'p', { className: 'vb-book__f vb-book__f--full' }, Teks( 'labelName', 'label', '', 'Label nama' ), el( 'input', { type: 'text', disabled: true, placeholder: a.placeholderName } ) ),
						el( 'p', { className: 'vb-book__f' }, Teks( 'labelDate', 'label', '', 'Label tanggal' ), el( 'input', { type: 'date', disabled: true } ) ),
						el( 'p', { className: 'vb-book__f' }, Teks( 'labelUnit', 'label', '', 'Label pilihan' ), el( 'select', { disabled: true }, el( 'option', null, a.placeholderUnit ) ) ),
						el( 'p', { className: 'vb-book__f vb-book__f--full' }, el( 'span', { className: 'vb-btn vb-btn--primary vb-btn--md vb-book__btn' }, Teks( 'buttonText', 'span', 'vb-btn__text', 'Teks tombol' ) ) )
					),
					( a.note || props.isSelected ) && Teks( 'note', 'p', 'vb-book__note', 'Catatan kecil di bawah form (opsional)' )
				)
			);
		},
		save: function () {
			return null;
		},
	} );

	/* ------------------------------------------------------------------ */
	/* Modul berita: vb/news-heading, vb/box, vb/posts                     */
	/* ------------------------------------------------------------------ */
	daftarkan( 'vb/news-heading', {
		edit: function ( props ) {
			var a = props.attributes;
			var an = useState( null );
			var blockProps = useBlockProps( { ref: an[ 1 ], className: 'vb-nhead vb-nhead--' + a.headStyle + ' vb-nhead--' + a.size } );
			var ikon = useIkon( props, 'icon' );
			var tautan = useTautan( props, an[ 0 ] );
			return el( Fragment, null,
				Toolbar( ikon.toolbar, tautan.toolbar ),
				el( BlockControls, { group: 'other' }, el( c.ToolbarGroup, null, [ 2, 3, 4 ].map( function ( n ) {
					return el( c.ToolbarButton, { key: n, isPressed: a.level === n, label: 'Judul H' + n, onClick: function () {
						props.setAttributes( { level: n } );
					} }, 'H' + n );
				} ) ) ),
				el( InspectorControls, null, Panel( 'Judul rubrik', [
					Pilih( 'Gaya', a.headStyle, { bar: 'Batang aksen di kiri', line: 'Garis bawah memanjang', block: 'Label berlatar aksen' }, Setel( props, 'headStyle' ) ),
					Pilih( 'Ukuran', a.size, { sm: 'Kecil (judul kotak)', md: 'Sedang', lg: 'Besar' }, Setel( props, 'size' ) ),
					el( 'p', { key: 'tip', className: 'vb-tip' }, 'Ketik judul & teks tautan langsung di kanvas. Tombol bintang di toolbar memilih ikon (atau klik ikonnya), tombol rantai mengatur tujuan "Lihat Lainnya" (bisa cari kategori/halaman). Tanpa tautan, teks "Lihat Lainnya" disembunyikan.' ),
				] ) ),
				el( 'div', blockProps,
					el( 'h' + a.level, { className: 'vb-nhead__title' },
						el( Ikon, { name: a.icon, className: 'vb-ikon vb-nhead__ikon', onClick: ikon.buka } ),
						el( RichText, { tagName: 'span', value: a.title, onChange: Setel( props, 'title' ), placeholder: 'Nama rubrik…', allowedFormats: TEKS_JUDUL } )
					),
					( a.url || props.isSelected ) && el( 'span', { className: 'vb-nhead__more' + ( a.url ? '' : ' is-kosong' ) },
						el( RichText, { tagName: 'span', value: a.linkLabel, onChange: Setel( props, 'linkLabel' ), placeholder: 'Lihat Lainnya', allowedFormats: [] } ),
						el( Ikon, { name: 'arrow-right', className: 'vb-ikon vb-ikon--kecil' } )
					)
				),
				ikon.modal,
				tautan.popover
			);
		},
		save: function () {
			return null;
		},
	} );

	daftarkan( 'vb/box', {
		edit: function ( props ) {
			var a = props.attributes;
			var blockProps = useBlockProps( { className: 'vb-box vb-box--' + a.boxStyle + ' vb-boxpad-' + a.padding + ' vb-gap-' + a.gap + ( a.fill ? ' vb-box--fill' : '' ) } );
			var inner = useInnerBlocksProps( blockProps, {
				template: modul.berita === false ? [ [ 'vb/heading' ] ] : [ [ 'vb/news-heading', { title: 'Terpopuler', size: 'sm', level: 3 } ], [ 'vb/posts', { layout: 'list', count: 4, orderBy: 'popular' } ] ],
				renderAppender: props.isSelected ? InnerBlocks.ButtonBlockAppender : false,
			} );
			return el( Fragment, null,
				el( InspectorControls, null, Panel( 'Kotak', [
					Pilih( 'Gaya kotak', a.boxStyle, { shadow: 'Putih berbayang', border: 'Garis tepi', soft: 'Latar abu lembut', dark: 'Gelap', plain: 'Polos (tanpa latar)' }, Setel( props, 'boxStyle' ) ),
					Pilih( 'Jarak dalam', a.padding, { none: 'Tanpa', sm: 'Rapat', md: 'Sedang', lg: 'Lega' }, Setel( props, 'padding' ) ),
					Pilih( 'Jarak antar blok', a.gap, JARAK, Setel( props, 'gap' ) ),
					el( c.ToggleControl, { key: 'f', label: 'Setinggi kolom di sebelahnya', checked: a.fill, onChange: Setel( props, 'fill' ), __nextHasNoMarginBottom: true } ),
				] ) ),
				el( 'div', inner )
			);
		},
		save: function () {
			return el( InnerBlocks.Content );
		},
	} );

	daftarkan( 'vb/posts', {
		edit: function ( props ) {
			var a = props.attributes;
			var kategori = wp.data.useSelect( function ( s ) {
				return s( 'core' ).getEntityRecords( 'taxonomy', 'category', { per_page: 100, hide_empty: false, _fields: 'id,name' } );
			}, [] ) || [];
			var opsiKat = { 0: 'Semua kategori' };
			kategori.forEach( function ( k ) {
				opsiKat[ k.id ] = k.name;
			} );
			var angka = function ( kunci ) {
				return function ( v ) {
					var ubah = {};
					ubah[ kunci ] = parseInt( v, 10 ) || 0;
					props.setAttributes( ubah );
				};
			};
			var TAMPILAN = { overlay: 'Foto berlapis (judul di atas foto)', list: 'Baris (judul + foto kecil)', excerpt: 'Daftar (foto + ringkasan)', grid: 'Grid kartu' };
			return el( Fragment, null,
				el( BlockControls, { group: 'block' }, el( c.ToolbarGroup, null, Object.keys( TAMPILAN ).map( function ( k ) {
					var ikonTb = { overlay: 'format-image', list: 'list-view', excerpt: 'excerpt-view', grid: 'grid-view' }[ k ];
					return el( c.ToolbarButton, { key: k, icon: ikonTb, label: TAMPILAN[ k ], isPressed: a.layout === k, onClick: function () {
						props.setAttributes( { layout: k } );
					} } );
				} ) ) ),
				el( InspectorControls, null,
					Panel( 'Sumber berita', [
						Pilih( 'Kategori', String( a.category ), opsiKat, angka( 'category' ) ),
						Pilih( 'Urutan', a.orderBy, { date: 'Terbaru', popular: 'Terpopuler (paling dibaca)', comment_count: 'Komentar terbanyak', rand: 'Acak' }, Setel( props, 'orderBy' ) ),
						el( c.RangeControl, { key: 'n', label: 'Jumlah berita', value: a.count, min: 1, max: 24, onChange: Setel( props, 'count' ) } ),
						el( c.RangeControl, { key: 'o', label: 'Lewati berita pertama (offset)', value: a.offset, min: 0, max: 20, onChange: Setel( props, 'offset' ), help: 'Mis. 1 bila berita teratas sudah tampil di blok lain.' } ),
						el( c.ToggleControl, { key: 'x', label: 'Kecualikan berita yang sedang dibuka', checked: a.excludeCurrent, onChange: Setel( props, 'excludeCurrent' ), __nextHasNoMarginBottom: true } ),
					] ),
					Panel( 'Tampilan', [
						Pilih( 'Tampilan', a.layout, TAMPILAN, Setel( props, 'layout' ) ),
						a.layout === 'list' && Pilih( 'Posisi foto', a.thumbPos, { right: 'Kanan', left: 'Kiri', none: 'Tanpa foto' }, Setel( props, 'thumbPos' ) ),
						a.layout === 'overlay' && el( c.RangeControl, { key: 'h', label: 'Tinggi foto (px)', value: a.imageHeight, min: 160, max: 900, step: 10, onChange: Setel( props, 'imageHeight' ) } ),
						a.layout === 'overlay' && el( c.ToggleControl, { key: 'fl', label: 'Isi penuh tinggi kolom', checked: a.fill, onChange: Setel( props, 'fill' ), __nextHasNoMarginBottom: true } ),
						Pilih( 'Ukuran judul', a.titleSize, { sm: 'Kecil', md: 'Sedang', lg: 'Besar', xl: 'Sangat besar' }, Setel( props, 'titleSize' ) ),
						el( c.RangeControl, { key: 'c', label: 'Kolom desktop', value: a.columns, min: 1, max: 6, onChange: Setel( props, 'columns' ) } ),
						el( c.RangeControl, { key: 'ct', label: 'Kolom tablet', value: a.columnsTablet, min: 1, max: 4, onChange: Setel( props, 'columnsTablet' ) } ),
						el( c.RangeControl, { key: 'cm', label: 'Kolom HP', value: a.columnsMobile, min: 1, max: 3, onChange: Setel( props, 'columnsMobile' ) } ),
						Pilih( 'Jarak antar berita', a.gap, JARAK, Setel( props, 'gap' ) ),
						( a.layout === 'overlay' || a.layout === 'grid' ) && el( c.ToggleControl, { key: 'k', label: 'Tampilkan label kategori', checked: a.showCategory, onChange: Setel( props, 'showCategory' ), __nextHasNoMarginBottom: true } ),
						el( c.ToggleControl, { key: 'd', label: 'Tampilkan tanggal', checked: a.showDate, onChange: Setel( props, 'showDate' ), __nextHasNoMarginBottom: true } ),
						( a.layout === 'excerpt' || a.layout === 'grid' ) && el( c.ToggleControl, { key: 'r', label: 'Tampilkan ringkasan', checked: a.showExcerpt, onChange: Setel( props, 'showExcerpt' ), __nextHasNoMarginBottom: true } ),
						( a.layout === 'excerpt' || a.layout === 'grid' ) && a.showExcerpt && el( c.RangeControl, { key: 'rl', label: 'Panjang ringkasan (kata)', value: a.excerptLength, min: 5, max: 60, onChange: Setel( props, 'excerptLength' ) } ),
						el( c.TextControl, { key: 'e', label: 'Teks bila kosong', value: a.emptyText, onChange: Setel( props, 'emptyText' ), __nextHasNoMarginBottom: true, __next40pxDefaultSize: true } ),
					] )
				),
				el( 'div', useBlockProps( { className: 'vb-ssr vb-ssr--posts' + ( a.fill ? ' vb-ssr--fill' : '' ) } ), el( SSR, { block: 'vb/posts', attributes: a } ) )
			);
		},
		save: function () {
			return null;
		},
	} );
}( window.wp, window.vbData ) );
