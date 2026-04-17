<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { KeyRound, RefreshCw, ShieldCheck, ShieldAlert, Server } from 'lucide-vue-next'
import PCard from '@/components/ui/PCard.vue'
import PButton from '@/components/ui/PButton.vue'
import PInput from '@/components/ui/PInput.vue'
import PSwitch from '@/components/ui/PSwitch.vue'
import { useAppStore } from '@/stores/app'

const app = useAppStore()

const apiKeyInput = ref('')
const rememberKey = ref(true)
const submitError = ref<string | null>(null)

const isChecking = computed(() => app.authStatus === 'checking')
const apiOrigin = computed(() => {
  if (app.apiBase) return app.apiBase
  if (typeof window !== 'undefined') return window.location.origin
  return '同源'
})
const cardTitle = computed(() => {
  if (isChecking.value) return '正在验证访问权限'
  return '输入 API Key 解锁控制台'
})
const cardSubtitle = computed(() => {
  if (isChecking.value) return '正在探测 Shore 服务状态并校验当前访问凭据。'
  return '该 Shore 服务已启用 API Key 保护。解锁后，HTTP 请求与事件流都会自动带上当前凭据。'
})
const sourceHint = computed(() => {
  if (!app.hasAnyApiKey) return '当前未检测到任何可用 API Key。'
  return `当前凭据来源：${app.authSourceLabel}`
})

watch(
  () => app.apiKeySource,
  (source) => {
    if (source === 'session') rememberKey.value = false
    if (source === 'local') rememberKey.value = true
  },
  { immediate: true }
)

watch(
  () => app.authError,
  (message) => {
    if (!isChecking.value) {
      submitError.value = message
    }
  },
  { immediate: true }
)

async function submitUnlock() {
  submitError.value = null
  try {
    await app.unlock(apiKeyInput.value, rememberKey.value)
    apiKeyInput.value = ''
  } catch (err) {
    submitError.value = (err as Error).message || '解锁失败，请稍后重试。'
  }
}

async function retry() {
  submitError.value = null
  const success = await app.retryAuth()
  if (!success) {
    submitError.value = app.authError
  }
}

function clearSavedKey() {
  submitError.value = null
  app.clearSavedApiKey()
}
</script>

<template>
  <div class="min-h-screen bg-shore-bg text-ink-1 relative overflow-hidden">
    <div
      class="pointer-events-none absolute -top-24 left-1/2 -translate-x-1/2 h-[420px] w-[760px] blur-[120px] opacity-35"
      style="background: radial-gradient(closest-side, rgba(124,92,255,0.55), transparent 72%)"
    />

    <div class="relative min-h-screen flex items-center justify-center px-6 py-10">
      <div class="w-full max-w-5xl grid gap-6 lg:grid-cols-[1.08fr_0.92fr]">
        <PCard edge>
          <div class="flex items-start gap-4">
            <div
              class="h-12 w-12 shrink-0 rounded-[14px] bg-gradient-to-br from-accent-hi to-accent-lo shadow-accent flex items-center justify-center"
            >
              <ShieldCheck class="h-6 w-6 text-white" :stroke-width="1.9" />
            </div>
            <div class="min-w-0">
              <div class="text-[12px] uppercase tracking-[0.2em] text-ink-4 font-display">Shore Memory</div>
              <h1 class="mt-2 text-[28px] leading-tight tracking-tight font-display">{{ cardTitle }}</h1>
              <p class="mt-2 text-[14px] text-ink-3 max-w-[52ch]">
                {{ cardSubtitle }}
              </p>
            </div>
          </div>

          <div class="mt-8 grid gap-4 sm:grid-cols-3">
            <div class="rounded-card border border-shore-line/80 bg-[#0F1018]/85 p-4">
              <div class="flex items-center gap-2 text-[11px] uppercase tracking-wider text-ink-4 font-display">
                <Server class="h-3.5 w-3.5" :stroke-width="1.75" />
                服务状态
              </div>
              <div class="mt-3 text-[14px] font-display text-ink-1">{{ app.health?.status ?? '未知' }}</div>
              <div class="mt-1 text-[12px] text-ink-4">
                {{ app.health?.worker_available ? 'Worker 可用' : 'Worker 状态未知' }}
              </div>
            </div>

            <div class="rounded-card border border-shore-line/80 bg-[#0F1018]/85 p-4">
              <div class="flex items-center gap-2 text-[11px] uppercase tracking-wider text-ink-4 font-display">
                <ShieldAlert class="h-3.5 w-3.5" :stroke-width="1.75" />
                访问控制
              </div>
              <div class="mt-3 text-[14px] font-display text-ink-1">
                {{ app.authRequired ? '需要 API Key' : '公开访问' }}
              </div>
              <div class="mt-1 text-[12px] text-ink-4">{{ sourceHint }}</div>
            </div>

            <div class="rounded-card border border-shore-line/80 bg-[#0F1018]/85 p-4">
              <div class="flex items-center gap-2 text-[11px] uppercase tracking-wider text-ink-4 font-display">
                <RefreshCw class="h-3.5 w-3.5" :stroke-width="1.75" />
                后台任务
              </div>
              <div class="mt-3 text-[14px] font-display text-ink-1">
                {{ app.health?.pending_tasks ?? 0 }} pending
              </div>
              <div class="mt-1 text-[12px] text-ink-4">
                {{ app.health?.failed_tasks ?? 0 }} failed
              </div>
            </div>
          </div>

          <div class="mt-8 rounded-card border border-shore-line/80 bg-shore-card/70 p-5">
            <div class="flex items-center gap-2 text-[12px] uppercase tracking-wider text-ink-4 font-display">
              <KeyRound class="h-4 w-4" :stroke-width="1.75" />
              API Key 解锁
            </div>

            <div v-if="isChecking" class="mt-5 flex items-center gap-3 text-[13px] text-ink-3">
              <span class="inline-block h-4 w-4 rounded-full border border-accent border-t-transparent animate-spin" />
              正在校验凭据与服务状态，请稍候。
            </div>

            <form v-else class="mt-5 space-y-4" @submit.prevent="submitUnlock">
              <div>
                <div class="mb-1.5 text-[11px] uppercase tracking-wider text-ink-4 font-display">
                  API Key
                </div>
                <PInput
                  v-model="apiKeyInput"
                  type="password"
                  placeholder="输入 PMS_API_KEY 对应的值"
                  @enter="submitUnlock"
                />
              </div>

              <div class="flex items-center justify-between gap-3 rounded-btn border border-shore-line/80 bg-[#0F1018]/70 px-3.5 py-3">
                <div>
                  <div class="text-[12px] font-display text-ink-1">记住 API Key</div>
                  <div class="text-[11px] text-ink-4">
                    关闭时仅保存到当前浏览器会话，开启后会写入本地存储。
                  </div>
                </div>
                <PSwitch v-model="rememberKey" />
              </div>

              <div v-if="submitError" class="rounded-btn border border-state-invalidated/35 bg-state-invalidated/10 px-3.5 py-3 text-[12px] text-state-invalidated">
                {{ submitError }}
              </div>

              <div class="flex flex-wrap items-center gap-2.5">
                <PButton variant="primary" :loading="app.unlocking" type="submit">
                  解锁控制台
                </PButton>
                <PButton variant="secondary" :loading="isChecking" @click="retry">
                  重新探测
                </PButton>
                <PButton v-if="app.hasStoredApiKey" variant="ghost" @click="clearSavedKey">
                  清除已保存的 Key
                </PButton>
              </div>
            </form>
          </div>
        </PCard>

        <PCard compact>
          <div class="text-[12px] uppercase tracking-[0.18em] text-ink-4 font-display">连接信息</div>
          <div class="mt-4 space-y-3 text-[13px]">
            <div class="flex items-start justify-between gap-4">
              <span class="text-ink-4">API Base</span>
              <span class="font-mono text-right text-ink-1 break-all">
                {{ apiOrigin }}
              </span>
            </div>
            <div class="flex items-start justify-between gap-4">
              <span class="text-ink-4">事件流</span>
              <span class="font-display text-right text-ink-1">{{ app.eventsStatus }}</span>
            </div>
            <div class="flex items-start justify-between gap-4">
              <span class="text-ink-4">Agent</span>
              <span class="font-display text-right text-ink-1">{{ app.agentId }}</span>
            </div>
            <div class="flex items-start justify-between gap-4">
              <span class="text-ink-4">凭据来源</span>
              <span class="font-display text-right text-ink-1">{{ app.authSourceLabel }}</span>
            </div>
          </div>

          <div class="mt-6 rounded-card border border-shore-line/80 bg-[#0F1018]/70 p-4 text-[12px] text-ink-3 leading-6">
            页面静态资源可以公开访问，但真正的敏感操作都在 <span class="font-mono text-ink-1">/v1/*</span>
            API 下。解锁成功后，控制台会自动把当前 API Key 用于 HTTP 请求和 WebSocket 事件订阅。
          </div>
        </PCard>
      </div>
    </div>
  </div>
</template>
