<script setup lang="ts">
import { LifeBuoy, MessageCircle } from '@lucide/vue';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';

/**
 * Tombol "Bantuan Support" di header dashboard (installer Velocity, 25 Nov 2026): info kontak Tim Support.
 * Nomor tetap (Tim Support Velocity), bukan pengaturan admin.
 */
const nomorWa = '6287742295809';
const nomorTampil = '0877-4229-5809';
</script>

<template>
    <Dialog>
        <DialogTrigger as-child>
            <Button
                variant="outline"
                size="sm"
                class="h-9 shrink-0 gap-2 max-sm:size-9 max-sm:px-0"
                title="Bantuan Tim Support"
                data-test="bantuan-support"
            >
                <LifeBuoy class="size-4" />
                <span class="max-sm:sr-only">Bantuan Support</span>
            </Button>
        </DialogTrigger>
        <DialogContent class="sm:max-w-md">
            <DialogHeader>
                <DialogTitle>Butuh bantuan?</DialogTitle>
                <DialogDescription>
                    Jika perlu bantuan, silakan menghubungi Tim Support kami
                    lewat WhatsApp.
                </DialogDescription>
            </DialogHeader>
            <div
                class="flex items-center justify-between gap-3 rounded-lg border p-4"
            >
                <div class="min-w-0">
                    <p class="text-sm text-muted-foreground">Tim Support</p>
                    <p class="text-lg font-semibold tabular-nums">
                        {{ nomorTampil }}
                    </p>
                </div>
                <Button as-child class="shrink-0 gap-2">
                    <a
                        :href="`https://wa.me/${nomorWa}`"
                        target="_blank"
                        rel="noopener"
                        data-test="bantuan-support-wa"
                    >
                        <MessageCircle class="size-4" />
                        Chat WhatsApp
                    </a>
                </Button>
            </div>
        </DialogContent>
    </Dialog>
</template>
