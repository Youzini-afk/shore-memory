"""
模型配置 CRUD Router
从 main.py 提取的 /api/models/* 路由
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models import AIModelConfig
from schemas import (
    CreateModelRequest,
    FetchRemoteModelsRequest,
    RemoteModelsResponse,
    StandardResponse,
    UpdateModelRequest,
)

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=List[AIModelConfig])
async def get_models(session: AsyncSession = Depends(get_session)):  # noqa: B008
    return (await session.exec(select(AIModelConfig))).all()


@router.post("", response_model=AIModelConfig)
async def create_model(
    payload: CreateModelRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    model = AIModelConfig(**payload.model_dump())
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model


@router.put("/{model_id}", response_model=AIModelConfig)
async def update_model(
    model_id: int,
    payload: UpdateModelRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    db_model = await session.get(AIModelConfig, model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_model, key, value)

    db_model.updated_at = datetime.utcnow()
    session.add(db_model)
    await session.commit()
    await session.refresh(db_model)
    return db_model


@router.delete("/{model_id}", response_model=StandardResponse)
async def delete_model(model_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    db_model = await session.get(AIModelConfig, model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    await session.delete(db_model)
    await session.commit()
    return StandardResponse(message="模型已成功删除")


@router.post("/remote", response_model=RemoteModelsResponse)
async def fetch_remote_models(payload: FetchRemoteModelsRequest):
    """获取远程服务商提供的模型列表"""
    from services.core.llm_service import LLMService

    llm = LLMService(payload.api_key, payload.api_base, "", provider=payload.provider)
    models = await llm.list_models()
    return RemoteModelsResponse(models=models)
