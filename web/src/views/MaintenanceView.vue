<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
import { useAppStore } from '@/stores/app'
import { computed } from 'vue'

const app = useAppStore()
const statusLabel = computed(() => {
  if (app.isEventsOpen) return 'events stream · 已连接'
  if (app.eventsStatus === 'connecting') return 'events stream · 连接中'
  return 'events stream · 未连接'
})
</script>

<template>
  <div class="min-h-full">
    <PHero title="Maintenance" subtitle="服务健康 · 任务队列 · 反思与重建">
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
          title="运维控制台待接入"
          hint="下一个里程碑 M5 会实装：KPI · 任务队列 · 维护操作按钮 · Metrics 小图 · Events live log。"
          milestone="Next · M5"
        />
      </PCard>
    </div>
  </div>
</template>
