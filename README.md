# Shore Memory

`shore-memory` 是 `Shore` 项目的独立记忆中台。

它的目标不是做一个“某个 Bot 的内部模块”，而是把记忆能力抽出来，作为一个单独服务，统一为以下角色提供能力：

- `AstrBot` 插件
- `Shore` 桌面客户端
- 未来的 `Hermes` worker / agent
- 其他聊天端、群聊端、事件源

这意味着 `shore-memory` 更像一个“记忆基础设施”，而不是某个前端或某个 Bot 框架的附属目录。

## 项目定位

在 `Shore` 的整体规划里，我们希望把三件事情拆开：

- `Bot 框架`：负责对接聊天平台、插件系统、消息流转
- `记忆中台`：负责长期记忆、召回、状态维护、异步整理
- `客户端`：负责桌面交互、桌宠能力、可视化和控制入口

`shore-memory` 负责第二部分，也就是“独立记忆库 / 记忆中台”。

当前实现遵循这些原则：

- 热路径用 `Rust`，保证短对话环境下的召回速度
- 异步智能处理放在 `Python worker`，方便先落 Embedding、Scorer、Reflection
- 不修改 `AstrBot` 本体，通过外部插件桥接接入
- 不依赖外部 Redis / MQ，先用 `SQLite + WAL` 承担元数据和任务队列
- 直接复用 vendored 的 `TriviumDB` Rust 源码，不把热路径偷偷退回 Python

## 当前状态

当前仓库已经是一个可以运行的 v1 原型，具备以下能力：

- 记忆写入：支持标准 turn 写入和通用 message/event 写入
- 记忆召回：支持结构化记忆上下文召回
- 角色状态：支持 `mood / vibe / mind` 的读写
- 异步整理：支持 turn scorer、reflection、memory indexing、全量 rebuild
- 运维接口：支持失败任务重试、同步摘要、Trivium 重建
- 事件流：支持 WebSocket 推送状态更新和维护事件

目前更适合用作：

- `AstrBot` 的长期互动记忆后端
- 桌面客户端的统一记忆中心
- 后续多端角色状态同步的基础服务

## 架构概览

```text
AstrBot 插件 / Shore 客户端 / 其他事件源
                |
                v
        shore-memory/server
        Rust HTTP + WebSocket
                |
      +---------+---------+
      |                   |
      v                   v
SQLite(WAL)         TriviumDB
元数据 / 任务 / 状态   向量 / 图谱 / 检索
      |
      v
shore-memory/worker
Python Embedding / Scorer / Reflection
```

核心职责拆分如下：

- `server/`
  - 对外提供 HTTP API 和 WebSocket 事件流
  - 管理 SQLite 元数据、原始事件、任务状态、Agent State
  - 负责同步 recall 热路径
  - 调用 `TriviumDB` 进行记忆索引和检索
  - 调度 Python worker 做异步总结和整理
- `worker/`
  - 负责 embedding
  - 负责 turn scorer
  - 负责 reflection / summary memory 生成
  - 未配置 LLM 时会退化为启发式逻辑，避免主服务完全不可用
- `vendor/TriviumDB/`
  - vendored 的 `TriviumDB` Rust 源码
  - 作为当前仓库的一部分参与构建
  - 避免继续依赖外部兄弟目录

## 记忆模型

当前 v1 采用“单用户 / 单租户，但支持多作用域”的思路。

关键身份字段：

- `agent_id`
- `user_uid`
- `channel_uid`
- `session_uid`
- `scope`

目前支持四种作用域：

- `private`：私聊记忆
- `group`：群聊记忆
- `shared`：跨端共享记忆
- `system`：系统设定与全局角色记忆

这样做的目的，是让私聊、群聊、系统设定、跨端共享记忆在召回时天然隔离，避免串域污染。

## 已实现接口

当前 `server` 已提供这些主要接口：

- `GET /health`
- `POST /v1/context/recall`
- `POST /v1/events/turn`
- `POST /v1/events/message`
- `POST /v1/memories`
- `GET /v1/agents/{agent_id}/state`
- `PATCH /v1/agents/{agent_id}/state`
- `POST /v1/maintenance/scorer/retry`
- `POST /v1/maintenance/reflection/run`
- `POST /v1/maintenance/trivium/rebuild`
- `GET /v1/maintenance/sync-summary`
- `WS /v1/events`

接口对应实现可参考：

- [`server/src/app.rs`](server/src/app.rs)
- [`server/src/types.rs`](server/src/types.rs)
- [`server/src/db.rs`](server/src/db.rs)

## 目录结构

```text
shore-memory/
├─ README.md
├─ .gitignore
├─ server/
│  ├─ .env.example
│  ├─ Cargo.toml
│  ├─ README.md
│  └─ src/
├─ worker/
│  ├─ .env.example
│  ├─ pyproject.toml
│  ├─ README.md
│  └─ app/
└─ vendor/
   └─ TriviumDB/
```

## 快速开始

### 1. 环境要求

- Rust stable
- Python 3.11+
- 推荐安装 `uv`

### 2. 配置服务端

复制：

```powershell
Copy-Item server\.env.example server\.env
```

常用配置项：

- `PMS_HOST`：默认 `127.0.0.1`
- `PMS_PORT`：默认 `7811`
- `PMS_METADATA_DB_PATH`：SQLite 元数据路径
- `PMS_TRIVIUM_DB_PATH`：Trivium 数据路径
- `PMS_WORKER_BASE_URL`：Python worker 地址，默认 `http://127.0.0.1:7812`

### 3. 配置 Worker

复制：

```powershell
Copy-Item worker\.env.example worker\.env
```

需要关注：

- `PMW_EMBEDDING_API_KEY`
- `PMW_EMBEDDING_API_BASE`
- `PMW_EMBEDDING_MODEL`
- `PMW_LLM_API_KEY`
- `PMW_LLM_API_BASE`
- `PMW_LLM_MODEL`

说明：

- Embedding 相关配置建议填写，否则无法走远程 embedding
- LLM 配置是可选的；不填时 worker 会使用启发式 scorer / reflection 退化运行

### 4. 启动 Worker

推荐：

```powershell
cd worker
uv run uvicorn app.main:app --host 127.0.0.1 --port 7812
```

### 5. 启动 Server

```powershell
cd server
cargo run
```

### 6. 健康检查

启动后可访问：

```text
GET http://127.0.0.1:7811/health
```

## 与 AstrBot 的关系

`shore-memory` 不修改 `AstrBot` 本体。

推荐接入方式是通过单独的桥接插件调用：

- recall：在 `on_llm_request` 前注入记忆上下文
- writeback：在 `on_llm_response` 后回写 turn

当前工作区里对应插件目录是：

- `E:\cursor_project\ananbot\astrbot_plugin_shore_bridge`

## 开发与验证

Rust 侧：

```powershell
cd server
cargo test
```

Python worker：

```powershell
cd worker
python -m compileall app
```

## 当前边界

这个仓库当前只负责“记忆中台”本身，不负责：

- 桌面客户端 UI
- AstrBot 本体修改
- Hermes 的完整 agent 编排
- 多节点部署和分布式一致性

换句话说，`shore-memory` 解决的是“统一记忆服务”问题，而不是整个 `Shore` 项目的全部问题。

## 后续建议方向

接下来比较自然的演进方向有：

- 完善 `AstrBot` 插件桥接，形成稳定接入链路
- 给客户端增加记忆浏览、编辑、状态观察界面
- 把 `Hermes` 的 agent 任务接进统一记忆上下文
- 增加补偿工具、导入导出、回放重建脚本
- 进一步优化 recall 缓存与降级策略

## 说明

- `vendor/TriviumDB` 是从本地最新 `E:\cursor_project\ananbot\TriviumDB` 同步进来的 vendored 版本
- 后续如果更新 `TriviumDB`，建议显式同步 vendored 内容，而不是重新改回外部 path dependency
- 当前仓库历史中保留了 `PeroCore` 的 git lineage，用于保留既有贡献者信息；但当前工作树已经聚焦为独立的 `shore-memory` 项目
