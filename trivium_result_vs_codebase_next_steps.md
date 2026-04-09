# PeroCore-electron × TriviumDB 整改优先级与事项清单

## 文档目的

本文档用于整理当前 PeroCore-electron 在接入 TriviumDB 0.5.0 后的"稳不稳"专项审查结果，输出可执行的整改优先级、问题事项、代码证据、风险说明与后续建议，便于后续排期和逐项收敛。

本文档经过两轮迭代：

- **第一轮**（原始审查）：建立整改事项总表，梳理补偿机制、重建能力、生命周期三大方向
- **第二轮**（现状对照）：逐项核实代码实际推进状态，区分"已完成"与"仍待收尾"，重新确认下一步优先动手事项

---

## 总体结论

当前这套接法已经从"存在明确 0.5.0 兼容性断裂风险"，提升到"核心路径可运行、主要检索链路已完成分层修复"的状态。

但从工程可靠性角度看，当前体系仍然存在以下结构性问题：

1. SQLite 与 TriviumDB 双写属于弱一致性，缺少补偿机制（**部分已补，仍有收尾空间**）
2. 缺少从 SQLite 全量重建 TriviumDB 的运维能力（**已完成**）
3. TriviumDB 已被用作业务图关系的一部分，但恢复与生命周期管理不足（**部分已补，flush 策略仍需收口**）
4. 损坏恢复策略较激进，异常分类不够精细（**未变，仍是风险点**）
5. 少量调用层仍残留旧式兼容心智（**部分已清理，仍有收尾空间**）

一句话判断：

> 当前系统"能用，而且比之前稳了很多"，但还不属于"可以完全放心依赖、出了问题也好修复"的状态。核心补偿机制已成型，下一步是彻底收尾。

---

## 整改优先级总表（现状版）

| 优先级 | 事项 | 风险等级 | 代码现状 | 是否建议立即处理 |
|---|---|---|:---:|---|
| P0 | 补齐 SQLite -> TriviumDB 全量重建能力 | 高 | **已完成** | ~~否~~ 已结项 |
| P0 | 建立 TriviumDB 写入失败补偿机制 | 高 | **大部分完成** | 收尾中 |
| P1 | 清理图关系链路中的旧式 neighbors 返回兼容逻辑 | 中高 | 未完成 | 建议尽快 |
| P1 | 完善 TriviumDB 生命周期管理与关键时点 flush 策略 | 中 | 未完成 | 建议尽快 |
| P1 | 细化 TriviumDB 初始化失败时的异常分类与恢复策略 | 中 | 未完成 | 建议尽快 |
| P2 | 建立 TriviumDB 版本升级后的 API 回归校验清单 | 中 | 未完成 | 保留为长期规范 |
| P2 | 继续收整调用层语义，明确基础/混合/高级检索边界 | 中低 | 基本完成 | 随功能演进处理 |

---

## P0：必须优先整改

### 事项 1：补齐 SQLite -> TriviumDB 全量重建能力

#### 问题描述
当前系统默认 SQLite 是主存储，TriviumDB 同时承担：

- 向量检索
- 图关系维护
- 关系继承
- 删除同步

但一旦 TriviumDB 写失败，系统没有统一的重建入口来恢复索引和图谱。

#### 风险
如果 TriviumDB 写失败，会出现：

- SQLite 有记录
- TriviumDB 没节点或缺边
- 后续搜索、联想、合并、关系维护出现偏差

#### 后果
- 某些记忆检索不到
- 图谱边断裂
- reflection 结果不稳定
- 问题无法通过现有运维方式快速修复

#### 代码现状：**已完成**

当前已具备完整实现：

- `ReindexService.rebuild_trivium_store_with_session(...)`
- `trivium_store.reset_storage()`
- 按 SQLite 全量扫描 `Memory`
- 优先复用 SQLite 中缓存的 embedding，不足时补算
- 重建节点 payload
- 重建时间顺序双向关系边
- 重建结束后显式 `flush()`
- 后台路由入口：`POST /api/memory/rebuild_trivium`

关键代码位置：

- [reindex_service.py](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/core/reindex_service.py)
- [trigger_rebuild_trivium](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/routers/maintenance_router.py#L332-L345)
- [reset_storage](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_store.py#L326-L341)

#### 结论
- 状态：**已完成，可从 P0 主清单中移出**
- 后续仅需补"运维规则"和"回归校验"，不再属于功能缺口

---

### 事项 2：建立 TriviumDB 写入失败补偿机制

#### 问题描述
当前 TriviumDB 写失败只打印日志，不做重试、不做补偿、不落失败任务。

#### 风险
这会导致"主库成功、索引层失败"的长期漂移，且在 reflection 链路中会进一步放大为：

- 新节点已写入 SQLite，但 TriviumDB 未建节点
- 旧节点已从 SQLite 删除，但 TriviumDB 仍残留幽灵节点
- 合并后的继承边未补齐，图谱结构失真
- 重写 embedding 后，TriviumDB 仍保留旧向量和旧 payload
- 社交记忆子系统出现独立 store 的双写漂移

#### 代码现状：**大部分完成，仍有收尾空间**

当前已经落地的能力包括：

**已完成能力 A：统一补偿任务模型**

- `TriviumSyncTask` 已具备：`operation`、`memory_id`、`store_name`、`dedupe_key`、`payload_json`、`status`、`retry_count`、`last_error`、`agent_id`
- 数据库迁移里已经自动补 `store_name`

关键代码位置：

- [TriviumSyncTask](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/models.py#L254-L266)
- [database.py](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/database.py#L117-L133)

**已完成能力 B：补偿服务已覆盖三类操作**

- `upsert_memory`
- `link_memories`
- `delete_memory`

并且已带有去重键构建、pending/failed 任务重试、成功后删任务、失败后累计 `retry_count`、按 store flush。

关键代码位置：

- [trivium_sync_service.py](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_sync_service.py)

**已完成能力 C：多 store 已正式进入补偿体系**

- 默认 `memory`
- 独立 `social`
- `store_name` 过滤重试
- `store_name` 统计摘要

关键代码位置：

- [social_memory_service.py](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/nit_core/plugins/social_adapter/social_memory_service.py#L44-L104)

**已完成能力 D：运维入口与启动自愈已落地**

- 手动重试接口：`POST /api/memory/retry_trivium_sync`
- 任务列表接口：`GET /api/memory/trivium_sync_tasks`
- 任务摘要接口：`GET /api/memory/trivium_sync_summary`
- 启动时自动恢复 pending / failed 任务
- 启动日志按 store / operation 输出摘要

关键代码位置：

- [maintenance_router.py](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/routers/maintenance_router.py#L347-L429)
- [main.py](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/main.py#L256-L287)

**已完成能力 E：memory_service.py 主链路已全面接入**

- `upsert_memory` 已接入
- 时间边 `link_memories` 已接入

关键代码位置：

- [memory_service.py:L120-L192](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/memory_service.py#L120-L192)

#### 仍未完全收尾的部分

**问题 1：`reflection_service.py` 并非所有写点都已统一到补偿语义**

已经能确认接入补偿兜底的写点包括：

- 删除记忆后同步删 Trivium 节点（双重兜底）
- 反思过程中重写 embedding / upsert
- 合并后新记忆写入 Trivium
- 合并后删除旧节点
- 重复社交摘要清理删除
- 边界维护删除
- 回滚恢复里的 upsert

但仍有部分关系边路径（主要是图边继承链路）还保持"直接写 Trivium，异常时局部兜底"风格，没有完全收敛成统一写入语义。

**问题 2：图边继承失败补偿实现存在语义不够严谨的问题**

在合并记忆时，边继承失败后的补偿是用 `enqueue_time_link(...)` 去排队，但传入了 `label="inherited"`。方法名是"time link"，实际用途是"继承图边"，语义上有混用。

#### reflection_service.py Trivium 写点接入清单（现状版）

| 位置 | 操作类型 | 当前行为 | 现状 |
|---|---|---|---|
| [reflection_service.py:L625-L639](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L625-L639) | delete_memory | 删除记忆后同步删除 Trivium 节点，失败后入补偿队列 | **已接入** |
| [reflection_service.py:L857-L864](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L857-L864) | upsert_memory | 反思过程中重算 embedding 并覆写节点，失败后入补偿队列 | **已接入** |
| [reflection_service.py:L982-L993](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L982-L993) | upsert_memory | 合并后新记忆写入 Trivium，失败后入补偿队列 | **已接入** |
| [reflection_service.py:L1000-L1035](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1000-L1035) | link_memories | 将旧节点对外关系继承到新节点，失败后用 enqueue_time_link 补偿（语义混用） | **部分接入，需收口** |
| [reflection_service.py:L1037-L1048](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1037-L1048) | delete_memory | 合并后删除旧节点，失败后入补偿队列 | **已接入** |
| [reflection_service.py:L1091-L1101](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1091-L1101) | delete_memory | 清理重复社交摘要时同步删向量，失败后入补偿队列 | **已接入** |
| [reflection_service.py:L1130-L1139](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1130-L1139) | delete_memory | 维护边界时删除低重要记忆，失败后入补偿队列 | **已接入** |
| [reflection_service.py:L1211-L1218](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1211-L1218) | link_memories | dream_and_associate 新建关系边，失败后未入补偿队列 | **未接入** |
| [reflection_service.py:L1289-L1296](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1289-L1296) | link_memories | scan_lonely_memories 为孤独记忆补边，失败后未入补偿队列 | **未接入** |
| [reflection_service.py:L1623-L1633](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1623-L1633) | delete_memory | 撤销创建记忆时同步删向量，失败后入补偿队列 | **已接入** |
| [reflection_service.py:L1672-L1682](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1672-L1682) | upsert_memory | 恢复 modified_data 时重建向量节点，失败后入补偿队列 | **已接入** |
| [reflection_service.py:L1716-L1726](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1716-L1726) | upsert_memory | 恢复 deleted_data 时回放节点，失败后入补偿队列 | **已接入** |

#### 结论
- 状态：**大部分已完成，但仍有收尾空间**
- 当前这项不再是"补偿机制有没有"，而是"补偿机制是否彻底统一、语义是否干净"

---

## P1：建议尽快整改

### 事项 3：清理图关系链路中的旧式 neighbors 返回兼容逻辑

#### 问题描述
主封装层里，`neighbors()` 返回格式已经被收敛为 `List[int]`，但部分业务代码仍保留旧式多类型猜测逻辑。

#### 当前较稳定的封装
- [get_neighbors](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_store.py#L294-L302)
- [has_link](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_store.py#L304-L311)

#### 遗留旧逻辑位置
- [reflection_service.py:L1001-L1015](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1001-L1015)

#### 风险
说明调用层仍然保留"绑定层返回可能不稳定"的旧心智，会带来：

- 维护成本增加
- 封装边界不清晰
- 后续重构时容易遗漏

#### 整改建议
把 reflection 中涉及 `neighbors` 的处理统一为：

- 只接受 `int`
- 不再兼容 `.id` / tuple / dict

#### 目标状态
让 `TriviumMemoryStore` 成为唯一返回格式适配层，业务层只消费明确结构。

---

### 事项 4：完善 TriviumDB 生命周期管理与关键时点 flush 策略

#### 问题描述
当前 TriviumDB 有：

- `enable_auto_compaction(interval_secs=300)`
- `flush()`

但没有形成明确的上层生命周期管理策略。

#### 代码证据
- [trivium_store.py:L57-L95](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_store.py#L57-L95)
- [flush](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_store.py#L318-L322)
- [aura_vision_service.py:L205-L207](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/perception/aura_vision_service.py#L205-L207)

#### 当前 flush 点（分散存在）
- 补偿任务批量重试结束后：按 touched stores flush
- reindex 完成后 flush
- rebuild 完成后 flush
- `reflection_service.py` 某些恢复路径结束后 flush
- `aura_vision_service.py` 中有显式 flush

关键代码位置：

- [trivium_sync_service.py:L353-L355](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_sync_service.py#L353-L355)
- [reindex_service.py:L113](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/core/reindex_service.py#L113)
- [reindex_service.py:L233](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/core/reindex_service.py#L233)
- [reflection_service.py:L1656-L1661](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/reflection_service.py#L1656-L1661)
- [aura_vision_service.py:L205-L206](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/perception/aura_vision_service.py#L205-L206)

#### 风险
缺少统一的 flush 策略，会导致：

- 批量写入后落盘时机不明确
- 应用退出前没有统一收尾
- 恢复和运维动作没有明确入口

#### 整改建议
建议建立以下策略：

1. 批量导入/批量维护后显式 flush
2. 应用关闭前增加统一 flush hook
3. 后续 rebuild/recover 任务结束后统一 flush

---

### 事项 5：细化 TriviumDB 初始化失败时的异常分类与恢复策略

#### 问题描述
当前 `_ensure_loaded` 的恢复策略偏激进：只要初始化异常，就倾向把整个 data_dir 迁走并重建。

#### 代码证据
- [trivium_store.py:L57-L95](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_store.py#L57-L95)

#### 当前逻辑
1. 尝试打开数据库
2. 任意异常都打印"可能损坏"
3. 直接备份目录并重建

当前优点是自愈能力强、不容易把用户卡死。但问题在于：

- 文件占用也可能被当成损坏
- 权限问题也可能被当成损坏
- 暂时性初始化失败也可能触发整库迁移

#### 风险
误判成本较高，尤其在用户已有本地数据时。

#### 整改建议
至少区分：

1. 模块 / DLL 加载失败
2. 权限问题
3. 文件占用问题
4. 真正的数据损坏问题

---

## P2：建议纳入长期规范

### 事项 6：建立 TriviumDB 版本升级后的 API 回归校验清单

#### 问题描述
虽然这轮已经完成了对 0.5.0 的兼容修复，但 PeroCore 依赖的 API 仍然比较深。

#### 当前依赖面
集中在：

- `insert_with_id`
- `index_text`
- `index_keyword`
- `search`
- `search_hybrid`
- `search_advanced`
- `neighbors`
- `link`
- `delete`
- `flush`
- `enable_auto_compaction`

关键代码位置：

- [trivium_store.py](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_store.py)

#### 建议
建立升级回归 checklist，至少覆盖：

1. insert / delete / link / neighbors
2. basic / hybrid / advanced 三条搜索路径
3. payload_filter 生效性
4. flush / auto_compaction 是否可用
5. 最小业务回归样例

---

### 事项 7：继续收整调用层语义，明确基础 / 混合 / 高级检索边界

#### 现状
当前 `trivium_store.search()` 已经把基础 / hybrid / advanced 做了明显分派，整体方向是对的。

关键代码位置：

- [trivium_store.search](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/trivium_store.py#L224-L286)
- [memory_service.py:L498-L511](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/memory_service.py#L498-L511)
- [memory_service.py:L541-L603](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/memory_service.py#L541-L603)
- [memory_service.py:L661-L704](file:///c:/Users/15901/Desktop/Workstation/PeroCore-electron/backend/services/memory/memory_service.py#L661-L704)

#### 建议
后续新增功能时继续保持这个原则：

- 默认优先高层 API
- 只有确实需要时才走 advanced
- 业务调用点明确表达意图，不依赖隐式默认值

---

## 当前状态变化说明

相对于最初审查时的判断，当前已经完成的稳定性提升包括：

1. 已修复 `search_advanced` 在 0.5.0 下的位置参数错位问题
2. 已将检索分派重构为 `basic / hybrid / advanced` 三层
3. 已将 `has_link()` 收敛为基于 `List[int]` 的明确实现
4. 已将主要调用点改为显式表达 DPP / 混合检索意图
5. 已完成 lint 与最小回归验证
6. **已补齐 SQLite -> TriviumDB 全量重建能力**
7. **已建立写入失败补偿机制，覆盖 upsert/link/delete 三类操作**
8. **已支持多 store（memory / social）复用统一补偿体系**
9. **已落地启动自愈与运维观测入口**

因此，原本"API 兼容性高风险"这一项，现在更准确的判断应当是：

- **已从高风险下降为中风险**

但"一致性、恢复、可运维性"相关问题仍然是当前整改重点。

---

## 下一步优先动手事项

### 第一优先级：收 `reflection_service.py` 剩余写点，彻底统一补偿语义

#### 具体内容
1. 接入 `dream_and_associate` 的 link 失败到补偿队列
2. 接入 `scan_lonely_memories` 的 link 失败到补偿队列
3. 把图边继承失败补偿从 `enqueue_time_link(...)` 改为更语义明确的统一入口
4. 顺手清理 `reflection_service.py` 中图边继承逻辑里的局部兼容心智

#### 预期收益
- `reflection_service.py` 将真正纳入统一补偿体系
- 补偿语义不再存在"时间边"和"继承边"混用问题

---

### 第二优先级：补 Trivium 生命周期治理，统一 flush 策略

#### 具体内容
1. 明确哪些批处理任务结束后必须 flush
2. 给主应用补统一 shutdown flush hook
3. 为多 store 做统一 flush 入口或批量 flush 管理

#### 预期收益
- 减少"逻辑已成功但落盘时机不稳定"的灰区
- 让 rebuild / retry / 恢复链路更像完整工程能力

---

### 第三优先级：细化 `_ensure_loaded()` 异常分类

#### 具体内容
1. 先区分 `ImportError/OSError` 与运行期打开失败
2. 再区分权限 / 占用 / 数据损坏等典型错误模式
3. 至少先做到"不是所有异常都自动迁库重建"

#### 预期收益
- 降低误判导致的目录迁移风险
- 让本地数据更可控、更可解释

---

## 建议执行顺序

### 第一阶段（当前最优先）
1. 收 `reflection_service.py` 剩余写点（dream_and_associate、scan_lonely_memories）
2. 统一关系边失败补偿入口（解决 enqueue_time_link 语义混用）
3. 清理图边继承逻辑中的语义混用

### 第二阶段
4. 统一批量任务结束后的 flush 规则
5. 增加主应用 shutdown flush
6. 统一多 store flush 入口

### 第三阶段
7. 细化 `_ensure_loaded()` 的异常分类
8. 降低误判损坏时的自动迁移激进度

### 第四阶段
9. 建立 TriviumDB 升级回归 checklist
10. 持续收整新增调用层语义

---

## 最终结论

当前这套接法已经具备继续演进的基础，主要问题不再是"TriviumDB 0.5.0 API 能不能接上"，而是：

- 双写弱一致性怎么补（**大部分已完成**）
- 索引/图谱怎么重建（**已完成**）
- 出问题后怎么恢复（**已具备启动自愈，仍需完善生命周期**）
- 生命周期怎么管理（**待收口**）

后续整改应优先围绕"补偿收口"、"生命周期治理"、"初始化异常治理"这三个方向推进。
