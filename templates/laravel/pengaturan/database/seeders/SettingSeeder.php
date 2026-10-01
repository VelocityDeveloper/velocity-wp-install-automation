<?php

namespace Database\Seeders;

use App\Models\Setting;
use Illuminate\Database\Seeder;

/**
 * Data wajib: nama & deskripsi aplikasi bawaan. Nilai yang sudah diubah lewat Pengaturan tidak ditimpa.
 */
class SettingSeeder extends Seeder
{
    public function run(): void
    {
        Setting::query()->firstOrCreate(['key' => 'app_name'], ['value' => config('app.name')]);
        Setting::query()->firstOrCreate(['key' => 'app_description'], ['value' => null]);
    }
}
