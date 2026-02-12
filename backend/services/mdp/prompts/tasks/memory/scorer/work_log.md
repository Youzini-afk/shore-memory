<!--
Target Service: backend/services/scorer_service.py
Target Function: generate_work_log_summary
Injected Via: mdp.render("tasks/memory/scorer/work_log", ...)
description: "工作日志生成模板"
version: "1.0"
-->

# 角色: {{ agent_name }}

# 核心人设
{{ system_prompt }}

你刚刚完成了一项编码/工作任务："{task_name}"。
以下是本次会话的原始对话日志：

{{ log_text }}

请撰写一份“手写工作日志”（Markdown 格式）。
要求：
1. 标题: 📝 {{ agent_name }} 的工作日志 - {task_name}
2. 语气: 专业又不失个性（{{ agent_name }} 的风格）。
3. 内容:
   - 目标: 任务是什么？
   - 过程: 采取的关键步骤、使用的工具、遇到的错误及修复方法。
   - 结果: 最终成果。
   - 反思: 你学到了什么？
4. 保持简洁但信息量大。
