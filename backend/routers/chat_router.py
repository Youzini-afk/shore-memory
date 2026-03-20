"""
Chat Router
从 main.py 提取的 /api/chat 核心路由 (SSE 流式对话)

包含：ChatRequest / ChatMessage 模型、Token 验证、SSE 事件生成
"""

import asyncio
import base64
import json
import logging
import os
import re
from contextlib import suppress
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import Config
from services.agent.agent_service import AgentService
from services.interaction.tts_service import get_tts_service

router = APIRouter(tags=["chat"])

current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


# --- Models for Validation ---


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    source: str = "desktop"
    session_id: str = Field(default="default", alias="sessionId")

    model: Optional[str] = None
    temperature: Optional[float] = None


async def verify_token(
    authorization: Optional[str] = Header(None),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    """
    验证前端传来的 Token。实现"前端不可信"原则的第一步。
    """
    config_stmt = select(Config).where(Config.key == "frontend_access_token")
    config_result = await session.exec(config_stmt)
    db_config = config_result.first()

    expected_token = db_config.value if db_config else "pero_default_token"

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未授权访问：缺少令牌")

    token = authorization.split(" ")[1]
    if token != expected_token:
        raise HTTPException(status_code=403, detail="未授权访问：令牌无效")

    return token


@router.post("/api/chat")
async def chat(
    request: ChatRequest,
    token: str = Depends(verify_token),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    messages = [m.model_dump() for m in request.messages]
    source = request.source
    session_id = request.session_id

    valid_sources = ["desktop", "mobile", "system_trigger", "ide", "qq"]
    if source not in valid_sources:
        print(f"[安全] 检测到无效来源: {source}。正在重置为 desktop。")
        source = "desktop"

    agent = AgentService(session)
    tts_service = get_tts_service()

    async def event_generator():
        full_response_text = ""

        try:
            queue = asyncio.Queue()

            async def status_callback(status_type, message):
                await queue.put(
                    {
                        "type": "status",
                        "payload": {"type": status_type, "message": message},
                    }
                )

            tts_queue = asyncio.Queue()

            async def generate_tts_chunk(text_chunk):
                try:
                    clean_text = re.sub(
                        r"<([A-Z_]+)>.*?</\1>", "", text_chunk, flags=re.S
                    )
                    clean_text = re.sub(r"<[^>]+>", "", clean_text)
                    clean_text = re.sub(
                        r"【(?:Thinking|Monologue).*?】",
                        "",
                        clean_text,
                        flags=re.S | re.IGNORECASE,
                    )
                    clean_text = re.sub(
                        r"\[(?:Thinking|Monologue).*?\]",
                        "",
                        clean_text,
                        flags=re.S | re.IGNORECASE,
                    )
                    clean_text = re.sub(
                        r"\((?:Thinking|Monologue).*?\)",
                        "",
                        clean_text,
                        flags=re.S | re.IGNORECASE,
                    )

                    clean_text = re.sub(r"[\U00010000-\U0010ffff]", "", clean_text)
                    clean_text = re.sub(
                        r"[^\w\s\u4e00-\u9fa5，。！？；：" "（）\n\.,!\?\-]",
                        "",
                        clean_text,
                    )

                    segments = [s.strip() for s in clean_text.split("\n") if s.strip()]
                    if segments:
                        clean_text = segments[-1]

                    clean_text = clean_text.strip()

                    if clean_text:
                        audio_path = await tts_service.synthesize(clean_text)
                        if audio_path and os.path.exists(audio_path):
                            with open(audio_path, "rb") as audio_file:
                                audio_data = base64.b64encode(audio_file.read()).decode(
                                    "utf-8"
                                )

                            with suppress(Exception):
                                os.remove(audio_path)

                            return audio_data
                except Exception as e:
                    print(f"TTS 分块错误: {e}")
                return None

            async def run_tts():
                tts_buffer = ""
                tts_delimiters = re.compile(r"([。！？\.!\?\n]+)")

                filler_played = False
                filler_phrase = "唔...让我想想..."
                filler_cache_path = os.path.join(
                    current_dir, "assets", "filler_thinking.mp3"
                )

                from nit_core.dispatcher import (
                    NITStreamFilter,
                    ThinkingBlockStreamFilter,
                    XMLStreamFilter,
                )

                xml_filter = XMLStreamFilter(
                    tag_names=["THOUGHT", "PEROCUE", "CHARACTER_STATUS", "METADATA"]
                )
                nit_filter = NITStreamFilter()
                thinking_filter = ThinkingBlockStreamFilter()

                try:
                    while True:
                        try:
                            if not filler_played:
                                raw_chunk = await asyncio.wait_for(
                                    tts_queue.get(), timeout=3.0
                                )
                            else:
                                raw_chunk = await tts_queue.get()
                        except asyncio.TimeoutError:
                            if not filler_played:
                                logger.info("检测到 TTS 超时，为 Pero 播放本地垫话...")
                                audio_data = None

                                if os.path.exists(filler_cache_path):
                                    with (
                                        suppress(Exception),
                                        open(filler_cache_path, "rb") as f,
                                    ):
                                        audio_data = base64.b64encode(f.read()).decode(
                                            "utf-8"
                                        )

                                if not audio_data:
                                    audio_data = await generate_tts_chunk(filler_phrase)
                                    if audio_data:
                                        with (
                                            suppress(Exception),
                                            open(filler_cache_path, "wb") as f,
                                        ):
                                            f.write(base64.b64decode(audio_data))
                                        logger.info(
                                            f"已保存垫话到缓存: {filler_cache_path}"
                                        )

                                if audio_data:
                                    await queue.put(
                                        {"type": "audio", "payload": audio_data}
                                    )
                                filler_played = True
                            raw_chunk = await tts_queue.get()

                        if raw_chunk is None:  # Sentinel
                            remaining_xml = xml_filter.flush()
                            remaining_nit = (
                                nit_filter.filter(remaining_xml) + nit_filter.flush()
                            )

                            if remaining_nit:
                                tts_buffer += remaining_nit

                            if tts_buffer.strip():
                                audio_data = await generate_tts_chunk(tts_buffer)
                                if audio_data:
                                    await queue.put(
                                        {"type": "audio", "payload": audio_data}
                                    )
                            break

                        if not filler_played and len(raw_chunk.strip()) > 0:
                            filler_played = True

                        filtered_xml = xml_filter.filter(raw_chunk)
                        filtered_nit = nit_filter.filter(filtered_xml)
                        filtered_thinking = thinking_filter.filter(filtered_nit)

                        tts_buffer += filtered_thinking

                        if len(tts_buffer) > 10:
                            parts = tts_delimiters.split(tts_buffer)
                            if len(parts) > 1:
                                for i in range(0, len(parts) - 1, 2):
                                    sentence = parts[i] + parts[i + 1]
                                    if sentence.strip():
                                        audio_data = await generate_tts_chunk(sentence)
                                        if audio_data:
                                            await queue.put(
                                                {"type": "audio", "payload": audio_data}
                                            )

                                tts_buffer = parts[-1]
                except Exception as e:
                    print(f"TTS 工作线程错误: {e}")
                finally:
                    await queue.put({"type": "done"})

            react_turn = [0]
            turn_buffer = [""]

            def wrapped_status_callback(status, msg):
                if status == "thinking":
                    react_turn[0] += 1
                    if react_turn[0] > 2:
                        turn_buffer[0] = ""
                return status_callback(status, msg)

            async def run_chat():
                try:
                    async for chunk in agent.chat(
                        messages,
                        source=source,
                        session_id=session_id,
                        on_status=wrapped_status_callback,
                    ):
                        if chunk:
                            await queue.put({"type": "text", "payload": chunk})

                            if react_turn[0] <= 1:
                                await tts_queue.put(chunk)
                            else:
                                turn_buffer[0] += chunk

                    if react_turn[0] > 1 and turn_buffer[0].strip():
                        await tts_queue.put(turn_buffer[0])

                except Exception as e:
                    import traceback

                    traceback.print_exc()
                    await queue.put({"type": "error", "payload": str(e)})
                    await tts_queue.put(None)
                finally:
                    await tts_queue.put(None)

            asyncio.create_task(run_chat())
            asyncio.create_task(run_tts())

            while True:
                item = await queue.get()
                if item["type"] == "done":
                    break

                if item["type"] == "error":
                    error_chunk = {
                        "choices": [{"delta": {"content": f"Error: {item['payload']}"}}]
                    }
                    yield f"data: {json.dumps(error_chunk)}\n\n"
                    break

                if item["type"] == "audio":
                    yield f"data: {json.dumps({'audio': item['payload']})}\n\n"

                if item["type"] == "status":
                    status_chunk = {"status": item["payload"]}
                    yield f"data: {json.dumps(status_chunk)}\n\n"

                if item["type"] == "text":
                    chunk = item["payload"]
                    full_response_text += chunk

                    response_chunk = {"choices": [{"delta": {"content": chunk}}]}
                    yield f"data: {json.dumps(response_chunk)}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as e:
            print(f"对话错误: {e}")
            import traceback

            traceback.print_exc()
            error_chunk = {"choices": [{"delta": {"content": f"Error: {str(e)}"}}]}
            yield f"data: {json.dumps(error_chunk)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
