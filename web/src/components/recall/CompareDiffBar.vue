<script setup lang="ts">
/**
 * A/B Compare 顶部 diff summary：命中重合度（Jaccard）、A only / B only /
 * 交集计数、rank drift。给用户一眼看出两组 recipe 在本次 query 下的差异。
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { GitCompare, CircleDot, Circle, Minus, Sigma as SigmaIcon, Target } from 'lucide-vue-next'
import { useRecallStore } from '@/stores/recall'
import { useGraphStore } from '@/stores/graph'

const store = useRecallStore()
const router = useRouter()
const graph = useGraphStore()
const { compareDiff, variantA, variantB } = storeToRefs(store)

type PingGroup = 'aOnly' | 'shared' | 'bOnly' | 'union'

const hasData = computed(
  () => !!variantA.value.response && !!variantB.value.response
)

const jaccardDisplay = computed(() =>
  hasData.value ? (compareDiff.value.jaccard * 100).toFixed(0) + '%' : '—'
)

const jaccardTone = computed<'accent' | 'amber' | 'muted' | 'invalid'>(() => {
  if (!hasData.value) return 'muted'
  const j = compareDiff.value.jaccard
  if (j >= 0.8) return 'accent'
  if (j >= 0.4) return 'amber'
  return 'invalid'
})

function idsFor(group: PingGroup): number[] {
  if (!hasData.value) return []
  if (group === 'aOnly') return compareDiff.value.aOnly
  if (group === 'shared') return compareDiff.value.intersection
  if (group === 'bOnly') return compareDiff.value.bOnly
  return compareDiff.value.union
}

function canPing(group: PingGroup): boolean {
  return idsFor(group).length > 0
}

function pingGroup(group: PingGroup): void {
  const ids = idsFor(group)
  if (!ids.length) return
  graph.pingMemories(ids)
  void router.push({ name: 'graph' })
}
</script>

<template>
  <div
    class="rounded-panel border border-shore-line/80 bg-shore-surface/85 px-4 py-3 flex flex-wrap items-center gap-x-5 gap-y-3"
  >
    <div class="flex items-center gap-2">
      <div
        class="h-7 w-7 rounded-btn bg-accent/10 border border-accent/20 flex items-center justify-center text-accent"
      >
        <GitCompare class="h-3.5 w-3.5" :stroke-width="1.75" />
      </div>
      <div class="min-w-0">
        <div class="text-[10px] uppercase tracking-[0.22em] font-display text-ink-5">
          重合度 Jaccard
        </div>
        <div
          class="text-[16px] font-display tabular"
          :class="{
            'text-accent': jaccardTone === 'accent',
            'text-sig-amber': jaccardTone === 'amber',
            'text-state-invalidated': jaccardTone === 'invalid',
            'text-ink-4': jaccardTone === 'muted'
          }"
        >
          {{ jaccardDisplay }}
        </div>
      </div>
    </div>

    <div class="h-8 w-px bg-shore-line/80" />

    <div class="flex items-center gap-3">
      <div class="flex items-center gap-1.5">
        <span
          class="h-2.5 w-2.5 rounded-full"
          style="background: #7C5CFF; box-shadow: 0 0 8px #7C5CFF88"
        />
        <div>
          <div class="text-[10px] uppercase tracking-[0.2em] font-display text-ink-5">仅 A</div>
          <div class="text-[13px] font-display tabular text-ink-1">
            {{ hasData ? compareDiff.aOnly.length : '—' }}
          </div>
        </div>
      </div>

      <CircleDot class="h-3 w-3 text-ink-5" :stroke-width="1.75" />

      <div class="flex items-center gap-1.5">
        <span
          class="h-2.5 w-2.5 rounded-full"
          style="background: #22C55E; box-shadow: 0 0 8px #22C55E88"
        />
        <div>
          <div class="text-[10px] uppercase tracking-[0.2em] font-display text-ink-5">共同</div>
          <div class="text-[13px] font-display tabular text-ink-1">
            {{ hasData ? compareDiff.intersection.length : '—' }}
          </div>
        </div>
      </div>

      <Circle class="h-3 w-3 text-ink-5" :stroke-width="1.75" />

      <div class="flex items-center gap-1.5">
        <span
          class="h-2.5 w-2.5 rounded-full"
          style="background: #38BDF8; box-shadow: 0 0 8px #38BDF888"
        />
        <div>
          <div class="text-[10px] uppercase tracking-[0.2em] font-display text-ink-5">仅 B</div>
          <div class="text-[13px] font-display tabular text-ink-1">
            {{ hasData ? compareDiff.bOnly.length : '—' }}
          </div>
        </div>
      </div>
    </div>

    <div class="h-8 w-px bg-shore-line/80" />

    <div class="flex items-center gap-2">
      <SigmaIcon class="h-3.5 w-3.5 text-ink-4" :stroke-width="1.75" />
      <div>
        <div class="text-[10px] uppercase tracking-[0.22em] font-display text-ink-5">
          排名回调
        </div>
        <div class="text-[12.5px] font-display tabular text-ink-1">
          <template v-if="hasData && compareDiff.rankPairs.length">
            均 {{ compareDiff.avgRankDrift.toFixed(1) }} ·
            最大 {{ compareDiff.maxRankDrift }}
          </template>
          <template v-else>—</template>
        </div>
      </div>
    </div>

    <div class="h-8 w-px bg-shore-line/80" />

    <div class="flex items-center gap-1.5">
      <button
        type="button"
        class="h-7 px-2 rounded-btn border border-shore-line bg-shore-card text-[10.5px] text-ink-2 font-display transition-colors"
        :class="canPing('aOnly') ? 'hover:text-accent hover:border-accent/60' : 'opacity-45 cursor-not-allowed'"
        :disabled="!canPing('aOnly')"
        title="在图谱中高亮仅 A 独有的命中"
        @click="pingGroup('aOnly')"
      >
        高亮仅 A
      </button>
      <button
        type="button"
        class="h-7 px-2 rounded-btn border border-shore-line bg-shore-card text-[10.5px] text-ink-2 font-display transition-colors"
        :class="canPing('shared') ? 'hover:text-accent hover:border-accent/60' : 'opacity-45 cursor-not-allowed'"
        :disabled="!canPing('shared')"
        title="在图谱中高亮共同命中"
        @click="pingGroup('shared')"
      >
        高亮共同
      </button>
      <button
        type="button"
        class="h-7 px-2 rounded-btn border border-shore-line bg-shore-card text-[10.5px] text-ink-2 font-display transition-colors"
        :class="canPing('bOnly') ? 'hover:text-accent hover:border-accent/60' : 'opacity-45 cursor-not-allowed'"
        :disabled="!canPing('bOnly')"
        title="在图谱中高亮仅 B 独有的命中"
        @click="pingGroup('bOnly')"
      >
        高亮仅 B
      </button>
      <button
        type="button"
        class="h-7 px-2.5 rounded-btn border border-shore-line bg-shore-card text-[10.5px] text-ink-2 font-display transition-colors inline-flex items-center gap-1"
        :class="canPing('union') ? 'hover:text-accent hover:border-accent/60' : 'opacity-45 cursor-not-allowed'"
        :disabled="!canPing('union')"
        title="在图谱中高亮全部命中"
        @click="pingGroup('union')"
      >
        <Target class="h-3.5 w-3.5" :stroke-width="1.75" />
        高亮全部
      </button>
    </div>

    <div class="flex-1" />

    <div class="flex flex-col items-end text-right">
      <div class="text-[10px] uppercase tracking-[0.2em] font-display text-ink-5">
        延迟
      </div>
      <div class="text-[11.5px] font-display tabular text-ink-2 flex items-center gap-1.5">
        <span class="inline-flex items-center gap-1">
          <span class="h-1.5 w-1.5 rounded-full" style="background: #7C5CFF" />
          <span>A</span>
          <span class="text-ink-1">{{ variantA.latencyMs ?? '—' }}</span>
          <span v-if="variantA.latencyMs !== null" class="text-ink-5">ms</span>
        </span>
        <Minus class="h-2.5 w-2.5 text-ink-5" :stroke-width="1.75" />
        <span class="inline-flex items-center gap-1">
          <span class="h-1.5 w-1.5 rounded-full" style="background: #38BDF8" />
          <span>B</span>
          <span class="text-ink-1">{{ variantB.latencyMs ?? '—' }}</span>
          <span v-if="variantB.latencyMs !== null" class="text-ink-5">ms</span>
        </span>
      </div>
    </div>
  </div>
</template>
