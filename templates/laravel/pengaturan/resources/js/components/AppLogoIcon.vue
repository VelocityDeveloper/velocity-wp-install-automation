<script setup lang="ts">
import { usePage } from '@inertiajs/vue3';
import { computed } from 'vue';
import type { HTMLAttributes } from 'vue';

/** Logo aplikasi dari Pengaturan > Aplikasi (tanpa unggahan: logo contoh). Atur ukuran lewat class, mis. size-9. */
defineOptions({
    inheritAttrs: false,
});

type Props = {
    className?: HTMLAttributes['class'];
};

defineProps<Props>();

const site = computed(() => usePage().props.site);
</script>

<template>
    <img
        :src="site.logo_url"
        :alt="`Logo ${site.name}`"
        :class="['object-contain', className]"
        v-bind="$attrs"
    />
</template>
