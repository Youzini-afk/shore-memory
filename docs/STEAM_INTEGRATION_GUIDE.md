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

| 资产类型 (Type)        | 物理位置 (Physical Path)    | 说明                                       |
| :--------------------- | :-------------------------- | :----------------------------------------- |
| **3D 模型 (model_3d)** | `public/assets/3d/`         | Bedrock 3D 模型文件夹 (含 `manifest.json`) |
| **人设 (persona)**     | `backend/services/mdp/`     | 包含提示词组件、Agent 专属配置等           |
| **插件 (plugin)**      | `backend/nit_core/plugins/` | 具有独立功能的 Python 插件                 |
| **模组 (mod)**         | `backend/mods/`             | 用户自定义的功能扩展                       |
| **接口 (interface)**   | `backend/interfaces/`       | 系统核心接口定义与扩展                     |

### 3.2 统一资产定义 (`asset.json`)

所有资产（无论是内置、本地还是创意工坊下载）均需在根目录包含一个 `asset.json`（或在现有 `manifest.json` 中嵌入元数据）：

```json
{
  "asset_id": "com.user.cute_pero_model",
  "type": "model_3d", // plugin | persona | model_3d | mod | interface
  "source": "workshop", // official | local | workshop
  "display_name": "超级可爱的 Pero 模型",
  "version": "1.0.2",
  "workshop_id": "123456789", // 仅当 source 为 workshop 时存在
  "config": {} // 特定资产配置
}
```

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

系统维护一个全局单例 `AssetRegistry`，负责扫描并注册所有可用资产。程序逻辑（如前端加载模型、后端加载人设）通过 `asset_id` 进行资源请求，由注册表根据虚拟路径解析出真实的物理地址。

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

## 6. 后续行动计划 (Action Plan)

1.  **[Backend] 虚拟路径适配**:
    - 实现 `core/path_resolver.py`，支持环境感知和逻辑路径转换。
    - 在 Python 端，识别 `sys.frozen` 或打包环境，动态调整 `@app` 路径。
2.  **[Backend] 资产加载重构**:
    - 将 `MDPManager` (人设)、`PluginManager` (插件) 接入 `PathResolver`。
    - 实现 `AssetRegistry` 统一管理 `backend/mods` 和 `backend/interfaces` 目录。
3.  **[Frontend] 模型加载适配**:
    - 更新 Bedrock 加载逻辑，支持从外部目录（如 `@workshop`）加载 3D 模型资产。
4.  **[DevOps] 目录规范化**:
    - 统一 `data` 目录入口，支持通过环境变量 `PERO_DATA_DIR` 迁移，为云同步做准备。
5.  **[Steam] 功能接入**:
    - 接入 Steamworks SDK 正式 App ID，测试 Overlay 弹出与云存档上传。
