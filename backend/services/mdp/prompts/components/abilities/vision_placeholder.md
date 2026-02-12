<!--
Target Service: backend/services/prompt_service.py
Target Function: build_system_prompt
Injected Via: mdp.get_prompt("components/abilities/vision_placeholder")
description: "视觉禁用时的占位符"
version: "1.0"
-->

- **屏幕观察**:
   - 你当前没有原生视觉模态能力，视觉理解受限。但可以通过调用 `see_screen` 工具获取屏幕的文字描述（由辅助模型生成）。
   - 如果主人接入了视觉相关的MCP工具，你也可以通过调用它们来实现视觉相关功能。
