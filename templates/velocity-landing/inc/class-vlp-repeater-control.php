<?php
/**
 * Kontrol Customizer untuk daftar item yang bisa ditambah, dihapus, dan diurutkan.
 * Nilai disimpan sebagai JSON di satu setting; tampilan item dibangun oleh
 * assets/js/customize-repeater.js dari parameter `vlpFields`.
 *
 * @package velocity-landing
 */

defined('ABSPATH') || exit;

class VLP_Repeater_Control extends WP_Customize_Control
{
	public $type = 'vlp_repeater';

	/** @var array Field per item dari skema: [kunci => [type, label]]. */
	public $vlp_fields = array();

	/** @var string Sebutan satu item, mis. "Layanan". */
	public $vlp_item_label = 'Item';

	public function to_json()
	{
		parent::to_json();
		$this->json['vlpFields'] = $this->vlp_fields;
		$this->json['vlpItemLabel'] = $this->vlp_item_label;
	}

	/**
	 * Wadah kosong; isinya dibangun JS supaya item baru bisa ditambah tanpa memuat ulang.
	 */
	public function render_content()
	{
		?>
		<span class="customize-control-title"><?php echo esc_html($this->label); ?></span>
		<?php if ($this->description) : ?>
			<span class="description customize-control-description"><?php echo esc_html($this->description); ?></span>
		<?php endif; ?>
		<div class="vlp-repeater">
			<ul class="vlp-repeater-daftar"></ul>
			<button type="button" class="button vlp-repeater-tambah">
				<span class="dashicons dashicons-plus-alt2" aria-hidden="true"></span>
				<?php echo esc_html('Tambah ' . $this->vlp_item_label); ?>
			</button>
		</div>
		<?php
	}
}
