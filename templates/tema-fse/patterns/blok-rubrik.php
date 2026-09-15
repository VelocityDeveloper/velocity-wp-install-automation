<?php
/**
 * Title: Blok Rubrik (1 besar + 3 daftar)
 * Slug: velocity-fse/blok-rubrik
 * Categories: velocity
 * Keywords: berita, rubrik, kategori, query
 * Description: Pilih kategorinya lewat pengaturan kedua Query Loop di sidebar kanan editor.
 */
?>
<!-- wp:group {"className":"vf-seksi","layout":{"type":"default"}} -->
<div class="wp-block-group vf-seksi"><!-- wp:group {"className":"vf-rubrik-bar","layout":{"type":"flex","flexWrap":"nowrap","justifyContent":"space-between"}} -->
<div class="wp-block-group vf-rubrik-bar"><!-- wp:heading -->
<h2 class="wp-block-heading">Nama Rubrik</h2>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p><a href="/berita/">Lihat semua →</a></p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->

<!-- wp:columns {"className":"vf-utama-baris"} -->
<div class="wp-block-columns vf-utama-baris"><!-- wp:column {"width":"53%"} -->
<div class="wp-block-column" style="flex-basis:53%"><!-- wp:query {"queryId":31,"query":{"perPage":1,"pages":0,"offset":0,"postType":"post","order":"desc","orderBy":"date","author":"","search":"","exclude":[],"sticky":"","inherit":false}} -->
<div class="wp-block-query"><!-- wp:post-template {"className":"vf-kartu"} -->
<!-- wp:post-featured-image {"isLink":true,"aspectRatio":"16/10"} /-->

<!-- wp:post-title {"level":3,"isLink":true} /-->

<!-- wp:post-date /-->
<!-- /wp:post-template --></div>
<!-- /wp:query --></div>
<!-- /wp:column -->

<!-- wp:column -->
<div class="wp-block-column"><!-- wp:query {"queryId":32,"query":{"perPage":3,"pages":0,"offset":1,"postType":"post","order":"desc","orderBy":"date","author":"","search":"","exclude":[],"sticky":"","inherit":false}} -->
<div class="wp-block-query"><!-- wp:post-template {"className":"vf-daftar"} -->
<!-- wp:post-featured-image {"isLink":true,"aspectRatio":"4/3"} /-->

<!-- wp:group {"className":"vf-daftar__teks","layout":{"type":"default"}} -->
<div class="wp-block-group vf-daftar__teks"><!-- wp:post-title {"level":3,"isLink":true} /-->

<!-- wp:post-date /--></div>
<!-- /wp:group -->
<!-- /wp:post-template --></div>
<!-- /wp:query --></div>
<!-- /wp:column --></div>
<!-- /wp:columns --></div>
<!-- /wp:group -->
