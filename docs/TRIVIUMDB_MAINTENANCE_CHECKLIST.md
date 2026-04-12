# PeroCore TriviumDB 运维与升级回归校验规范

> **版本**：1.0.0 · **更新时间**：2026-04-13
> **适用范围**：PeroCore 接入 TriviumDB 引擎升级、日常维护、回归测试
> **不适用范围**：SQLite 主库其他不涉及 TriviumDB 同步的业务逻辑

---

## 目录

1. [概述](#1-概述)
2. [核心功能回归 (API Level)](#2-核心功能回归-api-level)
3. [一致性与补偿机制回归 (Consistency Level)](#3-一致性与补偿机制回归-consistency-level)
4. [稳健性与自愈回归 (Resilience Level)](#4-稳健性与自愈回归-resilience-level)
5. [性能与生命周期回归 (Resource & Lifecycle Level)](#5-性能与生命周期回归-resource--lifecycle-level)

---

## 1. 概述

本文档定义了 PeroCore 在 TriviumDB 引擎升级或日常维护后的回归标准。根据 "稳不稳" 专项审查结果，进一步规范核心补偿机制、重建能力和生命周期的测试边界，确保记忆系统的稳定性。

---

## 2. 核心功能回归 (API Level)

每次引擎版本变动后，必须核实以下 API 的表现：

- [ ] **向量插入 (insert_with_id):** 确保 ID 冲突处理符合预期（覆盖模式）。
- [ ] **关联连边 (link):** 验证 `label` 和 `weight` 参数是否正常工作。
- [ ] **邻居查询 (neighbors):** 确认返回格式为 `List[int]`，不再包含旧版的复杂结构。
- [ ] **基础检索 (search_basic):** 验证基础检索下向量搜索准确度。
- [ ] **混合检索 (search_hybrid):** 验证 `hybrid_alpha` 的分配逻辑与实际排序混合效果。
- [ ] **高级检索 (search_advanced):** 校验位置参数（如 `enable_dpp`）是否位移以及高级检索选项是否生效。
- [ ] **过滤条件生效性 (payload_filter):** 核验依据 payload 属性过滤数据的表现是否符合预期。
- [ ] **最小业务回归样例:** 运行完整的“记忆存入 -> 图边生成 -> 检索召回”最小全链路以验证核心串联。

---

## 3. 一致性与补偿机制回归 (Consistency Level)

- [ ] **断网/异常模拟:** 模拟 `trivium_store` 及其底层抛出异常，观察 `TriviumSyncTask` 表是否成功产生 Pending 任务（覆盖 `upsert`, `link`, `delete`）。
- [ ] **多 Store 补偿支持:** 确认异常后补偿任务中的 `store_name`（如 `memory`, `social`）均成功记录，并且重试时正确路由。
- [ ] **启动自愈:** 重启后端，验证系统启动阶段是否成功消费和处理积压的 pending/failed 任务。
- [ ] **语义正确性收敛:** 核实 `reflection_service.py` 中的各类写操作（包含 `inherited` 图边继承、`dream_and_associate`、`scan_lonely_memories`）发生异常均统一进入补偿队列。
- [ ] **全量重建校验:** 手动调用 `POST /api/memory/rebuild_trivium`，验证能否顺利从 SQLite 主库全量扫描、重建向量节点、重建时间顺序双向边并隐式触发 Flush。

---

## 4. 稳健性与自愈回归 (Resilience Level)

- [ ] **初始化异常分类:** 模拟破坏初始化环境，区分 ImportError/OSError、权限不足、文件占用等问题，确保非数据本身损坏造成的异常不会激进地触发备库迁移与完全重建。
- [ ] **目录占用测试:** 在后端启动时用其他程序锁定 `.tdb` 文件，验证 `_ensure_loaded` 是否抛出精准错误日志，而不直接判定为死库并备份。
- [ ] **损坏恢复:** 修改并破坏一个测试 store 的文件头等核心数据，验证系统是否能自动备份 `_corrupt_{timestamp}`，并重新初始化空库进行后续的任务补偿。
- [ ] **存盘完整性:** 正常关闭后端，检查日志中是否有 `TriviumDB 磁盘同步完成` 的打印以保证退出前数据持久化无损。

---

## 5. 性能与生命周期回归 (Resource & Lifecycle Level)

- [ ] **统一 Flush 策略执行:** 确认批量导入、批量运维动作完成后是否均有显式调用 `flush()`。核查主应用 Shutdown 时是否触发全局的统一下刷动作。
- [ ] **自动压缩清理 (Auto Compaction):** 验证后台 compaction 任务是否在配置周期（如 `interval_secs=300`）后正确触发并成功执行。
- [ ] **并发检索线程安全:** 执行大并发检索（例如 10+ 线程同时并发检索）时，观察 `thread_name_prefix="trivium"` 线程池的状态、资源使用和延迟情况，确认不宕机且读写安全。

---

> **一句话总结**：
> TriviumDB 已从初期的兼容适配进入稳定性护航阶段。后续每次版本发布或重构，均需以此校验清单为准绳，确保补偿、生命周期与持久化的安全无虞。

---

*最后更新日期: 2026-04-13*
*维护者: Carola*
