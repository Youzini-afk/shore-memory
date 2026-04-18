<script setup lang="ts">
import { storeToRefs } from 'pinia'
import PCard from '@/components/ui/PCard.vue'
import ActionCard from './ActionCard.vue'
import { useMaintenanceStore } from '@/stores/maintenance'
import { useAppStore } from '@/stores/app'

const store = useMaintenanceStore()
const app = useAppStore()
const { actions } = storeToRefs(store)

async function runSafe(fn: () => Promise<unknown>) {
  try {
    await fn()
  } catch {
    // store 已经把 error 存起来
  }
}
</script>

<template>
  <PCard edge class="flex flex-col gap-3 h-full">
    <div class="flex items-center justify-between gap-3">
      <div>
        <div class="font-display text-[14px] text-ink-1">维护动作</div>
        <div class="mt-0.5 text-[11.5px] text-ink-4">
          当前 Agent: <span class="text-ink-2">{{ app.agentId }}</span>
        </div>
      </div>
    </div>

    <ActionCard
      title="重试失败的评分任务"
      description="把该 Agent 所有失败的 score_turn 任务重新排入队列，不会触发新的 LLM 计算。"
      tag="同步 · 安全"
      tag-tone="ink"
      button-label="立即重试"
      button-variant="secondary"
      :run="actions.scorer_retry"
      @trigger="runSafe(store.retryScorerAction)"
    />

    <ActionCard
      title="触发反思任务"
      description="手动触发一次 ReflectionRun，会消耗 LLM 额度。完成后会回写 Agent 状态。"
      tag="异步 · 耗 LLM"
      tag-tone="amber"
      button-label="排入反思"
      button-variant="secondary"
      :run="actions.reflection_run"
      @trigger="runSafe(store.runReflectionAction)"
    />

    <ActionCard
      title="重建 TriviumDB 索引"
      description="重新拉所有记忆重写向量 + BM25 索引。耗时数分钟，期间召回会短暂降级。"
      tag="异步 · 重活"
      tag-tone="invalidated"
      button-label="重建索引"
      button-variant="danger"
      :require-confirm="true"
      :run="actions.trivium_rebuild"
      @trigger="runSafe(store.rebuildTriviumAction)"
    />
  </PCard>
</template>
