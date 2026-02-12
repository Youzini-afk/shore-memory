import json
import uuid
from typing import Any, Dict, List, Optional

from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import (
    AgentLocation,
    AgentProfile,
    ButlerConfig,
    GroupChatMember,
    GroupChatRoom,
    StrongholdFacility,
    StrongholdRoom,
    get_local_now,
)


class StrongholdService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Initialization ---
    async def ensure_initial_data(self):
        """确保据点系统有默认数据（默认设施和客厅），并归位无家可归的 Agent"""
        print("[Stronghold] Checking initialization...")
        
        # 1. 确保默认设施存在
        default_facility_name = "我的据点"
        facility = await self.get_facility_by_name(default_facility_name)
        if not facility:
            print(f"[Stronghold] Creating default facility: {default_facility_name}")
            facility = await self.create_facility(
                name=default_facility_name, 
                description="温馨的家", 
                icon="HomeFilled"
            )
        
        # 2. 确保默认房间（客厅）存在
        default_room_name = "客厅"
        living_room = await self.get_room_by_name(default_room_name)
        if not living_room:
            print(f"[Stronghold] Creating default room: {default_room_name}")
            living_room = await self.create_room(
                facility_id=facility.id,
                name=default_room_name,
                description="宽敞明亮的公共区域，适合大家聚在一起。",
                allowed_agents=None # 允许所有人
            )
            # 设置一些默认环境
            default_env = {
                "光照": 80,
                "温度": 24,
                "音乐": "Relaxing Piano",
                "清洁度": 100
            }
            living_room.environment_json = json.dumps(default_env)
            self.session.add(living_room)
            await self.session.commit()
            
        # 3. 同步数据库中的 AgentProfile 与 AgentManager 的配置
        from services.agent.agent_manager import get_agent_manager
        am = get_agent_manager()
        
        # 获取所有配置中的 Agent
        all_config_agents = am.agents # dict[id, AgentProfile]
        
        for agent_id in all_config_agents:
            # 检查数据库中是否存在
            db_agent = (await self.session.exec(select(AgentProfile).where(AgentProfile.name == agent_id))).first()
            
            is_active = agent_id in am.enabled_agents
            
            if not db_agent:
                print(f"[Stronghold] Initializing new agent in DB: {agent_id}")
                new_agent = AgentProfile(
                    name=agent_id,
                    avatar="pero.png", # 默认头像
                    role="assistant",
                    is_active=is_active
                )
                self.session.add(new_agent)
            else:
                # 同步激活状态
                if db_agent.is_active != is_active:
                    db_agent.is_active = is_active
                    self.session.add(db_agent)
        
        await self.session.commit()

        # 4. 归位无家可归的 Agent
        # 也要包括虽然没激活但在数据库里的其他 Agent (role != 'system')
        # 这里简化策略：所有非 system 的 agent 都应该有个位置
        all_agents = (await self.session.exec(select(AgentProfile).where(AgentProfile.role != 'system'))).all()
        
        for agent in all_agents:
            # 检查是否已有位置，并且该位置是否有效
            location = await self.session.get(AgentLocation, agent.name)
            
            is_homeless = True
            if location:
                # 验证房间是否存在
                room = await self.session.get(StrongholdRoom, location.room_id)
                if room:
                    is_homeless = False
                else:
                    print(f"[Stronghold] Agent '{agent.name}' in invalid room {location.room_id}, resetting.")
            
            if is_homeless:
                print(f"[Stronghold] Moving homeless agent '{agent.name}' to {default_room_name}")
                await self.move_agent(agent.name, living_room.id)

    # --- Facility Management ---
    async def create_facility(self, name: str, description: str, icon: str = None) -> StrongholdFacility:
        facility = StrongholdFacility(name=name, description=description, icon=icon)
        self.session.add(facility)
        await self.session.commit()
        await self.session.refresh(facility)
        return facility
    
    # --- Butler Config ---
    async def get_butler_config(self) -> ButlerConfig:
        statement = select(ButlerConfig)
        config = (await self.session.exec(statement)).first()
        if not config:
            # Create default if not exists
            config = ButlerConfig(
                name="Butler", 
                persona="[提示] 请使用 group/butler/persona.md 进行人设配置"
            )
            self.session.add(config)
            await self.session.commit()
            await self.session.refresh(config)
        return config

    async def list_facilities(self) -> List[StrongholdFacility]:
        return (await self.session.exec(select(StrongholdFacility))).all()

    async def get_facility_by_name(self, name: str) -> Optional[StrongholdFacility]:
        statement = select(StrongholdFacility).where(StrongholdFacility.name == name)
        return (await self.session.exec(statement)).first()

    # --- Room Management ---
    async def create_room(self, facility_id: int, name: str, description: str, allowed_agents: List[str] = None) -> StrongholdRoom:
        room_id = str(uuid.uuid4())
        room = StrongholdRoom(
            id=room_id,
            facility_id=facility_id,
            name=name,
            description=description,
            allowed_agents_json=json.dumps(allowed_agents or [])
        )
        self.session.add(room)
        # Create linked GroupChatRoom for chatting
        chat_room = GroupChatRoom(
            id=room_id,
            name=name,
            description=description,
            creator_id="system"
        )
        self.session.add(chat_room)

        # Add allowed agents as members (default: system)
        self.session.add(GroupChatMember(room_id=room_id, agent_id="system", role="admin"))
        # Also add user by default
        self.session.add(GroupChatMember(room_id=room_id, agent_id="user", role="member"))

        if allowed_agents:
            for agent_id in allowed_agents:
                self.session.add(GroupChatMember(room_id=room_id, agent_id=agent_id, role="member"))

        await self.session.commit()
        await self.session.refresh(room)
        return room

    async def get_room(self, room_id: str) -> Optional[StrongholdRoom]:
        return await self.session.get(StrongholdRoom, room_id)
    
    async def get_room_by_name(self, name: str) -> Optional[StrongholdRoom]:
        statement = select(StrongholdRoom).where(StrongholdRoom.name == name)
        return (await self.session.exec(statement)).first()

    async def list_rooms(self, facility_id: Optional[int] = None) -> List[StrongholdRoom]:
        if facility_id:
            statement = select(StrongholdRoom).where(StrongholdRoom.facility_id == facility_id)
        else:
            statement = select(StrongholdRoom)
        return (await self.session.exec(statement)).all()

    async def update_room(self, room_id: str, updates: Dict[str, Any]) -> Optional[StrongholdRoom]:
        room = await self.get_room(room_id)
        if not room:
            return None
        
        for key, value in updates.items():
            if hasattr(room, key):
                setattr(room, key, value)
        
        self.session.add(room)
        await self.session.commit()
        await self.session.refresh(room)
        return room

    async def delete_room(self, room_id: str):
        """删除房间（禁止删除客厅）"""
        room = await self.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")
            
        if room.name == "客厅":
            raise ValueError("Living Room cannot be deleted.")
            
        # 1. 将该房间内的 Agent 移到客厅
        agents = await self.get_room_agents(room_id)
        if agents:
            living_room = await self.get_room_by_name("客厅")
            if living_room:
                for agent_id in agents:
                    await self.move_agent(agent_id, living_room.id)
        
        # 2. 删除关联的 GroupChatRoom (Cascade delete might handle members/messages but let's be safe)
        # Actually SQLModel doesn't auto cascade unless configured. We might need to manually clean up.
        # For now, let's just delete the StrongholdRoom. 
        # Ideally we should also delete GroupChatRoom to clean up history or archive it.
        # Let's keep it simple: Delete StrongholdRoom logic.
        
        self.session.delete(room)
        await self.session.commit()


    # --- Agent Location ---
    async def move_agent(self, agent_id: str, room_id: str) -> AgentLocation:
        # Check if room exists
        room = await self.get_room(room_id)
        if not room:
            raise ValueError(f"Room {room_id} not found")

        # Update or create location
        location = await self.session.get(AgentLocation, agent_id)
        if location:
            location.room_id = room_id
            location.updated_at = get_local_now()
        else:
            location = AgentLocation(agent_id=agent_id, room_id=room_id)
        
        self.session.add(location)
        await self.session.commit()
        await self.session.refresh(location)
        return location

    async def get_agent_location(self, agent_id: str) -> Optional[StrongholdRoom]:
        location = await self.session.get(AgentLocation, agent_id)
        if location:
            return await self.get_room(location.room_id)
        return None

    async def get_room_agents(self, room_id: str) -> List[str]:
        statement = select(AgentLocation.agent_id).where(AgentLocation.room_id == room_id)
        return (await self.session.exec(statement)).all()

    # --- Environment ---
    async def update_environment_variable(self, room_id: str, key: str, value: Any):
        room = await self.get_room(room_id)
        if not room:
            return
        
        env = json.loads(room.environment_json)
        env[key] = value
        room.environment_json = json.dumps(env)
        
        self.session.add(room)
        await self.session.commit()
        await self.session.refresh(room)

    # --- Butler Logic ---
    async def process_butler_instruction(self, instruction: Dict[str, Any]) -> str:
        """
        Process JSON instruction from Butler.
        Returns a result string.
        """
        action = instruction.get("action")
        params = instruction.get("params", {})

        if action == "create_room":
            facility_name = params.get("facility_name", "Default")
            facility = await self.get_facility_by_name(facility_name)
            if not facility:
                facility = await self.create_facility(name=facility_name, description="Auto-created facility")
            
            room = await self.create_room(
                facility_id=facility.id,
                name=params.get("name"),
                description=params.get("description"),
                allowed_agents=params.get("allowed_agents")
            )
            return f"Room '{room.name}' created in facility '{facility.name}'."

        elif action == "update_room_env":
            room_name = params.get("room_name")
            room = await self.get_room_by_name(room_name)
            if room:
                await self.update_environment_variable(room.id, params.get("key"), params.get("value"))
                return f"Updated environment variable '{params.get('key')}' in room '{room_name}'."
            return f"Room '{room_name}' not found."

        elif action == "move_agent":
            agent_id = params.get("agent_id")
            room_name = params.get("target_room")
            room = await self.get_room_by_name(room_name)
            if room:
                await self.move_agent(agent_id, room.id)
                return f"Moved agent '{agent_id}' to room '{room_name}'."
            return f"Room '{room_name}' not found."
            
        elif action == "create_facility":
            name = params.get("name")
            description = params.get("description")
            await self.create_facility(name, description)
            return f"Facility '{name}' created."

        elif action == "delete_room":
            room_name = params.get("room_name")
            room = await self.get_room_by_name(room_name)
            if room:
                try:
                    await self.delete_room(room.id)
                    return f"Room '{room_name}' deleted."
                except ValueError as e:
                    return f"Failed to delete room: {str(e)}"
            return f"Room '{room_name}' not found."

        return f"Unknown action: {action}"

    async def process_butler_call(self, agent_id: str, query: str):
        """
        处理 Agent 对管家的呼叫请求。
        1. 收集上下文
        2. 调用 LLM 生成 Narrative 和 Maintenance Actions
        3. 执行 Actions
        4. 将 Narrative 作为系统消息插入群聊
        """
        from services.core.llm_service import llm_service
        from services.mdp.manager import mdp
        
        # 1. 获取上下文
        # 修复: prompt_service._get_stronghold_context 可能不存在或逻辑不完整
        # 我们在这里手动构建基础 Context，不依赖 prompt_service 的具体实现细节
        context = {}
        
        # 获取当前 Agent 的位置
        current_room = await self.get_agent_location(agent_id)
        if current_room:
             context["current_room_name"] = current_room.name
             context["stronghold_environment"] = current_room.environment_json
        else:
             context["current_room_name"] = "未知"
             context["stronghold_environment"] = "{}"

        # 补充更详细的 Context
        # (1) 所有房间列表
        all_rooms = await self.list_rooms()
        rooms_desc = []
        for r in all_rooms:
            # 简略描述，节省 Token
            rooms_desc.append(f"- {r.name} (ID: {r.id}): {r.description}")
        context["all_rooms_list"] = "\n".join(rooms_desc)

        # (2) 所有 Agent 位置状态
        # 获取所有非系统 Agent
        all_agents = (await self.session.exec(select(AgentProfile).where(AgentProfile.role != 'system'))).all()
        agents_status = []
        for agent in all_agents:
            loc = await self.get_agent_location(agent.name)
            loc_name = loc.name if loc else "Unknown"
            agents_status.append(f"- {agent.name}: currently in {loc_name} (Active: {agent.is_active})")
        context["all_agents_status"] = "\n".join(agents_status)

        # 从 MDP 加载管家人设
        persona_prompt = mdp.get_prompt("group/butler/persona")
        context["persona"] = persona_prompt.content if persona_prompt else "你是据点的 AI 管家。"
        
        context["agent_name"] = agent_id
        context["user_query"] = query
        
        # 渲染 flattened_group_history
        # 注意：这里需要复用 HistoryFetcher 的逻辑，或者简化处理
        # 为简单起见，我们假设 prompt_service._get_stronghold_context 还没包含 history
        # 我们手动获取一下
        # TODO: 更好的方式是重构 Preprocessor 让其可复用
        # 这里暂时手动获取最近 10 条
        from models import GroupChatMessage
        current_room = await self.get_agent_location(agent_id)
        if current_room:
            stmt = select(GroupChatMessage).where(GroupChatMessage.room_id == current_room.id).order_by(desc(GroupChatMessage.timestamp)).limit(10)
            msgs = (await self.session.exec(stmt)).all()
            msgs.reverse()
            history_text = "\n".join([f"- {m.role}: {m.content}" for m in msgs])
            context["flattened_group_history"] = history_text
            context["current_room_name"] = current_room.name
        else:
            context["flattened_group_history"] = "（无历史）"
            context["current_room_name"] = "未知"

        # 2. 渲染 Prompt
        prompt = mdp.render("group/butler/narrate_and_maintain", context)
        
        # 3. 调用 LLM
        # 使用 JSON Mode
        try:
            response_text = await llm_service.chat_completion(
                messages=[{"role": "system", "content": prompt}],
                model="gpt-4o", # 建议使用强模型
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response_text)
            narrative = result.get("narrative", "")
            actions = result.get("maintenance_actions", [])
            
            # 4. 执行 Actions
            for action in actions:
                await self.process_butler_instruction(action)
                
            # 5. 插入 Narrative 到群聊
            if narrative and current_room:
                # 插入一条 role='system' 消息，sender_id='Butler'
                msg = GroupChatMessage(
                    room_id=current_room.id,
                    sender_id="Butler",
                    content=narrative,
                    role="system", 
                    mentions_json="[]",
                    timestamp=get_local_now()
                )
                self.session.add(msg)
                await self.session.commit()
                
        except Exception as e:
            print(f"[StrongholdService] 管家处理失败: {e}")
            import traceback
            traceback.print_exc()

    async def update_butler_enabled(self, enabled: bool):
        config = await self.get_butler_config()
        config.enabled = enabled
        self.session.add(config)
        await self.session.commit()
