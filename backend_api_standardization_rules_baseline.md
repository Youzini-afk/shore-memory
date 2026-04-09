# Backend API 统一规则基线

## 1. 文档目的

本文用于定义当前 `PeroCore-electron` 主应用 backend API 的统一规则基线。

它的定位不是问题分析，也不是实施排期，而是回答下面的问题：

1. 以后主应用 backend API 应该按什么规则写
2. 当前已经比较合理、且大多数路由正在遵守的规则有哪些
3. 结合标准 CRUD 体验，哪些地方应当被进一步统一
4. 在不触碰外部插件、MOD、插件内聚型路由的前提下，主应用 API 应如何收敛

本文默认沿用当前范围约束：**外部插件、MOD、插件内聚型路由先不动**。

---

## 2. 适用范围

本规则基线适用于：

- `backend/main.py`
- `backend/routers/*.py` 中的主应用 router
- 主应用自身的 WebSocket 入口
- 主应用 HTTP API 的路径设计、请求体、响应体、错误处理、`response_model`、命名方式

本规则基线暂不直接约束：

- `backend/nit_core/plugins/social_adapter/social_router.py`
- `backend/mods/_external_plugins/router.py`
- 其他插件内聚型路由
- MOD 自行维护的接口体系

---

## 3. 设计原则

统一规则基线遵循以下原则：

1. **优先延续当前主流写法，而不是推翻重来**
2. **优先贴近标准 CRUD 体验，但不强行把所有接口都做成纯 REST**
3. **资源型接口和动作型接口分开治理**
4. **先保证可维护、可预测，再追求形式绝对统一**
5. **前端可迁移性必须纳入规则设计**

一句话总结：

> 主应用 backend API 的目标，不是“看起来完全一样”，而是“同类接口遵守同类规则，前后端都能稳定预期”。

---

## 4. 路由组织规则

### 4.1 主应用 router 必须使用 `prefix`

这是本基线的首要规则。

#### 规则

1. 主应用 router 必须通过 `APIRouter(prefix="...")` 声明命名空间
2. endpoint 装饰器中只写相对路径
3. 不再新增“router 无 prefix、装饰器里直接写完整 `/api/...`”的写法

#### 推荐写法

```python
router = APIRouter(prefix="/api/models", tags=["models"])

@router.get("")
async def list_models():
    ...

@router.get("/{model_id}")
async def get_model(model_id: str):
    ...
```

#### 不推荐写法

```python
router = APIRouter(tags=["models"])

@router.get("/api/models")
async def list_models():
    ...
```

#### 原因

- router 边界更清晰
- 后续路径收敛更容易
- 同一业务域的接口更容易盘点和迁移

---

### 4.2 `main.py` 只负责挂载，不负责堆积具体路由实现

#### 规则

1. `main.py` 负责 `include_router(...)`
2. HTTP 业务路由原则上不直接写在 `main.py`
3. 主应用 WebSocket 入口也应逐步抽离到独立 router 文件

#### 允许的例外

- 启动生命周期逻辑
- 应用初始化逻辑
- 极少量必须贴近应用对象的装配代码

#### 目标

让 `main.py` 成为“应用装配入口”，而不是“路由实现混合体”。

---

### 4.3 一个业务域原则上只保留一个主命名空间

#### 规则

同一业务域应优先只保留一个主路径入口。

例如：

- 配置域：应在 `/api/config` 或 `/api/configs` 中二选一
- 模型域：统一挂在 `/api/models`
- MCP 域：统一挂在 `/api/mcp`
- agent 域：统一挂在 `/api/agents`

#### 说明

允许为了兼容保留旧路径别名，但旧路径应被明确标记为兼容层，而不是继续视为同级标准入口。

---

## 5. 路径命名规则

### 5.1 资源型接口优先使用复数名词

这是与标准 CRUD 体验对齐的基础规则。

#### 规则

资源集合优先使用复数路径：

- `/api/models`
- `/api/agents`
- `/api/memories`
- `/api/configs` 或 `/api/config`（二选一后固定）

#### 典型 CRUD 风格

- `GET /api/models`：获取列表
- `GET /api/models/{id}`：获取详情
- `POST /api/models`：创建资源
- `PUT /api/models/{id}`：整体更新
- `PATCH /api/models/{id}`：局部更新
- `DELETE /api/models/{id}`：删除资源

#### 说明

如果某一领域天然更像“配置中心”而不是“普通资源集合”，也可以使用单数名词，但一旦选定就要固定，不再同时并存单复数两套标准入口。

---

### 5.2 动作型接口使用“资源路径 + 动作后缀”

项目中存在大量非 CRUD 接口，这很正常，不应强行伪装成 CRUD。

#### 规则

当接口本质是“触发动作”而不是“增删改查资源”时，应使用 action 风格路径。

#### 推荐形式

- `/api/memories/reindex`
- `/api/memories/retry-sync`
- `/api/tasks/check`
- `/api/maintenance/run`
- `/api/chat/stream`

#### 不推荐的情况

- 动作接口混进资源详情路径但语义不清
- 同一领域一部分写 `/run_xxx`，一部分写 `/doXxx`，一部分写 `/retry_xxx`

#### 规则细化

1. 动作名称应尽量使用短语义、可读的路径段
2. 优先使用统一风格，避免 snake_case / camelCase / 混合并存
3. 若项目已有大量 plain segment 写法，可优先统一为 plain segment 或 kebab-case，不建议继续扩散下划线命名

---

### 5.3 同一领域内单数 / 复数不得同时作为标准入口并存

#### 规则

例如 `memory` 与 `memories`，`config` 与 `configs`，不能长期同时作为标准入口存在。

#### 允许情况

- 可以暂时保留兼容别名
- 但必须明确哪一套是标准入口，哪一套是过渡入口

#### 推荐方向

- 资源型领域优先复数
- 中心型、系统型领域可保留单数
- 一旦选定，不再新增第二套并行标准

---

### 5.4 路径层级不宜过深

#### 规则

路径设计以 2 到 4 层为宜，尽量避免出现过深、语义重复的层级。

#### 推荐

- `/api/models`
- `/api/models/{id}`
- `/api/models/{id}/test`
- `/api/memories/reindex`

#### 不推荐

- `/api/system/configs/global/default/list/all`
- `/api/memory/trivium/sync/tasks/retry/manual`

#### 原因

路径越深，越容易暴露领域划分不清的问题。

---

## 6. HTTP 方法规则

### 6.1 标准 CRUD 优先遵守 HTTP 语义

#### 规则

- `GET`：读取
- `POST`：创建或触发一次性动作
- `PUT`：整体替换更新
- `PATCH`：局部更新
- `DELETE`：删除

#### 要求

如果一个接口明显是 CRUD 语义，就尽量不要随意改成动词式路径 + POST 的方式。

例如：

- 获取配置列表，不应写成 `POST /api/configs/query`
- 删除模型，不应写成 `POST /api/models/{id}/delete`

除非存在明确历史兼容或复杂业务原因。

---

### 6.2 动作型接口允许使用 `POST`

#### 规则

当接口是在触发行为、任务、重建、扫描、重试时，允许优先使用 `POST`。

例如：

- `POST /api/memories/reindex`
- `POST /api/memories/retry-sync`
- `POST /api/tasks/check`

#### 原因

这类接口本质上是在发起命令，而不是修改单一资源字段。

---

### 6.3 不使用 GET 承载有副作用的动作

#### 规则

会引发写入、重建、删除、扫描、重试、副作用任务的接口，不应使用 `GET`。

#### 目标

保证接口行为符合直觉，也更利于前端、代理层和测试工具理解其语义。

---

## 7. 请求体建模规则

### 7.1 复杂请求必须优先使用 Pydantic 模型

#### 规则

以下情况优先使用 `BaseModel`：

- 字段多于一个
- 存在嵌套结构
- 存在可选参数组合
- 后续可能扩展字段
- 前端需要稳定 schema

#### 推荐写法

```python
class UpdateConfigRequest(BaseModel):
    key: str
    value: str
    scope: str | None = None
```

#### 不推荐写法

- 直接 `Dict[str, Any]`
- 接收松散对象但没有模型定义

---

### 7.2 简单开关型参数允许保留轻量写法

#### 规则

对非常简单的单参数接口，可以保留轻量方式，例如：

- `Body(..., embed=True)`
- 查询参数
- 路径参数

#### 适用前提

只有在字段极少、语义稳定、未来扩展概率低时才适合。

否则仍建议转成请求模型。

---

### 7.3 同一类接口的请求体风格应保持一致

#### 规则

如果同一领域的多个 action 接口都属于“触发任务 + 带少量参数”，则应统一建模方式。

例如不要出现：

- 一个接口用 `BaseModel`
- 一个接口用 `Dict[str, Any]`
- 一个接口用裸布尔值
- 一个接口再用 query string

除非它们语义本来就明显不同。

---

## 8. 响应体规则

### 8.1 响应体分三类治理：CRUD / action / summary

这是本基线最核心的响应规则。

#### 第一类：CRUD 资源接口

#### 规则

CRUD 接口允许直接返回资源对象或资源列表，但必须满足：

1. 有清晰 `response_model`
2. 字段边界稳定
3. 不混入临时提示字段

#### 示例

- 返回单个 `ModelConfig`
- 返回 `List[Agent]`
- 返回 `Memory` 详情对象

---

#### 第二类：action 动作接口

#### 规则

动作型接口统一返回 envelope 结构。

#### 推荐结构

```json
{
  "status": "success",
  "message": "...",
  "data": {}
}
```

#### 最低要求

1. 要有 `status`
2. 可以有 `message`
3. 结果数据统一放在 `data`

#### 原因

动作接口天然更像“执行结果”，而不是“资源本体”，适合使用统一结果包装。

---

#### 第三类：summary / stats 接口

#### 规则

汇总、统计、状态类接口可以直接返回摘要对象，但应满足：

1. 字段命名稳定
2. 语义明确
3. 有 `response_model` 或等价 schema 约束

#### 示例

- dashboard summary
- connection info
- sync summary
- system status

---

### 8.2 不再新增裸字符串、裸值返回

#### 规则

除非是非常明确的底层健康探针或历史兼容接口，否则不应新增如下返回：

- `"pong"`
- 单独布尔值
- 单独数字
- `None`

#### 推荐

即使是简单状态接口，也尽量返回结构化对象。

例如：

```json
{
  "status": "ok"
}
```

---

### 8.3 `response_model` 应作为默认要求，而不是可选加分项

#### 规则

主应用新接口应默认声明 `response_model`，除非确实无法稳定描述。

#### 尤其适用于

- CRUD 接口
- summary / stats 接口
- 固定结构的 action 返回

#### 价值

- OpenAPI 更完整
- 前端类型更容易生成
- 代码审查时更容易发现响应边界问题

---

## 9. 错误处理规则

### 9.1 标准错误优先使用 HTTP 状态码 + 结构化错误

#### 规则

优先使用 `HTTPException` 或统一异常转换机制表达失败。

#### 推荐映射

- 参数错误：400
- 未认证：401
- 未授权：403
- 资源不存在：404
- 冲突：409
- 服务端异常：500

---

### 9.2 不再把 `200 + {"error": ...}` 作为标准失败出口

#### 规则

除兼容期外，不再新增“HTTP 200，但 body 里带 `error` 字段表示失败”的做法。

#### 原因

- 前端很难统一处理
- 与 HTTP 语义冲突
- 测试断言容易混乱

---

### 9.3 错误结构优先兼容 `detail`，过渡期兼容旧字段

#### 规则

在主应用统一化过程中，错误返回应优先让前端可以稳定读取 `detail`。

#### 过渡要求

如果历史接口暂时无法一次性改完，前端兼容层可同时兼容：

- `detail`
- `message`
- `error`

但 backend 新规则应优先收敛到标准异常语义。

---

## 10. 领域边界规则

### 10.1 资源域和运维域分开

#### 规则

同一领域内，资源接口和运维接口应尽量分层，不要长期混在一起。

#### 推荐理解

- `memories`：资源集合、详情、查询、更新、删除
- `maintenance`：重建、扫描、补偿、清理、批处理任务

#### 说明

如果为了兼容暂时不能拆路径，也应在 router 内部先完成语义分组，不再继续随意扩张。

---

### 10.2 配置域优先按职责划分，而不是继续堆成泛入口

#### 规则

配置接口应尽量分清：

- 系统配置
- 模型配置
- MCP 配置
- 语音配置
- 用户偏好或模式开关

#### 目标

避免任何配置最后都堆到一个“万能 config 接口”里。

---

### 10.3 聊天、任务、连接、资产等独立领域保持独立 router

#### 规则

已经有较明确边界的领域，应继续维持独立 router，而不是重新混合回大杂烩路由。

例如：

- `chat_router.py`
- `task_control_router.py`
- `connection_router.py`
- `asset_router.py`

---

## 11. WebSocket 规则

### 11.1 主应用 WebSocket 入口应视为路由体系的一部分

#### 规则

主应用 WebSocket 不应长期直接散落在 `main.py` 中。

#### 推荐方向

1. 抽到独立 WebSocket router 文件
2. 保持原有 URL 不变
3. 与 HTTP router 一样具备可盘点性

---

### 11.2 插件内聚型 WebSocket 暂不纳入本轮基线改造

#### 规则

外部插件、MOD、插件内部自带 WebSocket，当前只做边界声明，不作为本轮统一化实施对象。

---

## 12. 标签与命名规则

### 12.1 tags 应与业务域名称稳定对应

#### 规则

- 一个 router 的 tags 应尽量与其业务域一致
- 避免同一领域多个近义 tag 并存
- 新增 router 时不要随意创造新同义词

#### 推荐

- `models`
- `agents`
- `memory`
- `maintenance`
- `system`

关键不是绝对单复数，而是同类统一。

---

### 12.2 路径段命名保持统一风格

#### 规则

主应用路径段应使用同一种主风格，不继续混用：

- snake_case
- kebab-case
- camelCase

#### 建议

结合现有项目实际，优先沿用当前更常见、改动成本更低的一套风格，并逐步停止继续扩散历史混搭。

如果要新定规则，更推荐 plain segment 或 kebab-case 的可读风格。

---

## 13. 前端兼容规则

### 13.1 backend 规则变更必须同步评估前端影响

#### 规则

凡涉及以下变更，都必须同步检查前端：

- 路径改名
- 返回体结构变化
- 错误字段变化
- 请求体字段变化

#### 重点关注文件

- `src/composables/dashboard/useDashboard.ts`
- `src/composables/dashboard/useMemories.ts`
- `src/composables/dashboard/useModelConfig.ts`
- `src/views/MainWindow.vue`
- `src/api/assets.ts`
- 其他直接拼接 `API_BASE` 或硬编码路径的文件

---

### 13.2 路径收敛优先采用“兼容迁移”而不是“直接切断”

#### 规则

如果未来要把历史路径收敛到标准入口，优先采用：

1. 保留旧路径兼容一段时间
2. 前端逐步切换到新路径
3. 最后删除兼容层

而不是一次性强切。

---

### 13.3 前端应逐步建立统一请求封装

#### 规则

随着 backend 统一化推进，前端也应逐步收敛：

- base URL
- 错误解析
- envelope 拆包
- 超时处理
- 常用 API 常量或 typed client

这样才能真正承接 backend 的规则收敛。

---

## 14. 新增接口准入基线

以后新增主应用 API 时，至少应回答以下问题：

1. 它属于哪个业务域
2. 应该挂在哪个 router
3. 是 CRUD 还是 action 还是 summary
4. 路径是否符合当前命名规则
5. 请求体是否需要 Pydantic 模型
6. 是否有明确 `response_model`
7. 错误是否符合统一策略
8. 是否会影响前端既有调用
9. 是否误把插件 / 外部路由范围也一起卷入

如果其中多个问题回答不清，通常说明接口设计还不够稳定。

---

## 15. 推荐落地顺序

如果后续按本基线实施，建议顺序如下：

1. 先统一 router prefix 规则
2. 再统一配置命名与错误处理
3. 再统一 action 返回体与请求体建模
4. 再梳理 memory / maintenance / config 领域边界
5. 再抽离主应用 WebSocket
6. 最后处理路径兼容层与前端迁移

---

## 16. 最终结论

当前最适合 `PeroCore-electron` 主应用 backend 的统一规则，并不是一套脱离现状、完全理想化的 API 设计，而是：

- 以当前多数 router 已具备的模块化方向为基础
- 用 `prefix + 相对路径` 统一路由组织
- 用“CRUD / action / summary”三类规则统一接口体验
- 用 `response_model`、结构化错误、Pydantic 请求体提升契约稳定性
- 用兼容迁移方式降低前端与历史路径的切换成本

一句话总结：

> 这份规则基线的目标，不是让所有接口长得完全一样，而是让主应用 backend 的同类接口遵守同类规则，最终形成可维护、可扩展、可迁移的一套 API 体系。