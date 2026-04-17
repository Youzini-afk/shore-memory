<script setup lang="ts">
import { computed } from 'vue'
import type { MemorySnippet } from '@/api/types'
import PBadge from '@/components/ui/PBadge.vue'
import SignalBar from './SignalBar.vue'

interface Props {
  memory: MemorySnippet
  rank: number
}
const props = defineProps<Props>()

const stateTone = computed(() => {
  const s = props.memory.lifecycle?.state
  if (s === 'superseded') return 'superseded'
  if (s === 'invalidated') return 'invalidated'
  if (s === 'archived') return 'archived'
  return 'active'
})

const scoreDisplay = computed(() => {
  const s = props.memory.score
  if (typeof s !== 'number' || !Number.isFinite(s)) return '—'
  return s >= 10 ? s.toFixed(1) : s.toFixed(3)
})

const relTime = computed(() => {
  const t = props.memory.time
  if (!t) return ''
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '\u521a\u521a'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  return `${Math.floor(diff / 86400)} d ago`
})

const scopeLabel = computed(() => props.memory.scope)
</script>

<template>
  <article
    class="group relative rounded-panel bg-shore-card border border-shore-line/80 px-4 py-3.5 transition-all duration-240 ease-shore hover:border-shore-border hover:-translate-y-[1px]"
  >
    <span
      class="pointer-events-none absolute left-0 top-4 bottom-4 w-[2px] rounded-full opacity-70"
      :class="{
        'bg-state-active': stateTone === 'active',
        'bg-state-superseded': stateTone === 'superseded',
        'bg-state-invalidated': stateTone === 'invalidated',
        'bg-state-archived': stateTone === 'archived'
      }"
    />

    <header class="flex items-center gap-3">
      <span class="shore-dot"
        :class="{
          'text-state-active': stateTone === 'active',
          'text-state-superseded': stateTone === 'superseded',
          'text-state-invalidated': stateTone === 'invalidated',
          'text-state-archived': stateTone === 'archived'
        }"
      />
      <span class="font-mono tabular text-[11.5px] text-ink-3"
        >#{{ memory.id }}</span
      >
      <PBadge :tone="stateTone === 'active' ? 'active' : stateTone" size="sm">
        {{ memory.lifecycle?.state ?? 'active' }}
      </PBadge>
      <PBadge tone="ink" size="sm">{{ scopeLabel }}</PBadge>
      <span class="ml-auto flex items-baseline gap-1 font-display tabular">
        <span class="text-[10px] uppercase tracking-wider text-ink-4">score</span>
        <span class="text-[18px] text-ink-1">{{ scoreDisplay }}</span>
        <span v-if="rank === 1" class="text-[9.5px] text-accent uppercase tracking-wider font-display">top</span>
      </span>
    </header>

    <p
      class="mt-2 text-[13.5px] leading-[1.55] text-ink-1 line-clamp-2 whitespace-pre-wrap break-words"
    >
      {{ memory.content }}
    </p>

    <footer class="mt-3 flex items-start justify-between gap-4">
      <div class="flex-1 min-w-0">
        <SignalBar :breakdown="memory.score_breakdown" :score="memory.score" />
      </div>
      <div
        v-if="memory.entities && memory.entities.length"
        class="shrink-0 max-w-[220px] flex flex-wrap gap-1.5 justify-end"
      >
        <span
          v-for="ent in memory.entities.slice(0, 4)"
          :key="ent.name"
          class="inline-flex items-center px-2 h-5 rounded-pill text-[10px] bg-accent/10 border border-accent/25 text-accent-hi"
          :title="ent.entity_type"
          >{{ ent.name }}</span
        >
        <span
          v-if="(memory.entities?.length ?? 0) > 4"
          class="inline-flex items-center px-2 h-5 rounded-pill text-[10px] bg-shore-elev text-ink-4 border border-shore-line"
          >+{{ (memory.entities?.length ?? 0) - 4 }}</span
        >
      </div>
    </footer>

    <div class="mt-2 flex items-center gap-3 text-[10.5px] text-ink-5 font-display">
      <span>{{ relTime }}</span>
      <span v-if="memory.lifecycle?.supersedes_memory_id">
        supersedes <span class="font-mono tabular text-ink-3">#{{ memory.lifecycle?.supersedes_memory_id }}</span>
      </span>
      <span v-if="memory.lifecycle?.invalid_at">
        invalid_at <span class="font-mono tabular text-ink-3">{{ memory.lifecycle?.invalid_at }}</span>
      </span>
    </div>
  </article>
</template>
