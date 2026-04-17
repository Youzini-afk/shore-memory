<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
import { useAppStore } from '@/stores/app'
import { computed } from 'vue'

const app = useAppStore()
const statusLabel = computed(() => {
  if (app.isEventsOpen) return '事件流 · 已连接'
  if (app.eventsStatus === 'connecting') return '事件流 · 连接中'
  return '事件流 · 未连接'
})
</script>

<template>
  <div class="min-h-full">
    <PHero title="运维" subtitle="服务健康 · 任务队列 · 反思与重建">
      <template #actions>
        <span
          class="flex items-center gap-2 px-3 py-1.5 rounded-btn bg-shore-card border border-shore-line/80 text-[11px] text-ink-3"
        >
          <span
            class="shore-dot"
            :class="app.isEventsOpen ? 'bg-state-active' : 'bg-ink-5'"
          />
          {{ statusLabel }}
        </span>
      </template>
    </PHero>
    <div class="px-8 pb-10">
      <PCard edge>
        <PEmpty
          title="运维控制台即将接入"
          hint="下一个里程碑会实装关键指标 · 任务队列 · 维护操作按钮 · Metrics 小图与实时事件日志。"
          milestone="即将上线 · M5"
        />
      </PCard>
    </div>
  </div>
</template>
