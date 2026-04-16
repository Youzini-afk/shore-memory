use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::Duration;

use anyhow::{Context, Result, anyhow};
use chrono::Utc;
use rusqlite::{Connection, OptionalExtension, Transaction, params};
use serde_json::Value;

use crate::types::{
    AgentStatePatch, AgentStateResponse, MemoryRecord, MemoryScope, SyncSummaryResponse, TaskKind,
    TaskRecord, TaskStatus,
};

#[derive(Debug, Clone)]
pub struct MetadataStore {
    db_path: PathBuf,
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
    pub tags: Vec<String>,
    pub metadata: Value,
    pub importance: f32,
    pub sentiment: Option<String>,
    pub source: String,
    pub embedding_json: Option<String>,
}

impl MetadataStore {
    pub fn new(db_path: PathBuf) -> Self {
        Self { db_path }
    }

    pub fn init(&self) -> Result<()> {
        if let Some(parent) = self.db_path.parent() {
            fs::create_dir_all(parent).with_context(|| {
                format!("failed to create metadata db parent dir: {}", parent.display())
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
                tags_json TEXT NOT NULL DEFAULT '[]',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                importance REAL NOT NULL DEFAULT 1,
                sentiment TEXT,
                source TEXT NOT NULL DEFAULT 'system',
                embedding_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT
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

            CREATE INDEX IF NOT EXISTS idx_memories_agent_scope_created
            ON memories(agent_id, scope, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_memories_agent_archived
            ON memories(agent_id, archived_at, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_tasks_status_created
            ON tasks(status, created_at ASC);

            CREATE INDEX IF NOT EXISTS idx_tasks_agent_kind_status
            ON tasks(agent_id, task_type, status);
            "#,
        )?;

        Ok(())
    }

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
    ) -> Result<()> {
        let now = now_rfc3339();
        let conn = self.open_conn()?;
        let tx = conn.unchecked_transaction()?;
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
        }
        tx.commit()?;
        Ok(())
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
    ) -> Result<()> {
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
        Ok(())
    }

    pub fn insert_memory(&self, new_memory: &NewMemoryRecord) -> Result<MemoryRecord> {
        let now = now_rfc3339();
        let conn = self.open_conn()?;
        conn.execute(
            r#"
            INSERT INTO memories (
                agent_id, user_uid, channel_uid, session_uid, scope,
                memory_type, content, tags_json, metadata_json, importance,
                sentiment, source, embedding_json, created_at, updated_at
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15)
            "#,
            params![
                new_memory.agent_id,
                new_memory.user_uid,
                new_memory.channel_uid,
                new_memory.session_uid,
                new_memory.scope.as_str(),
                new_memory.memory_type,
                new_memory.content,
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
                now,
                now
            ],
        )?;
        let id = conn.last_insert_rowid();
        self.get_memory_by_id(id)?
            .ok_or_else(|| anyhow!("memory inserted but not found: {id}"))
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
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
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
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE id IN ({})
            "#,
            std::iter::repeat_n("?", ids.len()).collect::<Vec<_>>().join(", ")
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
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE agent_id = ?1 AND archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT ?2
            "#,
        )?;

        let rows = stmt.query_map(params![agent_id, limit as i64], row_to_memory_record)?;
        rows.collect::<rusqlite::Result<Vec<_>>>().map_err(Into::into)
    }

    pub fn list_reflection_candidates(&self, agent_id: &str, limit: usize) -> Result<Vec<MemoryRecord>> {
        let conn = self.open_conn()?;
        let mut stmt = conn.prepare(
            r#"
            SELECT
                id, agent_id, user_uid, channel_uid, session_uid, scope, memory_type, content,
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE agent_id = ?1 AND archived_at IS NULL
            ORDER BY importance ASC, created_at ASC
            LIMIT ?2
            "#,
        )?;

        let rows = stmt.query_map(params![agent_id, limit as i64], row_to_memory_record)?;
        rows.collect::<rusqlite::Result<Vec<_>>>().map_err(Into::into)
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
        let mut stmt = tx.prepare(
            "UPDATE memories SET archived_at = ?1, updated_at = ?2 WHERE id = ?3",
        )?;
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
                tags_json, metadata_json, importance, sentiment, source, embedding_json,
                created_at, updated_at, archived_at, access_count, last_accessed_at
            FROM memories
            WHERE agent_id = ?1 AND archived_at IS NULL
            ORDER BY created_at ASC, id ASC
            "#,
        )?;

        let rows = stmt.query_map(params![agent_id], row_to_memory_record)?;
        rows.collect::<rusqlite::Result<Vec<_>>>().map_err(Into::into)
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
            mood: patch
                .mood
                .clone()
                .unwrap_or(current.mood),
            vibe: patch
                .vibe
                .clone()
                .unwrap_or(current.vibe),
            mind: patch
                .mind
                .clone()
                .unwrap_or(current.mind),
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
            && let Some(existing) = find_active_task_by_dedupe(&tx, key)? {
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
        let stale_cutoff = Utc::now() - chrono::Duration::minutes(10);
        let stale_cutoff = stale_cutoff.to_rfc3339();
        let maybe = tx
            .query_row(
                r#"
                SELECT id, task_type, status, dedupe_key, agent_id, payload_json,
                       last_error, retry_count, created_at, updated_at, started_at
                FROM tasks
                WHERE status = 'pending'
                   OR (status = 'processing' AND started_at IS NOT NULL AND started_at < ?1)
                ORDER BY created_at ASC
                LIMIT 1
                "#,
                params![stale_cutoff],
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

    fn open_conn(&self) -> Result<Connection> {
        if let Some(parent) = self.db_path.parent() {
            fs::create_dir_all(parent).with_context(|| {
                format!("failed to create db parent dir: {}", parent.display())
            })?;
        }
        let conn = Connection::open(&self.db_path)
            .with_context(|| format!("failed to open sqlite db: {}", self.db_path.display()))?;
        conn.busy_timeout(Duration::from_secs(5))?;
        conn.pragma_update(None, "foreign_keys", "ON")?;
        Ok(conn)
    }

    pub fn db_path(&self) -> &Path {
        &self.db_path
    }
}

fn row_to_memory_record(row: &rusqlite::Row<'_>) -> rusqlite::Result<MemoryRecord> {
    let scope: String = row.get(5)?;
    let tags_json: String = row.get(8)?;
    let metadata_json: String = row.get(9)?;
    Ok(MemoryRecord {
        id: row.get(0)?,
        agent_id: row.get(1)?,
        user_uid: row.get(2)?,
        channel_uid: row.get(3)?,
        session_uid: row.get(4)?,
        scope: scope.parse().map_err(to_from_sql_error)?,
        memory_type: row.get(6)?,
        content: row.get(7)?,
        tags: parse_tags(&tags_json),
        metadata: parse_json_value(&metadata_json),
        importance: row.get(10)?,
        sentiment: row.get(11)?,
        source: row.get(12)?,
        embedding_json: row.get(13)?,
        created_at: row.get(14)?,
        updated_at: row.get(15)?,
        archived_at: row.get(16)?,
        access_count: row.get(17)?,
        last_accessed_at: row.get(18)?,
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

fn find_active_task_by_dedupe(tx: &Transaction<'_>, dedupe_key: &str) -> Result<Option<TaskRecord>> {
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
    use super::MetadataStore;
    use crate::types::{TaskKind, TaskStatus};
    use serde_json::json;
    use tempfile::tempdir;

    #[test]
    fn task_retry_and_summary_work() {
        let temp_dir = tempdir().expect("tempdir");
        let store = MetadataStore::new(temp_dir.path().join("test.sqlite3"));
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

        store.fail_task(task.id, "worker unavailable").expect("fail task");
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
