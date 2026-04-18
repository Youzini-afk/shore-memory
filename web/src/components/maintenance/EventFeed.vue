<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import PCard from '@/components/ui/PCard.vue'
import PBadge from '@/components/ui/PBadge.vue'
import PButton from '@/components/ui/PButton.vue'
import { useMaintenanceStore, type RecordedEvent } from '@/stores/maintenance'
import { useAppStore } from '@/stores/app'

const store = useMaintenanceStore()
const app = useAppStore()
const { events } = storeToRefs(store)

type FilterKey = 'all' | 'memory' | 'agent' | 'maintenance' | 'error' | 'config'

const FILTER_OPTIONS: Array<{ value: FilterKey; label: string; hint: string }> = [
  { value: 'all', label: '全部', hint: '所有类型' },
  { value: 'memory', label: '记忆', hint: 'memory.*' },
  { value: 'agent', label: 'Agent', hint: 'agent.state.*' },
  { value: 'maintenance', label: '维护', hint: 'maintenance.*' },
  { value: 'error', label: '错误', hint: 'sync.failed / lagged' },
  { value: 'config', label: '配置', hint: 'model_config.*' }
]

const filter = ref<FilterKey>('all')

function matchesFilter(evt: RecordedEvent, key: FilterKey): boolean {
  if (key === 'all') return true
  if (key === 'memory') return evt.event.startsWith('memory.')
  if (key === 'agent') return evt.event.startsWith('agent.')
  if (key === 'maintenance') return evt.event.startsWith('maintenance.')
  if (key === 'error') return evt.event === 'sync.failed' || evt.event === 'lagged'
  if (key === 'config') return evt.event.startsWith('model_config.')
  return true
}

const filtered = computed(() => events.value.filter((e) => matchesFilter(e, filter.value)))

function eventTone(event: string): 'accent' | 'blue' | 'active' | 'amber' | 'invalidated' | 'ink' {
  if (event.startsWith('memory.')) return 'accent'
  if (event.startsWith('agent.')) return 'blue'
  if (event.startsWith('maintenance.')) return 'active'
  if (event === 'sync.failed') return 'invalidated'
  if (event === 'lagged') return 'amber'
  if (event.startsWith('model_config.')) return 'amber'
  return 'ink'
}

function formatTime(evt: RecordedEvent): string {
  const iso = evt.at
  const ts = iso ? Date.parse(iso) : evt.receivedAt
  const base = Number.isNaN(ts) ? evt.receivedAt : ts
  const now = new Date()
  const sameDay = new Date(base).toDateString() === now.toDateString()
  if (sameDay) {
    return new Date(base).toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }
  return new Date(base).toLocaleString()
}

function describePayload(evt: RecordedEvent): string {
  const p = evt.payload
  if (!p || typeof p !== 'object') return ''
  const fragments: string[] = []
  const maybe = (key: string) => {
    const v = (p as Record<string, unknown>)[key]
    if (typeof v === 'string' || typeof v === 'number') {
      fragments.push(`${key}=${v}`)
    }
  }
  maybe('agent_id')
  maybe('memory_id')
  maybe('task_id')
  maybe('kind')
  maybe('retried')
  if (fragments.length === 0) {
    const keys = Object.keys(p).slice(0, 3)
    if (keys.length) fragments.push(keys.join(', '))
  }
  return fragments.join(' · ')
}

function stringifyPayload(evt: RecordedEvent): string {
  try {
    return JSON.stringify(evt.payload, null, 2)
  } catch {
    return String(evt.payload)
  }
}

const openIds = ref<Set<string>>(new Set())
function toggleOpen(id: string) {
  if (openIds.value.has(id)) {
    openIds.value.delete(id)
  } else {
    openIds.value.add(id)
  }
  // ref 需要 reassign 才能触发响应
  openIds.value = new Set(openIds.value)
}
</script>

<template>
  <PCard edge class="flex flex-col gap-3 h-full min-h-0">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="font-display text-[14px] text-ink-1">实时事件流</div>
        <div class="mt-0.5 text-[11.5px] text-ink-4">
          订阅 <code class="font-mono text-ink-3">/v1/events</code>
          · WS {{ app.isEventsOpen ? '已连接' : '未连接' }}
        </div>
      </div>
      <PButton size="sm" variant="ghost" :disabled="events.length === 0" @click="store.clearEvents()">
        清空
      </PButton>
    </div>

    <!-- 筛选 -->
    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="opt in FILTER_OPTIONS"
        :key="opt.value"
        type="button"
        :title="opt.hint"
        class="px-2.5 h-6 rounded-pill text-[11px] border transition-all duration-240 ease-shore select-none"
        :class="
          filter === opt.value
            ? 'text-ink-1 border-accent/50 bg-accent/12'
            : 'text-ink-3 border-shore-line hover:text-ink-1 hover:border-shore-border hover:bg-shore-hover'
        "
        @click="filter = opt.value"
      >
        {{ opt.label }}
      </button>
    </div>

    <!-- 列表 -->
    <div class="flex-1 min-h-0 overflow-auto rounded-btn bg-[#0F1018] border border-shore-line/60">
      <div v-if="filtered.length === 0" class="py-8 text-center text-[12px] text-ink-4">
        <template v-if="!app.isEventsOpen">等待 WS 连接…</template>
        <template v-else-if="filter !== 'all'">当前筛选下暂无事件</template>
        <template v-else>等待事件到达</template>
      </div>

      <ol v-else class="divide-y divide-shore-line/60">
        <li
          v-for="evt in filtered"
          :key="evt.id"
          class="px-3 py-2 flex flex-col gap-1"
        >
          <div class="flex items-center gap-2 flex-wrap">
            <PBadge :tone="eventTone(evt.event)" size="sm" dot>
              {{ evt.event }}
            </PBadge>
            <span class="text-[11px] text-ink-4 tabular">{{ formatTime(evt) }}</span>
            <button
              type="button"
              class="ml-auto text-[10.5px] text-ink-5 hover:text-ink-2 transition-colors"
              @click="toggleOpen(evt.id)"
            >
              {{ openIds.has(evt.id) ? '收起 payload' : '展开 payload' }}
            </button>
          </div>
          <div v-if="describePayload(evt)" class="text-[11.5px] text-ink-3 font-mono truncate">
            {{ describePayload(evt) }}
          </div>
          <pre
            v-if="openIds.has(evt.id)"
            class="mt-1 rounded-btn bg-[#08080C] border border-shore-line/60 p-2 whitespace-pre-wrap break-words font-mono text-[11px] text-ink-2 max-h-60 overflow-auto"
          >{{ stringifyPayload(evt) }}</pre>
        </li>
      </ol>
    </div>

    <div class="text-[10.5px] text-ink-5 tabular">
      缓冲 {{ events.length }} / 100 条
    </div>
  </PCard>
</template>
