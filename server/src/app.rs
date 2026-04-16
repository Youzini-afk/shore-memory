use std::sync::Arc;

use anyhow::{Context, Result, anyhow};
use axum::extract::Path;
use axum::extract::State;
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use moka::future::Cache;
use serde::Deserialize;
use serde_json::{Value, json};
use tokio::sync::broadcast;
use tokio::time::{sleep, timeout};
use tracing::{error, warn};

use crate::config::ServiceConfig;
use crate::db::{MetadataStore, NewMemoryRecord};
use crate::trivium::TriviumStore;
use crate::types::{
    AgentStatePatch, AgentStateResponse, CreateMemoryRequest, EventMessageRequest, MemoryRecord,
    RecallRequest, RecallResponse, ServerEvent, SyncSummaryResponse, TaskActionResponse, TaskKind,
    TaskRecord, TurnEventRequest, WorkerMemoryDraft,
    infer_scope, scope_visible_for_request,
};
use crate::worker::{WorkerClient, memory_draft_metadata_with_task, reflection_inputs_from_memories};

#[derive(Clone)]
pub struct AppState {
    pub config: ServiceConfig,
    pub store: Arc<MetadataStore>,
    pub trivium: Arc<TriviumStore>,
    pub worker: WorkerClient,
    pub recall_cache: Cache<String, RecallResponse>,
    pub embedding_cache: Cache<String, Vec<f32>>,
    pub events: broadcast::Sender<ServerEvent>,
}

impl AppState {
    pub fn new(
        config: ServiceConfig,
        store: MetadataStore,
        trivium: TriviumStore,
        worker: WorkerClient,
    ) -> Self {
        let (events, _) = broadcast::channel(1024);
        Self {
            recall_cache: Cache::builder()
                .time_to_live(config.recall_cache_ttl)
                .max_capacity(2_048)
                .build(),
            embedding_cache: Cache::builder()
                .time_to_live(config.embedding_cache_ttl)
                .max_capacity(8_192)
                .build(),
            config,
            store: Arc::new(store),
            trivium: Arc::new(trivium),
            worker,
            events,
        }
    }

    pub fn router(self) -> Router {
        Router::new()
            .route("/health", get(health))
            .route("/v1/context/recall", post(recall))
            .route("/v1/events/turn", post(events_turn))
            .route("/v1/events/message", post(events_message))
            .route("/v1/memories", post(create_memory))
            .route(
                "/v1/agents/{agent_id}/state",
                get(get_agent_state).patch(update_agent_state),
            )
            .route("/v1/maintenance/scorer/retry", post(retry_scorer))
            .route("/v1/maintenance/reflection/run", post(run_reflection))
            .route("/v1/maintenance/trivium/rebuild", post(rebuild_trivium))
            .route("/v1/maintenance/sync-summary", get(sync_summary))
            .route("/v1/events", get(events_ws))
            .with_state(self)
    }

    pub fn spawn_background_loops(self: Arc<Self>) {
        tokio::spawn({
            let state = Arc::clone(&self);
            async move {
                loop {
                    if let Err(err) = state.tick_task_queue().await {
                        error!("task queue tick failed: {err:#}");
                    }
                    sleep(state.config.task_poll_interval).await;
                }
            }
        });
    }

    async fn tick_task_queue(&self) -> Result<()> {
        let Some(task) = self.store.claim_next_task()? else {
            return Ok(());
        };

        let result = self.process_task(task.clone()).await;
        match result {
            Ok(()) => {
                self.store.complete_task(task.id)?;
            }
            Err(err) => {
                let message = err.to_string();
                self.store.fail_task(task.id, &message)?;
                self.emit_event("sync.failed", json!({"task_id": task.id, "error": message}))
                    .await;
            }
        }
        Ok(())
    }

    async fn process_task(&self, task: TaskRecord) -> Result<()> {
        match task.task_type {
            TaskKind::ScoreTurn => self.process_score_turn(task).await,
            TaskKind::ReflectionRun => self.process_reflection(task).await,
            TaskKind::RebuildTrivium => self.process_rebuild(task).await,
            TaskKind::IndexMemory => self.process_index_memory(task).await,
        }
    }

    async fn process_score_turn(&self, task: TaskRecord) -> Result<()> {
        let payload: TurnTaskPayload =
            serde_json::from_str(&task.payload_json).context("invalid score_turn payload")?;
        let response = self.worker.score_turn(&payload.request).await?;

        for memory in response.memories {
            self.insert_and_index_draft(task.id, payload.request.agent_id.as_str(), memory)
                .await?;
        }

        if let Some(state_patch) = response.state_patch {
            let state = self
                .store
                .upsert_agent_state(payload.request.agent_id.as_str(), &state_patch)?;
            self.emit_event(
                "agent.state.updated",
                json!({
                    "agent_id": state.agent_id,
                    "mood": state.mood,
                    "vibe": state.vibe,
                    "mind": state.mind,
                }),
            )
            .await;
        }

        Ok(())
    }

    async fn process_reflection(&self, task: TaskRecord) -> Result<()> {
        let payload: MaintenanceAgentRequest =
            serde_json::from_str(&task.payload_json).context("invalid reflection payload")?;
        let candidates = self.store.list_reflection_candidates(&payload.agent_id, 24)?;
        if candidates.len() < 4 {
            self.emit_event(
                "maintenance.completed",
                json!({"task_id": task.id, "kind": "reflection_run", "report": {"reason": "not_enough_candidates"}}),
            )
            .await;
            return Ok(());
        }

        let result = self
            .worker
            .reflect(&payload.agent_id, reflection_inputs_from_memories(&candidates))
            .await?;

        for memory in result.summary_memories {
            self.insert_and_index_draft(task.id, &payload.agent_id, memory)
                .await?;
        }

        if !result.retire_memory_ids.is_empty() {
            self.store.archive_memories(&result.retire_memory_ids)?;
            self.enqueue_task(
                TaskKind::RebuildTrivium,
                &payload.agent_id,
                json!({ "agent_id": payload.agent_id }),
                Some(format!("rebuild:{}", payload.agent_id)),
            )?;
        }

        if let Some(state_patch) = result.state_patch {
            let state = self.store.upsert_agent_state(&payload.agent_id, &state_patch)?;
            self.emit_event(
                "agent.state.updated",
                json!({
                    "agent_id": state.agent_id,
                    "mood": state.mood,
                    "vibe": state.vibe,
                    "mind": state.mind,
                }),
            )
            .await;
        }

        self.emit_event(
            "maintenance.completed",
            json!({
                "task_id": task.id,
                "kind": "reflection_run",
                "report": result.report,
            }),
        )
        .await;

        Ok(())
    }

    async fn process_rebuild(&self, task: TaskRecord) -> Result<()> {
        let payload: MaintenanceAgentRequest =
            serde_json::from_str(&task.payload_json).context("invalid rebuild payload")?;
        let memories = self.store.all_active_memories(&payload.agent_id)?;
        let mut rebuild_items = Vec::with_capacity(memories.len());

        for memory in memories {
            let embedding = if let Some(raw) = memory.embedding_json.as_deref() {
                serde_json::from_str::<Vec<f32>>(raw).unwrap_or_default()
            } else {
                Vec::new()
            };

            let embedding = if embedding.is_empty() {
                let embedding = self.get_or_fetch_embedding(&memory.content).await?;
                self.store
                    .update_memory_embedding(memory.id, &serde_json::to_string(&embedding)?)?;
                embedding
            } else {
                embedding
            };

            rebuild_items.push((memory, embedding));
        }

        let inserted = self.trivium.rebuild(rebuild_items).await?;
        self.recall_cache.invalidate_all();
        self.emit_event(
            "maintenance.completed",
            json!({
                "task_id": task.id,
                "kind": "rebuild_trivium",
                "inserted": inserted,
            }),
        )
        .await;
        Ok(())
    }

    async fn process_index_memory(&self, task: TaskRecord) -> Result<()> {
        let payload: IndexMemoryPayload =
            serde_json::from_str(&task.payload_json).context("invalid index_memory payload")?;
        let memory = self
            .store
            .get_memory_by_id(payload.memory_id)?
            .ok_or_else(|| anyhow!("memory not found for indexing: {}", payload.memory_id))?;

        let embedding = self.get_or_fetch_embedding(&memory.content).await?;
        self.store
            .update_memory_embedding(memory.id, &serde_json::to_string(&embedding)?)?;
        self.trivium
            .insert_memory(memory.clone(), embedding, payload.previous_memory_id)
            .await?;
        self.recall_cache.invalidate_all();
        self.emit_event(
            "memory.indexed",
            json!({"task_id": task.id, "memory_id": memory.id, "agent_id": memory.agent_id}),
        )
        .await;
        Ok(())
    }

    pub async fn handle_recall(&self, request: RecallRequest) -> Result<RecallResponse> {
        let cache_key = cache_key_for_recall(&request);
        if let Some(cached) = self.recall_cache.get(&cache_key).await {
            return Ok(cached);
        }

        let limit = request
            .limit
            .unwrap_or(self.config.search_top_k)
            .clamp(1, 32);
        let embedding = self.get_or_fetch_embedding(&request.query).await.ok();
        let degraded = embedding.is_none();

        let hits = self
            .trivium
            .search(
                request.agent_id.clone(),
                request.user_uid.clone(),
                request.channel_uid.clone(),
                request.query.clone(),
                embedding.clone(),
                limit.saturating_mul(8),
                self.config.search_expand_depth,
                self.config.search_min_score,
            )
            .await
            .unwrap_or_default();

        let mut scored = std::collections::BTreeMap::<i64, f32>::new();
        for hit in &hits {
            scored.insert(hit.id as i64, hit.score);
        }

        let mut selected = Vec::new();
        if !hits.is_empty() {
            let ids: Vec<i64> = hits.iter().map(|hit| hit.id as i64).collect();
            let memory_map = self
                .store
                .list_memories_by_ids(&ids)?
                .into_iter()
                .map(|memory| (memory.id, memory))
                .collect::<std::collections::HashMap<_, _>>();

            for id in ids {
                if selected.len() >= limit {
                    break;
                }
                if let Some(memory) = memory_map.get(&id)
                    && memory.archived_at.is_none()
                    && scope_visible_for_request(
                        memory,
                        request.user_uid.as_deref(),
                        request.channel_uid.as_deref(),
                    ) {
                        selected.push(memory.clone());
                    }
            }
        }

        if selected.len() < limit {
            let query = request.query.to_lowercase();
            let recent = self.store.list_recent_memories(&request.agent_id, 64)?;
            for memory in recent {
                if selected.len() >= limit {
                    break;
                }
                if selected.iter().any(|item| item.id == memory.id) {
                    continue;
                }
                if memory.archived_at.is_some() {
                    continue;
                }
                if !scope_visible_for_request(
                    &memory,
                    request.user_uid.as_deref(),
                    request.channel_uid.as_deref(),
                ) {
                    continue;
                }
                if query.is_empty() || memory.content.to_lowercase().contains(&query) {
                    selected.push(memory);
                }
            }
        }

        let accessed_ids = selected.iter().map(|item| item.id).collect::<Vec<_>>();
        self.store.mark_memories_accessed(&accessed_ids)?;

        let memory_context = selected
            .iter()
            .map(|memory| crate::types::MemorySnippet {
                id: memory.id,
                time: memory.created_at.clone(),
                content: memory.content.clone(),
                scope: memory.scope.clone(),
                score: scored.get(&memory.id).copied(),
            })
            .collect::<Vec<_>>();

        let agent_state = if request.include_state.unwrap_or(false) {
            Some(self.store.get_agent_state(&request.agent_id)?)
        } else {
            None
        };

        let response = RecallResponse {
            memory_context,
            agent_state,
            degraded,
        };
        self.recall_cache.insert(cache_key, response.clone()).await;
        Ok(response)
    }

    pub fn enqueue_task(
        &self,
        kind: TaskKind,
        agent_id: &str,
        payload: Value,
        dedupe_key: Option<String>,
    ) -> Result<TaskRecord> {
        self.store
            .enqueue_task(kind, agent_id, &payload, dedupe_key.as_deref())
    }

    async fn insert_and_index_draft(
        &self,
        task_id: i64,
        agent_id: &str,
        draft: WorkerMemoryDraft,
    ) -> Result<MemoryRecord> {
        let previous_memory_id = self.store.get_latest_memory_id_for_agent(agent_id)?;
        let record = self.store.insert_memory(&NewMemoryRecord {
            agent_id: agent_id.to_string(),
            user_uid: draft.user_uid.clone(),
            channel_uid: draft.channel_uid.clone(),
            session_uid: draft.session_uid.clone(),
            scope: draft.scope.clone(),
            memory_type: draft.memory_type.clone(),
            content: draft.content.clone(),
            tags: draft.tags.clone(),
            metadata: memory_draft_metadata_with_task(task_id, &draft),
            importance: draft.importance,
            sentiment: draft.sentiment.clone(),
            source: draft.source.clone(),
            embedding_json: None,
        })?;

        let embedding = self.get_or_fetch_embedding(&record.content).await?;
        self.store
            .update_memory_embedding(record.id, &serde_json::to_string(&embedding)?)?;
        let updated = self
            .store
            .get_memory_by_id(record.id)?
            .ok_or_else(|| anyhow!("memory vanished after insert: {}", record.id))?;
        self.trivium
            .insert_memory(updated.clone(), embedding, previous_memory_id)
            .await?;
        self.recall_cache.invalidate_all();
        self.emit_event(
            "memory.indexed",
            json!({"memory_id": updated.id, "agent_id": updated.agent_id, "scope": updated.scope.as_str()}),
        )
        .await;
        Ok(updated)
    }

    async fn get_or_fetch_embedding(&self, text: &str) -> Result<Vec<f32>> {
        let key = cache_key_for_text(text);
        if let Some(embedding) = self.embedding_cache.get(&key).await {
            return Ok(embedding);
        }

        let future = self.worker.embed(text);
        let embedding = timeout(self.config.embedding_timeout, future)
            .await
            .context("embedding timeout elapsed")?
            .context("embedding worker returned error")?;

        self.embedding_cache.insert(key, embedding.clone()).await;
        Ok(embedding)
    }

    async fn emit_event(&self, event: &str, payload: Value) {
        let _ = self.events.send(ServerEvent {
            event: event.to_string(),
            payload,
            at: chrono::Utc::now(),
        });
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ServiceError {
    #[error("{0}")]
    BadRequest(String),
    #[error("{0}")]
    Internal(String),
}

impl IntoResponse for ServiceError {
    fn into_response(self) -> Response {
        let (status, message) = match self {
            Self::BadRequest(message) => (StatusCode::BAD_REQUEST, message),
            Self::Internal(message) => (StatusCode::INTERNAL_SERVER_ERROR, message),
        };

        (status, Json(json!({ "error": message }))).into_response()
    }
}

impl From<anyhow::Error> for ServiceError {
    fn from(value: anyhow::Error) -> Self {
        Self::Internal(value.to_string())
    }
}

#[derive(Debug, Clone, Deserialize)]
struct MaintenanceAgentRequest {
    agent_id: String,
}

#[derive(Debug, Clone, Deserialize)]
struct TurnTaskPayload {
    request: crate::types::WorkerScoreTurnRequest,
}

#[derive(Debug, Clone, Deserialize)]
struct IndexMemoryPayload {
    memory_id: i64,
    previous_memory_id: Option<i64>,
}

async fn health(State(state): State<AppState>) -> Result<Json<Value>, ServiceError> {
    let worker = state.worker.health().await.is_ok();
    let summary = state.store.get_sync_summary()?;
    Ok(Json(json!({
        "status": "ok",
        "worker_available": worker,
        "pending_tasks": summary.pending_tasks,
        "failed_tasks": summary.failed_tasks,
        "metadata_db_path": state.store.db_path().display().to_string(),
    })))
}

async fn recall(
    State(state): State<AppState>,
    Json(request): Json<RecallRequest>,
) -> Result<Json<RecallResponse>, ServiceError> {
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if request.query.trim().is_empty() {
        return Err(ServiceError::BadRequest("query is required".to_string()));
    }
    let response = state.handle_recall(request).await?;
    Ok(Json(response))
}

async fn events_turn(
    State(state): State<AppState>,
    Json(request): Json<TurnEventRequest>,
) -> Result<(StatusCode, Json<TaskActionResponse>), ServiceError> {
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if request.messages.is_empty() {
        return Err(ServiceError::BadRequest("messages cannot be empty".to_string()));
    }

    let scope = infer_scope(request.scope_hint.clone(), request.channel_uid.as_deref());
    let metadata = request.metadata.clone().unwrap_or_else(|| json!({}));
    let pairs = request
        .messages
        .iter()
        .map(|msg| (msg.role.clone(), msg.content.clone()))
        .collect::<Vec<_>>();
    state.store.insert_raw_turn(
        &request.agent_id,
        request.user_uid.as_deref(),
        request.channel_uid.as_deref(),
        request.session_uid.as_deref(),
        &scope,
        &request.source,
        &pairs,
        &metadata,
    )?;

    let task = state.enqueue_task(
        TaskKind::ScoreTurn,
        &request.agent_id,
        json!({
            "request": {
                "agent_id": request.agent_id,
                "user_uid": request.user_uid,
                "channel_uid": request.channel_uid,
                "session_uid": request.session_uid,
                "scope": scope,
                "source": request.source,
                "messages": request.messages,
                "metadata": metadata,
            }
        }),
        Some(format!(
            "score_turn:{}:{}:{}",
            request.agent_id,
            request.session_uid.clone().unwrap_or_else(|| "none".to_string()),
            blake3::hash(request.messages.iter().map(|item| item.content.as_str()).collect::<Vec<_>>().join("\n").as_bytes()).to_hex()
        )),
    )?;

    Ok((
        StatusCode::ACCEPTED,
        Json(TaskActionResponse {
            status: "queued".to_string(),
            task_id: Some(task.id),
            message: "turn persisted and scoring queued".to_string(),
        }),
    ))
}

async fn events_message(
    State(state): State<AppState>,
    Json(request): Json<EventMessageRequest>,
) -> Result<(StatusCode, Json<TaskActionResponse>), ServiceError> {
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if request.content.trim().is_empty() {
        return Err(ServiceError::BadRequest("content is required".to_string()));
    }
    let scope = infer_scope(request.scope_hint.clone(), request.channel_uid.as_deref());
    let metadata = request.metadata.clone().unwrap_or_else(|| json!({}));
    let role = request.role.clone().unwrap_or_else(|| "system".to_string());

    state.store.insert_raw_message(
        &request.event_kind,
        &request.agent_id,
        request.user_uid.as_deref(),
        request.channel_uid.as_deref(),
        request.session_uid.as_deref(),
        &scope,
        &role,
        &request.content,
        &request.source,
        &metadata,
    )?;

    let maybe_task = if matches!(role.as_str(), "user" | "assistant" | "system") {
        Some(state.enqueue_task(
            TaskKind::ScoreTurn,
            &request.agent_id,
            json!({
                "request": {
                    "agent_id": request.agent_id,
                    "user_uid": request.user_uid,
                    "channel_uid": request.channel_uid,
                    "session_uid": request.session_uid,
                    "scope": scope,
                    "source": request.source,
                    "messages": [{ "role": role, "content": request.content }],
                    "metadata": metadata,
                }
            }),
            None,
        )?)
    } else {
        None
    };

    Ok((
        StatusCode::ACCEPTED,
        Json(TaskActionResponse {
            status: "accepted".to_string(),
            task_id: maybe_task.map(|task| task.id),
            message: "message event persisted".to_string(),
        }),
    ))
}

async fn create_memory(
    State(state): State<AppState>,
    Json(request): Json<CreateMemoryRequest>,
) -> Result<(StatusCode, Json<Value>), ServiceError> {
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if request.content.trim().is_empty() {
        return Err(ServiceError::BadRequest("content is required".to_string()));
    }

    let previous_memory_id = state.store.get_latest_memory_id_for_agent(&request.agent_id)?;
    let record = state.store.insert_memory(&NewMemoryRecord {
        agent_id: request.agent_id.clone(),
        user_uid: request.user_uid.clone(),
        channel_uid: request.channel_uid.clone(),
        session_uid: request.session_uid.clone(),
        scope: request.scope.clone(),
        memory_type: request.memory_type.clone().unwrap_or_else(|| "event".to_string()),
        content: request.content.clone(),
        tags: request.tags.clone().unwrap_or_default(),
        metadata: request.metadata.clone().unwrap_or_else(|| json!({})),
        importance: request.importance.unwrap_or(5.0),
        sentiment: request.sentiment.clone(),
        source: request.source.clone().unwrap_or_else(|| "manual".to_string()),
        embedding_json: None,
    })?;

    let task = state.enqueue_task(
        TaskKind::IndexMemory,
        &request.agent_id,
        json!({"memory_id": record.id, "previous_memory_id": previous_memory_id}),
        Some(format!("index_memory:{}", record.id)),
    )?;

    Ok((
        StatusCode::ACCEPTED,
        Json(json!({
            "status": "queued",
            "memory_id": record.id,
            "task_id": task.id,
        })),
    ))
}

async fn get_agent_state(
    Path(agent_id): Path<String>,
    State(state): State<AppState>,
) -> Result<Json<AgentStateResponse>, ServiceError> {
    Ok(Json(state.store.get_agent_state(&agent_id)?))
}

async fn update_agent_state(
    Path(agent_id): Path<String>,
    State(state): State<AppState>,
    Json(patch): Json<AgentStatePatch>,
) -> Result<Json<AgentStateResponse>, ServiceError> {
    if patch.mood.is_none() && patch.vibe.is_none() && patch.mind.is_none() {
        return Err(ServiceError::BadRequest(
            "at least one of mood/vibe/mind must be set".to_string(),
        ));
    }

    let response = state.store.upsert_agent_state(&agent_id, &patch)?;
    state
        .emit_event(
            "agent.state.updated",
            json!({
                "agent_id": response.agent_id,
                "mood": response.mood,
                "vibe": response.vibe,
                "mind": response.mind,
            }),
        )
        .await;
    Ok(Json(response))
}

async fn retry_scorer(
    State(state): State<AppState>,
    Json(request): Json<MaintenanceAgentRequest>,
) -> Result<Json<TaskActionResponse>, ServiceError> {
    let retried = state
        .store
        .retry_failed_tasks(TaskKind::ScoreTurn, Some(&request.agent_id))?;
    state
        .emit_event(
            "maintenance.completed",
            json!({
                "kind": "retry_scorer",
                "agent_id": request.agent_id,
                "retried": retried,
            }),
        )
        .await;
    Ok(Json(TaskActionResponse {
        status: "ok".to_string(),
        task_id: None,
        message: format!("retried {retried} failed scorer tasks"),
    }))
}

async fn run_reflection(
    State(state): State<AppState>,
    Json(request): Json<MaintenanceAgentRequest>,
) -> Result<(StatusCode, Json<TaskActionResponse>), ServiceError> {
    let task = state.enqueue_task(
        TaskKind::ReflectionRun,
        &request.agent_id,
        json!({ "agent_id": request.agent_id }),
        Some(format!("reflection:{}", request.agent_id)),
    )?;
    Ok((
        StatusCode::ACCEPTED,
        Json(TaskActionResponse {
            status: "queued".to_string(),
            task_id: Some(task.id),
            message: "reflection queued".to_string(),
        }),
    ))
}

async fn rebuild_trivium(
    State(state): State<AppState>,
    Json(request): Json<MaintenanceAgentRequest>,
) -> Result<(StatusCode, Json<TaskActionResponse>), ServiceError> {
    let task = state.enqueue_task(
        TaskKind::RebuildTrivium,
        &request.agent_id,
        json!({ "agent_id": request.agent_id }),
        Some(format!("rebuild:{}", request.agent_id)),
    )?;
    Ok((
        StatusCode::ACCEPTED,
        Json(TaskActionResponse {
            status: "queued".to_string(),
            task_id: Some(task.id),
            message: "rebuild queued".to_string(),
        }),
    ))
}

async fn sync_summary(
    State(state): State<AppState>,
) -> Result<Json<SyncSummaryResponse>, ServiceError> {
    Ok(Json(state.store.get_sync_summary()?))
}

async fn events_ws(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_events_socket(socket, state))
}

async fn handle_events_socket(mut socket: WebSocket, state: AppState) {
    let mut rx = state.events.subscribe();
    loop {
        tokio::select! {
            maybe_message = socket.recv() => {
                match maybe_message {
                    Some(Ok(Message::Close(_))) | None => break,
                    Some(Ok(Message::Ping(payload))) => {
                        if socket.send(Message::Pong(payload)).await.is_err() {
                            break;
                        }
                    }
                    Some(Ok(_)) => {}
                    Some(Err(err)) => {
                        warn!("websocket receive error: {err}");
                        break;
                    }
                }
            }
            event = rx.recv() => {
                match event {
                    Ok(event) => {
                        match serde_json::to_string(&event) {
                            Ok(text) => {
                                if socket.send(Message::Text(text.into())).await.is_err() {
                                    break;
                                }
                            }
                            Err(err) => {
                                warn!("failed to serialize server event: {err}");
                            }
                        }
                    }
                    Err(err) => {
                        warn!("event broadcast receive error: {err}");
                        break;
                    }
                }
            }
        }
    }
}

fn cache_key_for_recall(request: &RecallRequest) -> String {
    blake3::hash(
        serde_json::to_string(request)
            .unwrap_or_else(|_| request.query.clone())
            .as_bytes(),
    )
    .to_hex()
    .to_string()
}

fn cache_key_for_text(text: &str) -> String {
    blake3::hash(text.trim().as_bytes()).to_hex().to_string()
}
