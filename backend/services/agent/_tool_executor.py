"""
AgentToolExecutor
=================
Agent 服务的工具调用执行层。

负责接收来自 ReAct 循环的工具调用指令，根据工具类型分发执行：
1. 特殊工具拦截：finish_task、search_files（需要 UI 注入）、take_screenshot/see_screen（多模态）
2. NIT 调度器统一执行（所有注册的 NIT 插件）
3. MCP 工具调用（外部 MCP 服务）
4. 未知工具 Fallback
5. NIT 文本模式解析执行（save_parsed_metadata）
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel.ext.asyncio.session import AsyncSession

# 移动端敏感工具关键词（统一定义，避免散布在多处）
MOBILE_SENSITIVE_KEYWORDS = [
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


class AgentToolExecutor:
    """工具调用执行器：负责将 LLM 的 Function Calling 请求路由到对应执行入口。"""

    def __init__(self, session: AsyncSession, mdp):
        self.session = session
        self.mdp = mdp

    async def execute_tool_call(
        self,
        tool_call: Dict,
        source: str,
        config: Dict[str, Any],
        mcp_tool_map: Dict,
        mcp_clients: List,
        on_status,
        final_messages: List[Dict],
        tool_policy_engine=None,  # 可选：用于 search_files 辅助模型分析
        user_message: str = "",
    ) -> Tuple[str, bool, Optional[str]]:
        """
        执行单次工具调用。

        Returns:
            (function_response, should_terminate, sse_payload_or_none)
            - function_response: 工具返回内容字符串
            - should_terminate: True 表示应终止 ReAct 循环
            - sse_payload: 需要推送给前端的 SSE 数据（如状态更新）
        """
        function_name = tool_call["function"]["name"]
        args_str = tool_call["function"]["arguments"] or "{}"

        # --- 解析参数 ---
        function_args, arg_error = self._parse_args(args_str, function_name)
        if arg_error:
            return f"错误: {arg_error}。请确保参数是有效的 JSON。", False, None

        # --- 移动端安全门控（硬拦截）---
        if source == "mobile" and any(
            kw in function_name.lower() for kw in MOBILE_SENSITIVE_KEYWORDS
        ):
            print(f"[🛡️ ToolExecutor] 已拦截移动端对敏感工具 '{function_name}' 的执行。")
            return (
                f"错误：权限拒绝。出于安全原因，工具 '{function_name}' 被限制远程/移动连接使用。",
                False,
                None,
            )

        # --- 分发执行 ---

        # 1. 完成任务
        if function_name == "finish_task":
            return await self._handle_finish_task(function_args)

        # 2. search_files（需要 UI 注入 + 辅助模型分析）
        if function_name == "search_files":
            return await self._handle_search_files(
                function_args, on_status, tool_policy_engine, user_message
            )

        # 3. take_screenshot / see_screen（多模态处理）
        if function_name in ("take_screenshot", "see_screen"):
            return await self._handle_screenshot(
                function_name, function_args, config, on_status, final_messages
            )

        # 4. NIT 调度器统一执行
        from nit_core.dispatcher import get_dispatcher

        nit_dispatcher = get_dispatcher()
        normalized_name = nit_dispatcher.parser.normalize_key(function_name)

        if normalized_name in nit_dispatcher.list_plugins():
            return await self._handle_nit_tool(
                function_name, function_args, nit_dispatcher, on_status
            )

        # 5. MCP 工具
        if function_name.startswith("mcp_") and mcp_tool_map:
            return await self._handle_mcp_tool(
                function_name, function_args, mcp_tool_map, on_status
            )

        # 6. 回退
        print(f"[ToolExecutor] 未找到工具 {function_name}。")
        return f"Error: Tool '{function_name}' not found or not supported.", False, None

    # ─────────────────────────────────────────────
    # NIT 文本模式解析执行
    # ─────────────────────────────────────────────

    async def save_parsed_metadata(
        self,
        text: str,
        source: str,
        mcp_clients: Optional[List] = None,
        execute_nit: bool = True,
        expected_nit_id: str = None,
        allowed_tools: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """解析并执行 LLM 响应文本中的 NIT 工具调用指令。"""
        try:
            nit_results = []
            if execute_nit:
                # 移动端 NIT 脚本硬隔离
                if source == "mobile":
                    sensitive_keywords = MOBILE_SENSITIVE_KEYWORDS
                    if "<nit" in text and any(
                        kw in text.lower() for kw in sensitive_keywords
                    ):
                        print(
                            f"[🛡️ ToolExecutor] 已拦截来自移动端的 NIT 脚本执行: {text[:50]}..."
                        )
                        return [
                            {
                                "status": "error",
                                "message": "权限拒绝：NIT 脚本包含移动端受限的工具。",
                            }
                        ]

                from nit_core.dispatcher import get_dispatcher

                nit_dispatcher = get_dispatcher()

                # 准备 MCP 插件（若存在）
                extra_plugins = None
                if mcp_clients:
                    try:
                        from nit_core.bridge import NITBridge

                        bridge = NITBridge(nit_dispatcher)
                        extra_plugins = await bridge.get_mcp_plugins(mcp_clients)
                    except Exception as e:
                        print(f"[ToolExecutor] 将 MCP 工具桥接到 NIT 失败: {e}")

                nit_results = await nit_dispatcher.dispatch(
                    text,
                    extra_plugins=extra_plugins,
                    expected_nit_id=expected_nit_id,
                    allowed_tools=allowed_tools,
                )

                if nit_results:
                    print(f"[ToolExecutor] 执行了 {len(nit_results)} 个 NIT 工具调用")

            await self.session.commit()
            return nit_results
        except Exception as e:
            await self.session.rollback()
            print(f"[ToolExecutor] save_parsed_metadata 出错: {e}")
            return []

    # ─────────────────────────────────────────────
    # 私有处理方法
    # ─────────────────────────────────────────────

    def _parse_args(
        self, args_str: str, function_name: str
    ) -> Tuple[Dict, Optional[str]]:
        """解析工具参数 JSON，返回 (args_dict, error_or_None)。"""
        try:
            return json.loads(args_str), None
        except json.JSONDecodeError as e:
            try:
                args, _ = json.JSONDecoder().raw_decode(args_str)
                print(f"[ToolExecutor] 从额外数据错误中恢复。解析结果: {args}")
                return args, None
            except Exception:
                print(f"[ToolExecutor] 解析工具参数失败: {args_str}, 错误: {e}")
                return {}, f"Failed to parse arguments: {str(e)}"
        except Exception as e:
            print(f"[ToolExecutor] 解析工具参数失败: {args_str}, 错误: {e}")
            return {}, f"Failed to parse arguments: {str(e)}"

    async def _handle_finish_task(self, function_args: Dict) -> Tuple[str, bool, None]:
        """处理 finish_task 工具：终止 ReAct 循环。"""
        print(
            f"[ToolExecutor] finish_task 被调用。状态: {function_args.get('status', 'success')}"
        )
        return "任务已完成。终止循环。", True, None

    async def _handle_search_files(
        self,
        function_args: Dict,
        on_status,
        tool_policy_engine,
        user_message: str,
    ) -> Tuple[str, bool, None]:
        """处理 search_files 工具：拦截结果注入 UI，可选触发辅助模型分析。"""
        from nit_core.tools import TOOLS_MAPPING

        print("[ToolExecutor] 拦截 search_files 调用以进行 UI 注入...")
        if on_status:
            await on_status("thinking", "正在处理大数据量任务...")

        try:
            func = TOOLS_MAPPING["search_files"]
            raw_data = (
                await func(**function_args)
                if asyncio.iscoroutinefunction(func)
                else func(**function_args)
            )

            # 辅助模型分析
            aux_analysis = None
            if tool_policy_engine:
                try:
                    data_list = json.loads(raw_data)
                    if isinstance(data_list, list) and len(data_list) > 0:
                        if on_status:
                            await on_status("thinking", "正在分析搜索结果...")
                        aux_analysis = (
                            await tool_policy_engine.analyze_file_results_with_aux(
                                user_message, data_list
                            )
                        )
                except Exception as e:
                    print(f"[ToolExecutor] 触发辅助分析失败: {e}")

            try:
                data_list = json.loads(raw_data)
                count = len(data_list) if isinstance(data_list, list) else 1
            except Exception:
                count = "若干"

            aux_msg = f"\n\n[辅助模型分析结果]:\n{aux_analysis}" if aux_analysis else ""
            function_response = (
                f"System: 已成功处理。获取到 {count} 条数据，UI 列表已在后台准备就绪。{aux_msg}\n"
                "请结合辅助模型的分析结果（如果有），告知用户你已经处理完成，并可以简要复述分析结论。"
            )
            print(
                f"[ToolExecutor] search_files 已拦截。{count} 项已从 LLM 上下文中隐藏。"
            )
        except Exception as e:
            function_response = f"拦截工具执行期间出错: {e}"

        return function_response, False, None

    async def _handle_screenshot(
        self,
        function_name: str,
        function_args: Dict,
        config: Dict,
        on_status,
        final_messages: List[Dict],
    ) -> Tuple[str, bool, None]:
        """处理截图类工具：非多模态走 MCP 视觉分析，多模态注入图片。"""
        print(f"[ToolExecutor] 调用工具: {function_name}")
        enable_vision = config.get("enable_vision", False)

        if not enable_vision:
            # 非多模态：调用 MCP 视觉分析（回退到文字描述）
            if on_status:
                await on_status("thinking", "正在通过 MCP 分析屏幕内容...")
            # 注意：_analyze_screen_with_mcp 暂保留在 AgentService 中，
            # 此处返回占位符，实际调用由 ReActLoop 协调
            return (
                "[Vision] 请 AgentService._analyze_screen_with_mcp() 处理。",
                False,
                None,
            )

        # 多模态模式：注入截图到上下文
        if on_status:
            await on_status("thinking", "正在查看截图池...")
        try:
            from services.perception.screenshot_service import screenshot_manager

            count = function_args.get("count", 1)
            if not isinstance(count, int):
                count = 1
            count = max(1, min(10, count))

            latest_shot = screenshot_manager.capture()
            final_screenshots = []

            if count == 1:
                if latest_shot:
                    final_screenshots = [latest_shot]
            else:
                recent_screenshots = screenshot_manager.get_recent(count, max_age=15)
                final_screenshots = recent_screenshots

            if not final_screenshots:
                return "❌ 无法获取最新截图（可能截图失败）。", False, None

            # 将截图注入到 final_messages（副作用）
            content = [
                {
                    "type": "text",
                    "text": f"系统提示：以下是最近捕获的 {len(final_screenshots)} 张屏幕截图（按时间顺序排列）：",
                }
            ]
            for i, shot in enumerate(final_screenshots):
                content.append(
                    {
                        "type": "text",
                        "text": f"--- 截图 {i + 1} (捕获时间: {shot['time_str']}) ---",
                    }
                )
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{shot['base64']}"},
                    }
                )

            final_messages.append({"role": "user", "content": content})
            print(
                f"[ToolExecutor] {len(final_screenshots)} 张截图已注入上下文。(最新: {final_screenshots[-1]['time_str']})"
            )

            return (
                f"已成功获取并发送了最近的 {len(final_screenshots)} 张截图。请查看最新的消息中的图片进行分析。",
                False,
                None,
            )
        except Exception as e:
            return f"截图工具执行出错: {e}", False, None

    async def _handle_nit_tool(
        self,
        function_name: str,
        function_args: Dict,
        nit_dispatcher,
        on_status,
    ) -> Tuple[str, bool, Optional[str]]:
        """通过 NIT 调度器执行工具。"""
        print(f"[ToolExecutor] 将工具 {function_name} 委托给 NITDispatcher...")
        if on_status:
            await on_status("thinking", f"正在调用能力: {function_name}...")

        sse_payload = None
        try:
            result = await nit_dispatcher._execute_plugin(function_name, function_args)
            function_response = str(result)
            print(f"[ToolExecutor] NIT 工具 {function_name} 执行成功。")

            # 实时状态同步：特殊工具触发 SSE 推送
            if function_name in [
                "update_character_status",
                "update_status",
                "set_status",
                "finish_task",
            ]:
                sse_payload = self._try_extract_sse_payload(result)

            # 结果截断保护
            if len(function_response) > 10000:
                function_response = (
                    function_response[:10000] + "\n... (result truncated)"
                )

        except Exception as e:
            print(f"[ToolExecutor] NIT 工具 {function_name} 失败: {e}")
            function_response = f"执行工具出错: {e}"

        return function_response, False, sse_payload

    async def _handle_mcp_tool(
        self,
        function_name: str,
        function_args: Dict,
        mcp_tool_map: Dict,
        on_status,
    ) -> Tuple[str, bool, None]:
        """执行 MCP 工具调用。"""
        import time

        real_tool_name = function_name[4:]  # 去掉 "mcp_" 前缀
        client = mcp_tool_map.get(function_name)

        if not client:
            print(f"[ToolExecutor] 映射中未找到 MCP 工具 {function_name}")
            return f"错误: 未找到 MCP 工具 {function_name}。", False, None

        print(f"[ToolExecutor] 调用 MCP 工具: {real_tool_name} (在 {client.name} 上)")
        if on_status:
            await on_status(
                "thinking", f"正在调用插件 ({client.name}): {real_tool_name}..."
            )

        start_time = time.time()
        try:
            mcp_response = await client.call_tool(real_tool_name, function_args)
            duration = time.time() - start_time
            print(f"[ToolExecutor] MCP 工具 {real_tool_name} 执行耗时 {duration:.2f}s")
        except Exception as e:
            print(f"[ToolExecutor] MCP 工具 {real_tool_name} 失败: {e}")
            mcp_response = f"Error: {e}"

        return str(mcp_response), False, None

    def _try_extract_sse_payload(self, result: Any) -> Optional[str]:
        """尝试从工具返回值中提取状态触发器，构造 SSE payload。"""
        try:
            if isinstance(result, dict) or (
                isinstance(result, str) and result.strip().startswith("{")
            ):
                triggers = (
                    result if isinstance(result, dict) else json.loads(str(result))
                )
                return json.dumps({"triggers": triggers}, ensure_ascii=False)
        except Exception:
            pass
        return None
