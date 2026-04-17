<script setup lang="ts">
import { Waypoints, Zap } from 'lucide-vue-next'
const items = [
  { color: '#10B981', label: '有效', kind: 'memory' },
  { color: '#7C5CFF', label: '已取代', kind: 'memory' },
  { color: '#F43F5E', label: '已失效', kind: 'memory' },
  { color: '#64748B', label: '已归档', kind: 'memory' },
  { color: '#38BDF8', label: '实体', kind: 'entity' }
] as const
</script>

<template>
  <div
    class="rounded-panel border border-shore-line/80 bg-shore-surface/85 backdrop-blur-sm px-3 py-2.5 shadow-accent-sm"
  >
    <div
      class="text-[10px] uppercase tracking-[0.22em] font-display text-ink-5 mb-1.5 flex items-center gap-1.5"
    >
      <span class="h-1 w-1 rounded-full bg-accent" />
      图例
    </div>
    <div class="flex flex-col gap-1">
      <div
        v-for="item in items"
        :key="item.label"
        class="flex items-center gap-2 text-[11px] font-display text-ink-2"
      >
        <span
          class="h-2.5 w-2.5 rounded-full shrink-0"
          :style="{ backgroundColor: item.color, boxShadow: `0 0 10px ${item.color}55` }"
        />
        <span>{{ item.label }}</span>
      </div>
    </div>
    <div class="mt-2 pt-2 border-t border-shore-line/60 space-y-1">
      <div class="flex items-center gap-1.5 text-[10.5px] text-ink-4">
        <Waypoints class="h-3 w-3 text-accent" :stroke-width="1.75" />
        <span class="font-display">记忆 ↔ 实体</span>
      </div>
      <div class="flex items-center gap-1.5 text-[10.5px] text-ink-4">
        <Zap class="h-3 w-3 text-state-invalidated" :stroke-width="1.75" />
        <span class="font-display">取代链</span>
      </div>
    </div>
  </div>
</template>
