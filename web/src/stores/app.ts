import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, onUnauthorized, ShoreApiError } from '@/api/http'
import type { HealthResponse, SyncSummaryResponse } from '@/api/types'
import { getEventsClient, type EventsStatus } from '@/api/events'
import {
  clearStoredApiKey,
  getApiKey,
  getApiKeyState,
  setStoredApiKey,
  subscribeApiKey,
  type ApiKeySource
} from '@/api/runtimeAuth'

/**
 * 全局应用状态：
 * - 当前 agent（默认 shore）
 * - 服务健康信息
 * - WS 连接状态 + 最后事件时间
 */
export const useAppStore = defineStore('app', () => {
  const agentId = ref<string>(localStorage.getItem('shore:agent') ?? 'shore')
  const apiBase = ref<string>(import.meta.env.VITE_SHORE_API || '')
  const health = ref<HealthResponse | null>(null)
  const healthError = ref<string | null>(null)
  const authStatus = ref<'checking' | 'ready' | 'locked'>('checking')
  const authRequired = ref(false)
  const authError = ref<string | null>(null)
  const unlocking = ref(false)
  const apiKeySource = ref<ApiKeySource>(getApiKeyState().source)
  const eventsStatus = ref<EventsStatus>('disconnected')
  const lastEventAt = ref<number | null>(null)

  let healthTimer: number | null = null
  let bootstrapped = false
  let detachEventsStatus: (() => void) | null = null
  let detachEventsListener: (() => void) | null = null
  let detachUnauthorized: (() => void) | null = null
  let detachApiKeyListener: (() => void) | null = null

  const isHealthy = computed(() => !!health.value && health.value.status === 'ok')
  const isEventsOpen = computed(() => eventsStatus.value === 'open' || eventsStatus.value === 'lagged')
  const needsUnlock = computed(() => authRequired.value && authStatus.value !== 'ready')
  const canRenderConsole = computed(() => authStatus.value === 'ready')
  const hasAnyApiKey = computed(() => apiKeySource.value !== 'none')
  const hasStoredApiKey = computed(() => apiKeySource.value === 'session' || apiKeySource.value === 'local')
  const authSourceLabel = computed(() => {
    switch (apiKeySource.value) {
      case 'session':
        return '当前会话'
      case 'local':
        return '本地记住'
      case 'window':
        return '页面注入'
      case 'env':
        return '构建环境'
      default:
        return '未提供'
    }
  })

  function setAgent(next: string) {
    agentId.value = next
    localStorage.setItem('shore:agent', next)
  }

  function syncApiKeyState() {
    apiKeySource.value = getApiKeyState().source
  }

  function resolveAuthError(err: unknown): string {
    if (err instanceof ShoreApiError && (err.status === 401 || err.status === 403)) {
      return 'API Key 无效或已失效，请重新输入后解锁。'
    }
    if (err instanceof ShoreApiError) return err.message
    return (err as Error).message || '鉴权校验失败，请稍后重试。'
  }

  function connectEvents() {
    getEventsClient().connect()
  }

  function lockConsole(message: string | null) {
    authStatus.value = 'locked'
    authError.value = message
    getEventsClient().disconnect()
  }

  async function verifyProtectedAccess() {
    await api.get<SyncSummaryResponse>('/v1/maintenance/sync-summary', { timeoutMs: 5000 })
  }

  async function refreshHealth(): Promise<HealthResponse | null> {
    try {
      const res = await api.get<HealthResponse>('/health', { timeoutMs: 4000 })
      health.value = res
      healthError.value = null
      const nextAuthRequired = !!res.api_auth_required
      authRequired.value = nextAuthRequired
      if (nextAuthRequired && authStatus.value === 'ready' && !getApiKey()) {
        lockConsole('服务已开启 API Key 保护，请重新解锁控制台。')
      }
      if (!nextAuthRequired && authStatus.value !== 'ready') {
        authStatus.value = 'ready'
        authError.value = null
        connectEvents()
      }
      return res
    } catch (err) {
      health.value = null
      healthError.value = err instanceof ShoreApiError ? err.message : (err as Error).message
      return null
    }
  }

  function startHealthPolling(runImmediately = true) {
    if (healthTimer !== null) return
    if (runImmediately) void refreshHealth()
    healthTimer = window.setInterval(() => void refreshHealth(), 15000)
  }

  function stopHealthPolling() {
    if (healthTimer !== null) {
      window.clearInterval(healthTimer)
      healthTimer = null
    }
  }

  async function ensureAuthorized(messageWhenMissing = '服务已启用 API Key，请先输入 API Key。') {
    if (!authRequired.value) {
      authStatus.value = 'ready'
      authError.value = null
      connectEvents()
      return true
    }

    if (!getApiKey()) {
      lockConsole(messageWhenMissing)
      return false
    }

    authStatus.value = 'checking'
    authError.value = null
    try {
      await verifyProtectedAccess()
      authStatus.value = 'ready'
      authError.value = null
      connectEvents()
      return true
    } catch (err) {
      lockConsole(resolveAuthError(err))
      return false
    }
  }

  async function bootstrap() {
    if (bootstrapped) return
    bootstrapped = true
    syncApiKeyState()
    startHealthPolling(false)
    const client = getEventsClient()
    detachEventsStatus = client.onStatus((s) => {
      eventsStatus.value = s
      lastEventAt.value = client.getLastEventAt()
    })
    detachEventsListener = client.on(() => {
      lastEventAt.value = client.getLastEventAt()
    })
    detachUnauthorized = onUnauthorized((error) => {
      if (!authRequired.value) return
      lockConsole(resolveAuthError(error))
    })
    detachApiKeyListener = subscribeApiKey(() => {
      syncApiKeyState()
      if (authRequired.value && !getApiKey()) {
        lockConsole('API Key 已清除，请重新解锁控制台。')
        return
      }
      if (authStatus.value === 'ready') {
        client.reconnect()
      }
    })

    const res = await refreshHealth()
    if (!res) {
      authStatus.value = 'ready'
      authError.value = null
      connectEvents()
      return
    }

    if (!authRequired.value) {
      authStatus.value = 'ready'
      authError.value = null
      connectEvents()
      return
    }

    await ensureAuthorized()
  }

  async function unlock(apiKey: string, remember: boolean) {
    const normalized = apiKey.trim()
    if (!normalized) {
      const message = '请输入 API Key。'
      authError.value = message
      throw new Error(message)
    }

    unlocking.value = true
    setStoredApiKey(normalized, remember)
    syncApiKeyState()
    try {
      const success = await ensureAuthorized('服务已启用 API Key，请先输入 API Key。')
      if (!success) {
        clearStoredApiKey()
        syncApiKeyState()
        throw new Error(authError.value ?? 'API Key 校验失败。')
      }
      await refreshHealth()
    } catch (err) {
      clearStoredApiKey()
      syncApiKeyState()
      const message = resolveAuthError(err)
      lockConsole(message)
      throw new Error(message)
    } finally {
      unlocking.value = false
    }
  }

  async function retryAuth() {
    syncApiKeyState()
    const res = await refreshHealth()
    if (!res) {
      lockConsole(healthError.value ?? '无法连接 Shore 服务。')
      return false
    }
    return ensureAuthorized('服务已启用 API Key，请输入 API Key 后再试。')
  }

  function clearSavedApiKey() {
    clearStoredApiKey()
    syncApiKeyState()
    if (authRequired.value) {
      if (getApiKey()) {
        authError.value = null
        if (authStatus.value === 'ready') {
          getEventsClient().reconnect()
        }
      } else {
        lockConsole('已清除已保存的 API Key。')
      }
    } else {
      authError.value = null
    }
  }

  function teardown() {
    bootstrapped = false
    stopHealthPolling()
    detachEventsStatus?.()
    detachEventsStatus = null
    detachEventsListener?.()
    detachEventsListener = null
    detachUnauthorized?.()
    detachUnauthorized = null
    detachApiKeyListener?.()
    detachApiKeyListener = null
    getEventsClient().disconnect()
  }

  return {
    agentId,
    apiBase,
    health,
    healthError,
    authStatus,
    authRequired,
    authError,
    unlocking,
    apiKeySource,
    eventsStatus,
    lastEventAt,
    isHealthy,
    isEventsOpen,
    needsUnlock,
    canRenderConsole,
    hasAnyApiKey,
    hasStoredApiKey,
    authSourceLabel,
    setAgent,
    refreshHealth,
    bootstrap,
    unlock,
    retryAuth,
    clearSavedApiKey,
    teardown
  }
})
