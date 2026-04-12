# PeroCore 代码注释规范与术语对照表

> **版本**：1.1.0 · **更新时间**：2026-04-13
> **适用范围**：PeroCore 项目所有模块的代码注释（Python / TypeScript / Vue）
> **不适用范围**：外部插件内部注释、第三方库源码

---

## 目录

1. [基本原则](#1-基本原则)
2. [术语对照表](#2-术语对照表)
3. [注释清理示例](#3-注释清理示例)

---

## 1. 基本原则

PeroCore 项目代码注释的统一化目标，是让任何开发者都能快速理解业务意图，而不是重复描述代码的执行细节。

| # | 原则 | 说明 |
|---|------|------|
| 1 | **功能性优先** | 注释应解释代码「做什么」（What）和「为什么这么做」（Why），而不是「怎么做」（How），除非逻辑极为复杂 |
| 2 | **简洁明了** | 去除冗余的思考过程、已尝试的方案记录或调试临时笔记 |
| 3 | **中文为主** | 业务逻辑注释统一使用中文 |
| 4 | **保留术语** | 专业术语、专有名词、第三方库名称保留英文原文，不强制翻译 |
| 5 | **增量清理** | 逐步替换旧的冗长注释，不要求一次性全部修改 |

---

## 2. 术语对照表

在注释中，以下术语建议保留英文原文或使用约定的中文译名：

| 英文术语 | 建议中文译名 / 用法 | 备注 |
| :--------------- | :---------------- | :------------------------------- |
| **Token** | Token / 词元 | LLM 输入输出的基本单位 |
| **Embedding** | Embedding / 向量 | 文本的向量化表示 |
| **Prompt** | Prompt / 提示词 | LLM 的输入指令 |
| **Agent** | Agent / 智能体 | 具有自主能力的执行单元 |
| **Vector Store** | 向量库 | 存储 Embedding 的数据库 |
| **IPC** | IPC | 进程间通信（Electron） |
| **Payload** | Payload / 载荷 | 数据传输的有效载荷 |
| **Hook** | Hook / 钩子 | Vue 或 React 的生命周期 / 功能钩子 |
| **Component** | 组件 | UI 组件 |
| **Middleware** | 中间件 | 请求处理管道中的组件 |
| **Buffer** | Buffer / 缓冲区 | 二进制数据缓冲区 |
| **Stream** | 流 | 数据流 |
| **Socket** | Socket / 套接字 | 网络通信端点 |
| **NapCat** | NapCat | QQ 协议适配器名称（勿译） |
| **Rust Engine** | Rust 引擎 | 核心高性能计算模块 |
| **UI/UX** | UI/UX | 用户界面 / 用户体验 |

---

## 3. 注释清理示例

### 3.1 移除思考过程注释

注释中不应保留开发过程中的推理记录或临时决策说明。

**❌ 改写前**

```python
# I was thinking about using a loop here, but then I realized that list comprehension is faster.
# Also, we need to check if x is not None because sometimes the API returns null.
# So let's try this approach first.
result = [x for x in data if x is not None]
```

**✅ 改写后**

```python
# 过滤空值，使用列表推导式优化性能
result = [x for x in data if x is not None]
```

---

### 3.2 翻译业务逻辑注释

原有英文注释应统一翻译为中文，技术术语本身可保留英文。

**❌ 改写前**

```typescript
// Check if the environment is ready.
// We need Python, Node.js and the DLLs.
// If not, return an error status.
if (!checkEnv()) {
  return 'error'
}
```

**✅ 改写后**

```typescript
// 检查运行环境（Python、Node.js、DLLs）
if (!checkEnv()) {
  return 'error'
}
```

---

### 3.3 简化代码块描述

注释只需说明代码块的核心职责，不需要描述实现细节（如布局方案选择理由）。

**❌ 改写前**

```vue
<!--
  This section is for the main dashboard layout.
  It includes the sidebar, the header, and the content area.
  I used flexbox here to make it responsive.
-->
<div class="dashboard-container">
```

**✅ 改写后**

```vue
<!-- 仪表盘主布局 -->
<div class="dashboard-container">
```

---

> **一句话总结**：
> 注释的职责是传递意图，而不是复述代码。中文优先，术语保留英文，去除噪声。

---

*本文档由 Carola 整理，适用于 PeroCore 全体开发规范。*
