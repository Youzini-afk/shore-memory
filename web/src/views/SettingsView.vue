<script setup lang="ts">
import PHero from '@/components/ui/PHero.vue'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
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
          <div class="text-ink-4">Worker</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.health?.worker_available ? 'available' : 'unknown' }}
          </div>
          <div class="text-ink-4">Pending Tasks</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.health?.pending_tasks ?? 0 }}</div>
          <div class="text-ink-4">Failed Tasks</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.health?.failed_tasks ?? 0 }}</div>
        </div>
      </PCard>
      <PCard edge>
        <div class="text-[12px] uppercase font-display tracking-wider text-ink-4 mb-3">
          鉴权
        </div>
        <div class="grid grid-cols-3 gap-y-2 text-[13px]">
          <div class="text-ink-4">Required</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.authRequired ? 'yes' : 'no' }}
          </div>
          <div class="text-ink-4">Status</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.authStatus }}</div>
          <div class="text-ink-4">Source</div>
          <div class="col-span-2 font-display text-ink-1">{{ app.authSourceLabel }}</div>
          <div class="text-ink-4">Stored Key</div>
          <div class="col-span-2 font-display text-ink-1">
            {{ app.hasStoredApiKey ? 'present' : 'none' }}
          </div>
          <div class="text-ink-4">Last Error</div>
          <div class="col-span-2 text-ink-2 min-h-[20px]">{{ app.authError ?? '–' }}</div>
        </div>

        <div class="mt-5 flex flex-wrap gap-2">
          <PButton variant="secondary" @click="app.retryAuth">重新验证</PButton>
          <PButton v-if="app.hasStoredApiKey" variant="ghost" @click="app.clearSavedApiKey">
            清除已保存 Key
          </PButton>
        </div>

        <div class="mt-4 text-[12px] text-ink-4 leading-6">
          若服务端启用了 <span class="font-mono text-ink-2">PMS_API_KEY</span>，控制台会在未通过验证时自动回到解锁页。
        </div>
      </PCard>
    </div>
  </div>
</template>
