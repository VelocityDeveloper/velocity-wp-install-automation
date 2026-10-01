<?php

namespace App\Http\Controllers;

use App\Models\Setting;
use Illuminate\Support\Facades\Storage;
use Symfony\Component\HttpFoundation\StreamedResponse;

/**
 * Logo & favicon unggahan dari disk privat. Terbuka untuk tamu karena tampil di halaman depan,
 * halaman masuk, dan tab peramban.
 */
class AppImageController extends Controller
{
    public function show(string $image): StreamedResponse
    {
        $path = Setting::imagePath($image);
        $disk = Storage::disk(Setting::DISK);

        abort_if($path === null || ! $disk->exists($path), 404);

        return $disk->response($path, null, [
            'X-Content-Type-Options' => 'nosniff',
            'Content-Security-Policy' => "default-src 'none'; sandbox",
            'Cache-Control' => 'public, max-age=604800',
        ], 'inline');
    }
}
