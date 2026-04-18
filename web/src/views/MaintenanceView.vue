<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import PHero from '@/components/ui/PHero.vue'
import PBadge from '@/components/ui/PBadge.vue'
import KpiTile from '@/components/maintenance/KpiTile.vue'
import SyncSummaryPanel from '@/components/maintenance/SyncSummaryPanel.vue'
import MaintenanceActions from '@/components/maintenance/MaintenanceActions.vue'
import EventFeed from '@/components/maintenance/EventFeed.vue'
import { useAppStore } from '@/stores/app'
import { useMaintenanceStore } from '@/stores/maintenance'

const app = useAppStore()
const maintenance = useMaintenanceStore()
const { health } = storeToRefs(app)
const { summary, summaryLoading } = storeToRefs(maintenance)

const statusLabel = computed(() => {
  if (app.isEventsOpen) return '事件流 · 已连接'
  if (app.eventsStatus === 'connecting') return '事件流 · 连接中'
  return '事件流 · 未连接'
})

const serviceKpi = computed(() => {
  if (!health.value) return { value: '未知', tone: 'warn' as const, hint: '无法连接服务' }
  const value = health.value.status ?? '—'
  return {
    value,
    tone: value === 'ok' ? ('ok' as const) : ('warn' as const),
    hint: health.value.api_auth_required ? 'API Key 鉴权已开启' : 'API Key 鉴权未启用'
  }
})

const workerKpi = computed(() => {
  if (!health.value) return { value: '未知', tone: 'warn' as const, hint: '等待首次健康检查' }
  const ok = !!health.value.worker_available
  return {
    value: ok ? '可达' : '不可达',
    tone: ok ? ('ok' as const) : ('error' as const),
    hint: ok ? 'Worker HTTP /health OK' : '检查 worker 进程'
  }
})

const pendingKpi = computed(() => {
  const count = summary.value?.pending_tasks ?? health.value?.pending_tasks ?? 0
  const oldest = summary.value?.oldest_pending_created_at
  const hint = oldest
    ? `最早排队于 ${new Date(oldest).toLocaleString()}`
    : '队列为空'
  const tone: 'accent' | 'warn' | 'ok' = count > 50 ? 'warn' : count > 0 ? 'accent' : 'ok'
  return { value: count, tone, hint }
})

const failedKpi = computed(() => {
  const count = summary.value?.failed_tasks ?? health.value?.failed_tasks ?? 0
  const hint = summary.value?.latest_error
    ? summary.value.latest_error.split('\n')[0].slice(0, 80)
    : count > 0
      ? '存在失败任务，可一键重试'
      : '没有失败任务'
  const tone: 'error' | 'warn' | 'ok' = count > 0 ? 'error' : 'ok'
  return { value: count, tone, hint }
})

onMounted(() => {
  maintenance.bindEvents()
  maintenance.startPolling()
})

onBeforeUnmount(() => {
  maintenance.stopPolling()
})
</script>

<template>
  <div class="min-h-full flex flex-col">
    <PHero title="运维" subtitle="服务健康 · 任务队列 · 反思与重建 · 实时事件">
      <template #actions>
        <PBadge tone="accent" size="sm" dot>Agent · {{ app.agentId }}</PBadge>
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

    <div class="px-8 pb-10 flex flex-col gap-6">
      <!-- KPI row -->
      <div class="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <KpiTile
          label="服务"
          :value="serviceKpi.value"
          :tone="serviceKpi.tone"
          :hint="serviceKpi.hint"
          icon="●"
          :loading="!health && summaryLoading"
        />
        <KpiTile
          label="Worker"
          :value="workerKpi.value"
          :tone="workerKpi.tone"
          :hint="workerKpi.hint"
          icon="◉"
        />
        <KpiTile
          label="待处理任务"
          :value="pendingKpi.value"
          :tone="pendingKpi.tone"
          :hint="pendingKpi.hint"
          icon="⧗"
        />
        <KpiTile
          label="失败任务"
          :value="failedKpi.value"
          :tone="failedKpi.tone"
          :hint="failedKpi.hint"
          icon="⚠"
        />
      </div>

      <!-- 三栏 -->
      <div class="grid grid-cols-12 gap-6">
        <div class="col-span-12 xl:col-span-4 min-w-0">
          <SyncSummaryPanel />
        </div>
        <div class="col-span-12 xl:col-span-4 min-w-0">
          <MaintenanceActions />
        </div>
        <div class="col-span-12 xl:col-span-4 min-w-0 flex flex-col min-h-[480px]">
          <EventFeed />
        </div>
      </div>
    </div>
  </div>
</template>
