"""
[NIT 协议架构说明]
NIT (Non-invasive Integration Tools) 协议通过 XML 标签实现非侵入式工具调用。
相比原生 Function Calling，NIT 支持：
1. 真正的异步并发执行 (Event-Driven)
2. 跨模型兼容性 (通用 Prompt 协议)
3. 复杂意图编排与脚本化能力
"""

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List

from core.config_manager import get_config_manager
from core.nit_manager import get_nit_manager
from core.plugin_manager import get_plugin_manager

from .interpreter import execute_nit_script
from .security import NITSecurityManager

# 插件注册表：PluginName -> Handler Function
PLUGIN_REGISTRY = {}

logger = logging.getLogger("pero.nit")


def normalize_nit_key(key: str) -> str:
    """归一化插件名/参数名"""
    return key.lower().replace("_", "").replace("-", "")


def remove_nit_tags(text: str) -> str:
    """移除文本中所有的 NIT 调用块 (1.0 和 2.0)"""
    # 移除 NIT 1.0: [[[NIT_CALL]]] ... [[[NIT_END]]]
    text = re.sub(
        r"\[\[\[NIT_CALL\]\]\].*?\[\[\[NIT_END\]\]\]", "", text, flags=re.DOTALL
    )
    # 移除 NIT 2.0: <nit-XXXX> ... </nit-XXXX> 或 <nit> ... </nit>
    text = re.sub(
        r"<(nit(?:-[0-9a-fA-F]{4})?)>.*?</\1>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text.strip()


class NITStreamFilter:
    """
    NIT 流式过滤器：拦截并隐藏 NIT 调用块 (1.0 和 2.0)
    """

    def __init__(self):
        self.buffer = ""
        self.in_nit_block = False
        self.m1_start = "[[[NIT_CALL]]]"
        self.m1_end = "[[[NIT_END]]]"
        self.tag_pattern = re.compile(r"<(nit(?:-[0-9a-fA-F]{4})?)>", re.IGNORECASE)
        self.end_tag_pattern = re.compile(
            r"</(nit(?:-[0-9a-fA-F]{4})?)>", re.IGNORECASE
        )

    def filter(self, chunk: str) -> str:
        self.buffer += chunk
        output = ""

        while self.buffer:
            if not self.in_nit_block:
                idx1 = self.buffer.find(self.m1_start)
                match2 = self.tag_pattern.search(self.buffer)
                idx2 = match2.start() if match2 else -1

                starts = [i for i in [idx1, idx2] if i != -1]
                if not starts:
                    # 保留缓冲区末尾以防分割
                    safe_len = len(self.buffer) - len(self.m1_start) - 10
                    if safe_len > 0:
                        output += self.buffer[:safe_len]
                        self.buffer = self.buffer[safe_len:]
                    return output

                first_start = min(starts)
                output += self.buffer[:first_start]
                self.buffer = self.buffer[first_start:]
                self.in_nit_block = True
            else:
                idx1_end = self.buffer.find(self.m1_end)
                match2_end = self.end_tag_pattern.search(self.buffer)
                idx2_end = match2_end.end() if match2_end else -1

                if idx1_end != -1 and (idx2_end == -1 or idx1_end < idx2_end):
                    self.buffer = self.buffer[idx1_end + len(self.m1_end) :]
                    self.in_nit_block = False
                elif idx2_end != -1:
                    self.buffer = self.buffer[idx2_end:]
                    self.in_nit_block = False
                else:
                    return output

        return output

    def flush(self) -> str:
        """Clear buffer at the end"""
        res = ""
        if not self.in_nit_block:
            res = self.buffer
        self.buffer = ""
        return res


class XMLStreamFilter:
    """
    通用 XML 标签流式过滤器
    用于隐藏特定的 XML 标签及其内容 (如 <PEROCUE>)
    """

    def __init__(self, tag_names: List[str] = None):
        if tag_names is None:
            tag_names = ["PEROCUE", "CHARACTER_STATUS"]
        self.tag_names = [t.upper() for t in tag_names]
        self.buffer = ""
        self.in_block = False
        self.current_end_tag = ""

    def filter(self, chunk: str) -> str:
        self.buffer += chunk
        output = ""

        while self.buffer:
            if not self.in_block:
                # Look for any start tag
                found_tag = None
                found_idx = -1
                for tag in self.tag_names:
                    idx = self.buffer.upper().find(f"<{tag}>")
                    if idx != -1 and (found_idx == -1 or idx < found_idx):
                        found_idx = idx
                        found_tag = tag

                if found_idx == -1:
                    # No start tag, safe to output most of it
                    safe_len = max(0, len(self.buffer) - 20)
                    output += self.buffer[:safe_len]
                    self.buffer = self.buffer[safe_len:]
                    return output

                output += self.buffer[:found_idx]
                self.buffer = self.buffer[found_idx:]
                self.in_block = True
                self.current_end_tag = f"</{found_tag}>".upper()
            else:
                idx = self.buffer.upper().find(self.current_end_tag)
                if idx != -1:
                    self.buffer = self.buffer[idx + len(self.current_end_tag) :]
                    self.in_block = False
                    self.current_end_tag = ""
                else:
                    return output
        return output

    def flush(self) -> str:
        res = ""
        if not self.in_block:
            res = self.buffer
        self.buffer = ""
        return res


class ThinkingBlockStreamFilter:
    """
    思考块过滤器：隐藏 Thinking/Monologue 块
    """

    def __init__(self, tag_names: List[str] = None):
        if tag_names is None:
            self.tag_names = ["Thinking", "Monologue"]

        # 匹配 【Thinking, [Thinking, (Thinking
        pattern_str = r"(?:【|\[|\()(?:" + "|".join(self.tag_names) + r")"
        self.start_pattern = re.compile(pattern_str, re.IGNORECASE)

        self.buffer = ""
        self.in_block = False
        self.current_closer = ""

    def filter(self, chunk: str) -> str:
        self.buffer += chunk
        output = ""

        while self.buffer:
            if not self.in_block:
                match = self.start_pattern.search(self.buffer)
                if not match:
                    safe_len = max(0, len(self.buffer) - 15)
                    output += self.buffer[:safe_len]
                    self.buffer = self.buffer[safe_len:]
                    return output

                start_idx = match.start()
                opener = match.group(0)[0]
                if opener == "【":
                    self.current_closer = "】"
                elif opener == "[":
                    self.current_closer = "]"
                elif opener == "(":
                    self.current_closer = ")"
                else:
                    self.current_closer = "】"

                output += self.buffer[:start_idx]
                self.buffer = self.buffer[start_idx:]
                self.in_block = True

            else:
                closer_idx = self.buffer.find(self.current_closer)
                if closer_idx != -1:
                    self.buffer = self.buffer[closer_idx + len(self.current_closer) :]
                    self.in_block = False
                    self.current_closer = ""
                else:
                    return output

        return output

    def flush(self) -> str:
        res = ""
        if not self.in_block:
            res = self.buffer
        self.buffer = ""
        return res


class NITDispatcher:
    """
    NIT 核心调度器
    负责接收文本流，解析指令，分发任务
    """

    def __init__(self):
        self.pm = get_plugin_manager()
        self.nm = get_nit_manager()
        self.category_map = {}  # Map[norm_plugin_name] -> List[tool_names]
        self.tool_to_manifest = {}  # Map[norm_tool_name] -> Manifest
        # 初始化时加载工具
        self._load_tools()
        self._register_browser_bridge()

    def _load_tools(self):
        """从 PluginManager 加载所有工具"""
        try:
            # 1. Register standard tool names
            tools = self.pm.get_all_tools_map()

            # 2. Register PluginName.ToolName aliases for namespaced calls
            manifests = self.pm.get_all_manifests()
            for manifest in manifests:
                plugin_name = manifest.get("name")
                if not plugin_name:
                    continue

                # Register to category map
                norm_plugin_name = normalize_nit_key(plugin_name)
                if norm_plugin_name not in self.category_map:
                    self.category_map[norm_plugin_name] = []

                commands = []
                if (
                    "capabilities" in manifest
                    and "invocationCommands" in manifest["capabilities"]
                ):
                    commands = manifest["capabilities"]["invocationCommands"]
                elif (
                    "capabilities" in manifest
                    and "toolDefinitions" in manifest["capabilities"]
                ):
                    commands = manifest["capabilities"]["toolDefinitions"]

                for cmd in commands:
                    cmd_id = cmd.get("commandIdentifier")
                    if cmd_id and cmd_id in tools:
                        # Map tool to manifest
                        norm_tool_name = normalize_nit_key(cmd_id)
                        self.tool_to_manifest[norm_tool_name] = manifest

                        # Add to category map
                        self.category_map[norm_plugin_name].append(cmd_id)

                        # Register standard name
                        self._register_tool(cmd_id, tools[cmd_id])

                        # Register "PluginName.ToolName"
                        namespaced_name = f"{plugin_name}.{cmd_id}"
                        self._register_tool(namespaced_name, tools[cmd_id])
                        # Also map namespaced name to manifest
                        self.tool_to_manifest[normalize_nit_key(namespaced_name)] = (
                            manifest
                        )

            logger.info(f"已加载工具。总数: {len(PLUGIN_REGISTRY)}")

        except Exception as e:
            logger.error(f"加载工具出错: {e}", exc_info=True)

    def reload_tools(self):
        """重新加载所有工具"""
        logger.info("正在 Dispatcher 中重新加载工具...")
        # Clear existing registry and map
        global PLUGIN_REGISTRY
        PLUGIN_REGISTRY.clear()
        self.category_map.clear()
        self.tool_to_manifest.clear()

        # Reload from PM
        self.pm.reload_plugins()
        self._load_tools()

    def _register_tool(self, name: str, func: Callable):
        """Helper to register a tool with normalization"""
        norm_name = normalize_nit_key(name)

        # 创建适配器
        def make_adapter(f=func):
            async def adapter(**kwargs):
                if asyncio.iscoroutinefunction(f):
                    return await f(**kwargs)
                else:
                    return f(**kwargs)

            return adapter

        adapter = make_adapter()
        PLUGIN_REGISTRY[norm_name] = adapter

        # 如果 norm_name 和 name 不同，且 name 没被占用，也注册原始名称
        if norm_name != name and name not in PLUGIN_REGISTRY:
            PLUGIN_REGISTRY[name] = adapter

    def _register_browser_bridge(self):
        """注册浏览器桥接服务 (BrowserBridge)"""
        # BrowserBridge 也是一种特殊形式的工具
        try:
            from services.browser_bridge_service import BrowserBridgeService

            bridge = BrowserBridgeService()

            async def browser_bridge_adapter(**kwargs):
                if bridge.latest_page_info:
                    return str(bridge.latest_page_info)
                return "当前没有可用的浏览器页面信息。"

            PLUGIN_REGISTRY["get_browser_page_info"] = browser_bridge_adapter

        except ImportError:
            logger.warning("无法导入 BrowserBridgeService。")
        except Exception as e:
            logger.warning(f"BrowserBridgeService 初始化失败: {e}")

    def list_plugins(self) -> List[str]:
        """获取所有已注册的插件名称"""
        return sorted(list(PLUGIN_REGISTRY.keys()))

    def get_tools_description(self, category_filter: str = "core") -> str:
        """
        [Deprecated]
        此方法已被 AgentService 中的 Unified Tool Policy Enforcement 取代。
        仅保留为空实现以防止遗留代码报错，未来应彻底移除。
        """
        return ""

    async def _echo_plugin(self, params: Dict[str, Any]) -> str:
        """测试用插件"""
        msg = params.get("message", "") or params.get("msg", "")
        return f"[Echo Plugin] Received: {msg}"

    async def dispatch(
        self,
        text: str,
        extra_plugins: Dict[str, Any] = None,
        expected_nit_id: str = None,
        allowed_tools: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        处理 AI 输出的文本块
        返回执行结果列表

        :param text: 包含 NIT 指令的文本
        :param extra_plugins: 临时的额外插件注册表 (例如 MCP 动态加载的工具)
        :param expected_nit_id: 本轮期望的 NIT-ID (用于安全握手)
        :param allowed_tools: 允许执行的工具名称白名单 (如果为 None 则不限制)
        """
        results = []

        # 1. 优先处理 NIT 2.0 脚本 (<nit>...</nit>)
        # Regex to capture <nit> or <nit-XXXX>
        # group(1): full tag name (e.g. "nit" or "nit-A9B2")
        # group(2): ID part only (e.g. "A9B2") if present
        # group(3): content
        nit_pattern = r"<(nit(?:-([0-9a-fA-F]{4}))?)>(.*?)</\1>"
        nit_matches = list(re.finditer(nit_pattern, text, re.DOTALL | re.IGNORECASE))

        if nit_matches:
            logger.info(f"检测到 {len(nit_matches)} 个 NIT 脚本块。")

            # 用于在闭包中捕获当前 block 执行过的工具
            current_block_tools = []

            # Pre-calculate normalized allowed tools set for performance
            normalized_allowed = None
            if allowed_tools is not None:
                normalized_allowed = {normalize_nit_key(t) for t in allowed_tools}

            # 定义 Runtime 的执行器回调
            async def runtime_tool_executor(name: str, params: Dict[str, Any]):
                # --- Whitelist Check ---
                if normalized_allowed is not None:
                    norm_name = normalize_nit_key(name)
                    # Also check against direct name just in case
                    if (
                        norm_name not in normalized_allowed
                        and name not in allowed_tools
                    ):
                        logger.warning(f"安全拦截: 工具 '{name}' 不在白名单中。")
                        return f"⚠️ 权限拒绝: 当前模式下不允许使用工具 '{name}'。请尝试使用其他工具，或告知用户无法执行此操作。"
                # -----------------------

                current_block_tools.append(name)
                return await self._execute_plugin(name, params, extra_plugins)

            for match in nit_matches:
                full_tag = match.group(0)
                # tag_name = match.group(1)
                extracted_id = match.group(2)
                script = match.group(3)

                # 重置当前 block 的工具列表
                current_block_tools = []

                # --- Security Validation ---
                if expected_nit_id:
                    if extracted_id:
                        # ID 存在，必须匹配
                        is_valid, status = NITSecurityManager.validate_id(
                            extracted_id, expected_nit_id
                        )
                        if not is_valid:
                            msg = f"安全拦截: NIT ID 不匹配 (预期 {expected_nit_id}, 实际 {extracted_id})"
                            logger.warning(msg)
                            results.append(
                                {
                                    "plugin": "NIT_Script",
                                    "status": "blocked",
                                    "output": msg,
                                    "raw_block": full_tag,
                                }
                            )
                            continue
                    else:
                        # ID 不存在 (<nit>) -> Fallback Mode
                        logger.warning(
                            f"NIT 回退: 使用了标准 <nit> 标签而非 <nit-{expected_nit_id}>。允许执行。"
                        )
                # ---------------------------

                try:
                    # 去除 script 中的 HTML 实体转义 (如 &gt; -> >) 如果有的话
                    # 但通常 LLM 输出是纯文本。
                    output = await execute_nit_script(script, runtime_tool_executor)
                    results.append(
                        {
                            "plugin": "NIT_Script",
                            "status": "success",
                            "output": output,
                            "raw_block": full_tag,
                            "executed_tools": list(current_block_tools),  # Copy list
                        }
                    )
                except Exception as e:
                    logger.error(f"NIT 脚本错误: {e}", exc_info=True)
                    results.append(
                        {
                            "plugin": "NIT_Script",
                            "status": "error",
                            "output": f"Script Error: {str(e)}",
                            "raw_block": full_tag,
                            "executed_tools": list(
                                current_block_tools
                            ),  # Copy partial list
                        }
                    )

        return results

    async def _execute_plugin(
        self,
        plugin_name: str,
        params: Dict[str, Any],
        extra_plugins: Dict[str, Any] = None,
    ) -> str:
        """执行单个插件"""
        start_time = time.perf_counter()

        # [Fix] 移除路径幻觉
        if "\\" in plugin_name or "/" in plugin_name:
            original_path = plugin_name
            plugin_name = os.path.basename(plugin_name.replace("\\", "/").rstrip("/"))
            logger.warning(f"移除路径前缀: '{original_path}' -> '{plugin_name}'")

        # 日志参数截断
        params_str = json.dumps(params, ensure_ascii=False)
        if len(params_str) > 200:
            params_str = params_str[:200] + "..."
        logger.info(f"▶ 工具调用: {plugin_name} | 参数: {params_str}")

        norm_name = normalize_nit_key(plugin_name)

        # 状态与权限检查
        manifest = self.tool_to_manifest.get(norm_name)
        if manifest:
            plugin_id = manifest.get("name")
            category = manifest.get("_category", "core")

            # 轻量模式检查
            config = get_config_manager()
            if config.get("lightweight_mode", False):
                if plugin_id not in ["ScreenVision", "TaskLifecycle", "MemoryOps"]:
                    logger.warning(f"轻量模式拦截: {plugin_name}")
                    return f"错误: 工具 '{plugin_name}' 在轻量聊天模式下受限。"

            if not self.nm.is_category_enabled(category):
                return f"错误: 类别 '{category}' 已禁用。"
            if not self.nm.is_plugin_enabled(plugin_id):
                return f"错误: 插件 '{plugin_id}' 已禁用。"

        # 查找 Handler (Extra -> Global -> Auto-Route)
        handler = None
        if extra_plugins:
            handler = extra_plugins.get(norm_name) or next(
                (
                    v
                    for k, v in extra_plugins.items()
                    if normalize_nit_key(k) == norm_name
                ),
                None,
            )

        if not handler:
            handler = PLUGIN_REGISTRY.get(norm_name)

        # 自动路由 (PluginName.CommandName)
        if not handler:
            routing_keys = ["command", "commandidentifier", "action", "tool"]
            potential_cmds = [(k, params.get(k)) for k in routing_keys if params.get(k)]

            for key, cmd in potential_cmds:
                namespaced_key = normalize_nit_key(f"{plugin_name}.{cmd}")
                handler = PLUGIN_REGISTRY.get(namespaced_key)
                if handler:
                    logger.info(f"自动路由: {plugin_name} + {cmd} -> {namespaced_key}")
                    params.pop(key, None)
                    break

                cmd_key = normalize_nit_key(cmd)
                handler = PLUGIN_REGISTRY.get(cmd_key)
                if handler:
                    logger.info(f"自动路由: {plugin_name} + {cmd} -> {cmd_key}")
                    params.pop(key, None)
                    break

        if not handler:
            if norm_name in self.category_map:
                tools = self.category_map[norm_name]
                msg = f"错误: '{plugin_name}' 是类别而非工具。可用工具: {', '.join(tools)}"
                logger.error(msg)
                raise RuntimeError(msg)

            msg = f"错误: 未找到插件 '{plugin_name}' (归一化名: {norm_name})。"
            logger.error(msg)
            raise RuntimeError(msg)

        try:
            result = None
            if asyncio.iscoroutinefunction(handler):
                result = await handler(**params)
            else:
                # [Async] 在线程池运行同步阻塞函数
                loop = asyncio.get_running_loop()
                from functools import partial

                result = await loop.run_in_executor(None, partial(handler, **params))

            duration = (time.perf_counter() - start_time) * 1000
            result_str = str(result)
            result_preview = (
                result_str[:100] + "..." if len(result_str) > 100 else result_str
            )

            logger.info(
                f"✔ 完成: {plugin_name} | {duration:.2f}ms | 结果: {result_preview}"
            )
            return result

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"✘ 失败: {plugin_name} | {duration:.2f}ms | 错误: {e}", exc_info=True
            )
            raise e


# 全局单例
_dispatcher_instance = None


def get_dispatcher():
    global _dispatcher_instance
    if _dispatcher_instance is None:
        _dispatcher_instance = NITDispatcher()
    return _dispatcher_instance
