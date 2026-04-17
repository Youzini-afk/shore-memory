/**
 * Shore Memory API 类型（根据 server/src/types.rs 对齐）
 */

export type MemoryState = 'active' | 'superseded' | 'invalidated' | 'archived'
export type MemoryScope = 'private' | 'shared' | 'public'
export type MemoryType =
  | 'event'
  | 'fact'
  | 'promise'
  | 'preference'
  | 'work_log'
  | 'summary'
  | 'interaction_summary'
  | 'archived_event'
  | string

export interface MemoryRecord {
  id: number
  agent_id: string
  user_uid?: string | null
  channel_uid?: string | null
  session_uid?: string | null
  scope: MemoryScope | string
  memory_type: MemoryType
  content: string
  content_hash?: string | null
  tags: string[]
  metadata: Record<string, unknown>
  importance: number
  sentiment?: string | null
  source: string
  embedding_json?: string | null
  state: MemoryState | string
  valid_at?: string | null
  invalid_at?: string | null
  supersedes_memory_id?: number | null
  archived_at?: string | null
  created_at: string
  updated_at: string
  access_count?: number
  last_accessed_at?: string | null
}

export interface EntityRecord {
  id: number
  agent_id: string
  name: string
  entity_type?: string | null
  scope: string
  linked_memory_count?: number
}

export interface MemoryHistoryRecord {
  id: number
  memory_id: number | null
  agent_id: string
  event: string
  old_content?: string | null
  new_content?: string | null
  old_metadata?: Record<string, unknown> | null
  new_metadata?: Record<string, unknown> | null
  note?: string | null
  created_at: string
}

export interface ListMemoriesResponse {
  items: MemoryRecord[]
  total: number
  limit: number
  offset: number
}

export interface MemoryDetailResponse {
  memory: MemoryRecord
  entities: EntityRecord[]
  history: MemoryHistoryRecord[]
}

export interface UpdateMemoryRequest {
  content?: string
  tags?: string[]
  metadata?: Record<string, unknown>
  importance?: number
  sentiment?: string | null
  source?: string
  state?: MemoryState
  valid_at?: string
  invalid_at?: string | null
  supersedes_memory_id?: number | null
  archived?: boolean
}

export interface UpdateMemoryResponse {
  memory: MemoryRecord
  rebuild_task_id?: number | null
  rebuild_queued: boolean
}

export interface ExportMemoriesResponse {
  agent_id: string
  exported_at: string
  count: number
  items: MemoryRecord[]
}

/* ---------------- Recall ---------------- */

export interface RecallRequest {
  agent_id: string
  query: string
  user_uid?: string
  channel_uid?: string
  session_uid?: string
  limit?: number
  recipe?: string
  include_invalid?: boolean
}

export interface ScoreBreakdown {
  semantic: number
  bm25: number
  entity: number
  contiguity: number
  final: number
}

export interface MemoryLifecycle {
  state: string
  valid_at?: string | null
  invalid_at?: string | null
  supersedes?: number | null
  archived_at?: string | null
}

export interface MemorySnippet {
  id: number
  content: string
  importance: number
  scope: string
  memory_type: string
  score: number
  score_breakdown?: ScoreBreakdown
  lifecycle?: MemoryLifecycle
  tags?: string[]
  entities?: string[]
}

export interface RecallResponse {
  memories: MemorySnippet[]
  trace_id: string
  latency_ms: number
  cache: 'hit' | 'miss'
  degraded: boolean
  degraded_reason?: string
}

/* ---------------- Agent state ---------------- */

export interface AgentStatePatch {
  mood?: string
  vibe?: string
  mind?: string
}

export interface AgentStateResponse {
  agent_id: string
  mood: string
  vibe: string
  mind: string
  updated_at?: string
}

/* ---------------- Maintenance ---------------- */

export interface SyncSummaryResponse {
  pending_tasks: number
  running_tasks: number
  failed_tasks: number
  succeeded_tasks_24h?: number
}

export interface TaskActionResponse {
  task_id?: number
  status: string
  message?: string
}

/* ---------------- Events ---------------- */

export type ServerEventType =
  | 'memory.updated'
  | 'agent.state.updated'
  | 'maintenance.completed'
  | 'sync.failed'
  | 'lagged'
  | string

export interface ServerEvent {
  type: ServerEventType
  payload: Record<string, unknown>
  at?: string
}

/* ---------------- Common ---------------- */

export interface HealthResponse {
  status: string
  trace_id?: string
  worker_reachable?: boolean
  task_queue_depth?: number
}
