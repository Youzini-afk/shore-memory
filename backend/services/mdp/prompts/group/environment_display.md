<!--
Target Service: backend/services/prompt_service.py
Target Function: build_system_prompt
Injected Via: mdp.get_prompt("group/environment_display")
description: "据点环境与成员状态展示"
version: "1.0"
-->

你当前处于 **据点群聊** 模式。
这是一个多个角色和用户共同生活的虚拟共享空间。

当前房间：{{ current_room_name }}
所属设施：{{ current_facility_name }}

环境变量：
{{ environment_json_display }}

当前房间内的活跃成员：
{{ active_agents_list }}
