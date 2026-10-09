<?php

/*
 * Cek seeder untuk runner laravel-agen (dijalankan dengan cwd = folder aplikasi):
 * migrate:fresh --seed di database SQLite SEMENTARA, lalu setiap model Eloquent di app/Models
 * harus punya baris. Seeding diulang sekali lagi untuk memastikan seeder aman dijalankan ulang.
 *
 * Wajib diberi env DB_CONNECTION=sqlite + DB_DATABASE=<berkas sementara>; bila konfigurasi yang
 * termuat bukan berkas itu (mis. config ter-cache), skrip berhenti SEBELUM migrate:fresh supaya
 * database dev MariaDB tidak pernah terhapus.
 *
 * Keluaran: satu baris JSON {"ok":bool,"kosong":[...],"galat":str,"jumlah":{Model:n}}.
 */

use Illuminate\Contracts\Console\Kernel;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Support\Facades\Artisan;

$dir = getcwd();
require $dir.'/vendor/autoload.php';
$app = require $dir.'/bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();

function selesai(array $hasil): never
{
    echo json_encode($hasil + ['ok' => false, 'kosong' => [], 'galat' => '', 'jumlah' => []], JSON_UNESCAPED_UNICODE).PHP_EOL;
    exit($hasil['ok'] ?? false ? 0 : 1);
}

$target = getenv('DB_DATABASE');
if (config('database.default') !== 'sqlite' || ! $target || config('database.connections.sqlite.database') !== $target) {
    selesai(['galat' => 'Pengaman: koneksi yang termuat bukan SQLite sementara ('.config('database.default')
        .'); cek seeder dibatalkan. Jalankan php artisan config:clear bila config ter-cache.']);
}

try {
    Artisan::call('migrate:fresh', ['--seed' => true, '--force' => true]);
} catch (Throwable $e) {
    selesai(['galat' => 'migrate:fresh --seed gagal: '.$e->getMessage().' ('.basename($e->getFile()).':'.$e->getLine().')']);
}

$jumlah = [];
$kosong = [];
$akar = $dir.'/app/Models';
$berkas = is_dir($akar) ? new RecursiveIteratorIterator(new RecursiveDirectoryIterator($akar, FilesystemIterator::SKIP_DOTS)) : [];
foreach ($berkas as $f) {
    if ($f->getExtension() !== 'php') {
        continue;
    }
    $kelas = 'App\\Models\\'.str_replace('/', '\\', substr($f->getPathname(), strlen($akar) + 1, -4));
    if (! class_exists($kelas)) {
        continue;
    }
    $r = new ReflectionClass($kelas);
    if ($r->isAbstract() || ! $r->isSubclassOf(Model::class)) {
        continue;
    }
    $n = $kelas::query()->withoutGlobalScopes()->count();
    $jumlah[$r->getShortName()] = $n;
    if ($n === 0) {
        $kosong[] = $r->getShortName();
    }
}

try {
    Artisan::call('db:seed', ['--force' => true]);
} catch (Throwable $e) {
    selesai(['jumlah' => $jumlah, 'kosong' => $kosong,
        'galat' => 'Seeder tidak aman dijalankan ulang (db:seed kedua gagal): '.$e->getMessage()]);
}

selesai([
    'ok' => ! $kosong,
    'jumlah' => $jumlah,
    'kosong' => $kosong,
    'galat' => $kosong ? 'Model tanpa data seeder: '.implode(', ', $kosong) : '',
]);
