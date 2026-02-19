import json
import uuid
from typing import List, Optional

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import GroupChatMember, GroupChatMessage, GroupChatRoom


class GroupChatService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_room(
        self, name: str, creator_id: str, member_ids: List[str], description: str = None
    ) -> GroupChatRoom:
        room_id = str(uuid.uuid4())
        room = GroupChatRoom(
            id=room_id, name=name, creator_id=creator_id, description=description
        )
        self.session.add(room)

        # 添加创建者（如果不在 member_ids 中）
        if creator_id not in member_ids:
            self.session.add(
                GroupChatMember(room_id=room_id, agent_id=creator_id, role="admin")
            )

        # 添加成员
        for member_id in member_ids:
            role = "admin" if member_id == creator_id else "member"
            # 检查是否已添加
            existing = (
                await self.session.exec(
                    select(GroupChatMember).where(
                        GroupChatMember.room_id == room_id,
                        GroupChatMember.agent_id == member_id,
                    )
                )
            ).first()
            if not existing:
                self.session.add(
                    GroupChatMember(room_id=room_id, agent_id=member_id, role=role)
                )

        await self.session.commit()
        await self.session.refresh(room)
        return room

    async def list_rooms(self) -> List[GroupChatRoom]:
        statement = select(GroupChatRoom).order_by(desc(GroupChatRoom.created_at))
        return (await self.session.exec(statement)).all()

    async def get_room(self, room_id: str) -> Optional[GroupChatRoom]:
        return await self.session.get(GroupChatRoom, room_id)

    async def get_room_members(self, room_id: str) -> List[GroupChatMember]:
        statement = select(GroupChatMember).where(GroupChatMember.room_id == room_id)
        return (await self.session.exec(statement)).all()

    async def add_message(
        self,
        room_id: str,
        sender_id: str,
        content: str,
        role: str = "user",
        mentions: List[str] = None,
    ) -> GroupChatMessage:
        if mentions is None:
            mentions = []
        msg = GroupChatMessage(
            room_id=room_id,
            sender_id=sender_id,
            content=content,
            role=role,
            mentions_json=json.dumps(mentions),
        )
        self.session.add(msg)
        await self.session.commit()
        await self.session.refresh(msg)

        # 注入记忆（每个 Agent 独立的记忆）
        if content.strip():
            members = await self.get_room_members(room_id)
            from services.memory.memory_service import MemoryService

            for member in members:
                # 不对用户注入，仅对 Agent 注入
                if member.agent_id == "user":
                    continue

                # 上下文处理
                # 如果发送者是自己，标记为 "I said"
                prefix = (
                    "I said" if member.agent_id == sender_id else f"{sender_id} said"
                )
                context_content = f"[{prefix} in Group]: {content}"

                try:
                    await MemoryService.save_memory(
                        session=self.session,
                        content=context_content,
                        tags=f"group_chat,room:{room_id},sender:{sender_id}",
                        memory_type="group_chat",
                        source="group_chat",
                        agent_id=member.agent_id,
                    )
                except Exception as e:
                    print(f"[GroupChat] 为 {member.agent_id} 注入记忆失败: {e}")

        # [Auto-Dispatch] 触发调度器
        # 仅当发送者是 User 或 Agent 时触发 (系统消息不触发，防止死循环)
        if role in ["user", "assistant"] and sender_id != "Butler":
            # 异步触发，不阻塞当前请求
            import asyncio

            asyncio.create_task(self._trigger_dispatch(room_id))

        return msg

    async def _trigger_dispatch(self, room_id: str):
        """后台触发调度器"""
        # 需要新的 Session
        from database import get_session
        from services.chat.group_chat_dispatcher import GroupChatDispatcher

        # 获取最近历史
        # 这里使用一个新的 session 上下文
        async for session in get_session():
            try:
                # 重新初始化 service 以使用新 session
                service = GroupChatService(session)
                history = await service.get_history(room_id, limit=10)

                dispatcher = GroupChatDispatcher(session)
                next_agent = await dispatcher.decide_next_turn(room_id, history)

                if next_agent:
                    print(f"[GroupChat] 调度器决定下一位发言者: {next_agent}")
                    await dispatcher.run_turn(room_id, next_agent)
                else:
                    print("[GroupChat] 调度器决定: 无人接话")
            except Exception as e:
                print(f"[GroupChat] 调度异常: {e}")
            break  # 只运行一次

    async def get_history(
        self, room_id: str, limit: int = 50
    ) -> List[GroupChatMessage]:
        stmt = (
            select(GroupChatMessage)
            .where(GroupChatMessage.room_id == room_id)
            .order_by(desc(GroupChatMessage.timestamp))
            .limit(limit)
        )
        msgs = (await self.session.exec(stmt)).all()
        return sorted(msgs, key=lambda x: x.timestamp)

    @staticmethod
    async def trigger_group_response(room_id: str):
        """静态方法：在后台使用新会话触发群组响应"""
        import asyncio

        asyncio.create_task(GroupChatService._run_group_response_task(room_id))

    @staticmethod
    async def _run_group_response_task(room_id: str):
        from sqlalchemy.orm import sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession

        from database import engine

        try:
            # 为后台任务创建新会话
            async_session = sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
            async with async_session() as session:
                service = GroupChatService(session)
                await service.process_group_response_logic(room_id)
        except Exception as e:
            print(f"[GroupChat] 后台任务失败: {e}")

    async def process_group_response_logic(self, room_id: str):
        """触发群组中所有 Agent 的响应。"""
        from services.agent.agent_service import AgentService

        members = await self.get_room_members(room_id)
        # 过滤掉用户并获取 Agent ID
        agent_ids = [m.agent_id for m in members if m.agent_id != "user"]

        if not agent_ids:
            return

        # 获取最近的历史记录作为上下文
        history_msgs = await self.get_history(room_id, limit=20)

        async def respond_for_agent(agent_id: str):
            try:
                # 1. 为该 Agent 格式化消息
                # 视角转换：
                # - 如果 msg.sender_id == agent_id，则为 'assistant'
                # - 如果 msg.sender_id == 'user'，则为 'user'
                # - 如果 msg.sender_id == other_agent，则为 'user'（外部），但带有前缀

                formatted_msgs = []
                for m in history_msgs:
                    role = "user"
                    content = m.content

                    if m.sender_id == agent_id:
                        role = "assistant"
                    elif m.sender_id == "user":
                        role = "user"
                    else:
                        # 其他 Agent 发言
                        role = "user"
                        content = f"[{m.sender_id}]: {content}"

                    formatted_msgs.append({"role": role, "content": content})

                # 2. 调用 AgentService
                # 我们需要一个新的会话来避免并行运行时的冲突吗？
                # 实际上，self.session 是异步会话，共享它进行读取可能没问题，
                # 但 AgentService 会写入数据库。在并发任务之间共享一个会话是有风险的。
                # 理想情况下，我们应该生成新会话。
                # 但对于 MVP，如果会话共享很难，让我们尝试顺序执行，
                # 或者使用同一个会话但要小心。
                # 为了安全起见，让我们先顺序运行。

                agent_service = AgentService(self.session)
                response_content = ""

                # 使用特定来源 'group_chat'
                async for chunk in agent_service.chat(
                    messages=formatted_msgs,
                    source="group_chat",
                    session_id=f"group_{room_id}",  # 隔离历史记录（虽然我们传递了显式消息）
                    agent_id_override=agent_id,
                ):
                    response_content += chunk

                # 3. 将响应添加到群聊
                if response_content:
                    await self.add_message(
                        room_id, agent_id, response_content, role="assistant"
                    )

            except Exception as e:
                print(f"[GroupChat] {agent_id} 响应失败: {e}")

        # 顺序运行以避免 DB 会话冲突
        for aid in agent_ids:
            await respond_for_agent(aid)
