<script setup lang="ts">
interface Props {
  title: string
  subtitle?: string
}
defineProps<Props>()
</script>

<template>
  <div class="relative px-8 pt-8 pb-6 overflow-hidden">
    <div
      class="pointer-events-none absolute -top-24 -left-20 h-64 w-[560px] blur-[100px] opacity-40"
      style="background: radial-gradient(closest-side, rgba(124,92,255,0.45), transparent 70%)"
    />
    <div class="relative flex items-start justify-between gap-6">
      <div class="min-w-0">
        <h1 class="font-display text-[26px] leading-tight tracking-tight text-ink-1 truncate">
          {{ title }}
        </h1>
        <p v-if="subtitle" class="mt-1.5 text-[13px] text-ink-3">{{ subtitle }}</p>
      </div>
      <div class="shrink-0 flex items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <div
      class="pointer-events-none absolute left-8 right-8 bottom-0 h-px bg-gradient-to-r from-transparent via-shore-border to-transparent"
    />
  </div>
</template>
