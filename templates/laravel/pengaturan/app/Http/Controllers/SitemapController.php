<?php

namespace App\Http\Controllers;

use App\Models\Setting;
use Illuminate\Routing\RedirectController;
use Illuminate\Routing\Route;
use Illuminate\Support\Facades\Route as Router;
use Illuminate\Support\Str;
use Symfony\Component\HttpFoundation\Response;

/**
 * /sitemap.xml dan /robots.txt untuk Google Search Console (installer Velocity).
 * Alamat dibentuk dari domain permintaan, jadi otomatis memakai domain produksi sesudah deploy.
 * Sakelar Pengaturan > Aplikasi "Izinkan mesin pencari" mati (aplikasi internal) -> robots Disallow semua, sitemap 404.
 */
class SitemapController extends Controller
{
    /** Middleware yang menandai halaman bukan untuk umum. */
    private const array PRIVATE_MIDDLEWARE = ['auth', 'guest', 'verified', 'password.confirm', 'signed'];

    /** Segmen pertama URI yang tidak dimasukkan ke sitemap walau terbuka untuk tamu (selain awalan `_` dan `.`). */
    private const array EXCLUDED_SEGMENTS = [
        'settings', 'gambar-aplikasi', 'sitemap.xml', 'robots.txt', 'up', 'storage', 'api', 'sanctum',
    ];

    public function sitemap(): Response
    {
        abort_unless(Setting::searchIndexingEnabled(), 404);

        $xml = '<?xml version="1.0" encoding="UTF-8"?>'."\n"
            .'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'."\n";

        foreach ($this->urls() as $url) {
            $xml .= '  <url><loc>'.htmlspecialchars($url['loc'], ENT_XML1).'</loc>'
                .(isset($url['lastmod']) ? '<lastmod>'.$url['lastmod'].'</lastmod>' : '')
                .'</url>'."\n";
        }

        return response($xml.'</urlset>'."\n", 200, ['Content-Type' => 'application/xml; charset=UTF-8']);
    }

    public function robots(): Response
    {
        $body = Setting::searchIndexingEnabled()
            ? "User-agent: *\nDisallow:\n\nSitemap: ".route('sitemap')."\n"
            : "User-agent: *\nDisallow: /\n";

        return response($body, 200, ['Content-Type' => 'text/plain; charset=UTF-8']);
    }

    /**
     * @return list<array{loc: string, lastmod?: string}>
     */
    private function urls(): array
    {
        $urls = [];

        foreach (Router::getRoutes()->getRoutes() as $route) {
            if ($this->isPublicPage($route)) {
                $urls[] = ['loc' => url($route->uri())];
            }
        }

        return array_values(array_unique([...$urls, ...$this->contentUrls()], SORT_REGULAR));
    }

    /**
     * Halaman konten publik dari database (artikel, produk, halaman, dll.). Saat aplikasi punya konten publik
     * ber-slug, tambahkan di sini, mis.:
     *   Article::query()->published()->get()->map(fn ($a) => ['loc' => route('articles.show', $a), 'lastmod' => $a->updated_at->toAtomString()])
     *
     * @return list<array{loc: string, lastmod?: string}>
     */
    private function contentUrls(): array
    {
        return [];
    }

    private function isPublicPage(Route $route): bool
    {
        if (! in_array('GET', $route->methods(), true) || $route->parameterNames() !== []) {
            return false;
        }

        $segment = Str::before($route->uri(), '/');

        // `_inertia`, `_boost`, `.well-known`, dll. = rute internal paket
        if ($route->getControllerClass() === RedirectController::class
            || Str::startsWith($segment, ['_', '.'])
            || in_array($segment, self::EXCLUDED_SEGMENTS, true)) {
            return false;
        }

        foreach ($route->gatherMiddleware() as $middleware) {
            if (is_string($middleware) && in_array(Str::before($middleware, ':'), self::PRIVATE_MIDDLEWARE, true)) {
                return false;
            }
        }

        return true;
    }
}
