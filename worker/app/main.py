import json
import os
import re
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="shore-memory-worker", version="0.1.0")


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    embedding: list[float]


class TurnMessage(BaseModel):
    role: str
    content: str


class ScoreTurnRequest(BaseModel):
    agent_id: str
    user_uid: Optional[str] = None
    channel_uid: Optional[str] = None
    session_uid: Optional[str] = None
    scope: str
    source: str
    messages: list[TurnMessage]
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentStatePatch(BaseModel):
    mood: Optional[str] = None
    vibe: Optional[str] = None
    mind: Optional[str] = None


class MemoryDraft(BaseModel):
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    importance: float = 5.0
    sentiment: Optional[str] = None
    memory_type: str = "event"
    scope: str
    source: str
    user_uid: Optional[str] = None
    channel_uid: Optional[str] = None
    session_uid: Optional[str] = None


class ScoreTurnResponse(BaseModel):
    memories: list[MemoryDraft] = Field(default_factory=list)
    state_patch: Optional[AgentStatePatch] = None


class ReflectionMemoryInput(BaseModel):
    id: int
    content: str
    importance: float
    scope: str
    created_at: str


class ReflectRequest(BaseModel):
    agent_id: str
    memories: list[ReflectionMemoryInput]


class ReflectResponse(BaseModel):
    summary_memories: list[MemoryDraft] = Field(default_factory=list)
    retire_memory_ids: list[int] = Field(default_factory=list)
    state_patch: Optional[AgentStatePatch] = None
    report: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    api_key = os.getenv("PMW_EMBEDDING_API_KEY", "").strip()
    api_base = os.getenv("PMW_EMBEDDING_API_BASE", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.getenv("PMW_EMBEDDING_MODEL", "").strip()

    if not api_key or not model:
        raise HTTPException(
            status_code=503,
            detail="embedding worker is not configured with PMW_EMBEDDING_API_KEY and PMW_EMBEDDING_MODEL",
        )

    url = f"{api_base}/embeddings" if not api_base.endswith("/embeddings") else api_base
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "input": [text]}

    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"embedding upstream error: {exc.response.text}") from exc
        data = response.json()

    items = data.get("data") or []
    if not items or not items[0].get("embedding"):
        raise HTTPException(status_code=502, detail="embedding upstream returned no embedding")

    return EmbedResponse(embedding=items[0]["embedding"])


@app.post("/v1/tasks/score-turn", response_model=ScoreTurnResponse)
async def score_turn(req: ScoreTurnRequest) -> ScoreTurnResponse:
    if not req.messages:
        return ScoreTurnResponse()

    llm_result = await maybe_llm_score_turn(req)
    if llm_result is not None:
        return llm_result

    return heuristic_score_turn(req)


@app.post("/v1/tasks/reflect", response_model=ReflectResponse)
async def reflect(req: ReflectRequest) -> ReflectResponse:
    if len(req.memories) < 4:
        return ReflectResponse(report={"mode": "noop", "reason": "not_enough_memories"})

    llm_result = await maybe_llm_reflect(req)
    if llm_result is not None:
        return llm_result

    return heuristic_reflect(req)


async def maybe_llm_score_turn(req: ScoreTurnRequest) -> Optional[ScoreTurnResponse]:
    client = OpenAICompatClient.from_env(prefix="PMW_LLM")
    if client is None:
        return None

    transcript = "\n".join(f"{msg.role}: {msg.content}" for msg in req.messages)
    system_prompt = (
        "You are a memory scoring worker.\n"
        "Extract at most 2 durable long-term memories from the conversation.\n"
        "Return strict JSON with keys memories and optional state_patch.\n"
        "Each memory must include content, tags, importance, sentiment, memory_type, scope, source, user_uid, channel_uid, session_uid, metadata.\n"
        "Only keep durable preferences, commitments, plans, significant facts, or relationship-relevant events."
    )
    user_prompt = json.dumps(
        {
            "agent_id": req.agent_id,
            "scope": req.scope,
            "source": req.source,
            "user_uid": req.user_uid,
            "channel_uid": req.channel_uid,
            "session_uid": req.session_uid,
            "conversation": transcript,
        },
        ensure_ascii=False,
    )

    data = await client.chat_json(system_prompt, user_prompt)
    if not isinstance(data, dict):
        return None

    memories = []
    for item in data.get("memories", [])[:2]:
        if not isinstance(item, dict) or not str(item.get("content", "")).strip():
            continue
        memories.append(
            MemoryDraft(
                content=str(item.get("content", "")).strip(),
                tags=[str(tag) for tag in item.get("tags", []) if str(tag).strip()],
                metadata=item.get("metadata") or {},
                importance=float(item.get("importance", 5.0)),
                sentiment=(str(item.get("sentiment")).strip() or None)
                if item.get("sentiment") is not None
                else None,
                memory_type=str(item.get("memory_type", "event")).strip() or "event",
                scope=str(item.get("scope", req.scope)).strip() or req.scope,
                source=str(item.get("source", req.source)).strip() or req.source,
                user_uid=str(item.get("user_uid", req.user_uid or "")).strip() or req.user_uid,
                channel_uid=str(item.get("channel_uid", req.channel_uid or "")).strip() or req.channel_uid,
                session_uid=str(item.get("session_uid", req.session_uid or "")).strip() or req.session_uid,
            )
        )

    state_patch = None
    raw_state_patch = data.get("state_patch")
    if isinstance(raw_state_patch, dict):
        state_patch = AgentStatePatch(
            mood=as_optional_str(raw_state_patch.get("mood")),
            vibe=as_optional_str(raw_state_patch.get("vibe")),
            mind=as_optional_str(raw_state_patch.get("mind")),
        )

    return ScoreTurnResponse(memories=memories, state_patch=state_patch)


async def maybe_llm_reflect(req: ReflectRequest) -> Optional[ReflectResponse]:
    client = OpenAICompatClient.from_env(prefix="PMW_LLM")
    if client is None:
        return None

    system_prompt = (
        "You are a memory reflection worker.\n"
        "Consolidate old low-importance memories into at most 2 summary memories.\n"
        "Return strict JSON with keys summary_memories, retire_memory_ids, optional state_patch, report.\n"
        "Only retire memory ids that are safely represented by the new summaries."
    )
    user_prompt = json.dumps(
        {
            "agent_id": req.agent_id,
            "memories": [memory.model_dump() for memory in req.memories],
        },
        ensure_ascii=False,
    )

    data = await client.chat_json(system_prompt, user_prompt)
    if not isinstance(data, dict):
        return None

    summary_memories = []
    for item in data.get("summary_memories", [])[:2]:
        if not isinstance(item, dict) or not str(item.get("content", "")).strip():
            continue
        summary_memories.append(
            MemoryDraft(
                content=str(item.get("content", "")).strip(),
                tags=[str(tag) for tag in item.get("tags", []) if str(tag).strip()],
                metadata=item.get("metadata") or {},
                importance=float(item.get("importance", 4.0)),
                sentiment=as_optional_str(item.get("sentiment")),
                memory_type=str(item.get("memory_type", "summary")).strip() or "summary",
                scope=str(item.get("scope", "shared")).strip() or "shared",
                source=str(item.get("source", "reflection")).strip() or "reflection",
                user_uid=as_optional_str(item.get("user_uid")),
                channel_uid=as_optional_str(item.get("channel_uid")),
                session_uid=as_optional_str(item.get("session_uid")),
            )
        )

    retire_memory_ids = [
        int(value) for value in data.get("retire_memory_ids", []) if isinstance(value, int)
    ]
    state_patch = None
    if isinstance(data.get("state_patch"), dict):
        state_patch = AgentStatePatch(
            mood=as_optional_str(data["state_patch"].get("mood")),
            vibe=as_optional_str(data["state_patch"].get("vibe")),
            mind=as_optional_str(data["state_patch"].get("mind")),
        )

    return ReflectResponse(
        summary_memories=summary_memories,
        retire_memory_ids=retire_memory_ids,
        state_patch=state_patch,
        report=data.get("report") or {"mode": "llm"},
    )


def heuristic_score_turn(req: ScoreTurnRequest) -> ScoreTurnResponse:
    conversation = "\n".join(msg.content.strip() for msg in req.messages if msg.content.strip())
    if not conversation:
        return ScoreTurnResponse()

    last_user = next((msg.content.strip() for msg in reversed(req.messages) if msg.role == "user"), "")
    assistant_reply = next((msg.content.strip() for msg in reversed(req.messages) if msg.role == "assistant"), "")
    source_text = last_user or conversation
    tags = []
    importance = 5.0
    sentiment = detect_sentiment(source_text)

    if re.search(r"(提醒|记得|不要忘|后天|明天|周[一二三四五六日天])", source_text):
        tags.extend(["plan", "reminder"])
        importance = 7.0
    if re.search(r"(喜欢|爱吃|讨厌|不喜欢|偏好)", source_text):
        tags.extend(["preference"])
        importance = max(importance, 6.0)
    if re.search(r"(出差|旅行|生日|考试|面试|搬家)", source_text):
        tags.extend(["life_event"])
        importance = max(importance, 7.0)

    content = assistant_reply or source_text
    if assistant_reply and last_user:
        content = f"用户提到：{last_user}；随后得到回应：{assistant_reply}"
    elif last_user:
        content = last_user

    draft = MemoryDraft(
        content=content[:800],
        tags=dedupe(tags),
        metadata={"strategy": "heuristic"},
        importance=importance,
        sentiment=sentiment,
        memory_type="event" if "preference" not in tags else "preference",
        scope=req.scope,
        source=req.source,
        user_uid=req.user_uid,
        channel_uid=req.channel_uid,
        session_uid=req.session_uid,
    )

    state_patch = None
    if sentiment == "positive":
        state_patch = AgentStatePatch(mood="开心", vibe="亲近", mind="觉得这段对话值得记住")
    elif sentiment == "negative":
        state_patch = AgentStatePatch(mood="认真", vibe="关心", mind="需要留意用户当前的情绪和需求")

    return ScoreTurnResponse(memories=[draft], state_patch=state_patch)


def heuristic_reflect(req: ReflectRequest) -> ReflectResponse:
    selected = req.memories[: min(len(req.memories), 8)]
    summary_lines = [memory.content.strip() for memory in selected if memory.content.strip()]
    if len(summary_lines) < 4:
        return ReflectResponse(report={"mode": "noop", "reason": "too_few_nonempty_memories"})

    content = "近期低权重记忆总结：\n" + "\n".join(f"- {line}" for line in summary_lines[:8])
    summary = MemoryDraft(
        content=content[:1500],
        tags=["summary", "reflection"],
        metadata={"strategy": "heuristic_reflection", "source_memory_count": len(selected)},
        importance=4.0,
        sentiment=None,
        memory_type="summary",
        scope="shared",
        source="reflection",
        user_uid=None,
        channel_uid=None,
        session_uid=None,
    )
    return ReflectResponse(
        summary_memories=[summary],
        retire_memory_ids=[memory.id for memory in selected],
        state_patch=AgentStatePatch(mood="平静", vibe="整理中", mind="刚完成一轮记忆整合"),
        report={"mode": "heuristic", "retired_count": len(selected)},
    )


def detect_sentiment(text: str) -> Optional[str]:
    lower = text.lower()
    if any(token in lower for token in ["开心", "高兴", "喜欢", "顺利", "nice", "love"]):
        return "positive"
    if any(token in lower for token in ["难过", "生气", "烦", "讨厌", "糟糕", "angry", "sad"]):
        return "negative"
    return "neutral"


def dedupe(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def as_optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


class OpenAICompatClient:
    def __init__(self, api_key: str, api_base: str, model: str) -> None:
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model

    @classmethod
    def from_env(cls, prefix: str) -> Optional["OpenAICompatClient"]:
        api_key = os.getenv(f"{prefix}_API_KEY", "").strip()
        api_base = os.getenv(f"{prefix}_API_BASE", "https://api.openai.com/v1").strip()
        model = os.getenv(f"{prefix}_MODEL", "").strip()
        if not api_key or not model:
            return None
        return cls(api_key=api_key, api_base=api_base, model=model)

    async def chat_json(self, system_prompt: str, user_prompt: str) -> Optional[dict[str, Any]]:
        url = (
            f"{self.api_base}/chat/completions"
            if not self.api_base.endswith("/chat/completions")
            else self.api_base
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            return None

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
