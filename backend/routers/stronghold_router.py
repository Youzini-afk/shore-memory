from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import AgentProfile, ButlerConfig, StrongholdFacility, StrongholdRoom
from services.chat.stronghold_service import StrongholdService

router = APIRouter(prefix="/api/stronghold", tags=["stronghold"])


@router.get("/facilities", response_model=List[StrongholdFacility])
async def list_facilities(session: AsyncSession = Depends(get_session)):
    service = StrongholdService(session)
    return await service.list_facilities()


@router.post("/facilities", response_model=StrongholdFacility)
async def create_facility(
    name: str,
    description: str,
    icon: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    service = StrongholdService(session)
    return await service.create_facility(name, description, icon)


@router.get("/rooms", response_model=List[StrongholdRoom])
async def list_rooms(
    facility_id: Optional[int] = None, session: AsyncSession = Depends(get_session)
):
    service = StrongholdService(session)
    return await service.list_rooms(facility_id)


@router.post("/rooms", response_model=StrongholdRoom)
async def create_room(
    facility_id: int,
    name: str,
    description: str,
    session: AsyncSession = Depends(get_session),
):
    service = StrongholdService(session)
    return await service.create_room(facility_id, name, description)


@router.get("/butler", response_model=ButlerConfig)
async def get_butler(session: AsyncSession = Depends(get_session)):
    service = StrongholdService(session)
    return await service.get_butler_config()


@router.put("/butler/enabled")
async def update_butler_enabled(
    enabled: bool, session: AsyncSession = Depends(get_session)
):
    service = StrongholdService(session)
    await service.update_butler_enabled(enabled)
    return {"status": "ok"}


@router.post("/butler/execute")
async def execute_butler_instruction(
    instruction: Dict[str, Any], session: AsyncSession = Depends(get_session)
):
    service = StrongholdService(session)
    result = await service.process_butler_instruction(instruction)
    return {"result": result}


@router.get("/rooms/{room_id}/agents", response_model=List[str])
async def get_room_agents(room_id: str, session: AsyncSession = Depends(get_session)):
    service = StrongholdService(session)
    return await service.get_room_agents(room_id)


@router.get("/agents/status", response_model=List[Dict[str, Any]])
async def get_all_agents_status(session: AsyncSession = Depends(get_session)):
    """获取所有已启用的 Agent 及其当前位置"""
    service = StrongholdService(session)
    # 修正：仅获取 is_active=True (即在 LauncherView 中启用的) 且非系统角色
    active_agents = (
        await session.exec(
            select(AgentProfile).where(
                AgentProfile.role != "system",
                AgentProfile.is_active.is_(True),  # noqa: E712
            )
        )
    ).all()

    result = []
    for agent in active_agents:
        loc = await service.get_agent_location(agent.name)
        result.append(
            {
                "name": agent.name,
                "avatar": agent.avatar,
                "room_name": loc.name if loc else "未知区域",
                "room_id": loc.id if loc else None,
            }
        )
    return result


@router.post("/butler/call")
async def call_butler(
    request: Dict[str, str], session: AsyncSession = Depends(get_session)
):
    """
    request: {"agent_id": "user", "query": "xxx"}
    """
    service = StrongholdService(session)
    agent_id = request.get("agent_id", "user")
    query = request.get("query", "")
    await service.process_butler_call(agent_id, query)
    return {"status": "ok"}
