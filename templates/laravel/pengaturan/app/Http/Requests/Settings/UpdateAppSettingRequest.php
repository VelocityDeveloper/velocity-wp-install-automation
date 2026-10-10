<?php

namespace App\Http\Requests\Settings;

use Illuminate\Contracts\Validation\ValidationRule;
use Illuminate\Foundation\Http\FormRequest;

/**
 * Pengaturan aplikasi: nama, deskripsi, logo (JPG/PNG/WebP maks. 1 MB), dan favicon (PNG/ICO maks. 512 KB).
 * Kolom `remove_*` menghapus gambar unggahan sehingga tampilan kembali ke gambar contoh.
 * Kode verifikasi Google Search Console boleh ditempel sebagai tag meta utuh; yang disimpan hanya isi `content`.
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

    protected function prepareForValidation(): void
    {
        if (! $this->has('google_site_verification')) {
            return;
        }

        $code = trim((string) $this->input('google_site_verification'));

        if (preg_match('/content\s*=\s*["\']([^"\']*)["\']/i', $code, $match) === 1) {
            $code = trim($match[1]);
        }

        $this->merge(['google_site_verification' => $code === '' ? null : $code]);
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
            'search_engine_indexing' => ['boolean'],
            'google_site_verification' => ['nullable', 'string', 'max:100', 'regex:/^[A-Za-z0-9_-]+$/'],
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
            'google_site_verification.max' => 'Kode verifikasi Google maksimal 100 karakter.',
            'google_site_verification.regex' => 'Kode verifikasi Google tidak valid. Tempel tag meta dari Search Console atau isi content-nya saja.',
        ];
    }
}
