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
 * Pengaturan > Aplikasi: nama, deskripsi, logo, dan favicon. Nilai saat ini ada di prop bersama `site`.
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
        ]);
    }

    public function update(UpdateAppSettingRequest $request): RedirectResponse
    {
        Setting::put('app_name', $request->string('app_name')->trim()->value());
        Setting::put('app_description', $request->filled('app_description') ? $request->string('app_description')->trim()->value() : null);

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
