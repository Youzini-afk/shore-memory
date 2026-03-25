import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config_manager import get_config_manager
from models import Config, PetState
from services.agent.agent_manager import get_agent_manager
from services.mdp.manager import mdp

logger = logging.getLogger(__name__)


class PromptManager:
    """
    提示词管理组件，负责编排人设、上下文、记忆、时间等信息。
    已迁移至 MDP (Modular Dynamic Prompts) 系统。
    """

    def __init__(self):
        # 使用单例 MDP 管理器
        self.mdp = mdp
        self.agent_manager = get_agent_manager()

    async def _get_stronghold_context(self, agent_id: str) -> Dict[str, Any]:
        """
        [Stronghold] 获取据点群聊模式的上下文数据
        """
        from database import get_session
        from services.chat.stronghold_service import StrongholdService

        context = {
            "current_room_name": "未知区域",
            "current_facility_name": "未知设施",
            "environment_json_display": "（无环境数据）",
            "active_agents_list": "（暂无其他成员）",
        }

        async for session in get_session():
            service = StrongholdService(session)

            # 1. 获取当前位置
            room = await service.get_agent_location(agent_id)
            if room:
                context["current_room_name"] = room.name
                context["environment_json_display"] = room.environment_json

                # 2. 获取设施信息
                if room.facility_id:
                    # 注意：这里需要额外查询 Facility，暂时简化处理或假设 Facility 已知
                    # 可以在 StrongholdService 中增加 get_facility(id)
                    pass

                # 3. 获取同房间人员
                agents = await service.get_room_agents(room.id)
                # 过滤掉自己
                others = [a for a in agents if a != agent_id]
                context["active_agents_list"] = (
                    ", ".join(others) if others else "（只有你自己）"
                )

            break  # 只使用一个 session

        return context

    def _enrich_variables(
        self, variables: Dict[str, Any], is_social_mode: bool, is_work_mode: bool
    ):
        """
        丰富和处理变量，从配置和Agent状态中填充缺失信息
        """
        # 0. 注入核心人设 (system_prompt.md)
        # 允许在总结任务中通过 {{ system_prompt }} 引用
        if "system_prompt" not in variables:
            prompt = self.mdp.get_prompt("agents/pero/system_prompt")
            if prompt:
                variables["system_prompt"] = prompt.content

        # 0. 检查轻量级模式
        config = get_config_manager()
        is_lightweight = config.get("lightweight_mode", False)

        # 注入链逻辑（思维链）
        chain_name = variables.get("chain_name", "default")
        chain_prompt = self.mdp.get_prompt(f"components/chains/{chain_name}")
        variables["chain_logic"] = chain_prompt.content if chain_prompt else ""

        # 2. 默认值
        config_manager = get_config_manager()
        owner_name = config_manager.get("owner_name", "主人")
        variables.setdefault("owner_name", owner_name)
        # 统一 user 别名，用于模板中的 {{user}}
        variables["user"] = variables["owner_name"]
        # 统一 char 别名，用于模板中的 {{char}}（兼容角色卡片约定）
        variables["char"] = variables.get("agent_name", "")
        variables.setdefault("user_persona", "未设定")
        variables.setdefault("mood", "开心")
        variables.setdefault("vibe", "活泼")
        variables.setdefault("mind", "正在想主人...")
        variables.setdefault("vision_status", "")
        variables.setdefault("memory_context", "")

        # [社交模式/轻量模式特殊处理]
        if is_social_mode or is_lightweight:
            variables["chain_logic"] = ""

        # [多 Agent 集成]
        # 获取当前活跃 Agent 的配置，并将其合并到 variables 中
        # 注意：variables 中的临时变量（如用户输入）优先级高于 Agent 配置
        active_agent = self.agent_manager.get_active_agent()
        agent_config = {}
        if active_agent:
            # 将 AgentProfile 转换为字典
            agent_config = {
                "agent_name": active_agent.name,
                "agent_id": active_agent.id,
                "work_custom_persona": active_agent.work_custom_persona,
                "social_custom_persona": active_agent.social_custom_persona,
            }

        # 合并配置 (variables 优先)
        # 我们使用 setdefault 确保如果不传 agent_name，则使用 Agent 的名字
        for k, v in agent_config.items():
            variables.setdefault(k, v)

        # 1. 构建能力字符串
        enable_vision = variables.get("enable_vision", False)
        enable_voice = variables.get("enable_voice", False)
        enable_video = variables.get("enable_video", False)

        # [社交模式覆盖]
        if is_social_mode:
            # [Fix] 社交模式下不再强制清空 NIT 能力，而是交由模板 (social_rules.md) 控制
            # 我们只需要确保不加载不需要的组件即可

            # [修复] 注入表情包列表 (表情包列表注入)
            sticker_list_str = "（无可用表情包）"
            agent_id = variables.get("agent_id") or config.get("agent_id", "pero")
            agent_profile = self.agent_manager.get_agent(str(agent_id))

            if agent_profile and agent_profile.use_stickers:
                try:
                    # agent_profile.config_path 是绝对路径
                    agent_dir = os.path.dirname(agent_profile.config_path)
                    sticker_index_path = os.path.join(
                        agent_dir, "stickers", "index.json"
                    )

                    if os.path.exists(sticker_index_path):
                        import json

                        with open(sticker_index_path, "r", encoding="utf-8") as f:
                            stickers = json.load(f)
                            keywords = list(stickers.keys())
                            if keywords:
                                sticker_list_str = ", ".join(keywords)
                except Exception as e:
                    logger.error(f"加载表情包配置失败: {e}")

            variables["sticker_list"] = sticker_list_str

            # 确保加载 sticker_expression 组件内容
            if "sticker_expression" not in variables:
                prompt = self.mdp.get_prompt("social/abilities/sticker_expression")
                variables["sticker_expression"] = prompt.content if prompt else ""

        abilities_parts = []

        # [修改] 仅在非社交模式下注入感官能力
        if not is_social_mode:
            # 视觉
            if enable_vision:
                # 检查提示是否存在以避免错误，如果需要则回退
                prompt = self.mdp.get_prompt("components/abilities/vision")
                if prompt:
                    abilities_parts.append(prompt.content)
            else:
                prompt = self.mdp.get_prompt("components/abilities/vision_placeholder")
                if prompt:
                    abilities_parts.append(prompt.content)

            # 语音
            if enable_voice:
                prompt = self.mdp.get_prompt("components/abilities/voice")
                if prompt:
                    abilities_parts.append(prompt.content)
            else:
                # 注意：如果 voice_placeholder 之前不在 core/abilities 中，它可能尚未存在于 components 中
                prompt = self.mdp.get_prompt("components/abilities/voice_placeholder")
                if prompt:
                    abilities_parts.append(prompt.content)

            # 视频
            if enable_video:
                prompt = self.mdp.get_prompt("components/abilities/video")
                if prompt:
                    abilities_parts.append(prompt.content)

        variables["ability_sensory"] = "\n".join(abilities_parts)

        # [核心能力加载]
        # 显式加载 ability 和 ability_nit，以支持新版目录结构 (components/abilities/...)
        if "ability" not in variables:
            # [修复] 仅在非社交模式下加载工作区能力，或在明确需要时加载
            # 社交模式下不应提及文件系统操作，除非未来有特定需求
            if not is_social_mode:
                prompt = self.mdp.get_prompt("components/abilities/workspace")
                variables["ability"] = prompt.content if prompt else ""
            else:
                variables["ability"] = ""

        if "ability_nit" not in variables:
            prompt = self.mdp.get_prompt("components/abilities/nit")
            variables["ability_nit"] = prompt.content if prompt else ""

        # [核心规则加载]
        if "system_core" not in variables:
            prompt = self.mdp.get_prompt("components/rules/system_core")
            variables["system_core"] = prompt.content if prompt else ""

        if "output_constraint" not in variables:
            prompt = self.mdp.get_prompt("components/output/output_constraint")
            variables["output_constraint"] = prompt.content if prompt else ""

        # [社交身份注入]
        default_name = config.get("bot_name", "Pero")
        bot_name = default_name
        try:
            from nit_core.plugins.social_adapter.social_service import (
                get_social_service,
            )

            social_service = get_social_service()
            if (
                social_service
                and hasattr(social_service, "bot_infos")
                and social_service.bot_infos
            ):
                # 获取第一个可用的 bot_info (通常我们只关心一个主号，或者取默认的一个)
                first_key = next(iter(social_service.bot_infos))
                info = social_service.bot_infos[first_key]
                bot_name = info.get("nickname", default_name)
        except ImportError:
            pass

        variables["bot_name"] = bot_name  # 保留 bot_name 以兼容旧的 Prompt
        variables.setdefault(
            "agent_name", bot_name
        )  # 仅当未设定时使用 bot_name 作为 agent_name

        # [工作模式解耦]
        # 优先使用 Agent 配置文件中定义的 work_custom_persona，如果没有则回退到全局配置
        variables["custom_persona"] = variables.get(
            "work_custom_persona"
        ) or config.get(
            "work_custom_persona",
            "你是一个全能的 AI 助手，你的名字是 {{ agent_name }}。",
        )

        # [社交模式修正]
        # 如果是社交模式，使用 social_custom_persona 覆盖 custom_persona
        if is_social_mode:
            # 1. 注入 owner_qq (从配置中获取，优先使用 owner_qq，兼容 master_qq)
            owner_qq = config.get("owner_qq") or config.get("master_qq") or "未知QQ"
            variables.setdefault("owner_qq", str(owner_qq))

            # 2. 获取并渲染 custom_persona (支持嵌套占位符如 {{ owner_qq }})
            raw_persona = (
                variables.get("social_custom_persona")
                or "你是一个活跃在社交平台的赛博女孩。"
            )
            if self.mdp.jinja_env and "{{" in raw_persona:
                try:
                    variables["custom_persona"] = self.mdp.jinja_env.from_string(
                        raw_persona
                    ).render(variables)
                except Exception as e:
                    logger.warning(f"渲染 custom_persona 失败: {e}")
                    variables["custom_persona"] = raw_persona
            else:
                variables["custom_persona"] = raw_persona

            # [Fix] 注入 social.md 所需的上下文变量
            if "xml_context" not in variables:
                # 优先使用群聊历史，其次是私聊/桌面历史
                hist = (
                    variables.get("flattened_group_history")
                    or variables.get("flattened_desktop_history")
                    or variables.get("recent_history_context")
                )
                variables["xml_context"] = hist if hist else "（暂无历史消息）"

            # 3. 渲染 sticker_expression (依赖 sticker_list)
            # [Fix] 强制渲染 sticker_expression，即使之前已加载了原始内容
            prompt = self.mdp.get_prompt("social/abilities/sticker_expression")
            content = prompt.content if prompt else ""
            if self.mdp.jinja_env and "{{" in content:
                try:
                    variables["sticker_expression"] = self.mdp.jinja_env.from_string(
                        content
                    ).render(variables)
                except Exception:
                    variables["sticker_expression"] = content
            else:
                variables["sticker_expression"] = content

            # 4. 渲染 social_instructions (依赖 custom_persona 和 sticker_expression)
            if "social_instructions" not in variables:
                prompt = self.mdp.get_prompt("social/social_instructions")
                content = prompt.content if prompt else ""
                # 必须手动渲染，因为 social.md 的渲染不会递归处理变量中的占位符
                if self.mdp.jinja_env and "{{" in content:
                    try:
                        variables["social_instructions"] = (
                            self.mdp.jinja_env.from_string(content).render(variables)
                        )
                    except Exception as e:
                        logger.warning(f"渲染 social_instructions 失败: {e}")
                        variables["social_instructions"] = content
                else:
                    variables["social_instructions"] = content

            if "xml_guide" not in variables:
                prompt = self.mdp.get_prompt("social/xml_guide")
                variables["xml_guide"] = prompt.content if prompt else ""

            if "instruction_prompt" not in variables:
                prompt = self.mdp.get_prompt("social/instruction_prompt")
                variables["instruction_prompt"] = prompt.content if prompt else ""

        # [群聊模式修正]
        # 如果是群聊模式，加载专属上下文
        is_group_mode = variables.get("mode") == "group"
        if is_group_mode:
            import asyncio

            try:
                # 获取 Agent ID，默认为 pero
                agent_id = variables.get("agent_id") or config.get("agent_id", "pero")
                # 同步上下文中运行异步方法
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果已经在事件循环中（例如 FastAPI 路由处理），我们不能直接 run_until_complete
                    # 这里有一个权宜之计，或者我们假设 _enrich_variables 可以在异步上下文中被调用
                    # 但目前的 PromptService 设计是同步的。
                    # 为了规避这个问题，我们使用一个简单的同步兜底，或者修改调用方为异步。
                    # 由于这是一个较大的架构变动，我们暂时尝试使用 run_in_executor 或直接创建新 loop (不安全)
                    # 更好的方案是：将 _enrich_variables 变为异步，或在调用它的地方提前获取数据。
                    pass
                else:
                    stronghold_data = loop.run_until_complete(
                        self._get_stronghold_context(agent_id)
                    )
                    variables.update(stronghold_data)
            except Exception as e:
                logger.error(f"[PromptManager] 获取据点上下文失败: {e}")
                # 兜底数据
                variables.update(
                    {
                        "current_room_name": "未知区域",
                        "current_facility_name": "未知设施",
                        "environment_json_display": "（数据获取失败）",
                        "active_agents_list": "（未知）",
                    }
                )

            # 加载群聊专属 Prompt 组件
            prompt = self.mdp.get_prompt("group/environment_display")
            variables["stronghold_environment"] = (
                self.mdp.render_string(prompt.content, variables) if prompt else ""
            )

            prompt = self.mdp.get_prompt("group/interaction_rules")
            variables["group_interaction_rules"] = prompt.content if prompt else ""

            prompt = self.mdp.get_prompt("group/output_format")
            variables["group_output_format"] = prompt.content if prompt else ""

            variables["current_room_state"] = (
                f"当前位置: {variables.get('current_room_name')} ({variables.get('current_facility_name')})"
            )

        # [人设加载]
        agent_id = variables.get("agent_id") or config.get("agent_id", "pero")
        agent_id = str(agent_id).lower()
        persona_template = config.get("persona_template", f"{agent_id}/system_prompt")

        render_context = {"agent_name": variables.get("agent_name", bot_name)}
        if "owner_name" in variables:
            render_context["owner_name"] = variables["owner_name"]

        variables["persona_definition"] = self.mdp.render(
            persona_template, render_context
        )

        # 注入工具描述 (如果尚未由 AgentService 注入)
        if "available_tools_desc" not in variables:
            # [重构] 优先使用动态工具列表 (由 AgentService 根据 config.json 策略计算)
            dynamic_tools = variables.get("dynamic_tools")

            if dynamic_tools and isinstance(dynamic_tools, list):
                # 如果有动态工具列表，直接生成描述
                tools_desc = self._generate_tools_description(dynamic_tools)
                variables["available_tools_desc"] = tools_desc
                logger.info(
                    f"[PromptManager] 已从 dynamic_tools 生成工具描述 ({len(dynamic_tools)} 个工具)"
                )
            else:
                # 最后的回退策略：如果 dynamic_tools 为空且不是社交模式，才尝试从 Dispatcher 获取
                # 注意：这通常意味着 AgentService 的工具预处理出现了意外
                if not is_social_mode:
                    try:
                        from nit_core.dispatcher import get_dispatcher

                        dispatcher = get_dispatcher()

                        # 默认仅获取核心类别作为兜底，以保证安全
                        tools_desc = dispatcher.get_tools_description(
                            category_filter="core"
                        )
                        if tools_desc:
                            variables["available_tools_desc"] = tools_desc
                            # 降低日志级别：这是一个预期的回退行为，无需作为 INFO/WARNING 刷屏
                            logger.debug(
                                "[PromptManager] dynamic_tools 缺失，已从 Dispatcher 获取核心工具作为回退"
                            )
                        else:
                            variables["available_tools_desc"] = "（当前无可用工具）"
                    except Exception as e:
                        logger.error(f"[PromptManager] 工具回退获取失败: {e}")
                        variables["available_tools_desc"] = "加载工具出错。"
                else:
                    # 社交模式下，如果没有 dynamic_tools，也尝试加载核心工具作为兜底
                    # 这确保 social_rules.md 中的 {{ available_tools_desc }} 不为空
                    try:
                        from nit_core.dispatcher import get_dispatcher

                        dispatcher = get_dispatcher()
                        # 仅加载核心工具，避免在社交模式暴露敏感操作
                        tools_desc = dispatcher.get_tools_description(
                            category_filter="core"
                        )
                        variables["available_tools_desc"] = (
                            tools_desc or "（当前无可用工具）"
                        )
                    except Exception:
                        variables["available_tools_desc"] = "（当前模式下无可用工具）"

    def _generate_tools_description(self, tools: List[Dict[str, Any]]) -> str:
        """
        将工具列表转换为 NIT 协议友好的自然语言描述。
        优先尝试从 NIT Dispatcher 获取自然语言描述 (description.json)，
        否则从 OpenAI Schema 回退生成。
        目标格式: - **tool_name**: 功能描述。参数 arg1: desc1; arg2: desc2。
        """
        if not tools:
            return "（当前无可用工具）"

        # 尝试获取 Dispatcher
        try:
            from nit_core.dispatcher import get_dispatcher

            dispatcher = get_dispatcher()
        except ImportError:
            dispatcher = None

        lines = []
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name")

            # 1. 尝试从 Dispatcher 获取自然语言描述 (优先)
            if dispatcher:
                nat_desc = dispatcher.get_tool_natural_description(name)
                if nat_desc:
                    desc = nat_desc.get("description", "")
                    param = nat_desc.get("parameter", "")

                    full_desc = f"- **{name}**: {desc}"
                    if not (full_desc.endswith("。") or full_desc.endswith(".")):
                        full_desc += "。"

                    if param and "无" not in param and param != "":
                        full_desc += f" 参数 {param}"
                        if not (full_desc.endswith("。") or full_desc.endswith(".")):
                            full_desc += "。"

                    lines.append(full_desc)
                    continue

            # 2. Schema 回退逻辑 (处理 MCP 工具等)
            desc = func.get("description", "").strip()

            # [NIT 协议适配器]
            # 如果是原生 NIT 工具，desc 通常已经包含了详细的参数说明 (例如 "搜索文件。参数 query: ...")
            # 这种情况下我们不需要从参数模式重新生成，以免重复或格式混乱。
            # 简单的判断依据是检查是否包含 "参数" 关键字。
            if "参数" in desc or "Parameters" in desc or "Args:" in desc:
                lines.append(f"- **{name}**: {desc}")
                continue

            # 对于 MCP 工具或其他模式定义的工具，desc 通常只包含功能描述
            # 我们需要从参数中提取参数说明，以符合 NIT 协议要求的格式
            params = func.get("parameters", {})
            props = params.get("properties", {})
            required = params.get("required", [])

            param_parts = []
            for p_name, p_schema in props.items():
                p_desc = p_schema.get("description", "")

                # 标记必填项
                is_required = p_name in required
                req_mark = "" if is_required else "(可选)"

                if p_desc:
                    param_parts.append(f"{p_name}: {p_desc}{req_mark}")
                else:
                    param_parts.append(f"{p_name}{req_mark}")

            full_desc = f"- **{name}**: {desc}"
            if param_parts:
                # 补充参数说明
                # 确保标点符号自然
                if (
                    full_desc
                    and not full_desc.endswith("。")
                    and not full_desc.endswith(".")
                ):
                    full_desc += "。"

                full_desc += " 参数 " + "; ".join(param_parts) + "。"

            lines.append(full_desc)

        return "\n".join(lines)

    def build_system_prompt(
        self,
        variables: Dict[str, Any],
        is_social_mode: bool = False,
        is_work_mode: bool = False,
    ) -> str:
        # 0. 丰富变量
        self._enrich_variables(variables, is_social_mode, is_work_mode)

        # [工作模式专用构建]
        if is_work_mode:
            # 1. 覆盖 NIT 工具描述 (由 dynamic_tools 生成以确保过滤策略生效)
            dynamic_tools = variables.get("dynamic_tools")
            if dynamic_tools:
                variables["available_tools_desc"] = self._generate_tools_description(
                    dynamic_tools
                )
            else:
                # 回退：仅在 dynamic_tools 缺失时尝试从 Dispatcher 获取核心工具
                try:
                    from nit_core.dispatcher import get_dispatcher

                    dispatcher = get_dispatcher()
                    tools_desc = dispatcher.get_tools_description(
                        category_filter="core"
                    )
                    if not tools_desc or len(tools_desc) < 10:
                        tools_desc = dispatcher.get_tools_description()
                    variables["available_tools_desc"] = tools_desc
                except Exception as e:
                    logger.error(f"加载工作工具错误: {e}")
            nit_prompt = self.mdp.get_prompt("components/abilities/nit")
            if nit_prompt:
                content = nit_prompt.content
                content = re.sub(
                    r"### 3\. 执行逻辑与思考[\s\S]*?(?=### 4\.|$)", "", content
                )
                content = content.replace(
                    "在执行任何外部操作时，必须遵循‘思考-行动-观察’的循环。", ""
                )
                variables["ability_nit"] = content

            # 4. 渲染工作模式专用模板
            return self.mdp.render("templates/work", variables)

        # [群聊模式专用构建]
        if variables.get("mode") == "group":
            return self.mdp.render("templates/group", variables)

        # [社交模式专用构建]
        if is_social_mode:
            return self.mdp.render("templates/social", variables)

        # [轻量级模式]
        config = get_config_manager()
        is_lightweight = config.get("lightweight_mode", False)
        if is_lightweight and not is_social_mode:
            return self.mdp.render("templates/lightweight", variables)

        # 1. 渲染模板
        final_prompt = self.mdp.render("templates/system", variables)

        return final_prompt

    def build_instruction_prompt(
        self,
        variables: Dict[str, Any],
        is_social_mode: bool = False,
        is_work_mode: bool = False,
    ) -> str:
        """
        构建指令部分的提示词 (规则, 工具, 思维链)
        通常放在消息列表的最后，作为系统消息提醒模型
        """
        # [工作模式]
        # 使用 templates/work 注入到上下文末尾 (近因效应)
        if is_work_mode:
            blocks = self.mdp.render_blocks("templates/work", variables)
            return blocks.get("footer", "")

        # [主程序模式] (非社交, 非工作)
        # 使用 templates/system 注入到上下文末尾 (近因效应)
        if not is_social_mode:
            # 轻量模式下，指令提示词也需要从轻量模板提取
            # 注意：templates/lightweight.md 也应该有块头/尾结构
            config = get_config_manager()
            is_lightweight = config.get("lightweight_mode", False)
            template_name = (
                "templates/lightweight" if is_lightweight else "templates/system"
            )

            blocks = self.mdp.render_blocks(template_name, variables)
            return blocks.get("footer", "")

        # [社交模式]
        # 社交模式目前暂不追加额外的指令，以免引入不必要的复杂性 (如思考/独白可能不适合 QQ)
        # 如果未来需要，可以创建 instruction_social.md

        return ""

    async def get_rendered_system_prompt(
        self,
        session: AsyncSession,
        is_social_mode: bool = False,
        is_work_mode: bool = False,
        extra_variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        获取渲染后的完整系统提示词。
        1. 加载所有组件
        2. 合并变量
        3. 渲染
        """
        # 获取配置
        configs = {c.key: c.value for c in (await session.exec(select(Config))).all()}

        owner_name = configs.get("owner_name", "主人")
        user_persona = configs.get("user_persona", "未设定")

        # 获取宠物状态
        import json

        from sqlmodel import desc

        state = (
            await session.exec(
                select(PetState).order_by(desc(PetState.updated_at)).limit(1)
            )
        ).first()
        state = state or PetState()

        # 清洗状态字段，防止旧格式的 JSON/XML 污染提示词
        def clean_state_field(val: str, field_name: str) -> str:
            if not val:
                return ""
            val = val.strip()
            # 1. 尝试解析 JSON (针对旧数据 {"mood": "..."} 的情况)
            if val.startswith("{") and val.endswith("}"):
                try:
                    data = json.loads(val)
                    if isinstance(data, dict):
                        # 优先取同名键，否则取第一个字符串值
                        return str(
                            data.get(field_name)
                            or next(
                                (v for v in data.values() if isinstance(v, str)), val
                            )
                        )
                except Exception:
                    pass
            # 2. 移除 XML 标签
            if "<" in val:
                val = re.sub(r"<[^>]+>", "", val)
            return val

        variables = {
            "owner_name": owner_name,
            "user_persona": user_persona,
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "mood": clean_state_field(state.mood, "mood") or "开心",
            "vibe": clean_state_field(state.vibe, "vibe") or "活泼",
            "mind": clean_state_field(state.mind, "mind") or "正在想主人...",
            "memory_context": "",  # 陪伴模式目前不需要复杂的 RAG
            "graph_context": "",  # 知识图谱上下文占位符
        }

        # [Fix] 合并外部传入的变量 (如 social 模式的 xml_context)
        if extra_variables:
            variables.update(extra_variables)

        return self.build_system_prompt(
            variables, is_social_mode=is_social_mode, is_work_mode=is_work_mode
        )

    def clean_history_for_api(self, content: str) -> str:
        """
        清理历史记录中的冗余标签，仅保留 PEROCUE
        """
        if not content:
            return ""
        # 移除 MEMORY, CLICK_MESSAGES, IDLE_MESSAGES, BACK_MESSAGES, REMINDER, TOPIC
        content = re.sub(r"<MEMORY>[\s\S]*?<\/MEMORY>", "", content)
        content = re.sub(r"<CLICK_MESSAGES>[\s\S]*?<\/CLICK_MESSAGES>", "", content)
        content = re.sub(r"<IDLE_MESSAGES>[\s\S]*?<\/IDLE_MESSAGES>", "", content)
        content = re.sub(r"<BACK_MESSAGES>[\s\S]*?<\/BACK_MESSAGES>", "", content)
        content = re.sub(r"<FILE_RESULTS>[\s\S]*?<\/FILE_RESULTS>", "", content)
        content = re.sub(r"<REMINDER>[\s\S]*?<\/REMINDER>", "", content)
        content = re.sub(r"<TOPIC>[\s\S]*?<\/TOPIC>", "", content)
        return content.strip()

    async def compose_messages(
        self,
        history: List[Dict[str, str]],
        variables: Dict[str, Any],
        is_social_mode: bool = False,
        is_work_mode: bool = False,
        user_message: str = "",
        is_multimodal: bool = False,
        session: AsyncSession = None,  # 新增 session 参数
    ) -> List[Dict[str, str]]:
        """
        组装最终发送给 LLM 的消息列表。

        [MDP 重构 v3.0]
        不再使用传统的历史列表追加模式。
        而是采用 "Two-Turn" (两轮制) 或 "Single-Turn" (单轮制) 模式。
        所有的历史记录都已经通过预处理器被压扁并在 _enrich_variables 阶段
        注入到了系统提示词的各个占位符中（如 {{flattened_desktop_history}}）。

        因此，这里的 messages 列表通常只包含：
        1. 系统消息 (包含所有上下文、记忆、历史)
        2. 用户消息 (当前用户输入)
        """
        from core.event_bus import EventBus

        # [钩子] prompt.build.pre
        # 允许 MOD 修改变量 (variables)
        ctx = {
            "variables": variables,
            "is_social_mode": is_social_mode,
            "is_work_mode": is_work_mode,
            "user_message": user_message,
            "session": session,
        }
        await EventBus.publish("prompt.build.pre", ctx)

        # 1. 构建系统提示词
        # 注意：这里 session 参数是必须的，用于获取动态配置
        if not session:
            # 如果调用方没传 session，这可能是一个潜在的 bug，或者我们在同步上下文中
            # 暂时尝试从 variables 中获取，或者创建一个临时的
            # 但 compose_messages 通常在流水线中被调用，流水线应该有 session
            logger.warning("[PromptService] compose_messages 调用时缺少会话！")
            system_content = "系统错误：会话丢失。"
        else:
            system_content = await self.get_rendered_system_prompt(
                session,
                is_social_mode=is_social_mode,
                is_work_mode=is_work_mode,
                extra_variables=variables,
            )

        messages = [{"role": "system", "content": system_content}]

        # 2. 添加用户消息
        # 即使是空消息（例如触发式对话），也最好发一个用户消息以符合某些 LLM 的规范
        # 或者某些情况下系统提示词已经包含了用户输入（如 social 模式的 xml_context）
        # 但通常保持系统 + 用户结构是最稳健的。

        if user_message or is_multimodal:
            # 多模态处理逻辑保持不变
            # ...
            if is_multimodal:
                # 假设历史记录的最后一条是当前的多模态消息，或者我们需要从 variables 中获取
                # 这里简化处理，假设 variables['user_input_multimodal'] 存在
                content = variables.get("user_input_multimodal", user_message)
                messages.append({"role": "user", "content": content})
            else:
                messages.append({"role": "user", "content": user_message})

        # [钩子] prompt.build.post
        # 允许 MOD 修改最终的消息列表 (messages)
        ctx = {"messages": messages, "variables": variables}
        await EventBus.publish("prompt.build.post", ctx)

        return messages
