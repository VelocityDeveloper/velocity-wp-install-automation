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
	[
		'velocity/topbar',
		'velocity/populer',
		'velocity/kontak',
		'velocity/form-kirim',
		'velocity/hak-cipta',
		'velocity/judul-arsip',
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
