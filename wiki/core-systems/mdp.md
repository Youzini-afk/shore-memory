# MDP 系统 (Modular Dynamic Prompt)

MDP (Modular Dynamic Prompt) 是 PeroCore 的核心提示词管理系统，采用了**模块化**和**动态渲染**的设计理念。

## 1. 核心设计理念

1.  **模块化 (Modularity)**: 将庞大的 System Prompt 拆解为细粒度的组件（如 `rules`, `abilities`, `personas`），通过组合构建最终提示词。
2.  **动态性 (Dynamism)**: 支持运行时根据上下文（如当前时间、用户状态、Agent 记忆）动态注入变量。
3.  **继承与覆盖 (Inheritance & Override)**: 支持基于 Agent 身份的差异化配置，子 Agent 可以继承通用模板并覆盖特定组件。
4.  **递归渲染 (Recursive Rendering)**: 支持多层嵌套的变量引用，实现复杂的提示词逻辑。

## 2. 系统架构

<MDPGraph />

## 3. 目录结构

MDP 的源码位于 `backend/services/mdp`，其核心目录结构如下：

```markdown
backend/services/mdp/
├── manager.py # 核心管理器 (MDPManager)
├── prompts/ # 通用提示词仓库
│ ├── templates/ # 顶层模板 (如 system.md)
│ ├── components/ # 可复用组件
│ │ ├── rules/ # 核心规则
│ │ ├── abilities/ # 能力描述 (如 vision, voice)
│ │ └── ...
│ └── tasks/ # 特定任务提示词
└── agents/ # Agent 专属配置
├── pero/ # Pero 的专属覆盖
└── nana/ # Nana 的专属覆盖
```

## 4. 核心功能详解

### 4.1 模板与组件 (Templates & Components)

MDP 使用 **Jinja2** 作为模板引擎。所有的提示词文件（`.md`）都可以看作是一个组件。

例如，顶层模板 `templates/system.md` 可能长这样：

```markdown
# 系统规则

{{ system_core }}

# 人设定义

{{ persona_definition }}

# 当前状态

现实时间: {{ current_time }}
```

`MDPManager` 会自动在 `prompts/` 目录下查找 `system_core` 和 `persona_definition` 对应的文件，并将它们的内容填充进来。

### 4.2 Agent 覆盖机制 (Agent Overrides)

这是 MDP 最强大的特性之一。当渲染一个名为 `persona_definition` 的组件时，MDP 会根据传入的 `agent_name` 进行查找：

1.  **优先查找**: `agents/{agent_name}/persona_definition.md`
2.  **回退查找**: `prompts/components/personas/persona_definition.md` (如果路径匹配)

这意味着，你可以为 "Pero" 和 "Nana" 等不同的角色，编写完全不同的 `persona_definition`，但在代码中只需要调用同一个模板，系统会自动根据当前 Agent 加载对应的人设。

### 4.3 递归渲染 (Recursive Rendering)

MDP 支持高达 5 层的递归渲染。这允许你在组件中引用其他组件，或者在变量中包含模板语法。

**示例**:

- `templates/system.md` 包含 `{{ output_constraint }}`
- `components/output/output_constraint.md` 包含 `{{ json_format_instruction }}`
- 最终渲染时，会由内而外全部展开。

### 4.4 元数据 (Frontmatter)

每个 MDP 文件都支持 YAML Frontmatter，用于定义元数据：

```markdown
---
description: '核心系统安全协议'
version: '1.0'
---

# 实际内容...
```

### 4.5 Block 渲染机制 (Header/Footer Split)

为了应对长上下文（Long Context）场景，MDP 支持将 System Prompt 拆分为 `header` 和 `footer` 两个部分，形成 **"指令 - 上下文 - 约束"** 的三明治结构。

**为什么需要这个？**
当记忆片段 + 对话历史非常长时，模型可能会遗忘最开始的指令（注意力溃散）。通过 Block 机制，我们可以将核心指令放在头部，将输出格式约束和工具定义放在尾部，确保模型始终遵循规则。

**定义方式**:
在模板中使用 Jinja2 的 `{% block %}` 语法：

```markdown
{% block header %}

# 核心指令

你是一个...
{{ system_core }}
{% endblock %}

{% block footer %}

# 输出约束

请使用 JSON 格式...
{{ output_constraint }}
{% endblock %}
```

**渲染方式**:
使用 `mdp.render_blocks()` 而不是 `mdp.render()`：

```python
blocks = mdp.render_blocks("templates/system", context)
# blocks = {"header": "...", "footer": "..."}

# 业务层组装
final_prompt = f"{blocks['header']}\n\n{rag_context}\n\n{blocks['footer']}"
```

## 5. 最佳实践

- **保持组件原子化**: 每个组件应该只做一件事（例如只描述视觉能力，或只描述输出格式）。
- **使用相对路径**: 在引用组件时，尽量使用清晰的命名规范。
- **善用 Agent 目录**: 不要直接修改通用组件来实现个性化，应该在 `agents/` 目录下编写不同角色的人设。
- **版本控制**: 在提示词.MD文档的中的头部维护元数据注释，便于追踪 Prompt 的演进。
