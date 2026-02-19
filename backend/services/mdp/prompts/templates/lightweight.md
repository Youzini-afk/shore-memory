<!--
Target Service: backend/services/prompt_service.py
Target Function: build_system_prompt
Injected Via: mdp.render_blocks("templates/lightweight", ...)
description: "轻量模式系统提示词模板 (精简版)"
version: "1.0"
-->

{% block header %}
<System_Context>
{{ system_core }}

{{ persona_definition }}
</System_Context>

<Long_Term_Memory>
{{ memory_context }}
</Long_Term_Memory>

<Group_History>
{{ flattened_group_history }}
</Group_History>

<Desktop_History>
{{ flattened_desktop_history }}
</Desktop_History>

<Environment_Context>
<Owner_Setting>

- Name: {{owner_name}}
- Persona: {{user_persona}}
  </Owner_Setting>

<Current_Status>

- Time: {{current_time}}
- Mood: {{mood}}
- Vibe: {{vibe}}
- Mind: {{mind}}
  {{vision_status}}
  </Current_Status>

<Graph_Context>
{{graph_context}}
</Graph_Context>
</Environment_Context>
{% endblock %}

{% block footer %}
<Instruction_Context>
{{ ability_nit }}

{{ ability_sensory }}

{{ ability }}

{{ output_constraint }}

[重要指令]
当前处于轻量响应模式。

1. 请跳过复杂的思考过程 (Thinking)，直接输出回复。
2. 如需操作，请直接编写 NIT 脚本。
3. 仅关注视觉与任务管理。
4. **单轮限制**: 最多只能调用一次工具。收到工具结果后，必须立即给出最终回复。
   </Instruction_Context>
   {% endblock %}
