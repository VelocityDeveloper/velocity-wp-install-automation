<?php

namespace App\Providers;

use App\Models\User;
use BackedEnum;
use Illuminate\Support\Facades\Gate;
use Illuminate\Support\ServiceProvider;

/**
 * Hak mengelola Pengaturan > Aplikasi (nama, deskripsi, logo, favicon).
 */
class AppSettingServiceProvider extends ServiceProvider
{
    public function boot(): void
    {
        // Bila tabel users punya kolom `role`, hanya peran admin. Sebelum ada peran: akun pertama (admin seeder).
        Gate::define('manage-app-settings', function (User $user): bool {
            $role = $user->getAttribute('role');

            if ($role !== null) {
                return ($role instanceof BackedEnum ? $role->value : $role) === 'admin';
            }

            return $user->getKey() === User::query()->min('id');
        });
    }
}
