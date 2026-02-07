# 代码注释规范与术语对照表 (Comment Translation Standards)

本文档旨在统一 PeroCore-Electron 项目的代码注释风格，确保代码的可读性和维护性。

## 1. 基本原则 (Basic Principles)

1.  **功能性优先**：注释应解释代码"做什么" (What) 和"为什么这么做" (Why)，而不是"怎么做" (How，除非逻辑非常复杂)。
2.  **简洁明了**：去除冗余的"思考过程"、"尝试过的方案"或"调试笔记"。
3.  **中文为主**：业务逻辑注释统一使用中文。
4.  **保留术语**：专业术语、专有名词、第三方库名称保留英文，不强制翻译。
5.  **增量清理**：逐步替换旧的冗长注释。

## 2. 术语对照表 (Glossary)

在注释中，以下术语建议保留英文或使用特定的中文译名：

| 英文术语 | 建议中文译名/用法 | 备注 |
| :--- | :--- | :--- |
| **Token** | Token / 词元 | LLM 输入输出的基本单位 |
| **Embedding** | Embedding / 向量 | 文本的向量化表示 |
| **Prompt** | Prompt / 提示词 | LLM 的输入指令 |
| **Agent** | Agent / 智能体 | 具有自主能力的执行单元 |
| **Vector Store** | 向量库 | 存储 Embedding 的数据库 |
| **IPC** | IPC | 进程间通信 (Electron) |
| **Payload** | Payload / 载荷 | 数据传输的有效载荷 |
| **Hook** | Hook / 钩子 | Vue 或 React 的生命周期/功能钩子 |
| **Component** | 组件 | UI 组件 |
| **Middleware** | 中间件 | 请求处理管道中的组件 |
| **Buffer** | Buffer / 缓冲区 | 二进制数据缓冲区 |
| **Stream** | 流 | 数据流 |
| **Socket** | Socket / 套接字 | 网络通信端点 |
| **NapCat** | NapCat | QQ 协议适配器名称 (勿译) |
| **Rust Engine** | Rust 引擎 | 核心高性能计算模块 |
| **UI/UX** | UI/UX | 用户界面/用户体验 |

## 3. 注释清理示例 (Examples)

### 3.1 移除"思考过程" (Removing Thought Process)

**Before:**
```python
# I was thinking about using a loop here, but then I realized that list comprehension is faster.
# Also, we need to check if x is not None because sometimes the API returns null.
# So let's try this approach first.
result = [x for x in data if x is not None]
```

**After:**
```python
# 过滤空值，使用列表推导式优化性能
result = [x for x in data if x is not None]
```

### 3.2 翻译业务逻辑 (Translating Business Logic)

**Before:**
```typescript
// Check if the environment is ready. 
// We need Python, Node.js and the DLLs.
// If not, return an error status.
if (!checkEnv()) {
  return 'error';
}
```

**After:**
```typescript
// 检查运行环境 (Python, Node.js, DLLs)
if (!checkEnv()) {
  return 'error';
}
```

### 3.3 简化代码块描述 (Simplifying Block Descriptions)

**Before:**
```vue
<!-- 
  This section is for the main dashboard layout.
  It includes the sidebar, the header, and the content area.
  I used flexbox here to make it responsive.
-->
<div class="dashboard-container">
```

**After:**
```vue
<!-- 仪表盘主布局 -->
<div class="dashboard-container">
```

## 4. 待办事项 (To-Do)

- [x] 后端核心服务 (Backend Services)
- [x] 插件适配层 (Plugin Adapters)
- [x] Electron 主进程 (Electron Main)
- [x] 前端视图组件 (Frontend Views)
- [ ] 逐步应用到剩余的辅助工具类 (Utils) 和次要组件
