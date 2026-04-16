use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
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

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum MemoryScopeHint {
    Auto,
    Private,
    Group,
    Shared,
    System,
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
    pub query: String,
    pub source: Option<String>,
    pub limit: Option<usize>,
    pub include_state: Option<bool>,
    pub scope_hint: Option<MemoryScopeHint>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallResponse {
    pub memory_context: Vec<MemorySnippet>,
    pub agent_state: Option<AgentStateResponse>,
    pub degraded: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemorySnippet {
    pub id: i64,
    pub time: String,
    pub content: String,
    pub scope: MemoryScope,
    pub score: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TurnEventRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    pub source: String,
    pub scope_hint: Option<MemoryScopeHint>,
    pub messages: Vec<TurnMessage>,
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
    pub source: String,
    pub event_kind: String,
    pub role: Option<String>,
    pub content: String,
    pub scope_hint: Option<MemoryScopeHint>,
    pub metadata: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateMemoryRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    pub scope: MemoryScope,
    pub memory_type: Option<String>,
    pub content: String,
    pub tags: Option<Vec<String>>,
    pub metadata: Option<Value>,
    pub importance: Option<f32>,
    pub sentiment: Option<String>,
    pub source: Option<String>,
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

#[derive(Debug, Clone)]
pub struct MemoryRecord {
    pub id: i64,
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    pub scope: MemoryScope,
    pub memory_type: String,
    pub content: String,
    pub tags: Vec<String>,
    pub metadata: Value,
    pub importance: f32,
    pub sentiment: Option<String>,
    pub source: String,
    pub embedding_json: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub archived_at: Option<String>,
    pub access_count: i64,
    pub last_accessed_at: Option<String>,
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkerScoreTurnRequest {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
    pub scope: MemoryScope,
    pub source: String,
    pub messages: Vec<TurnMessage>,
    pub metadata: Value,
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
    pub summary_memories: Vec<WorkerMemoryDraft>,
    pub retire_memory_ids: Vec<i64>,
    pub state_patch: Option<AgentStatePatch>,
    pub report: Value,
}

pub fn infer_scope(
    scope_hint: Option<MemoryScopeHint>,
    channel_uid: Option<&str>,
) -> MemoryScope {
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

#[cfg(test)]
mod tests {
    use super::{
        MemoryRecord, MemoryScope, MemoryScopeHint, infer_scope, scope_visible_for_request,
    };
    use serde_json::json;

    fn sample_memory(scope: MemoryScope, user_uid: Option<&str>, channel_uid: Option<&str>) -> MemoryRecord {
        MemoryRecord {
            id: 1,
            agent_id: "shore".to_string(),
            user_uid: user_uid.map(ToString::to_string),
            channel_uid: channel_uid.map(ToString::to_string),
            session_uid: None,
            scope,
            memory_type: "event".to_string(),
            content: "hello".to_string(),
            tags: vec![],
            metadata: json!({}),
            importance: 1.0,
            sentiment: None,
            source: "test".to_string(),
            embedding_json: None,
            created_at: "2026-01-01T00:00:00Z".to_string(),
            updated_at: "2026-01-01T00:00:00Z".to_string(),
            archived_at: None,
            access_count: 0,
            last_accessed_at: None,
        }
    }

    #[test]
    fn infer_scope_from_hint_and_channel() {
        assert_eq!(infer_scope(Some(MemoryScopeHint::Private), Some("telegram:dm:1")), MemoryScope::Private);
        assert_eq!(infer_scope(Some(MemoryScopeHint::Group), Some("telegram:dm:1")), MemoryScope::Group);
        assert_eq!(infer_scope(Some(MemoryScopeHint::Auto), Some("telegram:group:1")), MemoryScope::Group);
        assert_eq!(infer_scope(Some(MemoryScopeHint::Auto), Some("telegram:dm:1")), MemoryScope::Private);
        assert_eq!(infer_scope(None, Some("desktop:session")), MemoryScope::Shared);
    }

    #[test]
    fn scope_visibility_respects_private_and_group_boundaries() {
        let private_memory = sample_memory(MemoryScope::Private, Some("user:master"), None);
        assert!(scope_visible_for_request(&private_memory, Some("user:master"), None));
        assert!(!scope_visible_for_request(&private_memory, Some("user:other"), None));

        let group_memory = sample_memory(MemoryScope::Group, None, Some("telegram:group:1"));
        assert!(scope_visible_for_request(&group_memory, None, Some("telegram:group:1")));
        assert!(!scope_visible_for_request(&group_memory, None, Some("telegram:group:2")));

        let shared_memory = sample_memory(MemoryScope::Shared, None, None);
        assert!(scope_visible_for_request(&shared_memory, None, None));
    }
}
