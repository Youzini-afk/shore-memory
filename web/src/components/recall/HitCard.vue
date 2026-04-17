<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronRight, ExternalLink, FileText, Target } from 'lucide-vue-next'
import type { MemorySnippet, ScoreBreakdown } from '@/api/types'
import PBadge from '@/components/ui/PBadge.vue'
import SignalBar from './SignalBar.vue'
import { useGraphStore } from '@/stores/graph'
import { useMemoriesStore } from '@/stores/memories'

interface Props {
  memory: MemorySnippet
  rank: number
}
const props = defineProps<Props>()
const router = useRouter()
const graph = useGraphStore()
const memories = useMemoriesStore()

const expanded = ref(false)

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
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  return `${Math.floor(diff / 86400)} d ago`
})

const scopeLabel = computed(() => props.memory.scope)

interface BreakdownRow {
  key: keyof Pick<ScoreBreakdown, 'semantic' | 'bm25' | 'entity' | 'contiguity'>
  label: string
  color: string
  value: number
  share: number
}

const breakdownRows = computed<BreakdownRow[]>(() => {
  const b = props.memory.score_breakdown
  if (!b) return []
  const palette = {
    semantic: '#7C5CFF',
    bm25: '#38BDF8',
    entity: '#22C55E',
    contiguity: '#F59E0B'
  }
  const rows: BreakdownRow[] = (
    ['semantic', 'bm25', 'entity', 'contiguity'] as const
  ).map((k) => ({
    key: k,
    label: k,
    color: palette[k],
    value: Number(b[k] ?? 0),
    share: 0
  }))
  const total = rows.reduce((acc, r) => acc + Math.max(0, r.value), 0)
  if (total > 0) {
    for (const r of rows) r.share = Math.max(0, r.value) / total
  }
  return rows
})

const combined = computed(() => props.memory.score_breakdown?.combined ?? null)
const divisor = computed(() => props.memory.score_breakdown?.divisor ?? null)

function viewInGraph(ev: Event) {
  ev.stopPropagation()
  graph.pingMemories([props.memory.id])
  void router.push({ name: 'graph' })
}

function openInMemories(ev: Event) {
  ev.stopPropagation()
  void memories.select(props.memory.id)
  void router.push({ name: 'memories' })
}

function toggleExpanded() {
  expanded.value = !expanded.value
}

function fmt(v: number): string {
  if (!Number.isFinite(v)) return '—'
  if (Math.abs(v) >= 100) return v.toFixed(0)
  if (Math.abs(v) >= 10) return v.toFixed(1)
  return v.toFixed(3)
}
</script>

<template>
  <article
    class="group relative rounded-panel bg-shore-card border border-shore-line/80 transition-all duration-240 ease-shore hover:border-shore-border"
    :class="expanded ? 'border-accent/45 shadow-accent-sm' : 'hover:-translate-y-[1px]'"
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

    <button
      type="button"
      class="w-full px-4 py-3.5 text-left"
      @click="toggleExpanded"
    >
      <header class="flex items-center gap-3">
        <span class="shore-dot"
          :class="{
            'text-state-active': stateTone === 'active',
            'text-state-superseded': stateTone === 'superseded',
            'text-state-invalidated': stateTone === 'invalidated',
            'text-state-archived': stateTone === 'archived'
          }"
        />
        <span class="font-mono tabular text-[11.5px] text-ink-3">#{{ memory.id }}</span>
        <PBadge :tone="stateTone === 'active' ? 'active' : stateTone" size="sm">
          {{ memory.lifecycle?.state ?? 'active' }}
        </PBadge>
        <PBadge tone="ink" size="sm">{{ scopeLabel }}</PBadge>
        <span class="ml-auto flex items-baseline gap-1 font-display tabular">
          <span class="text-[10px] uppercase tracking-wider text-ink-4">score</span>
          <span class="text-[18px] text-ink-1">{{ scoreDisplay }}</span>
          <span
            v-if="rank === 1"
            class="text-[9.5px] text-accent uppercase tracking-wider font-display"
          >
            top
          </span>
          <ChevronRight
            class="ml-2 h-3.5 w-3.5 text-ink-4 transition-transform duration-200"
            :class="expanded ? 'rotate-90 text-accent' : ''"
            :stroke-width="1.75"
          />
        </span>
      </header>

      <p
        class="mt-2 text-[13.5px] leading-[1.55] text-ink-1 whitespace-pre-wrap break-words"
        :class="expanded ? '' : 'line-clamp-2'"
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
          supersedes
          <span class="font-mono tabular text-ink-3">
            #{{ memory.lifecycle?.supersedes_memory_id }}
          </span>
        </span>
        <span v-if="memory.lifecycle?.invalid_at">
          invalid_at
          <span class="font-mono tabular text-ink-3">{{ memory.lifecycle?.invalid_at }}</span>
        </span>
      </div>
    </button>

    <!-- Expanded pane -->
    <div
      v-if="expanded"
      class="border-t border-shore-line/80 px-4 py-3.5 bg-shore-elev/35 space-y-3"
    >
      <!-- Action row -->
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="h-7 px-2.5 rounded-btn border border-shore-line bg-shore-card text-[11px] text-ink-2 hover:text-accent hover:border-accent/60 transition-colors flex items-center gap-1.5 font-display"
          @click="viewInGraph"
        >
          <Target class="h-3.5 w-3.5" :stroke-width="1.75" />
          view in graph
        </button>
        <button
          type="button"
          class="h-7 px-2.5 rounded-btn border border-shore-line bg-shore-card text-[11px] text-ink-2 hover:text-accent hover:border-accent/60 transition-colors flex items-center gap-1.5 font-display"
          @click="openInMemories"
        >
          <FileText class="h-3.5 w-3.5" :stroke-width="1.75" />
          open in memories
        </button>
        <span class="flex-1" />
        <span
          v-if="divisor !== null"
          class="text-[10.5px] font-display text-ink-4 tabular"
        >
          divisor
          <span class="text-ink-2 ml-0.5">{{ fmt(divisor) }}</span>
        </span>
        <span
          v-if="combined !== null"
          class="text-[10.5px] font-display text-ink-4 tabular"
        >
          combined
          <span class="text-ink-1 ml-0.5">{{ fmt(combined) }}</span>
        </span>
      </div>

      <!-- Signal table -->
      <div
        v-if="breakdownRows.length"
        class="rounded-btn border border-shore-line/60 divide-y divide-shore-line/50 bg-shore-card/45"
      >
        <div
          v-for="row in breakdownRows"
          :key="row.key"
          class="grid grid-cols-[90px_1fr_60px_46px] items-center px-3 py-2 text-[11.5px] font-display"
        >
          <div class="flex items-center gap-2 text-ink-2">
            <span class="h-1.5 w-1.5 rounded-full" :style="{ background: row.color }" />
            <span>{{ row.label }}</span>
          </div>
          <div class="relative h-1.5 rounded-pill bg-shore-elev overflow-hidden">
            <span
              class="absolute inset-y-0 left-0 rounded-pill"
              :style="{ width: `${row.share * 100}%`, background: row.color, opacity: 0.85 }"
            />
          </div>
          <div class="text-right tabular text-ink-1">{{ fmt(row.value) }}</div>
          <div class="text-right tabular text-ink-4">
            {{ (row.share * 100).toFixed(0) }}%
          </div>
        </div>
      </div>

      <!-- Meta row -->
      <div
        class="flex flex-wrap gap-x-5 gap-y-1.5 text-[10.5px] text-ink-4 font-display"
      >
        <span>
          time
          <span class="text-ink-2 ml-1 font-mono tabular">{{ memory.time }}</span>
        </span>
        <span v-if="memory.lifecycle?.valid_at">
          valid_at
          <span class="text-ink-2 ml-1 font-mono tabular">{{ memory.lifecycle?.valid_at }}</span>
        </span>
        <span v-if="memory.entities?.length">
          entities
          <span class="text-ink-2 ml-1 tabular">{{ memory.entities.length }}</span>
        </span>
      </div>

      <!-- Full entity list (expanded) -->
      <div
        v-if="memory.entities && memory.entities.length > 4"
        class="flex flex-wrap gap-1.5"
      >
        <span
          v-for="ent in memory.entities"
          :key="ent.name + ent.entity_type"
          class="inline-flex items-center gap-1 px-2 h-5 rounded-pill text-[10px] bg-accent/10 border border-accent/25 text-accent-hi"
          :title="ent.entity_type"
        >
          <span>{{ ent.name }}</span>
          <span class="text-[9px] opacity-75">·{{ ent.entity_type ?? '—' }}</span>
        </span>
      </div>

      <div
        v-if="memory.lifecycle?.supersedes_memory_id"
        class="text-[11px] text-ink-3 font-display flex items-center gap-1"
      >
        <ExternalLink class="h-3 w-3 text-state-superseded" :stroke-width="1.75" />
        supersedes memory
        <span class="font-mono tabular text-ink-1">
          #{{ memory.lifecycle?.supersedes_memory_id }}
        </span>
      </div>
    </div>
  </article>
</template>
