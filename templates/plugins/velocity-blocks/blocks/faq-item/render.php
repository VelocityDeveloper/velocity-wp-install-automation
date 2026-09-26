<?php
/** vb/faq-item — satu tanya-jawab (<details>). */
$a = $attributes;
printf(
	'<details class="vb-faq__item wp-block-vb-faq-item"><summary class="vb-faq__q"><span>%1$s</span><span class="vb-faq__ikon" aria-hidden="true"></span></summary><div class="vb-faq__a">%2$s</div></details>',
	wp_kses_post( $a['question'] ?? '' ),
	wpautop( wp_kses_post( $a['answer'] ?? '' ) )
);
