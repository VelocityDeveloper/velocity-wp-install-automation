<script setup lang="ts">
import { Head, Link, usePage } from '@inertiajs/vue3';
import { computed } from 'vue';
import AppFooter from '@/components/AppFooter.vue';
import { Button } from '@/components/ui/button';
import { dashboard, login } from '@/routes';

/** Halaman depan: logo, nama, dan deskripsi dari Pengaturan > Aplikasi. */
const site = computed(() => usePage().props.site);
</script>

<template>
    <Head title="Selamat datang" />

    <div class="flex min-h-svh flex-col bg-background text-foreground">
        <main
            class="flex flex-1 flex-col items-center justify-center gap-8 p-6"
        >
            <div class="flex max-w-xl flex-col items-center gap-4 text-center">
                <img
                    :src="site.logo_url"
                    :alt="`Logo ${site.name}`"
                    class="size-20 object-contain"
                />
                <h1 class="text-2xl font-semibold sm:text-3xl">
                    {{ site.name }}
                </h1>
                <p
                    v-if="site.description"
                    class="text-sm whitespace-pre-line text-muted-foreground"
                >
                    {{ site.description }}
                </p>
            </div>

            <Button v-if="$page.props.auth.user" as-child>
                <Link :href="dashboard()">Buka Dasbor</Link>
            </Button>
            <Button v-else as-child>
                <Link :href="login()">Masuk</Link>
            </Button>
        </main>

        <AppFooter />
    </div>
</template>
