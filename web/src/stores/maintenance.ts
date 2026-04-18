import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { useAppStore } from './app'
import {
  getSyncSummary,
  rebuildTrivium,
  retryScorer,
  runReflection
} from '@/api/maintenance'
import { getEventsClient } from '@/api/events'
import { ShoreApiError } from '@/api/http'
import type { ServerEvent, SyncSummaryResponse, TaskActionResponse } from '@/api/types'

/**
 * 运维 store：
 *
 * - `summary`：最近一次 `/v1/maintenance/sync-summary`。默认 15s 轮询，
 *   `maintenance.completed` / `sync.failed` / `memory.indexed` 触发时
 *   500ms 去抖重拉。
 * - `actions`：三种维护动作（scorer 重试 / 反思 / 重建索引）的最近一次
 *   调用状态。`scorer_retry` 同步返回；另两种入队 `task_id` 后挂起，
 *   WS 收到匹配 task_id 的 `maintenance.completed` 才标记为 settled。
 * - `events`：环形缓冲的最近 MAX_EVENTS 条事件，用于 EventFeed 展示。
 */

export type MaintenanceActionKey = 'scorer_retry' | 'reflection_run' | 'trivium_rebuild'

export interface MaintenanceActionRun {
  status: 'idle' | 'pending' | 'queued' | 'success' | 'error'
  taskId?: number | null
  message?: string | null
  startedAt?: number | null
  settledAt?: number | null
  error?: string | null
}

export interface RecordedEvent {
  id: string
  event: string
  payload: Record<string, unknown>
  receivedAt: number
  at?: string
}

const POLL_INTERVAL_MS = 15_000
const REFRESH_DEBOUNCE_MS = 500
const MAX_EVENTS = 100

function idleAction(): MaintenanceActionRun {
  return {
    status: 'idle',
    taskId: null,
    message: null,
    startedAt: null,
    settledAt: null,
    error: null
  }
}

function genEventId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    try {
      return (crypto as Crypto).randomUUID()
    } catch {
      // fallthrough
    }
  }
  return `e-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export const useMaintenanceStore = defineStore('maintenance', () => {
  const app = useAppStore()

  const summary = ref<SyncSummaryResponse | null>(null)
  const summaryError = ref<string | null>(null)
  const summaryLoading = ref(false)
  const lastSummaryAt = ref<number | null>(null)

  const actions = ref<Record<MaintenanceActionKey, MaintenanceActionRun>>({
    scorer_retry: idleAction(),
    reflection_run: idleAction(),
    trivium_rebuild: idleAction()
  })

  const events = ref<RecordedEvent[]>([])
  const lastEventAt = computed(() => events.value[0]?.receivedAt ?? null)

  let pollTimer: number | null = null
  let refreshTimer: number | null = null
  let eventsBound = false

  const totalTasks = computed(() => {
    if (!summary.value) return 0
    return Object.values(summary.value.by_status).reduce(
      (acc, count) => acc + (count ?? 0),
      0
    )
  })

  async function refreshSummary(): Promise<SyncSummaryResponse | null> {
    summaryLoading.value = true
    summaryError.value = null
    try {
      const res = await getSyncSummary()
      summary.value = res
      lastSummaryAt.value = Date.now()
      return res
    } catch (err) {
      summaryError.value =
        err instanceof ShoreApiError ? err.message : (err as Error).message
      return null
    } finally {
      summaryLoading.value = false
    }
  }

  function scheduleRefresh() {
    if (refreshTimer !== null) return
    refreshTimer = window.setTimeout(() => {
      refreshTimer = null
      void refreshSummary()
    }, REFRESH_DEBOUNCE_MS)
  }

  function startPolling(runImmediately = true) {
    if (pollTimer !== null) return
    if (runImmediately) void refreshSummary()
    pollTimer = window.setInterval(() => {
      void refreshSummary()
    }, POLL_INTERVAL_MS)
  }

  function stopPolling() {
    if (pollTimer !== null) {
      window.clearInterval(pollTimer)
      pollTimer = null
    }
    if (refreshTimer !== null) {
      window.clearTimeout(refreshTimer)
      refreshTimer = null
    }
  }

  function pushEvent(evt: ServerEvent) {
    const record: RecordedEvent = {
      id: genEventId(),
      event: evt.event,
      payload: (evt.payload ?? {}) as Record<string, unknown>,
      receivedAt: Date.now(),
      at: evt.at
    }
    events.value.unshift(record)
    if (events.value.length > MAX_EVENTS) {
      events.value.length = MAX_EVENTS
    }
  }

  function clearEvents() {
    events.value = []
  }

  function settleActionByTaskId(taskId: number, payload: Record<string, unknown>) {
    const message =
      typeof payload.report === 'object' && payload.report !== null
        ? JSON.stringify(payload.report)
        : typeof payload.message === 'string'
          ? payload.message
          : '任务已完成'
    for (const key of Object.keys(actions.value) as MaintenanceActionKey[]) {
      const run = actions.value[key]
      if (run.status === 'queued' && run.taskId === taskId) {
        actions.value[key] = {
          ...run,
          status: 'success',
          settledAt: Date.now(),
          message
        }
      }
    }
  }

  function bindEvents() {
    if (eventsBound) return
    eventsBound = true
    const client = getEventsClient()
    client.on((evt) => {
      pushEvent(evt)
    })
    const refreshTriggers = new Set([
      'maintenance.completed',
      'sync.failed',
      'memory.indexed'
    ])
    client.on((evt) => {
      if (refreshTriggers.has(evt.event)) {
        scheduleRefresh()
      }
      if (evt.event === 'maintenance.completed') {
        const payload = (evt.payload ?? {}) as Record<string, unknown>
        const tid = payload.task_id
        if (typeof tid === 'number') {
          settleActionByTaskId(tid, payload)
        }
      }
    })
  }

  async function dispatch(
    key: MaintenanceActionKey,
    fn: (agentId: string) => Promise<TaskActionResponse>,
    opts: { asyncTask: boolean }
  ) {
    actions.value[key] = {
      ...idleAction(),
      status: 'pending',
      startedAt: Date.now()
    }
    try {
      const res = await fn(app.agentId)
      const taskId = res.task_id ?? null
      actions.value[key] = {
        status: opts.asyncTask ? 'queued' : 'success',
        taskId,
        message: res.message ?? null,
        startedAt: actions.value[key].startedAt,
        settledAt: opts.asyncTask ? null : Date.now(),
        error: null
      }
      // 动作触发后立即拉一下摘要
      scheduleRefresh()
      return res
    } catch (err) {
      const message =
        err instanceof ShoreApiError ? err.message : (err as Error).message
      actions.value[key] = {
        status: 'error',
        taskId: null,
        message: null,
        startedAt: actions.value[key].startedAt,
        settledAt: Date.now(),
        error: message
      }
      throw err
    }
  }

  function retryScorerAction() {
    return dispatch('scorer_retry', retryScorer, { asyncTask: false })
  }

  function runReflectionAction() {
    return dispatch('reflection_run', runReflection, { asyncTask: true })
  }

  function rebuildTriviumAction() {
    return dispatch('trivium_rebuild', rebuildTrivium, { asyncTask: true })
  }

  function resetAction(key: MaintenanceActionKey) {
    actions.value[key] = idleAction()
  }

  // Agent 切换：重置动作状态 + 重拉摘要，事件缓冲保留
  watch(
    () => app.agentId,
    () => {
      actions.value = {
        scorer_retry: idleAction(),
        reflection_run: idleAction(),
        trivium_rebuild: idleAction()
      }
      void refreshSummary()
    }
  )

  return {
    summary,
    summaryError,
    summaryLoading,
    lastSummaryAt,
    actions,
    events,
    lastEventAt,
    totalTasks,
    refreshSummary,
    startPolling,
    stopPolling,
    bindEvents,
    clearEvents,
    retryScorerAction,
    runReflectionAction,
    rebuildTriviumAction,
    resetAction
  }
})
