<!--
Target Service: backend/services/prompt_service.py
Target Function: build_system_prompt (when source=social)
Injected Via: mdp.render("templates/social", ...)
description: "社交模式专用系统提示词"
version: "1.1"
-->

{% block header %}
<System_Context>
{{ system_core }}

{{ social_instructions }}
</System_Context>

<Context>
{{ xml_context }}
</Context>

{% endblock %}

{% block footer %}
<Instruction_Context>
{{ xml_guide }}

{{ instruction_prompt }}
</Instruction_Context>
{% endblock %}
