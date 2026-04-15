"""
维护与记忆管理 Router
从 main.py 提取的 /api/maintenance/*, /api/memory/reindex,
/api/nit/status, /api/tasks/*, /api/memories/* 路由
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import sessionmaker
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from schemas import (
    ImportStoryRequest,
    ScheduledTaskResponse,
)

from database import engine, get_session
from models import ConversationLog, MaintenanceRecord, ScheduledTask
from models import TriviumSyncTask
from peroproto import perolink_pb2
from services.core.gateway_client import gateway_client
from services.memory.memory_service import MemoryService
from services.memory.memory_importer import MemoryImporter

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


async def _run_retry_background(log_id: int):
    from services.memory.scorer_service import ScorerService

    try:
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            scorer = ScorerService(session)
            await scorer.retry_interaction(log_id)
            # 广播更新
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = "backend_main"
            envelope.target_id = "broadcast"
            envelope.timestamp = int(time.time() * 1000)
            envelope.request.action_name = "log_updated"
            envelope.request.params["id"] = str(log_id)
            envelope.request.params["operation"] = "update"
            await gateway_client.send(envelope)
    except Exception as e:
        print(f"[Maintenance] 后台重试日志 {log_id} 失败: {e}")


# --- 记忆运维细分路由 (从 memory_router 迁移) ---


@router.post("/memory/import")
async def import_story_maintenance(
    request: ImportStoryRequest,
    session: AsyncSession = Depends(get_session),
):
    """从 memory_router 迁移：导入故事初始化记忆"""
    importer = MemoryImporter(session)
    result = await importer.import_story(request.story, request.agent_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/memory/run_secretary")
async def run_memory_secretary_maintenance(
    session: AsyncSession = Depends(get_session),
):
    """从 memory_router 迁移：手工触发记忆秘书"""
    from services.memory.reflection_service import ReflectionService

    try:
        service = ReflectionService(session)
        return await service.run_maintenance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/memory/history/{log_id}/retry")
async def retry_log_analysis_maintenance(
    log_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """从 memory_router 迁移：重新分析聊天记录"""
    log = await session.get(ConversationLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="未找到日志")
    background_tasks.add_task(_run_retry_background, log_id)
    return {"status": "queued", "message": "分析重试已在后台启动喵"}


@router.get("/nit/status")
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


@router.get("/tasks", response_model=List[ScheduledTaskResponse])
async def get_tasks(
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    statement = select(ScheduledTask).where(not ScheduledTask.is_triggered)
    if agent_id:
        statement = statement.where(ScheduledTask.agent_id == agent_id)
    return (await session.exec(statement)).all()


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    try:
        task = await session.get(ScheduledTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await session.delete(task)
        await session.commit()
        return {"status": "success", "message": "任务已被移除喵"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/tasks/check")
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


# --- 记忆运维资产保留分界线 ---


@router.delete("/memory/orphaned_edges")
async def delete_orphaned_edges(session: AsyncSession = Depends(get_session)):
    service = MemoryService()
    count = await service.delete_orphaned_edges(session)
    return {"status": "success", "message": f"清理完成，共移除 {count} 条孤立边喵~", "deleted_count": count}


@router.post("/memory/scan_lonely")
async def scan_lonely_memories(
    limit: int = 5,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    return await service.scan_lonely_memories(limit=limit)


@router.post("/memory/legacy_maintenance")
async def run_legacy_maintenance(session: AsyncSession = Depends(get_session)):
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    return await service.run_maintenance()


@router.post("/memory/dream")
async def trigger_dream(limit: int = 10, session: AsyncSession = Depends(get_session)):
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    return await service.dream_and_associate(limit=limit)


# --- 维护 ---


@router.post("/maintenance/run")
async def run_maintenance_api(session: AsyncSession = Depends(get_session)):  # noqa: B008
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    return await service.run_maintenance()


@router.post("/maintenance/undo/{record_id}")
async def undo_maintenance_api(
    record_id: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    from services.memory.reflection_service import ReflectionService

    service = ReflectionService(session)
    success = await service.undo_maintenance(record_id)
    if not success:
        raise HTTPException(status_code=400, detail="Undo failed or record not found")
    return {"status": "success", "message": "维护记录已撤销喵！", "record_id": record_id}


@router.get("/maintenance/records")
async def get_maintenance_records(session: AsyncSession = Depends(get_session)):  # noqa: B008
    """获取最近的维护记录"""
    statement = (
        select(MaintenanceRecord).order_by(desc(MaintenanceRecord.timestamp)).limit(10)
    )
    return (await session.exec(statement)).all()


# --- 记忆重建索引 ---


@router.post("/memory/reindex")
async def trigger_reindex(
    agent_id: str = "pero", session: AsyncSession = Depends(get_session)
):  # noqa: B008
    """
    手动触发记忆重索引喵~ 🔄
    用于切换 Embedding 模型后重新生成向量。
    """
    try:
        from services.core.reindex_service import ReindexService

        asyncio.create_task(
            ReindexService.reindex_memories_with_session(session, agent_id)
        )
        return {"status": "success", "message": "重索引任务已在后台启动喵~ ✨"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动重索引失败: {str(e)}") from e


@router.post("/memory/rebuild_trivium")
async def trigger_rebuild_trivium(
    agent_id: str = "pero", session: AsyncSession = Depends(get_session)
):  # noqa: B008
    """
    手动触发 TriviumDB 全量重建。
    用于 SQLite 与向量图谱脱节后的回放恢复。
    """
    try:
        from services.core.reindex_service import ReindexService

        result = await ReindexService.rebuild_trivium_store_with_session(
            session, agent_id
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"TriviumDB 重建失败: {str(e)}"
        ) from e


@router.post("/memory/retry_trivium_sync")
async def retry_trivium_sync(
    agent_id: Optional[str] = None,
    store_name: Optional[str] = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
):  # noqa: B008
    """
    手动触发 TriviumDB 补偿任务重试。
    用于补写历史失败的节点或关系同步任务。
    """
    try:
        from services.memory.trivium_sync_service import TriviumSyncService

        return await TriviumSyncService.retry_pending_tasks(
            session,
            agent_id=agent_id,
            store_name=store_name,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"TriviumDB 补偿重试失败: {str(e)}"
        ) from e


@router.get("/memory/trivium_sync_tasks", response_model=List[TriviumSyncTask])
async def list_trivium_sync_tasks(
    agent_id: Optional[str] = None,
    store_name: Optional[str] = None,
    status: Optional[str] = None,
    operation: Optional[str] = None,
    min_retry_count: Optional[int] = None,
    max_retry_count: Optional[int] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):  # noqa: B008
    """
    获取 TriviumDB 补偿任务列表。
    支持按 agent、store、状态、操作类型、重试次数和时间范围过滤，便于多 store 运维排障。
    """
    try:
        from services.memory.trivium_sync_service import TriviumSyncService

        return await TriviumSyncService.list_tasks(
            session,
            agent_id=agent_id,
            store_name=store_name,
            status=status,
            operation=operation,
            min_retry_count=min_retry_count,
            max_retry_count=max_retry_count,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"获取 TriviumDB 补偿任务列表失败: {str(e)}"
        ) from e


@router.get("/memory/trivium_sync_summary")
async def get_trivium_sync_summary(
    agent_id: Optional[str] = None,
    store_name: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):  # noqa: B008
    """
    获取 TriviumDB 补偿任务摘要。
    返回按状态、按 store、按操作类型的聚合情况、失败排行和健康标记，便于观察多 store 健康度。
    """
    try:
        from services.memory.trivium_sync_service import TriviumSyncService

        return await TriviumSyncService.get_task_summary(
            session,
            agent_id=agent_id,
            store_name=store_name,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"获取 TriviumDB 补偿任务摘要失败: {str(e)}"
        ) from e
