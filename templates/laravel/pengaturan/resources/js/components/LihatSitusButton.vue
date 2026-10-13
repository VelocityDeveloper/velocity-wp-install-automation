<script setup lang="ts">
import { ExternalLink } from '@lucide/vue';
import { Button } from '@/components/ui/button';
import { home } from '@/routes';

/**
 * Tombol "Lihat situs" di header dashboard (installer Velocity): membuka halaman publik di tab baru.
 * App tanpa situs publik (halaman depan langsung ke login) membuang tombol ini dari header.
 */
</script>

<template>
    <Button
        variant="outline"
        size="sm"
        class="h-9 shrink-0 gap-2 max-sm:size-9 max-sm:px-0"
        as-child
    >
        <a
            :href="home().url"
            target="_blank"
            rel="noopener"
            title="Lihat situs publik di tab baru"
            data-test="lihat-situs"
        >
            <ExternalLink class="size-4" />
            <span class="max-sm:sr-only">Lihat situs</span>
        </a>
    </Button>
</template>
