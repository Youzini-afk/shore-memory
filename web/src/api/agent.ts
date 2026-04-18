/**
 * /v1/agents/{agent_id}/state 接口封装
 *
 * 对齐 server/src/app.rs::{get_agent_state, update_agent_state}。
 * 服务端会在 scorer / reflection pipeline 完成后自动 upsert 并通过 WS
 * 广播 `agent.state.updated`，所以前端多数情况下只需 GET 一次，后续由
 * 事件流驱动刷新。
 */
import { api } from './http'
import type { AgentStatePatch, AgentStateResponse } from './types'

export function getAgentState(agentId: string): Promise<AgentStateResponse> {
  const encoded = encodeURIComponent(agentId)
  return api.get<AgentStateResponse>(`/v1/agents/${encoded}/state`, {
    timeoutMs: 8000
  })
}

export function patchAgentState(
  agentId: string,
  patch: AgentStatePatch
): Promise<AgentStateResponse> {
  const encoded = encodeURIComponent(agentId)
  return api.patch<AgentStateResponse>(`/v1/agents/${encoded}/state`, patch, {
    timeoutMs: 8000
  })
}
