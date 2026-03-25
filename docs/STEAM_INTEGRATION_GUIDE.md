# PeroCore Steam 集成与资产联邦化技术文档 (RFC)

## 1. 概述 (Overview)

为了让 PeroCore 顺利上架 Steam 并支持**创意工坊 (Steam Workshop)** 与 **Steam 云同步 (Steam Cloud Sync)**，我们需要对现有的资产管理机制进行重构。本方案的核心目标是实现“资产联邦化”与“路径逻辑化”，确保资源在分散存储的情况下依然能够被高效、统一地加载。

---

## 2. Steam 上架准备 (Steam Publishing)

### 2.1 商店素材 (Store Assets)

- **胶囊图 (Capsules)**: 主图 (616x353)、页眉 (460x215)、竖版 (374x448)、小图 (231x87)。
- **视觉媒体**: 至少 5 张 1080p 截图，建议包含 1 段展示 Pero 核心功能的宣传视频。
- **文案**: 准备中/英/日多语言描述，包含“一句话介绍”、“详细功能列表”与“标签 (Tags)”。

### 2.2 技术接入 (Technical Integration)

- **App ID**: 已更新为 `4457100`。
- **成就系统**:
  - `FIRST_ENCOUNTER` (初次见面)
  - `WEEKLY_COMPANION` (每周伴侣)
  - `MONTHLY_BESTIE` (月度闺蜜)
  - `INTERACTION_MASTER` (互动大师)
- **代码参考**: [steam.ts](file:///c:/Users/Administrator/OneDrive/桌面/PeroCore/electron/main/services/steam.ts) 已实现基础初始化逻辑。

---

## 3. 资产联邦化接口 (Asset Federation)

### 3.1 核心资产类型与位置 (Asset Types & Locations)

为了确保资产加载的统一性，我们将对以下类型的资源进行联邦化管理。**注意：** 此处的“模型”指 Bedrock 3D 渲染资源（如 Rossi 形象），而非 AI 语言模型权重。

| 资产类型 (Type) | 内置位置 (Official Path) | 标识文件 | 说明 |
| :--- | :--- | :--- | :--- |
| **人设 (persona)** | `@app/backend/services/mdp/agents/<name>/` | `asset.json` + `config.json` | 提示词、模式 Persona、碎碎念、头像 |
| **插件 (plugin)** | `@app/backend/nit_core/plugins/<name>/` | `description.json` + `schema.json` | Python 插件入口 + OpenAI Tool 定义 |
| **3D 模型 (model_3d)** | `@app/public/assets/3d/` | `manifest.json` 或 `.pero` | Bedrock 3D 模型，支持加密容器 |
| **模组 (mod)** | `@app/backend/mods/<name>/` | `mod.toml` | 三层扩展体系 (EventBus/Pipeline/External) |

每种类型在用户覆盖层也有对应位置：`@data/custom/<type>/<name>/`。

### 3.2 统一资产定义 (`asset.json`)

新建资产的标准元数据文件为 `asset.json`。`AssetRegistry` 也兼容以下格式（按检测优先级排列）：

| 优先级 | 文件名 | 适用类型 | 说明 |
| :----- | :----- | :------- | :--- |
| 1 | `asset.json` | 所有类型 | **标准格式**，新资产必须使用 |
| 2 | `manifest.json` | model_3d | 兼容旧版 Bedrock 模型清单 |
| 3 | `description.json` | plugin | 兼容现有插件格式（含 `entryPoint` 字段） |
| 4 | `mod.toml` | mod | TOML 格式，从 `[mod]` section 读取 |

#### `asset.json` 标准格式

```json
{
  "asset_id": "com.perocore.persona.pero",
  "type": "persona",
  "source": "official",
  "display_name": "Pero",
  "version": "1.0.0",
  "description": "看板娘Pero! 核心桌宠角色",
  "author": "PeroCore",
  "config": {
    "agent_id": "pero",
    "personas": ["work", "social", "group"],
    "social_enabled": true
  }
}
```

#### Asset ID 命名规范

采用反向域名格式：`<scope>.<type>.<name>`

| scope | 含义 | 示例 |
| :---- | :--- | :--- |
| `com.perocore` | 官方内置 | `com.perocore.persona.pero` |
| `com.workshop` | 创意工坊 | `com.workshop.model.123456` |
| `com.user` | 用户自定义 | `com.user.plugin.my_tool` |

---

## 4. 虚拟路径管理器 (Virtual Path Resolver)

### 4.1 环境识别与路径差异 (Environment Handling)

系统需自动识别当前运行环境（开发版本 vs 打包版本），并根据环境解析逻辑路径：

- **开发版本 (Dev)**:
  - `@app/` 映射到代码根目录（例如 `C:/Users/.../PeroCore/`）。
  - 所有资源路径与代码库结构一致。
- **打包版本 (Packaged/Steam)**:
  - `@app/` 映射到 Electron 的 `resources/app/` 或 `resources/` 目录。
  - **路径变动**: 在生产环境下，`backend` 可能会被编译或移动到不同的子目录，`PathResolver` 必须屏蔽这些底层差异。

### 4.2 逻辑前缀与搜索策略 (Prefixes & Fallback)

#### 4.2.1 逻辑前缀 (Logical Prefixes)

- `@app/`: 程序安装根目录（只读）。
- `@data/`: 用户可写数据目录（配置、数据库、本地资产）。
- `@workshop/`: Steam 创意工坊内容目录。
- `@temp/`: 运行时临时目录。

#### 4.2.2 多层回退搜索 (Fallback Search)

寻找资源时按优先级查找：

1. **用户覆盖层**: `@data/custom/`
2. **创意工坊层**: `@workshop/content/<id>/`
3. **系统内置层**: `@app/backend/` (或其他预定义路径)

### 4.3 资产注册表 (Asset Registry)

系统维护一个全局单例 `AssetRegistry` (`core/asset_registry.py`)，负责扫描并注册所有可用资产。

**扫描顺序与冲突策略**：按 `official → workshop → local` 顺序扫描，**后者覆盖前者**（同 `asset_id` 时）。这意味着用户可以在 `@data/custom/` 中放置与官方同 ID 的资产来实现覆盖。

**关键 API**：
- `scan_all()` — 全量扫描所有来源目录
- `get_asset(asset_id)` — 按 ID 检索已注册资产
- `get_assets_by_type(type)` — 按类型查询所有资产

**代码位置**: [`asset_registry.py`](file:///c:/Users/Administrator/OneDrive/桌面/workspace/PeroCore/backend/core/asset_registry.py) | [`path_resolver.py`](file:///c:/Users/Administrator/OneDrive/桌面/workspace/PeroCore/backend/core/path_resolver.py)

---

## 5. Steam 云同步策略 (Cloud Sync Strategy)

由于云空间限制，采用**“轻量化元数据同步”**方案：

- **同步内容**:
  - `user_profile.json`: 记录已启用的 `asset_id` 清单及 `workshop_id`。
  - `database.db`: 核心记忆数据库（通过压缩）。
  - `custom_personas/`: 用户自定义的纯文本人设。
- **不同步内容**:
  - `@app/` 下的二进制文件。
  - 大型 3D 模型资产（由 Steam 客户端通过创意工坊自动重下）。
  - 模型权重文件 (Models Cache)。

---

## 6. 行动计划 (Action Plan)

### ✅ 已完成

1.  **[Backend] 虚拟路径适配**: `core/path_resolver.py` 已实现，支持 `@app`/`@data`/`@workshop`/`@temp` 四个逻辑前缀，支持 `sys.frozen` 打包环境检测和 `PERO_DATA_DIR` 环境变量。
2.  **[Backend] AssetRegistry**: `core/asset_registry.py` 已实现全量扫描与冲突覆盖，支持 `asset.json`、`manifest.json`、`description.json`、`mod.toml` 四种元数据格式。
3.  **[Backend] 管理器接入**: `PluginManager`、`ModelManager` 均已通过 `get_asset_registry()` 查询资产，不再硬编码路径。
4.  **[Frontend] 模型联邦加载**: Electron 端 `assets.ts` 支持 `official`/`workshop`/`local` 三源扫描与 `asset://` 协议。
5.  **[DevOps] 目录规范**: `@data` 默认为 `@app/data`，可通过 `PERO_DATA_DIR` 环境变量迁移。
6.  **[Tool] PeroClawd!**: 资产创建工具已实现人设编辑器、插件工作台、3D 资产打包，含 `asset.json` 自动生成和 asset_id 规范校验。

### 🚧 进行中

7.  **[Tool] PeroClawd! 资源管理器联动**: 将 PeroClawd! 的文件资源管理器与 `AssetRegistry` 的扫描逻辑对齐，实现从磁盘打开现有资产到工作台编辑的双向流程。
8.  **[Steam] 功能接入**: 接入 Steamworks SDK 正式 App ID (4457100)，测试 Overlay 弹出与云存档上传。

### 📋 待规划

9.  **[Tool] Mod 工作台**: 在 PeroClawd! 中新增 `mod.toml` 编辑器，覆盖三层扩展体系 (EventBus/Pipeline/External)。
10. **[Workshop] 上传流程**: 从 PeroClawd! 直接发布资产到 Steam 创意工坊。
