<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import PHero from '@/components/ui/PHero.vue'
import PBadge from '@/components/ui/PBadge.vue'
import StateMirror from '@/components/agent/StateMirror.vue'
import StateEditor from '@/components/agent/StateEditor.vue'
import StateTimeline from '@/components/agent/StateTimeline.vue'
import { useAgentStore } from '@/stores/agent'
import { useAppStore } from '@/stores/app'

const agentStore = useAgentStore()
const app = useAppStore()
const { remote } = storeToRefs(agentStore)

onMounted(() => {
  agentStore.bindEvents()
  if (!remote.value) {
    void agentStore.load()
  }
})
</script>

<template>
  <div class="min-h-full">
    <PHero title="Agent 状态" subtitle="心情 · 氛围 · 心绪三元组 · 实时镜像">
      <template #actions>
        <PBadge tone="accent" size="sm" dot>Agent · {{ app.agentId }}</PBadge>
        <span
          class="flex items-center gap-2 px-3 py-1.5 rounded-btn bg-shore-card border border-shore-line/80 text-[11px] text-ink-3"
        >
          <span
            class="shore-dot"
            :class="app.isEventsOpen ? 'bg-state-active' : 'bg-ink-5'"
          />
          {{ app.isEventsOpen ? '事件流 · 已连接' : '事件流 · 未连接' }}
        </span>
      </template>
    </PHero>

    <div class="px-8 pb-10 grid grid-cols-12 gap-6">
      <div class="col-span-12 xl:col-span-7 flex flex-col gap-6 min-w-0">
        <StateMirror />
        <StateTimeline />
      </div>
      <div class="col-span-12 xl:col-span-5 flex flex-col gap-6 min-w-0">
        <StateEditor />
      </div>
    </div>
  </div>
</template>
