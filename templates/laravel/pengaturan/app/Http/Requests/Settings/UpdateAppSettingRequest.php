<?php

namespace App\Http\Requests\Settings;

use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;

/**
 * Pengaturan aplikasi: nama, deskripsi, logo (JPG/PNG/WebP maks. 1 MB), dan favicon (PNG/ICO maks. 512 KB).
 * Kolom `remove_*` menghapus gambar unggahan sehingga tampilan kembali ke gambar contoh.
 */
class UpdateAppSettingRequest extends FormRequest
{
    /** @var array<string, int> */
    public const array MAX_KILOBYTES = [
        'logo' => 1024,
        'favicon' => 512,
    ];

    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return $this->user()->can('manage-app-settings');
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, ValidationRule|array<mixed>|string>
     */
    public function rules(): array
    {
        return [
            'app_name' => ['required', 'string', 'max:100'],
            'app_description' => ['nullable', 'string', 'max:300'],
            'logo' => ['nullable', 'file', 'extensions:jpg,jpeg,png,webp', 'mimes:jpg,jpeg,png,webp', 'max:'.self::MAX_KILOBYTES['logo']],
            'favicon' => ['nullable', 'file', 'extensions:png,ico', 'mimes:png,ico', 'max:'.self::MAX_KILOBYTES['favicon']],
            'remove_logo' => ['boolean'],
            'remove_favicon' => ['boolean'],
        ];
    }

    /**
     * @return array<string, string>
     */
    public function messages(): array
    {
        return [
            'app_name.required' => 'Nama aplikasi wajib diisi.',
            'app_name.max' => 'Nama aplikasi maksimal 100 karakter.',
            'app_description.max' => 'Deskripsi aplikasi maksimal 300 karakter.',
            'logo.file' => 'Logo gagal diunggah.',
            'logo.extensions' => 'Logo harus berformat JPG, PNG, atau WebP.',
            'logo.mimes' => 'Logo harus berformat JPG, PNG, atau WebP.',
            'logo.max' => 'Ukuran logo maksimal 1 MB.',
            'logo.uploaded' => 'Logo gagal diunggah. Pastikan ukurannya tidak lebih dari 1 MB.',
            'favicon.file' => 'Favicon gagal diunggah.',
            'favicon.extensions' => 'Favicon harus berformat PNG atau ICO.',
            'favicon.mimes' => 'Favicon harus berformat PNG atau ICO.',
            'favicon.max' => 'Ukuran favicon maksimal 512 KB.',
            'favicon.uploaded' => 'Favicon gagal diunggah. Pastikan ukurannya tidak lebih dari 512 KB.',
        ];
    }
}
