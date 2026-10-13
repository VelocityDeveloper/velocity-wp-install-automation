<script setup lang="ts">
import { Moon, Sun } from '@lucide/vue';
import { computed } from 'vue';
import { Button } from '@/components/ui/button';
import { useAppearance } from '@/composables/useAppearance';

/** Tombol mode terang/gelap di header kanan atas (pengganti Pengaturan > Tampilan, installer Velocity). */
const { resolvedAppearance, updateAppearance } = useAppearance();

const isDark = computed(() => resolvedAppearance.value === 'dark');
const label = computed(() =>
    isDark.value ? 'Ganti ke mode terang' : 'Ganti ke mode gelap',
);

function toggle(): void {
    updateAppearance(isDark.value ? 'light' : 'dark');
}
</script>

<template>
    <Button
        variant="ghost"
        size="icon"
        class="size-9 shrink-0"
        :aria-label="label"
        :title="label"
        data-test="appearance-toggle"
        @click="toggle"
    >
        <Sun v-if="isDark" class="size-5" />
        <Moon v-else class="size-5" />
    </Button>
</template>
