<script setup lang="ts">
import { ImageUp, Trash2, Undo2 } from '@lucide/vue';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import InputError from '@/components/InputError.vue';
import { Button } from '@/components/ui/button';

/**
 * Satu gambar di Pengaturan > Aplikasi (logo, favicon): pratinjau, pilih berkas baru, dan tandai hapus
 * (kembali ke gambar contoh). Berkas dikirim bersama formulir saat Simpan ditekan.
 */
const props = defineProps<{
    id: string;
    label: string;
    hint: string;
    accept: string;
    maxKilobytes: number;
    currentUrl: string;
    sampleUrl: string;
    uploaded: boolean;
    error?: string;
}>();

const file = defineModel<File | null>('file', { required: true });
const remove = defineModel<boolean>('remove', { required: true });

const input = ref<HTMLInputElement | null>(null);
const localError = ref<string | undefined>();
const objectUrl = ref<string | null>(null);

watch(file, (value) => {
    if (objectUrl.value) {
        URL.revokeObjectURL(objectUrl.value);
    }

    objectUrl.value = value ? URL.createObjectURL(value) : null;
});

onBeforeUnmount(() => {
    if (objectUrl.value) {
        URL.revokeObjectURL(objectUrl.value);
    }
});

const previewUrl = computed(() =>
    remove.value ? props.sampleUrl : (objectUrl.value ?? props.currentUrl),
);

const maxLabel = computed(() =>
    props.maxKilobytes >= 1024
        ? `${props.maxKilobytes / 1024} MB`
        : `${props.maxKilobytes} KB`,
);

function choose(): void {
    input.value?.click();
}

function pick(event: Event): void {
    const target = event.target as HTMLInputElement;
    const picked = target.files?.[0] ?? null;
    target.value = '';
    localError.value = undefined;

    if (!picked) {
        return;
    }

    if (picked.size > props.maxKilobytes * 1024) {
        localError.value = `Ukuran ${props.label.toLowerCase()} maksimal ${maxLabel.value}.`;

        return;
    }

    file.value = picked;
    remove.value = false;
}

function undo(): void {
    file.value = null;
    remove.value = false;
}
</script>

<template>
    <div class="grid gap-2" :data-test="`setting-${id}`">
        <span class="text-sm font-medium">{{ label }}</span>
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start">
            <div
                class="flex size-24 shrink-0 items-center justify-center overflow-hidden rounded-md border border-dashed bg-muted/40"
            >
                <img
                    :src="previewUrl"
                    :alt="`Pratinjau ${label.toLowerCase()}`"
                    class="size-full object-contain p-2"
                />
            </div>
            <div class="grid gap-2">
                <p class="text-[13px] text-muted-foreground">
                    {{ hint }} Maksimal {{ maxLabel }}.
                </p>
                <p v-if="file" class="text-[13px]">
                    Berkas baru: {{ file.name }} (disimpan saat Simpan ditekan)
                </p>
                <p v-else-if="remove" class="text-[13px] text-destructive">
                    Kembali ke gambar contoh saat Simpan ditekan.
                </p>
                <p v-else-if="!uploaded" class="text-[13px] text-muted-foreground">
                    Saat ini memakai gambar contoh.
                </p>
                <div
                    class="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center"
                >
                    <input
                        :id="id"
                        ref="input"
                        type="file"
                        :accept="accept"
                        class="sr-only"
                        tabindex="-1"
                        aria-hidden="true"
                        :data-test="`${id}-input`"
                        @change="pick"
                    />
                    <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        @click="choose"
                    >
                        <ImageUp />
                        {{ uploaded || file ? 'Ganti' : 'Unggah' }}
                    </Button>
                    <Button
                        v-if="file || remove"
                        type="button"
                        variant="ghost"
                        size="sm"
                        @click="undo"
                    >
                        <Undo2 />
                        Batalkan
                    </Button>
                    <Button
                        v-else-if="uploaded"
                        type="button"
                        variant="ghost"
                        size="sm"
                        class="text-destructive hover:text-destructive"
                        @click="remove = true"
                    >
                        <Trash2 />
                        Hapus
                    </Button>
                </div>
                <InputError :message="localError ?? error" />
            </div>
        </div>
    </div>
</template>
