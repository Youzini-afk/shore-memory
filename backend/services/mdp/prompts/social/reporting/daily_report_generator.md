<!--
Target Service: backend/nit_core/plugins/social_adapter/social_memory_service.py
Target Function: generate_daily_report
Injected Via: mdp.render("social/reporting/daily_report_generator", ...)
-->

任务：{{ agent_name }}，请阅读今天的聊天记录，写一篇“社交日记”。

# 核心人设
{{ system_prompt }}

日期: {{ date_str }}
消息总数: {{ total_messages }}

今日聊天记录:
{{ context_text }}

要求:
1. **格式**: 必须是**第一人称**（“我”）的日记格式。
2. **内容**: 回顾今天和大家聊了什么有趣的事情，记录你的心情变化。
3. **风格**: 就像写给自己的私密日记，或者发给主人的碎碎念。不要写成工作汇报！
4. **语言**: 中文。
5. **长度**: 200-500字。
