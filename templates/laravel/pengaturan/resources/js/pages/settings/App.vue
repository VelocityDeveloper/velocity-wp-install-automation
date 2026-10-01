<script setup lang="ts">
import { Head, useForm, usePage } from '@inertiajs/vue3';
import { computed } from 'vue';
import AppSettingController from '@/actions/App/Http/Controllers/Settings/AppSettingController';
import AppImageField from '@/components/AppImageField.vue';
import Heading from '@/components/Heading.vue';
import InputError from '@/components/InputError.vue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Spinner } from '@/components/ui/spinner';

defineProps<{
    maxKilobytes: { logo: number; favicon: number };
    uploaded: { logo: boolean; favicon: boolean };
}>();

defineOptions({
    layout: {
        breadcrumbs: [
            {
                title: 'Pengaturan aplikasi',
                href: AppSettingController.edit(),
            },
        ],
    },
});

const IMAGE_ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp';
const FAVICON_ACCEPT =
    '.png,.ico,image/png,image/x-icon,image/vnd.microsoft.icon';
const SAMPLE = { logo: '/images/logo-contoh.png', favicon: '/favicon.ico' };

const site = computed(() => usePage().props.site);

const form = useForm<{
    app_name: string;
    app_description: string;
    logo: File | null;
    favicon: File | null;
    remove_logo: boolean;
    remove_favicon: boolean;
}>({
    app_name: site.value.name,
    app_description: site.value.description ?? '',
    logo: null,
    favicon: null,
    remove_logo: false,
    remove_favicon: false,
});

function submit(): void {
    form.submit(AppSettingController.update(), {
        preserveScroll: true,
        onSuccess: () =>
            form.reset('logo', 'favicon', 'remove_logo', 'remove_favicon'),
    });
}
</script>

<template>
    <!-- key: judul tab ikut nama aplikasi baru begitu disimpan. -->
    <Head :key="site.name" title="Pengaturan aplikasi" />

    <h1 class="sr-only">Pengaturan aplikasi</h1>

    <form class="flex flex-col space-y-6" @submit.prevent="submit">
        <Heading
            variant="small"
            title="Aplikasi"
            description="Nama, deskripsi, logo, dan favicon yang tampil di halaman depan, halaman masuk, sidebar, dan tab peramban"
        />

        <div class="grid gap-2">
            <Label for="app_name">Nama aplikasi</Label>
            <Input
                id="app_name"
                v-model="form.app_name"
                required
                maxlength="100"
                placeholder="Nama aplikasi"
            />
            <InputError :message="form.errors.app_name" />
        </div>

        <div class="grid gap-2">
            <Label for="app_description">Deskripsi aplikasi</Label>
            <textarea
                id="app_description"
                v-model="form.app_description"
                maxlength="300"
                rows="3"
                placeholder="Satu atau dua kalimat tentang aplikasi ini"
                class="flex min-h-20 w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-xs outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 md:text-sm"
            />
            <InputError :message="form.errors.app_description" />
        </div>

        <AppImageField
            id="logo"
            v-model:file="form.logo"
            v-model:remove="form.remove_logo"
            label="Logo"
            hint="JPG, PNG, atau WebP. Sebaiknya persegi dengan latar transparan."
            :accept="IMAGE_ACCEPT"
            :max-kilobytes="maxKilobytes.logo"
            :current-url="site.logo_url"
            :sample-url="SAMPLE.logo"
            :uploaded="uploaded.logo"
            :error="form.errors.logo"
        />

        <AppImageField
            id="favicon"
            v-model:file="form.favicon"
            v-model:remove="form.remove_favicon"
            label="Favicon"
            hint="Ikon di tab peramban. PNG atau ICO persegi, mis. 512×512 piksel."
            :accept="FAVICON_ACCEPT"
            :max-kilobytes="maxKilobytes.favicon"
            :current-url="site.favicon_url"
            :sample-url="SAMPLE.favicon"
            :uploaded="uploaded.favicon"
            :error="form.errors.favicon"
        />

        <div>
            <Button
                type="submit"
                :disabled="form.processing"
                data-test="save-app-settings"
            >
                <Spinner v-if="form.processing" />
                Simpan
            </Button>
        </div>
    </form>
</template>
