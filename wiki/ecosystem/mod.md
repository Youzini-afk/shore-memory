# MOD组件

PeroCore 引入了全新的 MOD 系统，允许开发者通过编写 MOD 来扩展和修改系统的核心功能。与简单的插件不同，MOD 拥有更高的权限，可以替换系统的核心组件（如内存管理、Prompt构建、预处理/后处理等），实现对系统行为的深度定制。

## 1. 系统概览

PeroCore 的 MOD 系统基于 **IoC (控制反转)** 容器和 **依赖注入** 模式。核心组件通过接口定义，并在系统启动时注册到容器中。MOD 可以在系统启动阶段（Bootstrap）加载，并覆盖默认的组件实现。

## 2. 目录结构与入口

所有 MOD 存放在 `backend/mods/` 目录下。每个 MOD 是一个独立的文件夹，必须包含 `mod_init.py` 文件。

### 目录示例

```
backend/mods/
  └── my_awesome_mod/
      ├── mod_init.py       # MOD 入口文件（必须）
      ├── my_memory.py      # 自定义组件实现
      └── resources/        # 其他资源文件
```

### 入口文件 `mod_init.py`

`mod_init.py` 必须包含一个 `init()` 函数。该函数会在系统启动时被自动调用。

```python
# backend/mods/my_awesome_mod/mod_init.py

def init():
    print("[MyMod] 正在初始化...")
    # 在这里进行 Hook 注册或组件替换
```

## 3. Hook 系统 (轻量级扩展)

除了完全替换核心组件，MOD 还可以通过订阅事件来“监听”或“修改”系统行为，这种方式兼容性更好。

### 使用方法

```python
from core.event_bus import EventBus

# 定义一个 Hook 函数 (可以是 sync 或 async)
async def on_memory_save(ctx):
    content = ctx["content"]
    print(f"[监控] 正在保存记忆: {content}")

    # 修改上下文 (如果允许)
    ctx["tags"] += ",hooked"

def init():
    # 订阅事件
    EventBus.subscribe("memory.save.pre", on_memory_save)
```

### 可用事件列表

| 事件名              | 触发时机       | 上下文 (ctx)                                                   | 是否可修改            |
| :------------------ | :------------- | :------------------------------------------------------------- | :-------------------- |
| `memory.save.pre`   | 保存记忆前     | `content`, `tags`, `agent_id`, `cancel` (设为 True 可取消保存) | 是                    |
| `memory.save.post`  | 保存记忆后     | `memory` (Memory对象)                                          | 否                    |
| `prompt.build.pre`  | 构建 Prompt 前 | `variables`, `user_message`, `session`                         | 是 (可修改 variables) |
| `prompt.build.post` | 构建 Prompt 后 | `messages` (最终消息列表), `variables`                         | 是 (可修改 messages)  |

## 4. 核心组件替换 (深度定制)

开发者可以实现核心接口来替换系统组件。

### 核心接口说明

接口定义在 `backend/interfaces/core.py` 中。

| 接口名                  | 描述                                           | 默认实现               |
| :---------------------- | :--------------------------------------------- | :--------------------- |
| `IMemoryService`        | 记忆服务，负责管理长期/短期记忆的存储与检索    | `MemoryService`        |
| `IPromptManager`        | Prompt 管理器，负责构建发送给 LLM 的最终提示词 | `PromptManager`        |
| `IScorerService`        | 评分服务，用于评估记忆相关性、上下文重要性等   | `ScorerService`        |
| `IPreprocessorManager`  | 预处理器管理器，负责管理输入预处理管道         | `PreprocessorManager`  |
| `IPostprocessorManager` | 后处理器管理器，负责管理输出后处理管道         | `PostprocessorManager` |

### 如何替换组件

要替换组件，你需要：

1.  定义一个类，实现对应的接口。
2.  在 `mod_init.py` 的 `init()` 函数中，使用 `ComponentContainer.override()` 方法注册你的实现。

#### 示例：自定义 PromptManager

```python
# backend/mods/my_prompt_mod/custom_prompt.py
from interfaces.core import IPromptManager

class CustomPromptManager(IPromptManager):
    def get_system_prompt(self, agent_id: str) -> str:
        return "这是来自 MOD 的自定义系统提示词！"

    def build_prompt(self, query: str, context: dict) -> str:
        return f"MOD 处理过的 Query: {query}"
```

```python
# backend/mods/my_prompt_mod/mod_init.py
from core.component_container import ComponentContainer
from interfaces.core import IPromptManager
from .custom_prompt import CustomPromptManager

def init():
    print("[MyPromptMod] 替换 PromptManager...")
    # 注意：第二个参数是一个工厂函数（lambda），用于延迟实例化
    ComponentContainer.override(IPromptManager, lambda: CustomPromptManager())
```

### 如何获取组件

在你的 MOD 或其他代码中，如果需要使用核心组件，**不要直接实例化**，而应该从容器中获取。这确保了你获取到的是可能已经被其他 MOD 替换过的最新实例。

```python
from core.component_container import ComponentContainer
from interfaces.core import IMemoryService

def some_function():
    # 从容器中获取当前的 MemoryService 实例
    memory_service = ComponentContainer.get(IMemoryService)

    # 使用该服务
    memories = memory_service.get_memories("查询")
```

## 5. 扩展预处理器与后处理器

除了替换整个管理器，你还可以向现有的 `PreprocessorManager` 或 `PostprocessorManager` 注册新的处理器，从而插入自定义的处理逻辑。

```python
# backend/mods/my_filter_mod/mod_init.py
from core.component_container import ComponentContainer
from interfaces.core import IPreprocessorManager

class MySensitiveFilter:
    def process(self, input_text: str) -> str:
        return input_text.replace("敏感词", "***")

def init():
    # 1. 获取当前的预处理器管理器
    pm = ComponentContainer.get(IPreprocessorManager)

    # 2. 注册一个新的预处理器
    # 注意：这取决于 PreprocessorManager 的具体实现是否有 register 方法
    # 默认的 PreprocessorManager 支持 register
    pm.register(MySensitiveFilter())
    print("[MyFilterMod] 已注册敏感词过滤器")
```

## 6. 开发注意事项

1.  **接口兼容性**：自定义组件必须完整实现接口中定义的所有方法，否则运行时会报错。建议使用 `abc` 模块或类型检查工具确保兼容性。
2.  **加载顺序**：MOD 的加载顺序目前是基于文件系统的顺序（通常是字母顺序）。如果多个 MOD 试图替换同一个组件，后加载的 MOD 会覆盖先加载的。
3.  **异常处理**：`mod_init.py` 中的代码应包含适当的异常处理，避免因为一个 MOD 的错误导致整个系统无法启动。
4.  **不要修改核心代码**：尽量通过 MOD 机制来扩展功能，避免直接修改 `backend/core` 或 `backend/services` 下的代码，以便于后续升级。
