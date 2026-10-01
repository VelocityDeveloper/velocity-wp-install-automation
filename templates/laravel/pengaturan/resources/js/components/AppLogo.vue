<script setup lang="ts">
import { usePage } from '@inertiajs/vue3';
import { computed } from 'vue';

/** Logo + nama aplikasi dari Pengaturan > Aplikasi (tanpa unggahan: logo contoh). */
const site = computed(() => usePage().props.site);
</script>

<template>
    <img
        :src="site.logo_url"
        :alt="`Logo ${site.name}`"
        class="size-8 shrink-0 rounded-md object-contain"
    />
    <div class="ml-1 grid flex-1 text-left text-sm">
        <span class="mb-0.5 truncate leading-tight font-semibold">{{
            site.name
        }}</span>
    </div>
</template>
