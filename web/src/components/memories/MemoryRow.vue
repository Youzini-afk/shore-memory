<script setup lang="ts">
import { computed } from 'vue'
import type { MemoryRecord, MemoryState } from '@/api/types'
import PBadge from '@/components/ui/PBadge.vue'

interface Props {
  memory: MemoryRecord
  selected?: boolean
}
const props = defineProps<Props>()

const stateTone = computed<'active' | 'superseded' | 'invalidated' | 'archived'>(() => {
  const s = (props.memory.state || 'active') as MemoryState
  if (s === 'active' || s === 'superseded' || s === 'invalidated' || s === 'archived') return s
  return 'archived'
})

const stateDotVar = computed(() => `var(--state-${stateTone.value})`)

const scopeTone = computed<'accent' | 'blue' | 'amber' | 'ink'>(() => {
  switch (props.memory.scope) {
    case 'private':
      return 'accent'
    case 'group':
      return 'blue'
    case 'shared':
      return 'amber'
    case 'system':
      return 'ink'
    default:
      return 'ink'
  }
})

const relativeTime = computed(() => {
  const ts = Date.parse(props.memory.updated_at || props.memory.created_at || '')
  if (Number.isNaN(ts)) return ''
  const diff = (Date.now() - ts) / 1000
  if (diff < 60) return `${Math.max(1, Math.floor(diff))}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d`
  return new Date(ts).toLocaleDateString()
})

const importanceTone = computed(() => {
  const v = props.memory.importance
  if (v >= 7) return 'text-sig-amber'
  if (v >= 4) return 'text-accent'
  return 'text-ink-4'
})

const importanceDisplay = computed(() => {
  const v = props.memory.importance
  if (!Number.isFinite(v)) return '—'
  return v.toFixed(1)
})

const contentPreview = computed(() => {
  const c = props.memory.content ?? ''
  return c.length > 280 ? `${c.slice(0, 280)}…` : c
})

const entityCount = computed(() => {
  const meta = props.memory.metadata as Record<string, unknown> | undefined
  const linked = props.memory.linked_memory_ids?.length ?? 0
  const tagCount = props.memory.tags?.length ?? 0
  return { linked, tags: tagCount, meta: meta ? Object.keys(meta).length : 0 }
})
</script>

<template>
  <div
    class="group relative flex gap-3 px-5 py-3 cursor-pointer transition-colors border-b border-shore-line/40 hover:bg-shore-hover"
    :class="selected ? 'bg-shore-selected' : ''"
  >
    <!-- Left state rail -->
    <div class="relative w-[2px] shrink-0 self-stretch">
      <span
        class="absolute inset-0 rounded-[2px]"
        :style="{ background: stateDotVar, opacity: selected ? 0.95 : 0.5 }"
      />
    </div>

    <!-- Main -->
    <div class="flex-1 min-w-0">
      <!-- Top meta row -->
      <div class="flex items-center gap-2 text-[11px] font-display">
        <span class="tabular text-ink-5 shrink-0">#{{ memory.id }}</span>
        <span class="text-ink-4 truncate max-w-[120px]">{{ memory.memory_type }}</span>
        <PBadge :tone="stateTone" size="sm">{{ stateTone }}</PBadge>
        <PBadge :tone="scopeTone" size="sm">{{ memory.scope }}</PBadge>
        <span v-if="memory.archived_at" class="text-[10.5px] text-state-archived">archived</span>
        <span v-if="memory.supersedes_memory_id" class="text-[10.5px] text-state-superseded">
          supersedes · #{{ memory.supersedes_memory_id }}
        </span>
        <span class="flex-1" />
        <span
          class="tabular text-[10.5px] font-display"
          :class="importanceTone"
          title="importance"
        >
          {{ importanceDisplay }}
        </span>
        <span class="tabular text-[10.5px] text-ink-4 shrink-0">{{ relativeTime }}</span>
      </div>

      <!-- Content -->
      <div
        class="mt-1 text-[13px] leading-[1.55] text-ink-1 line-clamp-2"
        :class="stateTone === 'archived' || stateTone === 'invalidated' ? 'opacity-60 italic' : ''"
      >
        {{ contentPreview }}
      </div>

      <!-- Meta footer -->
      <div class="mt-1.5 flex items-center gap-3 text-[10.5px] text-ink-5 font-display">
        <span v-if="memory.tags?.length" class="flex items-center gap-1">
          <span class="h-1 w-1 rounded-full bg-accent/70" />
          {{ entityCount.tags }} tag{{ entityCount.tags === 1 ? '' : 's' }}
        </span>
        <span v-if="memory.linked_memory_ids?.length" class="flex items-center gap-1">
          <span class="h-1 w-1 rounded-full bg-sig-blue/80" />
          {{ entityCount.linked }} link{{ entityCount.linked === 1 ? '' : 's' }}
        </span>
        <span v-if="memory.source" class="truncate max-w-[160px]">
          src · <span class="text-ink-3">{{ memory.source }}</span>
        </span>
        <span v-if="memory.session_uid" class="truncate max-w-[200px]">
          session · <span class="text-ink-3">{{ memory.session_uid }}</span>
        </span>
      </div>
    </div>
  </div>
</template>
