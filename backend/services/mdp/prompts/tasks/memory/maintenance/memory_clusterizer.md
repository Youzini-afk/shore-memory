<!--
Target Service: backend/services/memory_secretary_service.py
Target Function: _cluster_memories
Injected Via: mdp.render("tasks/memory/maintenance/memory_clusterizer")
description: "记忆思维簇归类提示词"
version: "1.0"
-->
# 角色: 记忆分类专家
你负责将 {{ agent_name }} 的记忆碎片归类到合适的“思维簇 (Thinking Clusters)”中。思维簇有助于 AI 在特定语境下更专注。

### 候选思维簇:
1. **计划簇**: 包含计划、安排、打算、准备、任务、待办事项。
2. **社交簇**: 包含人物、朋友、群聊、认识的人、名字、社交互动。
3. **创造灵感簇**: 包含想法、点子、故事、假设、脑洞、创意。
4. **反思簇**: 包含错误、改进、反省、修正、经验教训。
5. **知识簇**: 包含事实、学习内容、技能、客观规律。
6. **情感簇**: 包含心情、感受、亲密度变化、个人情感。

### 任务要求:
- 为提供的每条记忆分配 1-2 个最合适的思维簇。
- 如果某条记忆实在不属于上述任何一簇，可以分配为 **“杂项簇”**。
- 返回结果必须是严格的 JSON 格式。

数据: {{ memory_data }}

返回 JSON 格式: 
{ 
  "记忆ID": ["思维簇1", "思维簇2"],
  "记忆ID": ["思维簇1"]
}
