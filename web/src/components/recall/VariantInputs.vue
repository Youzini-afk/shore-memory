<script setup lang="ts">
/**
 * A/B Compare 模式下，单个变体的参数卡片：recipe / scope_hint /
 * include_invalid / include_state / debug，以及单独再跑这个 variant 的
 * 按钮。共享字段（query、uids、limit）由 SharedQueryInputs 提供。
 */
import { computed } from 'vue'
import { Zap, RefreshCw } from 'lucide-vue-next'
import PCard from '@/components/ui/PCard.vue'
import PSegment from '@/components/ui/PSegment.vue'
import PSwitch from '@/components/ui/PSwitch.vue'
import type {
  MemoryScopeHint,
  RecallRecipeId,
  RecallResponse
} from '@/api/types'
import type { RecallVariantState } from '@/stores/recall'
import { useRecallStore } from '@/stores/recall'

interface Props {
  variant: RecallVariantState
  accent: 'accent-a' | 'accent-b'
}
const props = defineProps<Props>()

const store = useRecallStore()

const recipeOptions: { label: string; value: RecallRecipeId }[] = [
  { value: 'fast', label: '极速' },
  { value: 'hybrid', label: '混合' },
  { value: 'entity_heavy', label: '实体' },
  { value: 'contiguous', label: '连贯' }
]

const scopeOptions: { label: string; value: MemoryScopeHint }[] = [
  { value: 'auto', label: '自动' },
  { value: 'private', label: '私有' },
  { value: 'group', label: '群组' },
  { value: 'shared', label: '共享' },
  { value: 'system', label: '系统' }
]

const hits = computed<number>(() => props.variant.response?.memory_context?.length ?? 0)
const latency = computed<number | null>(() => props.variant.latencyMs)
const degraded = computed<boolean>(() => !!props.variant.response?.degraded)

const accentColor = computed(() =>
  props.accent === 'accent-a' ? '#7C5CFF' : '#38BDF8'
)

async function runOnly() {
  await store.runVariant(props.variant)
}
</script>

<template>
  <PCard edge compact>
    <!-- Header -->
    <div class="flex items-center gap-2 mb-3">
      <span
        class="h-6 px-2 inline-flex items-center justify-center rounded-btn text-[11px] font-display tabular text-white"
        :style="{ background: accentColor }"
      >
        {{ variant.config.label }}
      </span>
      <span class="text-[11px] uppercase tracking-[0.2em] font-display text-ink-4">
        {{ variant.config.recipe }}
      </span>
      <span class="ml-auto flex items-center gap-2 text-[10.5px] font-display text-ink-4">
        <span v-if="variant.loading" class="flex items-center gap-1 text-ink-2">
          <span class="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
          正在跑
        </span>
        <template v-else-if="variant.response">
          <span class="tabular text-ink-2">{{ hits }} 条</span>
          <span v-if="latency !== null" class="tabular text-ink-3">·{{ latency }}ms</span>
          <span v-if="degraded" class="text-sig-amber">· 已降级</span>
        </template>
        <span v-else class="text-ink-5">—</span>
      </span>
    </div>

    <!-- Recipe -->
    <div class="mb-3">
      <div class="mb-1.5 text-[10px] font-display uppercase tracking-wider text-ink-4">
        召回配方
      </div>
      <PSegment v-model="variant.config.recipe" :options="recipeOptions" size="sm" block />
    </div>

    <!-- Scope -->
    <div class="mb-3">
      <div class="mb-1.5 text-[10px] font-display uppercase tracking-wider text-ink-4">
        作用域提示
      </div>
      <PSegment v-model="variant.config.scope_hint" :options="scopeOptions" size="sm" block />
    </div>

    <!-- Switches (tight layout) -->
    <div class="grid grid-cols-2 gap-2.5 mb-3">
      <label class="flex items-center gap-2 cursor-pointer">
        <PSwitch v-model="variant.config.include_invalid" />
        <span class="text-[11px] text-ink-2 font-display">含失效</span>
      </label>
      <label class="flex items-center gap-2 cursor-pointer">
        <PSwitch v-model="variant.config.include_state" />
        <span class="text-[11px] text-ink-2 font-display">含状态</span>
      </label>
      <label class="flex items-center gap-2 cursor-pointer">
        <PSwitch v-model="variant.config.debug" />
        <span class="text-[11px] text-ink-2 font-display">调试</span>
      </label>
    </div>

    <!-- Error row -->
    <div
      v-if="variant.error"
      class="mb-3 rounded-btn bg-state-invalidated/10 border border-state-invalidated/30 px-2.5 py-1.5 text-[11px] text-state-invalidated"
    >
      {{ variant.error }}
    </div>

    <!-- Re-run this variant only -->
    <button
      type="button"
      class="w-full h-8 rounded-btn border border-shore-line bg-shore-card text-[11.5px] text-ink-2 hover:text-ink-0 hover:border-accent/60 transition-colors flex items-center justify-center gap-2 font-display"
      :disabled="variant.loading"
      @click="runOnly"
    >
      <RefreshCw class="h-3.5 w-3.5" :stroke-width="1.75" :class="variant.loading ? 'animate-spin' : ''" />
      仅跑 {{ variant.config.label }}
      <span class="inline-flex items-center text-accent ml-1">
        <Zap class="h-3 w-3" :stroke-width="1.75" />
      </span>
    </button>
  </PCard>
</template>
