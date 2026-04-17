<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import PHero from '@/components/ui/PHero.vue'
import PBadge from '@/components/ui/PBadge.vue'
import PKbd from '@/components/ui/PKbd.vue'
import QueryBuilder from '@/components/recall/QueryBuilder.vue'
import ResultsPanel from '@/components/recall/ResultsPanel.vue'
import { useAppStore } from '@/stores/app'
import { useRecallStore } from '@/stores/recall'
import { useHotkey } from '@/composables/useHotkeys'

const app = useAppStore()
const recall = useRecallStore()
const { lastLatencyMs, hits, degraded, response } = storeToRefs(recall)

const queryBuilderRef = ref<InstanceType<typeof QueryBuilder> | null>(null)

// ⌘/Ctrl + Enter 直接提交（无论焦点在哪）
useHotkey(
  'mod+enter',
  () => {
    void recall.submit()
  },
  { preventDefault: true }
)

// ⌘/Ctrl + K 聚焦查询输入
useHotkey(
  'mod+k',
  () => {
    queryBuilderRef.value?.focusQuery()
  },
  { preventDefault: true }
)
</script>

<template>
  <div class="min-h-full flex flex-col">
    <PHero
      title="Recall Playground"
      subtitle="对 Agent 的长期记忆做一次多信号召回 · 观察分数拆解"
    >
      <template #actions>
        <div class="flex items-center gap-2">
          <PBadge tone="accent" size="sm" dot>
            Agent · {{ app.agentId }}
          </PBadge>
          <PBadge v-if="response !== null" :tone="degraded ? 'amber' : 'active'" size="sm">
            {{ degraded ? 'degraded' : 'nominal' }}
          </PBadge>
          <div
            v-if="response !== null"
            class="hidden md:flex items-center gap-2 text-[11px] text-ink-4 font-display pl-1"
          >
            <span class="tabular text-ink-2">{{ lastLatencyMs }} ms</span>
            <span>·</span>
            <span class="tabular text-ink-2">{{ hits }} hit</span>
          </div>
          <span class="hidden md:inline-flex items-center gap-1.5 text-[10.5px] text-ink-5 pl-2">
            召回 <PKbd combo="mod+enter" /> 聚焦 <PKbd combo="mod+k" />
          </span>
        </div>
      </template>
    </PHero>

    <div class="px-8 pb-10 flex-1 grid grid-cols-12 gap-5 min-h-0">
      <div class="col-span-12 xl:col-span-5 min-w-0">
        <QueryBuilder ref="queryBuilderRef" />
      </div>
      <div class="col-span-12 xl:col-span-7 min-w-0">
        <ResultsPanel />
      </div>
    </div>
  </div>
</template>
