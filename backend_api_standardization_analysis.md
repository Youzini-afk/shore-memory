# Backend API 统一化 / 规范化改造分析

## 1. 文档目的

本文基于当前 `PeroCore-electron/backend` 实际代码结构，对 API 路由的收纳情况、接口风格一致性、后续统一化改造点，以及前端同步影响进行集中分析。

本文的改造范围做如下约束：**外部插件、MOD、插件内聚型路由先不动**，本轮主要聚焦主应用 backend 内部可统一、可规范的核心路由与 WebSocket 入口。

目标不是立即改代码，而是先把“为了统一化、规范化，究竟要改哪些地方”一次性梳理清楚，供后续分阶段实施。

---

## 2. 当前总体结论

### 2.1 路由收纳情况

当前 `backend` 的 HTTP API **大部分已经模块化并放入 `backend/routers`**，但**并没有做到全部收纳**。

当前实际情况如下：

1. 主业务 API 大多位于 `backend/routers`
2. 仍有插件相关路由位于非 `routers` 目录
3. 仍有 WebSocket 入口直接定义在 `main.py`

因此，从“结构收纳”角度看，项目当前处于：

- **主业务路由基本收敛**
- **插件路由和 WebSocket 入口尚未完全统一归档**

不过如果按照本文当前约束来看：

- **外部插件、MOD、插件内聚型路由不纳入这一轮改造范围**
- **真正需要改造的重点，是主应用核心 router 的统一化，以及 `main.py` 中 WebSocket 入口的收敛方式**

### 2.2 接口规范一致性

当前 API 规范**不是完全统一**，主要问题集中在：

1. 路由前缀组织方式不统一
2. 路径命名风格不统一
3. 返回体 envelope 不统一
4. 错误处理风格不统一
5. 请求参数建模方式不统一
6. `response_model` 使用不统一
7. 部分领域边界存在重叠或历史叠加

整体判断：

> 当前 backend API 已经具备“可维护的模块化雏形”，但距离“统一、规范、可治理”的 API 体系仍有明显差距。

---

## 3. 当前路由分布现状

### 3.1 已放入 `backend/routers` 的主路由模块

当前主应用已挂载的核心 router 包括：

- `agent_router.py`
- `asset_router.py`
- `chat_router.py`
- `config_router.py`
- `connection_router.py`
- `group_chat_router.py`
- `ide_router.py`
- `ipc_router.py`
- `maintenance_router.py`
- `mcp_config_router.py`
- `memory_router.py`
- `model_router.py`
- `nit_router.py`
- `pet_router.py`
- `scheduler_router.py`
- `stronghold_router.py`
- `sync_router.py`
- `system_router.py`
- `task_control_router.py`
- `voice_router.py`

此外，`memory_router.py` 中还导出了：

- `history_router`
- `legacy_memories_router`

### 3.2 未收纳进 `backend/routers` 的路由

当前至少有以下两类路由不在 `backend/routers` 下：

#### 3.2.1 social 插件路由

位置：

- `backend/nit_core/plugins/social_adapter/social_router.py`

特点：

- 作为插件内聚的一部分存在
- 路由前缀为 `/api/social`
- 包含 HTTP 与 WebSocket 能力

#### 3.2.2 外部插件管理路由

位置：

- `backend/mods/_external_plugins/router.py`

特点：

- 是插件注册/反注册/查询/通知相关入口
- 路由前缀为 `/api/plugins`

这一部分在本文中仍然需要保留分析结论，因为它们解释了当前整体路由结构为什么不是“全部在 `backend/routers` 里”。

但在后续改造范围上，应明确视为：

- **例外项**
- **暂不调整项**
- **不作为本轮 API 统一化的实施对象**

### 3.3 直接写在 `main.py` 的 WebSocket 入口

当前至少还有两个 WebSocket 入口直接定义在 `main.py`：

- `/ws/browser`
- `/ws/gateway`

这说明：

- HTTP 路由大多已经 router 化
- WebSocket 入口尚未完成同等程度的收敛

---

## 4. 当前 API 规范不统一的主要表现

### 4.1 路由前缀组织方式不统一

当前项目存在两种并行风格：

#### 风格 A：router 自带 prefix

例如：

- `/api/config`
- `/api/models`
- `/api/mcp`
- `/api/agents`
- `/api/ide`
- `/api/groupchat`

这种写法的特点是：

- `APIRouter(prefix="...")`
- endpoint 使用相对路径
- router 级边界清晰

#### 风格 B：router 无 prefix，endpoint 自己写完整路径

例如：

- `maintenance_router.py`
- `system_router.py`
- `chat_router.py`
- `pet_router.py`
- `voice_router.py`

这种写法的特点是：

- `APIRouter(tags=[...])`
- 每个装饰器都直接写 `/api/...`
- 路由命名空间不在 router 层统一管理

#### 结论

这会导致：

1. 不同 router 的组织方式不一致
2. 路径命名空间难以统一重构
3. 新增接口时容易继续延续历史混搭

---

### 4.2 路径命名风格不统一

#### 4.2.1 `config` 与 `configs` 并存

当前存在两套路由：

- `/api/config/*`
- `/api/configs*`

这会造成：

- 语义重复
- 前端接入时记忆成本增高
- 后续文档和测试难统一

#### 4.2.2 `memory` 与 `memories` 交叉使用

当前存在：

- `/api/memories/*`
- `/api/memory/*`

其中：

- `/api/memories/*` 偏资源和维护混合
- `/api/memory/*` 偏重建、补偿、Trivium 运维

这并非完全错误，但当前没有清晰的统一规则说明：

- 单数表示 subsystem action
- 复数表示 resource collection

由于没有显式规则，实际表现更像历史演进结果而不是有意设计。

#### 4.2.3 一部分使用 REST 风格，一部分使用动作风格

例如：

- `/models/{id}`、`/mcp/{id}` 较接近 CRUD / REST
- `/tasks/check`、`/maintenance/run`、`/memory/retry_trivium_sync` 更偏 action endpoint
- `/ipc/{command}` 则更像 RPC 风格

这说明项目中同时存在：

- REST 风格
- action 风格
- command/RPC 风格

但当前缺少统一的边界规则。

---

### 4.3 返回体格式不统一

当前接口返回格式至少有以下几类：

#### 类型 A：统一状态对象

例如：

```json
{"status": "success"}
```

或：

```json
{"status": "success", "message": "..."}
```

#### 类型 B：直接返回模型对象

例如：

- 直接返回 `Memory`
- 直接返回 `VoiceConfig`
- 直接返回 `MCPConfig`

#### 类型 C：直接返回列表

例如：

- 模型列表
- 任务列表
- 群聊历史

#### 类型 D：直接返回自由结构字典

例如：

- 系统状态
- overview 统计
- connection info
- trivium sync summary

#### 类型 E：返回裸字符串或裸值

例如：

- `"pong"`
- `"0.6.3-docker"`
- `None`

#### 结论

当前系统没有统一的 response envelope 约束，例如：

- 是否统一包含 `success`
- 是否统一包含 `code`
- 是否统一包含 `message`
- 数据是否统一放到 `data` 字段

这会直接影响：

- 前端错误处理
- 前端类型收敛
- 自动化测试编写
- API 文档化

---

### 4.4 错误处理风格不统一

当前错误处理至少有以下几类：

1. `raise HTTPException(status_code=..., detail=...)`
2. `except Exception as e: raise HTTPException(500, detail=...)`
3. `return {"error": str(e)}`
4. 某些接口直接返回非结构化错误信息

问题在于：

- 有些失败会体现为 4xx/5xx
- 有些失败仍返回 200，但 body 中有 `error`
- 前端无法使用单一策略处理错误

这也是当前规范化里优先级较高的一项。

---

### 4.5 请求参数建模不统一

当前 POST / PUT 接口的参数风格混用明显：

1. 使用 Pydantic `BaseModel`
2. 直接使用 `Dict[str, Any]`
3. 使用 `Body(..., embed=True)` 的单字段参数
4. 个别地方接受原始列表或松散 payload

这会造成：

- 请求 schema 不稳定
- 自动文档不完整
- 前后端契约难统一
- 后续重构易出现兼容性问题

---

### 4.6 `response_model` 使用不统一

当前一部分 router 已经较规范：

- `agent_router`
- `model_router`
- `mcp_config_router`
- `voice_router`
- `group_chat_router`
- `stronghold_router`

但另一部分历史接口没有统一声明 `response_model`。

后果包括：

- OpenAPI 文档质量不一致
- 响应字段边界不清晰
- 前端类型生成困难

---

### 4.7 领域边界存在重叠

#### 4.7.1 memory 相关能力分散

当前 memory 相关能力横跨：

- `memory_router.py`
- `maintenance_router.py`

其中 `/api/memories/*` 有一部分在维护路由里，另一部分能力在 `memory_router.py`。

这会导致：

- memory 域边界不够清晰
- 后续继续扩展时容易失控
- 前端开发者难判断某类能力该去哪个模块找

#### 4.7.2 配置相关能力分散

配置能力目前至少横跨：

- `config_router.py`
- `system_router.py`

问题不只是文件分散，而是命名和语义也分散。

---

## 5. 需要改造的地方清单

以下按优先级拆分。

### 5.1 P0：必须优先统一的部分

#### P0-1：建立统一的路由组织规则

需要明确并固定一套规则：

1. router 必须使用 `prefix`
2. endpoint 内只写相对路径
3. 同一业务域只允许一个主命名空间入口
4. WebSocket 是否也要 router 化，需要统一规范

建议目标：

- `system_router`、`maintenance_router`、`chat_router`、`pet_router`、`voice_router` 等改成 prefix 风格
- 禁止新代码继续在 decorator 中直接硬编码完整 `/api/...`

#### P0-2：统一配置接口命名

需要决定：

- 保留 `/api/config`
- 还是保留 `/api/configs`

二者必须选一套作为标准。

建议：

- 若按“配置资源集合”理解，倾向统一为 `/api/configs`
- 若按“配置中心”理解，也可统一为 `/api/config`

关键不是选哪套，而是必须收敛为一套。

#### P0-3：统一错误处理策略

必须明确：

1. 业务失败统一使用 HTTP 状态码还是始终 200 + 业务码
2. 服务器异常如何返回
3. 前端应该如何统一解析错误

建议：

- 参数错误：400
- 未授权：401/403
- 资源不存在：404
- 服务端异常：500
- 不再允许以 200 + `{"error": ...}` 充当标准错误出口

#### P0-4：统一返回体策略

需要明确：

- 是否所有接口都使用 envelope
- 哪些接口可以直接返回资源对象
- 哪些 action 接口必须包含 `status/message`

建议采用分层策略，而不是强制所有接口完全同构：

1. **CRUD 资源接口**
   - 允许直接返回资源对象 / 列表
   - 必须有清晰 `response_model`

2. **动作型接口**
   - 统一返回：
     ```json
     {
       "status": "success",
       "message": "...",
       "data": {...}
     }
     ```
   - 至少保证结构一致

3. **统计 / 摘要接口**
   - 可直接返回 summary 对象
   - 但字段命名和错误语义必须稳定

#### P0-5：统一请求体建模方式

建议规则：

1. 简单开关型参数可保留 `Body(..., embed=True)`
2. 复杂 POST/PUT 请求统一用 Pydantic 模型
3. 禁止新增松散 `Dict[str, Any]` 风格接口，除非有明确的动态 schema 需求

---

### 5.2 P1：应当尽快推进的部分

#### P1-1：整理 memory 域路由边界

需要梳理：

- `memory_router.py` 负责什么
- `maintenance_router.py` 负责什么
- `/api/memories/*` 与 `/api/memory/*` 的命名规则是什么

建议方向：

- `memories`：资源视角（列表、详情、删除、图谱、标签）
- `memory-maintenance` 或 `maintenance/memory`：维护操作（dream、scan、cleanup、rebuild、sync retry）
- 避免继续把不同语义混在同一路径层级里

#### P1-2：整理配置相关边界

建议明确分层：

- 全局系统配置
- 模型配置
- MCP 配置
- 语音配置
- 用户偏好配置

避免 `config_router` 和 `system_router` 都继续承载“泛配置入口”。

#### P1-3：提升 `response_model` 覆盖率

建议对以下接口补齐响应 schema：

- 系统统计类接口
- maintenance 类接口
- memory 摘要/维护类接口
- Trivium sync observability 接口

这会显著提升：

- OpenAPI 可读性
- 前端类型安全
- 文档自动生成能力

#### P1-4：收纳 WebSocket 入口

建议把：

- `/ws/browser`
- `/ws/gateway`

抽到独立 router 文件中，例如：

- `routers/ws_router.py`
- 或按域拆分为 browser/gateway router

好处：

- `main.py` 更纯粹
- API / WebSocket 入口更易盘点
- 路由治理方式统一

#### P1-5：明确插件路由的归档策略

外部插件、MOD、插件内聚型路由在本轮**不做结构改造**。

因此这里更准确的目标不是“现在就把它们收进统一目录”，而是先在规范层明确：

1. 它们属于例外项
2. 它们可以继续保留在各自目录中，强调插件内聚
3. 主应用 API 统一化时，不以移动这些路由文件为前置条件

换句话说，这一项当前应当作为**边界声明与例外规则**，而不是实施性改造任务。

如果后续要做更大范围的全局路由治理，再单独评估是否需要把插件路由纳入统一目录。

---

### 5.3 P2：中长期优化项

#### P2-1：区分 REST / action / RPC 三类接口

建议明确：

1. **REST**：资源 CRUD
2. **action**：触发行为、维护任务、重建、重试
3. **RPC/command**：像 IPC 这种通用命令派发

然后对三类分别制定规范。

#### P2-2：统一标签、前缀、命名文案

例如：

- tags 是否使用单数还是复数
- 路由命名是否统一 snake_case / kebab_case / plain segment
- `memory` / `memories` / `maintenance` / `tasks` 这些路径词是否有固定规则

#### P2-3：形成 API 治理文档与新增接口准入规则

建议后续新增接口时必须经过以下检查：

- 属于哪个业务域
- 应放在哪个 router
- 请求体是否要建模
- 响应体是否需要 schema
- 错误码是否符合统一策略
- 是否会影响前端已有调用

---

## 6. 前端方面是否需要同步更改

结论是：**需要，而且影响不小。**

原因是前端当前已经直接依赖了很多现有路径和返回格式。

### 6.1 当前前端对 backend API 的依赖特点

当前前端存在以下现状：

1. 大量页面/组合式函数直接写死具体路径
2. 有些地方通过统一 `API_BASE` 拼接
3. 有些地方自行拼装 base URL
4. 有些接口调用默认依赖旧的返回体结构
5. 测试中也写死了部分请求路径

这意味着 backend 一旦做统一化，前端绝不能视作“无影响”。

### 6.2 已发现的前端同步风险点

#### 6.2.1 `config` / `configs` 路径改名会直接影响前端

前端当前明确在调用：

- `/configs`
- `/models`
- `/memory/reindex`
- `/system/reset`
- `/mcp`
- `/memories/*`
- `/pet/state`
- `/connection/info`
- `/open-path`

其中，`useModelConfig.ts` 已经大量依赖 `/configs`。

如果 backend 把 `/api/configs` 收敛到 `/api/config`，前端必须同步调整。

#### 6.2.2 `MainWindow.vue` 与部分页面存在自行拼装 API_BASE 的情况

例如：

- `MainWindow.vue` 自己拼 `http://<host>:9120`
- `FileExplorer.vue` 自己拼 `.../api/ide`
- `Pet3DView.vue` 局部代码里出现硬编码 `http://localhost:9120/api`

这说明前端自身也存在“调用入口不统一”的问题。

如果 backend 做统一化，前端也应同步做一轮收敛：

- 尽量统一复用一个 API base 和请求封装
- 减少页面级硬编码

#### 6.2.3 返回体统一后，前端解析逻辑要跟着改

如果 backend 后续统一 response envelope，例如把很多动作接口都改成：

```json
{
  "status": "success",
  "message": "...",
  "data": {...}
}
```

那么前端当前这些写法会受到影响：

- 直接把 `res.json()` 当成列表/对象
- 直接读根字段而不是 `data`
- 依赖 `res.ok` 之外的非统一消息字段

#### 6.2.4 错误处理统一后，前端也要调整错误解析方式

前端当前很多地方是：

- 先判断 `res.ok`
- 再读取 `detail` / `message` / 默认文案

但如果 backend 目前有些接口还是 200 + `error`，前端就可能没有统一兜住。

后端一旦统一错误策略，前端也应该同步建立统一错误解析器。

#### 6.2.5 自动化测试也会跟着受影响

前端测试中已有对具体 URL 的断言。

如果路径规范调整：

- 测试快照
- `fetch` 调用断言
- mock handler

都需要同步更新。

### 6.3 前端建议同步改造项

#### FE-1：统一前端 API 访问基址

建议：

- Dashboard、MainWindow、Pet3DView、IDE 等场景尽量复用统一 API base 方案
- 禁止继续新增页面内写死 `http://localhost:9120/api`

#### FE-2：统一前端请求封装

建议把前端网络层至少收敛为：

1. 统一 base URL
2. 统一超时处理
3. 统一错误提示
4. 统一 JSON 解析
5. 统一 envelope 拆包逻辑

#### FE-3：统一前端错误解析

建议前端统一封装：

- 优先读 `detail`
- 兼容 `message`
- 兼容旧 `error`
- 在过渡期支持新旧接口并存

#### FE-4：前端 API 常量化 / typed client 化

当前很多路径仍直接在业务文件里拼接字符串。

后续若要降低 backend 改造对前端的冲击，建议逐步把关键 API 抽象成：

- API 常量
- 或 typed client 方法

这样当 backend 路径调整时，前端修改面会明显缩小。

#### FE-5：针对 Dashboard 做优先同步

当前 Dashboard 是后台管理能力最集中的前端入口。

如果后端 API 规范化分阶段推进，优先需要同步关注：

- `useDashboard.ts`
- `useModelConfig.ts`
- `useMemories.ts`
- `MainWindow.vue`
- `Pet3DView.vue`
- `FileExplorer.vue`

---

## 7. 建议的实施顺序

建议不要一次性大改全部 API，而是分阶段推进。

### 阶段 1：先定规则，不改对外路径

产出统一规则：

1. router prefix 规则
2. 请求体建模规则
3. 错误处理规则
4. `response_model` 规则
5. response envelope 规则
6. 主应用路由与插件路由的边界规则

此阶段尽量不破坏前端，也不触碰外部插件、MOD、插件内聚型路由。

### 阶段 2：做内部结构收敛

包括：

- 把无 prefix router 改成 prefix 风格
- 抽离 WebSocket router
- 梳理 memory / config 域边界
- 但暂时保留原路径兼容
- 改造范围仅限主应用 backend 自身路由，不包含外部插件、MOD、插件内聚型路由

### 阶段 3：建立兼容层并开始路径收敛

例如：

- 保留旧路径一段时间
- 新路径作为标准入口
- 前端逐步迁移到新路径

### 阶段 4：前端统一切换

包括：

- 替换旧 endpoint
- 收敛请求封装
- 更新测试断言
- 移除过渡兼容逻辑

### 阶段 5：删除旧接口与兼容层

当所有前端和调用方完成迁移后：

- 删除旧别名路径
- 删除兼容性分支
- 清理历史接口文档

---

## 8. 最终建议

如果以“统一化、规范化”为目标，我的建议是：

### 必须做的核心改造

1. 统一主应用 router prefix 风格
2. 统一配置接口命名
3. 统一错误处理方式
4. 统一返回结构策略
5. 统一请求体建模方式
6. 整理 memory / maintenance / config 域边界
7. 抽离主应用 WebSocket 入口
8. 明确外部插件、MOD、插件内聚型路由属于例外范围，暂不纳入本轮改造

### 必须同步考虑的前端问题

1. 前端路径依赖会被直接影响
2. 前端请求封装也需要同步规范化
3. 返回体与错误处理统一后，前端解析必须同步升级
4. 前端测试也要同步调整

### 总体判断

> 这次 API 统一化改造不能只看 backend。
>
> 如果只改 backend 而不同时设计前端迁移策略，最终一定会出现：前端大量接口失配、错误提示混乱、测试断裂、维护成本上升。
>
> 正确做法应当是：**先出统一规则，再做 backend 收敛，同时给前端提供兼容迁移窗口，最后整体切换。**
