<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { AlertTriangle, Sparkles } from 'lucide-vue-next'
import { useRecallStore } from '@/stores/recall'
import PCard from '@/components/ui/PCard.vue'
import MetricTile from './MetricTile.vue'
import HitCard from './HitCard.vue'

const store = useRecallStore()
const { loading, response, memories, lastLatencyMs, degraded, form } = storeToRefs(store)

const hitCount = computed(() => memories.value.length)
const latencyDisplay = computed(() => {
  const v = lastLatencyMs.value
  if (v === null || v === undefined) return '—'
  return String(v)
})

const latencyTone = computed<'default' | 'good' | 'warn' | 'danger'>(() => {
  const v = lastLatencyMs.value
  if (v === null || v === undefined) return 'default'
  if (v < 120) return 'good'
  if (v < 500) return 'default'
  if (v < 1500) return 'warn'
  return 'danger'
})

const hitsTone = computed<'default' | 'good' | 'muted'>(() => {
  if (response.value === null) return 'muted'
  return hitCount.value > 0 ? 'good' : 'muted'
})

const agentState = computed(() => response.value?.agent_state ?? null)
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Metrics -->
    <div class="grid grid-cols-4 gap-3">
      <MetricTile
        label="Latency"
        :value="latencyDisplay"
        suffix="ms"
        :tone="latencyTone"
        hint="前端测量端到端耗时"
      />
      <MetricTile
        label="Hits"
        :value="response ? hitCount : '—'"
        :tone="hitsTone"
        :hint="response ? `配方 ${form.recipe}` : '等待召回'"
      />
      <MetricTile
        label="Recipe"
        :value="form.recipe"
        tone="accent"
        :hint="`limit ${form.limit}`"
      />
      <MetricTile
        label="Status"
        :value="response ? (degraded ? 'degraded' : 'nominal') : '—'"
        :tone="response ? (degraded ? 'warn' : 'good') : 'muted'"
        :hint="degraded ? 'embedding 不可用，已降级' : '向量通道正常'"
      />
    </div>

    <!-- Degraded banner -->
    <div
      v-if="degraded"
      class="rounded-panel border border-sig-amber/35 bg-sig-amber/10 px-4 py-3 flex items-start gap-3"
    >
      <AlertTriangle class="h-4 w-4 text-sig-amber mt-0.5" :stroke-width="1.75" />
      <div class="flex-1 min-w-0">
        <div class="text-[12.5px] text-sig-amber font-display tracking-tight">
          Degraded · 向量召回通道不可用
        </div>
        <div class="text-[11px] text-ink-3 mt-0.5">
          Worker embedding 暂不可用，已自动降级到 BM25 + 实体信号。结果仍可用，但排序精度受影响。
        </div>
      </div>
    </div>

    <!-- Results -->
    <PCard edge class="!p-0 overflow-hidden">
      <div
        class="px-5 pt-4 pb-3 border-b border-shore-line/80 flex items-center justify-between"
      >
        <div
          class="text-[11px] uppercase tracking-[0.2em] font-display text-ink-4 flex items-center gap-2"
        >
          <span class="h-1 w-1 rounded-full bg-accent" />
          命中结果
        </div>
        <div v-if="agentState" class="text-[10.5px] text-ink-4 font-display tracking-tight">
          Agent <span class="text-ink-2">{{ agentState.agent_id }}</span>
          · mood <span class="text-ink-2">{{ agentState.mood }}</span>
        </div>
      </div>

      <div class="p-5">
        <!-- Loading skeleton -->
        <div v-if="loading" class="space-y-3">
          <div
            v-for="i in 3"
            :key="i"
            class="rounded-panel bg-shore-elev/60 border border-shore-line/60 h-[112px] animate-pulse"
          />
        </div>

        <!-- Empty -->
        <div
          v-else-if="response === null"
          class="flex flex-col items-center justify-center py-16 gap-3"
        >
          <div
            class="h-12 w-12 rounded-card bg-accent/10 border border-accent/20 flex items-center justify-center text-accent"
          >
            <Sparkles class="h-5 w-5" :stroke-width="1.75" />
          </div>
          <div class="font-display text-[14px] text-ink-1">准备就绪</div>
          <div class="text-[11px] text-ink-4 max-w-md text-center">
            在左侧输入查询并按 ⌘↵ 开始召回；结果会按综合分数倒序排列，并拆解 semantic / bm25 / entity / contiguity 四路信号。
          </div>
        </div>

        <!-- No hits -->
        <div
          v-else-if="!hitCount"
          class="flex flex-col items-center justify-center py-12 gap-2"
        >
          <div class="font-display text-[13.5px] text-ink-1">没有命中结果</div>
          <div class="text-[11px] text-ink-4 text-center max-w-md">
            尝试切换 Recipe、放宽作用域、或开启 include_invalid 做时光回溯。
          </div>
        </div>

        <!-- Hits -->
        <div v-else class="flex flex-col gap-3">
          <HitCard
            v-for="(mem, idx) in memories"
            :key="mem.id"
            :memory="mem"
            :rank="idx + 1"
          />
        </div>
      </div>
    </PCard>
  </div>
</template>
