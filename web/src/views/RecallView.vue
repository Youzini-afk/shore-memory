<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import PBadge from '@/components/ui/PBadge.vue'
import PSegment from '@/components/ui/PSegment.vue'
import QueryBuilder from '@/components/recall/QueryBuilder.vue'
import ResultsPanel from '@/components/recall/ResultsPanel.vue'
import SharedQueryInputs from '@/components/recall/SharedQueryInputs.vue'
import VariantInputs from '@/components/recall/VariantInputs.vue'
import CompareDiffBar from '@/components/recall/CompareDiffBar.vue'
import CompareResults from '@/components/recall/CompareResults.vue'
import { useAppStore } from '@/stores/app'
import { useRecallStore } from '@/stores/recall'
import type { RecallMode } from '@/stores/recall'

const app = useAppStore()
const recall = useRecallStore()
const { mode, variantA, variantB } = storeToRefs(recall)

const queryBuilderRef = ref<InstanceType<typeof QueryBuilder> | null>(null)

const modeOptions: Array<{ value: RecallMode; label: string; hint: string }> = [
  { value: 'single', label: 'Single', hint: '单次召回 · 细节模式' },
  { value: 'compare', label: 'A/B Compare', hint: '双变体并跑 · diff 视图' }
]

function onKey(ev: KeyboardEvent) {
  // ⌘K focus（保留原有行为）
  if ((ev.metaKey || ev.ctrlKey) && (ev.key === 'k' || ev.key === 'K')) {
    ev.preventDefault()
    queryBuilderRef.value?.focusQuery?.()
  }
  if ((ev.metaKey || ev.ctrlKey) && ev.key === 'Enter') {
    ev.preventDefault()
    if (mode.value === 'compare') {
      void recall.runCompare()
    } else {
      void recall.submit()
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div class="h-full flex flex-col min-h-0">
    <!-- Header -->
    <div class="relative px-8 pt-6 pb-4 overflow-hidden border-b border-shore-line/80">
      <div
        class="pointer-events-none absolute -top-24 -right-10 h-64 w-[520px] blur-[100px] opacity-35"
        style="background: radial-gradient(closest-side, rgba(124,92,255,0.45), transparent 70%)"
      />
      <div class="relative flex items-end justify-between gap-6">
        <div class="min-w-0">
          <h1 class="font-display text-[24px] leading-tight tracking-tight text-ink-1">
            Recall Playground
          </h1>
          <p class="mt-1 text-[12.5px] text-ink-3">
            四信号融合 · 语义 / BM25 / 实体 / 连贯性。调参、看分数、在 graph 上定位命中
          </p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <PBadge tone="accent" size="sm" dot>Agent · {{ app.agentId }}</PBadge>
          <PBadge v-if="mode === 'compare'" tone="blue" size="sm">
            A/B mode
          </PBadge>
        </div>
      </div>

      <!-- Mode switcher -->
      <div class="mt-4 flex items-center gap-3">
        <PSegment
          :model-value="mode"
          :options="modeOptions"
          size="sm"
          @update:model-value="(v) => recall.setMode(v as RecallMode)"
        />
        <span class="text-[10.5px] text-ink-5 font-display">
          <template v-if="mode === 'single'">
            调参 → 跑一次 → 看 score breakdown / 跳转 memory & graph
          </template>
          <template v-else>
            同 query 双变体并跑 · 自动算 Jaccard / rank drift / A-only / B-only
          </template>
        </span>
      </div>
    </div>

    <!-- Body · Single mode -->
    <div
      v-if="mode === 'single'"
      class="flex-1 min-h-0 grid grid-cols-12 gap-6 px-8 py-6 overflow-y-auto"
    >
      <div class="col-span-12 lg:col-span-5 xl:col-span-4">
        <QueryBuilder ref="queryBuilderRef" />
      </div>
      <div class="col-span-12 lg:col-span-7 xl:col-span-8 min-w-0">
        <ResultsPanel />
      </div>
    </div>

    <!-- Body · Compare mode -->
    <div
      v-else
      class="flex-1 min-h-0 px-8 py-6 overflow-y-auto space-y-5"
    >
      <!-- Shared query -->
      <SharedQueryInputs />

      <!-- A / B variant inputs -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <VariantInputs :variant="variantA" accent="accent-a" />
        <VariantInputs :variant="variantB" accent="accent-b" />
      </div>

      <!-- Diff summary -->
      <CompareDiffBar />

      <!-- Results -->
      <CompareResults />
    </div>
  </div>
</template>
