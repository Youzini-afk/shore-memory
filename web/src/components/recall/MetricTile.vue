<script setup lang="ts">
interface Props {
  label: string
  value: string | number
  suffix?: string
  tone?: 'default' | 'accent' | 'good' | 'warn' | 'danger' | 'muted'
  hint?: string
}
withDefaults(defineProps<Props>(), { tone: 'default' })
</script>

<template>
  <div
    class="relative rounded-panel bg-shore-card border border-shore-line/80 px-4 py-3.5 overflow-hidden"
  >
    <div
      class="pointer-events-none absolute -bottom-6 -right-6 h-16 w-16 blur-2xl opacity-40"
      :style="{
        background:
          tone === 'accent'
            ? 'radial-gradient(closest-side, rgba(124,92,255,0.45), transparent 70%)'
            : tone === 'good'
              ? 'radial-gradient(closest-side, rgba(16,185,129,0.35), transparent 70%)'
              : tone === 'warn'
                ? 'radial-gradient(closest-side, rgba(245,158,11,0.35), transparent 70%)'
                : tone === 'danger'
                  ? 'radial-gradient(closest-side, rgba(244,63,94,0.35), transparent 70%)'
                  : 'radial-gradient(closest-side, rgba(255,255,255,0.05), transparent 70%)'
      }"
    />
    <div
      class="text-[10.5px] uppercase tracking-[0.18em] font-display text-ink-4 flex items-center gap-1.5"
    >
      <span class="inline-block h-1 w-1 rounded-full"
        :class="{
          'bg-accent': tone === 'accent',
          'bg-state-active': tone === 'good',
          'bg-sig-amber': tone === 'warn',
          'bg-state-invalidated': tone === 'danger',
          'bg-ink-5': tone === 'muted' || tone === 'default'
        }"
      />
      {{ label }}
    </div>
    <div class="mt-1.5 flex items-baseline gap-1.5">
      <span
        class="font-display tabular text-[24px] leading-none"
        :class="{
          'text-ink-1': tone === 'default' || tone === 'muted',
          'text-accent-hi': tone === 'accent',
          'text-state-active': tone === 'good',
          'text-sig-amber': tone === 'warn',
          'text-state-invalidated': tone === 'danger'
        }"
      >
        {{ value }}
      </span>
      <span v-if="suffix" class="text-[11px] text-ink-4 font-display">{{ suffix }}</span>
    </div>
    <div v-if="hint" class="mt-1 text-[10.5px] text-ink-4">{{ hint }}</div>
  </div>
</template>
