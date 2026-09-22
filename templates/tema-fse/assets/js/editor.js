/**
 * Pratinjau blok dinamis tema di editor. Isinya dirender PHP (render.php tiap
 * blok); tanpa pendaftaran di sisi JS editor menampilkan "blok tidak didukung".
 */
( function ( wp ) {
	if ( ! wp || ! wp.blocks || ! wp.serverSideRender || ! wp.blockEditor ) {
		return;
	}
	var el = wp.element.createElement;
	var useBlockProps = wp.blockEditor.useBlockProps;
	var ServerSideRender = wp.serverSideRender;
	// Deret geser: berisi blok Gambar biasa (InnerBlocks) supaya isinya gampang
	// diganti lewat editor, bukan ServerSideRender yang hanya bisa dilihat.
	if ( wp.blocks.getBlockType( 'velocity/geser' ) === undefined && wp.blockEditor.InnerBlocks ) {
		wp.blocks.registerBlockType( 'velocity/geser', {
			edit: function ( props ) {
				var foto = props.attributes && props.attributes.tampilan === 'foto';
				var blokProps = useBlockProps( {
					className: 'vf-klien vf-logo-geser ' + ( foto ? 'vf-geser-foto' : 'vf-klien--logo' ),
				} );
				return el(
					'div',
					blokProps,
					el( wp.blockEditor.InnerBlocks, {
						allowedBlocks: [ 'core/image' ],
						template: [ [ 'core/image' ] ],
						templateLock: false,
						orientation: 'horizontal',
					} )
				);
			},
			save: function () {
				return el( wp.blockEditor.InnerBlocks.Content );
			},
		} );
	}

	// Kartu Ikon: ikon + judul + isi + tautan, semuanya disunting DI TEMPAT (toolbar &
	// teks langsung), tidak lewat halaman pengaturan (permintaan user 2026-09-19).
	if ( wp.blocks.getBlockType( 'velocity/kartu-ikon' ) === undefined && wp.components ) {
		var C = wp.components;
		var BE = wp.blockEditor;
		var daftarIkon = window.vfIkon || [];
		var dataSitus = window.vfSitus || {};
		var svgIkon = function ( slug, ukuran ) {
			var d = daftarIkon.find( function ( x ) { return x.slug === slug; } ) || daftarIkon[ 0 ] || { path: '' };
			return el( 'svg', { viewBox: '0 0 24 24', width: ukuran || 24, height: ukuran || 24, 'aria-hidden': true },
				el( 'path', { d: d.path, fill: 'currentColor' } ) );
		};
		var labelSumber = { alamat: 'Alamat', wa: 'WhatsApp', telp: 'Telepon', email: 'Email' };
		wp.blocks.registerBlockType( 'velocity/kartu-ikon', {
			edit: function ( props ) {
				var a = props.attributes;
				var ubah = props.setAttributes;
				var baris = a.tampilan === 'baris';
				var blokProps = useBlockProps( {
					className: ( baris ? 'vf-kartu-ikon vf-kartu-ikon--baris' : 'vf-kartu-ikon vf-kontak-kartu__item' ) +
						' vf-kontak-kartu__item--' + a.ikon,
				} );
				var placeholderIsi = a.sumber && dataSitus[ a.sumber ] ? dataSitus[ a.sumber ] : 'Tulis isi…';
				var judul = el( BE.RichText, {
					tagName: 'span', className: 'vf-kontak-kartu__judul', value: a.judul,
					placeholder: 'Judul…', allowedFormats: [ 'core/bold', 'core/italic' ],
					onChange: function ( v ) { ubah( { judul: v } ); },
				} );
				var isi = el( BE.RichText, {
					tagName: 'span', className: 'vf-kontak-kartu__isi', value: a.isi,
					placeholder: placeholderIsi, allowedFormats: [ 'core/bold', 'core/italic', 'core/link' ],
					onChange: function ( v ) { ubah( { isi: v } ); },
				} );
				var ikon = el( 'span', { className: 'vf-kontak-kartu__ikon' }, svgIkon( a.ikon, 22 ) );
				return el( wp.element.Fragment, null,
					el( BE.BlockControls, { group: 'block' },
						el( C.ToolbarGroup, null,
							el( C.Dropdown, {
								popoverProps: { placement: 'bottom-start' },
								renderToggle: function ( t ) {
									return el( C.ToolbarButton, {
										icon: svgIkon( a.ikon, 20 ), label: 'Ganti ikon',
										onClick: t.onToggle, 'aria-expanded': t.isOpen,
									} );
								},
								renderContent: function ( t ) {
									return el( 'div', { style: { display: 'grid', gridTemplateColumns: 'repeat(5, 40px)', gap: '6px', padding: '10px' } },
										daftarIkon.map( function ( x ) {
											return el( C.Button, {
												key: x.slug, label: x.label, showTooltip: true,
												isPressed: a.ikon === x.slug,
												icon: svgIkon( x.slug, 22 ),
												onClick: function () { ubah( { ikon: x.slug } ); t.onClose(); },
											} );
										} ) );
								},
							} ),
							el( C.Dropdown, {
								popoverProps: { placement: 'bottom-start' },
								renderToggle: function ( t ) {
									return el( C.ToolbarButton, {
										icon: 'admin-links', label: a.tautan ? 'Ubah tautan' : 'Pasang tautan',
										isPressed: !! a.tautan, onClick: t.onToggle, 'aria-expanded': t.isOpen,
									} );
								},
								renderContent: function () {
									return el( 'div', { style: { padding: '12px', width: '300px' } },
										el( C.TextControl, {
											label: 'Tautan (URL, tel:…, mailto:…)', value: a.tautan,
											placeholder: 'https://', onChange: function ( v ) { ubah( { tautan: v } ); },
										} ),
										el( C.ToggleControl, {
											label: 'Buka di tab baru', checked: !! a.tabBaru,
											onChange: function ( v ) { ubah( { tabBaru: v } ); },
										} ),
										a.tautan ? el( C.Button, { variant: 'secondary', isDestructive: true,
											onClick: function () { ubah( { tautan: '' } ); } }, 'Hapus tautan' ) : null );
								},
							} ) ) ),
					el( BE.InspectorControls, null,
						el( C.PanelBody, { title: 'Kartu Ikon', initialOpen: true },
							el( C.SelectControl, {
								label: 'Tampilan', value: a.tampilan,
								options: [ { label: 'Kartu (ikon di atas)', value: 'kartu' }, { label: 'Baris (ikon di kiri)', value: 'baris' } ],
								onChange: function ( v ) { ubah( { tampilan: v } ); },
							} ),
							el( C.SelectControl, {
								label: 'Ambil dari Data Situs bila isi kosong',
								help: 'Isi yang diketik selalu menang. Kosongkan isi untuk memakai data situs.',
								value: a.sumber,
								options: [ { label: '— tidak —', value: '' } ].concat( Object.keys( labelSumber ).map( function ( k ) {
									return { label: labelSumber[ k ], value: k };
								} ) ),
								onChange: function ( v ) { ubah( { sumber: v } ); },
							} ) ) ),
					el( 'div', blokProps, ikon,
						baris ? el( 'span', { className: 'vf-kartu-ikon__teks' }, judul, isi ) : judul,
						baris ? null : isi ) );
			},
			save: function () {
				return null;
			},
		} );
	}

	// Hak cipta: diketik langsung; {tahun} & {situs} diganti otomatis saat tampil.
	if ( wp.blocks.getBlockType( 'velocity/hak-cipta' ) === undefined ) {
		wp.blocks.registerBlockType( 'velocity/hak-cipta', {
			edit: function ( props ) {
				return el( wp.blockEditor.RichText, Object.assign( useBlockProps(), {
					tagName: 'p', value: props.attributes.teks,
					placeholder: '© {tahun} {situs}.',
					onChange: function ( v ) { props.setAttributes( { teks: v } ); },
				} ) );
			},
			save: function () {
				return null;
			},
		} );
	}

	[
		'velocity/topbar',
		'velocity/populer',
		'velocity/kontak',
		'velocity/form-kirim',
		'velocity/judul-arsip',
		'velocity/mobil-kartu',
		'velocity/mobil-warna',
		'velocity/mobil-spesifikasi',
		'velocity/simulasi-kredit',
	].forEach( function ( nama ) {
		if ( wp.blocks.getBlockType( nama ) ) {
			return;
		}
		wp.blocks.registerBlockType( nama, {
			edit: function () {
				return el( 'div', useBlockProps(), el( ServerSideRender, { block: nama } ) );
			},
			save: function () {
				return null;
			},
		} );
	} );
} )( window.wp );
