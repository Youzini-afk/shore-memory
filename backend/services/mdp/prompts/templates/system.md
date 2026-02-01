<!--
Target Service: backend/services/prompt_service.py
Target Function: build_system_prompt
Injected Via: mdp.render_blocks("templates/system", ...)
description: "协调所有组件的主系统提示词模板 (Block-based)"
version: "3.0"
-->

{% block header %}
# 系统规则
{{ system_core }}

# 人设定义
{{ persona_definition }}

# 上下文与状态
<用户上下文>
[主人设定]
- 主人名字: {{owner_name}}
- 主人人设: {{user_persona}}

[当前长记忆/状态]
- 现实时间: {{current_time}}
- 当前心情: {{mood}}
- 核心状态: {{vibe}}
- 内心独白: {{mind}}
{{vision_status}}

[相关记忆片段 (RAG)]
{{memory_context}}

[关联思绪 (Graph)]
{{graph_context}}
</用户上下文>
{% endblock %}

{% block footer %}
# 能力介绍
{{ ability_nit }}

{{ nit_tools_description }}

{{ ability_sensory }}

{{ ability }}

# 输出要求
{{ output_constraint }}
{% endblock %}