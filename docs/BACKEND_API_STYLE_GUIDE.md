# PeroCore Backend API 开发规范参考手册

> **版本**：1.1.0 · **更新时间**：2026-04-13
> **适用范围**：`backend/routers/*.py` 所有主应用 HTTP / WebSocket 路由
> **不适用范围**：外部插件（`mods/_external_plugins/`）、MOD 路由、插件内聚型路由（如 `social_router.py`）

---

## 目录

1. [设计原则](#1-设计原则)
2. [路由组织规则](#2-路由组织规则)
3. [路径命名规则](#3-路径命名规则)
4. [HTTP 方法规则](#4-http-方法规则)
5. [请求体建模规则](#5-请求体建模规则)
6. [响应体规则](#6-响应体规则)
7. [错误处理规则](#7-错误处理规则)
8. [领域边界规则](#8-领域边界规则)
9. [WebSocket 规则](#9-websocket-规则)
10. [标签与命名规则](#10-标签与命名规则)
11. [前端兼容规则](#11-前端兼容规则)
12. [新增接口准入清单](#12-新增接口准入清单)
13. [接口分类参考：REST / Action / RPC](#13-接口分类参考rest--action--rpc)
14. [当前领域路由速查表](#14-当前领域路由速查表)
15. [反模式速查（禁止做的事）](#15-反模式速查禁止做的事)

---

## 1. 设计原则

PeroCore 主应用 backend API 的统一化目标，**不是让所有接口长得完全一样**，而是让同类接口遵守同类规则，形成可维护、可扩展、可迁移的 API 体系。

具体而言，遵守以下五条核心原则：

| # | 原则 | 说明 |
|---|------|------|
| 1 | **延续为主，不推翻重来** | 优先在现有风格基础上统一，避免一次性大规模破坏性重构 |
| 2 | **资源型 / 动作型接口分开治理** | CRUD 接口和 action 接口规则不同，不强行统一成一套 |
| 3 | **可维护优先于形式绝对统一** | 先保证结构可预测、边界清晰，再追求视觉上的一致 |
| 4 | **前端可迁移性纳入规则设计** | 任何 backend 变更必须评估对前端的影响 |
| 5 | **约束范围明确** | 有明确的"本规范适用"与"本规范例外"两套边界 |

---

## 2. 路由组织规则

### 2.1 Router 必须使用 `prefix`（首要规则）

主应用每一个 router 文件必须通过 `APIRouter(prefix="...")` 声明其命名空间。

**✅ 推荐写法**

```python
router = APIRouter(prefix="/api/memories", tags=["memory"])

@router.get("")                    # 完整路径：GET /api/memories
async def list_memories(): ...

@router.get("/{memory_id}")        # 完整路径：GET /api/memories/{memory_id}
async def get_memory(memory_id: int): ...

@router.post("/reindex")           # 完整路径：POST /api/memories/reindex
async def reindex(): ...
```

**❌ 禁止写法**

```python
router = APIRouter(tags=["memory"])   # ❌ 没有 prefix

@router.get("/api/memories")          # ❌ 在装饰器里写完整路径
async def list_memories(): ...
```

**原因**：router 边界清晰、路径命名空间可统一治理、日后迁移代价小。

---

### 2.2 `main.py` 只做挂载，不堆积业务实现

`main.py` 应当是一个"装配入口"，只负责：

- `app.include_router(xxx_router)`
- 生命周期钩子（`on_startup` / `on_shutdown`）
- 应用初始化逻辑
- 中间件注册

**不应在 `main.py` 里出现的内容**：

- 业务接口的 `@app.get(...)` / `@app.post(...)` 装饰器
- 路由的具体实现逻辑
- WebSocket handler 实现（应抽到 `ws_router.py`）

**✅ `main.py` 挂载示例**

```python
app.include_router(agent_router)
app.include_router(memory_router)
app.include_router(maintenance_router)
app.include_router(ws_router)        # WebSocket 也 router 化后统一挂载
```

---

### 2.3 一个业务域只保留一个主命名空间

同一业务域不得同时维护两套并行标准入口。

| 业务域 | 标准命名空间 | 说明 |
|--------|-------------|------|
| 记忆资源 | `/api/memories` | 复数，资源集合 |
| 记忆运维 | `/api/maintenance/memory` | 归入 maintenance 域 |
| 模型配置 | `/api/models` | 复数 |
| 全局配置 | `/api/configs` | 统一为 configs |
| MCP 配置 | `/api/mcp` | 保持现状 |
| Agent 管理 | `/api/agents` | 复数 |
| 任务调度 | `/api/scheduler` | 当前标准 |
| 系统管理 | `/api/system` | 统计、状态、重置 |
| 运维操作 | `/api/maintenance` | 重建、修复、任务管理 |

> **允许例外**：为兼容旧版前端，可保留旧路径别名，但旧路径必须被明确标记为"兼容层"，而不是继续视为同级标准入口。

---

## 3. 路径命名规则

### 3.1 资源型接口优先使用复数名词

资源集合优先使用复数路径，对齐标准 CRUD 体验。

```
GET    /api/models          → 获取模型列表
GET    /api/models/{id}     → 获取单个模型
POST   /api/models          → 创建新模型
PUT    /api/models/{id}     → 整体更新模型
PATCH  /api/models/{id}     → 局部更新模型
DELETE /api/models/{id}     → 删除模型
```

**特殊说明**：若某领域天然更像"配置中心"而非"普通资源集合"，可使用单数名词，但一旦选定，不再同时维护单复数两套标准入口。

---

### 3.2 动作型接口使用「资源路径 + 动作后缀」

当接口本质是触发动作（而非增删改查资源）时，使用 action 风格路径：

**✅ 推荐格式**

```
POST /api/memories/reindex       # 重建向量索引
POST /api/memories/retry-sync    # 重试 Trivium 同步
POST /api/tasks/check            # 手动触发任务检查
POST /api/maintenance/run        # 运行维护
POST /api/scheduler/sync         # 同步提醒
```

**命名约定**

| 约定 | 示例 | 说明 |
|------|------|------|
| 优先用 kebab-case 或 plain segment | `retry-sync` / `reindex` | 比 snake_case 更贴近 URL 风格 |
| 动作名简洁，语义可读 | `rebuild`、`cleanup`、`check` | 避免 `do_xxx`、`runXxx`、`manual_trigger_xxx` |
| 同一领域保持一致风格 | 不要混用下划线和连字符 | 统一选一种后就不再切换 |

---

### 3.3 禁止单复数并存作为标准入口

以下这些"历史遗留双轨并存"的情况，应明确收敛：

| ❌ 当前问题 | ✅ 收敛目标 |
|------------|------------|
| `/api/config` 和 `/api/configs` 同时存在 | 选 `/api/configs` 作为标准，旧路径降级为兼容别名 |
| `/api/memory` 和 `/api/memories` 同时存在 | `memories` 为资源入口，`maintenance/memory` 为运维入口 |

---

### 3.4 路径层级保持 2-4 层，避免过深

**✅ 推荐**

```
/api/models
/api/models/{id}
/api/models/{id}/test
/api/memories/reindex
```

**❌ 不推荐**

```
/api/system/configs/global/default/list/all
/api/memory/trivium/sync/tasks/retry/manual
```

> 路径过深通常是领域划分不清的信号。如果发现路径越来越深，先整理领域边界，而不是继续往深处加层级。

---

## 4. HTTP 方法规则

### 4.1 标准 CRUD 遵守 HTTP 语义

| 方法 | 语义 | 适用场景 |
|------|------|----------|
| `GET` | 读取，无副作用 | 查询资源、获取状态、列表 |
| `POST` | 创建 / 触发一次性动作 | 新建资源、发起后台任务 |
| `PUT` | 整体替换更新 | 更新整条记录 |
| `PATCH` | 局部更新 | 修改单字段或部分字段 |
| `DELETE` | 删除 | 删除资源 |

### 4.2 动作型接口允许使用 `POST`

当接口是在触发行为、重建、扫描、重试时，允许优先使用 `POST`，即使不是在"创建资源"：

```python
@router.post("/reindex")  # 触发重建，用 POST 符合规范
async def reindex(): ...
```

### 4.3 禁止用 `GET` 承载有副作用的动作

会引发写入、重建、删除、扫描、重试的接口，**不应**使用 `GET`：

```python
# ❌ 错误示例
@router.get("/run-cleanup")   # GET 不应有副作用

# ✅ 正确示例
@router.post("/cleanup")
```

---

## 5. 请求体建模规则

### 5.1 复杂请求必须使用 Pydantic 模型

以下情况**必须**用 `BaseModel`：

- 字段多于一个
- 存在嵌套结构
- 存在可选参数组合
- 后续可能扩展字段
- 前端需要稳定 schema

**✅ 推荐写法**

```python
class UpdateConfigRequest(BaseModel):
    """批量更新配置请求"""
    configs: Dict[str, str]

class SyncRemindersRequest(BaseModel):
    """同步提醒请求"""
    reminders: List[ReminderItem]

@router.post("/sync", response_model=StandardResponse)
async def sync_reminders(payload: SyncRemindersRequest): ...
```

**❌ 禁止写法**

```python
# ❌ 直接接收无约束字典
@router.post("/sync")
async def sync_reminders(payload: Dict[str, Any] = Body(...)): ...
```

### 5.2 简单开关型参数可以保留轻量写法

仅在字段极少、语义稳定、未来扩展概率低时，允许以下替代方案：

```python
# 方案 A：查询参数（适合读取接口的过滤条件）
@router.get("/list")
async def list_tasks(agent_id: Optional[str] = None): ...

# 方案 B：路径参数（适合定位单个资源）
@router.delete("/{task_id}")
async def delete_task(task_id: int): ...

# 方案 C：已通过 ToggleRequest 统一的开关接口
class ToggleRequest(BaseModel):
    enabled: bool
```

### 5.3 同一领域的同类接口保持一致的建模方式

同一 router 里，同类接口的请求体风格必须统一，不允许出现：

```python
# ❌ 同一领域内混用风格
@router.post("/a")
async def action_a(payload: Dict[str, Any] = Body(...)): ...   # 字典风格

@router.post("/b")
async def action_b(payload: ActionBRequest): ...               # 模型风格

@router.post("/c")
async def action_c(enabled: bool = Body(..., embed=True)): ... # 裸参数风格
```

---

## 6. 响应体规则

### 6.1 响应体按接口类型分三类治理

#### 第一类：CRUD 资源接口

**规则**：可以直接返回资源对象或列表，但必须满足：

1. 有清晰的 `response_model`
2. 字段边界稳定，不混入临时提示字段

```python
@router.get("", response_model=List[Memory])
async def list_memories(...): ...

@router.get("/{memory_id}", response_model=Memory)
async def get_memory(memory_id: int, ...): ...
```

---

#### 第二类：Action 动作接口

**规则**：统一返回 envelope 结构，使用 `StandardResponse`：

```python
class StandardResponse(BaseModel):
    """通用的操作执行响应"""
    status: str = "success"
    message: str = "操作成功"
    data: Optional[Dict[str, Any]] = None
```

**使用方式**

```python
@router.post("/reindex", response_model=StandardResponse)
async def reindex():
    # ... 业务逻辑
    return StandardResponse(
        status="success",
        message="重建索引任务已在后台启动",
        data={"task_id": task_id}
    )
```

**最低要求**：要有 `status`，可以有 `message`，额外数据统一放 `data`。

---

#### 第三类：Summary / Stats 汇总接口

**规则**：可以直接返回摘要对象，但必须满足：

1. 字段命名稳定
2. 语义明确
3. 有 `response_model` 或等价 schema 约束

```python
class SystemStatsResponse(BaseModel):
    total_memories: int
    total_logs: int
    total_tasks: int

@router.get("/stats/overview", response_model=SystemStatsResponse)
async def get_stats(...): ...
```

---

### 6.2 `response_model` 是默认要求，不是可选加分项

主应用所有新增接口，**默认必须声明 `response_model`**，除非确实无法稳定描述（例如完全动态结构）。

**价值**：
- OpenAPI 文档自动生成完整
- 前端类型更容易生成
- 代码审查时响应边界一目了然

---

### 6.3 禁止新增裸字符串 / 裸值返回

**❌ 禁止**

```python
return "pong"           # ❌
return True             # ❌
return 42               # ❌
return None             # ❌（除非有意返回 204 No Content）
```

**✅ 即使是最简单的状态接口，也应返回结构化对象**

```python
return {"status": "ok"}                      # 最低标准
return StandardResponse(status="success")    # 规范标准
```

---

## 7. 错误处理规则

### 7.1 错误优先使用 HTTP 状态码 + 结构化错误体

**标准状态码映射**

| 场景 | HTTP 状态码 |
|------|------------|
| 请求参数非法 | `400 Bad Request` |
| 未认证 | `401 Unauthorized` |
| 未授权 / 权限不足 | `403 Forbidden` |
| 资源不存在 | `404 Not Found` |
| 状态冲突 | `409 Conflict` |
| 服务端内部错误 | `500 Internal Server Error` |

**推荐写法**

```python
from fastapi import HTTPException

# 基础用法
raise HTTPException(status_code=404, detail="未找到该记忆")

# 带上结构化 detail（兼容全局异常处理器）
raise HTTPException(
    status_code=400,
    detail={"message": "请求参数非法", "detail": "agent_id 不能为空"}
)
```

### 7.2 全局异常处理器统一兜底

`main.py` 已注册全局异常处理器，所有未捕获的异常都会被统一转换为以下格式，前端可稳定读取 `error.message` 和 `error.detail`：

```json
{
  "error": {
    "message": "操作失败",
    "detail": "具体的错误描述"
  }
}
```

**各 router 的职责边界**：

- 已知业务失败 → 自行 `raise HTTPException`（带 `status` 和 `detail`）
- 未知异常 → 交由全局异常处理器兜底，**不要**在每个接口里重复 try/except 500

### 7.3 禁止 `200 + {"error": ...}` 风格

**❌ 禁止**

```python
# 这种写法让前端无法通过 res.ok 判断失败，是反模式
return {"error": "something went wrong"}   # ❌
return {"success": False, "message": "..."} # ❌（不统一）
```

**✅ 正确做法**：失败就抛异常，让状态码说话。

### 7.4 过渡期前端错误兼容策略

过渡期内，前端应同时兼容以下字段（按优先级顺序读取）：

1. `detail`（FastAPI 标准字段）
2. `error.message`（全局异常处理器格式）
3. `message`（旧式接口兼容）

---

## 8. 领域边界规则

### 8.1 资源域与运维域分层

同一领域内，资源接口和运维接口必须分层，不得长期混在一起：

| 层级 | 路径前缀 | 职责 |
|------|---------|------|
| **资源层** | `/api/memories` | 列表、详情、查询、更新、删除 |
| **运维层** | `/api/maintenance/memory` | 重建索引、扫描、补偿、清理、同步重试 |

**说明**：如果为了兼容暂时不能拆路径，也应在 router 内部先完成语义分组注释，不再继续随意扩张。

---

### 8.2 配置域优先按职责分类，而不是堆成泛入口

配置接口应分清以下几类，避免什么都往一个"万能 config 接口"里塞：

| 配置类型 | 归属 router | 路径示例 |
|---------|------------|---------|
| 全局系统配置 | `config_router` | `/api/configs` |
| 模型配置（LLM/Embedding） | `model_router` | `/api/models` |
| MCP 配置 | `mcp_config_router` | `/api/mcp` |
| 语音配置 | `voice_router` | `/api/voice/configs` |
| 用户偏好/模式开关 | `config_router` 或专项 | `/api/configs/preferences` |

---

### 8.3 已明确边界的领域保持独立 router

以下领域已有较清晰边界，继续维持独立 router，不要随意合并或回归到大杂烩路由：

- `chat_router.py` → `/api/chat`
- `task_control_router.py` → `/api/task`
- `connection_router.py` → `/api/connection`
- `asset_router.py` → `/api/assets`
- `agent_router.py` → `/api/agents`
- `sync_router.py` → `/api/sync`
- `scheduler_router.py` → `/api/scheduler`

---

### 8.4 例外项明确声明

以下路由**不受本规范约束**，属于本轮改造范围的例外项：

| 例外项 | 位置 | 说明 |
|--------|------|------|
| 外部插件路由 | `mods/_external_plugins/router.py` | 插件内聚，不统一迁移 |
| Social 插件路由 | `nit_core/plugins/social_adapter/social_router.py` | 插件内聚 |
| MOD 自维护接口 | 各 MOD 目录 | 按插件自治原则 |

> 若后续需要将插件路由纳入统一治理，应单独立项评估，不在本规范范围内。

---

## 9. WebSocket 规则

### 9.1 主应用 WebSocket 视为路由体系的一部分

主应用的 WebSocket 入口不应长期散落在 `main.py` 中，应抽到独立 router 文件中统一管理：

**目标结构**

```python
# backend/routers/ws_router.py
router = APIRouter(tags=["websocket"])

@router.websocket("/ws/browser")
async def browser_ws(websocket: WebSocket): ...

@router.websocket("/ws/gateway")
async def gateway_ws(websocket: WebSocket): ...
```

```python
# main.py
app.include_router(ws_router)   # 与 HTTP router 同等方式挂载
```

**注意**：WebSocket 路径保持原有 `/ws/browser` 和 `/ws/gateway` 不变，只是迁移到独立文件，不破坏任何现有连接。

### 9.2 插件内聚型 WebSocket 暂不纳入本规范

外部插件、MOD、插件内部自带 WebSocket，当前只做边界声明，继续保持各自独立。

---

## 10. 标签与命名规则

### 10.1 Tags 与业务域稳定对应

一个 router 的 `tags` 应尽量与其业务域一致，避免同一领域多个近义 tag 并存：

**当前推荐 Tags 映射**

| router 文件 | 推荐 tag |
|------------|---------|
| `agent_router.py` | `agents` |
| `memory_router.py` | `memory` |
| `maintenance_router.py` | `maintenance` |
| `system_router.py` | `system` |
| `config_router.py` | `configs` |
| `model_router.py` | `models` |
| `mcp_config_router.py` | `mcp` |
| `voice_router.py` | `voice` |
| `chat_router.py` | `chat` |
| `scheduler_router.py` | `scheduler` |
| `asset_router.py` | `assets` |
| `ws_router.py` | `websocket` |

### 10.2 路径段命名保持 plain segment 或 kebab-case

主应用路径段应采用统一风格，**不继续混用**：

| 风格 | 示例 | 建议 |
|------|------|------|
| plain segment（推荐） | `reindex`、`rebuild`、`check` | 短动词，首选 |
| kebab-case（可用） | `retry-sync`、`dry-run` | 多词组合时使用 |
| snake_case（逐步淘汰） | `retry_sync` | 历史兼容，不再新增 |
| camelCase（禁止） | `retrySync` | URL 中禁用 |

---

## 11. 前端兼容规则

### 11.1 Backend 变更必须同步评估前端影响

凡涉及以下变更，都必须同步检查前端调用点：

- 路径改名
- 返回体结构变化
- 错误字段变化
- 请求体字段变化

**重点关注的前端文件**

| 优先级 | 文件 |
|--------|------|
| 高 | `src/composables/dashboard/useDashboard.ts` |
| 高 | `src/composables/dashboard/useTasks.ts` |
| 高 | `src/composables/dashboard/useDashboardData.ts` |
| 高 | `src/composables/dashboard/useMemories.ts` |
| 高 | `src/composables/dashboard/useModelConfig.ts` |
| 中 | `src/views/MainWindow.vue` |
| 中 | `src/api/assets.ts` |
| 低 | 其他直接拼接 `API_BASE` 或写死路径的文件 |

---

### 11.2 路径收敛优先采用"兼容迁移"，而不是"直接切断"

当历史路径需要收敛到标准入口时，应遵守以下顺序：

```
1. 先建立标准路径（新入口）
2. 保留旧路径别名（兼容层）一段时间
3. 前端逐步迁移到新路径
4. 确认所有调用方完成切换后，删除兼容层
```

不允许"直接删除旧路径、要求前端立刻同步"的强切方式。

---

### 11.3 前端应逐步建立统一请求封装

随着 backend 统一化推进，前端应同步收敛以下能力：

| 能力 | 目标 |
|------|------|
| base URL | 统一从 `@/config` 导入 `API_BASE`，禁止页面内硬编码 `http://localhost:9120` |
| 错误解析 | 统一封装：优先读 `detail` → `error.message` → `message` |
| 请求封装 | 统一使用 `fetchWithTimeout` 并结合 `API_BASE` |
| 超时处理 | 所有请求使用统一超时设置 |
| API 常量化 | 关键 API 路径抽象为常量或 typed client，降低 backend 改路径的冲击面 |

---

## 12. 新增接口准入清单

每次新增主应用 API 接口前，必须能够清晰回答以下问题：

```markdown
## 新接口准入检查

**接口信息**
- 名称：
- 路径：
- 方法：GET / POST / PUT / PATCH / DELETE

**准入检查项**

- [ ] 属于哪个业务域？
- [ ] 应放在哪个 router 文件？
- [ ] 是 CRUD 资源接口 / Action 动作接口 / Summary 汇总接口？
- [ ] 路径是否符合当前命名规范（前缀、风格、层级深度）？
- [ ] 请求体是否有 Pydantic 模型（字段多于 1 个时必须）？
- [ ] 是否有明确的 `response_model`？
- [ ] 错误处理是否使用 `HTTPException`，而不是返回 `{"error": ...}`？
- [ ] 是否会影响前端已有调用？（如有，是否已同步评估）
- [ ] 有无误将插件 / 外部路由一起卷入本次变更？
```

> 如果其中多个问题回答不清，通常说明接口设计还不够稳定。建议先梳理清楚再动手。

---

## 13. 接口分类参考：REST / Action / RPC

### 13.1 三类接口对比

| 类型 | 特征 | 路径风格 | HTTP 方法 | 返回体 |
|------|------|---------|----------|--------|
| **REST（资源型）** | 增删改查具体资源 | `/api/resources/{id}` | GET/POST/PUT/PATCH/DELETE | 直接返回资源对象或列表 |
| **Action（动作型）** | 触发行为、重建、重试、维护 | `/api/domain/action-name` | POST（为主） | `StandardResponse` envelope |
| **RPC / Command** | 通用命令派发（如 IPC） | `/api/ipc/{command}` | POST | 视命令结果而定 |

### 13.2 典型示例对照

**REST 接口示例**

```python
# ✅ 资源 CRUD——直接返回模型，带 response_model
@router.get("", response_model=List[MCPConfig])
async def get_mcps(session: AsyncSession = Depends(get_session)): ...

@router.post("", response_model=MCPConfig)
async def create_mcp(payload: CreateMCPRequest, ...): ...

@router.delete("/{mcp_id}", response_model=StandardResponse)
async def delete_mcp(mcp_id: int, ...): ...
```

**Action 接口示例**

```python
# ✅ 动作型——触发任务，返回 StandardResponse
@router.post("/reindex", response_model=StandardResponse)
async def trigger_reindex(session: AsyncSession = Depends(get_session)):
    # 后台启动任务
    return StandardResponse(status="success", message="索引重建已在后台启动")

@router.post("/cleanup", response_model=StandardResponse)
async def run_cleanup():
    result = await maintenance_service.cleanup()
    return StandardResponse(status="success", data={"deleted": result.count})
```

**RPC / Command 接口示例**

```python
# ✅ IPC 命令派发——结构更自由，但仍应有稳定模式
@router.post("/{command}")
async def dispatch_ipc(command: str, payload: Dict[str, Any] = Body(default={})):
    result = await ipc_handler.handle(command, payload)
    return result
```

---

## 14. 当前领域路由速查表

> 下表反映 P0/P1 标准化完成后的最终状态，各路径示例以实际 router prefix 为准。

| 业务域 | Router 文件 | Prefix | 典型接口 |
|--------|------------|--------|---------|
| Agent 管理 | `agent_router.py` | `/api/agents` | `GET /api/agents`, `POST /api/agents/active` |
| 资产管理 | `asset_router.py` | `/api/assets` | `GET /api/assets/` |
| 聊天 | `chat_router.py` | `/api/chat` | `POST /api/chat/stream` |
| 全局配置 | `config_router.py` | `/api/configs` | `GET /api/configs`, `POST /api/configs` |
| 连接信息 | `connection_router.py` | `/api/connection` | `GET /api/connection/info` |
| 群聊 | `group_chat_router.py` | `/api/groupchat` | ... |
| IDE 集成 | `ide_router.py` | `/api/ide` | ... |
| IPC 派发 | `ipc_router.py` | `/api/ipc` | `POST /api/ipc/{command}` |
| 运维操作 | `maintenance_router.py` | `/api/maintenance` | `POST /api/maintenance/run`, `GET /api/maintenance/tasks` |
| MCP 配置 | `mcp_config_router.py` | `/api/mcp` | `GET /api/mcp`, `PUT /api/mcp/{id}` |
| 记忆资源 | `memory_router.py` | `/api/memories` | `GET /api/memories/list`, `POST /api/memories/reindex` |
| 模型配置 | `model_router.py` | `/api/models` | `GET /api/models` |
| NIT 核心 | `nit_router.py` | `/api/nit` | ... |
| 宠物状态 | `pet_router.py` | `/api/pet` | `GET /api/pet/state` |
| 任务调度 | `scheduler_router.py` | `/api/scheduler` | `POST /api/scheduler/sync` |
| 堡垒系统 | `stronghold_router.py` | `/api/stronghold` | ... |
| 数据同步 | `sync_router.py` | `/api/sync` | `GET /api/sync/status`, `POST /api/sync/config` |
| 系统管理 | `system_router.py` | `/api/system` | `GET /api/system/stats/overview`, `POST /api/system/reset` |
| 任务控制 | `task_control_router.py` | `/api/task` | `GET /api/task/{session_id}/status` |
| 语音系统 | `voice_router.py` | `/api/voice` | `GET /api/voice/configs`, `POST /api/voice/tts` |
| WebSocket | `ws_router.py` | — | `WS /ws/browser`, `WS /ws/gateway` |

---

## 15. 反模式速查（禁止做的事）

一眼看出代码是否违反规范的快速对照表：

### ❌ 路由组织反模式

```python
# ❌ Router 无 prefix，在装饰器里写完整路径
router = APIRouter(tags=["memory"])
@router.get("/api/memories/list")
async def list_memories(): ...

# ❌ 在 main.py 里写业务接口
@app.get("/api/special-endpoint")
async def special(): ...
```

### ❌ 路径命名反模式

```python
# ❌ 同域单复数并存
@router.get("/api/memory")   # 与 /api/memories 并行
@router.get("/api/config")   # 与 /api/configs 并行

# ❌ 路径层级过深
@router.get("/api/memory/trivium/sync/tasks/retry/manual")

# ❌ 动作名称不统一（下划线与连字符混用）
@router.post("/retry_sync")  # ❌ 用了下划线
@router.post("/run-cleanup") # ✅ 用了连字符
```

### ❌ 请求体反模式

```python
# ❌ 多字段请求用裸字典
@router.post("/sync")
async def sync(payload: Dict[str, Any] = Body(...)): ...

# ❌ 同领域内建模风格不统一
@router.post("/action-a")
async def action_a(payload: ActionARequest): ...   # 模型
@router.post("/action-b")
async def action_b(data: Dict[str, Any]): ...      # 字典
```

### ❌ 响应体反模式

```python
# ❌ 返回裸字符串
return "pong"

# ❌ 200 + error 风格
return {"error": "something failed"}

# ❌ 没有 response_model
@router.get("")
async def list_items():   # ❌ 缺少 response_model=List[Item]
    ...
```

### ❌ 错误处理反模式

```python
# ❌ 捕获所有异常后返回 200 + error
try:
    ...
except Exception as e:
    return {"error": str(e)}  # ❌

# ❌ 用 GET 触发有副作用的动作
@router.get("/run-cleanup")   # ❌ GET 不应有副作用
async def run_cleanup(): ...
```

---

> **一句话总结**：  
> 主应用 backend API 的目标，不是让所有接口长得完全一样，而是让**同类接口遵守同类规则**，前后端都能稳定预期，形成一套可维护、可扩展、可迁移的 API 体系。

---

*本文档由 Carola 综合 `backend_api_standardization_analysis.md`、`backend_api_standardization_rules_baseline.md`、`backend_api_standardization_checklist.md` 整理生成，适用于 PeroCore Backend API 规范体系。*
