"""
语音配置与语音 API Router
从 main.py 提取的 /api/voice-configs/*, /api/voice/*, /api/tts/preview 路由
"""

import os
import uuid
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import VoiceConfig
from services.interaction.tts_service import get_tts_service
from services.perception.asr_service import get_asr_service

router = APIRouter(tags=["voice"])

current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TTSPreviewRequest(BaseModel):
    text: str


# --- 语音配置 CRUD ---


@router.get("/api/voice-configs", response_model=List[VoiceConfig])
async def get_voice_configs(session: AsyncSession = Depends(get_session)):  # noqa: B008
    return (await session.exec(select(VoiceConfig))).all()


@router.post("/api/voice-configs", response_model=VoiceConfig)
async def create_voice_config(
    config_data: Dict[str, Any] = Body(...),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    try:
        name = config_data.get("name")
        if not name:
            raise HTTPException(status_code=400, detail="名称不能为空")

        existing = (
            await session.exec(select(VoiceConfig).where(VoiceConfig.name == name))
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="名称已存在")

        config_data.pop("id", None)
        config_data.pop("created_at", None)
        config_data.pop("updated_at", None)

        new_config = VoiceConfig(**config_data)

        if new_config.is_active:
            others = (
                await session.exec(
                    select(VoiceConfig).where(VoiceConfig.type == new_config.type)
                )
            ).all()
            for other in others:
                other.is_active = False

        session.add(new_config)
        await session.commit()
        await session.refresh(new_config)
        return new_config
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        print(f"创建语音配置时出错: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"创建失败: {str(e)}") from e


@router.put("/api/voice-configs/{config_id}", response_model=VoiceConfig)
async def update_voice_config(
    config_id: int,
    config_data: Dict[str, Any] = Body(...),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    try:
        db_config = await session.get(VoiceConfig, config_id)
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")

        new_name = config_data.get("name")
        if new_name and new_name != db_config.name:
            existing = (
                await session.exec(
                    select(VoiceConfig)
                    .where(VoiceConfig.name == new_name)
                    .where(VoiceConfig.id != config_id)
                )
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="名称已存在")

        is_activating = config_data.get("is_active") and not db_config.is_active
        if is_activating:
            others = (
                await session.exec(
                    select(VoiceConfig)
                    .where(VoiceConfig.type == db_config.type)
                    .where(VoiceConfig.id != config_id)
                )
            ).all()
            for other in others:
                other.is_active = False

        exclude_fields = {"id", "created_at", "updated_at"}
        for key, value in config_data.items():
            if key not in exclude_fields and hasattr(db_config, key):
                setattr(db_config, key, value)

        db_config.updated_at = datetime.utcnow()
        session.add(db_config)
        await session.commit()
        await session.refresh(db_config)
        return db_config
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        print(f"更新语音配置时出错: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}") from e


@router.delete("/api/voice-configs/{config_id}")
async def delete_voice_config(
    config_id: int,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    try:
        db_config = await session.get(VoiceConfig, config_id)
        if not db_config:
            raise HTTPException(status_code=404, detail="Config not found")

        if db_config.is_active:
            raise HTTPException(status_code=400, detail="无法删除当前激活的配置")

        await session.delete(db_config)
        await session.commit()
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        import traceback

        print(f"删除语音配置时出错: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}") from e


# --- 语音 ASR/TTS API ---


@router.post("/api/voice/asr")
async def voice_asr(file: UploadFile = File(...)):  # noqa: B008
    """语音转文字接口"""
    try:
        default_data_dir = os.path.join(current_dir, "data")
        data_dir = os.environ.get("PERO_DATA_DIR", default_data_dir)
        temp_dir = os.path.join(data_dir, "temp_audio")

        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}.wav")
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        asr = get_asr_service()
        text = await asr.transcribe(temp_path)

        with suppress(Exception):
            os.remove(temp_path)

        if not text:
            raise HTTPException(status_code=500, detail="ASR failed")

        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/voice/tts")
async def voice_tts(payload: Dict[str, str] = Body(...)):  # noqa: B008
    """文字转语音接口"""
    text = payload.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    tts = get_tts_service()
    filepath = await tts.synthesize(text)
    if not filepath:
        raise HTTPException(status_code=500, detail="TTS synthesis failed")

    filename = os.path.basename(filepath)
    return {"audio_url": f"/api/voice/audio/{filename}"}


@router.get("/api/voice/audio/{filename}")
async def get_audio_file(filename: str):
    """获取语音文件"""
    default_data_dir = os.path.join(current_dir, "data")
    data_dir = os.environ.get("PERO_DATA_DIR", default_data_dir)
    file_path = os.path.join(data_dir, "temp_audio", filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(file_path, media_type="audio/mpeg")


@router.delete("/api/voice/audio/{filename}")
async def delete_audio(filename: str):
    """手动删除音频文件 (由前端播放完毕后触发)"""
    tts = get_tts_service()
    default_data_dir = os.path.join(current_dir, "data")
    data_dir = os.environ.get("PERO_DATA_DIR", default_data_dir)

    paths_to_check = [
        os.path.join(data_dir, "temp_audio", filename),
        os.path.join(tts.output_dir, filename),
    ]

    for filepath in paths_to_check:
        if os.path.exists(filepath):
            with suppress(Exception):
                os.remove(filepath)

    return {"status": "success"}


@router.post("/api/tts/preview")
async def preview_tts(request: TTSPreviewRequest):
    """
    为给定的文本生成 TTS 音频，应用与语音模式相同的过滤和情绪分析。
    """
    from services.core.realtime_session_manager import realtime_session_manager

    text = request.text
    if not text:
        raise HTTPException(status_code=400, detail="文本为空")

    cleaned_text = realtime_session_manager._clean_text(text, for_tts=True)

    if not cleaned_text or not cleaned_text.strip():
        raise HTTPException(status_code=400, detail="无可朗读的文本内容")

    voice, rate, pitch = realtime_session_manager._get_voice_params(text)

    tts = get_tts_service()
    filepath = await tts.synthesize(cleaned_text, voice=voice, rate=rate, pitch=pitch)

    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=500, detail="TTS 生成失败")

    return FileResponse(filepath, media_type="audio/mpeg", filename="preview.mp3")
