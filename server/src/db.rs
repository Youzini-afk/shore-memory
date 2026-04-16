use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result, anyhow};
use chrono::Utc;
use r2d2::{ManageConnection, Pool, PooledConnection};
use rusqlite::{Connection, OptionalExtension, Transaction, params};
use serde_json::Value;

use crate::types::{
    AgentStatePatch, AgentStateResponse, EntityRecord, MemoryRecord, MemoryScope, RawEventRecord,
    SyncSummaryResponse, TaskKind, TaskRecord, TaskStatus,
};

#[derive(Debug, Clone)]
pub struct MetadataStore {
    db_path: PathBuf,
    pool: Pool<SqliteConnectionManager>,
}

type SqlitePooledConnection = PooledConnection<SqliteConnectionManager>;

#[derive(Debug, Clone)]
struct SqliteConnectionManager {
    db_path: PathBuf,
}

impl SqliteConnectionManager {
    fn file(db_path: PathBuf) -> Self {
        Self { db_path }
    }
}

impl ManageConnection for SqliteConnectionManager {
    type Connection = Connection;
    type Error = rusqlite::Error;

    fn connect(&self) -> std::result::Result<Self::Connection, Self::Error> {
        Connection::open(&self.db_path)
    }

    fn is_valid(&self, conn: &mut Self::Connection) -> std::result::Result<(), Self::Error> {
        conn.execute_batch("SELECT 1")?;
        Ok(())
    }

    fn has_broken(&self, _conn: &mut Self::Connection) -> bool {
        false
    }
}

#[derive(Debug, Clone)]
pub struct NewMemoryRecord {
    pub agent_id: String,
    pub user_uid: Option<String>,
    pub channel_uid: Option<String>,
    pub session_uid: Option<String>,
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
    /// Stage 3 lifecycle fields. `state` defaults to `"active"` via
    /// `NewMemoryRecord::active()`; the others default to `None` meaning
    /// "valid since creation, no expiration, not a replacement".
    pub state: String,
    pub valid_at: Option<String>,
    pub supersedes_memory_id: Option<i64>,
}

impl NewMemoryRecord {
    /// Builder helper for the common case: a brand-new active memory with no
    /// lifecycle annotations. Callers that need to supersede or backdate a
    /// memory override the Stage 3 fields directly.
    pub fn active_defaults() -> (String, Option<String>, Option<i64>) {
        ("active".to_string(), None, None)
    }
}

/// Outcome of `insert_memory_with_dedup`: either a newly-created row or a
/// reference to an existing row with the same `(agent_id, content_hash)`.
///
/// Stage 1 does hash dedup at the `app.rs` layer (via `find_memory_by_hash`
/// + explicit branching), so this enum isn't yet wired into a dedicated DB
/// helper. It's kept here because Stage 3 reflection will likely move the
/// branching down into the store and return this outcome directly.
#[allow(dead_code)]
#[derive(Debug, Clone)]
pub enum InsertMemoryOutcome {
    Inserted(MemoryRecord),
    DuplicateOf(MemoryRecord),
}

impl MetadataStore {
    pub fn new(db_path: PathBuf) -> Result<Self> {
        if let Some(parent) = db_path.parent() {
            fs::create_dir_all(parent).with_context(|| {
                format!(
                    "failed to create metadata db parent dir for pool: {}",
                    parent.display()
                )
            })?;
        }
        let manager = SqliteConnectionManager::file(db_path.clone());
        let pool = Pool::builder()
            .max_size(16)
            .connection_timeout(Duration::from_secs(5))
            .build(manager)
            .with_context(|| {
                format!(
                    "failed to build sqlite connection pool: {}",
                    db_path.display()
                )
            })?;
        Ok(Self { db_path, pool })
    }

    pub fn init(&self) -> Result<()> {
        if let Some(parent) = self.db_path.parent() {
            fs::create_dir_all(parent).with_context(|| {
                format!(
                    "failed to create metadata db parent dir: {}",
                    parent.display()
                )
            })?;
        }

        let conn = self.open_conn()?;
        conn.execute_batch(
            r#"
            PRAGMA journal_mode = WAL;
            PRAGMA synchronous = NORMAL;
            PRAGMA foreign_keys = ON;
            PRAGMA busy_timeout = 5000;

            CREATE TABLE IF NOT EXISTS raw_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_kind TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                user_uid TEXT,
                channel_uid TEXT,
                session_uid TEXT,
                scope TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                user_uid TEXT,
                channel_uid TEXT,
                session_uid TEXT,
                scope TEXT NOT NULL,
                memory_type TEXT NOT NULL DEFAULT 'event',
                content TEXT NOT NULL,
                content_hash TEXT,
                source_event_ids TEXT NOT NULL DEFAULT '[]',
                linked_memory_ids TEXT NOT NULL DEFAULT '[]',
                tags_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                importance REAL NOT NULL DEFAULT 1,
                sentiment TEXT,
                source TEXT NOT NULL DEFAULT 'system',
                embedding_json TEXT,
                state TEXT NOT NULL DEFAULT 'active',
                valid_at TEXT,
                invalid_at TEXT,
                supersedes_memory_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS memory_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER,
                agent_id TEXT NOT NULL,
                event TEXT NOT NULL,
                old_content TEXT,
                new_content TEXT,
                old_metadata TEXT,
                new_metadata TEXT,
                source_task_id INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                user_uid TEXT,
                name_raw TEXT NOT NULL,
                name_norm TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                linked_memory_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS entity_memory_links (
                entity_id INTEGER NOT NULL,
                memory_id INTEGER NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                PRIMARY KEY(entity_id, memory_id)
            );

            CREATE TABLE IF NOT EXISTS agent_state (
                agent_id TEXT PRIMARY KEY,
                mood TEXT NOT NULL,
                vibe TEXT NOT NULL,
                mind TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                dedupe_key TEXT,
                agent_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                last_error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_raw_events_agent_scope_created
            ON raw_events(agent_id, scope, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_raw_events_session_created
            ON raw_events(agent_id, session_uid, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_memories_agent_scope_created
            ON memories(agent_id, scope, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_memories_agent_archived
            ON memories(agent_id, archived_at, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_memories_session_created
            ON memories(agent_id, session_uid, created_at DESC);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_agent_hash
            ON memories(agent_id, content_hash)
            WHERE content_hash IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_memories_agent_state_created
            ON memories(agent_id, state, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_memories_supersedes
            ON memories(supersedes_memory_id)
            WHERE supersedes_memory_id IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_memory_history_memory_created
            ON memory_history(memory_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_memory_history_agent_created
            ON memory_history(agent_id, created_at DESC);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_agent_user_type_norm
            ON entities(agent_id, IFNULL(user_uid, ''), entity_type, name_norm);

            CREATE INDEX IF NOT EXISTS idx_entities_agent_updated
            ON entities(agent_id, updated_at DESC);

            CREATE INDEX IF NOT EXISTS idx_entity_links_memory
            ON entity_memory_links(memory_id);

            CREATE INDEX IF NOT EXISTS idx_entity_links_entity
            ON entity_memory_links(entity_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_tasks_status_created
            ON tasks(status, created_at ASC);

            CREATE INDEX IF NOT EXISTS idx_tasks_agent_kind_status
            ON tasks(agent_id, task_type, status);
            "#,
        )?;

        Ok(())
    }

    /// Insert a turn (a sequence of role/content messages) into `raw_events`.
    ///
    /// Returns the list of inserted row ids in the same order as the supplied
    /// `messages`. Used by Stage 1 `events_turn` to plumb `source_event_ids`
    /// through the `ScoreTurn` task payload so the downstream memory can point
    /// back at the exact raw events it was distilled from.
    pub fn insert_raw_turn(
        &self,
        agent_id: &str,
        user_uid: Option<&str>,
        channel_uid: Option<&str>,
        session_uid: Option<&str>,
        scope: &MemoryScope,
        source: &str,
        messages: &[(String, String)],
        metadata: &Value,
    ) -> Result<Vec<i64>> {
        let now = now_rfc3339();
        let conn = self.open_conn()?;
        let tx = conn.unchecked_transaction()?;
        let mut ids = Vec::with_capacity(messages.len());
        for (role, content) in messages {
            tx.execute(
                r#"
                INSERT INTO raw_events (
                    event_kind, agent_id, user_uid, channel_uid, session_uid,
                    scope, role, content, source, metadata_json, created_at
                ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)
                "#,
                params![
                    "turn",
                    agent_id,
                    user_uid,
                    channel_uid,
                    session_uid,
                    scope.as_str(),
                    role,
                    content,
                    source,
                    to_json_text(metadata),
                    now
                ],
            )?;
            ids.push(tx.last_insert_rowid());
        }
        tx.commit()?;
        Ok(ids)
    }

    pub fn insert_raw_message(
        &self,
        event_kind: &str,
        agent_id: &str,
        user_uid: Option<&str>,
        channel_uid: Option<&str>,
        session_uid: Option<&str>,
        scope: &MemoryScope,
        role: &str,
        content: &str,
        source: &str,
        metadata: &Value,
    ) -> Result<i64> {
        let conn = self.open_conn()?;
        conn.execute(
            r#"
            INSERT INTO raw_events (
                event_kind, agent_id, user_uid, channel_uid, session_uid,
                scope, role, content, source, metadata_json, created_at
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)
            "#,
            params![
                event_kind,
                agent_id,
                user_uid,
                channel_uid,
                session_uid,
                scope.as_str(),
                role,
                content,
                source,
                to_json_text(metadata),
                now_rfc3339()
            ],
        )?;
        Ok(conn.last_insert_rowid())
    }

    /// Session-scoped raw event tail (role + content + created_at), most
    /// recent last. Used by Stage 1 scorer plumbing as `last_k_events`.
    pub fn list_recent_raw_events_for_session(
        &self,
        agent_id: &str,
        session_uid: Option<&str>,
        limit: usize,
    ) -> Result<Vec<RawEventRecord>> {
        if limit == 0 {
            return Ok(Vec::new());
        }
        let conn = self.open_conn()?;
        let (sql, rows): (&str, Vec<RawEventRecord>) = if let Some(sid) = session_uid {
            let mut stmt = conn.prepare(
                r#"
                SELECT id, role, content, created_at
                FROM raw_events
                WHERE agent_id = ?1 AND session_uid = ?2
                ORDER BY created_at DESC, id DESC
                LIMIT ?3
                "#,
            )?;
            let rows: Vec<RawEventRecord> = stmt
                .query_map(params![agent_id, sid, limit as i64], |row| {
                    Ok(RawEventRecord {
                        id: row.get(0)?,
                        role: row.get(1)?,
                        content: row.get(2)?,
                        created_at: row.get(3)?,
                    })
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            ("session", rows)
        } else {
            let mut stmt = conn.prepare(
                r#"
                SELECT id, role, content, created_at
                FROM raw_events
                WHERE agent_id = ?1 AND session_uid IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?2
                "#,
            )?;
            let rows: Vec<RawEventRecord> = stmt
                .query_map(params![agent_id, limit as i64], |row| {
                    Ok(RawEventRecord {
                        id: row.get(0)?,
                        role: row.get(1)?,
                        content: row.get(2)?,
                        created_at: row.get(3)?,
                    })
                })?
                .collect::<rusqlite::Result<Vec<_>>>()?;
            ("no_session", rows)
        };
        let _ = sql;
        // DB returns newest-first; reverse to chronological (oldest-first) so the
        // worker prompt can present the transcript in natural reading order.
        let mut ordered = rows;
        ordered.reverse();
        Ok(ordered)
    }

    /// Session-scoped recently extracted memory contents, newest first.
    /// Used by Stage 1 scorer plumbing as `recently_extracted`.
    pub fn list_recent_memories_by_session(
        &self,
        agent_id: &str,
        session_uid: Option<&str>,
        limit: usize,
    ) -> Result<Vec<String>> {
        if limit == 0 {
            return Ok(Vec::new());
        }
        let conn = self.open_conn()?;
        let rows: Vec<String> = if let Some(sid) = session_uid {
            let mut stmt = conn.prepare(
                r#"
                SELECT content FROM memories
                WHERE agent_id = ?1 AND session_uid = ?2 AND archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?3
                "#,
            )?;
            stmt.query_map(params![agent_id, sid, limit as i64], |row| {
                row.get::<_, String>(0)
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?
        } else {
            let mut stmt = conn.prepare(
                r#"
                SELECT content FROM memories
                WHERE agent_id = ?1 AND session_uid IS NULL AND archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?2
                "#,
            )?;
            stmt.query_map(params![agent_id, limit as i64], |row| {
                row.get::<_, String>(0)
            })?
            .collect::<rusqlite::Result<Vec<_>>>()?
        };
        Ok(rows)
    }

    /// Look up an existing memory by `(agent_id, content_hash)`. Used by Stage 1
    /// hash-based deduplication before inserting a newly-extracted draft.
    pub fn find_memory_by_hash(
        &self,
        agent_id: &str,
        content_hash: &str,
    ) -> Result<Option<MemoryRecord>> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT
                id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                content_hash, source_event_ids, linked_memory_ids,
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                state, valid_at, invalid_at, supersedes_memory_id,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE agent_id = ?1 AND content_hash = ?2
            LIMIT 1
            "#,
        )?;
        stmt.query_row(params![agent_id, content_hash], row_to_memory_record)
            .optional()
            .map_err(Into::into)
    }

    /// Normalize an entity name for dedup. Stage 2 uses simple lowercase +
    /// whitespace-collapse + trim. We intentionally avoid Unicode case folding
    /// surprises by only applying `to_lowercase` — adequate for latin names
    /// and a no-op for most CJK names where case doesn't apply.
    pub fn normalize_entity_name(name: &str) -> String {
        let lowered = name.trim().to_lowercase();
        lowered.split_whitespace().collect::<Vec<_>>().join(" ")
    }

    /// Insert an entity row if `(agent_id, user_uid, entity_type, name_norm)`
    /// is new, otherwise return the existing row. The second tuple element is
    /// `true` iff this call created the row.
    ///
    /// The `entities` unique index enforces dedup at the DB level, but we do
    /// the lookup-before-insert dance so we can always return a concrete
    /// `EntityRecord` without a second read.
    pub fn upsert_entity(
        &self,
        agent_id: &str,
        user_uid: Option<&str>,
        name_raw: &str,
        entity_type: &str,
    ) -> Result<(EntityRecord, bool)> {
        let name_norm = Self::normalize_entity_name(name_raw);
        if name_norm.is_empty() {
            return Err(anyhow!("entity name must not be empty"));
        }
        let now = now_rfc3339();
        let conn = self.open_conn()?;
        let tx = conn.unchecked_transaction()?;

        let existing = tx
            .query_row(
                r#"
                SELECT id, agent_id, user_uid, name_raw, name_norm, entity_type,
                       linked_memory_count, created_at, updated_at
                FROM entities
                WHERE agent_id = ?1
                  AND IFNULL(user_uid, '') = IFNULL(?2, '')
                  AND entity_type = ?3
                  AND name_norm = ?4
                LIMIT 1
                "#,
                params![agent_id, user_uid, entity_type, name_norm],
                row_to_entity_record,
            )
            .optional()?;

        if let Some(entity) = existing {
            tx.execute(
                "UPDATE entities SET updated_at = ?1 WHERE id = ?2",
                params![now, entity.id],
            )?;
            tx.commit()?;
            return Ok((
                EntityRecord {
                    updated_at: now,
                    ..entity
                },
                false,
            ));
        }

        tx.execute(
            r#"
            INSERT INTO entities (
                agent_id, user_uid, name_raw, name_norm, entity_type,
                linked_memory_count, created_at, updated_at
            ) VALUES (?1, ?2, ?3, ?4, ?5, 0, ?6, ?7)
            "#,
            params![
                agent_id,
                user_uid,
                name_raw,
                name_norm,
                entity_type,
                now,
                now
            ],
        )?;
        let id = tx.last_insert_rowid();
        tx.commit()?;

        Ok((
            EntityRecord {
                id,
                agent_id: agent_id.to_string(),
                user_uid: user_uid.map(str::to_string),
                name_raw: name_raw.to_string(),
                name_norm,
                entity_type: entity_type.to_string(),
                linked_memory_count: 0,
                created_at: now.clone(),
                updated_at: now,
            },
            true,
        ))
    }

    /// Idempotently link an entity to a memory. Returns `true` if a new link
    /// was actually inserted (in which case `entities.linked_memory_count` is
    /// bumped for spread-attenuation at recall time).
    pub fn link_entity_to_memory(
        &self,
        entity_id: i64,
        memory_id: i64,
        weight: f32,
    ) -> Result<bool> {
        let now = now_rfc3339();
        let conn = self.open_conn()?;
        let tx = conn.unchecked_transaction()?;
        let rows = tx.execute(
            r#"
            INSERT OR IGNORE INTO entity_memory_links (entity_id, memory_id, weight, created_at)
            VALUES (?1, ?2, ?3, ?4)
            "#,
            params![entity_id, memory_id, weight, now],
        )?;
        if rows > 0 {
            tx.execute(
                "UPDATE entities SET linked_memory_count = linked_memory_count + 1, updated_at = ?1 WHERE id = ?2",
                params![now, entity_id],
            )?;
        }
        tx.commit()?;
        Ok(rows > 0)
    }

    /// Return the entities attached to a given memory, most recent first.
    pub fn list_entities_for_memory(&self, memory_id: i64) -> Result<Vec<EntityRecord>> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT e.id, e.agent_id, e.user_uid, e.name_raw, e.name_norm, e.entity_type,
                   e.linked_memory_count, e.created_at, e.updated_at
            FROM entities e
            JOIN entity_memory_links l ON l.entity_id = e.id
            WHERE l.memory_id = ?1
            ORDER BY l.created_at DESC
            "#,
        )?;
        let rows = stmt.query_map(params![memory_id], row_to_entity_record)?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }

    /// Fetch a batch of entities by id. Preserves the SQL `IN (...)` order,
    /// not the input order.
    pub fn list_entities_by_ids(&self, ids: &[i64]) -> Result<Vec<EntityRecord>> {
        if ids.is_empty() {
            return Ok(Vec::new());
        }
        let conn = self.open_conn()?;
        let sql = format!(
            r#"
            SELECT id, agent_id, user_uid, name_raw, name_norm, entity_type,
                   linked_memory_count, created_at, updated_at
            FROM entities
            WHERE id IN ({})
            "#,
            std::iter::repeat_n("?", ids.len())
                .collect::<Vec<_>>()
                .join(", "),
        );
        let mut stmt = conn.prepare(&sql)?;
        let mut rows = stmt.query(rusqlite::params_from_iter(ids.iter()))?;
        let mut out = Vec::new();
        while let Some(row) = rows.next()? {
            out.push(row_to_entity_record(row)?);
        }
        Ok(out)
    }

    /// Return every memory id that an entity is attached to.
    /// Used by recall's entity-boost pass to propagate entity hits onto
    /// their linked memories.
    pub fn list_linked_memory_ids_for_entity(&self, entity_id: i64) -> Result<Vec<i64>> {
        let conn = self.open_conn()?;
        let mut stmt =
            conn.prepare("SELECT memory_id FROM entity_memory_links WHERE entity_id = ?1")?;
        let rows = stmt.query_map(params![entity_id], |row| row.get::<_, i64>(0))?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }

    /// Batch reverse lookup for entity links.
    ///
    /// Returns `entity_id -> [memory_id...]` and avoids the recall-time N+1
    /// loop over `list_linked_memory_ids_for_entity`.
    pub fn list_linked_memory_ids_for_entities(
        &self,
        entity_ids: &[i64],
    ) -> Result<BTreeMap<i64, Vec<i64>>> {
        if entity_ids.is_empty() {
            return Ok(BTreeMap::new());
        }
        let conn = self.open_conn()?;
        let sql = format!(
            "SELECT entity_id, memory_id FROM entity_memory_links WHERE entity_id IN ({}) ORDER BY entity_id ASC, memory_id ASC",
            (0..entity_ids.len())
                .map(|_| "?")
                .collect::<Vec<_>>()
                .join(",")
        );
        let mut stmt = conn.prepare(&sql)?;
        let mut rows = stmt.query(rusqlite::params_from_iter(entity_ids.iter()))?;
        let mut out: BTreeMap<i64, Vec<i64>> = BTreeMap::new();
        while let Some(row) = rows.next()? {
            let entity_id: i64 = row.get(0)?;
            let memory_id: i64 = row.get(1)?;
            out.entry(entity_id).or_default().push(memory_id);
        }
        Ok(out)
    }

    /// Return the session-adjacent memory ids for a reference memory. Used by
    /// the `Contiguous` recall recipe — up to `before` memories immediately
    /// earlier and up to `after` memories immediately later within the same
    /// `(agent_id, session_uid)` cluster.
    pub fn list_session_memories_around(
        &self,
        agent_id: &str,
        session_uid: Option<&str>,
        reference_memory_id: i64,
        before: usize,
        after: usize,
    ) -> Result<Vec<MemoryRecord>> {
        if before == 0 && after == 0 {
            return Ok(Vec::new());
        }
        let Some(reference) = self.get_memory_by_id(reference_memory_id)? else {
            return Ok(Vec::new());
        };
        let ref_created = reference.created_at.clone();

        let conn = self.open_conn()?;
        let mut out: Vec<MemoryRecord> = Vec::new();

        // Memories strictly before the reference (most recent of those first).
        if before > 0 {
            let (sql, rows): (&str, Vec<MemoryRecord>) = if let Some(sid) = session_uid {
                let mut stmt = conn.prepare(
                    r#"
                    SELECT
                        id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                        content_hash, source_event_ids, linked_memory_ids,
                        tags_json, metadata_json, importance, sentiment, source, embedding_json,
                        state, valid_at, invalid_at, supersedes_memory_id,
                        created_at, updated_at, archived_at, access_count, last_accessed_at
                    FROM memories
                    WHERE agent_id = ?1 AND session_uid = ?2 AND archived_at IS NULL
                      AND id <> ?3
                      AND (created_at < ?4 OR (created_at = ?4 AND id < ?3))
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?5
                    "#,
                )?;
                let rows = stmt
                    .query_map(
                        params![
                            agent_id,
                            sid,
                            reference_memory_id,
                            ref_created,
                            before as i64
                        ],
                        row_to_memory_record,
                    )?
                    .collect::<rusqlite::Result<Vec<_>>>()?;
                ("with_session", rows)
            } else {
                let mut stmt = conn.prepare(
                    r#"
                    SELECT
                        id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                        content_hash, source_event_ids, linked_memory_ids,
                        tags_json, metadata_json, importance, sentiment, source, embedding_json,
                        state, valid_at, invalid_at, supersedes_memory_id,
                        created_at, updated_at, archived_at, access_count, last_accessed_at
                    FROM memories
                    WHERE agent_id = ?1 AND session_uid IS NULL AND archived_at IS NULL
                      AND id <> ?2
                      AND (created_at < ?3 OR (created_at = ?3 AND id < ?2))
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?4
                    "#,
                )?;
                let rows = stmt
                    .query_map(
                        params![agent_id, reference_memory_id, ref_created, before as i64],
                        row_to_memory_record,
                    )?
                    .collect::<rusqlite::Result<Vec<_>>>()?;
                ("no_session", rows)
            };
            let _ = sql;
            out.extend(rows);
        }

        if after > 0 {
            let (sql, rows): (&str, Vec<MemoryRecord>) = if let Some(sid) = session_uid {
                let mut stmt = conn.prepare(
                    r#"
                    SELECT
                        id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                        content_hash, source_event_ids, linked_memory_ids,
                        tags_json, metadata_json, importance, sentiment, source, embedding_json,
                        state, valid_at, invalid_at, supersedes_memory_id,
                        created_at, updated_at, archived_at, access_count, last_accessed_at
                    FROM memories
                    WHERE agent_id = ?1 AND session_uid = ?2 AND archived_at IS NULL
                      AND id <> ?3
                      AND (created_at > ?4 OR (created_at = ?4 AND id > ?3))
                    ORDER BY created_at ASC, id ASC
                    LIMIT ?5
                    "#,
                )?;
                let rows = stmt
                    .query_map(
                        params![
                            agent_id,
                            sid,
                            reference_memory_id,
                            ref_created,
                            after as i64
                        ],
                        row_to_memory_record,
                    )?
                    .collect::<rusqlite::Result<Vec<_>>>()?;
                ("with_session", rows)
            } else {
                let mut stmt = conn.prepare(
                    r#"
                    SELECT
                        id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                        content_hash, source_event_ids, linked_memory_ids,
                        tags_json, metadata_json, importance, sentiment, source, embedding_json,
                        state, valid_at, invalid_at, supersedes_memory_id,
                        created_at, updated_at, archived_at, access_count, last_accessed_at
                    FROM memories
                    WHERE agent_id = ?1 AND session_uid IS NULL AND archived_at IS NULL
                      AND id <> ?2
                      AND (created_at > ?3 OR (created_at = ?3 AND id > ?2))
                    ORDER BY created_at ASC, id ASC
                    LIMIT ?4
                    "#,
                )?;
                let rows = stmt
                    .query_map(
                        params![agent_id, reference_memory_id, ref_created, after as i64],
                        row_to_memory_record,
                    )?
                    .collect::<rusqlite::Result<Vec<_>>>()?;
                ("no_session", rows)
            };
            let _ = sql;
            out.extend(rows);
        }

        Ok(out)
    }

    /// Append a memory lifecycle event to `memory_history`.
    ///
    /// `event` uses snake_case values such as `"add"`, `"skip_dup"`, `"update"`,
    /// `"archive"`, `"supersede"`, `"invalidate"`. Stage 1 only emits
    /// `"add"` and `"skip_dup"`.
    pub fn insert_memory_history(
        &self,
        memory_id: Option<i64>,
        agent_id: &str,
        event: &str,
        old_content: Option<&str>,
        new_content: Option<&str>,
        old_metadata: Option<&Value>,
        new_metadata: Option<&Value>,
        source_task_id: Option<i64>,
    ) -> Result<()> {
        let conn = self.open_conn()?;
        conn.execute(
            r#"
            INSERT INTO memory_history (
                memory_id, agent_id, event, old_content, new_content,
                old_metadata, new_metadata, source_task_id, created_at
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
            "#,
            params![
                memory_id,
                agent_id,
                event,
                old_content,
                new_content,
                old_metadata.map(to_json_text),
                new_metadata.map(to_json_text),
                source_task_id,
                now_rfc3339(),
            ],
        )?;
        Ok(())
    }

    pub fn insert_memory(&self, new_memory: &NewMemoryRecord) -> Result<MemoryRecord> {
        let now = now_rfc3339();
        let conn = self.open_conn()?;
        let source_event_ids_json = to_json_text(&Value::Array(
            new_memory
                .source_event_ids
                .iter()
                .map(|id| Value::Number((*id).into()))
                .collect(),
        ));
        let linked_memory_ids_json = to_json_text(&Value::Array(
            new_memory
                .linked_memory_ids
                .iter()
                .map(|id| Value::Number((*id).into()))
                .collect(),
        ));
        // Stage 3 defaults. `valid_at` falls back to `created_at` so
        // contradiction math always has a lower bound.
        let state = if new_memory.state.trim().is_empty() {
            "active".to_string()
        } else {
            new_memory.state.clone()
        };
        let valid_at = new_memory.valid_at.clone().unwrap_or_else(|| now.clone());
        conn.execute(
            r#"
            INSERT INTO memories (
                agent_id, user_uid, channel_uid, session_uid, scope,
                memory_type, content, content_hash, source_event_ids, linked_memory_ids,
                tags_json, metadata_json, importance, sentiment, source,
                embedding_json, state, valid_at, invalid_at, supersedes_memory_id,
                created_at, updated_at
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, NULL, ?19, ?20, ?21)
            "#,
            params![
                new_memory.agent_id,
                new_memory.user_uid,
                new_memory.channel_uid,
                new_memory.session_uid,
                new_memory.scope.as_str(),
                new_memory.memory_type,
                new_memory.content,
                new_memory.content_hash,
                source_event_ids_json,
                linked_memory_ids_json,
                to_json_text(&Value::Array(
                    new_memory
                        .tags
                        .iter()
                        .map(|tag| Value::String(tag.clone()))
                        .collect()
                )),
                to_json_text(&new_memory.metadata),
                new_memory.importance,
                new_memory.sentiment,
                new_memory.source,
                new_memory.embedding_json,
                state,
                valid_at,
                new_memory.supersedes_memory_id,
                now,
                now
            ],
        )?;
        let id = conn.last_insert_rowid();
        self.get_memory_by_id(id)?
            .ok_or_else(|| anyhow!("memory inserted but not found: {id}"))
    }

    /// Mark `drop_id` as superseded by `keep_id`: sets `state='superseded'`,
    /// `supersedes_memory_id=keep_id`, and stamps `invalid_at` with `now`.
    /// Idempotent — re-superseding an already-superseded memory just
    /// refreshes `updated_at`.
    pub fn supersede_memory(&self, drop_id: i64, keep_id: i64) -> Result<()> {
        if drop_id == keep_id {
            return Ok(());
        }
        let now = now_rfc3339();
        let conn = self.open_conn()?;
        conn.execute(
            r#"
            UPDATE memories
            SET state = 'superseded',
                supersedes_memory_id = ?1,
                invalid_at = COALESCE(invalid_at, ?2),
                updated_at = ?2
            WHERE id = ?3
            "#,
            params![keep_id, now, drop_id],
        )?;
        Ok(())
    }

    /// Mark a memory as invalidated. `invalid_at` defaults to "now" when the
    /// caller doesn't supply a specific moment. `state` transitions to
    /// `"invalidated"` (distinct from `"superseded"` — the former simply
    /// means "no longer true", the latter means "replaced by another memory").
    pub fn set_memory_invalid(
        &self,
        memory_id: i64,
        invalid_at: Option<&str>,
        new_state: Option<&str>,
    ) -> Result<()> {
        let now = now_rfc3339();
        let invalid_ts = invalid_at.unwrap_or(now.as_str()).to_string();
        let state = new_state.unwrap_or("invalidated").to_string();
        let conn = self.open_conn()?;
        conn.execute(
            r#"
            UPDATE memories
            SET state = ?1,
                invalid_at = ?2,
                updated_at = ?3
            WHERE id = ?4
            "#,
            params![state, invalid_ts, now, memory_id],
        )?;
        Ok(())
    }

    pub fn update_memory_embedding(&self, memory_id: i64, embedding_json: &str) -> Result<()> {
        let conn = self.open_conn()?;
        conn.execute(
            "UPDATE memories SET embedding_json = ?1, updated_at = ?2 WHERE id = ?3",
            params![embedding_json, now_rfc3339(), memory_id],
        )?;
        Ok(())
    }

    pub fn get_memory_by_id(&self, memory_id: i64) -> Result<Option<MemoryRecord>> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT
                id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                content_hash, source_event_ids, linked_memory_ids,
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                state, valid_at, invalid_at, supersedes_memory_id,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE id = ?1
            "#,
        )?;
        stmt.query_row(params![memory_id], row_to_memory_record)
            .optional()
            .map_err(Into::into)
    }

    pub fn list_memories_by_ids(&self, ids: &[i64]) -> Result<Vec<MemoryRecord>> {
        if ids.is_empty() {
            return Ok(Vec::new());
        }

        let conn = self.open_conn()?;
        let sql = format!(
            r#"
            SELECT
                id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                content_hash, source_event_ids, linked_memory_ids,
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                state, valid_at, invalid_at, supersedes_memory_id,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE id IN ({})
            "#,
            std::iter::repeat_n("?", ids.len())
                .collect::<Vec<_>>()
                .join(", ")
        );

        let mut stmt = conn.prepare(&sql)?;
        let mut rows = stmt.query(rusqlite::params_from_iter(ids.iter()))?;
        let mut records = Vec::new();
        while let Some(row) = rows.next()? {
            records.push(row_to_memory_record(row)?);
        }
        Ok(records)
    }

    pub fn list_recent_memories(&self, agent_id: &str, limit: usize) -> Result<Vec<MemoryRecord>> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT
                id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                content_hash, source_event_ids, linked_memory_ids,
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                state, valid_at, invalid_at, supersedes_memory_id,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE agent_id = ?1 AND archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT ?2
            "#,
        )?;

        let rows = stmt.query_map(params![agent_id, limit as i64], row_to_memory_record)?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }

    pub fn list_reflection_candidates(
        &self,
        agent_id: &str,
        limit: usize,
    ) -> Result<Vec<MemoryRecord>> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT
                id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                content_hash, source_event_ids, linked_memory_ids,
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                state, valid_at, invalid_at, supersedes_memory_id,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE agent_id = ?1 AND archived_at IS NULL
            ORDER BY importance ASC, created_at ASC
            LIMIT ?2
            "#,
        )?;

        let rows = stmt.query_map(params![agent_id, limit as i64], row_to_memory_record)?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }

    pub fn mark_memories_accessed(&self, memory_ids: &[i64]) -> Result<()> {
        if memory_ids.is_empty() {
            return Ok(());
        }
        let conn = self.open_conn()?;
        let tx = conn.unchecked_transaction()?;
        let now = now_rfc3339();
        let mut stmt = tx.prepare(
            "UPDATE memories SET access_count = access_count + 1, last_accessed_at = ?1 WHERE id = ?2",
        )?;
        for id in memory_ids {
            stmt.execute(params![now, id])?;
        }
        drop(stmt);
        tx.commit()?;
        Ok(())
    }

    pub fn archive_memories(&self, memory_ids: &[i64]) -> Result<()> {
        if memory_ids.is_empty() {
            return Ok(());
        }
        let conn = self.open_conn()?;
        let tx = conn.unchecked_transaction()?;
        let now = now_rfc3339();
        let mut stmt =
            tx.prepare("UPDATE memories SET archived_at = ?1, updated_at = ?2 WHERE id = ?3")?;
        for id in memory_ids {
            stmt.execute(params![now, now, id])?;
        }
        drop(stmt);
        tx.commit()?;
        Ok(())
    }

    pub fn all_active_memories(&self, agent_id: &str) -> Result<Vec<MemoryRecord>> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT
                id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                content_hash, source_event_ids, linked_memory_ids,
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                state, valid_at, invalid_at, supersedes_memory_id,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE agent_id = ?1 AND archived_at IS NULL
            ORDER BY created_at ASC, id ASC
            "#,
        )?;

        let rows = stmt.query_map(params![agent_id], row_to_memory_record)?;
        rows.collect::<rusqlite::Result<Vec<_>>>()
            .map_err(Into::into)
    }

    pub fn get_latest_memory_id_for_agent(&self, agent_id: &str) -> Result<Option<i64>> {
        let conn = self.open_conn()?;
        conn.query_row(
            "SELECT id FROM memories WHERE agent_id = ?1 AND archived_at IS NULL ORDER BY created_at DESC, id DESC LIMIT 1",
            params![agent_id],
            |row| row.get(0),
        )
        .optional()
        .map_err(Into::into)
    }

    pub fn get_agent_state(&self, agent_id: &str) -> Result<AgentStateResponse> {
        let conn = self.open_conn()?;
        let maybe = conn
            .query_row(
                "SELECT agent_id, mood, vibe, mind, updated_at FROM agent_state WHERE agent_id = ?1",
                params![agent_id],
                |row| {
                    Ok(AgentStateResponse {
                        agent_id: row.get(0)?,
                        mood: row.get(1)?,
                        vibe: row.get(2)?,
                        mind: row.get(3)?,
                        updated_at: row.get(4)?,
                    })
                },
            )
            .optional()?;

        Ok(maybe.unwrap_or(AgentStateResponse {
            agent_id: agent_id.to_string(),
            mood: "平静".to_string(),
            vibe: "正常".to_string(),
            mind: "正在整理记忆".to_string(),
            updated_at: now_rfc3339(),
        }))
    }

    pub fn upsert_agent_state(
        &self,
        agent_id: &str,
        patch: &AgentStatePatch,
    ) -> Result<AgentStateResponse> {
        let current = self.get_agent_state(agent_id)?;
        let next = AgentStateResponse {
            agent_id: agent_id.to_string(),
            mood: patch.mood.clone().unwrap_or(current.mood),
            vibe: patch.vibe.clone().unwrap_or(current.vibe),
            mind: patch.mind.clone().unwrap_or(current.mind),
            updated_at: now_rfc3339(),
        };

        let conn = self.open_conn()?;
        conn.execute(
            r#"
            INSERT INTO agent_state (agent_id, mood, vibe, mind, updated_at)
            VALUES (?1, ?2, ?3, ?4, ?5)
            ON CONFLICT(agent_id) DO UPDATE SET
                mood = excluded.mood,
                vibe = excluded.vibe,
                mind = excluded.mind,
                updated_at = excluded.updated_at
            "#,
            params![
                next.agent_id,
                next.mood,
                next.vibe,
                next.mind,
                next.updated_at
            ],
        )?;

        Ok(next)
    }

    pub fn enqueue_task(
        &self,
        task_type: TaskKind,
        agent_id: &str,
        payload: &Value,
        dedupe_key: Option<&str>,
    ) -> Result<TaskRecord> {
        let now = now_rfc3339();
        let conn = self.open_conn()?;
        let tx = conn.unchecked_transaction()?;

        if let Some(key) = dedupe_key
            && let Some(existing) = find_active_task_by_dedupe(&tx, key)?
        {
            tx.commit()?;
            return Ok(existing);
        }

        tx.execute(
            r#"
            INSERT INTO tasks (
                task_type, status, dedupe_key, agent_id, payload_json,
                last_error, retry_count, created_at, updated_at, started_at
            ) VALUES (?1, ?2, ?3, ?4, ?5, NULL, 0, ?6, ?7, NULL)
            "#,
            params![
                task_type.as_str(),
                TaskStatus::Pending.as_str(),
                dedupe_key,
                agent_id,
                to_json_text(payload),
                now,
                now
            ],
        )?;
        let id = tx.last_insert_rowid();
        tx.commit()?;
        self.get_task_by_id(id)?
            .ok_or_else(|| anyhow!("task inserted but not found: {id}"))
    }

    pub fn get_task_by_id(&self, task_id: i64) -> Result<Option<TaskRecord>> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT id, task_type, status, dedupe_key, agent_id, payload_json,
                   last_error, retry_count, created_at, updated_at, started_at
            FROM tasks
            WHERE id = ?1
            "#,
        )?;
        stmt.query_row(params![task_id], row_to_task_record)
            .optional()
            .map_err(Into::into)
    }

    pub fn claim_next_task(&self) -> Result<Option<TaskRecord>> {
        let conn = self.open_conn()?;
        let tx = conn.unchecked_transaction()?;
        let now = Utc::now();
        let stale_cutoff_score_turn = (now - chrono::Duration::minutes(3)).to_rfc3339();
        let stale_cutoff_reflection = (now - chrono::Duration::minutes(30)).to_rfc3339();
        let stale_cutoff_rebuild = (now - chrono::Duration::minutes(60)).to_rfc3339();
        let stale_cutoff_index = (now - chrono::Duration::minutes(5)).to_rfc3339();
        let maybe = tx
            .query_row(
                r#"
                SELECT id, task_type, status, dedupe_key, agent_id, payload_json,
                       last_error, retry_count, created_at, updated_at, started_at
                FROM tasks
                WHERE status = 'pending'
                   OR (
                        status = 'processing'
                    AND started_at IS NOT NULL
                    AND (
                        (task_type = 'score_turn' AND started_at < ?1)
                        OR (task_type = 'reflection_run' AND started_at < ?2)
                        OR (task_type = 'rebuild_trivium' AND started_at < ?3)
                        OR (task_type = 'index_memory' AND started_at < ?4)
                    )
                   )
                ORDER BY created_at ASC
                LIMIT 1
                "#,
                params![
                    stale_cutoff_score_turn,
                    stale_cutoff_reflection,
                    stale_cutoff_rebuild,
                    stale_cutoff_index
                ],
                row_to_task_record,
            )
            .optional()?;

        let Some(task) = maybe else {
            tx.commit()?;
            return Ok(None);
        };

        let now = now_rfc3339();
        tx.execute(
            "UPDATE tasks SET status = 'processing', updated_at = ?1, started_at = ?2 WHERE id = ?3",
            params![now, now, task.id],
        )?;
        tx.commit()?;
        let claimed = self
            .get_task_by_id(task.id)?
            .ok_or_else(|| anyhow!("claimed task disappeared: {}", task.id))?;
        Ok(Some(claimed))
    }

    pub fn complete_task(&self, task_id: i64) -> Result<()> {
        let conn = self.open_conn()?;
        conn.execute(
            "UPDATE tasks SET status = 'completed', updated_at = ?1 WHERE id = ?2",
            params![now_rfc3339(), task_id],
        )?;
        Ok(())
    }

    pub fn fail_task(&self, task_id: i64, error: &str) -> Result<()> {
        let conn = self.open_conn()?;
        conn.execute(
            "UPDATE tasks SET status = 'failed', updated_at = ?1, last_error = ?2, retry_count = retry_count + 1 WHERE id = ?3",
            params![now_rfc3339(), error, task_id],
        )?;
        Ok(())
    }

    pub fn retry_failed_tasks(&self, kind: TaskKind, agent_id: Option<&str>) -> Result<usize> {
        let conn = self.open_conn()?;
        let updated = if let Some(agent_id) = agent_id {
            conn.execute(
                "UPDATE tasks SET status = 'pending', updated_at = ?1 WHERE task_type = ?2 AND status = 'failed' AND agent_id = ?3",
                params![now_rfc3339(), kind.as_str(), agent_id],
            )?
        } else {
            conn.execute(
                "UPDATE tasks SET status = 'pending', updated_at = ?1 WHERE task_type = ?2 AND status = 'failed'",
                params![now_rfc3339(), kind.as_str()],
            )?
        };
        Ok(updated)
    }

    pub fn get_sync_summary(&self) -> Result<SyncSummaryResponse> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT task_type, status, last_error, created_at
            FROM tasks
            ORDER BY created_at ASC
            "#,
        )?;
        let mut rows = stmt.query([])?;

        let mut by_status = BTreeMap::new();
        let mut by_kind = BTreeMap::new();
        let mut failed_tasks = 0usize;
        let mut pending_tasks = 0usize;
        let mut oldest_pending_created_at = None;
        let mut latest_error = None;

        while let Some(row) = rows.next()? {
            let task_type: String = row.get(0)?;
            let status: String = row.get(1)?;
            let last_error: Option<String> = row.get(2)?;
            let created_at: String = row.get(3)?;

            *by_status.entry(status.clone()).or_insert(0usize) += 1;
            *by_kind.entry(task_type).or_insert(0usize) += 1;

            if status == "failed" {
                failed_tasks += 1;
                if latest_error.is_none() {
                    latest_error = last_error;
                }
            }
            if status == "pending" {
                pending_tasks += 1;
                if oldest_pending_created_at.is_none() {
                    oldest_pending_created_at = Some(created_at);
                }
            }
        }

        Ok(SyncSummaryResponse {
            by_status,
            by_kind,
            failed_tasks,
            pending_tasks,
            oldest_pending_created_at,
            latest_error,
        })
    }

    fn open_conn(&self) -> Result<SqlitePooledConnection> {
        let conn = self.pool.get().with_context(|| {
            format!(
                "failed to borrow sqlite connection from pool: {}",
                self.db_path.display()
            )
        })?;
        conn.busy_timeout(Duration::from_secs(5))?;
        conn.pragma_update(None, "foreign_keys", "ON")?;
        Ok(conn)
    }

    pub fn db_path(&self) -> &Path {
        &self.db_path
    }
}

fn row_to_memory_record(row: &rusqlite::Row<'_>) -> rusqlite::Result<MemoryRecord> {
    // Column order must match the 26-column SELECT list used throughout this
    // file. Any reshuffle must be mirrored here.
    let scope: String = row.get(5)?;
    let content_hash: Option<String> = row.get(8)?;
    let source_event_ids_json: String = row.get(9)?;
    let linked_memory_ids_json: String = row.get(10)?;
    let tags_json: String = row.get(11)?;
    let metadata_json: String = row.get(12)?;
    Ok(MemoryRecord {
        id: row.get(0)?,
        agent_id: row.get(1)?,
        user_uid: row.get(2)?,
        channel_uid: row.get(3)?,
        session_uid: row.get(4)?,
        scope: scope.parse().map_err(to_from_sql_error)?,
        memory_type: row.get(6)?,
        content: row.get(7)?,
        content_hash,
        source_event_ids: parse_i64_array(&source_event_ids_json),
        linked_memory_ids: parse_i64_array(&linked_memory_ids_json),
        tags: parse_tags(&tags_json),
        metadata: parse_json_value(&metadata_json),
        importance: row.get(13)?,
        sentiment: row.get(14)?,
        source: row.get(15)?,
        embedding_json: row.get(16)?,
        state: row.get(17)?,
        valid_at: row.get(18)?,
        invalid_at: row.get(19)?,
        supersedes_memory_id: row.get(20)?,
        created_at: row.get(21)?,
        updated_at: row.get(22)?,
        archived_at: row.get(23)?,
        access_count: row.get(24)?,
        last_accessed_at: row.get(25)?,
    })
}

fn parse_i64_array(raw: &str) -> Vec<i64> {
    serde_json::from_str::<Vec<i64>>(raw).unwrap_or_default()
}

fn row_to_entity_record(row: &rusqlite::Row<'_>) -> rusqlite::Result<EntityRecord> {
    Ok(EntityRecord {
        id: row.get(0)?,
        agent_id: row.get(1)?,
        user_uid: row.get(2)?,
        name_raw: row.get(3)?,
        name_norm: row.get(4)?,
        entity_type: row.get(5)?,
        linked_memory_count: row.get(6)?,
        created_at: row.get(7)?,
        updated_at: row.get(8)?,
    })
}

fn row_to_task_record(row: &rusqlite::Row<'_>) -> rusqlite::Result<TaskRecord> {
    let task_type: String = row.get(1)?;
    let status: String = row.get(2)?;
    Ok(TaskRecord {
        id: row.get(0)?,
        task_type: task_type.parse().map_err(to_from_sql_error)?,
        status: status.parse().map_err(to_from_sql_error)?,
        dedupe_key: row.get(3)?,
        agent_id: row.get(4)?,
        payload_json: row.get(5)?,
        last_error: row.get(6)?,
        retry_count: row.get(7)?,
        created_at: row.get(8)?,
        updated_at: row.get(9)?,
        started_at: row.get(10)?,
    })
}

fn find_active_task_by_dedupe(
    tx: &Transaction<'_>,
    dedupe_key: &str,
) -> Result<Option<TaskRecord>> {
    let task = tx
        .query_row(
            r#"
            SELECT id, task_type, status, dedupe_key, agent_id, payload_json,
                   last_error, retry_count, created_at, updated_at, started_at
            FROM tasks
            WHERE dedupe_key = ?1 AND status IN ('pending', 'processing')
            ORDER BY created_at DESC
            LIMIT 1
            "#,
            params![dedupe_key],
            row_to_task_record,
        )
        .optional()?;
    Ok(task)
}

fn parse_tags(raw: &str) -> Vec<String> {
    serde_json::from_str::<Vec<String>>(raw).unwrap_or_default()
}

fn parse_json_value(raw: &str) -> Value {
    serde_json::from_str(raw).unwrap_or(Value::Object(Default::default()))
}

fn to_json_text(value: &Value) -> String {
    serde_json::to_string(value).unwrap_or_else(|_| "{}".to_string())
}

fn now_rfc3339() -> String {
    Utc::now().to_rfc3339()
}

fn to_from_sql_error(err: String) -> rusqlite::Error {
    rusqlite::Error::FromSqlConversionFailure(
        0,
        rusqlite::types::Type::Text,
        Box::new(std::io::Error::new(std::io::ErrorKind::InvalidData, err)),
    )
}

#[cfg(test)]
mod tests {
    use super::{MetadataStore, NewMemoryRecord};
    use crate::types::{MemoryScope, TaskKind, TaskStatus};
    use serde_json::json;
    use tempfile::tempdir;

    fn memory_for(content: &str, hash: Option<&str>) -> NewMemoryRecord {
        NewMemoryRecord {
            agent_id: "shore".to_string(),
            user_uid: Some("u1".to_string()),
            channel_uid: None,
            session_uid: Some("s1".to_string()),
            scope: MemoryScope::Private,
            memory_type: "event".to_string(),
            content: content.to_string(),
            content_hash: hash.map(str::to_string),
            source_event_ids: vec![10, 11],
            linked_memory_ids: vec![],
            tags: vec!["tag-a".to_string()],
            metadata: json!({"k": "v"}),
            importance: 5.0,
            sentiment: None,
            source: "test".to_string(),
            embedding_json: None,
            state: "active".to_string(),
            valid_at: None,
            supersedes_memory_id: None,
        }
    }

    #[test]
    fn insert_raw_turn_returns_ids_in_order() {
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"))
            .expect("create metadata store");
        store.init().expect("init schema");

        let messages = vec![
            ("user".to_string(), "你好".to_string()),
            ("assistant".to_string(), "你也好".to_string()),
            ("user".to_string(), "今天有点累".to_string()),
        ];
        let ids = store
            .insert_raw_turn(
                "shore",
                Some("u1"),
                None,
                Some("s1"),
                &MemoryScope::Private,
                "test",
                &messages,
                &json!({}),
            )
            .expect("insert raw turn");
        assert_eq!(ids.len(), 3);
        assert!(
            ids[0] < ids[1] && ids[1] < ids[2],
            "ids must be monotonically increasing"
        );

        let events = store
            .list_recent_raw_events_for_session("shore", Some("s1"), 10)
            .expect("list recent raw events");
        // Returned in chronological order (oldest-first) per Stage 1 contract.
        assert_eq!(events.len(), 3);
        assert_eq!(events[0].role, "user");
        assert_eq!(events[0].content, "你好");
        assert_eq!(events[2].content, "今天有点累");
    }

    #[test]
    fn memory_hash_dedup_and_history_persist() {
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"))
            .expect("create metadata store");
        store.init().expect("init schema");

        // First insert with hash "abc" succeeds.
        let first = store
            .insert_memory(&memory_for("用户喜欢喝拿铁", Some("abc")))
            .expect("first insert");
        assert_eq!(first.content_hash.as_deref(), Some("abc"));
        assert_eq!(first.source_event_ids, vec![10, 11]);

        // Second insert with the same (agent_id, hash) should fail because of
        // the unique index — confirms hash dedup at the DB level.
        let second = store.insert_memory(&memory_for("用户喜欢喝拿铁", Some("abc")));
        assert!(second.is_err(), "duplicate hash must be rejected");

        // Third insert with a different hash must succeed.
        let third = store
            .insert_memory(&memory_for("用户偏好冷萃咖啡", Some("def")))
            .expect("third insert");
        assert_ne!(third.id, first.id);

        // Lookup by hash finds the original.
        let found = store
            .find_memory_by_hash("shore", "abc")
            .expect("lookup by hash")
            .expect("row present");
        assert_eq!(found.id, first.id);
        assert_eq!(found.content, "用户喜欢喝拿铁");

        // memory_history should record a skip-dup event plus the add events.
        store
            .insert_memory_history(
                Some(first.id),
                "shore",
                "add",
                None,
                Some(&first.content),
                None,
                Some(&first.metadata),
                Some(42),
            )
            .expect("write add history");
        store
            .insert_memory_history(
                Some(first.id),
                "shore",
                "skip_dup",
                Some(&first.content),
                Some("用户喜欢喝拿铁"),
                None,
                None,
                Some(43),
            )
            .expect("write skip_dup history");

        // Session-scoped memory listing returns the most recent first.
        let recent = store
            .list_recent_memories_by_session("shore", Some("s1"), 10)
            .expect("list recent memories");
        assert_eq!(recent.len(), 2);
        assert_eq!(recent[0], "用户偏好冷萃咖啡");
        assert_eq!(recent[1], "用户喜欢喝拿铁");
    }

    #[test]
    fn entity_upsert_and_link_flow() {
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"))
            .expect("create metadata store");
        store.init().expect("init schema");

        // Insert a memory so we have a valid memory_id to link to.
        let mem = store
            .insert_memory(&memory_for(
                "Elena 昨晚去了 Osteria Francescana",
                Some("h1"),
            ))
            .expect("insert memory");

        // First upsert creates the entity.
        let (elena, created) = store
            .upsert_entity("shore", Some("u1"), "Elena", "PERSON")
            .expect("upsert Elena");
        assert!(created, "first upsert should create the entity");
        assert_eq!(elena.linked_memory_count, 0);

        // Second upsert with same (agent, user, type, name_norm) returns the
        // same row with `created = false` and an updated timestamp.
        let (elena_again, created_again) = store
            .upsert_entity("shore", Some("u1"), "  eLeNa  ", "PERSON")
            .expect("upsert Elena again");
        assert!(!created_again, "second upsert should not re-create");
        assert_eq!(elena_again.id, elena.id);

        // Differing entity_type is a different entity.
        let (elena_place, created_place) = store
            .upsert_entity("shore", Some("u1"), "Elena", "PLACE")
            .expect("upsert Elena as PLACE");
        assert!(created_place);
        assert_ne!(elena_place.id, elena.id);

        // Link entity to memory twice — second link must be a no-op.
        let first_link = store
            .link_entity_to_memory(elena.id, mem.id, 1.0)
            .expect("first link");
        assert!(first_link);
        let second_link = store
            .link_entity_to_memory(elena.id, mem.id, 1.0)
            .expect("second link");
        assert!(!second_link);

        // The linked_memory_count reflects exactly one link after the two calls.
        let entities_of_mem = store
            .list_entities_for_memory(mem.id)
            .expect("list entities for memory");
        assert_eq!(entities_of_mem.len(), 1);
        assert_eq!(entities_of_mem[0].id, elena.id);
        assert_eq!(entities_of_mem[0].linked_memory_count, 1);

        // Reverse lookup (entity -> memory_ids) works.
        let linked = store
            .list_linked_memory_ids_for_entity(elena.id)
            .expect("list memory ids");
        assert_eq!(linked, vec![mem.id]);

        // Batch reverse lookup returns a stable entity->memory mapping.
        let linked_batch = store
            .list_linked_memory_ids_for_entities(&[elena.id, elena_place.id])
            .expect("list memory ids batch");
        assert_eq!(linked_batch.get(&elena.id).cloned(), Some(vec![mem.id]));
        assert_eq!(linked_batch.get(&elena_place.id), None);
    }

    #[test]
    fn session_memories_around_returns_neighbors() {
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"))
            .expect("create metadata store");
        store.init().expect("init schema");

        // Three memories in the same session with increasing created_at via
        // sequential inserts (SQLite's created_at comes from `Utc::now`; we
        // sleep briefly between inserts to ensure distinct timestamps).
        let m1 = store
            .insert_memory(&memory_for("阶段一", Some("h1")))
            .expect("insert m1");
        std::thread::sleep(std::time::Duration::from_millis(5));
        let m2 = store
            .insert_memory(&memory_for("阶段二", Some("h2")))
            .expect("insert m2");
        std::thread::sleep(std::time::Duration::from_millis(5));
        let m3 = store
            .insert_memory(&memory_for("阶段三", Some("h3")))
            .expect("insert m3");

        // Around m2, ask for 1 before + 1 after — should return m1 then m3.
        let neighbors = store
            .list_session_memories_around("shore", Some("s1"), m2.id, 1, 1)
            .expect("list neighbors");
        assert_eq!(neighbors.len(), 2);
        let neighbor_ids: Vec<i64> = neighbors.iter().map(|m| m.id).collect();
        assert!(neighbor_ids.contains(&m1.id));
        assert!(neighbor_ids.contains(&m3.id));

        // Ask for 2 before on m3 — should return m2 then m1.
        let before = store
            .list_session_memories_around("shore", Some("s1"), m3.id, 2, 0)
            .expect("list before m3");
        assert_eq!(before.len(), 2);
        // First element is the one closest to m3 (m2).
        assert_eq!(before[0].id, m2.id);
        assert_eq!(before[1].id, m1.id);
    }

    #[test]
    fn supersede_and_invalidate_lifecycle() {
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"))
            .expect("create metadata store");
        store.init().expect("init schema");

        let keep = store
            .insert_memory(&memory_for("用户喜欢拿铁", Some("h1")))
            .expect("insert keep");
        let drop = store
            .insert_memory(&memory_for("用户偏好拿铁", Some("h2")))
            .expect("insert drop");

        // Fresh memories are active and currently-valid.
        assert_eq!(keep.state, "active");
        assert!(keep.is_currently_valid("2099-01-01T00:00:00Z"));

        // Supersede drop by keep.
        store.supersede_memory(drop.id, keep.id).expect("supersede");
        let drop_after = store
            .get_memory_by_id(drop.id)
            .expect("load")
            .expect("exists");
        assert_eq!(drop_after.state, "superseded");
        assert_eq!(drop_after.supersedes_memory_id, Some(keep.id));
        assert!(drop_after.invalid_at.is_some());
        assert!(!drop_after.is_currently_valid("2099-01-01T00:00:00Z"));

        // Keep stays active.
        let keep_after = store
            .get_memory_by_id(keep.id)
            .expect("load")
            .expect("exists");
        assert_eq!(keep_after.state, "active");
        assert!(keep_after.is_currently_valid("2099-01-01T00:00:00Z"));

        // Invalidate the keep with a backdated timestamp.
        store
            .set_memory_invalid(keep.id, Some("2026-04-10T00:00:00Z"), Some("invalidated"))
            .expect("invalidate");
        let keep_invalid = store
            .get_memory_by_id(keep.id)
            .expect("load")
            .expect("exists");
        assert_eq!(keep_invalid.state, "invalidated");
        assert_eq!(
            keep_invalid.invalid_at.as_deref(),
            Some("2026-04-10T00:00:00Z")
        );
        // Once the state transitions away from "active", `is_currently_valid`
        // is always false regardless of the time cursor — callers wanting
        // time-travel use `RecallRequest::include_invalid=true`.
        assert!(!keep_invalid.is_currently_valid("2099-01-01T00:00:00Z"));
        assert!(!keep_invalid.is_currently_valid("2026-01-01T00:00:00Z"));
    }

    #[test]
    fn active_memory_with_future_invalid_at_stays_valid_until_then() {
        // Covers the `invalid_at > now` branch of `is_currently_valid`:
        // a still-active memory with a future expiration should be visible
        // until its deadline and invisible after it.
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"))
            .expect("create metadata store");
        store.init().expect("init schema");

        let mem = store
            .insert_memory(&memory_for("计划在 2027 截止", Some("h_plan")))
            .expect("insert");
        // Manually fast-path the invalid_at without flipping state, to mimic
        // a plan that's explicitly time-boxed rather than invalidated.
        store
            .set_memory_invalid(mem.id, Some("2027-01-01T00:00:00Z"), Some("active"))
            .expect("set future invalid_at on active");
        let updated = store
            .get_memory_by_id(mem.id)
            .expect("load")
            .expect("exists");
        assert_eq!(updated.state, "active");
        assert!(updated.is_currently_valid("2026-12-31T23:59:59Z"));
        assert!(!updated.is_currently_valid("2027-01-02T00:00:00Z"));
    }

    #[test]
    fn supersede_is_noop_for_self() {
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"))
            .expect("create metadata store");
        store.init().expect("init schema");

        let m = store
            .insert_memory(&memory_for("只此一条", Some("only")))
            .expect("insert");

        // Self-supersede is a guarded no-op — state must stay `active`.
        store.supersede_memory(m.id, m.id).expect("self supersede");
        let still = store.get_memory_by_id(m.id).expect("load").expect("exists");
        assert_eq!(still.state, "active");
        assert_eq!(still.supersedes_memory_id, None);
        assert!(still.is_currently_valid("2099-01-01T00:00:00Z"));
    }

    #[test]
    fn task_retry_and_summary_work() {
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"))
            .expect("create metadata store");
        store.init().expect("init sqlite schema");

        let task = store
            .enqueue_task(
                TaskKind::ScoreTurn,
                "shore",
                &json!({"agent_id": "shore"}),
                Some("score:1"),
            )
            .expect("enqueue");
        assert_eq!(task.status, TaskStatus::Pending);

        let claimed = store
            .claim_next_task()
            .expect("claim task")
            .expect("claimed task exists");
        assert_eq!(claimed.id, task.id);
        assert_eq!(claimed.status, TaskStatus::Processing);

        store
            .fail_task(task.id, "worker unavailable")
            .expect("fail task");
        let summary = store.get_sync_summary().expect("summary after failure");
        assert_eq!(summary.failed_tasks, 1);
        assert_eq!(summary.pending_tasks, 0);

        let retried = store
            .retry_failed_tasks(TaskKind::ScoreTurn, None)
            .expect("retry failed score tasks");
        assert_eq!(retried, 1);

        let summary = store.get_sync_summary().expect("summary after retry");
        assert_eq!(summary.failed_tasks, 0);
        assert_eq!(summary.pending_tasks, 1);
    }
}
