<script setup lang="ts">
interface Props {
  label: string
  mono?: boolean
}
defineProps<Props>()
</script>

<template>
  <div class="grid grid-cols-[112px_1fr] gap-3 py-2 border-b border-shore-line/40 last:border-b-0">
    <div class="text-[10.5px] uppercase tracking-[0.2em] font-display text-ink-5 pt-0.5">
      {{ label }}
    </div>
    <div
      class="min-w-0 text-[12.5px] text-ink-1"
      :class="mono ? 'font-mono tabular break-all' : 'break-words'"
    >
      <slot>
        <span class="text-ink-5">—</span>
      </slot>
    </div>
  </div>
</template>
