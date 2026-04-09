# Backend API 统一化实施清单

## 1. 文档目标

本文是对《`backend_api_standardization_analysis.md`》的实施化展开版本。

它不再侧重“问题分析”，而是直接回答下面几个问题：

1. 这一轮 API 统一化到底要改哪些文件
2. 每类文件要改什么
3. 哪些项可以先做，哪些项必须后置
4. 前端哪些文件需要同步注意
5. 哪些内容明确不在本轮范围内

本文默认沿用当前约束：**外部插件、MOD、插件内聚型路由先不动**。

---

## 2. 本轮实施范围

### 2.1 纳入本轮的 backend 范围

本轮主要聚焦主应用 backend 内部以下内容：

- `backend/main.py`
- `backend/routers/*.py` 中的主应用 router
- 主应用自身的 WebSocket 入口
- 主应用 API 的返回体、错误处理、请求体建模、`response_model` 使用方式

### 2.2 明确不纳入本轮的范围

本轮先不动以下内容：

- `backend/nit_core/plugins/social_adapter/social_router.py`
- `backend/mods/_external_plugins/router.py`
- 其他插件内聚型路由
- MOD 侧自行维护的接口组织方式

这些内容在分析层面要知道它们存在，但不作为本轮实施阻塞项。

---

## 3. 实施总原则

在开始具体改造前，先固定几条执行原则：

1. **先统一规则，再统一代码**
2. **先做主应用内部收敛，再考虑路径收敛**
3. **先保兼容，再推动前端迁移**
4. **不把插件/外部路由迁移作为本轮前置条件**
5. **所有对外路径改动都要同步评估前端影响**

---

## 4. P0 实施清单

P0 表示可以直接进入实施准备、且应优先推进的部分。

### P0-1：统一主应用 router 的 prefix 风格

#### 目标

把当前“无 prefix、装饰器里写完整 `/api/...`”的主应用 router，统一成 router 自带 `prefix`、endpoint 使用相对路径的写法。

#### 重点文件

- `backend/routers/system_router.py`
- `backend/routers/maintenance_router.py`
- `backend/routers/chat_router.py`
- `backend/routers/pet_router.py`
- `backend/routers/voice_router.py`
- 其他仍存在完整路径硬编码的主应用 router

#### 要做的事

1. 给 router 增加明确 `prefix`
2. 把 endpoint 装饰器里的完整路径改成相对路径
3. 保持现有对外 URL 不变，优先只做内部组织方式统一
4. 检查 `main.py` 中 `include_router(...)` 是否仍然成立

#### 输出结果

- 主应用 router 组织方式一致
- 新增接口时有明确的组织模板
- 后续做命名收敛时更容易批量处理

#### 注意事项

- 本阶段尽量不改已有对外路径
- 先不要碰插件 router
- 若某 router 同时承担多个领域，先记录，后续再拆

---

### P0-2：统一配置接口命名策略

#### 目标

在 `/api/config` 与 `/api/configs` 之间选定一套标准命名，并确定兼容迁移方案。

#### 重点文件

- `backend/routers/config_router.py`
- `backend/routers/system_router.py`
- `backend/main.py`（若有统一挂载或兼容处理需要）

#### 要做的事

1. 明确标准入口到底保留哪一套
2. 盘点当前所有配置相关 endpoint
3. 标记哪些是“历史兼容接口”
4. 设计兼容层或别名策略

#### 输出结果

- 配置域路径有统一标准
- 后续前端迁移路径清晰
- 文档与测试可以围绕同一套命名收敛

#### 前端同步注意

重点关注：

- `src/composables/dashboard/useModelConfig.ts`
- 其他直接使用 `/configs` 的前端代码

---

### P0-3：统一错误处理策略

#### 目标

消除“有些接口抛 `HTTPException`，有些接口返回 `{"error": ...}`，有些接口 200 但 body 表示失败”的混搭状态。

#### 重点文件

优先检查这些 router：

- `backend/routers/system_router.py`
- `backend/routers/maintenance_router.py`
- `backend/routers/chat_router.py`
- `backend/routers/memory_router.py`
- `backend/routers/pet_router.py`
- `backend/routers/voice_router.py`

#### 要做的事

1. 统一业务失败返回方式
2. 统一服务端异常出口
3. 清理直接 `return {"error": ...}` 的历史写法
4. 明确动作型接口失败时的状态码策略

#### 输出结果

- 前端可以用统一逻辑解析失败
- API 行为更稳定
- OpenAPI 表达更清晰

#### 前端同步注意

重点关注：

- 统一错误解析器
- `detail` / `message` / `error` 的兼容过渡
- 现有 toast / message 提示逻辑是否依赖旧字段

---

### P0-4：统一返回体策略

#### 目标

明确哪些接口直接返回资源，哪些接口返回 envelope，哪些接口返回 summary 对象。

#### 重点文件

- `backend/routers/maintenance_router.py`
- `backend/routers/system_router.py`
- `backend/routers/chat_router.py`
- `backend/routers/sync_router.py`
- `backend/routers/memory_router.py`

#### 要做的事

1. 区分 CRUD、action、summary 三类接口
2. 为 action 接口统一返回结构
3. 为 summary/statistics 接口明确字段稳定性要求
4. 盘点前端直接按根对象读取的地方

#### 输出结果

- 前后端对响应结构有稳定预期
- 后续类型收敛更容易

#### 前端同步注意

重点关注：

- `src/composables/dashboard/useDashboard.ts`
- `src/composables/dashboard/useMemories.ts`
- `src/views/MainWindow.vue`

这些地方很可能直接把 `res.json()` 当最终数据结构使用。

---

### P0-5：统一请求体建模方式

#### 目标

减少松散 `Dict[str, Any]`、裸参数、embed 单字段混用的情况，形成可预测的请求 schema 风格。

#### 重点文件

优先检查存在 POST / PUT / PATCH 的主应用 router：

- `backend/routers/config_router.py`
- `backend/routers/memory_router.py`
- `backend/routers/chat_router.py`
- `backend/routers/maintenance_router.py`
- `backend/routers/pet_router.py`
- `backend/routers/model_router.py`

#### 要做的事

1. 区分简单参数与复杂请求体
2. 复杂请求尽量统一为 Pydantic 模型
3. 历史松散 payload 接口做标注与收敛计划
4. 保证 OpenAPI 中请求 schema 清晰可读

#### 输出结果

- 请求契约更稳定
- 自动文档更完整
- 前端更容易做类型化调用

---

## 5. P1 实施清单

P1 表示在 P0 规则确定后，应尽快推进的收敛项。

### P1-1：梳理 memory 域与 maintenance 域边界

#### 重点文件

- `backend/routers/memory_router.py`
- `backend/routers/maintenance_router.py`

#### 要做的事

1. 列出 `memory_router` 中的资源型接口
2. 列出 `maintenance_router` 中的 memory 运维接口
3. 明确 `memories` 与 `memory` 的命名边界
4. 形成“资源接口”和“运维接口”的分层规则

#### 目标结果

- memory 领域不再靠历史习惯扩张
- 后续新增接口知道该放哪一边

#### 前端同步注意

重点关注：

- `src/composables/dashboard/useMemories.ts`
- Dashboard 中 memory 相关页面与操作面板

---

### P1-2：梳理配置域边界

#### 重点文件

- `backend/routers/config_router.py`
- `backend/routers/system_router.py`
- `backend/routers/model_router.py`
- `backend/routers/mcp_config_router.py`
- `backend/routers/voice_router.py`

#### 要做的事

1. 分清全局系统配置与业务配置
2. 分清模型配置、MCP 配置、语音配置的归属
3. 决定哪些能力继续保留泛配置入口，哪些要拆分

#### 目标结果

- 配置域层级清晰
- 不再出现“system 里也有 config，config 里也有系统项”的扩散

#### 前端同步注意

重点关注：

- `src/composables/dashboard/useModelConfig.ts`
- 与模型、语音、MCP 设置相关的 UI 区域

---

### P1-3：补齐 `response_model`

#### 重点文件

优先补齐这些领域：

- system 类接口
- maintenance 类接口
- memory 摘要类接口
- Trivium sync observability 接口

#### 要做的事

1. 盘点当前未声明 `response_model` 的主应用接口
2. 区分可以直接复用现有模型的接口
3. 对 summary / stats 类接口补充专用响应模型

#### 目标结果

- OpenAPI 文档质量提升
- 前端类型化能力提升

---

### P1-4：抽离主应用 WebSocket 入口

#### 重点文件

- `backend/main.py`
- 计划新增：`backend/routers/ws_router.py` 或等价文件

#### 要做的事

1. 梳理 `/ws/browser` 与 `/ws/gateway` 的职责
2. 抽离出独立 WebSocket router
3. 保持原入口路径不变
4. 让 `main.py` 只做挂载与启动编排

#### 目标结果

- `main.py` 更干净
- 路由盘点更完整
- HTTP 与 WebSocket 的治理方式更接近

#### 注意事项

- 这里只处理主应用 WebSocket
- 不碰插件内部自带的 WebSocket 路由

---

### P1-5：明确例外项规则

#### 目标

把“哪些不改”也写成明确规则，而不是口头约定。

#### 需要固化的内容

1. 外部插件、MOD、插件内聚型路由是本轮例外项
2. 例外项不阻塞主应用 API 统一化
3. 后续若要扩围，单独立项评估

#### 目标结果

- 范围边界清晰
- 实施时不会反复纠结是否要一起迁移插件路由

---

## 6. P2 实施清单

P2 表示不阻塞当前统一化落地，但适合在体系收敛后继续推进。

### P2-1：区分 REST / action / RPC 三类接口规范

#### 要做的事

1. 给资源型接口定义 REST 规则
2. 给行为触发型接口定义 action 规则
3. 给 IPC/命令派发类接口定义 RPC 规则

#### 目标结果

- 新接口设计不再混杂
- 路径命名和返回体策略更可预测

---

### P2-2：统一 tags、路径词和命名文案

#### 要做的事

1. 统一 tags 使用规则
2. 统一路径词风格
3. 统一单数 / 复数命名策略
4. 统一文档中的领域称谓

---

### P2-3：形成新增接口准入规则

#### 要做的事

给后续新增接口建立最小检查项：

- 放在哪个 router
- 用哪种请求体建模
- 返回体是否有 schema
- 错误策略是否符合规范
- 是否影响前端已有调用

---

## 7. 推荐的文件级实施顺序

为了降低风险，建议按下面顺序推进。

### 第一批：先统一最基础规则

- `backend/routers/system_router.py`
- `backend/routers/config_router.py`
- `backend/routers/maintenance_router.py`
- `backend/routers/chat_router.py`

原因：

- 这些文件最能代表当前不统一问题
- 同时会牵动错误处理、返回体、prefix 风格等核心规则

### 第二批：收敛 memory / config / websocket 边界

- `backend/routers/memory_router.py`
- `backend/main.py`
- `backend/routers/ws_router.py`（若开始抽离）
- 与 config 域相关的其他 router

### 第三批：补齐 schema 与细节一致性

- `backend/routers/sync_router.py`
- `backend/routers/pet_router.py`
- `backend/routers/voice_router.py`
- 其他仍缺 `response_model` 或请求体建模不清晰的 router

---

## 8. 前端同步清单

虽然这份文档聚焦 backend，但下面这些前端文件要提前纳入同步关注范围。

### 高优先级关注文件

- `src/composables/dashboard/useDashboard.ts`
- `src/composables/dashboard/useMemories.ts`
- `src/composables/dashboard/useModelConfig.ts`
- `src/views/MainWindow.vue`

### 次高优先级关注文件

- `src/components/Pet3DView.vue`
- `src/components/FileExplorer.vue`
- `src/api/assets.ts`
- 其他直接拼接 `API_BASE` 或写死路径的调用文件

### 前端需要同步检查的事项

1. 是否写死了旧路径
2. 是否直接依赖旧返回体结构
3. 是否假设错误字段一定是某一种格式
4. 测试里是否写死了接口路径或响应结构

---

## 9. 开工前检查清单

在真正开始改代码前，建议先逐项确认：

- [ ] 是否已经固定标准配置命名
- [ ] 是否已经固定错误处理策略
- [ ] 是否已经固定 action 接口的返回体结构
- [ ] 是否已经确定 `memory` / `memories` 的命名边界
- [ ] 是否已经确定 WebSocket 抽离方式
- [ ] 是否已经确认本轮不动插件 / MOD / 外部路由
- [ ] 是否已经列出需要同步检查的前端文件

---

## 10. 最终执行建议

如果接下来要正式动手，建议采用下面的节奏：

1. 先出一版“统一规则基线”
2. 再按文件批次推进 backend 改造
3. 每改一批，就同步核对前端受影响点
4. 先保兼容，再逐步收敛路径
5. 等主应用稳定后，再决定是否扩展到插件 / MOD 路由

一句话总结就是：

> 本轮最适合的做法，不是全域大迁移，而是把主应用 backend 内部先收成一套统一规则，再带着前端逐步迁移。