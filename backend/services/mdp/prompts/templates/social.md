<!--
Target Service: backend/services/prompt_service.py
Target Function: build_system_prompt (when source=social)
Injected Via: mdp.render("templates/social", ...)
description: "社交模式专用系统提示词"
version: "1.1"
-->

{% block header %}
# 系统规则
{{ system_core }}

# 人设定义
{{ social_instructions }}

# 上下文
<User Context>
{{ xml_context }}
</User Context>
{% endblock %}

{% block footer %}

{{ xml_guide }}

# 输出要求
{{ instruction_prompt }}
{% endblock %}