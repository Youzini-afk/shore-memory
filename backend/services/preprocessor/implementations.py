import datetime
import re
from typing import Any, Dict

import numpy as np
from sqlmodel import desc, select

from models import Config, ConversationLog, PetState
from services.core.embedding_service import embedding_service

from .base import BasePreprocessor


class UserInputPreprocessor(BasePreprocessor):
    """
    从输入消息列表中提取用户的文本消息。
    处理多模态内容。
    """

    @property
    def name(self) -> str:
        return "UserInputExtractor"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        messages = context.get("messages", [])
        user_text_override = context.get("user_text_override")

        user_message = user_text_override if user_text_override else ""
        is_multimodal = False

        if not user_message:
            for m in reversed(messages):
                if m["role"] == "user":
                    content = m.get("content", "")
                    if isinstance(content, str):
                        user_message = content
                    elif isinstance(content, list):
                        is_multimodal = True
                        # 尝试从多模态内容中提取文本
                        texts = [
                            item["text"]
                            for item in content
                            if item.get("type") == "text"
                        ]
                        user_message = " ".join(texts)
                    break

        print(f"[UserInputPreprocessor] 提取用户消息: {user_message[:50]}...")
        context["user_message"] = user_message
        context["is_multimodal"] = is_multimodal
        return context


class HistoryPreprocessor(BasePreprocessor):
    """
    从数据库获取并清理对话历史。
    支持多源历史拉取与压扁 (Flattening) 逻辑，为 MDP 的两轮制拼接提供支持。
    """

    @property
    def name(self) -> str:
        return "HistoryFetcher"

    async def _fetch_and_clean_logs(
        self,
        session,
        memory_service,
        source: str,
        limit: int,
        agent_id: str,
        before_id: str = None,
    ) -> list[Dict[str, str]]:
        """辅助函数：拉取并清理特定源的日志"""
        try:
            # 对于 Group/Desktop 模式，session_id 不作为过滤条件（我们拉取所有模式相关的日志）
            # 但为了保持兼容性，如果 source 是 ide/work，我们仍然通过 session_id 过滤
            query_session_id = None
            if source == "ide" or (
                isinstance(source, str) and source.startswith("work_")
            ):
                query_session_id = source  # 这里 source 可能被用作 session_id

            logs = await memory_service.query_logs(
                session,
                source=source if not query_session_id else None,
                session_id=query_session_id if query_session_id else "all",
                limit=limit,
                agent_id=agent_id,
                before_id=before_id,
            )
        except Exception as e:
            print(f"[HistoryPreprocessor] 拉取 {source} 日志失败: {e}")
            return []

        cleaned_msgs = []
        if not logs:
            return cleaned_msgs

        for log in logs:
            # [优化] 优先使用 raw_content 以获取 NIT 工具调用信息
            # 如果 raw_content 存在，我们尝试从中提取工具调用记录并格式化为 [工具调用历史: TOOLNAME]
            raw_content = log.raw_content
            content = log.content

            # 如果有 raw_content，尝试提取 NIT 标签
            if raw_content:
                # 匹配 <nit-TOOLNAME> 或 <nit>...</nit> (兼容旧版)
                # 我们只提取工具名，忽略参数
                # 匹配模式：<nit-([^>]+)> 或 <nit>
                # 注意：raw_content 可能包含多个工具调用

                # 1. 提取带名称的标签 <nit-xxx>
                tool_calls = re.findall(r"<nit-([a-zA-Z0-9_]+)>", raw_content)

                # 2. 如果没有带名称的标签，尝试提取旧版 <nit> 内部可能包含的信息（旧版较复杂，暂时只处理新版）
                # 或者如果有 <nit> 但没有具体的 nit-xxx，可能是一个通用 nit 块

                if tool_calls:
                    # 去重并格式化
                    # 例如: [工具调用历史: search_files, read_file]
                    unique_tools = sorted(set(tool_calls))
                    tools_str = ", ".join(unique_tools)
                    # 将工具调用记录附加到 content 后面（或者前面？）
                    # 通常工具调用是助手的行为，紧随其回复文本之后
                    if log.role == "assistant":
                        content += f"\n[工具调用历史: {tools_str}]"

            # 清理 XML 标签和 Thinking 块
            content = re.sub(
                r"<!-- PERO_RAG_BLOCK_START.*?-->", "", content, flags=re.S
            )
            content = re.sub(r"<!-- PERO_RAG_BLOCK_END -->", "", content, flags=re.S)
            content = re.sub(
                r"【\s*(?:Thinking|Monologue)\s*:.*?】", "", content, flags=re.S
            )
            content = re.sub(r"<([A-Z_]+)>.*?</\1>", "", content, flags=re.S)
            content = re.sub(r"<[^>]+>", "", content)
            content = content.strip()

            if content:
                cleaned_msgs.append(
                    {"role": log.role, "content": content, "timestamp": log.timestamp}
                )

        return cleaned_msgs

    def _flatten_history(self, messages: list[Dict[str, Any]], bot_name: str) -> str:
        """将消息列表压扁为 XML 格式"""
        if not messages:
            return "<!-- 暂无历史记录 -->"

        flattened_lines = []
        now = datetime.datetime.now()

        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            ts = msg.get("timestamp")

            # 格式化时间
            time_str = ""
            if ts:
                try:
                    # 兼容秒级和毫秒级时间戳
                    if ts > 1e11:  # 毫秒
                        dt = datetime.datetime.fromtimestamp(ts / 1000.0)
                    else:  # 秒
                        dt = datetime.datetime.fromtimestamp(ts)

                    # 如果不是今天的消息，增加日期显示 [MM-DD HH:MM]
                    if dt.date() != now.date():
                        time_str = dt.strftime("%m-%d %H:%M")
                    else:
                        time_str = dt.strftime("%H:%M")
                except Exception:
                    pass

            # 显示名称映射
            display_name = "User"
            if role == "assistant":
                display_name = bot_name
            elif role == "system":
                display_name = "System"
            elif role == "user":
                display_name = "User"  # 或者 owner_name

            # 转义内容，防止破坏 XML 结构
            content = (
                str(content)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            # 构建 XML 标签
            # <message role="user" name="User" time="12:00">Content</message>
            line = f'<message role="{role}" name="{display_name}"'
            if time_str:
                line += f' time="{time_str}"'
            line += f">{content}</message>"

            flattened_lines.append(line)

        return "\n".join(flattened_lines)

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        session = context["session"]
        memory_service = context["memory_service"]
        source = context.get("source", "desktop")
        session_id = context.get("session_id", "default")
        current_messages = context.get("messages", [])
        agent_id = context.get("agent_id", "pero")
        variables = context.get("variables", {})

        # 获取当前 Bot Name
        from core.config_manager import get_config_manager

        config_mgr = get_config_manager()
        bot_name = config_mgr.get("bot_name", "Pero")

        # [配置读取]
        memory_config = config_mgr.get_json("memory_config")

        # 确定当前模式
        mode_key = "desktop"
        if source == "social":
            mode_key = "social"
        elif source == "ide" or session_id.startswith("work_"):
            mode_key = "work"

        # 动态获取 limit
        limit = (
            memory_config.get("modes", {}).get(mode_key, {}).get("context_limit", 20)
        )

        # [多源拉取策略]
        # 1. Group History (群聊模式)
        # 2. Desktop History (桌宠模式)

        # limit 已由上方配置读取决定

        # 拉取 Group History (需要去 GroupChatMessage 表拉取，目前 query_logs 只查 ConversationLog)
        # 这是一个问题：HistoryFetcher 目前只封装了 ConversationLog 的查询。
        # 我们需要在 query_logs 增加对 GroupChatMessage 的支持，或者在这里单独处理。
        # 为了快速实现，我们暂时假设 query_logs 已经支持或者我们在这里直接查 Group 表。
        # 但 GroupChatMessage 结构不同。
        # 临时方案：我们在这里直接查 GroupChatMessage 表。

        from models import GroupChatMessage
        from services.chat.stronghold_service import StrongholdService

        stronghold_service = StrongholdService(session)
        # 获取当前 Agent 所在的 Room
        current_room = await stronghold_service.get_agent_location(agent_id)

        group_history_text = "（暂无群聊记录）"
        if current_room:
            stmt = (
                select(GroupChatMessage)
                .where(GroupChatMessage.room_id == current_room.id)
                .order_by(desc(GroupChatMessage.timestamp))
                .limit(limit)
            )
            group_msgs = (await session.exec(stmt)).all()
            # 翻转为正序
            group_msgs.reverse()

            # 转换为通用格式
            formatted_group_msgs = []
            for m in group_msgs:
                formatted_group_msgs.append(
                    {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                )

            group_history_text = self._flatten_history(formatted_group_msgs, bot_name)

        variables["flattened_group_history"] = group_history_text

        # 拉取 Desktop History (查 ConversationLog)
        desktop_msgs = await self._fetch_and_clean_logs(
            session, memory_service, "desktop", limit, agent_id
        )
        # query_logs (默认 sort='asc') 已经返回了按时间正序排列的记录 (Old -> New)
        # 所以我们不需要再次翻转，除非我们需要倒序显示。
        # Group History 那边是手动 query DESC 然后 reverse 成 ASC。
        # 这里保持一致，使用 ASC。

        variables["flattened_desktop_history"] = self._flatten_history(
            desktop_msgs, bot_name
        )

        # [Legacy Logic 兼容]
        # 为了兼容旧的逻辑（有些地方可能还在用 history_messages），我们保留原有逻辑
        # 但主要用于 Work 模式或 IDE 模式的流式上下文

        enable_history = True
        if source == "social":
            enable_history = False
        if "enable_history" in variables:
            enable_history = variables["enable_history"]

        if not enable_history:
            context["history_messages"] = []
            context["full_context_messages"] = current_messages
            context["earliest_timestamp"] = None
            return context

        # 原有逻辑：根据当前 session_id 拉取上下文 (主要用于 Work Mode 的连续性)
        # 如果是 Group 或 Desktop 模式，我们已经在上面压扁了，这里可以传空，或者为了保险起见传少量
        # 这里的 history_messages 将被 PromptManager 的 compose_messages 忽略（如果采用两轮制）
        # 但为了防止某些旧代码报错，我们还是拉取一下

        context["history_messages"] = []

        # 只有在 Work Mode 下，我们才需要“未压扁”的原始消息列表作为 Context，
        # 因为 Work Mode 可能需要精准的代码上下文，且我们还没有完全迁移 Work Mode 到两轮制（或者 Work Mode 也迁移？）
        # 根据 spec，Work Mode 也使用 XML 标签块拼接。
        # 所以这里的 history_messages 实际上可以为空了，因为所有的历史都进了 variables。

        # 暂时保留 Work Mode 的特殊处理，以防万一
        is_work_context = session_id.startswith("work_") or source == "ide"
        if is_work_context:
            work_msgs = await self._fetch_and_clean_logs(
                session,
                memory_service,
                session_id,
                50,
                agent_id,  # Work Mode session_id
            )
            context["history_messages"] = work_msgs
            # Work Mode 的压扁历史可能需要特殊处理，或者直接用 recent_history_context
            # 现在的 system.md 里 Work Mode 用的是 recent_history_context
            # 我们把 work_msgs 压扁放进 recent_history_context
            variables["recent_history_context"] = self._flatten_history(
                work_msgs, bot_name
            )

        context["full_context_messages"] = (
            current_messages  # 这里的 full_context 仅包含当前消息了
        )

        return context


class RAGPreprocessor(BasePreprocessor):
    """
    检索相关记忆和 PetState。
    """

    @property
    def name(self) -> str:
        return "RAGInjector"

    async def _get_pet_state(self, session, agent_id="pero") -> PetState:
        from sqlmodel import desc

        state = (
            await session.exec(
                select(PetState)
                .where(PetState.agent_id == agent_id)
                .order_by(desc(PetState.updated_at))
                .limit(1)
            )
        ).first()
        if not state:
            state = PetState(agent_id=agent_id)
            session.add(state)
            await session.commit()
            await session.refresh(state)
        return state

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        source = context.get("source", "desktop")

        # [可配置预处理器] 检查 RAG 是否已禁用
        enable_rag = True
        if source == "social":
            enable_rag = False

        variables = context.get("variables", {})
        if "enable_rag" in variables:
            enable_rag = variables["enable_rag"]

        if not enable_rag:
            variables["memory_context"] = ""  # 显式清除
            context["variables"] = variables
            return context

        session = context["session"]
        memory_service = context["memory_service"]
        user_message = context.get("user_message", "")
        full_context_messages = context.get("full_context_messages", [])
        earliest_timestamp = context.get("earliest_timestamp")
        agent_id = context.get("agent_id", "pero")

        # 获取 PetState
        pet_state = await self._get_pet_state(session, agent_id)

        # 获取用户配置
        from core.config_manager import get_config_manager

        config_mgr = get_config_manager()
        configs = {c.key: c.value for c in (await session.exec(select(Config))).all()}
        owner_name = configs.get("owner_name", "主人")
        user_persona = configs.get("user_persona", "未设定")

        # [配置读取] 动态 RAG limit
        memory_config = config_mgr.get_json("memory_config")
        mode_key = "desktop"
        if source == "social":
            mode_key = "social"
        elif source == "ide" or (
            context.get("session_id", "default").startswith("work_")
        ):
            mode_key = "work"

        rag_limit = (
            memory_config.get("modes", {}).get(mode_key, {}).get("rag_limit", 10)
        )

        # 获取相关记忆
        try:
            # [特性] 思考管道：自动链触发
            from services.agent.chain_service import chain_service

            # 1. 尝试路由到思考链
            chain_name = chain_service.route_chain(user_message)
            memory_context = ""

            if chain_name:
                print(f"[RAGPreprocessor] 触发思考链: {chain_name}")
                chain_result = await chain_service.execute_chain(
                    session, chain_name, user_message, agent_id=agent_id
                )
                formatted_chain = chain_service.format_chain_result(chain_result)

                if formatted_chain:
                    memory_context = formatted_chain
                    # 注意：如果链成功，我们跳过标准 RAG 以保持“惯性通道”的焦点。
                else:
                    print(
                        f"[RAGPreprocessor] 链 {chain_name} 未返回结果，回退到标准 RAG。"
                    )
                    chain_name = None  # 回退

            # 2. 标准 RAG（回退或默认）
            if not chain_name:
                # 加权向量：用户 (0.5)，助手 (0.35)，工具 (0.15)

                query_vec = None
                if full_context_messages:
                    # 内容清洗助手
                    def purify(text):
                        if not isinstance(text, str):
                            return ""
                        # 使用 Rust Core 进行高性能清洗
                        try:
                            from pero_memory_core import clean_text

                            return clean_text(text)
                        except ImportError:
                            # 回退到 Python 实现
                            # 移除 base64 图片和大型技术标签
                            import re

                            text = re.sub(
                                r'data:image/[^;]+;base64,[^"\'\s>]+',
                                "[IMAGE_DATA]",
                                text,
                            )
                            text = re.sub(
                                r"<([A-Z_]+)>.*?</\1>",
                                r"<\1>[OMITTED]</\1>",
                                text,
                                flags=re.S,
                            )
                            return text[:2000].strip()

                    # 查找候选
                    last_user = ""
                    last_assistant = ""
                    last_tool = ""

                    for msg in reversed(full_context_messages):
                        role = msg.get("role")
                        content = msg.get("content", "")
                        if role == "user" and not last_user:
                            last_user = purify(content)
                        elif role == "assistant" and not last_assistant:
                            last_assistant = purify(content)
                        elif role == "tool" and not last_tool:
                            last_tool = purify(content)

                        if last_user and last_assistant and last_tool:
                            break

                    # 编码并合并
                    embeddings = []
                    weights = []

                    if last_user:
                        embeddings.append(await embedding_service.encode_one(last_user))
                        weights.append(0.5)
                    if last_assistant:
                        embeddings.append(
                            await embedding_service.encode_one(last_assistant)
                        )
                        weights.append(0.35)
                    if last_tool:
                        embeddings.append(await embedding_service.encode_one(last_tool))
                        weights.append(0.15)

                    if embeddings:
                        # 如果并非所有角色都存在，则将权重归一化为总和为 1.0
                        total_weight = sum(weights)
                        normalized_weights = [w / total_weight for w in weights]

                        # 计算加权平均值
                        merged_vec = np.zeros_like(embeddings[0])
                        for emb, weight in zip(
                            embeddings, normalized_weights, strict=False
                        ):
                            merged_vec += np.array(emb) * weight
                        query_vec = merged_vec.tolist()

                # 执行搜索
                print(f"[RAGPreprocessor] 正在搜索相关记忆: {user_message[:30]}...")
                memories = await memory_service.get_relevant_memories(
                    session,
                    user_message,
                    limit=rag_limit,
                    exclude_after_time=earliest_timestamp,
                    query_vec=query_vec,
                    agent_id=agent_id,
                )
                print(
                    f"[RAGPreprocessor] 找到 {len(memories) if memories else 0} 条记忆。"
                )

                # [特性] RAG 刷新块构建
                # 创建富含元数据的注释块以进行动态刷新
                if memories:
                    # [优化] 简化元数据以减少提示词混乱
                    # 用户反馈：JSON 元数据是多余的，记忆缺少时间戳。

                    def format_memory_item(m):
                        # 如果可用则使用 realTime，否则转换时间戳
                        time_str = m.realTime
                        if not time_str and m.timestamp:
                            try:
                                # 时间戳以毫秒为单位
                                dt = datetime.datetime.fromtimestamp(
                                    m.timestamp / 1000.0
                                )
                                time_str = dt.strftime("%Y-%m-%d %H:%M")
                            except Exception:
                                time_str = ""

                        if time_str:
                            return f"- [{time_str}] {m.content}"
                        return f"- {m.content}"

                    inner_content = "\n".join([format_memory_item(m) for m in memories])

                    # 简化的块标记，无详细 JSON
                    memory_context = f"<!-- PERO_RAG_BLOCK_START -->\n{inner_content}\n<!-- PERO_RAG_BLOCK_END -->"
                else:
                    memory_context = "无相关记忆"

                # [Reinforcement]
                # 注意：mark_memories_accessed 现已在 get_relevant_memories 内部处理
                # 以确保所有访问路径（包括回退）的一致性。

        except Exception as e:
            print(f"[RAGPreprocessor] 检索记忆失败: {e}")
            memory_context = "无相关记忆 (检索出错)"

        # 填充变量
        variables = context.get("variables", {})
        variables.update(
            {
                "current_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "memory_context": memory_context,
                "mood": pet_state.mood,
                "vibe": pet_state.vibe,
                "mind": pet_state.mind,
                "owner_name": owner_name,
                "user_persona": user_persona,
            }
        )
        context["variables"] = variables

        return context


class WeeklyReportPreprocessor(BasePreprocessor):
    """
    独立检索周报：每次对话最多只注入 1 条最相关的周报。
    """

    @property
    def name(self) -> str:
        return "WeeklyReportInjector"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        source = context.get("source", "desktop")

        # [可配置预处理器] 检查图谱是否已禁用
        enable_graph = True
        if source == "social":
            enable_graph = False

        variables = context.get("variables", {})
        if "enable_graph" in variables:
            enable_graph = variables["enable_graph"]

        if not enable_graph:
            variables["graph_context"] = ""
            context["variables"] = variables
            return context

        agent_id = context.get("agent_id", "pero")

        weekly_report_context = ""

        try:
            # [修改] 改为从文件系统读取最新周报 (不再使用数据库检索)
            import os

            from utils.workspace_utils import get_workspace_root

            workspace = get_workspace_root(agent_id)
            report_dir = os.path.join(workspace, "weekly_reports")

            if os.path.exists(report_dir):
                files = [f for f in os.listdir(report_dir) if f.endswith(".md")]
                # 假设文件名格式为 YYYY-MM-DD.md，可以直接排序
                files.sort(reverse=True)

                if files:
                    latest_file = files[0]
                    file_path = os.path.join(report_dir, latest_file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        # 截断以防过长
                        if len(content) > 2000:
                            content = content[:2000] + "\n...(已截断)"

                        weekly_report_context = (
                            f"【最新周报】({latest_file[:-3]})\n{content}"
                        )
                        print(f"[WeeklyReport] 注入了来自 {latest_file} 的周报")
                    except Exception as e:
                        print(f"[WeeklyReport] 读取周报文件失败: {e}")

        except Exception as e:
            print(f"[WeeklyReport] 检索周报失败: {e}")

        variables = context.get("variables", {})
        variables["weekly_report_context"] = weekly_report_context
        context["variables"] = variables

        return context


class GraphFlashbackPreprocessor(BasePreprocessor):
    """
    在记忆图谱上执行逻辑闪回以查找关联碎片。
    """

    @property
    def name(self) -> str:
        return "GraphFlashback"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        session = context["session"]
        memory_service = context["memory_service"]
        user_message = context.get("user_message", "")
        agent_id = context.get("agent_id", "pero")

        if not user_message:
            print("[GraphFlashback] 跳过: 无用户消息")
            return context

        # 执行逻辑闪回
        try:
            print(f"[GraphFlashback] 开始逻辑闪回: {user_message[:30]}...")
            flashback = await memory_service.logical_flashback(
                session, user_message, limit=5, agent_id=agent_id
            )

            graph_context = ""
            if flashback:
                # 格式化闪回碎片
                fragments = [item["name"] for item in flashback]
                graph_context = "关联思绪: " + ", ".join(fragments)
                print(f"[GraphFlashback] 找到 {len(fragments)} 个碎片: {fragments}")
            else:
                print("[GraphFlashback] 未找到碎片。")

            # 填充变量
            variables = context.get("variables", {})
            variables["graph_context"] = graph_context
            context["variables"] = variables

        except Exception as e:
            print(f"[GraphFlashback] 失败: {e}")

        return context


class ConfigPreprocessor(BasePreprocessor):
    """
    加载 LLM 配置并确定能力（视觉、语音）。
    """

    @property
    def name(self) -> str:
        return "ConfigLoader"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:

        agent_service = context.get("agent_service")
        if agent_service:
            config = await agent_service._get_llm_config()
        else:
            # 回退或简化逻辑
            config = {}

        context["llm_config"] = config

        variables = context.get("variables", {})
        variables.update(
            {
                "enable_vision": config.get("enable_vision", False),
                "enable_voice": config.get("enable_voice", False),
                "enable_video": config.get("enable_video", False),
                "vision_status": "",
            }
        )
        context["variables"] = variables
        return context


class SystemPromptPreprocessor(BasePreprocessor):
    """
    使用 PromptManager 构建最终的系统提示词。
    """

    @property
    def name(self) -> str:
        return "SystemPromptInjector"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        source = context.get("source", "desktop")

        # [修复] 社交模式现在在 AgentService 中使用 MDP 管道，因此我们必须生成系统提示词。
        # 以前这被跳过，因为社交提示词是手动构建的。
        # if source == "social":
        #    return context

        # [NIT Security] 即使是手动构建的 Prompt，也需要注入 NIT ID
        # 但如果是社交模式，NIT ID 可能已经在 social_service 中处理了
        # 这里的逻辑主要是针对 IDE/Desktop 模式

        prompt_manager = context["prompt_manager"]
        variables = context.get("variables", {})
        is_voice_mode = context.get("is_voice_mode", False)
        nit_id = context.get("nit_id")

        # [工作模式检测]
        session_id = context.get("session_id", "default")
        source = context.get("source", "desktop")
        is_work_mode = session_id.startswith("work_") or source == "ide"

        # [工作模式上下文注入]
        if is_work_mode:
            try:
                # 获取最近的非工作模式对话 (default session) 作为前情提要
                # 排除所有 work_ 开头的 session，只取日常对话
                stmt = (
                    select(ConversationLog)
                    .where(~ConversationLog.session_id.startswith("work_"))
                    .order_by(desc(ConversationLog.timestamp))
                    .limit(4)
                )

                recent_logs = (await context["session"].exec(stmt)).all()
                # 结果是倒序的 (最新的在前)，我们需要反转回来按时间顺序显示
                recent_logs = sorted(recent_logs, key=lambda x: x.timestamp)

                # 获取当前 Bot Name
                from core.config_manager import get_config_manager

                config_mgr = get_config_manager()
                bot_name = config_mgr.get("bot_name", "Pero")

                context_str = ""
                if recent_logs:
                    context_str = "[近期日常对话回顾]\n"
                    for log in recent_logs:
                        role = "主人" if log.role == "user" else bot_name
                        # 简单的清理
                        content = re.sub(r"<[^>]+>", "", log.content).strip()
                        if len(content) > 100:
                            content = content[:100] + "..."
                        context_str += f"- {role}: {content}\n"

                variables["recent_history_context"] = context_str

            except Exception as e:
                print(f"[SystemPromptBuilder] 注入工作模式上下文失败: {e}")
                variables["recent_history_context"] = ""

        # [修复] 从上下文注入 dynamic_tools 到变量，以便 PromptManager 可以使用它
        if "dynamic_tools" in context:
            variables["dynamic_tools"] = context["dynamic_tools"]

        # [Fix] PromptManager.compose_messages is async and has a new signature
        # Inject is_voice_mode into variables for templates
        if is_voice_mode:
            variables["is_voice_mode"] = True

        final_messages = await prompt_manager.compose_messages(
            history=context.get("history_messages", []),
            variables=variables,
            is_social_mode=context.get("source") == "social",
            is_work_mode=is_work_mode,
            user_message=context.get("user_message", ""),
            is_multimodal=context.get("is_multimodal", False),
            session=context.get("session"),
        )

        # [NIT Security] 将动态握手 ID 注入系统提示词
        # [修复] 社交模式也支持工具调用（如提醒），因此不再跳过 NIT 注入
        if nit_id and final_messages and final_messages[0]["role"] == "system":
            from nit_core.security import NITSecurityManager

            security_prompt = NITSecurityManager.get_injection_prompt(nit_id)
            final_messages[0]["content"] += "\n" + security_prompt

        context["final_messages"] = final_messages
        return context


class PerceptionPreprocessor(BasePreprocessor):
    """
    [NEW] 感知日志注入器
    将 AuraVision 的静默感知记录注入到上下文中。
    """

    @property
    def name(self) -> str:
        return "PerceptionInjector"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from services.perception.multimodal_trigger_service import (
                multimodal_coordinator,
            )

            # 获取最近的感知记录
            recent_perceptions = multimodal_coordinator.get_recent_perceptions(limit=5)

            if not recent_perceptions:
                return context

            # 格式化感知日志
            perception_context = "[Internal Sense Log (Silent Observations)]\n"
            for p in recent_perceptions:
                timestamp = p.get("timestamp", "").split("T")[-1][:8]  # HH:MM:SS
                visual = p.get("visual", "Unknown")
                perception_context += f"- [{timestamp}] Observed: {visual}\n"

            perception_context += "\n(使用这些观察结果来了解用户的近期上下文，但不要显式提及“我看到你”，除非相关。)"

            # 注入变量 (追加到 memory_context)
            variables = context.get("variables", {})
            existing_memory = variables.get("memory_context", "")
            variables["memory_context"] = existing_memory + "\n\n" + perception_context
            context["variables"] = variables

            print(
                f"[PerceptionPreprocessor] 注入了 {len(recent_perceptions)} 条感知日志。"
            )

            # 注入后清空日志?
            # 策略：读取后不清空，只有在 AgentService 真正回复后，
            # 由 MultimodalCoordinator 的 clear_perception_log 清空 (这部分逻辑在 agent_service.py 并没有调用，需要补充)
            # 或者我们在读取后就视为“已消费”？
            # 暂时保持读取，让 Coordinator 的 clear_perception_log 在交互发生时被调用。

            # 补充：AgentService 回复后应该清空。
            # 既然这里是 Preprocessor，说明用户已经发起了对话。
            # 我们可以认为这次对话就会消费掉这些感知。
            multimodal_coordinator.clear_perception_log()

        except ImportError:
            pass
        except Exception as e:
            print(f"[PerceptionPreprocessor] 失败: {e}")

        return context
