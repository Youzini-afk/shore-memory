# 代码注释清理任务清单 (Cleanup To-Do List)

记录项目代码注释清理和本地化工作的进度。

## Phase 1: 后端核心服务 (Backend Services)
- [x] `backend/services/agent_service.py` - 简化 Agent 执行逻辑注释
- [x] `backend/services/memory_service.py` - 简化内存检索与 Rust 引擎集成注释
- [x] `backend/services/llm_service.py` - 修复 URL 构建逻辑，简化错误处理注释
- [x] `backend/services/preprocessor/implementations.py` - 简化 NIT 安全检查注释

## Phase 2: 插件与适配层 (Plugins & Adapters)
- [x] `backend/nit_core/plugins/social_adapter/social_service.py` - 简化社交服务启动逻辑
- [x] `backend/nit_core/plugins/social_adapter/social_memory_service.py` - 简化向量服务与内存交互
- [x] `backend/nit_core/dispatcher.py` - 简化插件分发器逻辑

## Phase 3: Electron 主进程 (Electron Main)
- [x] `electron/main/services/diagnostics.ts` - 简化环境诊断逻辑
- [x] `electron/main/services/gateway.ts` - 简化网关服务逻辑
- [x] `electron/main/services/napcat.ts` - 简化 NapCat 启动与管理
- [x] `electron/main/index.ts` - 简化主窗口创建与生命周期管理
- [x] `electron/main/services/python.ts` - 简化 Python 后端进程管理
- [x] `electron/main/windows/manager.ts` - 简化窗口管理器逻辑

## Phase 4: 前端视图与组件 (Frontend)
- [x] `src/views/DashboardView.vue` - 简化仪表盘逻辑
- [x] `src/views/LauncherView.vue` - 简化启动器逻辑与模板注释
- [x] `src/views/MainWindow.vue` - 简化主窗口逻辑
- [x] `src/views/Pet3DView.vue` - 简化 3D 宠物视图逻辑
- [x] `src/views/WorkModeView.vue` - 简化工作模式逻辑
- [x] `src/views/ChatModeView.vue` - 简化聊天模式逻辑
- [x] `src/components/avatar/BedrockAvatar.vue` - 简化 Bedrock 模型加载逻辑
- [x] `src/components/chat/ChatInterface.vue` - 简化聊天界面逻辑
- [x] `src/components/ide/TerminalManager.vue` - 简化终端管理器 UI 逻辑
- [x] `src/components/ide/FileExplorer.vue` - 简化文件浏览器逻辑
- [x] `src/components/ui/NotificationManager.vue` - 简化通知管理逻辑
- [x] `src/main.js` - 简化入口文件注释
- [x] `src/router.js` - 简化路由配置注释
- [x] `src/utils/ipcAdapter.ts` - 简化 IPC 适配器注释

## 下一步计划 (Next Steps)
- 随着开发进行，对新增代码保持此注释规范。
- 定期检查 `src/components` 下的其他次要组件。
- 检查 `backend/utils` 目录下的工具类文件。
