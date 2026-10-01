<?php

namespace App\Models;

use Database\Factories\SettingFactory;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Storage;
use RuntimeException;

/**
 * Pengaturan aplikasi berbentuk kunci–nilai: nama, deskripsi, logo, dan favicon (Pengaturan > Aplikasi).
 * Gambar unggahan disimpan di disk privat dan disajikan lewat AppImageController; tanpa unggahan dipakai
 * logo & favicon contoh di public/. Nilai di-cache karena dibaca di setiap permintaan Inertia.
 *
 * @property string $key
 * @property string|null $value
 */
class Setting extends Model
{
    /** @use HasFactory<SettingFactory> */
    use HasFactory;

    public const string DISK = 'local';

    public const string DIRECTORY = 'pengaturan';

    /** Gambar yang bisa diunggah; nilai disimpan di kunci "<nama>_path". */
    public const array IMAGES = ['logo', 'favicon'];

    /** Logo & favicon contoh bawaan installer (public/). */
    public const array SAMPLE_IMAGES = [
        'logo' => '/images/logo-contoh.png',
        'favicon' => '/favicon.ico',
    ];

    private const string CACHE_KEY = 'settings.all';

    protected $primaryKey = 'key';

    protected $keyType = 'string';

    public $incrementing = false;

    protected $fillable = ['key', 'value'];

    protected static function booted(): void
    {
        static::saved(fn () => Cache::forget(self::CACHE_KEY));
        static::deleted(fn () => Cache::forget(self::CACHE_KEY));
    }

    /**
     * @return array<string, string|null>
     */
    public static function values(): array
    {
        return Cache::rememberForever(
            self::CACHE_KEY,
            fn () => self::query()->pluck('value', 'key')->all(),
        );
    }

    public static function value(string $key, ?string $default = null): ?string
    {
        return self::values()[$key] ?? $default;
    }

    public static function put(string $key, ?string $value): void
    {
        self::query()->updateOrCreate(['key' => $key], ['value' => $value]);
    }

    public static function appName(): string
    {
        return self::value('app_name') ?: (string) config('app.name');
    }

    public static function appDescription(): ?string
    {
        return self::value('app_description') ?: null;
    }

    public static function imagePath(string $image): ?string
    {
        return self::value("{$image}_path");
    }

    /**
     * Alamat gambar unggahan (berpenanda versi agar cache peramban ikut berganti), atau gambar contoh.
     */
    public static function imageUrl(string $image): string
    {
        $path = self::imagePath($image);

        if ($path === null) {
            return self::SAMPLE_IMAGES[$image];
        }

        return route('app-images.show', ['image' => $image, 'v' => substr(md5($path), 0, 8)], absolute: false);
    }

    /**
     * Ganti gambar; berkas lama dihapus setelah berkas baru tersimpan.
     */
    public static function replaceImage(string $image, UploadedFile $file): void
    {
        $path = $file->store(self::DIRECTORY, self::DISK);

        if ($path === false) {
            throw new RuntimeException('Gagal menyimpan gambar.');
        }

        $oldPath = self::imagePath($image);
        self::put("{$image}_path", $path);

        if ($oldPath !== null) {
            Storage::disk(self::DISK)->delete($oldPath);
        }
    }

    /**
     * Hapus gambar unggahan; tampilan kembali memakai gambar contoh.
     */
    public static function removeImage(string $image): void
    {
        $oldPath = self::imagePath($image);

        if ($oldPath === null) {
            return;
        }

        self::put("{$image}_path", null);
        Storage::disk(self::DISK)->delete($oldPath);
    }

    /**
     * Identitas aplikasi yang dibagikan ke semua halaman Inertia (`site`).
     *
     * @return array{name: string, description: string|null, logo_url: string, favicon_url: string, can_manage: bool}
     */
    public static function shared(?User $user): array
    {
        return [
            'name' => self::appName(),
            'description' => self::appDescription(),
            'logo_url' => self::imageUrl('logo'),
            'favicon_url' => self::imageUrl('favicon'),
            'can_manage' => $user?->can('manage-app-settings') ?? false,
        ];
    }
}
