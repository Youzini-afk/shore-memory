<!--
Target Service: backend/services/prompt_service.py
Target Function: build_system_prompt
Injected Via: mdp.render_blocks("templates/system", ...)
description: "协调所有组件的主系统提示词模板 (Block-based)"
version: "3.0"
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
- 姓名: {{owner_name}}
- 设定: {{user_persona}}
</Owner_Setting>

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

<Current_Status>
- 当前时间: {{current_time}}
- 心情: {{mood}}
- 氛围: {{vibe}}
- 心理活动: {{mind}}
{{vision_status}}
</Current_Status>

</Instruction_Context>
{% endblock %}