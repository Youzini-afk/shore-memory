# shore-memory

`shore-memory` 是一个独立的、可嵌入的**长期记忆中台**，为对话式 Agent 提供：

- **写入**：把一段对话 / 一条消息 / 一条人工记忆持久化下来。
- **提炼**：用 LLM 把原始对话压缩成结构化的 memory（含实体、重要度、有效期等）。
- **召回**：按 Agent / 用户 / 频道可见域，做 **向量 + BM25 + 实体 + 连贯性** 的多信号融合召回。
- **反思**：周期性对历史 memory 做去重、失效、supersede、归档。
- **运维**：在线浏览、编辑、归档、导出记忆，并保持索引一致。
- **可观测**：request-id 贯穿、Prometheus 指标、事件流 WebSocket。

本项目是一个**单仓库、双进程**的架构：

- **Rust 服务端（`server/`）**：热路径、召回、任务调度、持久化、可观测。
- **Python 工作端（`worker/`）**：embedding、turn 打分、反思，冷路径。
- 两者通过本地 HTTP 通信，数据落在本机 SQLite + TriviumDB。

## 仓库结构

- `server/` Rust HTTP + WebSocket 服务，包含 SQLite + TriviumDB 集成
- `worker/` Python FastAPI Worker，负责 embedding / 打分 / 反思
- `vendor/TriviumDB/` 向量 + BM25 混合检索引擎（本地 vendored）
- `server/README.md` / `worker/README.md` 每个组件的独立说明

## 核心能力

### 1. 事件与记忆写入

- `POST /v1/events/turn`：提交一整轮对话（多条消息），服务端落 `raw_events`，并排 `score_turn` 任务。
- `POST /v1/events/message`：提交单条消息，可选排队打分。
- `POST /v1/memories`：直接落一条人工 memory，排 `index_memory` 任务建索引。

### 2. 多信号召回

- `POST /v1/context/recall`
- 召回管线（按 `recipe` 决定启用哪些信号）：
  - **semantic**：TriviumDB 向量检索
  - **bm25**：TriviumDB 文本检索，带自适应归一化
  - **entity**：抽实体 → entity-trivium 查邻近实体 → 批量反查关联 memory，做 spread-attenuated 加权
  - **contiguity**：session 相邻 memory 额外加分
- 融合使用 `additive_fuse`，权重可配。
- 支持 `include_invalid` 做 "时光回溯" 召回。
- 支持 `degraded` 标记：embedding 不可用时仍然可用 BM25 + 实体降级。

### 3. 反思 / 去重 / 生命周期

- `POST /v1/maintenance/reflection/run`：调度一次反思任务。
- 反思会：
  - 生成 summary memory
  - 对重复组 `supersede`
  - 对矛盾事实 `supersede` 或 `invalidate`
  - `archive` 过期 memory
  - 更新 `agent_state`（mood / vibe / mind）
- 所有生命周期变动都会 **bump 召回缓存 epoch**，让下一跳召回读到最新状态。

### 4. 记忆运维 API（R3）

- `GET /v1/memories`：带筛选和分页的记忆浏览，可按：
  - `agent_id` / `user_uid` / `channel_uid` / `session_uid`
  - `scope` / `state` / `memory_type`
  - `content_query`（`LIKE` 模糊匹配）
  - `include_archived` / `limit` / `offset`
- `GET /v1/memories/{memory_id}`：返回 memory 主体 + 关联 entity + 变更历史。
- `PATCH /v1/memories/{memory_id}`：手工编辑 memory，可改：
  - `content` / `tags` / `metadata` / `importance` / `sentiment` / `source`
  - `state` / `valid_at` / `invalid_at` / `supersedes_memory_id`
  - `archived`
- 编辑后会：
  - 写入 `memory_history`
  - 同步 TriviumDB payload（`update_payload`）
  - 若 `content` 变更：清空旧 embedding 并排 `rebuild_trivium` 任务
  - bump recall cache epoch
  - 广播 `memory.updated` 事件
- `GET /v1/memories/export`：导出指定 `agent_id` 的全部记忆快照，支持 `include_archived`。

### 5. Agent State

- `GET /v1/agents/{agent_id}/state`
- `PATCH /v1/agents/{agent_id}/state`（mood / vibe / mind 三元组）

### 6. 事件流（WebSocket）

- `GET /v1/events`
- 推送：
  - `agent.state.updated`
  - `memory.updated`
  - `maintenance.completed`
  - `sync.failed`
  - `lagged`（订阅方跟不上时的丢弃通知，不会直接断开连接）

### 7. 可观测性

- **Tracing**
  - `x-request-id` 自动生成和传播（`tower-http::request_id`）
  - 所有 HTTP handler 和 task 处理函数都带 `#[tracing::instrument]` span
- **Prometheus `/metrics`**，关键指标：
  - `shore_memory_http_duration_seconds{route,status}`
  - `shore_memory_recall_duration_seconds{recipe,degraded}`
  - `shore_memory_trivium_search_duration_seconds{kind}`
  - `shore_memory_worker_call_duration_seconds{op}`
  - `shore_memory_worker_call_errors_total{op}`
  - `shore_memory_task_processing_duration_seconds{kind,status}`
  - `shore_memory_task_errors_total{kind}`
  - `shore_memory_task_queue_depth{status}`
  - `shore_memory_cache_hit_total{cache}` / `shore_memory_cache_miss_total{cache}`
  - `shore_memory_recall_degraded_total{reason}`
- **`/health`** 快速探活（含 worker 可达性、任务队列深度、trace id）

### 8. 任务队列

- 任务类型：`score_turn`、`reflection_run`、`index_memory`、`rebuild_trivium`
- 多 worker 并发轮询，`PMS_TASK_WORKERS` 控制并发度
- 按任务类型差异化的 stale cutoff（例如 `reflection_run` 30 分钟，`rebuild_trivium` 60 分钟）
- 支持 `POST /v1/maintenance/scorer/retry` 重试失败任务
- 支持 `POST /v1/maintenance/trivium/rebuild` 全量重建索引
- `GET /v1/maintenance/sync-summary` 返回当前队列健康快照

## 性能与稳定性（R1 / R2 汇总）

- **SQLite 连接池**（r2d2 + 自定义 `ManageConnection`），避免高并发下打开/关闭连接抖动。
- **TriviumDB 并发**：`Mutex` → `RwLock`，召回可并发、写入仍串行。
- **TriviumDB payload 一致性**：memory 的 `state / archived` 变化会原地同步到 TriviumDB，不用全量 rebuild。
- **Recall 缓存**：moka，**按 `agent_id` + `epoch` 分片**，一次失效只清一个 agent，不会全局震荡。
- **Embedding 缓存**：moka，`(text hash) → Vec<f32>`，短 TTL。
- **Worker 超时**：`embed / embed_batch / extract_entities / score_turn / reflect` 每种操作各自独立超时。
- **WS lag**：订阅端跟不上时只丢事件并发 `lagged` 通知，不会踢连接。
- **批量实体反查**：`list_linked_memory_ids_for_entities`，一次 SQL 完成实体 → memory 的反向索引，消灭 N+1。
- **反思批量快照**：`list_memories_by_ids` 一次取齐 old snapshot，避免反思阶段 N 次 `get_memory_by_id`。

## 快速开始

### 1. 先启动 Python Worker

```powershell
# 在 worker/ 目录下
copy .env.example .env          # 首次
uvicorn app.main:app --host 127.0.0.1 --port 7812
```

Worker 没有配置 LLM 也能跑：自动回落到启发式打分 / 反思。

### 2. 再启动 Rust Server

```powershell
# 在 server/ 目录下
copy .env.example .env          # 首次
cargo run
```

默认监听 `http://127.0.0.1:7811`。

### 3. 冒烟验证

```powershell
# 健康检查
curl http://127.0.0.1:7811/health

# Prometheus 指标
curl http://127.0.0.1:7811/metrics

# 写一条 memory
curl -X POST http://127.0.0.1:7811/v1/memories `
     -H "Content-Type: application/json" `
     -d '{"agent_id":"shore","scope":"private","content":"用户喜欢夜间散步"}'

# 浏览 memory
curl "http://127.0.0.1:7811/v1/memories?agent_id=shore&limit=10"

# 召回
curl -X POST http://127.0.0.1:7811/v1/context/recall `
     -H "Content-Type: application/json" `
     -d '{"agent_id":"shore","query":"散步","limit":5}'
```

## 环境变量一览（`server/.env.example`）

- **网络 / 存储**
  - `PMS_HOST` / `PMS_PORT`：服务监听地址
  - `PMS_DATA_DIR`：数据根目录
  - `PMS_METADATA_DB_PATH`：SQLite 元数据 DB 路径
  - `PMS_TRIVIUM_DB_PATH`：Memory TriviumDB 路径
  - `PMS_ENTITY_TRIVIUM_DB_PATH`：Entity TriviumDB 路径
- **Worker 通信**
  - `PMS_WORKER_BASE_URL`：Python worker 的 base URL
  - `PMS_WORKER_TIMEOUT_MS`：兜底超时
  - `PMS_WORKER_TIMEOUT_EMBED_MS` / `PMS_WORKER_TIMEOUT_EMBED_BATCH_MS`
  - `PMS_WORKER_TIMEOUT_EXTRACT_ENTITIES_MS`
  - `PMS_WORKER_TIMEOUT_SCORE_TURN_MS`
  - `PMS_WORKER_TIMEOUT_REFLECT_MS`
- **缓存**
  - `PMS_RECALL_CACHE_TTL_SECS`
  - `PMS_EMBEDDING_CACHE_TTL_SECS`
- **任务队列**
  - `PMS_TASK_POLL_INTERVAL_MS`
  - `PMS_TASK_WORKERS`（并发 worker 数，默认 4）
- **召回调参**
  - `PMS_SEARCH_TOP_K` / `PMS_SEARCH_EXPAND_DEPTH` / `PMS_SEARCH_MIN_SCORE`
  - `PMS_ENTITY_MIN_SCORE` / `PMS_ENTITY_BOOST_WEIGHT`
  - `PMS_CONTIGUITY_BOOST_WEIGHT` / `PMS_CONTIGUITY_BOOST_VALUE`
  - `PMS_CONTIGUITY_BEFORE` / `PMS_CONTIGUITY_AFTER`
- **事件通道**
  - `PMS_EVENT_CHANNEL_CAP`：WebSocket 广播 channel 容量（默认 1024）

## 数据模型速览

- `raw_events`：所有外部事件的原始流水
- `memories`：提炼后的 memory，带完整 lifecycle（`state / valid_at / invalid_at / supersedes_memory_id / archived_at`）
- `memory_history`：每条 memory 的增改删历史（`add / update / archive / supersede / invalidate / skip_dup`）
- `entities` + `entity_memory_links`：实体与 memory 的多对多关系
- `agent_state`：每个 agent 的 mood / vibe / mind 快照
- `tasks`：调度队列

## 测试

```powershell
# Rust 单测
cargo test --manifest-path server/Cargo.toml

# Worker 语法检查
python -m py_compile worker/app/main.py
```

## 设计原则

- **单机优先**：所有依赖（SQLite、TriviumDB、Worker）都在本机跑，部署是一个目录。
- **冷热分离**：热路径（召回 / 写入 / 查询）在 Rust；冷路径（embedding / LLM 推理）在 Python。
- **对外稳定，对内可演进**：HTTP schema 尽量稳定，但内部索引 / 缓存 / 任务形态可以重建。
- **默认可用，配置兜底**：每个关键参数都有合理默认，LLM 缺席也能降级运行。
- **可观测优先**：任何新增热点都必须带 tracing span 和 Prometheus 指标。

## 路线图

- **R1（已完成）**：连接池、并发锁优化、per-operation timeout、batch reverse lookup、per-agent recall 缓存 epoch。
- **R2（已完成）**：request-id + tracing、Prometheus 指标、WS lag 容忍、多 worker 任务队列、差异化 stale cutoff。
- **R3（进行中 — 基础层已完成）**：记忆运维 API（list / detail / edit / archive / export），编辑后的补偿与一致性。
- **R3+（后续）**：导入接口、批量补偿工具、回放脚本、管理 UI。
