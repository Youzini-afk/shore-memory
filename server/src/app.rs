use std::sync::Arc;

use anyhow::{Context, Result, anyhow, bail};
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{Path, Query, Request, State};
use axum::http::{HeaderMap, HeaderName, StatusCode, header};
use axum::middleware::from_fn_with_state;
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use metrics::{counter, gauge, histogram};
use metrics_exporter_prometheus::PrometheusHandle;
use moka::future::Cache;
use serde::Deserialize;
use serde_json::{Value, json};
use tokio::sync::{RwLock, broadcast};
use tokio::time::{sleep, timeout};
use tower_http::request_id::{MakeRequestUuid, PropagateRequestIdLayer, SetRequestIdLayer};
use tower_http::services::{ServeDir, ServeFile};
use tower_http::trace::TraceLayer;
use tracing::{error, info, warn};

use crate::config::ServiceConfig;
use crate::db::{LoadedMemoryGraph, MetadataStore, NewMemoryRecord};
use crate::model_config::{
    DetectEmbeddingDimensionRequest, DetectEmbeddingDimensionResponse, ListProviderModelsRequest,
    ListProviderModelsResponse, ModelConfigFile, ModelConfigResponse, ModelConfigTestResponse,
    ProviderKind, ProviderTestResponse, ResolvedProviderProbe, RuntimeModelConfig,
    UpdateModelConfigRequest, UpdateModelConfigResponse, apply_update, delete_model_config_file,
    load_runtime_model_config, resolve_provider_probe, resolve_runtime_model_config,
    write_model_config_file,
};
use crate::recall_recipe::{
    FusionInputs, FusionWeights, additive_fuse, bm25_params_for_query, entity_spread_attenuation,
    normalize_bm25,
};
use crate::trivium::{EntityTriviumStore, TriviumStore};
use crate::types::{
    AgentStatePatch, AgentStateResponse, CreateMemoryRequest, EntityDraft, EntityRecord,
    EventMessageRequest, ExistingMemoryHint, ExportMemoriesRequest, ExportMemoriesResponse,
    GraphEntityNode, GraphMemoryEntityEdge, GraphMemoryNode, GraphRequest, GraphResponse,
    GraphStats, GraphSupersedeEdge, ListMemoriesRequest, ListMemoriesResponse,
    MemoryDetailResponse, MemoryRecord, MemoryScope, MemorySnippet, RecallRecipe, RecallRequest,
    RecallResponse, ScoreBreakdown, ServerEvent, SyncSummaryResponse, TaskActionResponse, TaskKind,
    TaskRecord, TurnEventRequest, TurnMessage, UpdateMemoryRequest, UpdateMemoryResponse,
    WorkerMemoryDraft, WorkerScoreTurnRequest, infer_scope, scope_visible_for_selected_request,
    selected_recall_scopes,
};
use crate::worker::{
    WorkerClient, memory_draft_metadata_with_task, reflection_inputs_from_memories,
};

/// Number of previous raw events from the same session to send to the scorer.
const SCORER_LAST_K_EVENTS: usize = 10;
/// Number of recently extracted memories (same session) to send to the scorer.
const SCORER_RECENTLY_EXTRACTED: usize = 10;
/// Number of semantically related existing memories offered to the scorer for
/// deduplication & linking. Opaque indices ("0", "1", ...) are used so the LLM
/// never sees real UUIDs.
const SCORER_EXISTING_POOL_SIZE: usize = 10;
const RECALL_CACHE_KEY_VERSION: &str = "v2";

#[derive(Clone)]
pub struct AppState {
    pub config: ServiceConfig,
    pub store: Arc<MetadataStore>,
    pub trivium: Arc<TriviumStore>,
    pub entity_trivium: Arc<EntityTriviumStore>,
    pub metrics_handle: Arc<PrometheusHandle>,
    pub worker: WorkerClient,
    pub recall_cache: Cache<String, RecallResponse>,
    pub recall_epoch: Cache<String, u64>,
    pub embedding_cache: Cache<String, Vec<f32>>,
    pub events: broadcast::Sender<ServerEvent>,
    pub reindex_lock: Arc<RwLock<()>>,
}

impl AppState {
    pub fn new(
        config: ServiceConfig,
        store: MetadataStore,
        trivium: TriviumStore,
        entity_trivium: EntityTriviumStore,
        metrics_handle: PrometheusHandle,
        worker: WorkerClient,
    ) -> Self {
        let event_channel_cap = std::env::var("PMS_EVENT_CHANNEL_CAP")
            .ok()
            .and_then(|s| s.parse::<usize>().ok())
            .unwrap_or(1024)
            .max(16);
        let (events, _) = broadcast::channel(event_channel_cap);
        Self {
            recall_cache: Cache::builder()
                .time_to_live(config.recall_cache_ttl)
                .max_capacity(2_048)
                .build(),
            recall_epoch: Cache::builder().max_capacity(4_096).build(),
            embedding_cache: Cache::builder()
                .time_to_live(config.embedding_cache_ttl)
                .max_capacity(8_192)
                .build(),
            config,
            store: Arc::new(store),
            trivium: Arc::new(trivium),
            entity_trivium: Arc::new(entity_trivium),
            metrics_handle: Arc::new(metrics_handle),
            worker,
            events,
            reindex_lock: Arc::new(RwLock::new(())),
        }
    }

    pub fn router(self) -> Router {
        let request_id_header = HeaderName::from_static("x-request-id");
        let web_dist = self.config.web_dist_path.clone();
        let mut v1_router = Router::new()
            .route("/v1/context/recall", post(recall))
            .route("/v1/events/turn", post(events_turn))
            .route("/v1/events/message", post(events_message))
            .route("/v1/memories", get(list_memories).post(create_memory))
            .route("/v1/memories/export", get(export_memories))
            .route(
                "/v1/memories/{memory_id}",
                get(get_memory).patch(update_memory),
            )
            .route("/v1/graph", get(graph))
            .route(
                "/v1/agents/{agent_id}/state",
                get(get_agent_state).patch(update_agent_state),
            )
            .route("/v1/maintenance/scorer/retry", post(retry_scorer))
            .route("/v1/maintenance/reflection/run", post(run_reflection))
            .route("/v1/maintenance/trivium/rebuild", post(rebuild_trivium))
            .route("/v1/maintenance/sync-summary", get(sync_summary))
            .route(
                "/v1/model-config",
                get(get_model_config)
                    .put(update_model_config)
                    .delete(restore_model_config_defaults),
            )
            .route("/v1/model-config/models", post(list_provider_models))
            .route(
                "/v1/model-config/embedding/dimension",
                post(detect_embedding_dimension),
            )
            .route("/v1/model-config/test", post(test_model_config))
            .route("/v1/events", get(events_ws));

        if self.config.api_key.is_some() {
            v1_router = v1_router.layer(from_fn_with_state(self.clone(), require_api_key));
        }

        let api_router = Router::new()
            .route("/health", get(health))
            .route("/metrics", get(metrics))
            .merge(v1_router)
            .with_state(self);

        let router = match web_dist.as_ref() {
            Some(dir) if dir.join("index.html").exists() => {
                info!("serving web UI from {}", dir.display());
                let index = dir.join("index.html");
                let spa_fallback = ServeFile::new(index);
                let static_service = ServeDir::new(dir).fallback(spa_fallback);
                api_router.fallback_service(static_service)
            }
            _ => api_router,
        };

        router
            .layer(TraceLayer::new_for_http())
            .layer(PropagateRequestIdLayer::new(request_id_header.clone()))
            .layer(SetRequestIdLayer::new(request_id_header, MakeRequestUuid))
    }

    pub fn spawn_background_loops(self: Arc<Self>) {
        for worker_idx in 0..self.config.task_workers {
            tokio::spawn({
                let state = Arc::clone(&self);
                async move {
                    loop {
                        if let Err(err) = state.tick_task_queue().await {
                            error!("task queue tick failed (worker={}): {err:#}", worker_idx);
                        }
                        sleep(state.config.task_poll_interval).await;
                    }
                }
            });
        }
        if let Some(reflection_interval) = self.config.reflection_interval {
            tokio::spawn({
                let state = Arc::clone(&self);
                async move {
                    loop {
                        sleep(reflection_interval).await;
                        if let Err(err) = state.enqueue_periodic_reflection() {
                            error!("periodic reflection scheduling failed: {err:#}");
                        }
                    }
                }
            });
        }
    }

    fn allowed_recall_scopes(
        &self,
        request_scope: MemoryScope,
        selected_scopes: &[MemoryScope],
    ) -> Vec<MemoryScope> {
        selected_scopes
            .iter()
            .copied()
            .filter(|scope| {
                self.config
                    .scope_recall
                    .weight(request_scope, *scope)
                    .is_some()
            })
            .collect()
    }

    fn enqueue_periodic_reflection(&self) -> Result<()> {
        for agent_id in self.store.list_agents_with_memories()? {
            let payload = json!({ "agent_id": agent_id.clone() });
            let dedupe_key = format!("reflection:{agent_id}");
            let _ = self.enqueue_task(
                TaskKind::ReflectionRun,
                &agent_id,
                payload,
                Some(dedupe_key),
            )?;
        }
        Ok(())
    }

    async fn tick_task_queue(&self) -> Result<()> {
        if let Ok(summary) = self.store.get_sync_summary() {
            gauge!("shore_memory_task_queue_depth", "status" => "pending")
                .set(summary.pending_tasks as f64);
            gauge!("shore_memory_task_queue_depth", "status" => "failed")
                .set(summary.failed_tasks as f64);
        }
        let Some(task) = self.store.claim_next_task()? else {
            return Ok(());
        };

        let kind_label = task.task_type.as_metric_label();
        let started = std::time::Instant::now();

        let result = self.process_task(task.clone()).await;
        match result {
            Ok(()) => {
                self.store.complete_task(task.id)?;
                histogram!("shore_memory_task_processing_duration_seconds", "kind" => kind_label, "status" => "ok")
                    .record(started.elapsed().as_secs_f64());
            }
            Err(err) => {
                let message = err.to_string();
                self.store.fail_task(task.id, &message)?;
                counter!("shore_memory_task_errors_total", "kind" => kind_label).increment(1);
                histogram!("shore_memory_task_processing_duration_seconds", "kind" => kind_label, "status" => "error")
                    .record(started.elapsed().as_secs_f64());
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

    #[tracing::instrument(skip(self, task), fields(task_id = task.id, task_kind = "score_turn"))]
    async fn process_score_turn(&self, task: TaskRecord) -> Result<()> {
        let payload: TurnTaskPayload =
            serde_json::from_str(&task.payload_json).context("invalid score_turn payload")?;
        let agent_id = payload.request.agent_id.clone();
        let session_uid = payload.request.session_uid.clone();
        let source_event_ids = payload.source_event_ids.clone();

        // Phase 1: gather session-scoped short-term context.
        let last_k_raw = self
            .store
            .list_recent_raw_events_for_session(
                &agent_id,
                session_uid.as_deref(),
                SCORER_LAST_K_EVENTS,
            )
            .unwrap_or_default();
        let last_k_events: Vec<TurnMessage> = last_k_raw
            .into_iter()
            .map(|ev| TurnMessage {
                role: ev.role,
                content: ev.content,
            })
            .collect();
        let recently_extracted = self
            .store
            .list_recent_memories_by_session(
                &agent_id,
                session_uid.as_deref(),
                SCORER_RECENTLY_EXTRACTED,
            )
            .unwrap_or_default();

        // Phase 2: retrieve top-k semantically related existing memories for
        // dedup + linking. Opaque indices ("0", "1", ...) are used so the LLM
        // never sees real UUIDs and cannot hallucinate identifiers.
        let query_text = payload
            .request
            .messages
            .iter()
            .map(|msg| msg.content.as_str())
            .collect::<Vec<_>>()
            .join("\n");
        let existing_pool = self
            .fetch_existing_dedup_pool(&query_text, &payload.request)
            .await
            .unwrap_or_default();
        let id_by_index: std::collections::HashMap<String, i64> = existing_pool
            .iter()
            .map(|(idx, mem)| (idx.clone(), mem.id))
            .collect();

        // Phase 3: build the enriched request and call the scorer.
        let mut enriched = payload.request.clone();
        enriched.last_k_events = last_k_events;
        enriched.recently_extracted = recently_extracted;
        enriched.existing_memories = existing_pool
            .iter()
            .map(|(idx, mem)| ExistingMemoryHint {
                index: idx.clone(),
                content: mem.content.clone(),
            })
            .collect();
        if enriched.observation_date.is_none() {
            enriched.observation_date = Some(chrono::Utc::now().to_rfc3339());
        }

        let score_started = std::time::Instant::now();
        let response = self.worker.score_turn(&enriched).await.map_err(|err| {
            counter!("shore_memory_worker_call_errors_total", "op" => "score_turn").increment(1);
            err
        })?;
        histogram!("shore_memory_worker_call_duration_seconds", "op" => "score_turn")
            .record(score_started.elapsed().as_secs_f64());

        // Phase 4: per-draft hash dedup + linked memory mapping + history.
        // Entities extracted by the LLM are collected here; Phase 5 lands them
        // once we know the concrete memory_id each draft landed as.
        let mut entity_pairs: Vec<(i64, EntityDraft)> = Vec::new();
        for mut draft in response.memories {
            let normalized = draft.content.trim();
            if normalized.is_empty() {
                continue;
            }
            let content_hash = blake3::hash(normalized.as_bytes()).to_hex().to_string();

            if let Some(existing) = self.store.find_memory_by_hash(&agent_id, &content_hash)? {
                // Same agent already has this exact content. Record the skip for
                // observability (so operators can tell a noop from a lost turn).
                self.store.insert_memory_history(
                    Some(existing.id),
                    &agent_id,
                    "skip_dup",
                    Some(&existing.content),
                    Some(&draft.content),
                    None,
                    None,
                    Some(task.id),
                )?;
                continue;
            }

            // Map opaque indices from `linked_existing_indices` (e.g. "0", "3")
            // back to real memory ids. Unknown indices are silently dropped.
            let linked_memory_ids: Vec<i64> = draft
                .linked_existing_indices
                .iter()
                .filter_map(|idx| id_by_index.get(idx.as_str()).copied())
                .collect();

            // Pull entities out before we move the draft into `insert_and_index_draft`.
            let draft_entities = std::mem::take(&mut draft.entities);

            let inserted = self
                .insert_and_index_draft(
                    task.id,
                    &agent_id,
                    draft,
                    Some(content_hash),
                    source_event_ids.clone(),
                    linked_memory_ids,
                )
                .await?;

            for entity in draft_entities {
                entity_pairs.push((inserted.id, entity));
            }

            self.store.insert_memory_history(
                Some(inserted.id),
                &agent_id,
                "add",
                None,
                Some(&inserted.content),
                None,
                Some(&inserted.metadata),
                Some(task.id),
            )?;
        }

        // Phase 5: entity landing — dedup, upsert into `entities`, index new
        // ones into the entity Trivium, and link to memory_ids. Non-fatal: any
        // failure here is logged but must not block a successful score pass.
        if !entity_pairs.is_empty() {
            if let Err(err) = self
                .land_entities_for_drafts(
                    &agent_id,
                    payload.request.user_uid.as_deref(),
                    entity_pairs,
                )
                .await
            {
                warn!("stage2 entity landing failed: {err:#}");
            }
        }

        if let Some(state_patch) = response.state_patch {
            let state = self.store.upsert_agent_state(&agent_id, &state_patch)?;
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

    /// Assemble an opaque existing-memory pool for the scorer prompt.
    ///
    /// The returned vec is indexed by position-as-string ("0", "1", ...); the
    /// server later uses this mapping to translate the LLM's
    /// `linked_existing_indices` back into real memory ids. Scope-visibility
    /// filtering is applied so cross-user contamination is impossible.
    async fn fetch_existing_dedup_pool(
        &self,
        query_text: &str,
        request: &WorkerScoreTurnRequest,
    ) -> Result<Vec<(String, MemoryRecord)>> {
        let _reindex_guard = self.reindex_lock.read().await;
        if query_text.trim().is_empty() {
            return Ok(Vec::new());
        }

        // Embedding is best-effort: if the worker is unavailable we still hand
        // over any BM25 hits trivium returns.
        let embedding = self.get_or_fetch_embedding(query_text).await.ok();
        let selected_scopes = selected_recall_scopes(request.scope, None);
        let allowed_scopes = self.allowed_recall_scopes(request.scope, &selected_scopes);

        let hits = self
            .trivium
            .search(
                request.agent_id.clone(),
                request.user_uid.clone(),
                request.channel_uid.clone(),
                allowed_scopes.clone(),
                query_text.to_string(),
                embedding,
                SCORER_EXISTING_POOL_SIZE.saturating_mul(2).max(1),
                self.config.search_expand_depth,
                self.config.search_min_score,
                false,
            )
            .await
            .unwrap_or_default();

        if hits.is_empty() {
            return Ok(Vec::new());
        }

        let ids: Vec<i64> = hits.iter().map(|hit| hit.id as i64).collect();
        let records = self.store.list_memories_by_ids(&ids)?;
        let record_by_id: std::collections::HashMap<i64, MemoryRecord> =
            records.into_iter().map(|mem| (mem.id, mem)).collect();

        let now = chrono::Utc::now().to_rfc3339();
        let mut out: Vec<(String, MemoryRecord)> = Vec::new();
        for id in ids {
            if out.len() >= SCORER_EXISTING_POOL_SIZE {
                break;
            }
            if let Some(mem) = record_by_id.get(&id) {
                if mem.archived_at.is_some() {
                    continue;
                }
                if !scope_visible_for_selected_request(
                    mem,
                    request.user_uid.as_deref(),
                    request.channel_uid.as_deref(),
                    &allowed_scopes,
                ) {
                    continue;
                }
                // Stage 3: don't feed superseded / invalidated memories into
                // the scorer pool — the LLM would otherwise be tempted to
                // re-link or re-extract a fact we've already retired.
                if !mem.is_currently_valid(&now) {
                    continue;
                }
                let idx = out.len().to_string();
                out.push((idx, mem.clone()));
            }
        }
        Ok(out)
    }

    /// Stage 2 entity landing pipeline.
    ///
    /// Given the `(memory_id, entity_draft)` pairs produced by Phase 4, this
    /// method:
    ///   1. Dedups by `(name_norm, entity_type)` within the batch.
    ///   2. Upserts each unique entity into `entities` via `MetadataStore`.
    ///   3. Batch-embeds the names of newly-created entities and inserts them
    ///      into the entity Trivium.
    ///   4. Creates `entity_memory_links` rows for every `(memory, entity)`.
    ///
    /// Failures at any individual step are logged; the method as a whole still
    /// returns `Ok(())` unless the SQL upsert itself fails, because entity
    /// landing is a recall-quality enhancer rather than a correctness
    /// requirement.
    async fn land_entities_for_drafts(
        &self,
        agent_id: &str,
        user_uid: Option<&str>,
        pairs: Vec<(i64, EntityDraft)>,
    ) -> Result<()> {
        let _reindex_guard = self.reindex_lock.read().await;
        use crate::db::MetadataStore;
        use std::collections::HashMap;

        if pairs.is_empty() {
            return Ok(());
        }

        // Step 1: dedup by (name_norm, entity_type) across the batch.
        struct UniqueEntity {
            name_raw: String,
            entity_type: String,
        }
        let mut unique_entities: Vec<UniqueEntity> = Vec::new();
        let mut key_to_idx: HashMap<(String, String), usize> = HashMap::new();
        let mut draft_to_key_idx: Vec<Option<usize>> = Vec::with_capacity(pairs.len());

        for (_memory_id, entity) in &pairs {
            let name_raw = entity.name.trim().to_string();
            let entity_type = if entity.entity_type.trim().is_empty() {
                "OTHER".to_string()
            } else {
                entity.entity_type.trim().to_string()
            };
            let name_norm = MetadataStore::normalize_entity_name(&name_raw);
            if name_norm.is_empty() {
                draft_to_key_idx.push(None);
                continue;
            }
            let key = (name_norm, entity_type.clone());
            let idx = if let Some(&existing) = key_to_idx.get(&key) {
                existing
            } else {
                let new_idx = unique_entities.len();
                unique_entities.push(UniqueEntity {
                    name_raw,
                    entity_type,
                });
                key_to_idx.insert(key, new_idx);
                new_idx
            };
            draft_to_key_idx.push(Some(idx));
        }

        if unique_entities.is_empty() {
            return Ok(());
        }

        // Step 2: upsert each unique entity. Track which ones were newly
        // created so we only pay the embed + Trivium-insert cost for those.
        let mut entity_records: Vec<EntityRecord> = Vec::with_capacity(unique_entities.len());
        let mut newly_created: Vec<usize> = Vec::new();
        for (i, unique) in unique_entities.iter().enumerate() {
            match self.store.upsert_entity(
                agent_id,
                user_uid,
                &unique.name_raw,
                &unique.entity_type,
            ) {
                Ok((record, created)) => {
                    if created {
                        newly_created.push(i);
                    }
                    entity_records.push(record);
                }
                Err(err) => {
                    warn!(
                        "upsert_entity failed for name='{}' type='{}': {:#}",
                        unique.name_raw, unique.entity_type, err
                    );
                    // Record a sentinel so the index layout stays aligned.
                    entity_records.push(EntityRecord {
                        id: -1,
                        agent_id: agent_id.to_string(),
                        user_uid: user_uid.map(str::to_string),
                        name_raw: unique.name_raw.clone(),
                        name_norm: MetadataStore::normalize_entity_name(&unique.name_raw),
                        entity_type: unique.entity_type.clone(),
                        linked_memory_count: 0,
                        created_at: String::new(),
                        updated_at: String::new(),
                    });
                }
            }
        }

        // Step 3: batch-embed names of newly-created entities and index them
        // into the entity Trivium. Best-effort — embedding failures don't
        // block the memory_entity_links write in step 4.
        if !newly_created.is_empty() {
            let texts: Vec<String> = newly_created
                .iter()
                .map(|&i| entity_records[i].name_raw.clone())
                .collect();
            match self.worker.embed_batch(texts.clone()).await {
                Ok(embeddings) if embeddings.len() == texts.len() => {
                    for (slot, &entity_idx) in newly_created.iter().enumerate() {
                        let record = &entity_records[entity_idx];
                        if record.id < 0 {
                            continue;
                        }
                        let embedding = match embeddings.get(slot) {
                            Some(v) if !v.is_empty() => v.clone(),
                            _ => continue,
                        };
                        if let Err(err) = self
                            .entity_trivium
                            .insert_entity(record.clone(), embedding)
                            .await
                        {
                            warn!(
                                "entity_trivium.insert_entity failed for id={}: {:#}",
                                record.id, err
                            );
                        }
                    }
                }
                Ok(embeddings) => {
                    warn!(
                        "entity embed_batch size mismatch: expected {} got {}",
                        texts.len(),
                        embeddings.len()
                    );
                }
                Err(err) => {
                    warn!("entity embed_batch failed: {err:#}");
                }
            }
        }

        // Step 4: link each draft's memory_id to its resolved entity_id.
        for ((memory_id, _draft), maybe_idx) in pairs.iter().zip(draft_to_key_idx.iter()) {
            let Some(idx) = *maybe_idx else { continue };
            let entity = &entity_records[idx];
            if entity.id < 0 {
                continue;
            }
            if let Err(err) = self.store.link_entity_to_memory(entity.id, *memory_id, 1.0) {
                warn!(
                    "link_entity_to_memory failed for (entity={}, memory={}): {:#}",
                    entity.id, memory_id, err
                );
            }
        }

        Ok(())
    }

    #[tracing::instrument(skip(self, task), fields(task_id = task.id, task_kind = "reflection_run"))]
    async fn process_reflection(&self, task: TaskRecord) -> Result<()> {
        let payload: MaintenanceAgentRequest =
            serde_json::from_str(&task.payload_json).context("invalid reflection payload")?;
        let candidates = self
            .store
            .list_reflection_candidates(&payload.agent_id, 24)?;
        if candidates.len() < 4 {
            self.emit_event(
                "maintenance.completed",
                json!({"task_id": task.id, "kind": "reflection_run", "report": {"reason": "not_enough_candidates"}}),
            )
            .await;
            return Ok(());
        }

        let reflect_started = std::time::Instant::now();
        let result = self
            .worker
            .reflect(
                &payload.agent_id,
                reflection_inputs_from_memories(&candidates),
            )
            .await
            .map_err(|err| {
                counter!("shore_memory_worker_call_errors_total", "op" => "reflect").increment(1);
                err
            })?;
        histogram!("shore_memory_worker_call_duration_seconds", "op" => "reflect")
            .record(reflect_started.elapsed().as_secs_f64());

        // Step 1: insert every summary memory first so `contradictions` can
        // reference them via `new_summary_idx`.
        let mut summary_ids: Vec<i64> = Vec::with_capacity(result.summary_memories.len());
        for memory in result.summary_memories {
            match self
                .insert_and_index_draft(
                    task.id,
                    &payload.agent_id,
                    memory,
                    None,
                    Vec::new(),
                    Vec::new(),
                )
                .await
            {
                Ok(inserted) => summary_ids.push(inserted.id),
                Err(err) => warn!("reflection summary insert failed: {err:#}"),
            }
        }

        // Preload old-memory snapshots once (avoid get_memory_by_id N+1).
        let mut old_snapshot_ids: std::collections::BTreeSet<i64> =
            std::collections::BTreeSet::new();
        for group in &result.duplicate_groups {
            for drop_id in &group.drop_ids {
                if *drop_id != group.keep_id {
                    old_snapshot_ids.insert(*drop_id);
                }
            }
        }
        for entry in &result.contradictions {
            old_snapshot_ids.insert(entry.old_id);
        }
        let old_snapshot_map: std::collections::HashMap<i64, MemoryRecord> = self
            .store
            .list_memories_by_ids(&old_snapshot_ids.into_iter().collect::<Vec<_>>())?
            .into_iter()
            .map(|m| (m.id, m))
            .collect();

        // Step 2: duplicate groups — drop_ids become `superseded` by keep_id.
        let mut supersede_events = 0usize;
        for group in &result.duplicate_groups {
            for drop_id in &group.drop_ids {
                if *drop_id == group.keep_id {
                    continue;
                }
                let old_snapshot = old_snapshot_map.get(drop_id);
                if let Err(err) = self.store.supersede_memory(*drop_id, group.keep_id) {
                    warn!(
                        "supersede_memory failed (drop={}, keep={}): {:#}",
                        drop_id, group.keep_id, err
                    );
                    continue;
                }
                self.sync_trivium_payload_for_memory(*drop_id).await;
                supersede_events += 1;
                let history_meta = json!({
                    "superseded_by": group.keep_id,
                    "reason": group.reason,
                    "source": "duplicate_group",
                });
                let _ = self.store.insert_memory_history(
                    Some(*drop_id),
                    &payload.agent_id,
                    "supersede",
                    old_snapshot.map(|m| m.content.as_str()),
                    None,
                    old_snapshot.map(|m| &m.metadata),
                    Some(&history_meta),
                    Some(task.id),
                );
            }
        }

        // Step 3: contradictions — invalidate old_id, optionally pointing to
        // a replacement memory (existing new_id or a newly-authored summary).
        let mut invalidate_events = 0usize;
        for entry in &result.contradictions {
            let resolved_new_id = entry.new_id.or_else(|| {
                entry
                    .new_summary_idx
                    .and_then(|idx| summary_ids.get(idx).copied())
            });
            let old_snapshot = old_snapshot_map.get(&entry.old_id);

            let op = match resolved_new_id {
                Some(new_id) => {
                    // supersede_memory sets state=superseded + invalid_at=now by default;
                    // override invalid_at if the LLM supplied a specific timestamp.
                    let res = self.store.supersede_memory(entry.old_id, new_id);
                    if res.is_ok()
                        && let Some(custom) = entry.invalid_at.as_deref()
                    {
                        let _ = self.store.set_memory_invalid(
                            entry.old_id,
                            Some(custom),
                            Some("superseded"),
                        );
                    }
                    res
                }
                None => self.store.set_memory_invalid(
                    entry.old_id,
                    entry.invalid_at.as_deref(),
                    Some("invalidated"),
                ),
            };
            if let Err(err) = op {
                warn!(
                    "contradiction apply failed for old_id={}: {:#}",
                    entry.old_id, err
                );
                continue;
            }
            self.sync_trivium_payload_for_memory(entry.old_id).await;
            invalidate_events += 1;
            let history_meta = json!({
                "contradicted_by": resolved_new_id,
                "new_summary_idx": entry.new_summary_idx,
                "invalid_at": entry.invalid_at,
                "reason": entry.reason,
                "source": "contradiction",
            });
            let event = if resolved_new_id.is_some() {
                "supersede"
            } else {
                "invalidate"
            };
            let _ = self.store.insert_memory_history(
                Some(entry.old_id),
                &payload.agent_id,
                event,
                old_snapshot.map(|m| m.content.as_str()),
                None,
                old_snapshot.map(|m| &m.metadata),
                Some(&history_meta),
                Some(task.id),
            );
        }

        // Any supersede / invalidate mutation requires a recall cache flush,
        // otherwise stale (pre-Stage-3) responses may leak back to callers.
        if supersede_events > 0 || invalidate_events > 0 {
            self.bump_recall_epoch(&payload.agent_id).await;
        }

        if !result.retire_memory_ids.is_empty() {
            self.store.archive_memories(&result.retire_memory_ids)?;
            for memory_id in &result.retire_memory_ids {
                self.sync_trivium_payload_for_memory(*memory_id).await;
            }
            self.bump_recall_epoch(&payload.agent_id).await;
            self.enqueue_task(
                TaskKind::RebuildTrivium,
                &payload.agent_id,
                json!({ "agent_id": payload.agent_id }),
                Some("rebuild:all".to_string()),
            )?;
        }

        if let Some(state_patch) = result.state_patch {
            let state = self
                .store
                .upsert_agent_state(&payload.agent_id, &state_patch)?;
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
                "stage3": {
                    "summary_count": summary_ids.len(),
                    "superseded": supersede_events,
                    "invalidated": invalidate_events,
                },
            }),
        )
        .await;

        Ok(())
    }

    #[tracing::instrument(skip(self, task), fields(task_id = task.id, task_kind = "rebuild_trivium"))]
    async fn process_rebuild(&self, task: TaskRecord) -> Result<()> {
        let _reindex_guard = self.reindex_lock.write().await;
        let payload: MaintenanceAgentRequest =
            serde_json::from_str(&task.payload_json).context("invalid rebuild payload")?;
        let memories = self.store.all_unarchived_memories()?;
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
        for agent_id in self.store.list_agents_with_memories()? {
            self.bump_recall_epoch(&agent_id).await;
        }
        self.emit_event(
            "maintenance.completed",
            json!({
                "task_id": task.id,
                "kind": "rebuild_trivium",
                "inserted": inserted,
                "requested_agent_id": payload.agent_id,
            }),
        )
        .await;
        Ok(())
    }

    #[tracing::instrument(skip(self, task), fields(task_id = task.id, task_kind = "index_memory"))]
    async fn process_index_memory(&self, task: TaskRecord) -> Result<()> {
        let _reindex_guard = self.reindex_lock.read().await;
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
        self.bump_recall_epoch(&memory.agent_id).await;
        self.emit_event(
            "memory.indexed",
            json!({"task_id": task.id, "memory_id": memory.id, "agent_id": memory.agent_id}),
        )
        .await;
        Ok(())
    }

    /// Stage 2 recall pipeline: recipe-driven multi-signal additive fusion.
    ///
    /// Pipeline:
    ///   1. Semantic signal via `search_semantic_only` (vector only).
    ///   2. BM25 signal via `search_text_only` when the recipe enables it,
    ///      normalized through `normalize_bm25`.
    ///   3. Entity boost: extract entities from the query, embed them in a
    ///      batch, search the entity Trivium, and propagate spread-attenuated
    ///      scores onto each linked memory.
    ///   4. Contiguity: for the top-N semantic hits, pull session-adjacent
    ///      memories and give them a fixed boost.
    ///   5. Fuse via `additive_fuse` with weights derived from the recipe.
    #[tracing::instrument(skip(self, request), fields(agent_id = %request.agent_id))]
    pub async fn handle_recall(&self, request: RecallRequest) -> Result<RecallResponse> {
        let _reindex_guard = self.reindex_lock.read().await;
        use std::collections::{HashMap, HashSet};
        let started = std::time::Instant::now();
        let recipe = RecallRecipe::parse(request.recipe.as_deref());
        let recipe_label = recipe.as_str();
        let request_scope = infer_scope(request.scope_hint, request.channel_uid.as_deref());
        let selected_scopes =
            selected_recall_scopes(request_scope, request.selected_scopes.as_deref());
        let allowed_scopes = self.allowed_recall_scopes(request_scope, &selected_scopes);

        let recall_epoch = self.recall_epoch.get(&request.agent_id).await.unwrap_or(0);
        let cache_key = cache_key_for_recall(&request, recall_epoch);
        if let Some(cached) = self.recall_cache.get(&cache_key).await {
            counter!("shore_memory_cache_hit_total", "cache" => "recall").increment(1);
            histogram!("shore_memory_recall_duration_seconds", "recipe" => recipe_label, "degraded" => "false")
                .record(started.elapsed().as_secs_f64());
            return Ok(cached);
        }
        counter!("shore_memory_cache_miss_total", "cache" => "recall").increment(1);
        let limit = request
            .limit
            .unwrap_or(self.config.search_top_k)
            .clamp(1, 32);
        let want_debug = request.debug.unwrap_or(false);
        let include_invalid_flag = request.include_invalid.unwrap_or(false);
        // Snapshot "now" once at the top so every `is_currently_valid` check
        // in this call sees the same cutoff.
        let now = chrono::Utc::now().to_rfc3339();
        let fetch_size = limit.saturating_mul(8).max(32);

        // Semantic is always required — lack of embedding flags `degraded`.
        let query_embedding = self.get_or_fetch_embedding(&request.query).await.ok();
        let degraded = query_embedding.is_none();
        if degraded {
            counter!("shore_memory_recall_degraded_total", "reason" => "embedding_unavailable")
                .increment(1);
        }

        // Signal A: semantic vector similarity.
        let mut semantic_map: HashMap<i64, f32> = HashMap::new();
        if let Some(vec) = query_embedding.clone() {
            let semantic_started = std::time::Instant::now();
            let hits = self
                .trivium
                .search_semantic_only(
                    request.agent_id.clone(),
                    request.user_uid.clone(),
                    request.channel_uid.clone(),
                    allowed_scopes.clone(),
                    vec,
                    fetch_size,
                    self.config.search_expand_depth,
                    self.config.search_min_score,
                    include_invalid_flag,
                )
                .await
                .unwrap_or_default();
            histogram!("shore_memory_trivium_search_duration_seconds", "kind" => "semantic")
                .record(semantic_started.elapsed().as_secs_f64());
            for hit in hits {
                semantic_map.insert(hit.id as i64, hit.score);
            }
        }

        // Signal B: BM25.
        let mut bm25_map: HashMap<i64, f32> = HashMap::new();
        if recipe.use_bm25() && !request.query.trim().is_empty() {
            let bm25_started = std::time::Instant::now();
            let bm25_hits = self
                .trivium
                .search_text_only(
                    request.agent_id.clone(),
                    request.user_uid.clone(),
                    request.channel_uid.clone(),
                    allowed_scopes.clone(),
                    request.query.clone(),
                    fetch_size,
                    self.config.search_min_score,
                    include_invalid_flag,
                )
                .await
                .unwrap_or_default();
            histogram!("shore_memory_trivium_search_duration_seconds", "kind" => "bm25")
                .record(bm25_started.elapsed().as_secs_f64());
            let (mid, steep) = bm25_params_for_query(&request.query);
            for hit in bm25_hits {
                bm25_map.insert(hit.id as i64, normalize_bm25(hit.score, mid, steep));
            }
        }

        // Signal C: entity boost with spread attenuation.
        let mut entity_map: HashMap<i64, f32> = HashMap::new();
        let mut entities_by_memory: HashMap<i64, Vec<EntityDraft>> = HashMap::new();
        if recipe.use_entity() && !request.query.trim().is_empty() {
            let extract_started = std::time::Instant::now();
            let extracted = match self.worker.extract_entities(&request.query, None).await {
                Ok(v) => v,
                Err(_) => {
                    counter!("shore_memory_worker_call_errors_total", "op" => "extract_entities")
                        .increment(1);
                    Vec::new()
                }
            };
            histogram!("shore_memory_worker_call_duration_seconds", "op" => "extract_entities")
                .record(extract_started.elapsed().as_secs_f64());
            if !extracted.is_empty() {
                let names: Vec<String> = extracted.iter().map(|e| e.name.clone()).collect();
                let embed_batch_started = std::time::Instant::now();
                let embeddings = match self.worker.embed_batch(names).await {
                    Ok(v) => v,
                    Err(_) => {
                        counter!("shore_memory_worker_call_errors_total", "op" => "embed_batch")
                            .increment(1);
                        Vec::new()
                    }
                };
                histogram!("shore_memory_worker_call_duration_seconds", "op" => "embed_batch")
                    .record(embed_batch_started.elapsed().as_secs_f64());
                let mut propagated_hits: Vec<(i64, f32, EntityDraft)> = Vec::new();
                for (idx, entity) in extracted.iter().enumerate() {
                    let Some(embedding) = embeddings.get(idx) else {
                        continue;
                    };
                    if embedding.is_empty() {
                        continue;
                    }
                    let entity_started = std::time::Instant::now();
                    let hits = self
                        .entity_trivium
                        .search_entities(
                            request.agent_id.clone(),
                            request.user_uid.clone(),
                            embedding.clone(),
                            8,
                            self.config.entity_min_score,
                        )
                        .await
                        .unwrap_or_default();
                    histogram!("shore_memory_trivium_search_duration_seconds", "kind" => "entity")
                        .record(entity_started.elapsed().as_secs_f64());
                    for entity_hit in hits {
                        let entity_id = entity_hit.id as i64;
                        let linked_count = entity_hit
                            .payload
                            .get("linked_memory_count")
                            .and_then(|v| v.as_i64())
                            .unwrap_or(1);
                        let attenuation = entity_spread_attenuation(linked_count);
                        let signal = entity_hit.score * attenuation;
                        propagated_hits.push((entity_id, signal, entity.clone()));
                    }
                }
                if !propagated_hits.is_empty()
                    && let Ok(linked_map) = {
                        let mut seen = HashSet::new();
                        let mut unique_ids = Vec::new();
                        for (entity_id, _, _) in &propagated_hits {
                            if seen.insert(*entity_id) {
                                unique_ids.push(*entity_id);
                            }
                        }
                        self.store.list_linked_memory_ids_for_entities(&unique_ids)
                    }
                {
                    for (entity_id, signal, entity) in propagated_hits {
                        let Some(memory_ids) = linked_map.get(&entity_id) else {
                            continue;
                        };
                        for mem_id in memory_ids {
                            let slot = entity_map.entry(*mem_id).or_insert(0.0);
                            if signal > *slot {
                                *slot = signal;
                            }
                            entities_by_memory
                                .entry(*mem_id)
                                .or_default()
                                .push(entity.clone());
                        }
                    }
                }
            }
        }

        // Union of all candidate ids (semantic ∪ bm25 ∪ entity).
        let mut candidate_set: HashSet<i64> = HashSet::new();
        let mut candidate_order: Vec<i64> = Vec::new();
        let push_candidate = |set: &mut HashSet<i64>, order: &mut Vec<i64>, id: i64| {
            if set.insert(id) {
                order.push(id);
            }
        };
        for id in semantic_map.keys() {
            push_candidate(&mut candidate_set, &mut candidate_order, *id);
        }
        for id in bm25_map.keys() {
            push_candidate(&mut candidate_set, &mut candidate_order, *id);
        }
        for id in entity_map.keys() {
            push_candidate(&mut candidate_set, &mut candidate_order, *id);
        }

        // Load records for the union.
        let mut record_by_id: HashMap<i64, MemoryRecord> = if candidate_order.is_empty() {
            HashMap::new()
        } else {
            self.store
                .list_memories_by_ids(&candidate_order)?
                .into_iter()
                .map(|m| (m.id, m))
                .collect()
        };

        // Signal D: contiguity — pull session-adjacent neighbors for the top
        // semantic picks when the recipe enables it.
        let mut contiguity_map: HashMap<i64, f32> = HashMap::new();
        if recipe.use_contiguity() && !semantic_map.is_empty() {
            let mut sorted: Vec<(i64, f32)> = semantic_map.iter().map(|(k, v)| (*k, *v)).collect();
            sorted.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            let seed_count = limit.min(sorted.len());
            let mut extra_ids: Vec<i64> = Vec::new();
            for (mem_id, _) in sorted.iter().take(seed_count) {
                let Some(mem) = record_by_id.get(mem_id) else {
                    continue;
                };
                let neighbors = self
                    .store
                    .list_session_memories_around(
                        &request.agent_id,
                        mem.session_uid.as_deref(),
                        *mem_id,
                        self.config.contiguity_before,
                        self.config.contiguity_after,
                    )
                    .unwrap_or_default();
                for neighbor in neighbors {
                    if candidate_set.insert(neighbor.id) {
                        candidate_order.push(neighbor.id);
                        extra_ids.push(neighbor.id);
                    }
                    contiguity_map
                        .entry(neighbor.id)
                        .or_insert(self.config.contiguity_boost_value);
                    record_by_id.entry(neighbor.id).or_insert(neighbor);
                }
            }
            // Any ids that sneaked in and aren't yet loaded would be loaded above;
            // `extra_ids` is kept for observability / future logging.
            let _ = extra_ids;
        }

        // If we still have nothing, fall back to recent memories (so the Bot
        // is never completely blind during a cold start or degraded worker).
        if candidate_order.is_empty() {
            let recent = self
                .store
                .list_recent_memories(&request.agent_id, limit.saturating_mul(2).max(16))?;
            for memory in recent {
                if candidate_set.insert(memory.id) {
                    candidate_order.push(memory.id);
                    record_by_id.entry(memory.id).or_insert(memory);
                }
            }
        }

        // Apply the additive fusion.
        let weights = FusionWeights::for_recipe(
            recipe,
            self.config.entity_boost_weight,
            self.config.contiguity_boost_weight,
        );

        struct Scored {
            memory: MemoryRecord,
            signals: FusionInputs,
            scope_weight: f32,
            combined: f32,
            divisor: f32,
        }

        let mut scored_candidates: Vec<Scored> = Vec::new();
        for id in &candidate_order {
            let Some(memory) = record_by_id.get(id) else {
                continue;
            };
            if memory.archived_at.is_some() {
                continue;
            }
            if !scope_visible_for_selected_request(
                memory,
                request.user_uid.as_deref(),
                request.channel_uid.as_deref(),
                &allowed_scopes,
            ) {
                continue;
            }
            let Some(scope_weight) = self.config.scope_recall.weight(request_scope, memory.scope)
            else {
                continue;
            };
            // Stage 3: drop superseded / invalidated / future-dated memories
            // unless the caller explicitly opted into time-travel.
            if !include_invalid_flag && !memory.is_currently_valid(&now) {
                continue;
            }
            let signals = FusionInputs {
                semantic: semantic_map.get(id).copied().unwrap_or(0.0),
                bm25: bm25_map.get(id).copied().unwrap_or(0.0),
                entity: entity_map.get(id).copied().unwrap_or(0.0),
                contiguity: contiguity_map.get(id).copied().unwrap_or(0.0),
            };
            let (combined, divisor) = additive_fuse(signals, weights);
            scored_candidates.push(Scored {
                memory: memory.clone(),
                signals,
                scope_weight,
                combined: combined * scope_weight,
                divisor,
            });
        }

        scored_candidates.sort_by(|a, b| {
            b.combined
                .partial_cmp(&a.combined)
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        scored_candidates.truncate(limit);

        let accessed_ids: Vec<i64> = scored_candidates.iter().map(|s| s.memory.id).collect();
        self.store.mark_memories_accessed(&accessed_ids)?;

        let memory_context = scored_candidates
            .into_iter()
            .map(|s| {
                let score_breakdown = if want_debug {
                    Some(ScoreBreakdown {
                        semantic: s.signals.semantic,
                        bm25: s.signals.bm25,
                        entity: s.signals.entity,
                        contiguity: s.signals.contiguity,
                        scope_weight: s.scope_weight,
                        combined: s.combined,
                        divisor: s.divisor,
                    })
                } else {
                    None
                };
                let entities = entities_by_memory.remove(&s.memory.id).unwrap_or_default();
                // Expose the memory lifecycle when the caller is actively
                // poking at state (debug or time-travel). Keeping it `None`
                // by default avoids leaking superseded data to callers that
                // don't know about it.
                let lifecycle = if want_debug || include_invalid_flag {
                    Some(s.memory.lifecycle())
                } else {
                    None
                };
                MemorySnippet {
                    id: s.memory.id,
                    time: s.memory.created_at,
                    content: s.memory.content,
                    scope: s.memory.scope,
                    score: Some(s.combined),
                    score_breakdown,
                    entities,
                    lifecycle,
                }
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
        histogram!("shore_memory_recall_duration_seconds", "recipe" => recipe_label, "degraded" => if degraded { "true" } else { "false" })
            .record(started.elapsed().as_secs_f64());
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
        content_hash: Option<String>,
        source_event_ids: Vec<i64>,
        linked_memory_ids: Vec<i64>,
    ) -> Result<MemoryRecord> {
        let _reindex_guard = self.reindex_lock.read().await;
        let previous_memory_id = self.store.get_latest_memory_id_for_agent(agent_id)?;
        let record = self.store.insert_memory(&NewMemoryRecord {
            agent_id: agent_id.to_string(),
            user_uid: draft.user_uid.clone(),
            channel_uid: draft.channel_uid.clone(),
            session_uid: draft.session_uid.clone(),
            scope: draft.scope.clone(),
            memory_type: draft.memory_type.clone(),
            content: draft.content.clone(),
            content_hash,
            source_event_ids,
            linked_memory_ids,
            tags: draft.tags.clone(),
            metadata: memory_draft_metadata_with_task(task_id, &draft),
            importance: draft.importance,
            sentiment: draft.sentiment.clone(),
            source: draft.source.clone(),
            embedding_json: None,
            state: "active".to_string(),
            valid_at: draft.valid_at.clone(),
            supersedes_memory_id: None,
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
        self.bump_recall_epoch(agent_id).await;
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
            counter!("shore_memory_cache_hit_total", "cache" => "embedding").increment(1);
            return Ok(embedding);
        }
        counter!("shore_memory_cache_miss_total", "cache" => "embedding").increment(1);

        let embed_started = std::time::Instant::now();
        let future = self.worker.embed(text);
        let embedding = timeout(self.config.embedding_timeout, future)
            .await
            .context("embedding timeout elapsed")?
            .context("embedding worker returned error")
            .map_err(|err| {
                counter!("shore_memory_worker_call_errors_total", "op" => "embed").increment(1);
                err
            })?;
        histogram!("shore_memory_worker_call_duration_seconds", "op" => "embed")
            .record(embed_started.elapsed().as_secs_f64());

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

    fn current_runtime_model_config(
        &self,
    ) -> Result<(RuntimeModelConfig, Option<ModelConfigFile>)> {
        load_runtime_model_config(&self.config.model_config_path)
    }

    async fn list_models_for_provider_probe(
        &self,
        probe: &ResolvedProviderProbe,
    ) -> Result<Vec<String>> {
        let api_key = probe
            .api_key
            .as_deref()
            .filter(|value| !value.trim().is_empty())
            .ok_or_else(|| anyhow!("provider api key is not configured"))?;
        let started = std::time::Instant::now();
        let models = self
            .worker
            .list_provider_models(&probe.api_base, api_key)
            .await?;
        histogram!("shore_memory_worker_call_duration_seconds", "op" => "provider_models")
            .record(started.elapsed().as_secs_f64());
        Ok(models)
    }

    async fn detect_embedding_dimension_for_probe(
        &self,
        probe: &ResolvedProviderProbe,
    ) -> Result<usize> {
        let api_key = probe
            .api_key
            .as_deref()
            .filter(|value| !value.trim().is_empty())
            .ok_or_else(|| anyhow!("embedding provider api key is not configured"))?;
        if probe.model.trim().is_empty() {
            bail!("embedding model is required");
        }
        let started = std::time::Instant::now();
        let dimension = self
            .worker
            .detect_embedding_dimension(&probe.api_base, api_key, &probe.model)
            .await?;
        histogram!("shore_memory_worker_call_duration_seconds", "op" => "embedding_dimension")
            .record(started.elapsed().as_secs_f64());
        if dimension == 0 {
            bail!("embedding provider returned invalid dimension 0");
        }
        Ok(dimension)
    }

    async fn test_runtime_model_config(
        &self,
        runtime: &RuntimeModelConfig,
    ) -> ModelConfigTestResponse {
        let embedding = if runtime.embedding.configured() {
            let started = std::time::Instant::now();
            let result = self.worker.embed("shore-memory model-config test").await;
            histogram!("shore_memory_worker_call_duration_seconds", "op" => "embed")
                .record(started.elapsed().as_secs_f64());
            match result {
                Ok(vector) if !vector.is_empty() => ProviderTestResponse {
                    ok: true,
                    configured: true,
                    message: "embedding call succeeded".to_string(),
                    dimension: Some(vector.len()),
                    source: runtime.embedding.source.clone(),
                },
                Ok(_) => ProviderTestResponse {
                    ok: false,
                    configured: true,
                    message: "embedding call returned empty vector".to_string(),
                    dimension: runtime.embedding.dimension,
                    source: runtime.embedding.source.clone(),
                },
                Err(err) => {
                    counter!("shore_memory_worker_call_errors_total", "op" => "embed").increment(1);
                    ProviderTestResponse {
                        ok: false,
                        configured: true,
                        message: format!("embedding call failed: {err:#}"),
                        dimension: runtime.embedding.dimension,
                        source: runtime.embedding.source.clone(),
                    }
                }
            }
        } else {
            ProviderTestResponse {
                ok: false,
                configured: false,
                message: "embedding provider is not configured".to_string(),
                dimension: runtime.embedding.dimension,
                source: runtime.embedding.source.clone(),
            }
        };

        let llm = if runtime.llm.configured() {
            let started = std::time::Instant::now();
            let result = self
                .worker
                .extract_entities("shore memory config test for OpenAI", None)
                .await;
            histogram!("shore_memory_worker_call_duration_seconds", "op" => "extract_entities")
                .record(started.elapsed().as_secs_f64());
            match result {
                Ok(_) => ProviderTestResponse {
                    ok: true,
                    configured: true,
                    message: "llm call succeeded".to_string(),
                    dimension: None,
                    source: runtime.llm.source.clone(),
                },
                Err(err) => {
                    counter!("shore_memory_worker_call_errors_total", "op" => "extract_entities")
                        .increment(1);
                    ProviderTestResponse {
                        ok: false,
                        configured: true,
                        message: format!("llm call failed: {err:#}"),
                        dimension: None,
                        source: runtime.llm.source.clone(),
                    }
                }
            }
        } else {
            ProviderTestResponse {
                ok: false,
                configured: false,
                message: "llm provider is not configured".to_string(),
                dimension: None,
                source: runtime.llm.source.clone(),
            }
        };

        ModelConfigTestResponse { embedding, llm }
    }

    async fn rebuild_all_embeddings_with_dim(&self, dim: usize) -> Result<(usize, usize, usize)> {
        self.embedding_cache.invalidate_all();
        self.embedding_cache.run_pending_tasks().await;

        let memories = self.store.all_unarchived_memories()?;
        let mut memory_items = Vec::with_capacity(memories.len());
        for memory in memories {
            let embedding = self.get_or_fetch_embedding(&memory.content).await?;
            memory_items.push((memory, embedding));
        }
        let refreshed_embeddings = memory_items.len();

        for (memory, embedding) in &memory_items {
            self.store
                .update_memory_embedding(memory.id, &serde_json::to_string(embedding)?)?;
        }

        let reindexed_memories = self.trivium.rebuild_with_dim(memory_items, dim).await?;

        let entities = self.store.list_all_entities()?;
        let mut entity_items = Vec::with_capacity(entities.len());
        if !entities.is_empty() {
            let names: Vec<String> = entities
                .iter()
                .map(|entity| entity.name_raw.clone())
                .collect();
            let embeddings = self.worker.embed_batch(names).await?;
            if embeddings.len() != entities.len() {
                bail!(
                    "entity embedding count mismatch during reindex: expected {}, got {}",
                    entities.len(),
                    embeddings.len()
                );
            }
            for (entity, vector) in entities.into_iter().zip(embeddings.into_iter()) {
                if vector.is_empty() {
                    bail!(
                        "entity embedding is empty during reindex: entity_id={}",
                        entity.id
                    );
                }
                entity_items.push((entity, vector));
            }
        }
        let reindexed_entities = self
            .entity_trivium
            .rebuild_with_dim(entity_items, dim)
            .await?;

        for agent_id in self.store.list_agents_with_memories()? {
            self.bump_recall_epoch(&agent_id).await;
        }

        Ok((refreshed_embeddings, reindexed_memories, reindexed_entities))
    }

    async fn bump_recall_epoch(&self, agent_id: &str) {
        let epoch = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos() as u64)
            .unwrap_or(0);
        self.recall_epoch.insert(agent_id.to_string(), epoch).await;
    }

    async fn sync_trivium_payload_for_memory(&self, memory_id: i64) {
        let memory = match self.store.get_memory_by_id(memory_id) {
            Ok(Some(memory)) => memory,
            Ok(None) => return,
            Err(err) => {
                warn!(
                    "get_memory_by_id failed while syncing trivium payload id={memory_id}: {err:#}"
                );
                return;
            }
        };
        if let Err(err) = self.trivium.update_memory_payload(memory).await {
            warn!("trivium payload sync failed id={memory_id}: {err:#}");
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ServiceError {
    #[error("{0}")]
    BadRequest(String),
    #[error("{0}")]
    NotFound(String),
    #[error("{0}")]
    Internal(String),
}

impl IntoResponse for ServiceError {
    fn into_response(self) -> Response {
        let (status, message) = match self {
            Self::BadRequest(message) => (StatusCode::BAD_REQUEST, message),
            Self::NotFound(message) => (StatusCode::NOT_FOUND, message),
            Self::Internal(message) => {
                error!("internal service error: {message}");
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "internal server error".to_string(),
                )
            }
        };

        (status, Json(json!({ "error": message }))).into_response()
    }
}

impl From<anyhow::Error> for ServiceError {
    fn from(value: anyhow::Error) -> Self {
        Self::Internal(format!("{value:#}"))
    }
}

#[derive(Debug, Clone, Deserialize)]
struct MaintenanceAgentRequest {
    agent_id: String,
}

/// Payload that accompanies every `ScoreTurn` task.
///
/// `source_event_ids` captures the row ids returned by `insert_raw_turn` (or a
/// single-entry vector from `insert_raw_message`) so that the memory produced
/// by scoring can point back at the exact raw events it was distilled from.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
struct TurnTaskPayload {
    request: crate::types::WorkerScoreTurnRequest,
    #[serde(default)]
    source_event_ids: Vec<i64>,
}

#[derive(Debug, Clone, Deserialize)]
struct IndexMemoryPayload {
    memory_id: i64,
    previous_memory_id: Option<i64>,
}

async fn health(State(state): State<AppState>) -> Result<Json<Value>, ServiceError> {
    let started = std::time::Instant::now();
    let worker = state.worker.health().await.is_ok();
    let summary = state.store.get_sync_summary()?;
    let trace_id = tracing::Span::current().id().map(|id| id.into_u64());
    histogram!("shore_memory_http_duration_seconds", "route" => "/health", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(json!({
        "status": "ok",
        "api_auth_required": state.config.api_key.is_some(),
        "worker_available": worker,
        "pending_tasks": summary.pending_tasks,
        "failed_tasks": summary.failed_tasks,
        "trace_id": trace_id,
    })))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn recall(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<RecallRequest>,
) -> Result<Json<RecallResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if request.query.trim().is_empty() {
        return Err(ServiceError::BadRequest("query is required".to_string()));
    }
    let response = state.handle_recall(request).await?;
    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/context/recall", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(response))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn events_turn(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<TurnEventRequest>,
) -> Result<(StatusCode, Json<TaskActionResponse>), ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if request.messages.is_empty() {
        return Err(ServiceError::BadRequest(
            "messages cannot be empty".to_string(),
        ));
    }

    let scope = infer_scope(request.scope_hint.clone(), request.channel_uid.as_deref());
    let metadata = request.metadata.clone().unwrap_or_else(|| json!({}));
    let pairs = request
        .messages
        .iter()
        .map(|msg| (msg.role.clone(), msg.content.clone()))
        .collect::<Vec<_>>();
    let source_event_ids = state.store.insert_raw_turn(
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
            },
            "source_event_ids": source_event_ids,
        }),
        Some(format!(
            "score_turn:{}:{}:{}",
            request.agent_id,
            request
                .session_uid
                .clone()
                .unwrap_or_else(|| "none".to_string()),
            blake3::hash(
                request
                    .messages
                    .iter()
                    .map(|item| item.content.as_str())
                    .collect::<Vec<_>>()
                    .join("\n")
                    .as_bytes()
            )
            .to_hex()
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
    .map(|resp| {
        histogram!("shore_memory_http_duration_seconds", "route" => "/v1/events/turn", "status" => "accepted")
            .record(started.elapsed().as_secs_f64());
        resp
    })
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn events_message(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<EventMessageRequest>,
) -> Result<(StatusCode, Json<TaskActionResponse>), ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if request.content.trim().is_empty() {
        return Err(ServiceError::BadRequest("content is required".to_string()));
    }
    let scope = infer_scope(request.scope_hint.clone(), request.channel_uid.as_deref());
    let metadata = request.metadata.clone().unwrap_or_else(|| json!({}));
    let role = request.role.clone().unwrap_or_else(|| "system".to_string());

    let source_event_id = state.store.insert_raw_message(
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
                },
                "source_event_ids": [source_event_id],
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
    .map(|resp| {
        histogram!("shore_memory_http_duration_seconds", "route" => "/v1/events/message", "status" => "accepted")
            .record(started.elapsed().as_secs_f64());
        resp
    })
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn list_memories(
    headers: HeaderMap,
    Query(request): Query<ListMemoriesRequest>,
    State(state): State<AppState>,
) -> Result<Json<ListMemoriesResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if let Some(state_filter) = request.state.as_deref()
        && !is_valid_memory_state(state_filter)
    {
        return Err(ServiceError::BadRequest(format!(
            "invalid memory state: {state_filter}"
        )));
    }
    let limit = request.limit.unwrap_or(50).clamp(1, 200);
    let offset = request.offset.unwrap_or(0);
    let (items, total) = state.store.list_memories_page(&request)?;
    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/memories:list", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(ListMemoriesResponse {
        items,
        total,
        limit,
        offset,
    }))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn create_memory(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<CreateMemoryRequest>,
) -> Result<(StatusCode, Json<Value>), ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if request.content.trim().is_empty() {
        return Err(ServiceError::BadRequest("content is required".to_string()));
    }

    let previous_memory_id = state
        .store
        .get_latest_memory_id_for_agent(&request.agent_id)?;
    let normalized_content = request.content.trim();
    let content_hash = if normalized_content.is_empty() {
        None
    } else {
        Some(
            blake3::hash(normalized_content.as_bytes())
                .to_hex()
                .to_string(),
        )
    };
    let record = state.store.insert_memory(&NewMemoryRecord {
        agent_id: request.agent_id.clone(),
        user_uid: request.user_uid.clone(),
        channel_uid: request.channel_uid.clone(),
        session_uid: request.session_uid.clone(),
        scope: request.scope.clone(),
        memory_type: request
            .memory_type
            .clone()
            .unwrap_or_else(|| "event".to_string()),
        content: request.content.clone(),
        content_hash,
        source_event_ids: Vec::new(),
        linked_memory_ids: Vec::new(),
        tags: request.tags.clone().unwrap_or_default(),
        metadata: request.metadata.clone().unwrap_or_else(|| json!({})),
        importance: request.importance.unwrap_or(5.0),
        sentiment: request.sentiment.clone(),
        source: request
            .source
            .clone()
            .unwrap_or_else(|| "manual".to_string()),
        embedding_json: None,
        state: "active".to_string(),
        valid_at: None,
        supersedes_memory_id: None,
    })?;
    state.store.insert_memory_history(
        Some(record.id),
        &request.agent_id,
        "manual",
        None,
        Some(&record.content),
        None,
        Some(&record.metadata),
        None,
    )?;

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
    .map(|resp| {
        histogram!("shore_memory_http_duration_seconds", "route" => "/v1/memories", "status" => "accepted")
            .record(started.elapsed().as_secs_f64());
        resp
    })
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn get_memory(
    headers: HeaderMap,
    Path(memory_id): Path<i64>,
    State(state): State<AppState>,
) -> Result<Json<MemoryDetailResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    let memory = state
        .store
        .get_memory_by_id(memory_id)?
        .ok_or_else(|| ServiceError::NotFound(format!("memory not found: {memory_id}")))?;
    let entities = state.store.list_entities_for_memory(memory_id)?;
    let history = state.store.list_memory_history(memory_id, 100)?;
    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/memories:get", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(MemoryDetailResponse {
        memory,
        entities,
        history,
    }))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn update_memory(
    headers: HeaderMap,
    Path(memory_id): Path<i64>,
    State(state): State<AppState>,
    Json(patch): Json<UpdateMemoryRequest>,
) -> Result<Json<UpdateMemoryResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    if !memory_patch_has_changes(&patch) {
        return Err(ServiceError::BadRequest(
            "at least one patch field is required".to_string(),
        ));
    }
    if let Some(content) = patch.content.as_deref()
        && content.trim().is_empty()
    {
        return Err(ServiceError::BadRequest(
            "content cannot be empty".to_string(),
        ));
    }
    if let Some(state_value) = patch.state.as_deref()
        && !is_valid_memory_state(state_value)
    {
        return Err(ServiceError::BadRequest(format!(
            "invalid memory state: {state_value}"
        )));
    }
    if let Some(Some(supersedes_memory_id)) = patch.supersedes_memory_id.as_ref()
        && *supersedes_memory_id == memory_id
    {
        return Err(ServiceError::BadRequest(
            "supersedes_memory_id cannot equal memory_id".to_string(),
        ));
    }

    let before = state
        .store
        .get_memory_by_id(memory_id)?
        .ok_or_else(|| ServiceError::NotFound(format!("memory not found: {memory_id}")))?;
    if let Some(content) = patch.content.as_deref() {
        let content_hash = blake3::hash(content.trim().as_bytes()).to_hex().to_string();
        if let Some(existing) = state
            .store
            .find_memory_by_hash(&before.agent_id, &content_hash)?
            && existing.id != memory_id
        {
            return Err(ServiceError::BadRequest(format!(
                "memory content duplicates existing memory {}",
                existing.id
            )));
        }
    }

    let updated = state.store.update_memory(memory_id, &patch)?;
    let content_changed = before.content != updated.content;
    let event_name = match patch.archived {
        Some(true) => "archive",
        Some(false) => "unarchive",
        None => "update",
    };
    state.store.insert_memory_history(
        Some(memory_id),
        &updated.agent_id,
        event_name,
        Some(&before.content),
        Some(&updated.content),
        Some(&before.metadata),
        Some(&updated.metadata),
        None,
    )?;
    state.sync_trivium_payload_for_memory(memory_id).await;
    let rebuild_task_id = if content_changed {
        Some(
            state
                .enqueue_task(
                    TaskKind::RebuildTrivium,
                    &updated.agent_id,
                    json!({ "agent_id": updated.agent_id }),
                    Some("rebuild:all".to_string()),
                )?
                .id,
        )
    } else {
        None
    };
    state.bump_recall_epoch(&updated.agent_id).await;
    state
        .emit_event(
            "memory.updated",
            json!({
                "memory_id": updated.id,
                "agent_id": updated.agent_id,
                "state": updated.state,
                "archived": updated.archived_at.is_some(),
                "rebuild_queued": rebuild_task_id.is_some(),
                "rebuild_task_id": rebuild_task_id,
            }),
        )
        .await;
    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/memories:patch", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(UpdateMemoryResponse {
        memory: updated,
        rebuild_task_id,
        rebuild_queued: rebuild_task_id.is_some(),
    }))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn export_memories(
    headers: HeaderMap,
    Query(request): Query<ExportMemoriesRequest>,
    State(state): State<AppState>,
) -> Result<Json<ExportMemoriesResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    let items = state
        .store
        .export_memories(&request.agent_id, request.include_archived.unwrap_or(false))?;
    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/memories/export", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(ExportMemoriesResponse {
        agent_id: request.agent_id,
        exported_at: chrono::Utc::now().to_rfc3339(),
        count: items.len(),
        items,
    }))
}

/// `GET /v1/graph` — returns the memory/entity subgraph for a given agent,
/// capped at `limit` memories (default 500, max 5000). Used by the web
/// "Memory Graph" view.
///
/// Nodes/edges are intentionally projected into a compact wire format
/// (`GraphMemoryNode`, `GraphEntityNode`, etc.) instead of the full
/// `MemoryRecord`, both to shrink the payload and to avoid exposing
/// internal fields (e.g. `embedding_json`) that the UI has no use for.
#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn graph(
    headers: HeaderMap,
    Query(request): Query<GraphRequest>,
    State(state): State<AppState>,
) -> Result<Json<GraphResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));

    if request.agent_id.trim().is_empty() {
        return Err(ServiceError::BadRequest("agent_id is required".to_string()));
    }
    if let Some(state_filter) = request.state.as_deref()
        && !is_valid_memory_state(state_filter)
    {
        return Err(ServiceError::BadRequest(format!(
            "invalid memory state: {state_filter}"
        )));
    }

    let limit = request.limit.unwrap_or(500).clamp(1, 5000);
    let include_archived = request.include_archived.unwrap_or(false);

    let LoadedMemoryGraph {
        memories,
        entities,
        memory_entity_links,
        supersede_edges,
        total_memories,
    } = state.store.load_memory_graph(
        &request.agent_id,
        request.state.as_deref(),
        include_archived,
        limit,
        request.user_uid.as_deref(),
        request.channel_uid.as_deref(),
    )?;

    // Fast lookup sets for the edge/entity pruning pass.
    let kept_memory_ids: std::collections::HashSet<i64> = memories.iter().map(|m| m.id).collect();

    // Map entity -> list of memory ids (within the kept set) for the
    // per-memory `entity_ids` field.
    let mut entity_ids_by_memory: std::collections::HashMap<i64, Vec<i64>> =
        std::collections::HashMap::new();
    let mut memory_count_by_entity: std::collections::HashMap<i64, usize> =
        std::collections::HashMap::new();
    let mut filtered_links: Vec<GraphMemoryEntityEdge> = Vec::new();
    for (entity_id, memory_id, weight) in &memory_entity_links {
        if !kept_memory_ids.contains(memory_id) {
            continue;
        }
        entity_ids_by_memory
            .entry(*memory_id)
            .or_default()
            .push(*entity_id);
        *memory_count_by_entity.entry(*entity_id).or_insert(0) += 1;
        filtered_links.push(GraphMemoryEntityEdge {
            memory_id: *memory_id,
            entity_id: *entity_id,
            weight: *weight,
        });
    }

    let memory_nodes: Vec<GraphMemoryNode> = memories
        .iter()
        .map(|m| {
            let preview = if m.content.chars().count() > 160 {
                let mut buf = m.content.chars().take(160).collect::<String>();
                buf.push('…');
                buf
            } else {
                m.content.clone()
            };
            let mut ids = entity_ids_by_memory.get(&m.id).cloned().unwrap_or_default();
            ids.sort_unstable();
            ids.dedup();
            GraphMemoryNode {
                id: m.id,
                scope: m.scope.clone(),
                memory_type: m.memory_type.clone(),
                content_preview: preview,
                state: m.state.clone(),
                importance: m.importance,
                session_uid: m.session_uid.clone(),
                supersedes_memory_id: m.supersedes_memory_id,
                archived_at: m.archived_at.clone(),
                created_at: m.created_at.clone(),
                updated_at: m.updated_at.clone(),
                entity_ids: ids,
            }
        })
        .collect();

    // Only emit entity nodes that still have at least one linked memory in
    // the kept set.
    let entity_nodes: Vec<GraphEntityNode> = entities
        .iter()
        .filter_map(|e| {
            memory_count_by_entity
                .get(&e.id)
                .copied()
                .filter(|c| *c > 0)
                .map(|count| GraphEntityNode {
                    id: e.id,
                    name: e.name_raw.clone(),
                    entity_type: e.entity_type.clone(),
                    linked_memory_count: e.linked_memory_count,
                    local_memory_count: count,
                })
        })
        .collect();

    let filtered_supersede_edges: Vec<GraphSupersedeEdge> = supersede_edges
        .into_iter()
        .filter(|(from, to)| kept_memory_ids.contains(from) && kept_memory_ids.contains(to))
        .map(|(from, to)| GraphSupersedeEdge {
            from_memory_id: from,
            to_memory_id: to,
        })
        .collect();

    let stats = GraphStats {
        memory_count: memory_nodes.len(),
        entity_count: entity_nodes.len(),
        memory_entity_edges: filtered_links.len(),
        supersede_edges: filtered_supersede_edges.len(),
        total_memories_for_agent: total_memories,
        truncated: total_memories > memory_nodes.len(),
    };

    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/graph", "status" => "ok")
        .record(started.elapsed().as_secs_f64());

    Ok(Json(GraphResponse {
        agent_id: request.agent_id,
        memories: memory_nodes,
        entities: entity_nodes,
        memory_entity_edges: filtered_links,
        supersede_edges: filtered_supersede_edges,
        stats,
        generated_at: chrono::Utc::now().to_rfc3339(),
    }))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn get_agent_state(
    headers: HeaderMap,
    Path(agent_id): Path<String>,
    State(state): State<AppState>,
) -> Result<Json<AgentStateResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    let out = Json(state.store.get_agent_state(&agent_id)?);
    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/agents/state:get", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(out)
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn update_agent_state(
    headers: HeaderMap,
    Path(agent_id): Path<String>,
    State(state): State<AppState>,
    Json(patch): Json<AgentStatePatch>,
) -> Result<Json<AgentStateResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
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
    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/agents/state:patch", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(response))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn get_model_config(
    headers: HeaderMap,
    State(state): State<AppState>,
) -> Result<Json<ModelConfigResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));

    let _reindex_guard = state.reindex_lock.read().await;
    let (runtime, file) = state.current_runtime_model_config()?;
    let response = runtime.to_response(&state.config.model_config_path, file.as_ref());

    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/model-config", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(response))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn list_provider_models(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<ListProviderModelsRequest>,
) -> Result<Json<ListProviderModelsResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));

    let _reindex_guard = state.reindex_lock.read().await;
    let (runtime, _) = state.current_runtime_model_config()?;
    let current = match request.provider {
        ProviderKind::Embedding => &runtime.embedding,
        ProviderKind::Llm => &runtime.llm,
    };
    let probe = resolve_provider_probe(
        current,
        &request.api_base,
        None,
        request.api_key.as_deref(),
        request.clear_api_key,
    );
    let models = state
        .list_models_for_provider_probe(&probe)
        .await
        .map_err(|err| {
            ServiceError::BadRequest(format!("failed to list provider models: {err:#}"))
        })?;

    let response = ListProviderModelsResponse {
        provider: request.provider,
        count: models.len(),
        models,
        source: probe.source,
        api_key_source: probe.api_key_source,
    };

    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/model-config/models", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(response))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn detect_embedding_dimension(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<DetectEmbeddingDimensionRequest>,
) -> Result<Json<DetectEmbeddingDimensionResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));

    let _reindex_guard = state.reindex_lock.read().await;
    let (runtime, _) = state.current_runtime_model_config()?;
    let probe = resolve_provider_probe(
        &runtime.embedding,
        &request.api_base,
        Some(&request.model),
        request.api_key.as_deref(),
        request.clear_api_key,
    );
    let dimension = state
        .detect_embedding_dimension_for_probe(&probe)
        .await
        .map_err(|err| {
            ServiceError::BadRequest(format!("failed to detect embedding dimension: {err:#}"))
        })?;

    let response = DetectEmbeddingDimensionResponse {
        model: probe.model,
        dimension,
        source: probe.source,
        api_key_source: probe.api_key_source,
    };

    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/model-config/embedding/dimension", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(response))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn update_model_config(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<UpdateModelConfigRequest>,
) -> Result<Json<UpdateModelConfigResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));

    let _exclusive = state.reindex_lock.write().await;

    let (previous_runtime, previous_file) = state.current_runtime_model_config()?;
    let previous_file_for_rollback = previous_file.clone();
    let auto_detect_dimension = request.embedding.auto_detect_dimension;
    let mut next_file = apply_update(previous_file, request)
        .map_err(|err| ServiceError::BadRequest(err.to_string()))?;

    if auto_detect_dimension {
        let preview_runtime = resolve_runtime_model_config(Some(&next_file));
        if preview_runtime
            .embedding
            .api_key
            .as_ref()
            .is_some_and(|value| !value.trim().is_empty())
        {
            let probe = ResolvedProviderProbe {
                api_base: preview_runtime.embedding.api_base.clone(),
                model: preview_runtime.embedding.model.clone(),
                api_key: preview_runtime.embedding.api_key.clone(),
                source: preview_runtime.embedding.source.clone(),
                api_key_source: preview_runtime.embedding.api_key_source.clone(),
            };
            let detected_dimension = state
                .detect_embedding_dimension_for_probe(&probe)
                .await
                .map_err(|err| {
                    ServiceError::BadRequest(format!(
                        "failed to auto-detect embedding dimension: {err:#}"
                    ))
                })?;
            next_file.embedding.dimension = Some(detected_dimension);
        }
    }

    let next_runtime = resolve_runtime_model_config(Some(&next_file));

    let embedding_changed = embedding_effective_changed(&previous_runtime, &next_runtime);
    let embedding_dimension_changed =
        previous_runtime.embedding.dimension != next_runtime.embedding.dimension;

    write_model_config_file(&state.config.model_config_path, &next_file)?;

    let mut memory_embeddings_refreshed = 0usize;
    let mut reindexed_memories = 0usize;
    let mut reindexed_entities = 0usize;
    if embedding_changed {
        let dim = next_runtime.embedding.dimension.unwrap_or(1536).max(1);
        match state.rebuild_all_embeddings_with_dim(dim).await {
            Ok((refreshed, memory_count, entity_count)) => {
                memory_embeddings_refreshed = refreshed;
                reindexed_memories = memory_count;
                reindexed_entities = entity_count;
            }
            Err(err) => {
                if let Some(file) = previous_file_for_rollback.as_ref() {
                    let _ = write_model_config_file(&state.config.model_config_path, file);
                } else {
                    let _ = delete_model_config_file(&state.config.model_config_path);
                }
                return Err(ServiceError::Internal(format!(
                    "model config applied but reindex failed and rollback attempted: {err:#}"
                )));
            }
        }
    }

    let (runtime, file) = state.current_runtime_model_config()?;
    let response = UpdateModelConfigResponse {
        config: runtime.to_response(&state.config.model_config_path, file.as_ref()),
        embedding_changed,
        embedding_dimension_changed,
        embedding_cache_cleared: embedding_changed,
        memory_embeddings_refreshed,
        reindexed_memories,
        reindexed_entities,
    };

    state
        .emit_event(
            "model_config.updated",
            json!({
                "embedding_changed": embedding_changed,
                "embedding_dimension_changed": embedding_dimension_changed,
                "memory_embeddings_refreshed": memory_embeddings_refreshed,
                "reindexed_memories": reindexed_memories,
                "reindexed_entities": reindexed_entities,
            }),
        )
        .await;

    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/model-config", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(response))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn restore_model_config_defaults(
    headers: HeaderMap,
    State(state): State<AppState>,
) -> Result<Json<UpdateModelConfigResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));

    let _exclusive = state.reindex_lock.write().await;

    let (previous_runtime, previous_file) = state.current_runtime_model_config()?;
    delete_model_config_file(&state.config.model_config_path)?;
    let (runtime_after, file_after) = state.current_runtime_model_config()?;

    let embedding_changed = embedding_effective_changed(&previous_runtime, &runtime_after);
    let embedding_dimension_changed =
        previous_runtime.embedding.dimension != runtime_after.embedding.dimension;

    let mut memory_embeddings_refreshed = 0usize;
    let mut reindexed_memories = 0usize;
    let mut reindexed_entities = 0usize;
    if embedding_changed {
        let dim = runtime_after.embedding.dimension.unwrap_or(1536).max(1);
        match state.rebuild_all_embeddings_with_dim(dim).await {
            Ok((refreshed, memory_count, entity_count)) => {
                memory_embeddings_refreshed = refreshed;
                reindexed_memories = memory_count;
                reindexed_entities = entity_count;
            }
            Err(err) => {
                if let Some(file) = previous_file.as_ref() {
                    let _ = write_model_config_file(&state.config.model_config_path, file);
                }
                return Err(ServiceError::Internal(format!(
                    "restore defaults applied but reindex failed and rollback attempted: {err:#}"
                )));
            }
        }
    }

    let response = UpdateModelConfigResponse {
        config: runtime_after.to_response(&state.config.model_config_path, file_after.as_ref()),
        embedding_changed,
        embedding_dimension_changed,
        embedding_cache_cleared: embedding_changed,
        memory_embeddings_refreshed,
        reindexed_memories,
        reindexed_entities,
    };

    state
        .emit_event(
            "model_config.restored",
            json!({
                "embedding_changed": embedding_changed,
                "embedding_dimension_changed": embedding_dimension_changed,
                "memory_embeddings_refreshed": memory_embeddings_refreshed,
                "reindexed_memories": reindexed_memories,
                "reindexed_entities": reindexed_entities,
            }),
        )
        .await;

    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/model-config:restore", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(response))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn test_model_config(
    headers: HeaderMap,
    State(state): State<AppState>,
) -> Result<Json<ModelConfigTestResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));

    let _reindex_guard = state.reindex_lock.read().await;
    let (runtime, _) = state.current_runtime_model_config()?;
    let response = state.test_runtime_model_config(&runtime).await;

    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/model-config/test", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(Json(response))
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn retry_scorer(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<MaintenanceAgentRequest>,
) -> Result<Json<TaskActionResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
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
    .map(|resp| {
        histogram!("shore_memory_http_duration_seconds", "route" => "/v1/maintenance/scorer/retry", "status" => "ok")
            .record(started.elapsed().as_secs_f64());
        resp
    })
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn run_reflection(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<MaintenanceAgentRequest>,
) -> Result<(StatusCode, Json<TaskActionResponse>), ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
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
    .map(|resp| {
        histogram!("shore_memory_http_duration_seconds", "route" => "/v1/maintenance/reflection/run", "status" => "accepted")
            .record(started.elapsed().as_secs_f64());
        resp
    })
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn rebuild_trivium(
    headers: HeaderMap,
    State(state): State<AppState>,
    Json(request): Json<MaintenanceAgentRequest>,
) -> Result<(StatusCode, Json<TaskActionResponse>), ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    let task = state.enqueue_task(
        TaskKind::RebuildTrivium,
        &request.agent_id,
        json!({ "agent_id": request.agent_id }),
        Some("rebuild:all".to_string()),
    )?;
    Ok((
        StatusCode::ACCEPTED,
        Json(TaskActionResponse {
            status: "queued".to_string(),
            task_id: Some(task.id),
            message: "rebuild queued".to_string(),
        }),
    ))
    .map(|resp| {
        histogram!("shore_memory_http_duration_seconds", "route" => "/v1/maintenance/trivium/rebuild", "status" => "accepted")
            .record(started.elapsed().as_secs_f64());
        resp
    })
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn sync_summary(
    headers: HeaderMap,
    State(state): State<AppState>,
) -> Result<Json<SyncSummaryResponse>, ServiceError> {
    let started = std::time::Instant::now();
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    let out = Json(state.store.get_sync_summary()?);
    histogram!("shore_memory_http_duration_seconds", "route" => "/v1/maintenance/sync-summary", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(out)
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn metrics(
    headers: HeaderMap,
    State(state): State<AppState>,
) -> Result<Response, ServiceError> {
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(rid));
    let started = std::time::Instant::now();
    let body = state.metrics_handle.render();
    let mut response = Response::new(axum::body::Body::from(body));
    response.headers_mut().insert(
        axum::http::header::CONTENT_TYPE,
        axum::http::HeaderValue::from_static("text/plain; version=0.0.4; charset=utf-8"),
    );
    histogram!("shore_memory_http_duration_seconds", "route" => "/metrics", "status" => "ok")
        .record(started.elapsed().as_secs_f64());
    Ok(response)
}

#[tracing::instrument(skip_all, fields(request_id = tracing::field::Empty))]
async fn events_ws(
    headers: HeaderMap,
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    let rid = request_id_from_headers(&headers);
    tracing::Span::current().record("request_id", tracing::field::display(&rid));
    ws.on_upgrade(move |socket| handle_events_socket(socket, state, rid))
}

#[tracing::instrument(skip(state, socket), fields(request_id = %request_id))]
async fn handle_events_socket(mut socket: WebSocket, state: AppState, request_id: String) {
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
                    Err(broadcast::error::RecvError::Lagged(skipped)) => {
                        let lagged_notice = ServerEvent {
                            event: "lagged".to_string(),
                            payload: json!({"dropped": skipped}),
                            at: chrono::Utc::now(),
                        };
                        if let Ok(text) = serde_json::to_string(&lagged_notice) {
                            if socket.send(Message::Text(text.into())).await.is_err() {
                                break;
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

async fn require_api_key(
    State(state): State<AppState>,
    request: Request,
    next: axum::middleware::Next,
) -> Response {
    let Some(expected) = state.config.api_key.as_deref() else {
        return next.run(request).await;
    };
    let provided = provided_api_key(&request);
    if provided.as_deref() == Some(expected) {
        return next.run(request).await;
    }
    (
        StatusCode::UNAUTHORIZED,
        Json(json!({ "error": "unauthorized" })),
    )
        .into_response()
}

fn provided_api_key(request: &Request) -> Option<String> {
    request
        .headers()
        .get("x-api-key")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(str::to_string)
        .or_else(|| {
            request
                .headers()
                .get(header::AUTHORIZATION)
                .and_then(|v| v.to_str().ok())
                .and_then(parse_bearer_token)
                .map(str::to_string)
        })
        .or_else(|| api_key_from_query(request.uri().query()))
}

fn parse_bearer_token(raw: &str) -> Option<&str> {
    raw.strip_prefix("Bearer ")
        .or_else(|| raw.strip_prefix("bearer "))
        .map(str::trim)
        .filter(|v| !v.is_empty())
}

fn api_key_from_query(query: Option<&str>) -> Option<String> {
    let raw = query?;
    for pair in raw.split('&') {
        let mut parts = pair.splitn(2, '=');
        let key = parts.next().unwrap_or_default();
        if key != "api_key" {
            continue;
        }
        let value = parts.next().unwrap_or_default();
        let decoded = decode_query_component(value)?;
        let trimmed = decoded.trim();
        if !trimmed.is_empty() {
            return Some(trimmed.to_string());
        }
    }
    None
}

fn decode_query_component(raw: &str) -> Option<String> {
    let bytes = raw.as_bytes();
    let mut out: Vec<u8> = Vec::with_capacity(bytes.len());
    let mut i = 0usize;
    while i < bytes.len() {
        match bytes[i] {
            b'+' => {
                out.push(b' ');
                i += 1;
            }
            b'%' => {
                if i + 2 >= bytes.len() {
                    return None;
                }
                let hi = (bytes[i + 1] as char).to_digit(16)?;
                let lo = (bytes[i + 2] as char).to_digit(16)?;
                out.push((hi * 16 + lo) as u8);
                i += 3;
            }
            byte => {
                out.push(byte);
                i += 1;
            }
        }
    }
    String::from_utf8(out).ok()
}

fn cache_key_for_recall(request: &RecallRequest, recall_epoch: u64) -> String {
    let request_hash = blake3::hash(
        serde_json::to_string(request)
            .unwrap_or_else(|_| request.query.clone())
            .as_bytes(),
    )
    .to_hex()
    .to_string();
    format!(
        "{}:{}:{}:{}",
        RECALL_CACHE_KEY_VERSION, request.agent_id, recall_epoch, request_hash
    )
}

fn cache_key_for_text(text: &str) -> String {
    blake3::hash(text.trim().as_bytes()).to_hex().to_string()
}

fn embedding_effective_changed(before: &RuntimeModelConfig, after: &RuntimeModelConfig) -> bool {
    before.embedding.api_base != after.embedding.api_base
        || before.embedding.model != after.embedding.model
        || before.embedding.dimension != after.embedding.dimension
        || before.embedding.api_key != after.embedding.api_key
}

fn request_id_from_headers(headers: &HeaderMap) -> String {
    headers
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .map(str::to_string)
        .unwrap_or_else(|| "unknown".to_string())
}

fn is_valid_memory_state(state: &str) -> bool {
    matches!(state, "active" | "superseded" | "invalidated" | "archived")
}

fn memory_patch_has_changes(patch: &UpdateMemoryRequest) -> bool {
    patch.content.is_some()
        || patch.tags.is_some()
        || patch.metadata.is_some()
        || patch.importance.is_some()
        || patch.sentiment.is_some()
        || patch.source.is_some()
        || patch.state.is_some()
        || patch.valid_at.is_some()
        || patch.invalid_at.is_some()
        || patch.supersedes_memory_id.is_some()
        || patch.archived.is_some()
}
