"""
系统状态与杂项 Router
从 main.py 提取的 /api/ping, /health, /api/system/*, /api/open-path,
/api/gateway/token, /api/stats/overview, /api/configs/*, /api/configs/waifu-texts 路由
"""

import json
import logging
import os
import subprocess
from datetime import datetime
from typing import Dict, Optional

import psutil
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import (
    Config,
    ConversationLog,
    Memory,
    MemoryRelation,
    PetState,
    ScheduledTask,
)

router = APIRouter(tags=["system"])

current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)


@router.get("/api/ping")
async def ping():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@router.get("/health")
async def health_check():
    return {"status": "healthy"}


@router.get("/api/system/status")
async def get_system_status():
    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return {
            "cpu": {"percent": cpu_percent, "count": psutil.cpu_count()},
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
            },
            "disk": {"total": disk.total, "used": disk.used, "percent": disk.percent},
            "boot_time": psutil.boot_time(),
        }
    except Exception as e:
        print(f"获取系统状态错误: {e}")
        return {"error": str(e)}


@router.post("/api/open-path")
async def open_path(payload: Dict[str, str] = Body(...)):  # noqa: B008
    """打开本地文件或文件夹"""
    path = payload.get("path")
    if not path:
        raise HTTPException(status_code=400, detail="Path is required")

    path = os.path.normpath(path)

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path does not exist")

    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        try:
            if os.path.isfile(path):
                subprocess.Popen(
                    ["explorer", "/select,", path], startupinfo=startupinfo
                )
            else:
                os.startfile(path)
        except Exception:
            try:
                os.startfile(path)
            except Exception as inner_e:
                print(f"打开路径 {path} 时出错: {inner_e}")
                raise HTTPException(status_code=500, detail=str(inner_e)) from inner_e
    else:
        subprocess.Popen(["xdg-open", path])

    return {"status": "success", "message": f"Opened {path}"}


@router.get("/api/gateway/token")
async def get_gateway_token_api():
    """获取 Gateway Token (用于前端连接 Gateway)"""
    try:
        token_path = os.path.join(current_dir, "data", "gateway_token.json")
        if os.path.exists(token_path):
            with open(token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"token": data.get("token")}
        raise HTTPException(status_code=404, detail="Token not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/stats/overview")
async def get_overview_stats(
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """
    获取概览页面的统计数据（总数），解耦渲染数量和显示数量。
    """
    try:
        mem_statement = select(func.count()).select_from(Memory)
        if agent_id:
            mem_statement = mem_statement.where(Memory.agent_id == agent_id)
        mem_count = (await session.exec(mem_statement)).one()

        log_statement = select(func.count()).select_from(ConversationLog)
        if agent_id:
            log_statement = log_statement.where(ConversationLog.agent_id == agent_id)
        log_count = (await session.exec(log_statement)).one()

        task_statement = select(func.count()).select_from(ScheduledTask)
        if agent_id:
            task_statement = task_statement.where(ScheduledTask.agent_id == agent_id)
        task_count = (await session.exec(task_statement)).one()

        return {
            "total_memories": mem_count,
            "total_logs": log_count,
            "total_tasks": task_count,
        }
    except Exception as e:
        logger.error(f"Failed to get overview stats: {e}")
        return {"total_memories": 0, "total_logs": 0, "total_tasks": 0}


# --- 配置 ---


@router.get("/api/configs")
async def get_configs(session: AsyncSession = Depends(get_session)):  # noqa: B008
    configs = (await session.exec(select(Config))).all()
    return {c.key: c.value for c in configs}


@router.post("/api/configs")
async def update_config(
    configs: Dict[str, str],
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    # [检查] 工作模式下阻止启用不兼容模式
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
            name_map = {
                "lightweight_mode": "轻量模式",
                "companion_mode": "陪伴模式",
                "aura_vision_enabled": "主动视觉模式",
            }

            for key, value in configs.items():
                if key in blocking_modes:
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
            config_obj.value = str(value)
        else:
            config_obj = Config(key=key, value=str(value))
            session.add(config_obj)

    await session.commit()

    # 刷新 Embedding Service 状态
    try:
        from services.core.embedding_service import embedding_service

        await embedding_service.refresh_config(session)
    except Exception as e:
        print(f"[Config] 刷新 Embedding Service 失败: {e}")

    return {"status": "success"}


@router.get("/api/configs/waifu-texts")
async def get_waifu_texts(session: AsyncSession = Depends(get_session)):  # noqa: B008
    """获取动态生成的 Live2D 台词配置 (Agent 专属)"""
    try:
        from services.agent.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        active_agent = agent_manager.get_active_agent()
        agent_id = active_agent.id if active_agent else "pero"

        agent_dir = os.path.join(current_dir, "services", "mdp", "agents", agent_id)
        texts_path = os.path.join(agent_dir, "waifu_texts.json")

        if os.path.exists(texts_path):
            try:
                with open(texts_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Main] 加载代理 {agent_id} 的 waifu_texts 失败: {e}")

        config = await session.get(Config, "waifu_dynamic_texts")
        if config:
            return json.loads(config.value)

        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- 系统重置 ---


@router.post("/api/system/reset")
async def reset_system(session: AsyncSession = Depends(get_session)):  # noqa: B008
    """一键恢复出厂设置：清理所有记忆、对话记录、状态和任务，但保留模型配置"""
    try:
        await session.exec(delete(MemoryRelation))
        await session.exec(delete(ConversationLog))
        await session.exec(delete(ScheduledTask))
        await session.exec(delete(Memory))
        await session.exec(delete(PetState))

        keep_configs = [
            "current_model_id",
            "reflection_model_id",
            "reflection_enabled",
            "global_llm_api_key",
            "global_llm_api_base",
            "frontend_access_token",
        ]
        await session.exec(delete(Config).where(Config.key.not_in(keep_configs)))

        default_state = PetState()
        session.add(default_state)

        await session.commit()
        return {"status": "success", "message": "系统已成功恢复出厂设置"}
    except Exception as e:
        await session.rollback()
        import traceback

        print(f"重置系统时出错: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, detail=f"恢复出厂设置失败: {str(e)}"
        ) from e
