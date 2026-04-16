use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, RwLock};

use anyhow::{Context, Result, anyhow};
use serde_json::{Value, json};
use tokio::task::spawn_blocking;
use tracing::warn;
use triviumdb::database::{Config as TriviumConfig, Database, SearchConfig};
use triviumdb::filter::Filter;
use triviumdb::node::SearchHit;

use crate::types::{EntityRecord, MemoryRecord, MemoryScope};

#[derive(Clone)]
pub struct TriviumStore {
    db_path: PathBuf,
    db: Arc<RwLock<Option<Database<f32>>>>,
    config: TriviumConfig,
}

impl TriviumStore {
    pub fn new(db_path: PathBuf) -> Result<Self> {
        if let Some(parent) = db_path.parent() {
            fs::create_dir_all(parent)
                .with_context(|| format!("failed to create trivium dir: {}", parent.display()))?;
        }
        let config = TriviumConfig {
            dim: 1536,
            ..Default::default()
        };
        let db = Database::<f32>::open_with_config(path_as_str(&db_path)?, config)
            .with_context(|| format!("failed to open trivium db: {}", db_path.display()))?;

        Ok(Self {
            db_path,
            db: Arc::new(RwLock::new(Some(db))),
            config,
        })
    }

    pub async fn search(
        &self,
        agent_id: String,
        user_uid: Option<String>,
        channel_uid: Option<String>,
        query_text: String,
        query_vector: Option<Vec<f32>>,
        limit: usize,
        expand_depth: usize,
        min_score: f32,
        include_invalid: bool,
    ) -> Result<Vec<SearchHit>> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let guard = db.read().map_err(|_| anyhow!("trivium db lock poisoned"))?;
            let db = guard
                .as_ref()
                .ok_or_else(|| anyhow!("trivium db not initialized"))?;
            let filter = build_visibility_filter(
                &agent_id,
                user_uid.as_deref(),
                channel_uid.as_deref(),
                include_invalid,
            );
            let config = SearchConfig {
                top_k: limit.max(5),
                expand_depth,
                min_score,
                enable_advanced_pipeline: query_vector.is_some(),
                enable_sparse_residual: false,
                enable_dpp: query_vector.is_some(),
                dpp_quality_weight: 1.1,
                enable_text_hybrid_search: true,
                text_boost: 1.6,
                payload_filter: Some(filter),
                ..Default::default()
            };
            db.search_hybrid(Some(query_text.as_str()), query_vector.as_deref(), &config)
                .map_err(|err| anyhow!(err.to_string()))
        })
        .await
        .map_err(|err| anyhow!("trivium search join error: {err}"))?
    }

    /// Vector-only recall — returns cosine-ish similarity scores isolated from
    /// BM25. Used by Stage 2 recall fusion for the `semantic` signal.
    pub async fn search_semantic_only(
        &self,
        agent_id: String,
        user_uid: Option<String>,
        channel_uid: Option<String>,
        query_vector: Vec<f32>,
        limit: usize,
        expand_depth: usize,
        min_score: f32,
        include_invalid: bool,
    ) -> Result<Vec<SearchHit>> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let guard = db.read().map_err(|_| anyhow!("trivium db lock poisoned"))?;
            let db = guard
                .as_ref()
                .ok_or_else(|| anyhow!("trivium db not initialized"))?;
            let filter = build_visibility_filter(
                &agent_id,
                user_uid.as_deref(),
                channel_uid.as_deref(),
                include_invalid,
            );
            let config = SearchConfig {
                top_k: limit.max(5),
                expand_depth,
                min_score,
                enable_advanced_pipeline: true,
                enable_sparse_residual: false,
                enable_dpp: true,
                dpp_quality_weight: 1.1,
                enable_text_hybrid_search: false,
                payload_filter: Some(filter),
                ..Default::default()
            };
            db.search_hybrid(None, Some(query_vector.as_slice()), &config)
                .map_err(|err| anyhow!(err.to_string()))
        })
        .await
        .map_err(|err| anyhow!("trivium semantic search join error: {err}"))?
    }

    /// BM25-only recall — returns text relevance scores isolated from vector
    /// similarity. Used by Stage 2 recall fusion for the `bm25` signal. The
    /// raw scores are unbounded and must be normalized at the caller via
    /// `recall_recipe::normalize_bm25`.
    pub async fn search_text_only(
        &self,
        agent_id: String,
        user_uid: Option<String>,
        channel_uid: Option<String>,
        query_text: String,
        limit: usize,
        min_score: f32,
        include_invalid: bool,
    ) -> Result<Vec<SearchHit>> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let guard = db.read().map_err(|_| anyhow!("trivium db lock poisoned"))?;
            let db = guard
                .as_ref()
                .ok_or_else(|| anyhow!("trivium db not initialized"))?;
            let filter = build_visibility_filter(
                &agent_id,
                user_uid.as_deref(),
                channel_uid.as_deref(),
                include_invalid,
            );
            let config = SearchConfig {
                top_k: limit.max(5),
                expand_depth: 0,
                min_score,
                enable_advanced_pipeline: false,
                enable_sparse_residual: false,
                enable_dpp: false,
                enable_text_hybrid_search: true,
                text_boost: 1.0,
                payload_filter: Some(filter),
                ..Default::default()
            };
            db.search_hybrid(Some(query_text.as_str()), None, &config)
                .map_err(|err| anyhow!(err.to_string()))
        })
        .await
        .map_err(|err| anyhow!("trivium bm25 search join error: {err}"))?
    }

    pub async fn insert_memory(
        &self,
        memory: MemoryRecord,
        embedding: Vec<f32>,
        previous_memory_id: Option<i64>,
    ) -> Result<()> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let mut guard = db
                .write()
                .map_err(|_| anyhow!("trivium db lock poisoned"))?;
            let db = guard
                .as_mut()
                .ok_or_else(|| anyhow!("trivium db not initialized"))?;
            db.insert_with_id(memory.id as u64, &embedding, build_payload(&memory))
                .map_err(|err| anyhow!(err.to_string()))?;
            db.index_text(memory.id as u64, &memory.content)
                .map_err(|err| anyhow!(err.to_string()))?;
            if let Some(prev_id) = previous_memory_id {
                if prev_id != memory.id {
                    db.link(memory.id as u64, prev_id as u64, "associative", 0.2)
                        .map_err(|err| anyhow!(err.to_string()))?;
                    db.link(prev_id as u64, memory.id as u64, "associative", 0.2)
                        .map_err(|err| anyhow!(err.to_string()))?;
                }
            }
            Ok(())
        })
        .await
        .map_err(|err| anyhow!("trivium insert join error: {err}"))?
    }

    pub async fn update_memory_payload(&self, memory: MemoryRecord) -> Result<()> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let mut guard = db
                .write()
                .map_err(|_| anyhow!("trivium db lock poisoned"))?;
            let db = guard
                .as_mut()
                .ok_or_else(|| anyhow!("trivium db not initialized"))?;
            db.update_payload(memory.id as u64, build_payload(&memory))
                .map_err(|err| anyhow!(err.to_string()))
        })
        .await
        .map_err(|err| anyhow!("trivium update payload join error: {err}"))?
    }

    pub async fn flush(&self) -> Result<()> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let mut guard = db
                .write()
                .map_err(|_| anyhow!("trivium db lock poisoned"))?;
            let db = guard
                .as_mut()
                .ok_or_else(|| anyhow!("trivium db not initialized"))?;
            db.flush().map_err(|err| anyhow!(err.to_string()))
        })
        .await
        .map_err(|err| anyhow!("trivium flush join error: {err}"))?
    }

    pub async fn rebuild(&self, items: Vec<(MemoryRecord, Vec<f32>)>) -> Result<usize> {
        let db = Arc::clone(&self.db);
        let db_path = self.db_path.clone();
        let config = self.config;
        spawn_blocking(move || {
            let mut guard = db
                .write()
                .map_err(|_| anyhow!("trivium db lock poisoned"))?;
            *guard = None;
            remove_store_files(&db_path)?;

            let mut database = Database::<f32>::open_with_config(path_as_str(&db_path)?, config)
                .with_context(|| format!("failed to reopen trivium db: {}", db_path.display()))?;

            let mut previous_memory_id = None;
            let mut inserted = 0usize;
            for (memory, embedding) in items {
                database
                    .insert_with_id(memory.id as u64, &embedding, build_payload(&memory))
                    .map_err(|err| anyhow!(err.to_string()))?;
                database
                    .index_text(memory.id as u64, &memory.content)
                    .map_err(|err| anyhow!(err.to_string()))?;
                if let Some(prev_id) = previous_memory_id {
                    database
                        .link(memory.id as u64, prev_id as u64, "associative", 0.2)
                        .map_err(|err| anyhow!(err.to_string()))?;
                    database
                        .link(prev_id as u64, memory.id as u64, "associative", 0.2)
                        .map_err(|err| anyhow!(err.to_string()))?;
                }
                previous_memory_id = Some(memory.id);
                inserted += 1;
            }
            database.flush().map_err(|err| anyhow!(err.to_string()))?;
            *guard = Some(database);
            Ok(inserted)
        })
        .await
        .map_err(|err| anyhow!("trivium rebuild join error: {err}"))?
    }
}

fn build_payload(memory: &MemoryRecord) -> Value {
    json!({
        "id": memory.id,
        "agent_id": memory.agent_id,
        "user_uid": memory.user_uid,
        "channel_uid": memory.channel_uid,
        "session_uid": memory.session_uid,
        "scope": memory.scope.as_str(),
        "memory_type": memory.memory_type,
        "content": memory.content,
        "tags": memory.tags,
        "importance": memory.importance,
        "sentiment": memory.sentiment,
        "source": memory.source,
        "created_at": memory.created_at,
        "state": memory.state,
        "archived": memory.archived_at.is_some(),
    })
}

/// Separate Trivium instance dedicated to the entity vector index.
///
/// Entities live in their own `*.tdb` file so that scope-level rebuilds on
/// memories don't blow away entity vectors and vice versa. The payload schema
/// is deliberately flat (`id`, `agent_id`, `user_uid`, `entity_type`,
/// `name_raw`, `name_norm`) — there's no scope concept for entities, only the
/// `(agent_id, user_uid)` pair.
#[derive(Clone)]
pub struct EntityTriviumStore {
    db_path: PathBuf,
    db: Arc<RwLock<Option<Database<f32>>>>,
    config: TriviumConfig,
}

impl EntityTriviumStore {
    pub fn new(db_path: PathBuf) -> Result<Self> {
        if let Some(parent) = db_path.parent() {
            fs::create_dir_all(parent).with_context(|| {
                format!("failed to create entity trivium dir: {}", parent.display())
            })?;
        }
        let config = TriviumConfig {
            dim: 1536,
            ..Default::default()
        };
        let db = Database::<f32>::open_with_config(path_as_str(&db_path)?, config)
            .with_context(|| format!("failed to open entity trivium db: {}", db_path.display()))?;

        Ok(Self {
            db_path,
            db: Arc::new(RwLock::new(Some(db))),
            config,
        })
    }

    pub async fn insert_entity(&self, entity: EntityRecord, embedding: Vec<f32>) -> Result<()> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let mut guard = db
                .write()
                .map_err(|_| anyhow!("entity trivium db lock poisoned"))?;
            let db = guard
                .as_mut()
                .ok_or_else(|| anyhow!("entity trivium db not initialized"))?;
            db.insert_with_id(entity.id as u64, &embedding, build_entity_payload(&entity))
                .map_err(|err| anyhow!(err.to_string()))?;
            db.index_text(entity.id as u64, &entity.name_raw)
                .map_err(|err| anyhow!(err.to_string()))?;
            Ok(())
        })
        .await
        .map_err(|err| anyhow!("entity trivium insert join error: {err}"))?
    }

    /// Vector search against the entity index.
    ///
    /// Visibility: private entities are only visible to the owning user;
    /// entities with `user_uid = NULL` are treated as shared across the agent.
    pub async fn search_entities(
        &self,
        agent_id: String,
        user_uid: Option<String>,
        query_vector: Vec<f32>,
        limit: usize,
        min_score: f32,
    ) -> Result<Vec<SearchHit>> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let guard = db
                .read()
                .map_err(|_| anyhow!("entity trivium db lock poisoned"))?;
            let db = guard
                .as_ref()
                .ok_or_else(|| anyhow!("entity trivium db not initialized"))?;
            let filter = build_entity_visibility_filter(&agent_id, user_uid.as_deref());
            let config = SearchConfig {
                top_k: limit.max(5),
                expand_depth: 0,
                min_score,
                enable_advanced_pipeline: true,
                enable_sparse_residual: false,
                enable_dpp: false,
                enable_text_hybrid_search: false,
                payload_filter: Some(filter),
                ..Default::default()
            };
            db.search_hybrid(None, Some(query_vector.as_slice()), &config)
                .map_err(|err| anyhow!(err.to_string()))
        })
        .await
        .map_err(|err| anyhow!("entity trivium search join error: {err}"))?
    }

    pub async fn flush(&self) -> Result<()> {
        let db = Arc::clone(&self.db);
        spawn_blocking(move || {
            let mut guard = db
                .write()
                .map_err(|_| anyhow!("entity trivium db lock poisoned"))?;
            let db = guard
                .as_mut()
                .ok_or_else(|| anyhow!("entity trivium db not initialized"))?;
            db.flush().map_err(|err| anyhow!(err.to_string()))
        })
        .await
        .map_err(|err| anyhow!("entity trivium flush join error: {err}"))?
    }

    pub async fn rebuild(&self, items: Vec<(EntityRecord, Vec<f32>)>) -> Result<usize> {
        let db = Arc::clone(&self.db);
        let db_path = self.db_path.clone();
        let config = self.config;
        spawn_blocking(move || {
            let mut guard = db
                .write()
                .map_err(|_| anyhow!("entity trivium db lock poisoned"))?;
            *guard = None;
            remove_store_files(&db_path)?;

            let mut database = Database::<f32>::open_with_config(path_as_str(&db_path)?, config)
                .with_context(|| {
                    format!("failed to reopen entity trivium db: {}", db_path.display())
                })?;

            let mut inserted = 0usize;
            for (entity, embedding) in items {
                database
                    .insert_with_id(entity.id as u64, &embedding, build_entity_payload(&entity))
                    .map_err(|err| anyhow!(err.to_string()))?;
                database
                    .index_text(entity.id as u64, &entity.name_raw)
                    .map_err(|err| anyhow!(err.to_string()))?;
                inserted += 1;
            }
            database.flush().map_err(|err| anyhow!(err.to_string()))?;
            *guard = Some(database);
            Ok(inserted)
        })
        .await
        .map_err(|err| anyhow!("entity trivium rebuild join error: {err}"))?
    }
}

fn build_entity_payload(entity: &EntityRecord) -> Value {
    json!({
        "id": entity.id,
        "agent_id": entity.agent_id,
        "user_uid": entity.user_uid,
        "entity_type": entity.entity_type,
        "name_raw": entity.name_raw,
        "name_norm": entity.name_norm,
        "linked_memory_count": entity.linked_memory_count,
    })
}

fn build_entity_visibility_filter(agent_id: &str, user_uid: Option<&str>) -> Filter {
    // Shared entities (user_uid IS NULL) OR the caller's own private entities.
    let mut visible = vec![Filter::eq("user_uid", Value::Null)];
    if let Some(user_uid) = user_uid {
        visible.push(Filter::eq("user_uid", Value::String(user_uid.to_string())));
    }
    Filter::and(vec![
        Filter::eq("agent_id", Value::String(agent_id.to_string())),
        Filter::or(visible),
    ])
}

fn build_visibility_filter(
    agent_id: &str,
    user_uid: Option<&str>,
    channel_uid: Option<&str>,
    include_invalid: bool,
) -> Filter {
    let mut visible: Vec<Filter> = vec![
        Filter::eq(
            "scope",
            Value::String(MemoryScope::System.as_str().to_string()),
        ),
        Filter::eq(
            "scope",
            Value::String(MemoryScope::Shared.as_str().to_string()),
        ),
    ];

    if let Some(user_uid) = user_uid {
        visible.push(Filter::and(vec![
            Filter::eq(
                "scope",
                Value::String(MemoryScope::Private.as_str().to_string()),
            ),
            Filter::eq("user_uid", Value::String(user_uid.to_string())),
        ]));
    }

    if let Some(channel_uid) = channel_uid {
        visible.push(Filter::and(vec![
            Filter::eq(
                "scope",
                Value::String(MemoryScope::Group.as_str().to_string()),
            ),
            Filter::eq("channel_uid", Value::String(channel_uid.to_string())),
        ]));
    }

    let mut predicates = vec![
        Filter::eq("agent_id", Value::String(agent_id.to_string())),
        Filter::or(visible),
    ];
    if !include_invalid {
        predicates.push(Filter::eq("state", Value::String("active".to_string())));
    }
    Filter::and(predicates)
}

fn remove_store_files(db_path: &Path) -> Result<()> {
    let db_file = db_path.to_path_buf();
    let vec_file = PathBuf::from(format!("{}.vec", db_path.display()));
    let wal_file = PathBuf::from(format!("{}.wal", db_path.display()));
    let lock_file = PathBuf::from(format!("{}.lock", db_path.display()));
    let flush_ok_file = PathBuf::from(format!("{}.flush_ok", db_path.display()));

    for candidate in [db_file, vec_file, wal_file, lock_file, flush_ok_file] {
        if candidate.exists()
            && let Err(err) = fs::remove_file(&candidate)
        {
            warn!(
                "failed to remove stale trivium file {}: {}",
                candidate.display(),
                err
            );
        }
    }
    Ok(())
}

fn path_as_str(path: &Path) -> Result<&str> {
    path.to_str()
        .ok_or_else(|| anyhow!("non-utf8 path not supported: {}", path.display()))
}
