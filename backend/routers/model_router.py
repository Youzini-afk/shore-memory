"""
模型配置 CRUD Router
从 main.py 提取的 /api/models/* 路由
"""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import AIModelConfig

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=List[AIModelConfig])
async def get_models(session: AsyncSession = Depends(get_session)):  # noqa: B008
    return (await session.exec(select(AIModelConfig))).all()


@router.post("", response_model=AIModelConfig)
async def create_model(
    model_data: Dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    model_data.pop("id", None)
    model = AIModelConfig(**model_data)
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return model


@router.put("/{model_id}", response_model=AIModelConfig)
async def update_model(
    model_id: int,
    model_data: Dict[str, Any] = Body(...),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    db_model = await session.get(AIModelConfig, model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    for key, value in model_data.items():
        if hasattr(db_model, key) and key not in ["id", "created_at"]:
            setattr(db_model, key, value)
    db_model.updated_at = datetime.utcnow()
    session.add(db_model)
    await session.commit()
    await session.refresh(db_model)
    return db_model


@router.delete("/{model_id}")
async def delete_model(model_id: int, session: AsyncSession = Depends(get_session)):  # noqa: B008
    db_model = await session.get(AIModelConfig, model_id)
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    await session.delete(db_model)
    await session.commit()
    return {"status": "success"}


@router.post("/remote")
async def fetch_remote_models(payload: Dict[str, Any] = Body(...)):  # noqa: B008
    """获取远程服务商提供的模型列表"""
    api_key = payload.get("api_key", "")
    api_base = payload.get("api_base", "https://api.openai.com")
    provider = payload.get("provider", "openai")

    from services.core.llm_service import LLMService

    llm = LLMService(api_key, api_base, "", provider=provider)
    models = await llm.list_models()
    print(f"后端返回模型列表: {models} (服务商: {provider})")
    return {"models": models}
