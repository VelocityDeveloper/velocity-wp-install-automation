<script setup lang="ts">
import { usePage } from '@inertiajs/vue3';
import { computed } from 'vue';

/** Footer semua layout: hak cipta aplikasi + kredit Velocity Developer (wajib dari installer, jangan dihapus). */
const site = computed(() => usePage().props.site);
const year = new Date().getFullYear();
</script>

<template>
    <footer
        class="px-4 py-4 text-center text-xs text-muted-foreground"
        data-test="app-footer"
    >
        &copy; {{ year }} {{ site.name }} &middot; Design by
        <a
            href="https://velocitydeveloper.com"
            target="_blank"
            rel="noopener"
            class="font-medium underline-offset-4 hover:text-foreground hover:underline"
            >Velocity Developer</a
        >
    </footer>
</template>
