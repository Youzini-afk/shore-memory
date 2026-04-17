<script setup lang="ts">
import { computed } from 'vue'
import type { ScoreBreakdown } from '@/api/types'

interface Props {
  breakdown?: ScoreBreakdown | null
  /** 没有 breakdown 时的 fallback 分数 */
  score?: number | null
}
const props = defineProps<Props>()

interface Segment {
  key: 'semantic' | 'bm25' | 'entity' | 'contiguity'
  label: string
  value: number
  color: string
}

const segments = computed<Segment[]>(() => {
  const b = props.breakdown
  if (!b) return []
  const all: Segment[] = [
    { key: 'semantic', label: 'semantic', value: b.semantic, color: '#7C5CFF' },
    { key: 'bm25', label: 'bm25', value: b.bm25, color: '#38BDF8' },
    { key: 'entity', label: 'entity', value: b.entity, color: '#22C55E' },
    { key: 'contiguity', label: 'contiguity', value: b.contiguity, color: '#F59E0B' }
  ]
  return all.filter((s) => Number.isFinite(s.value))
})

const sum = computed(() =>
  segments.value.reduce((acc, s) => acc + Math.max(0, s.value), 0)
)

function pct(v: number): number {
  if (sum.value <= 0) return 0
  return Math.max(0, v / sum.value) * 100
}

function fmt(v: number): string {
  if (!Number.isFinite(v)) return '—'
  if (Math.abs(v) >= 10) return v.toFixed(1)
  return v.toFixed(2)
}
</script>

<template>
  <div v-if="segments.length" class="flex flex-col gap-1.5">
    <div
      class="relative h-1.5 w-full rounded-pill bg-shore-line overflow-hidden flex"
    >
      <span
        v-for="s in segments"
        :key="s.key"
        class="h-full"
        :style="{ width: `${pct(Math.max(0, s.value))}%`, background: s.color }"
      />
    </div>
    <div class="flex items-center gap-3 flex-wrap text-[10.5px] text-ink-4 font-display">
      <span
        v-for="s in segments"
        :key="s.key"
        class="inline-flex items-center gap-1.5"
      >
        <span class="h-1.5 w-1.5 rounded-full" :style="{ background: s.color }" />
        <span class="text-ink-3">{{ s.label }}</span>
        <span class="tabular text-ink-2">{{ fmt(s.value) }}</span>
      </span>
    </div>
  </div>
  <div v-else-if="score !== null && score !== undefined" class="text-[10.5px] text-ink-4">
    score <span class="tabular text-ink-2">{{ fmt(score ?? 0) }}</span>
  </div>
</template>
