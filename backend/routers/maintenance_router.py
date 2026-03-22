"""
维护与记忆管理 Router
从 main.py 提取的 /api/maintenance/*, /api/memory/reindex,
/api/nit/status, /api/tasks/*, /api/memories/* 路由
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import (
    ConversationLog,
    MaintenanceRecord,
    Memory,
    ScheduledTask,
)
from services.memory.memory_service import MemoryService

router = APIRouter(tags=["maintenance"])


# --- NIT 状态 ---


@router.get("/api/nit/status")
async def get_nit_status():
    from nit_core.dispatcher import get_dispatcher

    dispatcher = get_dispatcher()

    plugin_names = dispatcher.pm.list_plugins()
    plugins_data = [{"name": name} for name in plugin_names]

    return {
        "nit_version": "1.0",
        "plugins_count": len(plugin_names),
        "active_mcp_count": 0,
        "plugins": plugins_data,
    }


# --- 任务 (定时任务) ---


@router.get("/api/tasks", response_model=List[ScheduledTask])
async def get_tasks(
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    statement = select(ScheduledTask).where(not ScheduledTask.is_triggered)
    if agent_id:
        statement = statement.where(ScheduledTask.agent_id == agent_id)
    return (await session.exec(statement)).all()


@router.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    try:
        task = await session.get(ScheduledTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await session.delete(task)
        await session.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/tasks/check")
async def check_tasks(session: AsyncSession = Depends(get_session)):  # noqa: B008
    now = datetime.now()
    tasks = (
        await session.exec(select(ScheduledTask).where(not ScheduledTask.is_triggered))
    ).all()
    triggered_prompts = []

    due_reminders = [
        t
        for t in tasks
        if t.type == "reminder"
        and datetime.fromisoformat(t.time.replace("Z", "+00:00")).replace(tzinfo=None)
        <= now
    ]
    if due_reminders:
        task = due_reminders[0]
        triggered_prompts.append(
            f"【管理系统提醒：Pero，你与主人的约定时间已到，请主动提醒主人。约定内容：{task.content}】"
        )
        task.is_triggered = True
        session.add(task)

    if not triggered_prompts:
        due_topics = [
            t
            for t in tasks
            if t.type == "topic"
            and datetime.fromisoformat(t.time.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
            <= now
        ]
        if due_topics:
            topic_list_str = "\n".join([f"- {t.content}" for t in due_topics])
            triggered_prompts.append(
                f"【管理系统提醒：Pero，以下是你之前想找主人聊的话题（已汇总）：\n{topic_list_str}\n\n请将这些话题自然地融合在一起，作为一次主动的聊天开场。】"
            )

            for t in due_topics:
                t.is_triggered = True
                session.add(t)

    if not triggered_prompts:
        last_log = (
            await session.exec(
                select(ConversationLog)
                .where(ConversationLog.role != "system")
                .order_by(desc(ConversationLog.timestamp))
                .limit(1)
            )
        ).first()
        if last_log and (now - last_log.timestamp).total_seconds() > 1200:
            pass

    await session.commit()
    return {"prompts": triggered_prompts}


# --- 记忆仪表盘 API ---


@router.get("/api/memories/list")
async def list_memories(
    limit: int = 50,
    offset: int = 0,
    date_start: str = None,
    date_end: str = None,
    tags: str = None,
    type: str = None,
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    service = MemoryService()
    target_agent = agent_id if agent_id else "pero"
    return await service.get_all_memories(
        session,
        limit,
        offset,
        date_start,
        date_end,
        tags,
        memory_type=type,
        agent_id=target_agent,
    )


@router.get("/api/memories/graph")
async def get_memory_graph(
    limit: int = 100,
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    service = MemoryService()
    target_agent = agent_id if agent_id else "pero"
    return await service.get_memory_graph(session, limit, agent_id=target_agent)


@router.delete("/api/memories/orphaned_edges")
async def delete_orphaned_edges(session: AsyncSession = Depends(get_session)):  # noqa: B008
    service = MemoryService()
    count = await service.delete_orphaned_edges(session)
    return {"status": "success", "deleted_count": count}


@router.post("/api/memories/scan_lonely")
async def scan_lonely_memories(
    limit: int = 5,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    result = await service.scan_lonely_memories(limit=limit)
    return result


@router.post("/api/memories/maintenance")
async def run_maintenance(session: AsyncSession = Depends(get_session)):  # noqa: B008
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    result = await service.run_maintenance()
    return result


@router.post("/api/memories/dream")
async def trigger_dream(limit: int = 10, session: AsyncSession = Depends(get_session)):  # noqa: B008
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    result = await service.dream_and_associate(limit=limit)
    return result


@router.get("/api/memories/tags")
async def get_tag_cloud(
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    service = MemoryService()
    target_agent = agent_id if agent_id else "pero"
    return await service.get_tag_cloud(session, agent_id=target_agent)


@router.get("/api/memories")
async def get_memories(
    query: str = None,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """获取记忆列表"""
    try:
        stmt = (
            select(Memory).order_by(desc(Memory.timestamp)).offset(offset).limit(limit)
        )
        if query:
            stmt = stmt.where(Memory.content.contains(query))

        memories = (await session.exec(stmt)).all()
        return memories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/memories", response_model=Memory)
async def add_memory(
    payload: Dict[str, Any],
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """手动添加记忆"""
    try:
        service = MemoryService()
        return await service.save_memory(
            session,
            content=payload.get("content", ""),
            tags=payload.get("tags", ""),
            importance=payload.get("importance", 1),
            msg_timestamp=payload.get("msgTimestamp"),
            source=payload.get("source", "desktop"),
            memory_type=payload.get("type", "event"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/memories/{memory_id}")
async def delete_memory(memory_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    """删除记忆"""
    try:
        memory = await session.get(Memory, memory_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Memory not found")

        await session.delete(memory)
        await session.commit()
        return {"status": "success", "id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- 维护 ---


@router.post("/api/maintenance/run")
async def run_maintenance_api(session: AsyncSession = Depends(get_session)):  # noqa: B008
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    return await service.run_maintenance()


@router.post("/api/maintenance/undo/{record_id}")
async def undo_maintenance_api(
    record_id: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    success = await service.undo_maintenance(record_id)
    if not success:
        raise HTTPException(status_code=400, detail="Undo failed or record not found")
    return {"status": "success", "message": "Maintenance undone"}


@router.get("/api/maintenance/records")
async def get_maintenance_records(session: AsyncSession = Depends(get_session)):  # noqa: B008
    """获取最近的维护记录"""
    statement = (
        select(MaintenanceRecord).order_by(desc(MaintenanceRecord.timestamp)).limit(10)
    )
    return (await session.exec(statement)).all()


# --- 记忆重建索引 ---


@router.post("/api/memory/reindex")
async def trigger_reindex(
    agent_id: str = "pero", session: AsyncSession = Depends(get_session)
):  # noqa: B008
    """
    手动触发记忆重索引喵~ 🔄
    用于切换 Embedding 模型后重新生成向量。
    """
    try:
        from services.core.reindex_service import ReindexService

        asyncio.create_task(ReindexService.reindex_all_memories(session, agent_id))
        return {"status": "success", "message": "重索引任务已在后台启动喵~ ✨"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动重索引失败: {str(e)}") from e
