# shore-memory-server

`shore-memory` 的 Rust 热路径。负责：

- HTTP / WebSocket 入口
- SQLite 元数据（memories、raw_events、entities、tasks、agent_state、memory_history）
- TriviumDB 向量 / BM25 索引（memory 和 entity 各一套）
- 任务调度（score / reflection / index / rebuild）
- Python Worker 的 HTTP 调用
- 可观测（tracing / Prometheus / 事件流）

## 模块

- `src/main.rs`：初始化 Prometheus recorder、打开 SQLite 连接池、起 TriviumDB、启动 Axum。
- `src/app.rs`：路由、HTTP handler、任务处理器、`AppState`、事件广播。
- `src/db.rs`：SQLite 连接池、所有 SQL、生命周期字段。
- `src/trivium.rs`：`TriviumStore` / `EntityTriviumStore`（memory + entity），`RwLock` 包装。
- `src/worker.rs`：`WorkerClient`，每种调用独立超时。
- `src/recall_recipe.rs`：recall 的融合权重、BM25 归一化、实体衰减。
- `src/types.rs`：全部对外 DTO。
- `src/config.rs`：从 env 读取所有配置项，带默认兜底。

## 路由速查

### 上下文 / 召回

- `POST /v1/context/recall` — 多信号召回（`recipe = fast / hybrid / entity_heavy / contiguous`）。

### 事件写入

- `POST /v1/events/turn` — 一整轮对话。
- `POST /v1/events/message` — 单条消息。

### 记忆管理

- `GET /v1/memories` — 分页 + 筛选浏览（`agent_id / user_uid / channel_uid / session_uid / scope / state / memory_type / content_query / include_archived / limit / offset`）。
- `POST /v1/memories` — 写入人工 memory。
- `GET /v1/memories/export?agent_id=...&include_archived=...` — 导出 memory 快照。
- `GET /v1/memories/{memory_id}` — 详情（memory + entity + history）。
- `PATCH /v1/memories/{memory_id}` — 编辑（content / tags / metadata / importance / sentiment / source / state / valid_at / invalid_at / supersedes_memory_id / archived）。

### Agent 状态

- `GET /v1/agents/{agent_id}/state`
- `PATCH /v1/agents/{agent_id}/state`

### 维护

- `POST /v1/maintenance/scorer/retry`
- `POST /v1/maintenance/reflection/run`
- `POST /v1/maintenance/trivium/rebuild`
- `GET /v1/maintenance/sync-summary`

### 可观测

- `GET /health` — 探活 + 队列摘要 + trace id。
- `GET /metrics` — Prometheus 文本。
- `GET /v1/events` — WebSocket 事件流（`memory.updated / agent.state.updated / maintenance.completed / sync.failed / lagged`）。

## 任务类型

- `score_turn`：对一整轮对话跑一次打分，产出 memory draft 和 entity。
- `index_memory`：对一条 memory 取 embedding 并写 TriviumDB。
- `reflection_run`：跑反思，去重 / supersede / invalidate / archive。
- `rebuild_trivium`：全量重建 memory TriviumDB。

多 worker 并发轮询（`PMS_TASK_WORKERS`）。每种任务有独立 stale cutoff，避免死卡。

## 运行

```powershell
copy .env.example .env   # 首次
cargo run
```

默认监听 `127.0.0.1:7811`。

## 测试

```powershell
cargo test --manifest-path Cargo.toml
```

单元测试覆盖：

- `insert_raw_turn` 顺序、`find_memory_by_hash` dedup、`session_memories_around` 邻居。
- `supersede / invalidate` 生命周期。
- `list_memories_page` 筛选 + `include_archived` 统计一致性。
- `update_memory` 后 `embedding_json` 会被清空、`content_hash` 重算。
- `reflection` / `task retry` / `sync summary` 行为。

## 环境变量

见根目录 README 的 **环境变量一览** 小节。所有变量都有合理默认。
