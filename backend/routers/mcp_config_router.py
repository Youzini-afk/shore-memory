"""
MCP 配置 CRUD Router
从 main.py 提取的 /api/mcp/* 路由
"""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import MCPConfig

router = APIRouter(prefix="/api/mcp", tags=["mcp"])


@router.get("", response_model=List[MCPConfig])
async def get_mcps(session: AsyncSession = Depends(get_session)):  # noqa: B008
    return (await session.exec(select(MCPConfig))).all()


@router.post("", response_model=MCPConfig)
async def create_mcp(
    mcp_data: Dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    mcp_data.pop("id", None)
    mcp_data.pop("created_at", None)
    mcp_data.pop("updated_at", None)
    new_mcp = MCPConfig(**mcp_data)
    session.add(new_mcp)
    await session.commit()
    await session.refresh(new_mcp)
    return new_mcp


@router.put("/{mcp_id}", response_model=MCPConfig)
async def update_mcp(
    mcp_id: int,
    mcp_data: Dict[str, Any] = Body(...),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    db_mcp = await session.get(MCPConfig, mcp_id)
    if not db_mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    for key, value in mcp_data.items():
        if hasattr(db_mcp, key) and key not in ["id", "created_at", "updated_at"]:
            setattr(db_mcp, key, value)
    db_mcp.updated_at = datetime.utcnow()
    session.add(db_mcp)
    await session.commit()
    await session.refresh(db_mcp)
    return db_mcp


@router.delete("/{mcp_id}")
async def delete_mcp(mcp_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    db_mcp = await session.get(MCPConfig, mcp_id)
    if not db_mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
    await session.delete(db_mcp)
    await session.commit()
    return {"status": "success"}
