/**
 * /v1/memories* 接口封装
 */
import { api } from './http'
import type {
  ExportMemoriesRequest,
  ExportMemoriesResponse,
  ListMemoriesRequest,
  ListMemoriesResponse,
  MemoryDetailResponse,
  UpdateMemoryRequest,
  UpdateMemoryResponse
} from './types'

function toQuery(req: ListMemoriesRequest): Record<string, unknown> {
  return {
    agent_id: req.agent_id,
    user_uid: req.user_uid ?? undefined,
    channel_uid: req.channel_uid ?? undefined,
    session_uid: req.session_uid ?? undefined,
    scope: req.scope ?? undefined,
    state: req.state ?? undefined,
    memory_type: req.memory_type ?? undefined,
    content_query: req.content_query ?? undefined,
    include_archived: req.include_archived,
    limit: req.limit,
    offset: req.offset
  }
}

export function listMemories(req: ListMemoriesRequest): Promise<ListMemoriesResponse> {
  return api.get<ListMemoriesResponse>('/v1/memories', {
    query: toQuery(req),
    timeoutMs: 15000
  })
}

export function getMemory(memoryId: number): Promise<MemoryDetailResponse> {
  return api.get<MemoryDetailResponse>(`/v1/memories/${memoryId}`, { timeoutMs: 10000 })
}

export function updateMemory(
  memoryId: number,
  patch: UpdateMemoryRequest
): Promise<UpdateMemoryResponse> {
  return api.patch<UpdateMemoryResponse>(`/v1/memories/${memoryId}`, patch, { timeoutMs: 15000 })
}

export function exportMemories(req: ExportMemoriesRequest): Promise<ExportMemoriesResponse> {
  return api.get<ExportMemoriesResponse>('/v1/memories/export', {
    query: {
      agent_id: req.agent_id,
      include_archived: req.include_archived
    },
    timeoutMs: 30000
  })
}
