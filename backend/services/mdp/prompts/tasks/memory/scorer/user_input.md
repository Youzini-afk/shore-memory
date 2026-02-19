<!--
Target Service: backend/services/scorer_service.py
Target Function: process_interaction
Injected Via: mdp.render("tasks/memory/scorer/user_input", ...)
description: "评分器用户输入模板"
version: "1.0"
-->

{{ user_label }}: {{ user_content }}
AI ({{ agent_name }}): {{ assistant_content }}

请分析上述对话并生成记忆摘要。
注意：

1. 如果是【系统事件】触发的对话，请在摘要中明确指出是“系统提醒”或“{{ agent_name }}主动观察到”，而不是“{{user}}说”。
2. 即使是系统触发，重点关注{{user}}的后续反应（如果有）或 {{ agent_name }} 的行为逻辑。
