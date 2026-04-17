<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useGraphStore } from '@/stores/graph'

const store = useGraphStore()
const { stats, loading, layoutRunning } = storeToRefs(store)

const tiles = computed(() => [
  { label: '节点', value: stats.value.memoryCount + stats.value.entityCount, tone: 'accent' },
  {
    label: '边',
    value: stats.value.memoryEntityEdges + stats.value.supersedeEdges,
    tone: 'default'
  },
  { label: '簇团', value: stats.value.communityCount, tone: 'default' },
  {
    label: '覆盖',
    value:
      stats.value.totalMemoriesForAgent === 0
        ? '—'
        : `${stats.value.memoryCount}/${stats.value.totalMemoriesForAgent}`,
    tone: stats.value.truncated ? 'warn' : 'default'
  }
])
</script>

<template>
  <div
    class="rounded-panel border border-shore-line/80 bg-shore-surface/85 backdrop-blur-sm px-3 py-2.5 shadow-accent-sm"
  >
    <div class="flex items-center gap-2 mb-2">
      <div
        class="text-[10px] uppercase tracking-[0.22em] font-display text-ink-5 flex items-center gap-1.5"
      >
        <span class="h-1 w-1 rounded-full bg-accent" />
        统计
      </div>
      <span
        v-if="loading"
        class="text-[9.5px] uppercase tracking-widest text-ink-4 font-display"
      >
        · 加载中
      </span>
      <span
        v-else-if="layoutRunning"
        class="text-[9.5px] uppercase tracking-widest text-accent font-display flex items-center gap-1"
      >
        <span class="h-1 w-1 rounded-full bg-accent animate-pulse" />
        布局中
      </span>
    </div>
    <div class="grid grid-cols-2 gap-x-4 gap-y-1.5 min-w-[170px]">
      <div v-for="t in tiles" :key="t.label" class="flex flex-col">
        <span class="text-[9.5px] uppercase tracking-[0.22em] font-display text-ink-5">
          {{ t.label }}
        </span>
        <span
          class="text-[14px] font-display tabular"
          :class="
            t.tone === 'warn'
              ? 'text-sig-amber'
              : t.tone === 'accent'
                ? 'text-accent'
                : 'text-ink-1'
          "
        >
          {{ t.value }}
        </span>
      </div>
    </div>
  </div>
</template>
