<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { AlertTriangle, Sparkles, Target } from 'lucide-vue-next'
import { useRecallStore } from '@/stores/recall'
import { useGraphStore } from '@/stores/graph'
import PCard from '@/components/ui/PCard.vue'
import MetricTile from './MetricTile.vue'
import HitCard from './HitCard.vue'

const store = useRecallStore()
const router = useRouter()
const graph = useGraphStore()
const { loading, response, memories, lastLatencyMs, degraded, form } = storeToRefs(store)

function pingAllInGraph() {
  const ids = memories.value.map((m) => m.id)
  if (!ids.length) return
  graph.pingMemories(ids)
  void router.push({ name: 'graph' })
}

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
const queryPlan = computed(() => response.value?.query_plan ?? null)
const plannedSubqueries = computed(() => queryPlan.value?.subqueries ?? [])
</script>

<template>
  <div class="flex flex-col gap-4">
    <!-- Metrics -->
    <div class="grid grid-cols-4 gap-3">
      <MetricTile
        label="延迟"
        :value="latencyDisplay"
        suffix="ms"
        :tone="latencyTone"
        hint="前端测量端到端耗时"
      />
      <MetricTile
        label="命中条数"
        :value="response ? hitCount : '—'"
        :tone="hitsTone"
        :hint="response ? `配方 ${form.recipe}` : '等待召回'"
      />
      <MetricTile
        label="配方"
        :value="form.recipe"
        tone="accent"
        :hint="`上限 ${form.limit} 条`"
      />
      <MetricTile
        label="状态"
        :value="response ? (degraded ? '已降级' : '正常') : '—'"
        :tone="response ? (degraded ? 'warn' : 'good') : 'muted'"
        :hint="degraded ? 'Embedding 不可用，已降级使用 BM25 与实体信号' : '向量通道正常'"
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
          已降级 · 向量召回通道不可用
        </div>
        <div class="text-[11px] text-ink-3 mt-0.5">
          Worker 的 Embedding 服务暂不可用，已自动降级到 BM25 与实体信号。结果仍可用，但排序精度受影响。
        </div>
      </div>
    </div>

    <div
      v-if="queryPlan"
      class="rounded-panel border border-shore-line/80 bg-shore-elev/30 px-4 py-3"
    >
      <div class="flex items-center justify-between gap-3 text-[11px] font-display">
        <span class="uppercase tracking-[0.2em] text-ink-4">Query Plan</span>
        <span class="text-ink-3">
          {{ queryPlan.source }}
          <span v-if="queryPlan.planner_degraded" class="text-sig-amber">· degraded</span>
        </span>
      </div>
      <div class="mt-2 text-[11px] text-ink-4">
        子查询 {{ queryPlan.subqueries.length }} 条
        <span v-if="queryPlan.requested_auto_plan"> · 请求了自动规划</span>
      </div>
      <ul v-if="queryPlan.subqueries.length" class="mt-2 space-y-1.5">
        <li
          v-for="(item, index) in queryPlan.subqueries"
          :key="`${index}:${item}`"
          class="text-[11.5px] text-ink-2"
        >
          <span class="font-mono text-ink-4 mr-1">#{{ index + 1 }}</span>{{ item }}
        </li>
      </ul>
      <div v-if="queryPlan.planner_error" class="mt-2 text-[11px] text-sig-amber">
        planner error: {{ queryPlan.planner_error }}
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
        <div class="flex items-center gap-3">
          <div v-if="agentState" class="text-[10.5px] text-ink-4 font-display tracking-tight">
            Agent <span class="text-ink-2">{{ agentState.agent_id }}</span>
            · 心情 <span class="text-ink-2">{{ agentState.mood }}</span>
          </div>
          <button
            v-if="memories.length"
            type="button"
            class="h-7 px-2.5 rounded-btn border border-shore-line bg-shore-card text-[11px] text-ink-2 hover:text-accent hover:border-accent/60 transition-colors flex items-center gap-1.5 font-display"
            title="在记忆图谱中对这组命中做脉冲定位"
            @click="pingAllInGraph"
          >
            <Target class="h-3.5 w-3.5" :stroke-width="1.75" />
            在图谱中高亮
          </button>
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
            在左侧输入查询并按 ⌘↵ 开始召回；结果会按综合分数倒序排序，并拆解为语义 / BM25 / 实体 / 连贯性四路信号。
          </div>
        </div>

        <!-- No hits -->
        <div
          v-else-if="!hitCount"
          class="flex flex-col items-center justify-center py-12 gap-2"
        >
          <div class="font-display text-[13.5px] text-ink-1">没有命中结果</div>
          <div class="text-[11px] text-ink-4 text-center max-w-md">
            尝试切换召回配方、放宽作用域、或打开“包含失效记忆”做时光回溯。
          </div>
        </div>

        <!-- Hits -->
        <div v-else class="flex flex-col gap-3">
          <HitCard
            v-for="(mem, idx) in memories"
            :key="mem.id"
            :memory="mem"
            :rank="idx + 1"
            :subqueries="plannedSubqueries"
          />
        </div>
      </div>
    </PCard>
  </div>
</template>
