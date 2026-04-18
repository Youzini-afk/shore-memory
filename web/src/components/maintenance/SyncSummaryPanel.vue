<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import PCard from '@/components/ui/PCard.vue'
import PBadge from '@/components/ui/PBadge.vue'
import PButton from '@/components/ui/PButton.vue'
import { useMaintenanceStore } from '@/stores/maintenance'

const store = useMaintenanceStore()
const { summary, summaryError, summaryLoading, lastSummaryAt, totalTasks } =
  storeToRefs(store)

const STATUS_ORDER: Array<{ key: string; label: string; tone: 'active' | 'accent' | 'amber' | 'invalidated' | 'ink' }> = [
  { key: 'pending', label: 'Pending', tone: 'amber' },
  { key: 'processing', label: 'Processing', tone: 'accent' },
  { key: 'completed', label: 'Completed', tone: 'active' },
  { key: 'failed', label: 'Failed', tone: 'invalidated' }
]

const KIND_LABEL: Record<string, string> = {
  score_turn: '评分 (score_turn)',
  reflection_run: '反思 (reflection_run)',
  rebuild_trivium: '重建索引 (rebuild_trivium)',
  index_memory: '入库 (index_memory)'
}

const KIND_ORDER = ['score_turn', 'reflection_run', 'rebuild_trivium', 'index_memory']

const statusSeries = computed(() => {
  const map = summary.value?.by_status ?? {}
  const total = Math.max(
    1,
    Object.values(map).reduce((acc, v) => acc + (v ?? 0), 0)
  )
  return STATUS_ORDER.map((entry) => {
    const count = map[entry.key] ?? 0
    return {
      ...entry,
      count,
      pct: Math.max(count > 0 ? 2 : 0, Math.round((count / total) * 100))
    }
  })
})

const kindSeries = computed(() => {
  const map = summary.value?.by_kind ?? {}
  const extras = Object.keys(map).filter((k) => !KIND_ORDER.includes(k))
  return [...KIND_ORDER, ...extras].map((key) => ({
    key,
    label: KIND_LABEL[key] ?? key,
    count: map[key] ?? 0
  }))
})

const oldestPendingAgo = computed(() => {
  const iso = summary.value?.oldest_pending_created_at
  if (!iso) return null
  const ts = Date.parse(iso)
  if (Number.isNaN(ts)) return iso
  const diff = Date.now() - ts
  if (diff < 1000) return '刚刚'
  if (diff < 60_000) return `${Math.floor(diff / 1000)} 秒前`
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return new Date(ts).toLocaleString()
})

const summaryAgeLabel = computed(() => {
  if (!lastSummaryAt.value) return null
  const diff = Date.now() - lastSummaryAt.value
  if (diff < 3_000) return '刚刚刷新'
  if (diff < 60_000) return `${Math.floor(diff / 1000)} 秒前`
  return `${Math.floor(diff / 60_000)} 分钟前`
})

const errorExpanded = ref(false)
function toggleError() {
  errorExpanded.value = !errorExpanded.value
}
</script>

<template>
  <PCard edge class="flex flex-col gap-4 h-full">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="font-display text-[14px] text-ink-1">任务队列摘要</div>
        <div class="mt-0.5 text-[11.5px] text-ink-4">
          共 <span class="tabular text-ink-2">{{ totalTasks }}</span> 条任务
          · 每 15s 自动刷新
          <span v-if="summaryAgeLabel" class="ml-1 text-ink-5">· {{ summaryAgeLabel }}</span>
        </div>
      </div>
      <PButton size="sm" variant="ghost" :loading="summaryLoading" @click="store.refreshSummary()">
        刷新
      </PButton>
    </div>

    <div v-if="summaryError" class="rounded-btn bg-state-invalidated/10 border border-state-invalidated/30 px-3 py-2 text-[11.5px] text-state-invalidated">
      {{ summaryError }}
    </div>

    <!-- by_status bar -->
    <div class="flex flex-col gap-2">
      <div class="text-[10.5px] tracking-[0.14em] uppercase text-ink-4 font-display">
        按状态分布
      </div>
      <div class="flex h-3 rounded-pill overflow-hidden border border-shore-line/60 bg-[#0F1018]">
        <div
          v-for="entry in statusSeries"
          :key="entry.key"
          class="h-full transition-all duration-240 ease-shore"
          :class="[
            entry.tone === 'amber' && 'bg-sig-amber/70',
            entry.tone === 'accent' && 'bg-accent/70',
            entry.tone === 'active' && 'bg-state-active/70',
            entry.tone === 'invalidated' && 'bg-state-invalidated/80'
          ]"
          :style="{ width: entry.pct + '%' }"
          :title="`${entry.label}: ${entry.count}`"
        />
      </div>
      <div class="flex flex-wrap gap-x-4 gap-y-1.5 text-[11.5px]">
        <span
          v-for="entry in statusSeries"
          :key="entry.key"
          class="inline-flex items-center gap-1.5"
        >
          <PBadge :tone="entry.tone" size="sm" dot>{{ entry.label }}</PBadge>
          <span class="tabular text-ink-2">{{ entry.count }}</span>
        </span>
      </div>
    </div>

    <!-- by_kind list -->
    <div class="flex flex-col gap-2">
      <div class="text-[10.5px] tracking-[0.14em] uppercase text-ink-4 font-display">
        按任务类型
      </div>
      <ul class="flex flex-col divide-y divide-shore-line/60">
        <li
          v-for="entry in kindSeries"
          :key="entry.key"
          class="flex items-center justify-between py-1.5 text-[12px]"
        >
          <span class="text-ink-2">{{ entry.label }}</span>
          <span class="tabular text-ink-1">{{ entry.count }}</span>
        </li>
      </ul>
    </div>

    <!-- oldest pending / latest error -->
    <div class="flex flex-col gap-2 pt-2 border-t border-shore-line/60">
      <div class="flex items-center justify-between text-[12px]">
        <span class="text-ink-4">最老待处理</span>
        <span class="tabular text-ink-1">
          {{ oldestPendingAgo ?? '—' }}
        </span>
      </div>
      <div v-if="summary?.latest_error" class="rounded-btn bg-state-invalidated/10 border border-state-invalidated/25 px-3 py-2">
        <button
          type="button"
          class="w-full flex items-center justify-between gap-2 text-[11.5px] text-state-invalidated"
          @click="toggleError"
        >
          <span class="tracking-wide uppercase font-display">最近失败</span>
          <span class="text-[10px] text-ink-4">{{ errorExpanded ? '收起' : '展开' }}</span>
        </button>
        <pre
          v-if="errorExpanded"
          class="mt-2 whitespace-pre-wrap break-words font-mono text-[11px] text-state-invalidated/90 max-h-40 overflow-auto"
        >{{ summary.latest_error }}</pre>
      </div>
    </div>
  </PCard>
</template>
