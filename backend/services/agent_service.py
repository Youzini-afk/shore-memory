import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, AsyncIterable, Dict, List, Optional

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.nit_manager import get_nit_manager
from models import (
    AIModelConfig,
    Config,
    ConversationLog,
    MCPConfig,
    PetState,
    ScheduledTask,
)
from nit_core.security import NITSecurityManager
from nit_core.tools import TOOLS_DEFINITIONS, TOOLS_MAPPING, plugin_manager
from nit_core.tools.core.WindowsOps.windows_ops import get_active_windows
from services.llm_service import LLMService
from services.mcp_service import McpClient
from services.memory_service import MemoryService
from services.postprocessor.implementations import (
    NITFilterPostprocessor,
    ThinkingFilterPostprocessor,
)
from services.postprocessor.manager import PostprocessorManager
from services.preprocessor.implementations import (
    ConfigPreprocessor,
    GraphFlashbackPreprocessor,
    HistoryPreprocessor,
    PerceptionPreprocessor,  # Added
    RAGPreprocessor,
    SystemPromptPreprocessor,
    UserInputPreprocessor,  # Added
)
from services.preprocessor.manager import PreprocessorManager
from services.prompt_service import PromptManager
from services.scorer_service import ScorerService
from services.session_service import set_current_session_context
from services.task_manager import task_manager


class AgentService:
    def __init__(self, session: AsyncSession):
        self.session = session

        # Inject session and agent_id for tool ops
        from services.agent_manager import get_agent_manager

        agent_id = "pero"
        try:
            agent_id = get_agent_manager().active_agent_id
        except Exception:
            pass

        set_current_session_context(session, agent_id)
        self.memory_service = MemoryService()
        self.scorer_service = ScorerService(session)
        self.prompt_manager = PromptManager()

        # 初始化辅助 MDP (使用集中式 MDP)
        self.mdp = self.prompt_manager.mdp

        # 初始化预处理器管道
        self.preprocessor_manager = PreprocessorManager()
        self.preprocessor_manager.register(UserInputPreprocessor())
        self.preprocessor_manager.register(HistoryPreprocessor())
        # self.preprocessor_manager.register(WeeklyReportPreprocessor()) # 根据用户请求禁用 (文档现在是静态文件)
        self.preprocessor_manager.register(RAGPreprocessor())
        self.preprocessor_manager.register(GraphFlashbackPreprocessor())
        self.preprocessor_manager.register(ConfigPreprocessor())
        self.preprocessor_manager.register(
            PerceptionPreprocessor()
        )  # 新增: 注入静默感知日志
        self.preprocessor_manager.register(SystemPromptPreprocessor())

        # 初始化后处理器管道
        self.postprocessor_manager = PostprocessorManager()
        self.postprocessor_manager.register(NITFilterPostprocessor())
        self.postprocessor_manager.register(ThinkingFilterPostprocessor())

    def _log_to_file(self, msg: str):
        try:
            # 使用绝对路径以确保日志文件在 backend 目录下创建
            data_dir = os.environ.get(
                "PERO_DATA_DIR",
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            log_path = os.path.join(data_dir, "debug_vision.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} {msg}\n")
        except Exception as e:
            print(f"写入日志文件失败: {e}")

    async def _get_reflection_config(self) -> Dict[str, Any]:
        """获取反思模型配置"""
        configs = {
            c.key: c.value for c in (await self.session.exec(select(Config))).all()
        }

        if configs.get("reflection_enabled") != "true":
            return None

        reflection_model_id = configs.get("reflection_model_id")
        if not reflection_model_id:
            return None

        try:
            model_config = await self.session.get(
                AIModelConfig, int(reflection_model_id)
            )
            if not model_config:
                return None

            global_api_key = configs.get("global_llm_api_key", "")
            global_api_base = configs.get(
                "global_llm_api_base", "https://api.openai.com"
            )

            final_api_key = (
                model_config.api_key
                if model_config.provider_type == "custom"
                else global_api_key
            )
            final_api_base = (
                model_config.api_base
                if model_config.provider_type == "custom"
                else global_api_base
            )

            return {
                "api_key": final_api_key,
                "api_base": final_api_base,
                "model": model_config.model_id,
                "temperature": 0.1,  # 反思需要理性，低温
                "enable_vision": model_config.enable_vision,
            }
        except Exception as e:
            print(f"获取反思配置出错: {e}")
            return None

    async def _analyze_file_results_with_aux(
        self, user_query: str, file_results: List[str]
    ) -> Optional[str]:
        """
        使用辅助模型分析文件搜索结果
        """
        try:
            # 1. 检查是否启用了辅助模型
            aux_model_config = (
                await self.session.exec(
                    select(AIModelConfig).where(AIModelConfig.name == "辅助模型")
                )
            ).first()

            if not aux_model_config:
                print("[Agent] 未配置辅助模型，跳过分析。")
                return None

            print(
                f"[Agent] 正在使用辅助模型 ({aux_model_config.model_id}) 分析搜索结果..."
            )

            # 2. 准备 Prompt
            # 限制文件数量以避免 Context Window 爆炸
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

            # 3. 调用辅助模型
            # 构造辅助 LLMService 实例
            # 注意：需要从 Config 中获取全局 API Key/Base 如果辅助模型配置为使用全局
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

            # 调用 chat 方法
            response = await aux_llm.chat(messages, temperature=0.3)
            return response["choices"][0]["message"]["content"]

        except Exception as e:
            print(f"[Agent] 辅助分析出错: {e}")
            return None

    async def _analyze_screen_with_mcp(
        self, mcp_client: Optional[McpClient] = None
    ) -> Optional[str]:
        """通过 MCP 调用视觉模型分析当前屏幕"""
        print("\n[Vision] 开始屏幕分析...", flush=True)

        self._log_to_file("开始屏幕分析")

        # 如果外部没有传入 mcp_client，则尝试从已启用的客户端中寻找具备视觉能力的
        if not mcp_client:
            try:
                clients = await self._get_mcp_clients()
                for client in clients:
                    # 简单检查客户端是否包含视觉工具关键词
                    try:
                        tools = await client.list_tools()
                        vision_keywords = [
                            "vision",
                            "analyze_image",
                            "screen_analysis",
                            "describe_image",
                            "see_screen",
                            "screenshot_analysis",
                            "ocr",
                        ]
                        if any(
                            any(k in t["name"].lower() for k in vision_keywords)
                            for t in tools
                        ):
                            mcp_client = client
                            print(f"[Vision] 发现具备视觉能力的客户端: {client.name}")
                            break
                    except Exception:
                        continue

                # 如果没找到，退而求其次用第一个
                if not mcp_client and clients:
                    mcp_client = clients[0]
                    print(
                        f"[Vision] 未找到特定的视觉客户端，使用第一个可用的: {mcp_client.name}"
                    )
            except Exception as e:
                msg = f"[Vision] 获取 MCP 客户端失败: {e}"
                print(msg, flush=True)
                self._log_to_file(msg)
                return f"❌ 视觉功能不可用：获取 MCP 客户端失败 ({e})"

        if not mcp_client:
            msg = "[Vision] 未配置 MCP 客户端。"
            print(msg, flush=True)
            self._log_to_file(msg)
            # 调试：打印当前库中所有的配置键
            try:
                keys = (await self.session.exec(select(Config.key))).all()
                print(f"[Vision] 可用的配置键: {keys}", flush=True)
            except Exception as e:
                print(f"[Vision] 列出配置键失败: {e}", flush=True)
            return "❌ 视觉功能不可用：未配置 MCP 服务器。请在设置中添加支持视觉能力的 MCP 服务器配置（如 GLM-4V）。"

    async def _analyze_screen_with_mcp_deprecated(self) -> str:
        """
        [已弃用] 旧版 MCP 视觉分析方法
        现已迁移至 NIT 架构，此方法保留仅为防止运行时 AttributeError，实际不应被调用。
        """
        return "⚠️ 此功能已迁移至 NIT 插件系统。"

    async def _run_reflection(
        self, task: str, history: str, screenshot_base64: str = None
    ) -> str:
        """运行反思逻辑"""
        config = await self._get_reflection_config()
        if not config:
            return None

        print("[Reflection] 触发反思机制...")

        # 视觉分析已迁移至 NIT，反思逻辑暂不强依赖视觉预分析
        vision_analysis = None
        is_blind = not config.get("enable_vision")

        llm = LLMService(
            api_key=config.get("api_key"),
            api_base=config.get("api_base"),
            model=config.get("model"),
            provider=config.get("provider", "openai"),
        )

        # 根据视觉能力状态动态调整 Prompt
        vision_prompt_name = "vision_enabled" if not is_blind else "vision_disabled"
        vision_instruction_block = "{{" + vision_prompt_name + "}}"

        # 生成工具列表字符串
        tools_list_str = ""
        # 动态获取最新工具定义
        # current_tools_defs = plugin_manager.get_all_definitions()

        # 改用符合 NIT 协议的筛选逻辑：必须经过 NIT Manager 的启用检查
        nit_manager = get_nit_manager()
        current_tools_defs = []

        for plugin_name, manifest in plugin_manager.plugins.items():
            # 1. 检查分类开关 (Level 1)
            category = manifest.get("_category", "plugins")  # 默认为 plugins
            if not nit_manager.is_category_enabled(category):
                continue

            # 2. 检查插件开关 (Level 2)
            if not nit_manager.is_plugin_enabled(plugin_name):
                continue

            # 3. 提取工具定义
            if (
                "capabilities" in manifest
                and "invocationCommands" in manifest["capabilities"]
            ):
                current_tools_defs.extend(
                    manifest["capabilities"]["invocationCommands"]
                )
            elif (
                "capabilities" in manifest
                and "toolDefinitions" in manifest["capabilities"]
            ):
                current_tools_defs.extend(manifest["capabilities"]["toolDefinitions"])

        for tool_def in current_tools_defs:
            if "function" in tool_def:
                func = tool_def["function"]
                name = func.get("name", "unknown")
                desc = func.get("description", "无描述")
                tools_list_str += f"- {name}: {desc}\n"
            elif "name" in tool_def:  # 支持 NIT 风格的定义
                name = tool_def.get("name", "unknown")
                desc = tool_def.get("description", "无描述")
                tools_list_str += f"- {name}: {desc}\n"
            elif "commandIdentifier" in tool_def:  # 支持 NIT 2.0 风格定义
                name = tool_def.get("commandIdentifier", "unknown")
                desc = tool_def.get("description", "无描述")
                tools_list_str += f"- {name}: {desc}\n"

        system_prompt = self.mdp.render(
            "tasks/memory/reflection/reflection_ui",
            {
                "tools_list_str": tools_list_str,
                "tools_count": len(tools_list_str),
                "vision_instruction": vision_instruction_block,
            },
        )
        user_content = f"任务目标: {task}\n\n近期操作历史:\n{history}"

        if vision_analysis:
            user_content += f"\n\n[当前屏幕视觉分析]:\n{vision_analysis}"
            print("[Reflection] 已将视觉分析添加到上下文。")

        messages = [{"role": "system", "content": system_prompt}]

        # 组装用户消息内容
        content = [{"type": "text", "text": user_content}]

        # 如果提供了截图且模型支持多模态，则注入图片
        if screenshot_base64 and config.get("enable_vision"):
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screenshot_base64}"},
                }
            )
            print("[Reflection] 已将截图注入反思上下文。")

        messages.append({"role": "user", "content": content})

        try:
            response = await llm.chat(
                messages, temperature=config.get("temperature", 0.7)
            )
            content = response["choices"][0]["message"]["content"]
            print(f"[Reflection] 结果: {content}")
            return content
        except Exception as e:
            print(f"[Reflection] 错误: {e}")
            return None

    async def _get_llm_config(self) -> Dict[str, Any]:
        # 1. 获取全局配置
        configs = {
            c.key: c.value for c in (await self.session.exec(select(Config))).all()
        }

        global_api_key = configs.get("global_llm_api_key", "")
        global_api_base = configs.get("global_llm_api_base", "https://api.openai.com")
        current_model_id = configs.get("current_model_id")

        # 默认回退配置
        fallback_config = {
            "api_key": global_api_key or configs.get("ppc.apiKey", ""),  # 兼容旧key
            "api_base": global_api_base
            or configs.get("ppc.apiBase", "https://api.openai.com"),
            "model": configs.get("ppc.modelName", "gpt-3.5-turbo"),
            "temperature": 0.7,
            "enable_vision": False,
        }

        # 2. 如果没有选中模型，使用默认/回退配置
        if not current_model_id:
            return fallback_config

        # 3. 获取选中模型卡片
        try:
            model_config = await self.session.get(AIModelConfig, int(current_model_id))
            if not model_config:
                return fallback_config
        except ValueError:
            return fallback_config

        # 4. 组装配置
        final_api_key = (
            model_config.api_key
            if model_config.provider_type == "custom"
            else global_api_key
        )
        final_api_base = (
            model_config.api_base
            if model_config.provider_type == "custom"
            else global_api_base
        )

        return {
            "api_key": final_api_key,
            "api_base": final_api_base,
            "model": model_config.model_id,
            "provider": model_config.provider,  # Added provider
            "temperature": model_config.temperature,
            "enable_vision": model_config.enable_vision,
        }

    async def _get_pet_state(self) -> PetState:
        # [多 Agent] 按活跃 Agent 过滤 PetState
        from services.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        active_agent_id = agent_manager.active_agent_id

        state = (
            await self.session.exec(
                select(PetState)
                .where(PetState.agent_id == active_agent_id)
                .order_by(desc(PetState.updated_at))
                .limit(1)
            )
        ).first()

        if not state:
            state = PetState(agent_id=active_agent_id)
            self.session.add(state)
            await self.session.commit()
            await self.session.refresh(state)
        return state

    async def handle_proactive_observation(self, intent_description: str, score: float):
        """
        处理来自 AuraVision 的主动视觉观察结果。
        """
        # 1. 检查现在是否应该说话
        # TODO: 实现更复杂的门控逻辑 (例如检查上次说话时间)
        print(f"[Agent] 收到主动观察结果: {intent_description} (评分: {score:.4f})")

        # 2. 构造内部感知 Prompt
        internal_promptuser_prompt = self.mdp.render(
            "tasks/perception/proactive_internal_sense",
            {"intent_description": intent_description, "score": f"{score:.4f}"},
        )

        # 3. 触发特殊会话
        # 这将涉及调用 self.process_request 并带有一个伪造的用户消息
        # 但标记为内部触发。
        pass

    async def _get_mcp_clients(self) -> List[McpClient]:
        """获取所有已启用的 MCP 客户端"""
        clients = []
        # 1. 尝试从新版通用 MCP 配置表中获取
        try:
            # 获取所有配置，无论是否启用，以此判断新表是否有数据
            all_mcp_configs = (await self.session.exec(select(MCPConfig))).all()

            if all_mcp_configs:
                print(
                    f"[AgentService] 在 MCPConfig 表中找到 {len(all_mcp_configs)} 个配置。以此为准。"
                )
                for mcp_config_obj in all_mcp_configs:
                    if not mcp_config_obj.enabled:
                        continue

                    print(
                        f"[AgentService] 加载已启用的 MCP 配置: {mcp_config_obj.name}"
                    )
                    client_config = {
                        "type": mcp_config_obj.type,
                        "name": mcp_config_obj.name,
                    }

                    if mcp_config_obj.type == "stdio":
                        client_config.update(
                            {
                                "command": mcp_config_obj.command,
                                "args": json.loads(mcp_config_obj.args or "[]"),
                                "env": json.loads(mcp_config_obj.env or "{}"),
                            }
                        )
                    elif mcp_config_obj.type == "sse":
                        client_config.update({"url": mcp_config_obj.url})

                    clients.append(McpClient(config=client_config))
                # 只要新表有数据（即使全部被禁用），就以此为准，不再向下回退
                return clients
        except Exception as e:
            print(f"[AgentService] 查询 MCPConfig 表错误: {e}")

        # 只有当新表完全没数据时，才尝试获取旧版配置作为回退
        # 2. 尝试获取完整 JSON 配置
        try:
            json_config = (
                await self.session.exec(
                    select(Config).where(Config.key == "mcp_config_json")
                )
            ).first()

            if json_config and json_config.value:
                try:
                    config_data = json.loads(json_config.value)
                    if "mcpServers" in config_data:
                        for name, server_config in config_data["mcpServers"].items():
                            # 检查是否启用 (默认为 True)
                            if not server_config.get("enabled", True):
                                print(
                                    f"[AgentService] 跳过已禁用的 MCP JSON 配置: {name}"
                                )
                                continue

                            print(f"[AgentService] 找到 MCP JSON 配置: {name}")
                            # 确保配置中有名字
                            if "name" not in server_config:
                                server_config["name"] = name
                            clients.append(McpClient(config=server_config))
                    else:
                        print("[AgentService] 找到直接 MCP JSON 配置")
                        clients.append(McpClient(config=config_data))
                except Exception as e:
                    print(f"[AgentService] 加载 MCP JSON 配置失败: {e}")
        except Exception as e:
            print(f"[AgentService] 查询 mcp_config_json 错误: {e}")

        # 3. 回退到旧的 URL/Key 配置 (仅当仍没有客户端时)
        if not clients:
            try:
                url_config = (
                    await self.session.exec(
                        select(Config).where(Config.key == "mcp_server_url")
                    )
                ).first()

                if url_config and url_config.value:
                    key_config = (
                        await self.session.exec(
                            select(Config).where(Config.key == "mcp_api_key")
                        )
                    ).first()
                    api_key = key_config.value if key_config else None

                    print(f"[AgentService] 回退到旧版 MCP URL 配置: {url_config.value}")
                    clients.append(
                        McpClient(
                            config={
                                "type": "sse",
                                "url": url_config.value,
                                "api_key": api_key,
                                "name": "Legacy-MCP",
                            }
                        )
                    )
            except Exception as e:
                print(f"[AgentService] 查询 mcp_server_url 错误: {e}")

        return clients

    async def _save_parsed_metadata(
        self,
        text: str,
        source: str = "desktop",
        mcp_clients: List[McpClient] = None,
        execute_nit: bool = True,
        expected_nit_id: str = None,
        allowed_tools: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """解析并保存 LLM 返回的元数据。现在主要负责 NIT 工具调用。"""
        try:
            # 1. 处理 NIT 工具调用 (核心逻辑)
            nit_results = []
            if execute_nit:
                # --- [安全门控] 针对手机端的 NIT 脚本硬隔离 ---
                if source == "mobile":
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
                    # 检查 text 中是否包含 <nit> 且内容涉及敏感词
                    if "<nit" in text and any(
                        kw in text.lower() for kw in sensitive_tool_keywords
                    ):
                        print(
                            f"[🛡️ 安全拦截] 已拦截来自移动端的 NIT 脚本执行: {text[:50]}..."
                        )
                        return [
                            {
                                "status": "error",
                                "message": "权限拒绝：NIT 脚本包含移动端受限的工具。",
                            }
                        ]

                from nit_core.dispatcher import get_dispatcher

                nit_dispatcher = get_dispatcher()

                # 准备 MCP 插件 (如果存在)
                extra_plugins = None
                if mcp_clients:
                    try:
                        from nit_core.bridge import NITBridge

                        bridge = NITBridge(nit_dispatcher)
                        extra_plugins = await bridge.get_mcp_plugins(mcp_clients)
                    except Exception as e:
                        print(f"[Agent] 将 MCP 工具桥接到 NIT 失败: {e}")

                nit_results = await nit_dispatcher.dispatch(
                    text,
                    extra_plugins=extra_plugins,
                    expected_nit_id=expected_nit_id,
                    allowed_tools=allowed_tools,
                )

                if nit_results:
                    print(f"[Agent] 执行了 {len(nit_results)} 个 NIT 工具调用")

            # 2. 传统 XML 标签解析 (已弃用，仅保留框架以防未来扩展)
            # 注意：状态更新 (PEROCUE, CLICK_MESSAGES 等) 已迁移至 UpdateStatusPlugin (NIT)
            # 长记忆 (MEMORY) 已由 ScorerService 独立处理

            await self.session.commit()
            return nit_results
        except Exception as e:
            await self.session.rollback()
            print(f"_save_parsed_metadata 出错: {e}")
            return []

    async def preview_prompt(
        self, session_id: str, source: str, log_id: int
    ) -> Dict[str, Any]:
        """
        预览特定对话日志的完整 Prompt (系统 + 历史 + 用户)。
        用于调试/仪表盘检查。
        """
        # 1. 获取目标日志
        log = await self.session.get(ConversationLog, log_id)
        if not log:
            return {"error": "Log not found"}

        # 2. 识别“当前消息”和“历史截止点”
        current_msg_log = None
        history_before_id = None

        if log.role == "assistant":
            # 查找此消息之前的最近一条用户消息
            stmt = (
                select(ConversationLog)
                .where(ConversationLog.session_id == session_id)
                .where(ConversationLog.source == source)
                .where(ConversationLog.id < log_id)
                .where(ConversationLog.role == "user")
                .order_by(desc(ConversationLog.id))
                .limit(1)
            )
            current_msg_log = (await self.session.exec(stmt)).first()

            if current_msg_log:
                history_before_id = current_msg_log.id
            else:
                # 回退：仅使用 log_id 之前的历史
                history_before_id = log.id

        else:
            # 用户日志已选中
            current_msg_log = log
            history_before_id = log.id

        # 3. 构造上下文
        messages = []
        if current_msg_log:
            messages.append({"role": "user", "content": current_msg_log.content})

        # 4. 运行预处理器管道 (空跑)
        agent_id = log.agent_id or "pero"

        context = {
            "messages": messages,
            "source": source,
            "session_id": session_id,
            "session": self.session,
            "memory_service": self.memory_service,
            "prompt_manager": self.prompt_manager,
            "agent_service": self,
            "agent_id": agent_id,
            "variables": {"history_before_id": history_before_id, "is_preview": True},
            "skip_system_prompt": False,
        }

        # 运行管道
        context = await self.preprocessor_manager.process(context)

        # 5. 提取最终消息
        final_messages = context.get("final_messages", [])

        return {"messages": final_messages}

    # [Legacy] social_chat method removed. Use chat(source='social') instead.

    async def _run_scorer_background(
        self,
        user_msg: str,
        assistant_msg: str,
        source: str,
        pair_id: str = None,
        agent_id: str = "pero",
    ):
        """后台运行 Scorer 服务，使用独立 Session"""
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        from database import engine

        try:
            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session() as session:
                scorer = ScorerService(session)
                await scorer.process_interaction(
                    user_msg, assistant_msg, source, pair_id=pair_id, agent_id=agent_id
                )
        except Exception as e:
            print(f"[Agent] 后台秘书服务失败: {e}")

    async def _trigger_dream(self, agent_id: str = "pero"):
        """后台触发梦境机制"""
        try:
            import random

            from sqlalchemy.orm import sessionmaker
            from sqlmodel.ext.asyncio.session import AsyncSession

            from database import engine
            from services.reflection_service import ReflectionService

            print(f"[Agent] 启动后台梦境任务 (agent_id={agent_id})...", flush=True)
            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session() as session:
                # Update last trigger time in Config
                # [Note] Config is global, but maybe we should key it by agent_id too?
                # For now, let's keep it global or key it if we want per-agent scheduling.
                # Given user request is about memory isolation, scheduling isolation is less critical
                # but good to have. Let's use a suffixed key.

                config_key = f"last_dream_trigger_time_{agent_id}"
                now_str = datetime.now().isoformat()
                config_last_dream = await session.get(Config, config_key)

                # Fallback to global key for backward compatibility or if first run
                if not config_last_dream and agent_id == "pero":
                    config_last_dream = await session.get(
                        Config, "last_dream_trigger_time"
                    )

                if not config_last_dream:
                    config_last_dream = Config(key=config_key, value=now_str)
                    session.add(config_last_dream)
                else:
                    config_last_dream.value = now_str
                    config_last_dream.updated_at = datetime.now()
                await session.commit()

                service = ReflectionService(session)

                # 1. 补录记忆 (Priority: Fix failures first)
                # Scorer tasks are agent-agnostic in lookup but agent-specific in processing.
                # However, backfill_failed_scorer_tasks iterates over logs which HAVE agent_id.
                # Ideally we should filter tasks by agent_id too.
                # But ReflectionService.backfill_failed_scorer_tasks doesn't support filtering yet.
                # It's safe to run globally as it respects log.agent_id.
                # UPDATE: Now it supports filtering to prevent log noise and potential race conditions.
                await service.backfill_failed_scorer_tasks(agent_id=agent_id)

                # 2. 孤独记忆扫描 (New Feature: Fix isolated memories)
                # 每次梦境周期扫描 3 个孤独记忆
                await service.scan_lonely_memories(limit=3, agent_id=agent_id)

                # 3. 关联挖掘 (High Priority)
                await service.dream_and_associate(limit=10, agent_id=agent_id)

                # 3. 记忆压缩 (Low Priority, 10% chance)
                if random.random() < 0.1:
                    # 默认配置: 压缩3天前的低价值记忆
                    await service.consolidate_memories(
                        lookback_days=3, importance_threshold=4, agent_id=agent_id
                    )

        except Exception as e:
            print(f"[Agent] 后台梦境失败: {e}")

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        source: str = "desktop",
        session_id: str = "default",
        on_status: Optional[Any] = None,
        is_voice_mode: bool = False,
        user_text_override: str = None,
        skip_save: bool = False,
        system_trigger_instruction: str = None,
        agent_id_override: str = None,
        capabilities: List[str] = None,
        skip_system_prompt: bool = False,
        initial_variables: Dict[str, Any] = None,
    ) -> AsyncIterable[str]:
        # [NIT 安全] 为此请求上下文生成 ID
        current_nit_id = NITSecurityManager.generate_random_id()

        # 通知 CompanionService 用户活动以防止中断
        try:
            # [Fix] 跳过 social/mobile 的陪伴更新
            if source not in ["social", "mobile"]:
                from services.companion_service import companion_service

                companion_service.update_activity()
        except ImportError:
            pass
        except Exception as e:
            print(f"[Agent] 更新陪伴活动失败: {e}")

        # 取消任何待处理的“反应”任务，因为用户正在交互
        if not system_trigger_instruction:
            try:
                # [Multi-Agent] 仅取消当前 Agent 的任务
                from services.agent_manager import get_agent_manager

                current_agent_id = (
                    agent_id_override or get_agent_manager().active_agent_id
                )

                # 假设“反应”类型的任务是那些应该在交互时取消的任务
                statement = (
                    select(ScheduledTask)
                    .where(ScheduledTask.type == "reaction")
                    .where(ScheduledTask.is_triggered == False)
                    .where(ScheduledTask.agent_id == current_agent_id)
                )
                tasks_to_cancel = (await self.session.exec(statement)).all()
                if tasks_to_cancel:
                    print(
                        f"[Agent] 检测到用户交互。取消 {len(tasks_to_cancel)} 个待处理的反应任务。"
                    )
                    for t in tasks_to_cancel:
                        await self.session.delete(t)
                    await self.session.commit()
            except Exception as e:
                print(f"[Agent] 取消反应任务失败: {e}")

        # [Work Mode] Session Override
        # Check if we are in an active work session. If so, override the session_id to isolate history.
        # [Fix] Disabled global override to prevent hijacking of 'default' (Pet) session.
        # IdeChat handles session resolution via ide_router.
        # try:
        #     config_session = (await self.session.exec(select(Config).where(Config.key == "current_session_id"))).first()
        #     if config_session and config_session.value and config_session.value != "default":
        #         original_session_id = session_id
        #         session_id = config_session.value
        #         print(f"[Agent] 工作模式激活: 覆盖会话 ID '{original_session_id}' -> '{session_id}'")
        # except Exception as e:
        #     print(f"[Agent] 检查会话覆盖失败: {e}")

        print(
            f"[Agent] 收到聊天请求。来源: {source}, 消息数: {len(messages)}, 语音: {is_voice_mode}"
        )

        # [功能] 多 Agent 支持
        # 从 AgentManager 提取 agent_id (标准化)
        from services.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        current_agent_id = agent_id_override or agent_manager.active_agent_id

        # 如果未设置，回退到 "pero" (尽管 AgentManager 应该处理这个问题)
        if not current_agent_id:
            current_agent_id = "pero"

        # 1. 初始化上下文
        context = {
            "messages": messages,
            "source": source,
            "session_id": session_id,
            "session": self.session,
            "memory_service": self.memory_service,
            "prompt_manager": self.prompt_manager,
            "user_text_override": user_text_override,
            "is_voice_mode": is_voice_mode,
            "agent_service": self,
            "agent_id": current_agent_id,  # 将显式 agent_id 添加到上下文
            "variables": initial_variables if initial_variables else {},
            "nit_id": current_nit_id,
            "skip_system_prompt": skip_system_prompt,  # 将跳过标志传递给预处理器
        }

        # 如果配置缺失，回退 (如果 ConfigPreprocessor 运行则不应发生)
        # [Refactor] 提前加载 Config 以支持工具计算
        config = await self._get_llm_config()

        # 5. 合并动态 MCP 工具
        if on_status:
            await on_status("thinking", "正在加载工具...")
        print("[Agent] 正在加载 MCP 工具...")

        # --- 工具列表优化 ---
        # [Refactor] Unified Tool Policy Enforcement
        from core.plugin_manager import get_plugin_manager
        from services.agent_manager import get_agent_manager

        plugin_manager = get_plugin_manager()
        agent_manager = get_agent_manager()
        agent_profile = agent_manager.get_agent(current_agent_id)

        # 1. Determine Policy Mode
        policy_mode = "desktop"
        if source == "social":
            policy_mode = "social"
        elif session_id and session_id.startswith("work_"):
            policy_mode = "work"
        elif source == "lightweight" or (session_id and "companion" in session_id):
            policy_mode = "lightweight"

        # 2. Get Policy Config
        policy = {}
        if agent_profile and agent_profile.tool_policies:
            policy = agent_profile.tool_policies.get(policy_mode, {})
            print(f"[Agent] 使用工具策略: {policy_mode} (Agent: {current_agent_id})")

        # 3. Fallback Defaults (Backward Compatibility)
        if not policy:
            print(f"[Agent] 未找到策略配置，使用默认回退策略: {policy_mode}")
            if policy_mode == "social":
                # Default safe social policy
                policy = {
                    "strategy": "whitelist",
                    "allowed_prefixes": ["qq_"],
                    "allowed_tools": [
                        "read_social_memory",
                        "read_agent_memory",
                        "qq_notify_master",
                    ],
                }
            elif policy_mode == "work":
                # Default work policy
                policy = {
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
            elif policy_mode == "lightweight":
                policy = {
                    "strategy": "whitelist",
                    "allowed_tools": [
                        "read_agent_memory",
                        "add_reminder",
                        "list_reminders",
                        "delete_reminder",
                    ],
                }
            else:
                policy = {"strategy": "all"}

        # 4. Build Tool Tags Map for Filtering
        tool_tags_map = {}
        all_manifests = plugin_manager.get_all_manifests()
        for m in all_manifests:
            tags = m.get("tags", [])
            # Add implicit tag based on category if needed
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

        # 5. Prepare All Potential Tools (Native + MCP)
        candidate_tools = []
        enable_vision = config.get("enable_vision", False)

        # 5.1 Native Tools
        for tool_def in TOOLS_DEFINITIONS:
            if "function" not in tool_def or "name" not in tool_def.get("function", {}):
                continue
            new_def = json.loads(json.dumps(tool_def))
            candidate_tools.append(new_def)

        # 5.2 MCP Tools
        mcp_clients = []
        try:
            mcp_clients = await self._get_mcp_clients()
            print(f"[Agent] 加载了 {len(mcp_clients)} 个 MCP 客户端")
        except Exception as e:
            print(f"[Agent] 获取 MCP 客户端失败: {e}")

        mcp_tool_map = {}  # tool_name -> client
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
                    # MCP tools don't have tags in our system yet, but we can treat 'mcp' as a tag if needed
                    tool_tags_map[tool_name] = ["mcp"]
            except Exception as e:
                print(f"[AgentService] 警告: 列出客户端 {client.name} 的工具失败: {e}")

        # 5.3 Plugin Tools (NIT Plugins)
        # Ensure plugins are also candidates so they can be whitelisted and exposed
        existing_tool_names = set(t["function"]["name"] for t in candidate_tools)
        for m in all_manifests:
            cmds = []
            if "capabilities" in m and "invocationCommands" in m["capabilities"]:
                cmds = m["capabilities"]["invocationCommands"]
            elif "capabilities" in m and "toolDefinitions" in m["capabilities"]:
                cmds = m["capabilities"]["toolDefinitions"]

            for cmd in cmds:
                c_id = cmd.get("commandIdentifier")
                if c_id and c_id not in existing_tool_names:
                    # Construct a basic function definition
                    # Note: Plugin args might not be perfect JSON Schema, so we default to empty dict if unsure
                    # or wrap them if they look like simple key-values.
                    # For now, we trust the plugin author or provide a permissive schema.
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

        # 6. Filter Tools based on Policy
        final_tools = []
        strategy = policy.get("strategy", "all")

        allowed_tools = set(policy.get("allowed_tools", []))
        allowed_tags = set(policy.get("allowed_tags", []))

        for tool in candidate_tools:
            t_name = tool["function"]["name"]
            t_tags = set(tool_tags_map.get(t_name, []))

            # Mobile Check (Global Safety)
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
            if source == "mobile" and any(
                kw in t_name.lower() for kw in sensitive_tool_keywords
            ):
                print(f"[安全] 为移动端过滤敏感工具: {t_name}")
                continue

            # Vision Check
            if enable_vision and t_name == "screen_ocr":
                continue
            if t_name in ["take_screenshot", "see_screen"] and not enable_vision:
                # Modify description for non-vision mode
                tool["function"][
                    "description"
                ] = "获取当前屏幕的视觉分析报告。系统将调用视觉 MCP 服务器分析屏幕内容并返回详细的文字描述。当你需要了解屏幕上的视觉信息、或出于好奇想看看主人在做什么但无法直接看到图片时，请使用此工具。"
                if "count" in tool["function"]["parameters"]["properties"]:
                    tool["function"]["parameters"]["properties"]["count"][
                        "description"
                    ] = "获取截图并分析的数量。在非多模态模式下，建议设为 1。"

            is_allowed = False
            if strategy == "all":
                is_allowed = True
            elif strategy == "whitelist":
                # Only 2 ways to allow: by exact name or by tag
                if t_name in allowed_tools:
                    is_allowed = True
                elif not t_tags.isdisjoint(allowed_tags):
                    is_allowed = True  # Overlap exists

            if is_allowed:
                final_tools.append(tool)

        dynamic_tools = final_tools
        print(
            f"[Agent] 最终工具列表 ({len(dynamic_tools)}): {[t['function']['name'] for t in dynamic_tools]}"
        )

        # --- Create Whitelist for NIT Security ---
        allowed_tool_names = [t["function"]["name"] for t in dynamic_tools]

        # [Refactor] Save calculated tools to context to avoid duplication
        context["dynamic_tools"] = dynamic_tools
        context["mcp_clients"] = mcp_clients
        context["mcp_tool_map"] = mcp_tool_map
        context["allowed_tool_names"] = allowed_tool_names

        # [Refactor] 移除 AgentService 中手动拼接工具描述的逻辑
        # 该职责已移交回 PromptManager，它将根据 Context 中的 dynamic_tools 自动生成

        # 2. 运行预处理器管道
        if on_status:
            await on_status("thinking", "正在整理记忆和思绪...")
        context = await self.preprocessor_manager.process(context)

        # 3. 提取结果
        user_message = context.get("user_message", "")
        final_messages = context.get("final_messages", [])
        # config = context.get("llm_config", {}) # 已提前加载

        # [功能] 系统触发指令

        if system_trigger_instruction:
            print(f"[Agent] 追加系统触发指令: {system_trigger_instruction}")
            final_messages.append(
                {"role": "system", "content": system_trigger_instruction}
            )
            if not user_message:
                user_message = f"【系统触发】{system_trigger_instruction}"

        # [功能] 移动端来源感知
        if source == "mobile":
            mobile_instruction = self.mdp.render("components/context/mobile")
            final_messages.append({"role": "system", "content": mobile_instruction})
            print("[Agent] 已注入移动端来源感知。")

        # [功能] 活跃窗口注入
        # 注入当前活跃窗口列表，防止 AI 幻觉（以为应用已打开）
        # [Fix] Social/Mobile 模式下不注入 PC 窗口信息，防止上下文混淆
        if source not in ["social", "mobile"]:
            try:
                active_windows = get_active_windows()
                if isinstance(active_windows, list) and active_windows:
                    # 限制数量以避免 Token 爆炸
                    window_list_str = "\n".join(active_windows[:20])
                    if len(active_windows) > 20:
                        window_list_str += f"\n... ({len(active_windows) - 20} more)"

                    state_msg = self.mdp.render(
                        "components/context/active_windows",
                        {"window_list_str": window_list_str},
                    )

                    # 追加到消息 (System role)
                    final_messages.append({"role": "system", "content": state_msg})
            except Exception as e:
                print(f"[Agent] 注入活跃窗口失败: {e}")

        # 如果配置缺失，回退 (如果 ConfigPreprocessor 运行则不应发生)
        if not config:
            config = await self._get_llm_config()

        print(f"[Agent] 通过预处理器构建 Prompt。消息数: {len(final_messages)}")

        llm = LLMService(
            api_key=config.get("api_key"),
            api_base=config.get("api_base"),
            model=config.get("model"),
            provider=config.get("provider", "openai"),
        )
        temperature = config.get("temperature", 0.7)

        # [Refactor] Retrieve pre-calculated tools from context
        dynamic_tools = context.get("dynamic_tools", [])
        mcp_clients = context.get("mcp_clients", [])
        mcp_tool_map = context.get("mcp_tool_map", {})
        allowed_tool_names = context.get("allowed_tool_names", [])

        print(
            f"[Agent] 使用预计算工具列表 ({len(dynamic_tools)}): {[t['function']['name'] for t in dynamic_tools]}"
        )

        # --- Native Tools Config ---
        disable_native_tools_config = (
            await self.session.exec(
                select(Config).where(Config.key == "disable_native_tools")
            )
        ).first()
        disable_native_tools = (
            disable_native_tools_config.value.lower() == "true"
            if disable_native_tools_config
            else False
        )
        tools_to_pass = None if disable_native_tools else dynamic_tools
        if disable_native_tools:
            print("[Agent] 原生工具 (Function Calling) 已通过配置禁用。")

        full_response_text = ""
        accumulated_full_response = (
            ""  # 用于保存完整的对话记录（包含所有 ReAct 轮次的思考过程）
        )
        pair_id = str(uuid.uuid4())  # 生成原子性绑定ID

        # --- ReAct Loop Configuration ---
        turn_count = 0
        MAX_TURNS = 30  # [Safety] Limit max turns to prevent infinite loops (was 9999)
        consecutive_error_count = 0  # 连续错误计数器

        # 注册任务管理器 (如果 session_id 存在)
        if session_id:
            task_manager.register(session_id)

        try:
            while turn_count < MAX_TURNS:
                # 1. 检查暂停状态
                if session_id:
                    # 如果暂停，这里会阻塞等待
                    await task_manager.check_pause(session_id)

                    # 2. 检查是否有用户注入的指令
                    injected = task_manager.get_injected_instruction(session_id)
                    if injected:
                        print(f"[Agent] 检测到注入指令: {injected}")
                        final_messages.append(
                            {"role": "user", "content": f"【主人即时指令】: {injected}"}
                        )
                        # 注入指令后，直接进入下一轮思考，带上新的上下文

                turn_count += 1
                current_turn_text = ""
                has_tool_calls_in_this_turn = False
                collected_tool_calls = []  # 用于收集本轮流式返回的工具调用片段

                if on_status:
                    await on_status("thinking", f"正在思考 (第 {turn_count} 轮)...")
                print(f"[Agent] 开始 LLM 流 (第 {turn_count} 轮)...")

                # Define Raw Stream Generator
                async def raw_stream_source():
                    nonlocal current_turn_text, full_response_text, has_tool_calls_in_this_turn, collected_tool_calls

                    async for delta in llm.chat_stream_deltas(
                        final_messages, temperature=temperature, tools=tools_to_pass
                    ):
                        # Debug Log: Print delta content
                        # print(f"[Agent] Stream Delta: {delta}")

                        # 1. 处理文本内容 (Content)
                        content = delta.get("content", "")
                        if content:
                            current_turn_text += content
                            full_response_text += content
                            yield content

                        # 2. 处理工具调用片段 (Tool Calls Delta)
                        if "tool_calls" in delta:
                            has_tool_calls_in_this_turn = True
                            for tc_delta in delta["tool_calls"]:
                                idx = tc_delta.get("index", 0)
                                while len(collected_tool_calls) <= idx:
                                    collected_tool_calls.append(
                                        {
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""},
                                        }
                                    )

                                target = collected_tool_calls[idx]
                                if "id" in tc_delta:
                                    target["id"] = tc_delta["id"]
                                if "function" in tc_delta:
                                    fn_delta = tc_delta["function"]
                                    if "name" in fn_delta:
                                        target["function"]["name"] = fn_delta["name"]
                                    if "arguments" in fn_delta:
                                        target["function"]["arguments"] += fn_delta[
                                            "arguments"
                                        ]

                # Debug Log: After stream
                if has_tool_calls_in_this_turn:
                    print(
                        f"[Agent] 收集到工具调用: {json.dumps(collected_tool_calls, ensure_ascii=False)}"
                    )
                else:
                    print(f"[Agent] 第 {turn_count} 轮未检测到工具调用")

                # Apply Postprocessor Pipeline
                # 如果 source 是 'ide' 或 'desktop' 或 'social'，则跳过 NIT 过滤，以便前端显示工具调用或后端直接处理
                processed_stream = self.postprocessor_manager.process_stream(
                    raw_stream_source(),
                    context={
                        "source": source,
                        "session_id": session_id,
                        "skip_nit_filter": (source in ["ide", "desktop", "social"]),
                    },
                )

                async for content in processed_stream:
                    yield content

                # Check if turn is finished
                if not has_tool_calls_in_this_turn:
                    # No tools called, this is the final answer

                    # === NIT Dispatcher Integration (Unified Flow) ===
                    # 检查是否有 NIT 调用指令，如果有则执行并进入下一轮
                    if full_response_text and full_response_text.strip():
                        # 注意：这里我们尝试执行 NIT，如果有结果，说明模型试图调用工具
                        nit_results = await self._save_parsed_metadata(
                            full_response_text,
                            source,
                            mcp_clients,
                            execute_nit=True,
                            expected_nit_id=current_nit_id,
                            allowed_tools=allowed_tool_names,
                        )

                        if nit_results:
                            print(
                                f"[Agent] 检测到 {len(nit_results)} 个 NIT 调用。继续对话循环。"
                            )

                            # 1. 将当前回复（包含 NIT 指令）追加到历史
                            # [Safety] Truncate extremely long responses to prevent context window explosion
                            safe_response_text = full_response_text
                            if len(safe_response_text) > 50000:
                                safe_response_text = (
                                    safe_response_text[:50000]
                                    + "\n...(truncated by system for safety)"
                                )
                                print(
                                    f"⚠️ [Agent] 响应已从 {len(full_response_text)} 截断为 50000 字符。"
                                )

                            final_messages.append(
                                {"role": "assistant", "content": safe_response_text}
                            )

                            # 2. 构造 Observation 消息
                            obs_text = "【系统通知：NIT工具执行反馈】\n"
                            has_screenshot_request = False
                            should_terminate_nit_loop = False

                            for res in nit_results:
                                out_str = str(res["output"])

                                # [Feature] Real-time Status Sync for NIT
                                # Check if the result contains state triggers (JSON)
                                try:
                                    if "triggers" in out_str or '"mood"' in out_str:
                                        import json

                                        # Try to parse the output as JSON
                                        # It might be wrapped in text, but if it's a direct return from tool it's usually JSON string
                                        # We look for a JSON object structure
                                        start_idx = out_str.find("{")
                                        end_idx = out_str.rfind("}")
                                        if start_idx != -1 and end_idx != -1:
                                            json_str = out_str[start_idx : end_idx + 1]
                                            data = json.loads(json_str)

                                            # If it has 'state' or 'triggers', broadcast it
                                            triggers = None
                                            if "triggers" in data:
                                                triggers = data["triggers"]
                                            elif "state" in data:
                                                triggers = data["state"]
                                            elif "mood" in data:  # Direct state object
                                                triggers = data

                                            if triggers:
                                                print(
                                                    f"[Agent] Detected state update in NIT result: {triggers}"
                                                )
                                                # 1. Push SSE
                                                sse_payload = json.dumps(
                                                    {"triggers": triggers},
                                                    ensure_ascii=False,
                                                )
                                                yield f"data: {sse_payload}\n\n"

                                                # 2. Broadcast via RealtimeSessionManager
                                                try:
                                                    from services.realtime_session_manager import (
                                                        realtime_session_manager,
                                                    )

                                                    await realtime_session_manager.broadcast(
                                                        {
                                                            "type": "triggers",
                                                            "data": triggers,
                                                        }
                                                    )
                                                except Exception:
                                                    pass
                                except Exception as e:
                                    print(
                                        f"[Agent] Failed to parse state update from NIT result: {e}"
                                    )

                                if len(out_str) > 2000:
                                    out_str = out_str[:2000] + "...(truncated)"

                                # --- 优化反馈文案与状态判定 ---
                                display_name = res["plugin"]
                                if display_name == "NIT_Script" and res.get(
                                    "executed_tools"
                                ):
                                    # 如果是脚本块，列出主要执行的工具
                                    display_name = (
                                        f"NIT 脚本: {', '.join(res['executed_tools'])}"
                                    )

                                # 启发式判定：如果输出以错误标识开头，或者包含“未找到插件”，则视为失败
                                is_actually_success = res["status"] == "success"
                                if is_actually_success:
                                    error_indicators = [
                                        "错误:",
                                        "⚠️",
                                        "未找到插件",
                                        "权限拒绝",
                                        "Error:",
                                    ]
                                    if (
                                        any(
                                            out_str.startswith(ind)
                                            for ind in error_indicators
                                        )
                                        or "未找到插件" in out_str
                                    ):
                                        is_actually_success = False
                                        # 同步更新 res['status'] 以便后续逻辑（如熔断、反思）能识别
                                        res["status"] = "error"

                                icon = "✅" if is_actually_success else "❌"
                                status_text = (
                                    "执行完成" if is_actually_success else "执行失败"
                                )

                                obs_text += f"{icon} 工具 [{display_name}] {status_text}。\n结果:\n{out_str}\n\n"
                                # ----------------------------

                                if res[
                                    "plugin"
                                ] == "finish_task" or "finish_task" in res.get(
                                    "executed_tools", []
                                ):
                                    should_terminate_nit_loop = True

                                    # [Fix] Extract summary from output if available and yield it
                                    # finish_task output format: "[System] Task finished... Summary: {summary}"
                                    output_str = str(res.get("output", ""))
                                    if "Summary: " in output_str:
                                        try:
                                            summary_part = output_str.split(
                                                "Summary: ", 1
                                            )[1]
                                            # Append to full_response_text so it gets saved
                                            full_response_text += summary_part
                                            # Yield to frontend
                                            yield summary_part
                                        except Exception as e:
                                            print(
                                                f"[Agent] Failed to extract summary from finish_task: {e}"
                                            )

                                # 宽松匹配截图请求 (处理大小写和别名)
                                plugin_name_lower = res["plugin"].lower()
                                executed_tools = res.get("executed_tools", [])

                                # 检查 plugin 字段或 executed_tools 列表
                                is_screenshot = (
                                    "screenshot" in plugin_name_lower
                                    or "see_screen" in plugin_name_lower
                                )
                                if not is_screenshot and executed_tools:
                                    for t in executed_tools:
                                        t_lower = t.lower()
                                        if (
                                            "screenshot" in t_lower
                                            or "see_screen" in t_lower
                                        ):
                                            is_screenshot = True
                                            break

                                # 支持 'screenshot', 'see_screen' 等关键词
                                if is_screenshot and res["status"] == "success":
                                    has_screenshot_request = True
                                    print(
                                        f"[Agent] 在 NIT 中检测到截图请求: {res['plugin']} (工具: {executed_tools})"
                                    )

                            # 3. 根据是否有多模态需求构造消息内容
                            enable_vision = config.get("enable_vision", False)
                            message_content = [{"type": "text", "text": obs_text}]

                            if has_screenshot_request and enable_vision:
                                try:
                                    print("[Agent] 正在为 NIT 调用注入截图...")
                                    from services.screenshot_service import (
                                        screenshot_manager,
                                    )

                                    # 强制捕获最新截图
                                    screenshot_data = screenshot_manager.capture()
                                    if screenshot_data:
                                        # 注入图片
                                        message_content.append(
                                            {
                                                "type": "image_url",
                                                "image_url": {
                                                    "url": f"data:image/png;base64,{screenshot_data['base64']}"
                                                },
                                            }
                                        )
                                        # 更新文本提示，带上时间戳以区分旧图
                                        capture_time = screenshot_data.get(
                                            "time_str",
                                            datetime.now().strftime("%H:%M:%S"),
                                        )
                                        obs_text += f"\n[系统] 已附带最新屏幕截图 (Time: {capture_time})。"
                                        message_content[0]["text"] = obs_text
                                        print(
                                            f"[Agent] 截图注入成功。时间: {capture_time}"
                                        )
                                    else:
                                        print("[Agent] 截图捕获返回 None。")
                                        obs_text += (
                                            "\n[系统] 尝试截图失败：无法获取图像数据。"
                                        )
                                        message_content[0]["text"] = obs_text
                                except Exception as e:
                                    print(f"[Agent] 为 NIT 注入截图失败: {e}")
                                    import traceback

                                    traceback.print_exc()
                                    obs_text += f"\n[系统] 尝试截图失败: {e}"
                                    message_content[0]["text"] = obs_text

                            final_messages.append(
                                {"role": "user", "content": message_content}
                            )

                            # 4. 检查连续错误熔断
                            has_error = any(
                                res["status"] == "error" for res in nit_results
                            )
                            if has_error:
                                consecutive_error_count += 1
                                print(
                                    f"[Agent] 检测到 NIT 工具错误。连续次数: {consecutive_error_count}"
                                )
                            else:
                                consecutive_error_count = 0

                            if consecutive_error_count >= 3:
                                print(
                                    f"⚠️ [Agent] NIT 连续错误 ({consecutive_error_count}) 达到上限。强制停止。"
                                )
                                final_messages.append(
                                    {
                                        "role": "system",
                                        "content": "【系统紧急干预】监测到你已经连续操作失败 3 次。请立即停止任何后续的思考与工具调用，放弃当前任务，并主动向主人汇报失败原因。",
                                    }
                                )
                                # 禁用后续工具调用
                                tools_to_pass = None

                            # 4.1 触发反思 (如果出错)
                            if has_error:
                                print("⚠️ [Agent] 检测到 NIT 工具执行错误，触发反思...")
                                history_context = "\n".join(
                                    [
                                        f"{m['role']}: {str(m.get('content',''))[:200]}"
                                        for m in final_messages[-5:]
                                    ]
                                )
                                # 尝试获取最新截图供反思使用
                                latest_screenshot = None
                                try:
                                    from services.screenshot_service import (
                                        screenshot_manager,
                                    )

                                    shot = screenshot_manager.capture()
                                    if shot:
                                        latest_screenshot = shot["base64"]
                                except Exception:
                                    pass

                                reflection_advice = await self._run_reflection(
                                    user_message, history_context, latest_screenshot
                                )

                                if (
                                    reflection_advice
                                    and "NORMAL" not in reflection_advice
                                ):
                                    final_messages.append(
                                        {
                                            "role": "system",
                                            "content": f"[反思助手提示]: 检测到上一步操作可能存在问题。建议参考：{reflection_advice}",
                                        }
                                    )

                            # 5. 重置状态，准备下一轮
                            accumulated_full_response += full_response_text + "\n"
                            full_response_text = ""
                            current_turn_text = ""
                            collected_tool_calls = []
                            has_tool_calls_in_this_turn = False

                            if should_terminate_nit_loop:
                                print("[Agent] NIT 循环由 finish_task 终止。")
                                break

                            # 4. 继续循环
                            continue

                    if turn_count == 1 and not full_response_text.strip():
                        print("[Agent] 流结束，无任何增量。")
                        self._log_to_file("流结束，无任何增量。")
                        err_msg = (
                            "⚠️ AI 没有返回有效内容。请检查网络连接或 API Key 配置。"
                        )
                        full_response_text = err_msg
                        yield err_msg
                    break

                # --- Tool Execution Phase ---
                # 1. Append Assistant Message (Thought + Tool Calls) to history
                # [Safety] Truncate extremely long thought process
                safe_turn_text = current_turn_text if current_turn_text else None
                if safe_turn_text and len(safe_turn_text) > 50000:
                    safe_turn_text = (
                        safe_turn_text[:50000] + "\n...(truncated by system for safety)"
                    )

                assistant_msg = {
                    "role": "assistant",
                    "content": safe_turn_text,
                    "tool_calls": collected_tool_calls,
                }
                final_messages.append(assistant_msg)

                # 2. Execute Tools
                intercepted_ui_data = {}  # 存储 tool_name -> raw_data
                should_terminate_loop = False

                for tool_call in collected_tool_calls:
                    function_name = tool_call["function"]["name"]
                    args_str = tool_call["function"]["arguments"] or "{}"
                    arg_parsing_error = None
                    try:
                        function_args = json.loads(args_str)
                    except json.JSONDecodeError as e:
                        # 尝试处理 "Extra data" (例如模型输出了多个 JSON 对象)
                        try:
                            function_args, _ = json.JSONDecoder().raw_decode(args_str)
                            print(
                                f"[Agent] 从额外数据错误中恢复。解析结果: {function_args}"
                            )
                        except Exception:
                            print(f"[Agent] 解析工具参数失败: {args_str}, 错误: {e}")
                            arg_parsing_error = f"Failed to parse arguments: {str(e)}"
                            function_args = {}
                    except Exception as e:
                        print(f"[Agent] 解析工具参数失败: {args_str}, 错误: {e}")
                        arg_parsing_error = f"Failed to parse arguments: {str(e)}"
                        function_args = {}

                    # 如果参数解析失败，直接生成错误响应，不执行函数
                    if arg_parsing_error:
                        final_messages.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "name": function_name,
                                "content": f"错误: {arg_parsing_error}。请确保参数是有效的 JSON。",
                            }
                        )
                        continue

                    # --- Tool Execution Strategy ---
                    # 1. Security Gate: 硬拦截机制 (Hard Isolation)
                    # 即使模型“猜”到了工具名，或者通过恶意脚本注入，只要来源是手机，就禁止执行敏感工具
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
                    if source == "mobile" and any(
                        kw in function_name.lower() for kw in sensitive_tool_keywords
                    ):
                        print(
                            f"[🛡️ 安全拦截] 已拦截来自移动端对敏感工具 '{function_name}' 的执行。"
                        )
                        final_messages.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "name": function_name,
                                "content": f"错误：权限拒绝。出于安全原因，工具 '{function_name}' 被限制远程/移动连接使用。",
                            }
                        )
                        continue

                    # 2. Interceptors: Handle tools with special UI/Context requirements first
                    # 3. NIT Dispatcher: Unified execution for all other plugins

                    if function_name == "finish_task":
                        print(
                            f"[Agent] finish_task 被调用。状态: {function_args.get('status', 'success')}"
                        )
                        summary = function_args.get("summary", "")
                        if summary:
                            full_response_text += summary
                            yield summary

                        final_messages.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "name": function_name,
                                "content": "任务已完成。终止循环。",
                            }
                        )
                        should_terminate_loop = True
                        break

                    if function_name == "search_files":
                        print(f"[Agent] 拦截 {function_name} 调用以进行 UI 注入...")
                        if on_status:
                            await on_status("thinking", "正在处理大数据量任务...")

                        try:
                            # Use legacy mapping or NIT dispatcher to get raw data
                            # Here we use legacy mapping for safety as it returns raw list/dict
                            func = TOOLS_MAPPING[function_name]
                            if asyncio.iscoroutinefunction(func):
                                raw_data = await func(**function_args)
                            else:
                                raw_data = func(**function_args)

                            tag_name = "FILE_RESULTS"
                            intercepted_ui_data[tag_name] = raw_data

                            # 辅助模型分析
                            aux_analysis = None
                            try:
                                data_list = json.loads(raw_data)
                                if isinstance(data_list, list) and len(data_list) > 0:
                                    if on_status:
                                        await on_status(
                                            "thinking", "正在分析搜索结果..."
                                        )
                                    aux_analysis = (
                                        await self._analyze_file_results_with_aux(
                                            user_message, data_list
                                        )
                                    )
                            except Exception as e:
                                print(f"[Agent] 触发辅助分析失败: {e}")

                            try:
                                data_list = json.loads(raw_data)
                                count = (
                                    len(data_list) if isinstance(data_list, list) else 1
                                )
                            except Exception:
                                count = "若干"

                            aux_msg = ""
                            if aux_analysis:
                                aux_msg = f"\n\n[辅助模型分析结果]:\n{aux_analysis}"

                            function_response = f"System: 已成功处理。获取到 {count} 条数据，UI 列表已在后台准备就绪。{aux_msg}\n请结合辅助模型的分析结果（如果有），告知用户你已经处理完成，并可以简要复述分析结论。"
                            print(
                                f"[Agent] {function_name} 已拦截。{count} 项已从 LLM 上下文中隐藏。"
                            )
                        except Exception as e:
                            function_response = f"拦截工具执行期间出错: {e}"

                        final_messages.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            }
                        )
                        continue

                    elif (
                        function_name == "take_screenshot"
                        or function_name == "see_screen"
                    ):
                        print(f"[Agent] 调用工具: {function_name}")

                        # 根据多模态状态决定执行逻辑
                        enable_vision = config.get("enable_vision", False)

                        if not enable_vision:
                            # 非多模态模式：尝试调用 MCP 视觉分析
                            if on_status:
                                await on_status(
                                    "thinking", "正在通过 MCP 分析屏幕内容..."
                                )
                            vision_description = await self._analyze_screen_with_mcp()

                            function_response = f"[视觉分析报告]:\n{vision_description}"
                            print("[Agent] MCP 视觉分析完成。")
                        else:
                            # 多模态模式：直接注入截图
                            if on_status:
                                await on_status("thinking", "正在查看截图池...")
                            try:
                                from services.screenshot_service import (
                                    screenshot_manager,
                                )

                                # 1. 获取请求的数量
                                count = function_args.get("count", 1)
                                if not isinstance(count, int):
                                    count = 1
                                count = max(1, min(10, count))

                                # 2. 捕获最新截图
                                # 强制捕获一张最新的，确保“所见即所得”，避免读取缓存池中的旧图
                                latest_shot = screenshot_manager.capture()

                                final_screenshots = []

                                if count == 1:
                                    # 如果只需要一张，直接使用刚刚捕获的这张，确保最新
                                    if latest_shot:
                                        final_screenshots = [latest_shot]
                                else:
                                    # 如果需要多张（回溯），则从池子中取
                                    # 使用较短的有效期（如 15 秒），确保获取到的是刚刚截取的
                                    recent_screenshots = screenshot_manager.get_recent(
                                        count, max_age=15
                                    )
                                    final_screenshots = recent_screenshots

                                if not final_screenshots:
                                    function_response = (
                                        "❌ 无法获取最新截图（可能截图失败）。"
                                    )
                                else:
                                    # 3. 将截图注入到下一轮的上下文中
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
                                                "text": f"--- 截图 {i+1} (捕获时间: {shot['time_str']}) ---",
                                            }
                                        )
                                        content.append(
                                            {
                                                "type": "image_url",
                                                "image_url": {
                                                    "url": f"data:image/png;base64,{shot['base64']}"
                                                },
                                            }
                                        )

                                    screenshot_msg = {
                                        "role": "user",
                                        "content": content,
                                    }
                                    final_messages.append(screenshot_msg)
                                    print(
                                        f"[Agent] {len(final_screenshots)} 张截图已注入上下文。(最新: {final_screenshots[-1]['time_str']})"
                                    )

                                    function_response = f"已成功获取并发送了最近的 {len(final_screenshots)} 张截图。请查看最新的消息中的图片进行分析。"
                            except Exception as e:
                                function_response = f"截图工具执行出错: {e}"

                        final_messages.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            }
                        )
                        continue

                    # --- NIT Dispatcher Integration ---
                    from nit_core.dispatcher import get_dispatcher

                    nit_dispatcher = get_dispatcher()

                    # 归一化工具名
                    normalized_name = nit_dispatcher.parser.normalize_key(function_name)

                    # 信任 Dispatcher 的注册表
                    if normalized_name in nit_dispatcher.list_plugins():
                        print(
                            f"[Agent] 将工具 {function_name} 委托给 NITDispatcher (统一流)..."
                        )
                        if on_status:
                            await on_status(
                                "thinking", f"正在调用能力: {function_name}..."
                            )

                        try:
                            # NIT 插件统一接口：接收 params 字典
                            result = await nit_dispatcher._execute_plugin(
                                function_name, function_args
                            )

                            # 如果结果是复杂对象，Dispatcher 里的插件应该已经处理成了字符串或特定结构
                            # 这里我们只负责转为字符串回传给 LLM
                            function_response = str(result)
                            print(f"[Agent] NIT 工具 {function_name} 执行成功。")

                            # [Feature] 实时状态同步
                            # 如果是 update_character_status 或 finish_task，解析其返回的 triggers 并立即推送到前端
                            if function_name in [
                                "update_character_status",
                                "update_status",
                                "set_status",
                                "finish_task",
                            ]:
                                try:
                                    import json

                                    # 注意：finish_task 返回的是 "[System] Task finished..." 字符串，可能不包含 JSON triggers
                                    # 但如果是 update_character_status 的别名调用，或者我们在 finish_task 里返回了 triggers
                                    # 实际上 task_lifecycle.py 内部已经做了广播，这里的逻辑主要是为了 SSE 推送 (如果是 SSE 连接的话)
                                    # 对于 finish_task，通常意味着对话结束，可能不需要在这里再次推送 triggers，因为 task_lifecycle.py 已经广播了
                                    # 不过为了保险起见，如果 result 是 dict (triggers)，我们才推送
                                    if isinstance(result, dict) or (
                                        isinstance(result, str)
                                        and result.strip().startswith("{")
                                    ):
                                        triggers = (
                                            result
                                            if isinstance(result, dict)
                                            else json.loads(str(result))
                                        )

                                        # 1. 构造 SSE 格式的 JSON 数据
                                        sse_payload = json.dumps(
                                            {"triggers": triggers}, ensure_ascii=False
                                        )
                                        sse_message = f"data: {sse_payload}\n\n"

                                        # 2. 推送到前端 (通过 yield SSE)
                                        yield sse_message

                                        # 3. 尝试广播给 RealtimeSessionManager (双保险，适用于语音模式)
                                        try:
                                            from services.realtime_session_manager import (
                                                realtime_session_manager,
                                            )

                                            await realtime_session_manager.broadcast(
                                                {"type": "triggers", "data": triggers}
                                            )
                                        except Exception:
                                            pass

                                        print(
                                            f"[Agent] 状态更新已推送到前端: {sse_payload[:50]}..."
                                        )
                                except Exception:
                                    # finish_task 返回普通字符串时会进入这里，这是正常的，忽略即可
                                    pass

                            # 特殊处理：如果是 search_files，且返回结果很大，可能需要截断或由辅助模型处理
                            # 思路是插件内部自己处理好返回内容
                            # 这里保留一个简单的截断保护
                            if len(function_response) > 10000:
                                function_response = (
                                    function_response[:10000]
                                    + "\n... (result truncated)"
                                )

                        except Exception as e:
                            print(f"[Agent] NIT 工具 {function_name} 失败: {e}")
                            function_response = f"执行工具出错: {e}"

                        final_messages.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "name": function_name,
                                "content": function_response,
                            }
                        )
                        continue

                    # --- MCP Tool Handling ---
                    if function_name.startswith("mcp_") and mcp_tool_map:
                        real_tool_name = function_name[4:]
                        client = mcp_tool_map.get(function_name)
                        if not client:
                            print(f"[Agent] 映射中未找到 MCP 工具 {function_name}")
                            mcp_response = f"错误: 未找到 MCP 工具 {function_name}。"
                        else:
                            print(
                                f"[Agent] 调用 MCP 工具: {real_tool_name} (在 {client.name} 上)"
                            )
                            if on_status:
                                await on_status(
                                    "thinking",
                                    f"正在调用插件 ({client.name}): {real_tool_name}...",
                                )

                            import time

                            start_time = time.time()
                            try:
                                mcp_response = await client.call_tool(
                                    real_tool_name, function_args
                                )
                                duration = time.time() - start_time
                                print(
                                    f"[Agent] MCP 工具 {real_tool_name} 执行耗时 {duration:.2f}s"
                                )
                            except Exception as e:
                                print(f"[Agent] MCP 工具 {real_tool_name} 失败: {e}")
                                mcp_response = f"Error: {e}"

                        final_messages.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "name": function_name,
                                "content": str(mcp_response),
                            }
                        )

                    else:
                        # --- Fallback for Unknown Tools ---
                        print(
                            f"[Agent] 在 NIT 注册表或 MCP 中未找到工具 {function_name}。"
                        )
                        final_messages.append(
                            {
                                "tool_call_id": tool_call["id"],
                                "role": "tool",
                                "name": function_name,
                                "content": f"Error: Tool '{function_name}' not found or not supported.",
                            }
                        )

                # 3. 触发按需反思机制
                last_tool_response = final_messages[-1].get("content", "")
                is_tool_error = (
                    "error" in str(last_tool_response).lower()
                    or "fail" in str(last_tool_response).lower()
                )

                if is_tool_error:
                    consecutive_error_count += 1
                    print(
                        f"[Agent] 检测到工具错误。连续次数: {consecutive_error_count}"
                    )
                else:
                    consecutive_error_count = 0

                # [Feature] 连续错误 3 次熔断机制
                if consecutive_error_count >= 3:
                    print(
                        f"⚠️ [Agent] 连续错误 ({consecutive_error_count}) 达到上限。强制停止。"
                    )
                    final_messages.append(
                        {
                            "role": "system",
                            "content": "【系统紧急干预】监测到你已经连续操作失败 3 次。请立即停止任何后续的思考与工具调用，放弃当前任务，并主动向主人汇报失败原因。",
                        }
                    )
                    # 禁用工具，强制 LLM 只能回复文本
                    tools_to_pass = None

                if is_tool_error:
                    print("⚠️ [Agent] 检测到工具执行错误，触发反思...")
                    history_context = "\n".join(
                        [
                            f"{m['role']}: {str(m.get('content',''))[:200]}"
                            for m in final_messages[-5:]
                        ]
                    )
                    # 尝试获取最新截图供反思使用
                    latest_screenshot = None
                    try:
                        from services.screenshot_service import screenshot_manager

                        shot = screenshot_manager.capture()
                        if shot:
                            latest_screenshot = shot["base64"]
                    except Exception:
                        pass

                    reflection_advice = await self._run_reflection(
                        user_message, history_context, latest_screenshot
                    )

                    if reflection_advice and "NORMAL" not in reflection_advice:
                        final_messages.append(
                            {
                                "role": "system",
                                "content": f"[反思助手提示]: 检测到上一步操作可能存在问题。建议参考：{reflection_advice}",
                            }
                        )

                # 4. Yield UI Tags Immediately
                if intercepted_ui_data:
                    for tag_name, raw_json in intercepted_ui_data.items():
                        tag = f"\n<{tag_name}>{raw_json}</{tag_name}>"
                        full_response_text += tag
                        yield tag
                        print(f"[Agent] 已向响应追加隐藏标签 {tag_name}。")

                if should_terminate_loop:
                    print("[Agent] 循环由 finish_task 终止。")
                    break

                # Loop continues to next turn...

            try:
                # 5. 最终合并所有轮次的内容用于持久化
                full_response_text = accumulated_full_response + full_response_text

                # Capture raw text before post-processing
                raw_full_text = full_response_text

                # Post-process full response text (Batch mode) before saving
                # This ensures memory and downstream services get clean text without protocol markers
                if full_response_text:
                    try:
                        full_response_text = await self.postprocessor_manager.process(
                            full_response_text,
                            context={"source": source, "session_id": session_id},
                        )
                    except Exception as pp_e:
                        print(f"[Agent] 后处理器失败: {pp_e}。使用原始文本。")

                # Broadcast LLM response to frontend via Gateway
                # [Modified] Allow 'ide' source to also broadcast to Pet (Desktop Pet should react to IDE chat)
                if not is_voice_mode and source in ["desktop", "ide"]:
                    from services.gateway_client import gateway_client

                    await gateway_client.broadcast_text_response(full_response_text)

                    # Trigger TTS (Text Mode)
                    # [Fix] Explicitly check source again to be safe (though source=="desktop" covers it)
                    asyncio.create_task(
                        self._generate_and_stream_tts(full_response_text)
                    )

                # 仅在正常生成回复（且不是报错）时才保存对话记录
                # 用户消息与 Pero 回复进行原子性绑定保存

                # [Robustness] Fallback extraction for user_message if missing
                if not user_message:
                    # Priority 1: Check override (Voice Mode)
                    if user_text_override:
                        user_message = user_text_override
                        print(
                            f"[Agent] 用户消息已从覆盖中恢复: '{user_message[:20]}...'"
                        )
                    else:
                        # Priority 2: Search in messages
                        print(
                            f"[Agent] 用户消息缺失。正在 {len(messages)} 条输入消息中搜索..."
                        )
                        for m in reversed(messages):
                            if m.get("role") == "user":
                                content = m.get("content", "")
                                if isinstance(content, str):
                                    user_message = content
                                elif isinstance(content, list):
                                    texts = [
                                        item["text"]
                                        for item in content
                                        if item.get("type") == "text"
                                    ]
                                    user_message = " ".join(texts)
                                break
                        if user_message:
                            print(
                                f"[Agent] 回退提取的用户消息: '{user_message[:20]}...'"
                            )
                        else:
                            print(
                                "[Agent] 严重: 无法从输入中提取用户消息。日志将不会被保存。"
                            )

                # [Feature] User Image Persistence (Fire and Forget)
                user_metadata = {}
                try:
                    target_msg = None
                    for m in reversed(messages):
                        if m.get("role") == "user":
                            target_msg = m
                            break

                    if target_msg and isinstance(target_msg.get("content"), list):
                        images = []
                        import base64

                        for item in target_msg["content"]:
                            if (
                                isinstance(item, dict)
                                and item.get("type") == "image_url"
                            ):
                                url = item["image_url"]["url"]
                                if url.startswith("data:image"):
                                    try:
                                        header, encoded = url.split(",", 1)
                                        ext = "png"
                                        if "jpeg" in header:
                                            ext = "jpg"
                                        elif "gif" in header:
                                            ext = "gif"
                                        elif "webp" in header:
                                            ext = "webp"

                                        img_data = base64.b64decode(encoded)

                                        current_dir = os.path.dirname(
                                            os.path.abspath(__file__)
                                        )
                                        backend_dir = os.path.dirname(current_dir)
                                        data_dir = os.environ.get(
                                            "PERO_DATA_DIR",
                                            os.path.join(backend_dir, "data"),
                                        )

                                        date_str = datetime.now().strftime("%Y-%m-%d")
                                        upload_dir = os.path.join(
                                            data_dir, "uploads", date_str
                                        )
                                        os.makedirs(upload_dir, exist_ok=True)

                                        filename = f"{uuid.uuid4()}.{ext}"
                                        file_path = os.path.join(upload_dir, filename)

                                        with open(file_path, "wb") as f:
                                            f.write(img_data)

                                        rel_path = f"uploads/{date_str}/{filename}"
                                        images.append(rel_path)
                                    except Exception as img_e:
                                        print(f"[Agent] 保存图片失败: {img_e}")

                        if images:
                            user_metadata["images"] = images
                            print(f"[Agent] 已持久化 {len(images)} 张图片用于显示。")
                except Exception as e:
                    print(f"[Agent] 图片处理错误: {e}")

                should_save = not skip_save and user_message and full_response_text
                print(
                    f"[Agent] 日志保存检查: 是否保存={should_save} (跳过保存={skip_save}, 有用户消息={bool(user_message)}, 响应长度={len(full_response_text) if full_response_text else 0})"
                )

                if should_save:
                    # 如果有覆盖文本，优先使用覆盖文本（确保音频输入时也能存下文本）
                    final_user_msg = (
                        user_text_override if user_text_override else user_message
                    )
                    try:
                        await self.memory_service.save_log_pair(
                            self.session,
                            source,
                            session_id,
                            final_user_msg,
                            full_response_text,
                            pair_id,
                            assistant_raw_content=raw_full_text,
                            user_metadata=user_metadata,
                            agent_id=current_agent_id,
                        )
                        print(f"[Agent] 对话日志对已保存 (pair_id: {pair_id})")
                    except Exception as e:
                        print(f"[Agent] 保存日志对失败: {e}")
                else:
                    if not skip_save:
                        print(
                            f"[Agent] 跳过保存。原因: 有用户消息={bool(user_message)}, 响应有效={bool(full_response_text and not full_response_text.startswith('Error:'))}"
                        )

                if full_response_text:
                    await self._save_parsed_metadata(
                        full_response_text,
                        source,
                        mcp_clients if "mcp_clients" in locals() else None,
                        execute_nit=False,
                    )

                # 触发 Scorer 服务进行记忆提取 (职责分离 - 后台异步执行)
                # [Optimization] Do not run scorer if the response is an error
                is_error_response = (
                    full_response_text.startswith("Error:")
                    or full_response_text.startswith("Network Error")
                    or full_response_text.startswith("⚠️")
                )

                if (
                    not skip_save
                    and user_message
                    and full_response_text
                    and not is_error_response
                ):
                    # [Fix] Skip background scorer for social/mobile mode as they have their own logic
                    # 社交模式/移动端有自己独立的总结机制，不需要触发“对话分析师”
                    if source in ["social", "mobile"]:
                        print(f"[Agent] 跳过 {source} 模式的后台分析。")
                    else:
                        final_user_msg = (
                            user_text_override if user_text_override else user_message
                        )
                        if len(full_response_text) > 5:
                            # 使用 background_task 包装以确保独立 Session
                            asyncio.create_task(
                                self._run_scorer_background(
                                    final_user_msg,
                                    full_response_text,
                                    source,
                                    pair_id=pair_id,
                                    agent_id=current_agent_id,
                                )
                            )

                # 显式提交，确保在流式响应的上下文中数据已持久化
                await self.session.commit()

                # [Trigger Dream] 3% probability to trigger background memory consolidation
                # [Fix] Disable Dream for social/mobile modes
                import random

                if source not in ["social", "mobile"] and random.random() < 0.03:
                    asyncio.create_task(self._trigger_dream(agent_id=current_agent_id))

            except Exception as log_err:
                print(f"保存对话日志失败 (成功路径): {log_err}")

        except Exception as e:
            import traceback

            error_msg = f"Error: {str(e)}"
            print(f"Agent 聊天错误 (内部): {traceback.format_exc()}")

            # [Optimization] Check for "invalid content" errors and handle gracefully
            # If error is about API returning no content, broadcast a toast and DO NOT save to DB
            err_str_lower = str(e).lower()
            is_empty_content_error = (
                "no valid content" in err_str_lower
                or "invalid api response" in err_str_lower
                or "choices array is missing" in err_str_lower
            )

            if is_empty_content_error:
                from services.gateway_client import gateway_client

                asyncio.create_task(
                    gateway_client.broadcast_error(
                        message="API 未返回有效内容，可能是模型正在思考或被截断，请重试。",
                        title="无效响应",
                        error_type="error",
                    )
                )
                # Return early, skip saving log
                return

            # [Troubleshooting] Attempt to save log even on error (User request: logs missing)
            try:
                # Ensure user_message is available
                final_u_msg = user_message
                if not final_u_msg and user_text_override:
                    final_u_msg = user_text_override

                # Append error to response so it's recorded
                final_response = full_response_text + f"\n\n[System Error]: {error_msg}"

                if final_u_msg:
                    await self.memory_service.save_log_pair(
                        self.session,
                        source,
                        session_id,
                        final_u_msg,
                        final_response,
                        pair_id,
                        agent_id=current_agent_id,
                    )
                    print(f"[Agent] 错误日志已保存 (pair_id: {pair_id})")
            except Exception as save_err:
                print(f"[Agent] 保存错误日志失败: {save_err}")

            yield error_msg
        finally:
            if session_id:
                task_manager.unregister(session_id)

            # 最后的兜底处理，清理 MCP 客户端资源
            if "mcp_clients" in locals():
                for client in mcp_clients:
                    try:
                        await client.close()
                    except Exception:
                        pass
            pass

    async def _generate_and_stream_tts(self, text: str):
        """Generate TTS audio and stream it to frontend (Text Mode)"""
        try:
            # Clean text (remove emojis, think tags, etc.)
            import re

            cleaned_text = re.sub(r"[\U00010000-\U0010ffff]", "", text)  # Remove emojis
            cleaned_text = re.sub(r"【.*?】", "", cleaned_text)  # Remove think tags
            cleaned_text = re.sub(r"<.*?>", "", cleaned_text)  # Remove html tags
            cleaned_text = re.sub(r"\*.*?\*", "", cleaned_text)  # Remove actions
            cleaned_text = cleaned_text.strip()

            if not cleaned_text:
                return

            import time
            import uuid

            from peroproto import perolink_pb2
            from services.gateway_client import gateway_client
            from services.tts_service import get_tts_service

            tts_service = get_tts_service()

            # Check if TTS is enabled
            from core.config_manager import get_config_manager

            if not get_config_manager().get("tts_enabled", True):
                return

            # Use default voice params
            audio_path = await tts_service.synthesize(cleaned_text)

            if audio_path:
                # Stream via Gateway
                with open(audio_path, "rb") as f:
                    audio_data = f.read()

                envelope = perolink_pb2.Envelope()
                envelope.id = str(uuid.uuid4())
                envelope.source_id = gateway_client.device_id
                envelope.target_id = "broadcast"
                envelope.timestamp = int(time.time() * 1000)

                envelope.stream.stream_id = str(uuid.uuid4())
                envelope.stream.data = audio_data
                envelope.stream.is_end = True
                envelope.stream.content_type = "audio/mp3"

                await gateway_client.send(envelope)

                # Cleanup
                try:
                    import os

                    os.remove(audio_path)
                except Exception:
                    pass
        except Exception as e:
            print(f"[Agent] TTS 生成失败: {e}")
