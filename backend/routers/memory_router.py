import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import ConversationLog
from peroproto import perolink_pb2
from schemas import UpdateChatLogRequest
from services.core.gateway_client import gateway_client
from services.memory.memory_service import MemoryService

router = APIRouter(prefix="/api/memories", tags=["memory"])
# history_router 将作为 memories 的子路由
history_router = APIRouter(prefix="/history", tags=["history"])

from typing import List

from sqlmodel import desc, select

from models import Memory
from schemas import AddMemoryRequest, MemoryGraphResponse, ChatLogResponse

# --- 记忆资源接口 (从 maintenance_router 迁移) ---


@router.get("/list", response_model=List[Memory])
async def list_memories(
    limit: int = 50,
    offset: int = 0,
    date_start: str = None,
    date_end: str = None,
    tags: str = None,
    type: str = None,
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """获取详细记忆列表"""
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


@router.get("/graph", response_model=MemoryGraphResponse)
async def get_memory_graph(
    limit: int = 100,
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """获取记忆图谱"""
    service = MemoryService()
    target_agent = agent_id if agent_id else "pero"
    return await service.get_memory_graph(session, limit, agent_id=target_agent)


@router.get("/tags", response_model=List[Dict[str, Any]])
async def get_tag_cloud(
    agent_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """获取标签云"""
    service = MemoryService()
    target_agent = agent_id if agent_id else "pero"
    return await service.get_tag_cloud(session, agent_id=target_agent)


@router.get("", response_model=List[Memory])
async def query_memories(
    query: str = None,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """基础记忆查询"""
    try:
        stmt = (
            select(Memory).order_by(desc(Memory.timestamp)).offset(offset).limit(limit)
        )
        if query:
            stmt = stmt.where(Memory.content.contains(query))
        return (await session.exec(stmt)).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("", response_model=Memory)
async def add_memory(
    payload: AddMemoryRequest,
    session: AsyncSession = Depends(get_session),
):
    """手动添加记忆"""
    service = MemoryService()
    return await service.save_memory(
        session,
        content=payload.content,
        tags=payload.tags,
        importance=payload.importance,
        msg_timestamp=payload.msgTimestamp,
        source=payload.source,
        memory_type=payload.type,
    )


@router.delete("/{memory_id}")
async def delete_memory(memory_id: int, session: AsyncSession = Depends(get_session)):
    """删除记忆"""
    memory = await session.get(Memory, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    await session.delete(memory)
    await session.commit()
    return {"status": "success", "message": "记忆已抹除喵...", "id": memory_id}


# --- 历史记录接口 (History Logs) ---


async def delete_memory_by_timestamp(
    msg_timestamp: str,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    service = MemoryService()
    await service.delete_by_msg_timestamp(session, msg_timestamp)
    return {"status": "success"}


@history_router.get("/{source}/{session_id}", response_model=List[ChatLogResponse])
async def get_chat_history(
    source: str,
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    date: str = None,
    sort: str = "asc",
    agent_id: Optional[str] = None,  # 新增agent_id参数
    query: Optional[str] = None,  # [特性] 统一搜索
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    service = MemoryService()
    # 若未提供agent_id则默认为"pero"（兼容性考虑）。
    # Dashboard通常查看特定代理。

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
            "session_id": getattr(log, "session_id", ""),
            "source": getattr(log, "source", ""),
            "role": log.role,
            "content": log.content,
            "raw_content": getattr(log, "raw_content", None),  # 返回原始内容
            "timestamp": log.timestamp,
            "sentiment": getattr(log, "sentiment", None),
            "importance": getattr(log, "importance", None),
            "metadata_json": log.metadata_json,
            "pair_id": getattr(log, "pair_id", None),  # 新增pair_id
            "analysis_status": getattr(log, "analysis_status", "pending"),
            "retry_count": getattr(log, "retry_count", 0),
            "last_error": getattr(log, "last_error", None),
        }
        for log in logs
    ]


# retry_analysis 逻辑已移至 maintenance_router.py


@history_router.delete("/{log_id}")
async def delete_chat_log(log_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    try:
        service = MemoryService()
        await service.delete_log(session, log_id)

        # 广播
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
        raise HTTPException(status_code=500, detail=str(e)) from None


@history_router.patch("/{log_id}", response_model=ChatLogResponse)
async def update_chat_log(
    log_id: int,
    payload: UpdateChatLogRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    try:
        log = await session.get(ConversationLog, log_id)
        if not log:
            raise HTTPException(status_code=404, detail="未找到日志")

        log.content = payload.content

        await session.commit()
        await session.refresh(log)

        # 广播
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
        raise HTTPException(status_code=500, detail=str(e)) from None


# 挂载子路由
router.include_router(history_router)
