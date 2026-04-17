<script setup lang="ts">
import { computed } from 'vue'
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()

const eventsStatusLabel = computed(() => {
  switch (app.eventsStatus) {
    case 'open':
      return '实时'
    case 'connecting':
      return '连接中'
    case 'error':
      return '错误'
    case 'lagged':
      return '积压'
    case 'disconnected':
    default:
      return '未连接'
  }
})

const healthStatusLabel = computed(() => {
  const status = app.health?.status
  if (!status) return '–'
  if (status === 'ok') return '正常'
  if (status === 'degraded') return '已降级'
  if (status === 'error') return '异常'
  return status
})

const authStatusLabel = computed(() => {
  switch (app.authStatus) {
    case 'checking':
      return '验证中'
    case 'ready':
      return '已解锁'
    case 'locked':
    default:
      return '已锁定'
  }
})
</script>

<template>
  <div class="min-h-full">
    <PHero title="设置" subtitle="API · 事件流 · 主题 · 快捷键" />
    <div class="px-8 pb-10 grid grid-cols-2 gap-5">
      <PCard edge>
        <div class="text-[12px] uppercase font-display tracking-wider text-ink-4 mb-3">
          环境
        </div>
        <div class="grid grid-cols-3 gap-y-2 text-[13px]">
          <div class="text-ink-4">API 地址</div>
          <div class="col-span-2 font-mono text-ink-1 truncate">
            {{ app.apiBase || '同源（由 axum 静态托管）' }}
          </div>
          <div class="text-ink-4">Agent</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.agentId }}</div>
          <div class="text-ink-4">事件流</div>
          <div class="col-span-2 font-display text-ink-1">{{ eventsStatusLabel }}</div>
          <div class="text-ink-4">服务健康</div>
          <div
            class="col-span-2 font-display"
            :class="app.isHealthy ? 'text-state-active' : 'text-ink-3'"
          >
            {{ healthStatusLabel }}
          </div>
          <div class="text-ink-4">Worker</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.health?.worker_available ? '可用' : '未知' }}
          </div>
          <div class="text-ink-4">待处理任务</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.health?.pending_tasks ?? 0 }}</div>
          <div class="text-ink-4">失败任务</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.health?.failed_tasks ?? 0 }}</div>
        </div>
      </PCard>
      <PCard edge>
        <div class="text-[12px] uppercase font-display tracking-wider text-ink-4 mb-3">
          鉴权
        </div>
        <div class="grid grid-cols-3 gap-y-2 text-[13px]">
          <div class="text-ink-4">是否启用</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.authRequired ? '是' : '否' }}
          </div>
          <div class="text-ink-4">状态</div>
          <div class="col-span-2 font-display text-ink-1">{{ authStatusLabel }}</div>
          <div class="text-ink-4">凭据来源</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.authSourceLabel }}</div>
          <div class="text-ink-4">已保存 Key</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.hasStoredApiKey ? '存在' : '无' }}
          </div>
          <div class="text-ink-4">最近错误</div>
          <div class="col-span-2 text-ink-2 min-h-[20px]">{{ app.authError ?? '–' }}</div>
        </div>

        <div class="mt-5 flex flex-wrap gap-2">
          <PButton variant="secondary" @click="app.retryAuth">重新验证</PButton>
          <PButton v-if="app.hasStoredApiKey" variant="ghost" @click="app.clearSavedApiKey">
            清除已保存 Key
          </PButton>
        </div>

        <div class="mt-4 text-[12px] text-ink-4 leading-6">
          若服务端启用了 <span class="font-mono text-ink-2">PMS_API_KEY</span>，控制台会在未通过验证时自动回退到解锁页。
        </div>
      </PCard>
    </div>
  </div>
</template>
