import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any, AsyncIterable, Dict, List, Optional

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.component_container import ComponentContainer
from core.nit_manager import get_nit_manager
from interfaces.core import (
    IPostprocessorManager,
    IPreprocessorManager,
    IPromptManager,
)
from interfaces.memory import IMemoryService
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
from services.agent.task_manager import task_manager
from services.core.llm_service import LLMService
from services.core.mcp_service import McpClient
from services.core.session_service import set_current_session_context
from services.memory.scorer_service import ScorerService


class AgentService:
    def __init__(self, session: AsyncSession):
        self.session = session

        # 注入session和agent_id用于工具操作
        from services.agent.agent_manager import get_agent_manager

        agent_id = "pero"
        import contextlib

        with contextlib.suppress(Exception):
            agent_id = get_agent_manager().active_agent_id

        set_current_session_context(session, agent_id)
        self.memory_service = ComponentContainer.get(IMemoryService)
        # 暂时 ScorerService 还需要 session 初始化，这里演示混合模式
        # 如果 ScorerService 也被完全 DI，需要工厂支持参数或上下文
        # 简单起见，这里假设 IScorerService 的实现不需要 session 或能自我获取
        # 但现有实现需要 session。我们先保持原样，或修改接口。
        # 鉴于时间，我们先只替换无状态或单例组件。

        self.scorer_service = ScorerService(
            session
        )  # ComponentContainer.get(IScorerService)

        self.prompt_manager = ComponentContainer.get(IPromptManager)

        # 初始化辅助MDP(集中式)
        self.mdp = self.prompt_manager.mdp

        # 初始化预处理器管道 (从容器获取)
        self.preprocessor_manager = ComponentContainer.get(IPreprocessorManager)

        # 初始化后处理器管道 (从容器获取)
        self.postprocessor_manager = ComponentContainer.get(IPostprocessorManager)

    def _log_to_file(self, msg: str):
        try:
            # 使用绝对路径确保日志在backend目录创建
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
        """使用辅助模型分析文件搜索结果"""
        try:
            # 1. 检查辅助模型启用状态
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

            # 2. 准备提示词 (Prompt)
            # 限制文件数防上下文窗口 (Context Window) 爆炸
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
            # 构造辅助LLMService实例
            # 注意：若配置为全局需获取API Key/Base
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
            # 调试：打印所有配置键
            try:
                keys = (await self.session.exec(select(Config.key))).all()
                print(f"[Vision] 可用的配置键: {keys}", flush=True)
            except Exception as e:
                print(f"[Vision] 列出配置键失败: {e}", flush=True)
            return "❌ 视觉功能不可用：未配置 MCP 服务器。请在设置中添加支持视觉能力的 MCP 服务器配置（如 GLM-4V）。"

    async def _analyze_screen_with_mcp_deprecated(self) -> str:
        """[已弃用] 旧版MCP视觉分析（已迁移NIT，保留防错）。"""
        return "⚠️ 此功能已迁移至 NIT 插件系统。"

    async def _run_reflection(
        self, task: str, history: str, screenshot_base64: str = None
    ) -> str:
        """运行反思逻辑"""
        config = await self._get_reflection_config()
        if not config:
            return None

        print("[Reflection] 触发反思机制...")

        # 视觉分析已迁移NIT，反思不强依赖预分析
        vision_analysis = None
        is_blind = not config.get("enable_vision")

        llm = LLMService(
            api_key=config.get("api_key"),
            api_base=config.get("api_base"),
            model=config.get("model"),
            provider=config.get("provider", "openai"),
        )

        # 根据视觉能力调整提示词 (Prompt)
        vision_prompt_name = "vision_enabled" if not is_blind else "vision_disabled"
        vision_instruction_block = "{{" + vision_prompt_name + "}}"

        # 生成工具列表字符串
        tools_list_str = ""
        # 动态获取最新工具定义
        # current_tools_defs = plugin_manager.get_all_definitions()

        # 使用NIT协议筛选逻辑（需NIT Manager启用）
        nit_manager = get_nit_manager()
        current_tools_defs = []

        for plugin_name, manifest in plugin_manager.plugins.items():
            # 1. 检查分类开关(Level 1)
            category = manifest.get("_category", "plugins")  # 默认为 plugins
            if not nit_manager.is_category_enabled(category):
                continue

            # 2. 检查插件开关(Level 2)
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
            "provider": model_config.provider,  # 新增provider
            "temperature": model_config.temperature,
            "enable_vision": model_config.enable_vision,
        }

    async def _get_pet_state(self) -> PetState:
        # [多Agent] 按活跃Agent过滤PetState
        from services.agent.agent_manager import get_agent_manager

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
        """处理AuraVision主动视觉观察结果。"""
        # 1. 检查现在是否应该说话
        # TODO: 实现复杂门控逻辑（如检查间隔）
        print(f"[Agent] 收到主动观察结果: {intent_description} (评分: {score:.4f})")

        # 2. 构造内部感知 Prompt
        self.mdp.render(
            "tasks/perception/proactive_internal_sense",
            {"intent_description": intent_description, "score": f"{score:.4f}"},
        )

        # 3. 触发特殊会话（调用process_request带伪造用户消息，标记为内部触发）。
        pass

    async def _get_mcp_clients(self) -> List[McpClient]:
        """获取所有已启用的 MCP 客户端"""
        clients = []
        # 1. 尝试从通用MCP配置表获取
        try:
            # 获取所有配置判断新表是否有数据
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
                # 新表有数据则以此为准不回退
                return clients
        except Exception as e:
            print(f"[AgentService] 查询 MCPConfig 表错误: {e}")

        # 新表无数据时回退旧配置
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
                            # 检查启用状态(默认True)
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

        # 3. 回退旧URL/Key配置(若无客户端)
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
        """解析保存LLM元数据，负责NIT工具调用。"""
        try:
            # 1. 处理NIT工具调用(核心逻辑)
            nit_results = []
            if execute_nit:
                # --- [安全门控] 手机端NIT脚本硬隔离 ---
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
                    # 检查text含<nit>且涉敏感词
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

                # 准备MCP插件(若存在)
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

            # 2. 传统XML标签解析(弃用，保留框架防扩展)
            # 注意：状态更新已迁移至UpdateStatusPlugin(NIT)
            # 长记忆(MEMORY)由ScorerService独立处理

            await self.session.commit()
            return nit_results
        except Exception as e:
            await self.session.rollback()
            print(f"_save_parsed_metadata 出错: {e}")
            return []

    async def preview_prompt(
        self, session_id: str, source: str, log_id: int
    ) -> Dict[str, Any]:
        """预览特定日志完整Prompt(系统+历史+用户)，用于调试/Dashboard。"""
        # 1. 获取目标日志
        log = await self.session.get(ConversationLog, log_id)
        if not log:
            return {"error": "Log not found"}

        # 2. 识别“当前消息”和“历史截止点”
        current_msg_log = None
        history_before_id = None

        if log.role == "assistant":
            # 查找此前最近一条用户消息
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

            history_before_id = current_msg_log.id if current_msg_log else log.id

        else:
            # 用户日志已选中
            current_msg_log = log
            history_before_id = log.id

        # 3. 构造上下文
        messages = []
        if current_msg_log:
            messages.append({"role": "user", "content": current_msg_log.content})

        # 4. 运行预处理器管道(空跑)
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

    # [遗留] social_chat已移除，使用chat(source='social')。

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
            from services.memory.reflection_service import ReflectionService

            print(f"[Agent] 启动后台梦境任务 (agent_id={agent_id})...", flush=True)
            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session() as session:
                # 更新Config中上次触发时间。
                # [注] Config全局，但应按agent_id区分。
                # 用户请求记忆隔离，调度隔离虽非关键但有益，使用后缀键。

                config_key = f"last_dream_trigger_time_{agent_id}"
                now_str = datetime.now().isoformat()
                config_last_dream = await session.get(Config, config_key)

                # 回退至全局键（兼容性或首次运行）
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

                # 1. 补录记忆(优先修复失败)
                # Scorer任务查找无关Agent但处理相关。
                # backfill_failed_scorer_tasks迭代含agent_id的日志。
                # 现在支持过滤以防日志干扰和竞争条件。
                await service.backfill_failed_scorer_tasks(agent_id=agent_id)

                # 2. 孤独记忆扫描(新特性：修复孤立记忆)
                # 每次梦境周期扫描 3 个孤独记忆
                await service.scan_lonely_memories(limit=3, agent_id=agent_id)

                # 3. 关联挖掘(高优先级)
                await service.dream_and_associate(limit=10, agent_id=agent_id)

                # 3. 记忆压缩(低优先级，10%概率)
                if random.random() < 0.1:
                    # 默认：压缩3天前低价值记忆
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
        # [NIT安全] 生成请求上下文ID
        current_nit_id = NITSecurityManager.generate_random_id()

        # 通知CompanionService用户活动防中断
        try:
            # [Fix] 跳过social/mobile陪伴更新
            if source not in ["social", "mobile"]:
                from services.agent.companion_service import companion_service

                companion_service.update_activity()
        except ImportError:
            pass
        except Exception as e:
            print(f"[Agent] 更新陪伴活动失败: {e}")

        # 用户交互时取消待处理“反应”任务
        if not system_trigger_instruction:
            try:
                # [多Agent] 仅取消当前Agent任务
                from services.agent.agent_manager import get_agent_manager

                current_agent_id = (
                    agent_id_override or get_agent_manager().active_agent_id
                )

                # 假设“反应”任务应在交互时取消
                statement = (
                    select(ScheduledTask)
                    .where(ScheduledTask.type == "reaction")
                    .where(not ScheduledTask.is_triggered)
                    .where(ScheduledTask.agent_id == current_agent_id)
                )
                tasks_to_cancel = (await self.session.exec(statement)).all()
                if tasks_to_cancel:
                    print(f"[Agent] 用户交互，取消{len(tasks_to_cancel)}个反应任务")
                    for t in tasks_to_cancel:
                        await self.session.delete(t)
                    await self.session.commit()
            except Exception as e:
                print(f"[Agent] 取消反应任务失败: {e}")

        # [工作模式] 会话覆盖
        # 检查是否处于工作会话以隔离历史。
        # [Fix] 禁用全局覆盖以防劫持'default'(Pet)会话。
        # IdeChat通过ide_router处理会话解析。
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

        # [功能] 多Agent支持
        # 从AgentManager提取agent_id(标准化)
        from services.agent.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        current_agent_id = agent_id_override or agent_manager.active_agent_id

        # 未设置回退"pero"(尽管AgentManager应处理)
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

        # 配置缺失回退(ConfigPreprocessor运行不应发生)
        # [Refactor] 提前加载Config支持工具计算
        config = await self._get_llm_config()

        # 5. 合并动态MCP工具
        if on_status:
            await on_status("thinking", "正在加载工具...")
        print("[Agent] 正在加载 MCP 工具...")

        # --- 工具列表优化 ---
        # [Refactor] 统一工具策略执行
        from core.plugin_manager import get_plugin_manager
        from services.agent.agent_manager import get_agent_manager

        plugin_manager = get_plugin_manager()
        agent_manager = get_agent_manager()
        agent_profile = agent_manager.get_agent(current_agent_id)

        # 1. 确定策略模式
        policy_mode = "desktop"
        if source == "social":
            policy_mode = "social"
        elif source == "group":
            policy_mode = "group"
        elif session_id and session_id.startswith("work_"):
            policy_mode = "work"
        elif source == "lightweight" or (session_id and "companion" in session_id):
            policy_mode = "lightweight"

        # 2. 获取策略配置
        policy = {}
        if agent_profile and agent_profile.tool_policies:
            policy = agent_profile.tool_policies.get(policy_mode, {})
            if not policy and policy_mode == "group":
                # 回退到 desktop 策略，如果 group 策略未定义
                policy = agent_profile.tool_policies.get("desktop", {})
                if policy:
                    print(
                        f"[Agent] Group 策略未定义，回退到 Desktop 策略 (Agent: {current_agent_id})"
                    )

            if policy:
                print(
                    f"[Agent] 使用工具策略: {policy_mode} (Agent: {current_agent_id})"
                )

        # 3. 回退默认(兼容性)
        if not policy:
            print(f"[Agent] 未找到配置，使用默认策略: {policy_mode}")
            if policy_mode == "social":
                # 默认安全社交策略
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
                # 默认工作策略
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

        # 4. 构建工具标签映射以进行过滤
        tool_tags_map = {}
        all_manifests = plugin_manager.get_all_manifests()
        for m in all_manifests:
            tags = m.get("tags", [])
            # 如果需要，基于类别添加隐式标签
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

        # 5.2 MCP 工具
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
                    # 系统中的 MCP 工具暂无标签，如有需要可将 'mcp' 视为标签
                    tool_tags_map[tool_name] = ["mcp"]
            except Exception as e:
                print(f"[AgentService] 警告: 列出客户端 {client.name} 的工具失败: {e}")

        # 5.3 插件工具 (NIT 插件)
        # 确保插件也作为候选项，以便加入白名单并暴露
        existing_tool_names = {t["function"]["name"] for t in candidate_tools}
        for m in all_manifests:
            cmds = []
            if "capabilities" in m and "invocationCommands" in m["capabilities"]:
                cmds = m["capabilities"]["invocationCommands"]
            elif "capabilities" in m and "toolDefinitions" in m["capabilities"]:
                cmds = m["capabilities"]["toolDefinitions"]

            for cmd in cmds:
                c_id = cmd.get("commandIdentifier")
                if c_id and c_id not in existing_tool_names:
                    # 构建基础函数定义。
                    # 注意：插件参数可能不是完美的 JSON Schema，如果不确定则默认为空字典，
                    # 或者如果是简单的键值对则进行包装。
                    # 目前我们信任插件作者或提供宽松的 Schema。
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

        # 6. 基于策略过滤工具
        final_tools = []
        strategy = policy.get("strategy", "all")

        allowed_tools = set(policy.get("allowed_tools", []))
        allowed_tags = set(policy.get("allowed_tags", []))

        for tool in candidate_tools:
            t_name = tool["function"]["name"]
            t_tags = set(tool_tags_map.get(t_name, []))

            # 移动端检查 (全局安全)
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

            # 视觉检查
            if enable_vision and t_name == "screen_ocr":
                continue
            if t_name in ["take_screenshot", "see_screen"] and not enable_vision:
                # 修改非视觉模式的描述
                tool["function"]["description"] = (
                    "获取当前屏幕的视觉分析报告。系统将调用视觉 MCP 服务器分析屏幕内容并返回详细的文字描述。当你需要了解屏幕上的视觉信息、或出于好奇想看看主人在做什么但无法直接看到图片时，请使用此工具。"
                )
                if "count" in tool["function"]["parameters"]["properties"]:
                    tool["function"]["parameters"]["properties"]["count"][
                        "description"
                    ] = "获取截图并分析的数量。在非多模态模式下，建议设为 1。"

            is_allowed = False
            if strategy == "all":
                is_allowed = True
            elif strategy == "whitelist":
                # 仅两种允许方式：精确名称匹配或标签匹配
                if t_name in allowed_tools:
                    is_allowed = True
                elif not t_tags.isdisjoint(allowed_tags):
                    is_allowed = True  # 存在重叠

            if is_allowed:
                final_tools.append(tool)

        # [轻量模式] 如果启用轻量模式，则过滤工具
        # 仅允许 TaskLifecycle 和 ScreenVision 相关工具
        is_lightweight = config.get("lightweight_mode", False)
        if is_lightweight and source not in ["social"]:
            lightweight_allowed_categories = {"TaskLifecycle", "ScreenVision"}
            # 同时也允许那些可能没有明确分类但必不可少的核心工具，或者依赖标签。
            # 这里假设 tool_tags_map 包含类似类别的标签。
            # 如果标签不足，可能需要硬编码的工具名白名单。
            # 让我们先尝试按标签过滤，假设标签包含分类名称。

            # 由于 'tool' 字典中没有直接的分类元数据（它在 tool_tags_map 中），我们需要遍历检查。
            lightweight_tools = []
            for tool in final_tools:
                t_name = tool["function"]["name"]
                t_tags = set(tool_tags_map.get(t_name, []))

                # 检查与允许类别的交集
                # 注意：标签可能是小写的，所以我们处理大小写敏感性
                if (
                    not t_tags.isdisjoint(
                        {c.lower() for c in lightweight_allowed_categories}
                    )
                    or not t_tags.isdisjoint(lightweight_allowed_categories)
                    or t_name in ["finish_task", "take_screenshot", "see_screen"]
                ):
                    lightweight_tools.append(tool)

            print(
                f"[Agent] 轻量模式开启: 工具列表已精简 ({len(lightweight_tools)}/{len(final_tools)})"
            )
            final_tools = lightweight_tools

        dynamic_tools = final_tools
        print(
            f"[Agent] 最终工具列表 ({len(dynamic_tools)}): {[t['function']['name'] for t in dynamic_tools]}"
        )

        # --- 创建 NIT 安全白名单 ---
        allowed_tool_names = [t["function"]["name"] for t in dynamic_tools]

        # [重构] 将计算出的工具保存到上下文以避免重复
        context["dynamic_tools"] = dynamic_tools
        context["mcp_clients"] = mcp_clients
        context["mcp_tool_map"] = mcp_tool_map
        context["allowed_tool_names"] = allowed_tool_names

        # [Refactor] 移除 AgentService 中手动拼接工具描述的逻辑
        # 该职责已完全移交给 PromptManager，它会根据 Context 中的 dynamic_tools 自动生成描述
        # 这样可以确保描述内容与 config.json 定义的过滤策略严格一致
        pass

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
            if final_messages and final_messages[0]["role"] == "system":
                final_messages[0]["content"] += (
                    f"\n\n<System_Trigger>\n{system_trigger_instruction}\n</System_Trigger>"
                )
            else:
                final_messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": f"<System_Trigger>\n{system_trigger_instruction}\n</System_Trigger>",
                    },
                )

            if not user_message:
                user_message = f"【系统触发】{system_trigger_instruction}"

        # [功能] 移动端来源感知
        if source == "mobile":
            mobile_instruction = self.mdp.render("components/context/mobile")
            if final_messages and final_messages[0]["role"] == "system":
                final_messages[0]["content"] += f"\n\n{mobile_instruction}"
            else:
                final_messages.insert(
                    0, {"role": "system", "content": mobile_instruction}
                )
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

                    # 追加到消息 (合并到 System role)
                    if final_messages and final_messages[0]["role"] == "system":
                        final_messages[0]["content"] += f"\n\n{state_msg}"
                    else:
                        final_messages.insert(
                            0, {"role": "system", "content": state_msg}
                        )
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

        # [重构] 从上下文检索预计算的工具
        dynamic_tools = context.get("dynamic_tools", [])
        mcp_clients = context.get("mcp_clients", [])
        mcp_tool_map = context.get("mcp_tool_map", {})
        allowed_tool_names = context.get("allowed_tool_names", [])

        print(
            f"[Agent] 使用预计算工具列表 ({len(dynamic_tools)}): {[t['function']['name'] for t in dynamic_tools]}"
        )

        # --- 原生工具配置 ---
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

        # [Fix] Companion 模式下不传递 Tools 给 LLM，避免 Function Calling 干扰纯文本回复
        # 社交模式 (Social) 现在允许调用一小部分 NIT 工具，因此不再禁用
        if session_id == "companion_mode":
            tools_to_pass = None
            print("[Agent] Companion 模式: 禁用 Function Calling (Tools=None)")

        if disable_native_tools:
            print("[Agent] 原生工具 (Function Calling) 已通过配置禁用。")

        full_response_text = ""
        accumulated_full_response = (
            ""  # 用于保存完整的对话记录（包含所有 ReAct 轮次的思考过程）
        )
        pair_id = str(uuid.uuid4())  # 生成原子性绑定ID

        # --- ReAct 循环配置 ---
        turn_count = 0
        MAX_TURNS = 30  # [安全] 限制最大轮次以防止无限循环 (原为 9999)

        # [Config] 社交模式/轻量模式/陪伴模式强制单轮 ReAct (1次工具调用 + 1次回复 = 2轮)
        if source in ["social", "lightweight"] or session_id == "companion_mode":
            MAX_TURNS = 1 if session_id == "companion_mode" else 2
            print(
                f"[Agent] {source if session_id != 'companion_mode' else 'companion'} 模式: 限制为单轮 ReAct (MAX_TURNS={MAX_TURNS})"
            )

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

                # 定义原始流生成器
                async def raw_stream_source(
                    tools_to_pass=tools_to_pass,
                    collected_tool_calls=collected_tool_calls,
                ):
                    nonlocal \
                        current_turn_text, \
                        full_response_text, \
                        has_tool_calls_in_this_turn

                    async for delta in llm.chat_stream_deltas(
                        final_messages, temperature=temperature, tools=tools_to_pass
                    ):
                        # 调试日志：打印增量内容
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

                # 调试日志：流结束后
                if has_tool_calls_in_this_turn:
                    print(
                        f"[Agent] 收集到工具调用: {json.dumps(collected_tool_calls, ensure_ascii=False)}"
                    )
                else:
                    print(f"[Agent] 第 {turn_count} 轮未检测到工具调用")

                # 应用后处理器管道
                # 如果 source 是 'ide' 或 'desktop'，则跳过 NIT 过滤，以便前端显示工具调用
                processed_stream = self.postprocessor_manager.process_stream(
                    raw_stream_source(),
                    context={
                        "source": source,
                        "session_id": session_id,
                        "skip_nit_filter": (source in ["ide", "desktop"]),
                    },
                )
                async for content in processed_stream:
                    yield content

                # 检查轮次是否结束
                if not has_tool_calls_in_this_turn:
                    # 未调用工具，这是最终答案

                    # === NIT 调度器集成 (统一流程) ===
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
                            # [安全] 截断过长的响应以防止上下文窗口爆炸
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

                                # [特性] NIT 实时状态同步
                                # 检查结果是否包含状态触发器 (JSON)
                                try:
                                    if "triggers" in out_str or '"mood"' in out_str:
                                        import json

                                        # 尝试将输出解析为 JSON
                                        # 它可能被包裹在文本中，但如果是工具直接返回通常是 JSON 字符串
                                        # 我们寻找 JSON 对象结构
                                        start_idx = out_str.find("{")
                                        end_idx = out_str.rfind("}")
                                        if start_idx != -1 and end_idx != -1:
                                            json_str = out_str[start_idx : end_idx + 1]
                                            data = json.loads(json_str)

                                            # 如果包含 'state' 或 'triggers'，则广播它
                                            triggers = None
                                            if "triggers" in data:
                                                triggers = data["triggers"]
                                            elif "state" in data:
                                                triggers = data["state"]
                                            elif "mood" in data:  # 直接状态对象
                                                triggers = data

                                            if triggers:
                                                print(
                                                    f"[Agent] Detected state update in NIT result: {triggers}"
                                                )
                                                # 1. 推送 SSE
                                                sse_payload = json.dumps(
                                                    {"triggers": triggers},
                                                    ensure_ascii=False,
                                                )
                                                yield f"data: {sse_payload}\n\n"

                                                # 2. 通过 RealtimeSessionManager 广播
                                                try:
                                                    from services.core.realtime_session_manager import (
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

                                    # [修复] 如果可用，从输出中提取摘要并生成
                                    # finish_task 输出格式: "[System] Task finished... Summary: {summary}"
                                    output_str = str(res.get("output", ""))
                                    if "Summary: " in output_str:
                                        try:
                                            summary_part = output_str.split(
                                                "Summary: ", 1
                                            )[1]
                                            # 追加到 full_response_text 以便保存
                                            full_response_text += summary_part
                                            # 生成到前端
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
                                    from services.perception.screenshot_service import (
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
                                        f"{m['role']}: {str(m.get('content', ''))[:200]}"
                                        for m in final_messages[-5:]
                                    ]
                                )
                                # 尝试获取最新截图供反思使用
                                latest_screenshot = None
                                try:
                                    from services.perception.screenshot_service import (
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

                # --- 工具执行阶段 ---
                # 1. 将助手消息 (思考 + 工具调用) 追加到历史记录
                # [安全] 截断过长的思考过程
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

                # 2. 执行工具
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

                    # --- 工具执行策略 ---
                    # 1. 安全门控: 硬拦截机制 (硬隔离)
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

                    # 2. 拦截器：优先处理具有特殊 UI/上下文要求的工具
                    # 3. NIT 调度器：统一执行所有其他插件

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
                            # 使用旧映射或 NIT 调度器获取原始数据
                            # 出于安全考虑，这里使用旧映射，因为它返回原始列表/字典
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
                                from services.perception.screenshot_service import (
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
                                                "text": f"--- 截图 {i + 1} (捕获时间: {shot['time_str']}) ---",
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

                    # --- NIT 调度器集成 ---
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
                                            from services.core.realtime_session_manager import (
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

                    # --- MCP 工具处理 ---
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
                            f"{m['role']}: {str(m.get('content', ''))[:200]}"
                            for m in final_messages[-5:]
                        ]
                    )
                    # 尝试获取最新截图供反思使用
                    latest_screenshot = None
                    try:
                        from services.perception.screenshot_service import (
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

                    if reflection_advice and "NORMAL" not in reflection_advice:
                        final_messages.append(
                            {
                                "role": "system",
                                "content": f"[反思助手提示]: 检测到上一步操作可能存在问题。建议参考：{reflection_advice}",
                            }
                        )

                # 4. 立即生成 UI 标签
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

                # 在后处理之前捕获原始文本
                raw_full_text = full_response_text

                # 在保存之前对完整响应文本进行后处理 (批处理模式)
                # 这确保记忆和下游服务获得干净的文本，没有协议标记
                if full_response_text:
                    try:
                        full_response_text = await self.postprocessor_manager.process(
                            full_response_text,
                            context={"source": source, "session_id": session_id},
                        )
                    except Exception as pp_e:
                        print(f"[Agent] 后处理器失败: {pp_e}。使用原始文本。")

                # 通过网关向前端广播 LLM 响应
                # [修改] 允许 'ide' 来源也广播给 Pet (桌面宠物应对 IDE 聊天做出反应)
                if not is_voice_mode and source in ["desktop", "ide"]:
                    from services.core.gateway_client import gateway_client

                    await gateway_client.broadcast_text_response(full_response_text)

                    # 触发 TTS (文本模式)
                    # [修复] 再次显式检查来源以确保安全 (虽然 source=="desktop" 已经覆盖)
                    asyncio.create_task(
                        self._generate_and_stream_tts(full_response_text)
                    )

                # 仅在正常生成回复（且不是报错）时才保存对话记录
                # 用户消息与 Pero 回复进行原子性绑定保存

                # [健壮性] 如果缺失 user_message，进行回退提取
                if not user_message:
                    # 优先级 1: 检查覆盖 (语音模式)
                    if user_text_override:
                        user_message = user_text_override
                        print(
                            f"[Agent] 用户消息已从覆盖中恢复: '{user_message[:20]}...'"
                        )
                    else:
                        # 优先级 2: 在消息中搜索
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

                # [特性] 用户图片持久化 (即发即弃)
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
                # [优化] 如果响应是错误，则不运行评分器
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
                    # [修复] 跳过社交/移动模式的后台评分器，因为它们有自己的逻辑
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

                # [触发梦境] 3% 的概率触发后台记忆整理
                # [修复] 禁用社交/移动模式的梦境
                import random

                if source not in ["social", "mobile"] and random.random() < 0.03:
                    asyncio.create_task(self._trigger_dream(agent_id=current_agent_id))

            except Exception as log_err:
                print(f"保存对话日志失败 (成功路径): {log_err}")

        except Exception as e:
            import traceback

            error_msg = f"Error: {str(e)}"
            print(f"Agent 聊天错误 (内部): {traceback.format_exc()}")

            # [优化] 检查“无效内容”错误并优雅处理
            # 如果错误是关于 API 未返回内容，广播 toast 且不保存到数据库
            err_str_lower = str(e).lower()
            is_empty_content_error = (
                "no valid content" in err_str_lower
                or "invalid api response" in err_str_lower
                or "choices array is missing" in err_str_lower
            )

            if is_empty_content_error:
                from services.core.gateway_client import gateway_client

                asyncio.create_task(
                    gateway_client.broadcast_error(
                        message="API 未返回有效内容，可能是模型正在思考或被截断，请重试。",
                        title="无效响应",
                        error_type="error",
                    )
                )
                # 提前返回，跳过保存日志
                return

            # [故障排除] 即使出错也尝试保存日志 (用户反馈：日志丢失)
            try:
                # 确保 user_message 可用
                final_u_msg = user_message
                if not final_u_msg and user_text_override:
                    final_u_msg = user_text_override

                # 将错误追加到响应以便记录
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
                import contextlib

                for client in mcp_clients:
                    with contextlib.suppress(Exception):
                        await client.close()
            pass

    async def _generate_and_stream_tts(self, text: str):
        """生成 TTS 音频并流式传输到前端 (文本模式)"""
        try:
            # 清理文本 (移除表情符号、思考标签等)
            import re

            cleaned_text = re.sub(r"[\U00010000-\U0010ffff]", "", text)  # 移除表情符号
            cleaned_text = re.sub(r"【.*?】", "", cleaned_text)  # 移除思考标签
            cleaned_text = re.sub(r"<.*?>", "", cleaned_text)  # 移除 html 标签
            cleaned_text = re.sub(r"\*.*?\*", "", cleaned_text)  # 移除动作
            cleaned_text = cleaned_text.strip()

            if not cleaned_text:
                return

            import time
            import uuid

            from peroproto import perolink_pb2
            from services.core.gateway_client import gateway_client
            from services.interaction.tts_service import get_tts_service

            tts_service = get_tts_service()

            # 检查 TTS 是否启用
            from core.config_manager import get_config_manager

            if not get_config_manager().get("tts_enabled", True):
                return

            # 使用默认语音参数
            audio_path = await tts_service.synthesize(cleaned_text)

            if audio_path:
                # 通过网关流式传输
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

                # 清理
                try:
                    import os

                    os.remove(audio_path)
                except Exception:
                    pass
        except Exception as e:
            print(f"[Agent] TTS 生成失败: {e}")
