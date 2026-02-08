import time
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from database import engine, get_session
from models import ConversationLog
from peroproto import perolink_pb2
from services.gateway_client import gateway_client
from services.memory_importer import MemoryImporter
from services.memory_secretary_service import MemorySecretaryService
from services.memory_service import MemoryService

router = APIRouter(prefix="/api/memory", tags=["memory"])
history_router = APIRouter(prefix="/api/history", tags=["history"])
legacy_memories_router = APIRouter(prefix="/api/memories", tags=["memory-legacy"])


class ImportStoryRequest(BaseModel):
    story: str
    agent_id: Optional[str] = "pero"


@router.post("/import_story")
async def import_story(
    request: ImportStoryRequest, session: AsyncSession = Depends(get_session)
):
    """
    Import a story/diary to initialize long-term memory.
    Extracts events using LLM and saves them as a sequential memory chain.
    """
    importer = MemoryImporter(session)
    result = await importer.import_story(request.story, request.agent_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.post("/secretary/run")
async def run_memory_secretary(session: AsyncSession = Depends(get_session)):
    try:
        service = MemorySecretaryService(session)
        return await service.run_maintenance()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@legacy_memories_router.delete("/by_timestamp/{msg_timestamp}")
async def delete_memory_by_timestamp(
    msg_timestamp: str, session: AsyncSession = Depends(get_session)
):
    service = MemoryService()
    await service.delete_by_msg_timestamp(session, msg_timestamp)
    return {"status": "success"}


@history_router.get("/{source}/{session_id}")
async def get_chat_history(
    source: str,
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    date: str = None,
    sort: str = "asc",
    agent_id: Optional[str] = None,  # Add agent_id param
    query: Optional[str] = None,  # [Feature] Unified Search
    session: AsyncSession = Depends(get_session),
):
    service = MemoryService()
    # If agent_id is not provided, default to "pero" to maintain backward compatibility,
    # OR we can make it optional in service.query_logs?
    # service.query_logs defaults to "pero".
    # If we want to support "all agents" when agent_id is None, we need to modify service.
    # But usually dashboard views a specific agent.
    # Let's pass agent_id if provided, otherwise default "pero" (handled by service default).

    target_agent = agent_id if agent_id else "pero"
    logs = await service.query_logs(
        session,
        source,
        session_id,
        limit,
        offset=offset,
        date_str=date,
        sort=sort,
        agent_id=target_agent,
        query=query,
    )
    return [
        {
            "id": log.id,
            "role": log.role,
            "content": log.content,
            "raw_content": getattr(log, "raw_content", None),  # Return raw content
            "timestamp": log.timestamp,
            "sentiment": getattr(log, "sentiment", None),
            "importance": getattr(log, "importance", None),
            "metadata_json": log.metadata_json,
            "pair_id": getattr(log, "pair_id", None),  # Added pair_id
            "analysis_status": getattr(log, "analysis_status", "pending"),
            "retry_count": getattr(log, "retry_count", 0),
            "last_error": getattr(log, "last_error", None),
        }
        for log in logs
    ]


async def run_retry_background(log_id: int):
    from services.scorer_service import ScorerService

    try:
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            scorer = ScorerService(session)
            await scorer.retry_interaction(log_id)

            # Broadcast update
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
        print(f"[MemoryRouter] 后台重试日志 {log_id} 失败: {e}")


@history_router.post("/{log_id}/retry_analysis")
async def retry_log_analysis(
    log_id: int,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    log = await session.get(ConversationLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    background_tasks.add_task(run_retry_background, log_id)
    return {"status": "queued", "message": "Analysis retry started in background"}


@history_router.delete("/{log_id}")
async def delete_chat_log(log_id: int, session: AsyncSession = Depends(get_session)):
    try:
        service = MemoryService()
        await service.delete_log(session, log_id)

        # Broadcast
        try:
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = "backend_main"
            envelope.target_id = "broadcast"
            envelope.timestamp = int(time.time() * 1000)
            envelope.request.action_name = "log_updated"
            envelope.request.params["id"] = str(log_id)
            envelope.request.params["operation"] = "delete"
            await gateway_client.send(envelope)
        except Exception as e:
            print(f"广播删除失败: {e}")

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@history_router.patch("/{log_id}")
async def update_chat_log(
    log_id: int,
    payload: Dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
):
    try:
        log = await session.get(ConversationLog, log_id)
        if not log:
            raise HTTPException(status_code=404, detail="Log not found")
        if "content" in payload:
            log.content = payload["content"]
        await session.commit()
        await session.refresh(log)

        # Broadcast
        try:
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
            print(f"广播更新失败: {e}")

        return log
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
