/**
 * /v1/graph 接口封装
 */
import { api } from './http'
import type { GraphRequest, GraphResponse } from './types'

export function fetchGraph(req: GraphRequest): Promise<GraphResponse> {
  return api.get<GraphResponse>('/v1/graph', {
    query: {
      agent_id: req.agent_id,
      limit: req.limit,
      include_archived: req.include_archived,
      state: req.state,
      user_uid: req.user_uid ?? undefined,
      channel_uid: req.channel_uid ?? undefined
    },
    timeoutMs: 30000
  })
}
