use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum MemoryScope {
    Private,
    Group,
    Shared,
    System,
}

impl MemoryScope {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Private => "private",
            Self::Group => "group",
            Self::Shared => "shared",
            Self::System => "system",
        }
    }
}

impl std::fmt::Display for MemoryScope {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for MemoryScope {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "private" => Ok(Self::Private),
            "group" => Ok(Self::Group),
            "shared" => Ok(Self::Shared),
            "system" => Ok(Self::System),
            _ => Err(format!("invalid memory scope: {s}")),
        }
    }
}

pub fn default_recall_scopes(request_scope: MemoryScope) -> Vec<MemoryScope> {
    match request_scope {
        MemoryScope::Private => vec![
            MemoryScope::Private,
            MemoryScope::Shared,
            MemoryScope::System,
        ],
        MemoryScope::Group => vec![MemoryScope::Group, MemoryScope::Shared, MemoryScope::System],
        MemoryScope::Shared => vec![MemoryScope::Shared, MemoryScope::System],
        MemoryScope::System => vec![MemoryScope::System, MemoryScope::Shared],
    }
}

pub fn selected_recall_scopes(
    request_scope: MemoryScope,
    selected_scopes: Option<&[MemoryScope]>,
) -> Vec<MemoryScope> {
    let mut out = default_recall_scopes(request_scope);
    if let Some(extra_scopes) = selected_scopes {
        for scope in extra_scopes {
            if !out.contains(scope) {
                out.push(*scope);
            }
        }
    }
    out
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MemoryScopeHint {
    Auto,
    Private,
    Group,
    Shared,
    System,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
#[serde(rename_all = "snake_case")]
pub enum MemoryDomainKind {
    GlobalPerson,
    PlatformPerson,
    ChannelShared,
    ChannelPerson,
    SessionThread,
}

impl MemoryDomainKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::GlobalPerson => "global_person",
            Self::PlatformPerson => "platform_person",
            Self::ChannelShared => "channel_shared",
            Self::ChannelPerson => "channel_person",
            Self::SessionThread => "session_thread",
        }
    }
}

impl std::fmt::Display for MemoryDomainKind {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for MemoryDomainKind {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "global_person" => Ok(Self::GlobalPerson),
            "platform_person" => Ok(Self::PlatformPerson),
            "channel_shared" => Ok(Self::ChannelShared),
            "channel_person" => Ok(Self::ChannelPerson),
            "session_thread" => Ok(Self::SessionThread),
            _ => Err(format!("invalid memory domain kind: {s}")),
        }
    }
}

impl Default for MemoryDomainKind {
    fn default() -> Self {
        Self::SessionThread
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default, PartialEq, Eq)]
pub struct MemoryDomain {
    pub kind: MemoryDomainKind,
    pub key: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub platform: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub channel_uid: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub session_uid: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub person_uid: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct IdentityAliasHint {
    pub account_uid: String,
    pub person_uid: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub confidence: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TaskKind {
    ScoreTurn,
    ReflectionRun,
    RebuildTrivium,
    IndexMemory,
}

impl TaskKind {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::ScoreTurn => "score_turn",
            Self::ReflectionRun => "reflection_run",
            Self::RebuildTrivium => "rebuild_trivium",
            Self::IndexMemory => "index_memory",
        }
    }

    pub fn as_metric_label(&self) -> &'static str {
        self.as_str()
    }
}

impl std::fmt::Display for TaskKind {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for TaskKind {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "score_turn" => Ok(Self::ScoreTurn),
            "reflection_run" => Ok(Self::ReflectionRun),
            "rebuild_trivium" => Ok(Self::RebuildTrivium),
            "index_memory" => Ok(Self::IndexMemory),
            _ => Err(format!("invalid task kind: {s}")),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum TaskStatus {
    Pending,
    Processing,
    Failed,
    Completed,
}

impl TaskStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Pending => "pending",
            Self::Processing => "processing",
            Self::Failed => "failed",
            Self::Completed => "completed",
        }
    }
}

impl std::fmt::Display for TaskStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

impl std::str::FromStr for TaskStatus {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "pending" => Ok(Self::Pending),
            "processing" => Ok(Self::Processing),
            "failed" => Ok(Self::Failed),
            "completed" => Ok(Self::Completed),
            _ => Err(format!("invalid task status: {s}")),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actor_account_uid: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actor_person_uid: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub focal_person_uids: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub source_platform: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub domain: Option<MemoryDomain>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub observation_at: Option<String>,
    pub query: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subqueries: Option<Vec<String>>,
    pub source: Option<String>,
    pub limit: Option<usize>,
    pub include_state: Option<bool>,
    pub scope_hint: Option<MemoryScopeHint>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub selected_scopes: Option<Vec<MemoryScope>>,
    #[serde(default)]
    pub debug: Option<bool>,
    #[serde(default)]
    pub auto_plan: Option<bool>,
    /// Stage 2 recall recipes (fast / hybrid / entity_heavy / contiguous).
    #[serde(default)]
    pub recipe: Option<String>,
    /// Stage 3 time-travel switch. When `true`, recall considers memories
    /// whose `state != active` or whose `invalid_at` has passed. Default is
    /// `false` — only currently-valid memories are returned.
    #[serde(default)]
    pub include_invalid: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallResponse {
    pub memory_context: Vec<MemorySnippet>,
    pub agent_state: Option<AgentStateResponse>,
    pub degraded: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub query_plan: Option<RecallQueryPlan>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemorySnippet {
    pub id: i64,
    pub time: String,
    pub content: String,
    pub scope: MemoryScope,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actor_person_uid: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subject_person_uid: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub domain: Option<MemoryDomain>,
    pub score: Option<f32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub score_breakdown: Option<ScoreBreakdown>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub entities: Vec<EntityDraft>,
    /// Stage 3 fact-lifetime metadata. Only populated when the caller asked
    /// for `debug=true` or explicitly requested `include_invalid=true` —
    /// active memories with no interesting state look the same as before.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub lifecycle: Option<MemoryLifecycle>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub query_debug: Option<MemoryQueryDebug>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScoreBreakdown {
    pub semantic: f32,
    pub bm25: f32,
    pub entity: f32,
    pub contiguity: f32,
    pub scope_weight: f32,
    pub domain_weight: f32,
    pub person_weight: f32,
    pub time_weight: f32,
    pub combined: f32,
    pub divisor: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallQueryPlan {
    pub source: String,
    #[serde(default)]
    pub subqueries: Vec<String>,
    #[serde(default)]
    pub requested_auto_plan: bool,
    #[serde(default)]
    pub planner_used: bool,
    #[serde(default)]
    pub planner_degraded: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub planner_error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MemoryQueryDebug {
    #[serde(default)]
    pub matched_subquery_indices: Vec<usize>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub best_subquery_index: Option<usize>,
}

/// Snapshot of a memory's temporal-fact lifecycle. Mirrors
/// `MemoryRecord.state / valid_at / invalid_at / supersedes_memory_id`.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MemoryLifecycle {
    pub state: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub valid_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub invalid_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub supersedes_memory_id: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TurnEventRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    #[serde(default)]
    pub actor_account_uid: Option<String>,
    #[serde(default)]
    pub actor_person_uid: Option<String>,
    #[serde(default)]
    pub subject_person_uid: Option<String>,
    #[serde(default)]
    pub source_platform: Option<String>,
    pub source: String,
    pub scope_hint: Option<MemoryScopeHint>,
    pub messages: Vec<TurnMessage>,
    #[serde(default)]
    pub domain: Option<MemoryDomain>,
    #[serde(default)]
    pub observation_at: Option<String>,
    #[serde(default)]
    pub alias_hints: Vec<IdentityAliasHint>,
    pub metadata: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TurnMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EventMessageRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    #[serde(default)]
    pub actor_account_uid: Option<String>,
    #[serde(default)]
    pub actor_person_uid: Option<String>,
    #[serde(default)]
    pub subject_person_uid: Option<String>,
    #[serde(default)]
    pub source_platform: Option<String>,
    pub source: String,
    pub event_kind: String,
    pub role: Option<String>,
    pub content: String,
    pub scope_hint: Option<MemoryScopeHint>,
    #[serde(default)]
    pub domain: Option<MemoryDomain>,
    #[serde(default)]
    pub observation_at: Option<String>,
    #[serde(default)]
    pub alias_hints: Vec<IdentityAliasHint>,
    pub metadata: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateMemoryRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    #[serde(default)]
    pub actor_account_uid: Option<String>,
    #[serde(default)]
    pub actor_person_uid: Option<String>,
    #[serde(default)]
    pub subject_person_uid: Option<String>,
    #[serde(default)]
    pub source_platform: Option<String>,
    pub scope: MemoryScope,
    pub memory_type: Option<String>,
    pub content: String,
    pub tags: Option<Vec<String>>,
    #[serde(default)]
    pub domain: Option<MemoryDomain>,
    #[serde(default)]
    pub observation_at: Option<String>,
    pub metadata: Option<Value>,
    pub importance: Option<f32>,
    pub sentiment: Option<String>,
    pub source: Option<String>,
    #[serde(default)]
    pub valid_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListMemoriesRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    #[serde(default)]
    pub actor_person_uid: Option<String>,
    #[serde(default)]
    pub subject_person_uid: Option<String>,
    #[serde(default)]
    pub source_platform: Option<String>,
    #[serde(default)]
    pub domain_kind: Option<MemoryDomainKind>,
    #[serde(default)]
    pub domain_key: Option<String>,
    pub scope: Option<MemoryScope>,
    pub state: Option<String>,
    pub memory_type: Option<String>,
    pub content_query: Option<String>,
    pub include_archived: Option<bool>,
    pub limit: Option<usize>,
    pub offset: Option<usize>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ListMemoriesResponse {
    pub items: Vec<MemoryRecord>,
    pub total: usize,
    pub limit: usize,
    pub offset: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateMemoryRequest {
    pub content: Option<String>,
    pub tags: Option<Vec<String>>,
    pub metadata: Option<Value>,
    pub importance: Option<f32>,
    pub sentiment: Option<Option<String>>,
    pub source: Option<String>,
    pub state: Option<String>,
    pub valid_at: Option<Option<String>>,
    pub invalid_at: Option<Option<String>>,
    pub supersedes_memory_id: Option<Option<i64>>,
    pub archived: Option<bool>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UpdateMemoryResponse {
    pub memory: MemoryRecord,
    pub rebuild_task_id: Option<i64>,
    pub rebuild_queued: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportMemoriesResponse {
    pub agent_id: String,
    pub exported_at: String,
    pub count: usize,
    pub items: Vec<MemoryRecord>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExportMemoriesRequest {
    pub agent_id: String,
    pub include_archived: Option<bool>,
}

/* ---------------- graph ---------------- */

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphRequest {
    pub agent_id: String,
    pub limit: Option<usize>,
    pub include_archived: Option<bool>,
    pub state: Option<String>,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    #[serde(default)]
    pub actor_person_uid: Option<String>,
    #[serde(default)]
    pub subject_person_uid: Option<String>,
    #[serde(default)]
    pub source_platform: Option<String>,
    #[serde(default)]
    pub domain_kind: Option<MemoryDomainKind>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphMemoryNode {
    pub id: i64,
    pub scope: MemoryScope,
    pub memory_type: String,
    pub content_preview: String,
    pub state: String,
    pub importance: f32,
    pub session_uid: Option<String>,
    pub actor_person_uid: Option<String>,
    pub subject_person_uid: Option<String>,
    pub source_platform: Option<String>,
    pub domain_kind: MemoryDomainKind,
    pub domain_key: String,
    pub observation_at: Option<String>,
    pub supersedes_memory_id: Option<i64>,
    pub archived_at: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    /// 该记忆挂载的 entity ID 列表（去重，顺序不保证）
    pub entity_ids: Vec<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphEntityNode {
    pub id: i64,
    pub name: String,
    pub entity_type: String,
    pub linked_memory_count: i64,
    /// 仅统计当前 graph 子集中挂载的记忆数量；用于渲染节点大小
    pub local_memory_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphMemoryEntityEdge {
    pub memory_id: i64,
    pub entity_id: i64,
    pub weight: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphSupersedeEdge {
    /// 较新的 memory id（来自 `memories.id`）
    pub from_memory_id: i64,
    /// 被替代的 memory id（来自 `supersedes_memory_id`）
    pub to_memory_id: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct GraphStats {
    pub memory_count: usize,
    pub entity_count: usize,
    pub memory_entity_edges: usize,
    pub supersede_edges: usize,
    pub total_memories_for_agent: usize,
    pub truncated: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphResponse {
    pub agent_id: String,
    pub memories: Vec<GraphMemoryNode>,
    pub entities: Vec<GraphEntityNode>,
    pub memory_entity_edges: Vec<GraphMemoryEntityEdge>,
    pub supersede_edges: Vec<GraphSupersedeEdge>,
    pub stats: GraphStats,
    pub generated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentStatePatch {
    pub mood: Option<String>,
    pub vibe: Option<String>,
    pub mind: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentStateResponse {
    pub agent_id: String,
    pub mood: String,
    pub vibe: String,
    pub mind: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskActionResponse {
    pub status: String,
    pub task_id: Option<i64>,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncSummaryResponse {
    pub by_status: std::collections::BTreeMap<String, usize>,
    pub by_kind: std::collections::BTreeMap<String, usize>,
    pub failed_tasks: usize,
    pub pending_tasks: usize,
    pub oldest_pending_created_at: Option<String>,
    pub latest_error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerEvent {
    pub event: String,
    pub payload: Value,
    pub at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryRecord {
    pub id: i64,
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    pub actor_account_uid: Option<String>,
    pub actor_person_uid: Option<String>,
    pub subject_person_uid: Option<String>,
    pub source_platform: Option<String>,
    pub domain_kind: MemoryDomainKind,
    pub domain_key: String,
    pub observation_at: Option<String>,
    pub scope: MemoryScope,
    pub memory_type: String,
    pub content: String,
    pub content_hash: Option<String>,
    pub source_event_ids: Vec<i64>,
    pub linked_memory_ids: Vec<i64>,
    pub tags: Vec<String>,
    pub metadata: Value,
    pub importance: f32,
    pub sentiment: Option<String>,
    pub source: String,
    pub embedding_json: Option<String>,
    /// Stage 3 lifecycle state. One of: `active / superseded / invalidated / archived`.
    pub state: String,
    pub valid_at: Option<String>,
    pub invalid_at: Option<String>,
    pub supersedes_memory_id: Option<i64>,
    pub created_at: String,
    pub updated_at: String,
    pub archived_at: Option<String>,
    pub access_count: i64,
    pub last_accessed_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryHistoryRecord {
    pub id: i64,
    pub memory_id: Option<i64>,
    pub agent_id: String,
    pub event: String,
    pub old_content: Option<String>,
    pub new_content: Option<String>,
    pub old_metadata: Option<Value>,
    pub new_metadata: Option<Value>,
    pub source_task_id: Option<i64>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryDetailResponse {
    pub memory: MemoryRecord,
    pub entities: Vec<EntityRecord>,
    pub history: Vec<MemoryHistoryRecord>,
}

impl MemoryRecord {
    /// `true` when this memory is currently valid — no supersede, no
    /// invalidation, no archival. Used by recall to drop superseded facts
    /// unless the caller explicitly asked for time-travel.
    pub fn is_currently_valid(&self, now: &str) -> bool {
        if self.state != "active" {
            return false;
        }
        if self.archived_at.is_some() {
            return false;
        }
        if let Some(expired) = &self.invalid_at {
            if expired.as_str() <= now {
                return false;
            }
        }
        true
    }

    pub fn lifecycle(&self) -> MemoryLifecycle {
        MemoryLifecycle {
            state: self.state.clone(),
            valid_at: self.valid_at.clone(),
            invalid_at: self.invalid_at.clone(),
            supersedes_memory_id: self.supersedes_memory_id,
        }
    }

    pub fn effective_time(&self) -> String {
        self.valid_at
            .clone()
            .or_else(|| self.observation_at.clone())
            .unwrap_or_else(|| self.created_at.clone())
    }

    pub fn domain_descriptor(&self) -> MemoryDomain {
        MemoryDomain {
            kind: self.domain_kind,
            key: self.domain_key.clone(),
            platform: self.source_platform.clone(),
            channel_uid: self.channel_uid.clone(),
            session_uid: self.session_uid.clone(),
            person_uid: self.subject_person_uid.clone().or_else(|| self.actor_person_uid.clone()),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawEventRecord {
    pub id: i64,
    pub role: String,
    pub content: String,
    pub created_at: String,
}

/// Stage 2 entity row. `name_norm` is the lowercased/trimmed version of
/// `name_raw` and is the canonical key for `(agent_id, user_uid, entity_type,
/// name_norm)` dedup.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityRecord {
    pub id: i64,
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub name_raw: String,
    pub name_norm: String,
    pub entity_type: String,
    pub linked_memory_count: i64,
    pub created_at: String,
    pub updated_at: String,
}

/// Named recall recipes. See `RECALL_RECIPES.md` for rationale; the enum
/// values are the `recipe` field of `RecallRequest`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RecallRecipe {
    /// Semantic-only, no BM25 / entity / contiguity. Lowest latency.
    Fast,
    /// Semantic + BM25 additive fusion. Default.
    Hybrid,
    /// Semantic + BM25 + entity boost (spread-attenuated).
    EntityHeavy,
    /// Semantic + BM25 + contiguity buffer (session-adjacent memories).
    Contiguous,
}

impl RecallRecipe {
    pub fn parse(raw: Option<&str>) -> Self {
        match raw.map(str::trim).filter(|s| !s.is_empty()) {
            Some("fast") => Self::Fast,
            Some("hybrid") => Self::Hybrid,
            Some("entity_heavy") | Some("entity-heavy") | Some("entity") => Self::EntityHeavy,
            Some("contiguous") | Some("ctg") => Self::Contiguous,
            _ => Self::Hybrid,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Fast => "fast",
            Self::Hybrid => "hybrid",
            Self::EntityHeavy => "entity_heavy",
            Self::Contiguous => "contiguous",
        }
    }

    pub fn use_bm25(&self) -> bool {
        !matches!(self, Self::Fast)
    }

    pub fn use_entity(&self) -> bool {
        matches!(self, Self::EntityHeavy)
    }

    pub fn use_contiguity(&self) -> bool {
        matches!(self, Self::Contiguous)
    }
}

#[derive(Debug, Clone)]
pub struct TaskRecord {
    pub id: i64,
    pub task_type: TaskKind,
    pub status: TaskStatus,
    pub dedupe_key: Option<String>,
    pub agent_id: String,
    pub payload_json: String,
    pub last_error: Option<String>,
    pub retry_count: i64,
    pub created_at: String,
    pub updated_at: String,
    pub started_at: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkerEmbedRequest {
    pub text: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct WorkerEmbedResponse {
    pub embedding: Vec<f32>,
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkerPlanQueryRequest {
    pub query: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct WorkerPlanQueryResponse {
    #[serde(default)]
    pub subqueries: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerScoreTurnRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    #[serde(default)]
    pub actor_account_uid: Option<String>,
    #[serde(default)]
    pub actor_person_uid: Option<String>,
    #[serde(default)]
    pub subject_person_uid: Option<String>,
    #[serde(default)]
    pub source_platform: Option<String>,
    #[serde(default)]
    pub domain: Option<MemoryDomain>,
    pub scope: MemoryScope,
    pub source: String,
    pub messages: Vec<TurnMessage>,
    pub metadata: Value,
    /// Session-scoped previous raw messages (most recent last). Stage 1 addition.
    #[serde(default)]
    pub last_k_events: Vec<TurnMessage>,
    /// Recently extracted memory contents from the same session (most recent first). Stage 1 addition.
    #[serde(default)]
    pub recently_extracted: Vec<String>,
    /// Top-k semantically related existing memories for dedup/linking.
    /// Server hands the worker opaque string indices ("0", "1", ...) to avoid UUID hallucination.
    #[serde(default)]
    pub existing_memories: Vec<ExistingMemoryHint>,
    /// ISO-8601 timestamp describing when the conversation actually happened.
    /// Used by the LLM prompt to ground relative temporal references.
    #[serde(default)]
    pub observation_date: Option<String>,
}

/// Opaque reference to an existing memory passed to the scorer for linking.
///
/// `index` is a stable string identifier for the current scoring call only.
/// The worker echoes selected indices via `WorkerMemoryDraft::linked_existing_indices`,
/// and the server maps them back to real memory ids.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExistingMemoryHint {
    pub index: String,
    pub content: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct WorkerScoreTurnResponse {
    pub memories: Vec<WorkerMemoryDraft>,
    pub state_patch: Option<AgentStatePatch>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerMemoryDraft {
    pub content: String,
    pub tags: Vec<String>,
    pub metadata: Value,
    pub importance: f32,
    pub sentiment: Option<String>,
    pub memory_type: String,
    pub scope: MemoryScope,
    pub source: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    #[serde(default)]
    pub actor_account_uid: Option<String>,
    #[serde(default)]
    pub actor_person_uid: Option<String>,
    #[serde(default)]
    pub subject_person_uid: Option<String>,
    #[serde(default)]
    pub source_platform: Option<String>,
    #[serde(default)]
    pub domain: Option<MemoryDomain>,
    #[serde(default)]
    pub observation_at: Option<String>,
    /// "user" | "assistant" | other — for attribution accounting.
    #[serde(default)]
    pub attributed_to: Option<String>,
    /// Opaque indices from `ExistingMemoryHint::index` that the worker wants to link this draft to.
    /// Server maps these back to real memory ids before persisting.
    #[serde(default)]
    pub linked_existing_indices: Vec<String>,
    /// Entities mentioned by this memory (Stage 2 feature, Stage 1 accepts them as pass-through).
    #[serde(default)]
    pub entities: Vec<EntityDraft>,
    /// Optional ISO-8601 "valid from" timestamp for the fact expressed by this memory.
    /// Populated later in Stage 3 but the field is accepted from day one.
    #[serde(default)]
    pub valid_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EntityDraft {
    pub name: String,
    #[serde(default, alias = "type")]
    pub entity_type: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkerReflectionRequest {
    pub agent_id: String,
    pub memories: Vec<ReflectionMemoryInput>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ReflectionMemoryInput {
    pub id: i64,
    pub content: String,
    pub importance: f32,
    pub scope: MemoryScope,
    pub created_at: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct WorkerReflectionResponse {
    #[serde(default)]
    pub summary_memories: Vec<WorkerMemoryDraft>,
    #[serde(default)]
    pub retire_memory_ids: Vec<i64>,
    #[serde(default)]
    pub state_patch: Option<AgentStatePatch>,
    #[serde(default = "default_empty_report")]
    pub report: Value,
    /// Stage 3: groups of memories the LLM judges to be exact duplicates.
    /// The `keep_id` wins; every `drop_ids` entry becomes `state = superseded`
    /// with `supersedes_memory_id = keep_id`.
    #[serde(default)]
    pub duplicate_groups: Vec<DuplicateGroup>,
    /// Stage 3: memories whose facts are contradicted by a newer memory.
    /// Each entry invalidates `old_id` and (optionally) sets `invalid_at`.
    #[serde(default)]
    pub contradictions: Vec<ContradictionEntry>,
}

fn default_empty_report() -> Value {
    Value::Object(Default::default())
}

/// LLM-identified duplicate cluster. `keep_id` is the canonical memory
/// the remaining `drop_ids` defer to.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DuplicateGroup {
    pub keep_id: i64,
    #[serde(default)]
    pub drop_ids: Vec<i64>,
    #[serde(default)]
    pub reason: Option<String>,
}

/// LLM-identified contradiction between two memories. The `old_id` is the
/// one whose fact no longer holds; the contradiction is either resolved by
/// an existing memory (`new_id`) or by a freshly-authored summary memory
/// (`new_summary_idx` pointing into `summary_memories`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContradictionEntry {
    pub old_id: i64,
    #[serde(default)]
    pub new_id: Option<i64>,
    #[serde(default)]
    pub new_summary_idx: Option<usize>,
    /// ISO-8601 timestamp. Defaults to `now` at the server when absent.
    #[serde(default)]
    pub invalid_at: Option<String>,
    #[serde(default)]
    pub reason: Option<String>,
}

pub fn infer_scope(scope_hint: Option<MemoryScopeHint>, channel_uid: Option<&str>) -> MemoryScope {
    match scope_hint.unwrap_or(MemoryScopeHint::Auto) {
        MemoryScopeHint::Private => MemoryScope::Private,
        MemoryScopeHint::Group => MemoryScope::Group,
        MemoryScopeHint::Shared => MemoryScope::Shared,
        MemoryScopeHint::System => MemoryScope::System,
        MemoryScopeHint::Auto => {
            let channel = channel_uid.unwrap_or_default();
            if channel.contains(":group:") {
                MemoryScope::Group
            } else if channel.contains(":dm:") || channel.contains(":private:") {
                MemoryScope::Private
            } else {
                MemoryScope::Shared
            }
        }
    }
}

pub fn scope_visible_for_request(
    memory: &MemoryRecord,
    user_uid: Option<&str>,
    channel_uid: Option<&str>,
) -> bool {
    match memory.scope {
        MemoryScope::System | MemoryScope::Shared => true,
        MemoryScope::Private => {
            user_uid.is_some()
                && memory.user_uid.as_deref().is_some()
                && memory.user_uid.as_deref() == user_uid
        }
        MemoryScope::Group => {
            channel_uid.is_some()
                && memory.channel_uid.as_deref().is_some()
                && memory.channel_uid.as_deref() == channel_uid
        }
    }
}

pub fn scope_visible_for_selected_request(
    memory: &MemoryRecord,
    user_uid: Option<&str>,
    channel_uid: Option<&str>,
    selected_scopes: &[MemoryScope],
) -> bool {
    if !selected_scopes.contains(&memory.scope) {
        return false;
    }
    scope_visible_for_request(memory, user_uid, channel_uid)
}

#[cfg(test)]
mod tests {
    use super::{
        MemoryDomainKind, MemoryRecord, MemoryScope, MemoryScopeHint, default_recall_scopes,
        infer_scope, scope_visible_for_request, scope_visible_for_selected_request,
        selected_recall_scopes,
    };
    use serde_json::json;

    fn sample_memory(
        scope: MemoryScope,
        user_uid: Option<&str>,
        channel_uid: Option<&str>,
    ) -> MemoryRecord {
        MemoryRecord {
            id: 1,
            agent_id: "shore".to_string(),
            user_uid: user_uid.map(ToString::to_string),
            channel_uid: channel_uid.map(ToString::to_string),
            session_uid: None,
            actor_account_uid: user_uid.map(ToString::to_string),
            actor_person_uid: user_uid.map(ToString::to_string),
            subject_person_uid: user_uid.map(ToString::to_string),
            source_platform: Some("test".to_string()),
            domain_kind: if channel_uid.is_some() {
                MemoryDomainKind::ChannelShared
            } else {
                MemoryDomainKind::GlobalPerson
            },
            domain_key: channel_uid.unwrap_or(user_uid.unwrap_or("global")).to_string(),
            observation_at: None,
            scope,
            memory_type: "event".to_string(),
            content: "hello".to_string(),
            content_hash: None,
            source_event_ids: vec![],
            linked_memory_ids: vec![],
            tags: vec![],
            metadata: json!({}),
            importance: 1.0,
            sentiment: None,
            source: "test".to_string(),
            embedding_json: None,
            state: "active".to_string(),
            valid_at: None,
            invalid_at: None,
            supersedes_memory_id: None,
            created_at: "2026-01-01T00:00:00Z".to_string(),
            updated_at: "2026-01-01T00:00:00Z".to_string(),
            archived_at: None,
            access_count: 0,
            last_accessed_at: None,
        }
    }

    #[test]
    fn infer_scope_from_hint_and_channel() {
        assert_eq!(
            infer_scope(Some(MemoryScopeHint::Private), Some("telegram:dm:1")),
            MemoryScope::Private
        );
        assert_eq!(
            infer_scope(Some(MemoryScopeHint::Group), Some("telegram:dm:1")),
            MemoryScope::Group
        );
        assert_eq!(
            infer_scope(Some(MemoryScopeHint::Auto), Some("telegram:group:1")),
            MemoryScope::Group
        );
        assert_eq!(
            infer_scope(Some(MemoryScopeHint::Auto), Some("telegram:dm:1")),
            MemoryScope::Private
        );
        assert_eq!(
            infer_scope(None, Some("desktop:session")),
            MemoryScope::Shared
        );
    }

    #[test]
    fn recall_recipe_parse_covers_aliases() {
        use crate::types::RecallRecipe;
        assert_eq!(RecallRecipe::parse(Some("fast")), RecallRecipe::Fast);
        assert_eq!(RecallRecipe::parse(Some("hybrid")), RecallRecipe::Hybrid);
        assert_eq!(
            RecallRecipe::parse(Some("entity")),
            RecallRecipe::EntityHeavy
        );
        assert_eq!(
            RecallRecipe::parse(Some("entity_heavy")),
            RecallRecipe::EntityHeavy
        );
        assert_eq!(
            RecallRecipe::parse(Some("entity-heavy")),
            RecallRecipe::EntityHeavy
        );
        assert_eq!(
            RecallRecipe::parse(Some("contiguous")),
            RecallRecipe::Contiguous
        );
        assert_eq!(RecallRecipe::parse(Some("ctg")), RecallRecipe::Contiguous);
        assert_eq!(RecallRecipe::parse(None), RecallRecipe::Hybrid);
        assert_eq!(RecallRecipe::parse(Some("unknown")), RecallRecipe::Hybrid);

        // Flag toggles reflect the intended signal mix.
        assert!(!RecallRecipe::Fast.use_bm25());
        assert!(RecallRecipe::Hybrid.use_bm25());
        assert!(RecallRecipe::EntityHeavy.use_entity());
        assert!(RecallRecipe::Contiguous.use_contiguity());
    }

    #[test]
    fn selected_recall_scopes_extend_default_scope_set() {
        assert_eq!(
            default_recall_scopes(MemoryScope::Group),
            vec![MemoryScope::Group, MemoryScope::Shared, MemoryScope::System]
        );
        assert_eq!(
            selected_recall_scopes(MemoryScope::Group, Some(&[MemoryScope::Private])),
            vec![
                MemoryScope::Group,
                MemoryScope::Shared,
                MemoryScope::System,
                MemoryScope::Private,
            ]
        );
    }

    #[test]
    fn scope_visibility_respects_private_and_group_boundaries() {
        let private_memory = sample_memory(MemoryScope::Private, Some("user:master"), None);
        assert!(scope_visible_for_request(
            &private_memory,
            Some("user:master"),
            None
        ));
        assert!(!scope_visible_for_request(
            &private_memory,
            Some("user:other"),
            None
        ));

        let group_memory = sample_memory(MemoryScope::Group, None, Some("telegram:group:1"));
        assert!(scope_visible_for_request(
            &group_memory,
            None,
            Some("telegram:group:1")
        ));
        assert!(!scope_visible_for_request(
            &group_memory,
            None,
            Some("telegram:group:2")
        ));

        let shared_memory = sample_memory(MemoryScope::Shared, None, None);
        assert!(scope_visible_for_request(&shared_memory, None, None));
    }

    #[test]
    fn selected_scope_visibility_rejects_unselected_scope() {
        let private_memory = sample_memory(MemoryScope::Private, Some("user:master"), None);
        assert!(!scope_visible_for_selected_request(
            &private_memory,
            Some("user:master"),
            None,
            &[MemoryScope::Group, MemoryScope::Shared],
        ));
        assert!(scope_visible_for_selected_request(
            &private_memory,
            Some("user:master"),
            None,
            &[MemoryScope::Private],
        ));
    }
}
