/**
 * Shore Memory API 类型（根据 server/src/types.rs 对齐）
 */

export type MemoryState = 'active' | 'superseded' | 'invalidated' | 'archived'
/** 对齐 server MemoryScope 枚举：private / group / shared / system */
export type MemoryScope = 'private' | 'group' | 'shared' | 'system'
export type MemoryScopeHint = 'auto' | 'private' | 'group' | 'shared' | 'system'
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
  source_event_ids: number[]
  linked_memory_ids: number[]
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
  access_count: number
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
  source_task_id?: number | null
  created_at: string
}

export interface ListMemoriesRequest {
  agent_id: string
  user_uid?: string | null
  channel_uid?: string | null
  session_uid?: string | null
  scope?: MemoryScope
  state?: MemoryState
  memory_type?: string
  content_query?: string
  include_archived?: boolean
  limit?: number
  offset?: number
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

export interface ExportMemoriesRequest {
  agent_id: string
  include_archived?: boolean
}

export interface ExportMemoriesResponse {
  agent_id: string
  exported_at: string
  count: number
  items: MemoryRecord[]
}

/* ---------------- Graph ---------------- */

/** GET /v1/graph 查询参数 */
export interface GraphRequest {
  agent_id: string
  limit?: number
  include_archived?: boolean
  state?: MemoryState
  user_uid?: string | null
  channel_uid?: string | null
}

export interface GraphMemoryNode {
  id: number
  scope: MemoryScope
  memory_type: MemoryType
  content_preview: string
  state: MemoryState | string
  importance: number
  session_uid?: string | null
  supersedes_memory_id?: number | null
  archived_at?: string | null
  created_at: string
  updated_at: string
  entity_ids: number[]
}

export interface GraphEntityNode {
  id: number
  name: string
  entity_type: string
  linked_memory_count: number
  local_memory_count: number
}

export interface GraphMemoryEntityEdge {
  memory_id: number
  entity_id: number
  weight: number
}

export interface GraphSupersedeEdge {
  from_memory_id: number
  to_memory_id: number
}

export interface GraphStats {
  memory_count: number
  entity_count: number
  memory_entity_edges: number
  supersede_edges: number
  total_memories_for_agent: number
  truncated: boolean
}

export interface GraphResponse {
  agent_id: string
  memories: GraphMemoryNode[]
  entities: GraphEntityNode[]
  memory_entity_edges: GraphMemoryEntityEdge[]
  supersede_edges: GraphSupersedeEdge[]
  stats: GraphStats
  generated_at: string
}

/* ---------------- Recall ---------------- */

/**
 * 与 server/src/types.rs::RecallRequest 对齐。
 * 字段全部 snake_case（原生传透）。
 */
export interface RecallRequest {
  agent_id: string
  query: string
  user_uid?: string | null
  channel_uid?: string | null
  session_uid?: string | null
  source?: string | null
  limit?: number
  include_state?: boolean
  scope_hint?: MemoryScopeHint
  selected_scopes?: MemoryScope[]
  debug?: boolean
  /** fast / hybrid / entity_heavy / contiguous */
  recipe?: RecallRecipeId
  include_invalid?: boolean
}

export type RecallRecipeId = 'fast' | 'hybrid' | 'entity_heavy' | 'contiguous'

export interface EntityDraft {
  name: string
  entity_type?: string
  scope?: MemoryScope
  confidence?: number
}

export interface ScoreBreakdown {
  semantic: number
  bm25: number
  entity: number
  contiguity: number
  scope_weight: number
  /** 融合后的最终分数 */
  combined: number
  /** 融合自适应分母 */
  divisor: number
}

export interface MemoryLifecycle {
  state: string
  valid_at?: string | null
  invalid_at?: string | null
  supersedes_memory_id?: number | null
}

export interface MemorySnippet {
  id: number
  time: string
  content: string
  scope: MemoryScope
  score?: number | null
  score_breakdown?: ScoreBreakdown | null
  entities?: EntityDraft[]
  lifecycle?: MemoryLifecycle | null
}

export interface RecallResponse {
  memory_context: MemorySnippet[]
  agent_state?: AgentStateResponse | null
  degraded: boolean
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
  by_status: Record<string, number>
  by_kind: Record<string, number>
  failed_tasks: number
  pending_tasks: number
  oldest_pending_created_at?: string | null
  latest_error?: string | null
}

export interface TaskActionResponse {
  task_id?: number
  status: string
  message?: string
}

/* ---------------- Model config ---------------- */

export type ProviderKind = 'embedding' | 'llm'
export type PresetKind = 'embedding' | 'llm'

export interface ProviderConfigResponse {
  api_base: string
  model: string
  dimension?: number
  temperature?: number
  configured: boolean
  api_key_configured: boolean
  api_key_masked?: string | null
  source: string
  api_key_source: string
  override_active: boolean
}

export interface ModelPresetResponse {
  id: string
  name: string
  kind: PresetKind
  api_base: string
  model: string
  dimension?: number
  temperature?: number
  configured: boolean
  api_key_configured: boolean
  api_key_masked?: string | null
  source: string
  api_key_source: string
  is_default: boolean
}

export interface RoleBindingResponse {
  preset_id?: string | null
  temperature?: number | null
  effective_preset_id?: string | null
  follows_default: boolean
  resolved: ProviderConfigResponse
}

export interface ModelConfigStorageResponse {
  path: string
  override_active: boolean
  updated_at?: string | null
}

export interface ModelConfigResponse {
  embedding: ProviderConfigResponse
  llm: ProviderConfigResponse
  roles: Record<string, ProviderConfigResponse>
  embedding_presets: ModelPresetResponse[]
  llm_presets: ModelPresetResponse[]
  default_embedding_preset?: string | null
  default_llm_preset?: string | null
  role_bindings: Record<string, RoleBindingResponse>
  storage: ModelConfigStorageResponse
}

export interface ListProviderModelsRequest {
  provider: ProviderKind
  api_base: string
  preset_id?: string
  role?: string
  api_key?: string
  clear_api_key: boolean
}

export interface ListProviderModelsResponse {
  provider: ProviderKind
  models: string[]
  count: number
  source: string
  api_key_source: string
}

export interface DetectEmbeddingDimensionRequest {
  api_base: string
  model: string
  preset_id?: string
  api_key?: string
  clear_api_key: boolean
}

export interface DetectEmbeddingDimensionResponse {
  model: string
  dimension: number
  source: string
  api_key_source: string
}

export interface UpdatePresetRequest {
  id: string
  name: string
  api_base?: string
  model?: string
  dimension?: number
  temperature?: number
  /** New api key to persist. Ignored when clear_api_key / api_key_unchanged is set. */
  api_key?: string
  clear_api_key?: boolean
  /** Ask the server to preserve the previously stored api key unchanged. */
  api_key_unchanged?: boolean
}

export interface UpdateRoleBindingRequest {
  /** null or undefined means "follow the currently-active default LLM preset". */
  preset_id?: string | null
  temperature?: number | null
}

export interface UpdateModelConfigRequest {
  embedding_presets: UpdatePresetRequest[]
  llm_presets: UpdatePresetRequest[]
  default_embedding_preset?: string
  default_llm_preset?: string
  role_bindings?: Record<string, UpdateRoleBindingRequest>
  auto_detect_embedding_dimension?: boolean
}

export interface UpdateModelConfigResponse {
  config: ModelConfigResponse
  embedding_changed: boolean
  embedding_dimension_changed: boolean
  embedding_cache_cleared: boolean
  memory_embeddings_refreshed: number
  reindexed_memories: number
  reindexed_entities: number
}

export interface ProviderTestResponse {
  ok: boolean
  configured: boolean
  message: string
  dimension?: number | null
  source: string
}

export interface ModelConfigTestResponse {
  embedding: ProviderTestResponse
  llm: ProviderTestResponse
  roles: Record<string, ProviderTestResponse>
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
  /** server 发送字段名为 `event`（对齐 `ServerEvent` 结构体） */
  event: ServerEventType
  payload: Record<string, unknown>
  at?: string
}

/* ---------------- Common ---------------- */

export interface HealthResponse {
  status: string
  trace_id?: string | number | null
  api_auth_required?: boolean
  worker_available?: boolean
  pending_tasks?: number
  failed_tasks?: number
}
