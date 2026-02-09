import datetime
import re
from typing import Any, Dict

import numpy as np
from sqlmodel import desc, select

from models import Config, ConversationLog, PetState
from services.embedding_service import embedding_service

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
    """

    @property
    def name(self) -> str:
        return "HistoryFetcher"

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        session = context["session"]
        memory_service = context["memory_service"]
        source = context.get("source", "desktop")
        session_id = context.get("session_id", "default")
        current_messages = context.get("messages", [])
        agent_id = context.get("agent_id", "pero")

        # [可配置预处理器] 检查是否通过配置禁用了历史记录获取
        # 默认为 True，除非显式禁用
        # 社交模式：默认禁用（因为它提供自己的上下文）
        enable_history = True
        if source == "social":
            enable_history = False

        # 允许通过变量覆盖（如果是 SocialService 注入的）
        variables = context.get("variables", {})
        if "enable_history" in variables:
            enable_history = variables["enable_history"]

        if not enable_history:
            context["history_messages"] = []
            context["full_context_messages"] = current_messages
            context["earliest_timestamp"] = None
            return context

        # 获取最近的日志
        try:
            # [上下文窗口调整]
            # 工作模式需要更长的上下文用于编码任务。
            is_work_context = session_id.startswith("work_") or source == "ide"

            # 策略调整：先拉取足够多的日志 (例如 200 条)，然后基于 Token 进行截断
            limit = 200 if is_work_context else 40

            # [特性] 预览提示词 (历史截止)
            before_id = variables.get("history_before_id")

            history_logs = await memory_service.query_logs(
                session,
                source,
                session_id,
                limit=limit,
                agent_id=agent_id,
                before_id=before_id,
            )
        except Exception as e:
            print(f"[HistoryPreprocessor] 获取历史日志失败: {e}")
            history_logs = []

        history_messages = []
        earliest_timestamp = None

        if history_logs:
            earliest_timestamp = history_logs[0].timestamp
            # print(f"[History] Context Window Start: {earliest_timestamp}")
            for log in history_logs:
                # Clean tags
                content = log.content

                content = re.sub(
                    r"<!-- PERO_RAG_BLOCK_START.*?-->", "", content, flags=re.S
                )
                content = re.sub(
                    r"<!-- PERO_RAG_BLOCK_END -->", "", content, flags=re.S
                )

                # 过滤掉 Thinking 和 Monologue 块，避免污染上下文
                content = re.sub(
                    r"【\s*(?:Thinking|Monologue)\s*:.*?】", "", content, flags=re.S
                )

                content = re.sub(r"<([A-Z_]+)>.*?</\1>", "", content, flags=re.S)
                content = re.sub(r"<[^>]+>", "", content)
                content = content.strip()
                if content:
                    history_messages.append({"role": log.role, "content": content})

        # [基于 Token 的截断]
        # 如果处于工作模式，我们使用 100K Token 的滑动窗口策略
        if is_work_context and history_messages:
            try:
                import tiktoken

                enc = tiktoken.get_encoding("cl100k_base")  # 适用于 GPT-4/GPT-3.5

                MAX_TOKENS = 100000  # 100K Limit
                current_tokens = 0
                truncated_history = []

                # 从最新的消息开始累加 (history_messages 是按时间顺序排列的，所以我们要倒序遍历)
                for msg in reversed(history_messages):
                    content = msg.get("content", "")
                    tokens = len(enc.encode(content))

                    if current_tokens + tokens > MAX_TOKENS:
                        print(
                            f"[History] 达到 Token 上限 ({current_tokens} + {tokens} > {MAX_TOKENS}). 正在截断旧消息。"
                        )
                        break

                    current_tokens += tokens
                    truncated_history.insert(0, msg)  # 保持原有顺序插入头部

                history_messages = truncated_history

            except ImportError:
                print("[History] 未找到 tiktoken。回退到消息计数限制。")
                # 回退：如果 tiktoken 失败，则保留最后 100 条消息
                if len(history_messages) > 100:
                    history_messages = history_messages[-100:]
            except Exception as e:
                print(f"[History] Token 截断失败: {e}")

        # 去重逻辑
        if current_messages and history_messages:

            def _safe_get_text(msg):
                c = msg.get("content", "")
                if isinstance(c, str):
                    return c.strip()
                elif isinstance(c, list):
                    return " ".join(
                        [item["text"] for item in c if item.get("type") == "text"]
                    ).strip()
                return ""

            first_msg_content = _safe_get_text(current_messages[0])
            match_index = -1
            for i in range(len(history_messages) - 1, -1, -1):
                if history_messages[i]["content"] == first_msg_content:
                    is_match = True
                    for j in range(
                        1, min(len(current_messages), len(history_messages) - i)
                    ):
                        if history_messages[i + j]["content"] != _safe_get_text(
                            current_messages[j]
                        ):
                            is_match = False
                            break
                    if is_match:
                        match_index = i
                        break

            if match_index != -1:
                history_messages = history_messages[:match_index]

        context["history_messages"] = history_messages
        context["earliest_timestamp"] = earliest_timestamp

        # 我们暂时不将它们合并到 "messages" 中，而是保持分离以提供灵活性
        # 但通常我们可能希望有一个 "full_context_messages" 列表
        context["full_context_messages"] = history_messages + current_messages

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
        configs = {c.key: c.value for c in (await session.exec(select(Config))).all()}
        owner_name = configs.get("owner_name", "主人")
        user_persona = configs.get("user_persona", "未设定")

        # 获取相关记忆
        try:
            # [特性] 思考管道：自动链触发
            from services.chain_service import chain_service

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
                        embeddings.append(embedding_service.encode_one(last_user))
                        weights.append(0.5)
                    if last_assistant:
                        embeddings.append(embedding_service.encode_one(last_assistant))
                        weights.append(0.35)
                    if last_tool:
                        embeddings.append(embedding_service.encode_one(last_tool))
                        weights.append(0.15)

                    if embeddings:
                        # 如果并非所有角色都存在，则将权重归一化为总和为 1.0
                        total_weight = sum(weights)
                        normalized_weights = [w / total_weight for w in weights]

                        # 计算加权平均值
                        merged_vec = np.zeros_like(embeddings[0])
                        for emb, weight in zip(embeddings, normalized_weights, strict=False):
                            merged_vec += np.array(emb) * weight
                        query_vec = merged_vec.tolist()

                # 执行搜索
                print(f"[RAGPreprocessor] 正在搜索相关记忆: {user_message[:30]}...")
                memories = await memory_service.get_relevant_memories(
                    session,
                    user_message,
                    limit=10,
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

        session = context["session"]
        memory_service = context["memory_service"]
        user_message = context.get("user_message", "")
        agent_id = context.get("agent_id", "pero")

        weekly_report_context = ""

        try:
            # 使用 get_relevant_memories 但限制类型为 weekly_report
            # 如果 user_message 为空，则取最新的

            reports = []

            if user_message:
                # 语义检索最相关的一条
                reports = await memory_service.get_relevant_memories(
                    session,
                    user_message,
                    limit=1,
                    filter_tags=["weekly_report"],
                    memory_type="weekly_report",  # 确保只检索此类型
                    agent_id=agent_id,
                )
            else:
                # 如果没有用户输入（可能是系统触发），则取最新的一条
                from sqlmodel import desc

                from models import Memory

                stmt = (
                    select(Memory)
                    .where(Memory.memory_type == "weekly_report")
                    .where(Memory.agent_id == agent_id)
                    .order_by(desc(Memory.timestamp))
                    .limit(1)
                )
                reports = (await session.exec(stmt)).all()

            if reports:
                report = reports[0]
                weekly_report_context = (
                    f"【相关周报】({report.realTime})\n{report.content}"
                )
                print(f"[WeeklyReport] 注入了来自 {report.realTime} 的周报")

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
        full_context_messages = context.get("full_context_messages", [])
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

        final_messages = prompt_manager.compose_messages(
            full_context_messages,
            variables,
            is_voice_mode=is_voice_mode,
            is_social_mode=context.get("source") == "social",  # Pass is_social_mode
            is_work_mode=is_work_mode,
        )

        # [NIT Security] 将动态握手 ID 注入系统提示词
        # [修复] 社交模式不支持工具，因此跳过 NIT 注入
        if (
            nit_id
            and source != "social"
            and final_messages
            and final_messages[0]["role"] == "system"
        ):
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
            from services.multimodal_trigger_service import multimodal_coordinator

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
