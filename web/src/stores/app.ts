import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, ShoreApiError } from '@/api/http'
import type { HealthResponse } from '@/api/types'
import { getEventsClient, type EventsStatus } from '@/api/events'

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
  const eventsStatus = ref<EventsStatus>('disconnected')
  const lastEventAt = ref<number | null>(null)

  let healthTimer: number | null = null

  const isHealthy = computed(() => !!health.value && health.value.status === 'ok')
  const isEventsOpen = computed(() => eventsStatus.value === 'open' || eventsStatus.value === 'lagged')

  function setAgent(next: string) {
    agentId.value = next
    localStorage.setItem('shore:agent', next)
  }

  async function refreshHealth() {
    try {
      const res = await api.get<HealthResponse>('/health', { timeoutMs: 4000 })
      health.value = res
      healthError.value = null
    } catch (err) {
      health.value = null
      healthError.value = err instanceof ShoreApiError ? err.message : (err as Error).message
    }
  }

  function startHealthPolling() {
    if (healthTimer !== null) return
    void refreshHealth()
    healthTimer = window.setInterval(() => void refreshHealth(), 15000)
  }

  function stopHealthPolling() {
    if (healthTimer !== null) {
      window.clearInterval(healthTimer)
      healthTimer = null
    }
  }

  function bootstrap() {
    startHealthPolling()
    const client = getEventsClient()
    client.onStatus((s) => {
      eventsStatus.value = s
      lastEventAt.value = client.getLastEventAt()
    })
    client.on(() => {
      lastEventAt.value = client.getLastEventAt()
    })
    client.connect()
  }

  function teardown() {
    stopHealthPolling()
    getEventsClient().disconnect()
  }

  return {
    agentId,
    apiBase,
    health,
    healthError,
    eventsStatus,
    lastEventAt,
    isHealthy,
    isEventsOpen,
    setAgent,
    refreshHealth,
    bootstrap,
    teardown
  }
})
