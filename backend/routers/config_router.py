import asyncio
from typing import Dict

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config_manager import get_config_manager
from core.nit_manager import get_nit_manager
from database import get_session
from models import Config
from nit_core.plugins.social_adapter.social_service import get_social_service

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("")
async def get_all_configs(session: AsyncSession = Depends(get_session)):  # noqa: B008
    configs = (await session.exec(select(Config))).all()
    return {c.key: c.value for c in configs}


@router.post("")
async def update_configs(
    configs: Dict[str, str], session: AsyncSession = Depends(get_session)  # noqa: B008
):
    # 检查：工作模式下禁止启用不兼容功能
    try:
        current_session = (
            await session.exec(select(Config).where(Config.key == "current_session_id"))
        ).first()
        is_work_mode = current_session and current_session.value.startswith("work_")

        if is_work_mode:
            blocking_modes = [
                "lightweight_mode",
                "companion_mode",
                "aura_vision_enabled",
            ]
            # 键名中文映射
            name_map = {
                "lightweight_mode": "轻量模式",
                "companion_mode": "陪伴模式",
                "aura_vision_enabled": "主动视觉模式",
            }

            for key, value in configs.items():
                if key in blocking_modes:
                    # 检查是否尝试启用
                    is_enabling = str(value).lower() == "true"
                    if is_enabling:
                        raise HTTPException(
                            status_code=403,
                            detail=f"无法启用{name_map.get(key, key)}：当前处于工作模式（会话隔离中）。请先退出工作模式。",
                        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Config] 工作模式检查失败: {e}")

    for key, value in configs.items():
        config_obj = await session.get(Config, key)
        if config_obj:
            config_obj.value = value
        else:
            config_obj = Config(key=key, value=value)
            session.add(config_obj)

    await session.commit()
    return {"status": "success"}


# 1. 轻量模式
@router.get("/lightweight_mode")
async def get_lightweight_mode():
    return {"enabled": get_config_manager().get("lightweight_mode", False)}


@router.post("/lightweight_mode")
async def set_lightweight_mode(enabled: bool = Body(..., embed=True)):
    await get_config_manager().set("lightweight_mode", enabled)
    return {"status": "success", "enabled": enabled}


# 6. 记忆配置 (Memory Config)
@router.get("/memory")
async def get_memory_config():
    return get_config_manager().get_json("memory_config")


@router.post("/memory")
async def set_memory_config(config: Dict = Body(...)):
    import json
    await get_config_manager().set("memory_config", json.dumps(config))
    return {"status": "success", "config": config}


# 2. 主动视觉
@router.get("/aura_vision")
async def get_aura_vision_mode():
    return {"enabled": get_config_manager().get("aura_vision_enabled", False)}


@router.post("/aura_vision")
async def set_aura_vision_mode(enabled: bool = Body(..., embed=True)):
    await get_config_manager().set("aura_vision_enabled", enabled)

    from services.perception.aura_vision_service import aura_vision_service

    if enabled:
        if not aura_vision_service.is_running:
            if aura_vision_service.initialize():
                asyncio.create_task(aura_vision_service.start_vision_loop())
            else:
                return {
                    "status": "error",
                    "message": "Failed to initialize AuraVision Service",
                }
    else:
        aura_vision_service.stop()

    return {"status": "success", "enabled": enabled}


# 3. 语音合成
@router.get("/tts")
async def get_tts_mode():
    return {"enabled": get_config_manager().get("tts_enabled", True)}


@router.post("/tts")
async def set_tts_mode(enabled: bool = Body(..., embed=True)):
    await get_config_manager().set("tts_enabled", enabled)
    return {"status": "success", "enabled": enabled}


# 4. 社交模式
@router.get("/social_mode")
async def get_social_mode():
    return {"enabled": get_nit_manager().is_plugin_enabled("social_adapter")}


@router.post("/social_mode")
async def set_social_mode(enabled: bool = Body(..., embed=True)):
    # 1. 更新NIT及配置
    get_nit_manager().set_plugin_status("social_adapter", enabled)
    await get_config_manager().set("enable_social_mode", enabled)

    # 2. 更新服务状态
    social_service = get_social_service()

    # 3. 刷新NIT工具
    try:
        from nit_core.dispatcher import get_dispatcher

        dispatcher = get_dispatcher()
        dispatcher.reload_tools()
        print(f"[Config] NIT工具已重载 (社交模式: {enabled})")
    except Exception as e:
        print(f"[Config] NIT工具重载失败: {e}")

    if enabled:
        await social_service.start()
    else:
        await social_service.stop()

    return {
        "status": "success",
        "enabled": enabled,
        "message": "Plugin status updated.",
    }


# 5. 陪伴模式
@router.get("/companion_mode")
async def get_companion_mode():
    return {"enabled": get_config_manager().get("companion_mode_enabled", False)}


@router.post("/companion_mode")
async def set_companion_mode(
    enabled: bool = Body(..., embed=True), session: AsyncSession = Depends(get_session)
):
    # 检查依赖：需先开启轻量模式
    config_mgr = get_config_manager()
    if enabled and not config_mgr.get("lightweight_mode", False):
        raise HTTPException(
            status_code=400, detail="请先开启“轻量模式”后再启动陪伴模式。"
        )

    # [New Requirement] Companion mode requires vision capability in current model
    if enabled:
        config_entry = await session.get(Config, "current_model_id")
        if not config_entry:
            raise HTTPException(status_code=400, detail="未配置当前对话模型，无法开启陪伴模式。")
        
        from models import AIModelConfig
        model_config = await session.get(AIModelConfig, int(config_entry.value))
        if not model_config or not model_config.enable_vision:
            raise HTTPException(
                status_code=400, 
                detail="当前对话模型未开启“图片模态”能力，陪伴模式需要模型能够理解屏幕截图。"
            )

    await config_mgr.set("companion_mode_enabled", enabled)

    from services.agent.companion_service import companion_service

    if enabled:
        await companion_service.start()
    else:
        await companion_service.stop()

    return {"status": "success", "enabled": enabled}
