<!--
Target Service: backend/services/prompt_service.py
Target Function: build_system_prompt
Injected Via: mdp.render_blocks("templates/group", ...)
description: "群聊模式专用系统提示词 (Block-based)"
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

<Desktop_History>
{{ flattened_desktop_history }}
</Desktop_History>

<Stronghold_Context>
{{ stronghold_environment }}
</Stronghold_Context>

<Room_State>
{{ current_room_state }}
</Room_State>

<Group_History>
{{ flattened_group_history }}
</Group_History>

{% endblock %}

{% block rules %}
<Interaction_Rules>
{{ ability_nit }}

{{ available_tools_desc }}

{{ group_interaction_rules }}

{{ output_constraint }}
</Interaction_Rules>
{% endblock %}
