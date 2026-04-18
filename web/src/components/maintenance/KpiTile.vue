<script setup lang="ts">
import { computed } from 'vue'

type Tone = 'neutral' | 'ok' | 'warn' | 'error' | 'accent'

interface Props {
  label: string
  value: string | number
  /** 次级文字（单位或趋势） */
  hint?: string
  tone?: Tone
  /** 左上角的小号 icon 字符（非必填，用 emoji 或字符避免引入 icon 包） */
  icon?: string
  loading?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  tone: 'neutral'
})

const toneCls = computed(() => {
  switch (props.tone) {
    case 'ok':
      return {
        dot: 'bg-state-active',
        value: 'text-ink-1',
        ring: 'border-state-active/25'
      }
    case 'warn':
      return {
        dot: 'bg-sig-amber',
        value: 'text-sig-amber',
        ring: 'border-sig-amber/30'
      }
    case 'error':
      return {
        dot: 'bg-state-invalidated',
        value: 'text-state-invalidated',
        ring: 'border-state-invalidated/35'
      }
    case 'accent':
      return {
        dot: 'bg-accent',
        value: 'text-ink-1',
        ring: 'border-accent/30'
      }
    case 'neutral':
    default:
      return {
        dot: 'bg-ink-5',
        value: 'text-ink-1',
        ring: 'border-shore-line/80'
      }
  }
})
</script>

<template>
  <div
    class="relative rounded-card bg-shore-card border p-4 flex flex-col gap-2 min-w-0"
    :class="toneCls.ring"
  >
    <div class="flex items-center justify-between gap-2">
      <span
        class="text-[10.5px] tracking-[0.16em] uppercase text-ink-4 font-display flex items-center gap-2"
      >
        <span class="shore-dot" :class="toneCls.dot" />
        {{ label }}
      </span>
      <span v-if="icon" class="text-[14px] text-ink-4">{{ icon }}</span>
    </div>
    <div class="flex items-baseline gap-2 min-w-0">
      <div
        class="font-display font-medium text-[26px] tabular leading-none truncate"
        :class="toneCls.value"
      >
        <template v-if="loading">—</template>
        <template v-else>{{ value }}</template>
      </div>
    </div>
    <div v-if="hint" class="text-[11.5px] text-ink-4 truncate" :title="hint">
      {{ hint }}
    </div>
  </div>
</template>
