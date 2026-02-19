import logging
from typing import List, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from models import GroupChatMessage

logger = logging.getLogger(__name__)


class GroupChatDispatcher:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def decide_next_turn(
        self, room_id: str, history: List[GroupChatMessage]
    ) -> Optional[str]:
        """
        决定下一个发言的角色。

        Args:
            room_id: 当前房间 ID
            history: 最近的聊天记录

        Returns:
            str: 下一个发言的角色 ID (agent_id)，或者 None (无需回复)
        """
        # 1. 获取所有可用成员 (排除 user 和 system/butler)
        from services.chat.group_chat_service import GroupChatService

        service = GroupChatService(self.session)
        members = await service.get_room_members(room_id)
        candidate_agents = [
            m.agent_id
            for m in members
            if m.agent_id not in ["user", "system", "Butler"]
        ]

        if not candidate_agents:
            return None

        # 2. 规则判断
        # 规则 A: 如果最后一条是 User 发言，必须有人回复
        last_msg = history[-1]
        if last_msg.sender_id == "user":
            # 简单策略：随机选一个，或者看 @mentions
            # 检查 mentions
            try:
                mentions = []
                if last_msg.mentions_json:
                    import json

                    mentions = json.loads(last_msg.mentions_json)

                # 如果 mention 了在场的 agent
                valid_mentions = [mid for mid in mentions if mid in candidate_agents]
                if valid_mentions:
                    return valid_mentions[0]  # 优先回复第一个被 @ 的
            except Exception:
                pass

            # 否则随机选一个
            import random

            return random.choice(candidate_agents)

        # 规则 B: 如果最后一条是某个 Agent 发言
        if last_msg.sender_id in candidate_agents:
            # 简单策略：有 30% 概率另一个 Agent 接话 (Agent 协作流)
            # 防止无限循环：如果连续 3 条都是 Agent 发言，强制停止
            agent_streak = 0
            for msg in reversed(history):
                if msg.sender_id in candidate_agents:
                    agent_streak += 1
                else:
                    break

            if agent_streak >= 3:
                return None

            import random

            if random.random() < 0.3:
                # 选一个除了刚才发言者之外的 Agent
                others = [a for a in candidate_agents if a != last_msg.sender_id]
                if others:
                    return random.choice(others)

        return None

    async def run_turn(self, room_id: str, agent_id: str):
        """
        执行指定 Agent 的发言回合。
        """
        from services.agent.agent_service import AgentService
        from services.chat.group_chat_service import GroupChatService

        # 1. 构造上下文
        # 注意：这里我们不需要手动构造 history 列表传给 AgentService
        # 因为 AgentService -> PromptService 会自动调用 _get_stronghold_context
        # 并通过 Preprocessor 拉取最新的 Group History
        # 我们只需要调用 AgentService.chat 即可，但入参怎么传？
        # 目前 AgentService.chat 主要是响应 User Input。
        # 这里是 Agent 主动发言 (Self-Correction / Active Response)。
        # 我们可以传入一个空的 user_input，或者特定的触发词。

        agent_service = AgentService(self.session)

        # 2. 调用 Agent
        # 使用 group 模式
        # 为了触发回复，我们可能需要传入一个特殊的 "Trigger" 消息，或者让 AgentService 支持 "无输入思考"
        # 现有的 AgentService.chat 逻辑强依赖 user_input
        # 我们这里暂时模拟一个 "System Trigger"

        # 更好的方式：直接调用 LLM，复用 PromptService 的 system prompt
        # 但这样会绕过 AgentService 的工具执行逻辑
        # 鉴于 GroupChat 模式下工具链比较简单，我们可以直接在 AgentService 中加一个 method
        # 或者直接用 chat 接口，传入 hidden_instruction

        try:
            response_gen = agent_service.chat(
                message="(系统触发：请根据当前群聊上下文进行发言，如果不想说话则输出空)",
                session_id=f"group_{room_id}",  # 使用群聊专用的 session_id
                agent_id=agent_id,
                mode="group",  # 关键：指定模式
                source="group",
            )

            full_response = ""
            async for chunk in response_gen:
                if isinstance(chunk, str):
                    full_response += chunk

            # 3. 保存回复
            if full_response.strip():
                # 清理 XML 等
                # TODO: 更精细的清洗
                clean_content = full_response

                chat_service = GroupChatService(self.session)
                await chat_service.add_message(
                    room_id=room_id,
                    sender_id=agent_id,
                    content=clean_content,
                    role="assistant",
                )

                # 4. 递归触发下一轮 (可选)
                # await self.trigger_next(room_id)
                # 为防止堆栈溢出，建议由外部循环控制，或者使用 asyncio.create_task 延时触发

        except Exception as e:
            logger.error(f"[Dispatcher] Agent {agent_id} 发言失败: {e}")
