"""
宠物状态 / 陪伴模式 / 社交模式 Router
从 main.py 提取的 /api/pet/state, /api/companion/*, /api/social/* 路由
"""

import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config_manager import get_config_manager
from database import get_session
from models import AIModelConfig, Config, PetState
from nit_core.plugins.social_adapter.social_service import get_social_service
from schemas import PetStateResponse, ToggleRequest
from services.agent.companion_service import companion_service

router = APIRouter(prefix="/api/pet", tags=["pet"])


@router.get("/state", response_model=PetStateResponse)
async def get_pet_state(session: AsyncSession = Depends(get_session)):  # noqa: B008
    try:
        from services.agent.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        active_agent = agent_manager.get_active_agent()
        active_agent_id = active_agent.id if active_agent else "pero"

        # 简单缓存 — 注意：这里不再使用 app.state，使用模块级缓存
        if active_agent_id in _pet_state_cache:
            cache_entry = _pet_state_cache[active_agent_id]
            if time.time() - cache_entry["time"] < 5:
                state = cache_entry["data"]
                response_data = state.model_dump()
                if active_agent:
                    response_data["active_agent"] = {
                        "id": active_agent.id,
                        "name": active_agent.name,
                    }
                return response_data

        statement = select(PetState).where(PetState.agent_id == active_agent_id)
        state = (await session.exec(statement)).first()

        if not state:
            state = PetState(
                agent_id=active_agent_id,
                mood="开心",
                vibe="正常",
                mind="正在想主人...",
            )
            session.add(state)
            await session.commit()
            await session.refresh(state)

        _pet_state_cache[active_agent_id] = {
            "data": state,
            "time": time.time(),
        }

        response_data = state.model_dump()
        if active_agent:
            response_data["active_agent"] = {
                "id": active_agent.id,
                "name": active_agent.name,
            }

        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# 模块级缓存，替代 app.state.pet_state_cache
_pet_state_cache: dict = {}


@router.get("/companion/status")
async def get_companion_status():
    config_mgr = get_config_manager()
    enabled = config_mgr.get("companion_mode_enabled", False)
    return {"enabled": enabled}


@router.post("/companion/toggle")
async def toggle_companion(
    request: ToggleRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    enabled = request.enabled

    config_mgr = get_config_manager()
    if enabled and not config_mgr.get("lightweight_mode", False):
        raise HTTPException(
            status_code=400, detail="请先开启“轻量模式”后再启动陪伴模式。"
        )

    if enabled:
        config_entry = await session.get(Config, "current_model_id")
        if not config_entry:
            raise HTTPException(
                status_code=400, detail="未配置当前对话模型，无法开启陪伴模式。"
            )

        model_config = await session.get(AIModelConfig, int(config_entry.value))
        if not model_config or not model_config.enable_vision:
            raise HTTPException(
                status_code=400,
                detail="当前对话模型未开启“图片模态”能力，陪伴模式需要模型能够理解屏幕截图。",
            )

    config = await session.get(Config, "companion_mode_enabled")
    if not config:
        config = Config(key="companion_mode_enabled", value="false")
        session.add(config)

    config.value = "true" if enabled else "false"
    config.updated_at = datetime.utcnow()
    await session.commit()

    await get_config_manager().set("companion_mode_enabled", enabled)

    if enabled:
        await companion_service.start()
    else:
        await companion_service.stop()

    return {"status": "success", "enabled": enabled}


# --- 社交模式 ---


@router.get("/social/status")
async def get_social_status():
    config_mgr = get_config_manager()
    enabled = config_mgr.get("enable_social_mode", False)
    return {"enabled": enabled}


@router.post("/social/toggle")
async def toggle_social(
    request: ToggleRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    enabled = request.enabled

    await get_config_manager().set("enable_social_mode", enabled)

    social_service = get_social_service()

    try:
        from nit_core.dispatcher import get_dispatcher

        dispatcher = get_dispatcher()
        dispatcher.reload_tools()
        print(f"[PetRouter] 社交模式切换后 NIT 工具已重载 (启用: {enabled})")
    except Exception as e:
        print(f"[PetRouter] 重载 NIT 工具失败: {e}")

    if enabled:
        await social_service.start()
    else:
        await social_service.stop()

    return {"status": "success", "enabled": enabled}
