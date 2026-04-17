<script setup lang="ts">
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import { useAppStore } from '@/stores/app'
import { RefreshCw, Activity } from 'lucide-vue-next'

const route = useRoute()
const app = useAppStore()

const title = computed(() => (route.meta?.title as string | undefined) ?? 'Shore Memory')
const queueDepth = computed(() => app.health?.task_queue_depth ?? 0)
const envLabel = computed(() => {
  if (app.apiBase) return app.apiBase
  if (typeof window !== 'undefined') return `${window.location.host}`
  return '127.0.0.1:7811'
})
</script>

<template>
  <header
    class="h-14 shrink-0 flex items-center px-6 bg-shore-surface border-b border-shore-line/80"
  >
    <!-- Title -->
    <div class="flex items-center gap-3 min-w-0">
      <span class="text-[13px] font-display font-medium text-ink-1 truncate">{{ title }}</span>
      <span class="text-[11px] text-ink-5 font-display uppercase tracking-wider">/ Console</span>
    </div>

    <div class="flex-1" />

    <!-- Right cluster -->
    <div class="flex items-center gap-2.5">
      <div
        class="flex items-center gap-2 px-2.5 py-1 rounded-btn bg-shore-card/80 border border-shore-line/80 text-[11px] text-ink-3"
        :title="'当前 Agent'"
      >
        <div class="h-4 w-4 rounded-full bg-gradient-to-br from-accent-hi to-accent-lo" />
        <span class="font-display tracking-tight text-ink-1">{{ app.agentId }}</span>
      </div>

      <div
        class="flex items-center gap-1.5 px-2.5 py-1 rounded-btn bg-shore-card/80 border border-shore-line/80 text-[11px] text-ink-4 tabular"
        :title="'任务队列深度'"
      >
        <Activity class="h-3.5 w-3.5 text-ink-4" :stroke-width="1.75" />
        <span class="font-display">queue</span>
        <span class="text-ink-2">{{ queueDepth }}</span>
      </div>

      <div
        class="px-2.5 py-1 rounded-btn bg-shore-card/80 border border-shore-line/80 text-[11px] text-ink-4 font-mono"
      >
        {{ envLabel }}
      </div>

      <button
        class="h-8 w-8 flex items-center justify-center rounded-btn text-ink-3 hover:text-ink-1 hover:bg-shore-hover transition-colors"
        title="刷新健康状态"
        @click="app.refreshHealth"
      >
        <RefreshCw class="h-4 w-4" :stroke-width="1.75" />
      </button>
    </div>
  </header>
</template>
