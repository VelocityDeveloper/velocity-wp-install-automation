<?php

namespace App\Http\Controllers\Settings;

use App\Http\Controllers\Controller;
use App\Http\Requests\Settings\UpdateAppSettingRequest;
use App\Models\Setting;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\Gate;
use Inertia\Inertia;
use Inertia\Response;

/**
 * Pengaturan > Aplikasi: nama, deskripsi, logo, favicon (prop bersama `site`) dan mesin pencari (prop `seo`).
 */
class AppSettingController extends Controller
{
    public function edit(): Response
    {
        Gate::authorize('manage-app-settings');

        return Inertia::render('settings/App', [
            'maxKilobytes' => UpdateAppSettingRequest::MAX_KILOBYTES,
            'uploaded' => [
                'logo' => Setting::imagePath('logo') !== null,
                'favicon' => Setting::imagePath('favicon') !== null,
            ],
            'seo' => [
                'search_engine_indexing' => Setting::searchIndexingEnabled(),
                'google_site_verification' => Setting::googleSiteVerification(),
                'sitemap_url' => route('sitemap'),
            ],
        ]);
    }

    public function update(UpdateAppSettingRequest $request): RedirectResponse
    {
        Setting::put('app_name', $request->string('app_name')->trim()->value());
        Setting::put('app_description', $request->filled('app_description') ? $request->string('app_description')->trim()->value() : null);

        if ($request->has('search_engine_indexing')) {
            Setting::put('search_engine_indexing', $request->boolean('search_engine_indexing') ? '1' : '0');
        }

        if ($request->has('google_site_verification')) {
            Setting::put('google_site_verification', $request->input('google_site_verification'));
        }

        foreach (Setting::IMAGES as $image) {
            if ($request->hasFile($image)) {
                Setting::replaceImage($image, $request->file($image));
            } elseif ($request->boolean("remove_{$image}")) {
                Setting::removeImage($image);
            }
        }

        Inertia::flash('toast', ['type' => 'success', 'message' => 'Pengaturan aplikasi disimpan.']);

        return back();
    }
}
