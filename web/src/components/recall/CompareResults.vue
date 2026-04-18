<script setup lang="ts">
/**
 * A/B Compare 模式结果：两列 HitCard，每条打上 "shared" / "unique" 标签，
 * 共同命中附带 rank drift 小提示。
 */
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { Sparkles, AlertTriangle } from 'lucide-vue-next'
import PCard from '@/components/ui/PCard.vue'
import PBadge from '@/components/ui/PBadge.vue'
import HitCard from './HitCard.vue'
import { useRecallStore } from '@/stores/recall'

const store = useRecallStore()
const { variantA, variantB, compareDiff } = storeToRefs(store)

const sharedIdSet = computed(() => new Set(compareDiff.value.intersection))
const driftById = computed(() => {
  const m = new Map<number, number>()
  for (const p of compareDiff.value.rankPairs) m.set(p.id, p.drift)
  return m
})

function hitsFor(which: 'a' | 'b') {
  const v = which === 'a' ? variantA.value : variantB.value
  return v.response?.memory_context ?? []
}

function columnMeta(which: 'a' | 'b') {
  const v = which === 'a' ? variantA.value : variantB.value
  const color = which === 'a' ? '#7C5CFF' : '#38BDF8'
  return {
    label: v.config.label,
    recipe: v.config.recipe,
    color,
    loading: v.loading,
    error: v.error,
    response: v.response
  }
}
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
    <!-- Column A -->
    <PCard
      v-for="which in ['a', 'b'] as const"
      :key="which"
      edge
      class="!p-0 overflow-hidden"
    >
      <div
        class="px-5 pt-4 pb-3 border-b border-shore-line/80 flex items-center justify-between"
      >
        <div class="flex items-center gap-2">
          <span
            class="h-5 w-5 inline-flex items-center justify-center rounded-btn text-[11px] font-display tabular text-white"
            :style="{ background: columnMeta(which).color }"
          >
            {{ columnMeta(which).label }}
          </span>
          <span class="text-[11px] uppercase tracking-[0.2em] font-display text-ink-4">
            {{ columnMeta(which).recipe }}
          </span>
        </div>
        <span class="text-[10.5px] font-display text-ink-4 flex items-center gap-2">
          <template v-if="columnMeta(which).response">
            <span class="tabular text-ink-2">
              {{ columnMeta(which).response?.memory_context.length ?? 0 }} 条
            </span>
            <span v-if="columnMeta(which).response?.degraded" class="text-sig-amber">
              · 已降级
            </span>
            <span v-if="columnMeta(which).response?.query_plan" class="text-ink-5"> · </span>
            <span v-if="columnMeta(which).response?.query_plan" class="text-[10.5px] font-display text-ink-4">
              {{ columnMeta(which).response?.query_plan?.source }} ({{ columnMeta(which).response?.query_plan?.subqueries.length ?? 0 }} 条子查询)
            </span>
          </template>
          <span v-else class="text-ink-5">—</span>
        </span>
      </div>

      <div
        v-if="columnMeta(which).response?.query_plan"
        class="px-5 py-2 border-b border-shore-line/60 bg-shore-elev/25"
      >
        <div class="text-[10.5px] font-display text-ink-4 flex items-center gap-2">
          <span>plan: {{ columnMeta(which).response?.query_plan?.source }}</span>
          <span class="text-ink-5">·</span>
          <span>{{ columnMeta(which).response?.query_plan?.subqueries.length ?? 0 }} 条子查询</span>
          <span
            v-if="columnMeta(which).response?.query_plan?.planner_degraded"
            class="text-sig-amber"
          >
            · degraded
          </span>
        </div>
      </div>

      <div class="p-4">
        <!-- Loading -->
        <div v-if="columnMeta(which).loading" class="space-y-3">
          <div
            v-for="i in 3"
            :key="i"
            class="rounded-panel bg-shore-elev/60 border border-shore-line/60 h-[112px] animate-pulse"
          />
        </div>

        <!-- Error -->
        <div
          v-else-if="columnMeta(which).error"
          class="rounded-btn border border-state-invalidated/35 bg-state-invalidated/10 px-3 py-3 text-[12px] text-state-invalidated flex items-start gap-2"
        >
          <AlertTriangle class="h-4 w-4 mt-0.5 shrink-0" :stroke-width="1.75" />
          <span>{{ columnMeta(which).error }}</span>
        </div>

        <!-- Empty / not run -->
        <div
          v-else-if="!columnMeta(which).response"
          class="flex flex-col items-center justify-center py-12 gap-2"
        >
          <div
            class="h-9 w-9 rounded-card bg-accent/10 border border-accent/20 flex items-center justify-center text-accent"
          >
            <Sparkles class="h-4 w-4" :stroke-width="1.75" />
          </div>
          <div class="text-[11.5px] font-display text-ink-2">未运行</div>
          <div class="text-[10.5px] text-ink-5 text-center max-w-[240px]">
            点击顶部“运行对比”或此列的“仅跑”按钮
          </div>
        </div>

        <!-- No hits -->
        <div
          v-else-if="!columnMeta(which).response?.memory_context.length"
          class="text-center py-10 text-[11.5px] text-ink-4"
        >
          未命中记忆
        </div>

        <!-- Hits -->
        <div v-else class="flex flex-col gap-3">
          <div
            v-for="(mem, idx) in hitsFor(which)"
            :key="mem.id"
            class="relative"
          >
            <!-- shared / unique label -->
            <div
              class="absolute -top-1.5 left-2 z-[1] flex items-center gap-1"
            >
              <PBadge
                v-if="sharedIdSet.has(mem.id)"
                tone="active"
                size="sm"
              >
                共同
              </PBadge>
              <PBadge v-else tone="accent" size="sm">
                仅 {{ columnMeta(which).label }}
              </PBadge>
              <span
                v-if="sharedIdSet.has(mem.id) && (driftById.get(mem.id) ?? 0) > 0"
                class="text-[10px] font-display tabular text-ink-4"
                :title="'与另一变体的排名回调'"
              >
                Δ {{ driftById.get(mem.id) }}
              </span>
            </div>
            <HitCard
              :memory="mem"
              :rank="idx + 1"
              :subqueries="columnMeta(which).response?.query_plan?.subqueries ?? []"
            />
          </div>
        </div>
      </div>
    </PCard>
  </div>
</template>
