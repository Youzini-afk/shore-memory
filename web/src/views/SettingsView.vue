<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PEmpty from '@/components/ui/PEmpty.vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()
</script>

<template>
  <div class="min-h-full">
    <PHero title="Settings" subtitle="API · 事件流 · 主题 · 快捷键" />
    <div class="px-8 pb-10 grid grid-cols-2 gap-5">
      <PCard edge>
        <div class="text-[12px] uppercase font-display tracking-wider text-ink-4 mb-3">
          环境
        </div>
        <div class="grid grid-cols-3 gap-y-2 text-[13px]">
          <div class="text-ink-4">API Base</div>
          <div class="col-span-2 font-mono text-ink-1 truncate">
            {{ app.apiBase || '同源 (axum 静态托管)' }}
          </div>
          <div class="text-ink-4">Agent</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.agentId }}</div>
          <div class="text-ink-4">Events</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.eventsStatus }}</div>
          <div class="text-ink-4">Health</div>
          <div
            class="col-span-2 font-display"
            :class="app.isHealthy ? 'text-state-active' : 'text-ink-3'"
          >
            {{ app.health?.status ?? '–' }}
          </div>
        </div>
      </PCard>
      <PCard edge>
        <PEmpty
          title="设置项待接入"
          hint="后续将提供 API base 重写、超时调参、主题切换、快捷键查看。"
          milestone="Polish · M6"
        />
      </PCard>
    </div>
  </div>
</template>
