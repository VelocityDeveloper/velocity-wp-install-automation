<?php

use App\Models\Setting;
use App\Models\User;
use Database\Seeders\SettingSeeder;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;
use Inertia\Testing\AssertableInertia as Assert;

beforeEach(function () {
    Storage::fake(Setting::DISK);
    // Akun pertama = pengelola pengaturan sebelum aplikasi punya peran (AppSettingServiceProvider).
    $this->admin = User::factory()->create();
});

test('guests see the sample logo, favicon, and Velocity Developer footer data', function () {
    $this->get(route('home'))
        ->assertOk()
        ->assertSee('<link rel="icon" href="/favicon.ico"', false)
        ->assertInertia(fn (Assert $page) => $page
            ->component('Welcome')
            ->where('site.name', config('app.name'))
            ->where('site.logo_url', Setting::SAMPLE_IMAGES['logo'])
            ->where('site.favicon_url', Setting::SAMPLE_IMAGES['favicon'])
            ->where('site.can_manage', false));

    expect(public_path('images/logo-contoh.png'))->toBeFile()
        ->and(public_path('favicon.ico'))->toBeFile();
});

test('admin saves app name, description, logo, and favicon', function () {
    $this->actingAs($this->admin)
        ->get(route('app-settings.edit'))
        ->assertOk()
        ->assertInertia(fn (Assert $page) => $page
            ->component('settings/App')
            ->where('uploaded.logo', false)
            ->where('site.can_manage', true));

    $this->post(route('app-settings.update'), [
        'app_name' => '  Aplikasi Contoh ',
        'app_description' => 'Sistem informasi contoh.',
        'logo' => UploadedFile::fake()->image('logo.png', 300, 300),
        'favicon' => UploadedFile::fake()->create('favicon.ico', 10, 'image/vnd.microsoft.icon'),
    ])->assertSessionHasNoErrors()->assertRedirect();

    expect(Setting::appName())->toBe('Aplikasi Contoh')
        ->and(Setting::appDescription())->toBe('Sistem informasi contoh.');

    foreach (Setting::IMAGES as $image) {
        Storage::disk(Setting::DISK)->assertExists(Setting::imagePath($image));
    }

    $this->get(route('home'))
        ->assertSee('<title>Aplikasi Contoh</title>', false)
        ->assertSee('<meta name="description" content="Sistem informasi contoh.">', false)
        ->assertSee(Setting::imageUrl('favicon'), false)
        ->assertInertia(fn (Assert $page) => $page
            ->where('site.name', 'Aplikasi Contoh')
            ->where('site.description', 'Sistem informasi contoh.')
            ->where('site.logo_url', Setting::imageUrl('logo')));
});

test('uploaded images are served to guests and removing one returns to the sample', function () {
    $this->actingAs($this->admin)->post(route('app-settings.update'), [
        'app_name' => 'Aplikasi Contoh',
        'logo' => UploadedFile::fake()->image('logo.webp'),
    ])->assertSessionHasNoErrors();
    $path = Setting::imagePath('logo');

    auth()->logout();
    $this->get(Setting::imageUrl('logo'))->assertOk()->assertHeader('X-Content-Type-Options', 'nosniff');
    $this->get('/gambar-aplikasi/lain')->assertNotFound();

    $this->actingAs($this->admin)->post(route('app-settings.update'), [
        'app_name' => 'Aplikasi Contoh',
        'remove_logo' => true,
    ])->assertSessionHasNoErrors();

    Storage::disk(Setting::DISK)->assertMissing($path);
    expect(Setting::imageUrl('logo'))->toBe(Setting::SAMPLE_IMAGES['logo']);
});

test('invalid app settings are rejected with Indonesian messages', function (array $data, string $field, string $message) {
    $this->actingAs($this->admin)
        ->post(route('app-settings.update'), ['app_name' => 'Aplikasi Contoh', ...$data])
        ->assertSessionHasErrors([$field => $message]);
})->with([
    'nama kosong' => [['app_name' => ''], 'app_name', 'Nama aplikasi wajib diisi.'],
    'logo pdf' => [['logo' => UploadedFile::fake()->create('logo.pdf', 10, 'application/pdf')], 'logo', 'Logo harus berformat JPG, PNG, atau WebP.'],
    'favicon jpg' => [['favicon' => UploadedFile::fake()->image('ikon.jpg')], 'favicon', 'Favicon harus berformat PNG atau ICO.'],
    'logo > 1 MB' => [['logo' => UploadedFile::fake()->image('logo.png')->size(2000)], 'logo', 'Ukuran logo maksimal 1 MB.'],
]);

test('other users cannot open or change app settings', function () {
    $user = User::factory()->create();

    $this->actingAs($user)->get(route('app-settings.edit'))->assertForbidden();
    $this->post(route('app-settings.update'), ['app_name' => 'Retas'])->assertForbidden();

    expect(Setting::appName())->toBe(config('app.name'));
});

test('setting seeder keeps a name changed in settings', function () {
    $this->seed(SettingSeeder::class);
    Setting::put('app_name', 'Nama Baru');

    $this->seed(SettingSeeder::class);

    expect(Setting::appName())->toBe('Nama Baru');
});
