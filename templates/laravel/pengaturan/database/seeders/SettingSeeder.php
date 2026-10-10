<?php

namespace Database\Seeders;

use App\Models\Setting;
use Illuminate\Database\Seeder;

/**
 * Data wajib: nama & deskripsi aplikasi bawaan, mesin pencari boleh mengindeks, kode Search Console kosong.
 * Nilai yang sudah diubah lewat Pengaturan tidak ditimpa.
 */
class SettingSeeder extends Seeder
{
    public function run(): void
    {
        Setting::query()->firstOrCreate(['key' => 'app_name'], ['value' => config('app.name')]);
        Setting::query()->firstOrCreate(['key' => 'app_description'], ['value' => null]);
        Setting::query()->firstOrCreate(['key' => 'search_engine_indexing'], ['value' => '1']);
        Setting::query()->firstOrCreate(['key' => 'google_site_verification'], ['value' => null]);
    }
}
