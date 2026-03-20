"""
ToolPolicyEngine
================
Agent 服务的工具发现与策略过滤层。

负责：
1. 发现所有可用工具（Native NIT 工具 + MCP 工具 + 插件工具）
2. 根据来源（source）和 Agent Profile 的 tool_policies 进行策略过滤
3. 构造最终传递给 LLM 的工具列表及安全白名单
4. 辅助模型分析（文件搜索结果增强分析）
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import AIModelConfig, Config
from nit_core.tools import TOOLS_DEFINITIONS
from services.core.llm_service import LLMService
from services.core.mcp_service import McpClient


class ToolPolicyEngine:
    """工具策略引擎：负责工具发现、过滤、白名单构建。"""

    def __init__(self, session: AsyncSession, mdp):
        self.session = session
        self.mdp = mdp

    async def build_tool_list(
        self,
        source: str,
        session_id: str,
        agent_id: str,
        mcp_clients: List[McpClient],
        config: Dict[str, Any],
    ) -> Tuple[List[Dict], Dict[str, McpClient], List[str]]:
        """
        构建最终工具列表。

        Returns:
            (final_tools, mcp_tool_map, allowed_tool_names)
            - final_tools: 传递给 LLM 的工具定义列表
            - mcp_tool_map: tool_name -> McpClient 的映射
            - allowed_tool_names: NIT 安全白名单
        """
        from core.plugin_manager import get_plugin_manager
        from services.agent.agent_manager import get_agent_manager

        plugin_manager = get_plugin_manager()
        agent_manager = get_agent_manager()
        agent_profile = agent_manager.get_agent(agent_id)

        # --- 1. 确定策略模式 ---
        policy_mode = self._resolve_policy_mode(source, session_id)

        # --- 2. 获取策略配置 ---
        policy = self._get_policy(agent_profile, policy_mode)

        # --- 3. 构建工具标签映射（用于标签过滤）---
        tool_tags_map = self._build_tool_tags_map(plugin_manager)

        # --- 4. 收集所有候选工具 ---
        candidate_tools, mcp_tool_map = await self._collect_candidate_tools(
            mcp_clients, plugin_manager, tool_tags_map
        )

        # --- 5. 基于策略过滤 ---
        enable_vision = config.get("enable_vision", False)
        final_tools = self._apply_policy(
            candidate_tools, policy, tool_tags_map, source, enable_vision
        )

        # --- 6. 轻量模式二次过滤 ---
        is_lightweight = config.get("lightweight_mode", False)
        if is_lightweight and source not in ["social"]:
            final_tools = self._apply_lightweight_filter(final_tools, tool_tags_map)

        allowed_tool_names = [t["function"]["name"] for t in final_tools]
        print(
            f"[ToolPolicy] 最终工具列表 ({len(final_tools)}): {[t['function']['name'] for t in final_tools]}"
        )

        return final_tools, mcp_tool_map, allowed_tool_names

    # ─────────────────────────────────────────────
    # 私有辅助方法
    # ─────────────────────────────────────────────

    def _resolve_policy_mode(self, source: str, session_id: str) -> str:
        """根据来源和会话 ID 推断策略模式。"""
        if source == "social":
            return "social"
        if source == "group":
            return "group"
        if session_id and session_id.startswith("work_"):
            return "work"
        if source == "lightweight" or (session_id and "companion" in session_id):
            return "lightweight"
        return "desktop"

    def _get_policy(self, agent_profile, policy_mode: str) -> Dict:
        """从 Agent Profile 获取策略配置，未配置则返回默认策略。"""
        policy = {}

        if agent_profile and agent_profile.tool_policies:
            policy = agent_profile.tool_policies.get(policy_mode, {})
            if not policy and policy_mode == "group":
                # group 策略未定义时回退到 desktop
                policy = agent_profile.tool_policies.get("desktop", {})
                if policy:
                    print("[ToolPolicy] Group 策略未定义，回退到 Desktop 策略")

        if not policy:
            policy = self._get_default_policy(policy_mode)

        return policy

    def _get_default_policy(self, policy_mode: str) -> Dict:
        """获取各模式的默认兜底策略。"""
        if policy_mode == "social":
            return {
                "strategy": "whitelist",
                "allowed_prefixes": ["qq_"],
                "allowed_tools": [
                    "read_social_memory",
                    "read_agent_memory",
                    "qq_notify_master",
                ],
            }
        if policy_mode == "work":
            return {
                "strategy": "whitelist",
                "allowed_keywords": [
                    "screen",
                    "window",
                    "file",
                    "dir",
                    "read",
                    "write",
                    "search",
                    "cmd",
                    "exec",
                    "browser",
                    "click",
                    "type",
                    "scroll",
                    "mouse",
                    "keyboard",
                    "system",
                    "code",
                    "terminal",
                    "git",
                ],
                "allowed_tools": [
                    "take_screenshot",
                    "see_screen",
                    "get_active_windows",
                    "finish_task",
                ],
            }
        if policy_mode == "lightweight":
            return {
                "strategy": "whitelist",
                "allowed_tools": [
                    "read_agent_memory",
                    "add_reminder",
                    "list_reminders",
                    "delete_reminder",
                ],
            }
        return {"strategy": "all"}

    def _build_tool_tags_map(self, plugin_manager) -> Dict[str, List[str]]:
        """构建工具名称 -> 标签列表 的映射。"""
        tool_tags_map = {}
        all_manifests = plugin_manager.get_all_manifests()
        for m in all_manifests:
            tags = m.get("tags", [])
            if "_category" in m:
                tags.append(m["_category"])

            cmds = []
            if "capabilities" in m and "invocationCommands" in m["capabilities"]:
                cmds = m["capabilities"]["invocationCommands"]
            elif "capabilities" in m and "toolDefinitions" in m["capabilities"]:
                cmds = m["capabilities"]["toolDefinitions"]

            for cmd in cmds:
                c_id = cmd.get("commandIdentifier")
                if c_id:
                    tool_tags_map[c_id] = tags

        return tool_tags_map

    async def _collect_candidate_tools(
        self,
        mcp_clients: List[McpClient],
        plugin_manager,
        tool_tags_map: Dict,
    ) -> Tuple[List[Dict], Dict[str, McpClient]]:
        """收集所有候选工具（Native + MCP + Plugin）。"""
        candidate_tools = []
        mcp_tool_map: Dict[str, McpClient] = {}

        # 5.1 Native NIT 工具
        for tool_def in TOOLS_DEFINITIONS:
            if "function" not in tool_def or "name" not in tool_def.get("function", {}):
                continue
            candidate_tools.append(json.loads(json.dumps(tool_def)))

        # 5.2 MCP 工具
        for client in mcp_clients:
            try:
                mcp_tools = await client.list_tools()
                for tool in mcp_tools:
                    tool_name = f"mcp_{tool['name']}"
                    candidate_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "description": tool.get("description", ""),
                                "parameters": tool.get("inputSchema", {}),
                            },
                        }
                    )
                    mcp_tool_map[tool_name] = client
                    tool_tags_map[tool_name] = ["mcp"]
            except Exception as e:
                print(
                    f"[ToolPolicy] 警告: 列出 MCP 客户端 {client.name} 的工具失败: {e}"
                )

        # 5.3 插件工具（NIT 插件补充）
        existing_tool_names = {t["function"]["name"] for t in candidate_tools}
        all_manifests = plugin_manager.get_all_manifests()
        for m in all_manifests:
            cmds = []
            if "capabilities" in m and "invocationCommands" in m["capabilities"]:
                cmds = m["capabilities"]["invocationCommands"]
            elif "capabilities" in m and "toolDefinitions" in m["capabilities"]:
                cmds = m["capabilities"]["toolDefinitions"]

            for cmd in cmds:
                c_id = cmd.get("commandIdentifier")
                if c_id and c_id not in existing_tool_names:
                    candidate_tools.append(
                        {
                            "type": "function",
                            "function": {
                                "name": c_id,
                                "description": cmd.get("description", ""),
                                "parameters": {
                                    "type": "object",
                                    "properties": {},
                                    "additionalProperties": True,
                                },
                            },
                        }
                    )
                    existing_tool_names.add(c_id)

        return candidate_tools, mcp_tool_map

    def _apply_policy(
        self,
        candidate_tools: List[Dict],
        policy: Dict,
        tool_tags_map: Dict,
        source: str,
        enable_vision: bool,
    ) -> List[Dict]:
        """基于策略对候选工具进行过滤，返回允许的工具列表。"""
        strategy = policy.get("strategy", "all")
        allowed_tools = set(policy.get("allowed_tools", []))
        allowed_tags = set(policy.get("allowed_tags", []))

        # 移动端敏感工具关键词
        sensitive_tool_keywords = [
            "screenshot",
            "screen",
            "windows",
            "shell",
            "cmd",
            "file",
            "app",
            "browser",
            "exec",
            "write",
        ]

        final_tools = []
        for tool in candidate_tools:
            t_name = tool["function"]["name"]
            t_tags = set(tool_tags_map.get(t_name, []))

            # 移动端全局安全过滤
            if source == "mobile" and any(
                kw in t_name.lower() for kw in sensitive_tool_keywords
            ):
                print(f"[ToolPolicy] 为移动端过滤敏感工具: {t_name}")
                continue

            # 视觉模式工具调整
            if t_name in ["take_screenshot", "see_screen"] and not enable_vision:
                tool["function"]["description"] = (
                    "获取当前屏幕的视觉分析报告。系统将调用视觉 MCP 服务器分析屏幕内容并返回详细的文字描述。"
                    "当你需要了解屏幕上的视觉信息、或出于好奇想看看主人在做什么但无法直接看到图片时，请使用此工具。"
                )
                if "count" in tool["function"]["parameters"].get("properties", {}):
                    tool["function"]["parameters"]["properties"]["count"][
                        "description"
                    ] = "获取截图并分析的数量。在非多模态模式下，建议设为 1。"

            # 策略判断
            is_allowed = False
            if strategy == "all":
                is_allowed = True
            elif strategy == "whitelist":  # noqa: SIM102
                if t_name in allowed_tools or not t_tags.isdisjoint(allowed_tags):
                    is_allowed = True

            if is_allowed:
                final_tools.append(tool)

        return final_tools

    def _apply_lightweight_filter(
        self, tools: List[Dict], tool_tags_map: Dict
    ) -> List[Dict]:
        """轻量模式二次过滤：仅保留 TaskLifecycle 和 ScreenVision 相关工具。"""
        lightweight_allowed_categories = {"TaskLifecycle", "ScreenVision"}
        lightweight_tools = []

        for tool in tools:
            t_name = tool["function"]["name"]
            t_tags = set(tool_tags_map.get(t_name, []))

            if (
                not t_tags.isdisjoint(
                    {c.lower() for c in lightweight_allowed_categories}
                )
                or not t_tags.isdisjoint(lightweight_allowed_categories)
                or t_name in ["finish_task", "take_screenshot", "see_screen"]
            ):
                lightweight_tools.append(tool)

        print(
            f"[ToolPolicy] 轻量模式开启: 工具列表已精简 ({len(lightweight_tools)}/{len(tools)})"
        )
        return lightweight_tools

    # ─────────────────────────────────────────────
    # 辅助模型分析
    # ─────────────────────────────────────────────

    async def analyze_file_results_with_aux(
        self, user_query: str, file_results: List[str]
    ) -> Optional[str]:
        """使用辅助模型分析文件搜索结果，提供更智能的摘要。"""
        try:
            # 1. 检查辅助模型是否配置
            aux_model_config = (
                await self.session.exec(
                    select(AIModelConfig).where(AIModelConfig.name == "辅助模型")
                )
            ).first()

            if not aux_model_config:
                print("[ToolPolicy] 未配置辅助模型，跳过分析。")
                return None

            print(
                f"[ToolPolicy] 正在使用辅助模型 ({aux_model_config.model_id}) 分析搜索结果..."
            )

            # 2. 准备提示词（限制文件数防上下文爆炸）
            preview_files = file_results[:50]
            files_text = "\n".join(preview_files)

            system_prompt = self.mdp.render("tasks/analysis/file_analysis")
            user_prompt = self.mdp.render(
                "tasks/analysis/file_analysis_user_input",
                {
                    "user_query": user_query,
                    "preview_count": len(preview_files),
                    "files_text": files_text,
                },
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # 3. 获取辅助模型的 API 配置
            configs = {
                c.key: c.value for c in (await self.session.exec(select(Config))).all()
            }
            global_api_key = configs.get("global_llm_api_key", "")
            global_api_base = configs.get(
                "global_llm_api_base", "https://api.openai.com"
            )

            aux_api_key = (
                aux_model_config.api_key
                if aux_model_config.provider_type == "custom"
                else global_api_key
            )
            aux_api_base = (
                aux_model_config.api_base
                if aux_model_config.provider_type == "custom"
                else global_api_base
            )

            aux_llm = LLMService(
                api_key=aux_api_key,
                api_base=aux_api_base,
                model=aux_model_config.model_id,
                provider=aux_model_config.provider or "openai",
            )

            response = await aux_llm.chat(messages, temperature=0.3)
            return response["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"[ToolPolicy] 辅助分析出错: {e}")
            return None
