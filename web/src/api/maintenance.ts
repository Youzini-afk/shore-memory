/**
 * /v1/maintenance/* 接口封装
 *
 * 对齐 server/src/app.rs::{retry_scorer, run_reflection, rebuild_trivium,
 * sync_summary}。
 *
 * - retry_scorer: 同步，立刻返回 `retried N failed scorer tasks`
 * - run_reflection / rebuild_trivium: 入队，202 + `task_id`，真正结束时
 *   通过 WS 广播 `maintenance.completed` 事件（payload 带 task_id）
 */
import { api } from './http'
import type { SyncSummaryResponse, TaskActionResponse } from './types'

export function getSyncSummary(): Promise<SyncSummaryResponse> {
  return api.get<SyncSummaryResponse>('/v1/maintenance/sync-summary', {
    timeoutMs: 8000
  })
}

export function retryScorer(agentId: string): Promise<TaskActionResponse> {
  return api.post<TaskActionResponse>(
    '/v1/maintenance/scorer/retry',
    { agent_id: agentId },
    { timeoutMs: 12000 }
  )
}

export function runReflection(agentId: string): Promise<TaskActionResponse> {
  return api.post<TaskActionResponse>(
    '/v1/maintenance/reflection/run',
    { agent_id: agentId },
    { timeoutMs: 12000 }
  )
}

export function rebuildTrivium(agentId: string): Promise<TaskActionResponse> {
  return api.post<TaskActionResponse>(
    '/v1/maintenance/trivium/rebuild',
    { agent_id: agentId },
    { timeoutMs: 12000 }
  )
}
