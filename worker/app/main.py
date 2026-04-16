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


class EmbedBatchRequest(BaseModel):
    texts: list[str]


class EmbedBatchResponse(BaseModel):
    embeddings: list[list[float]]


class ExtractEntitiesRequest(BaseModel):
    query: str
    observation_date: Optional[str] = None


class TurnMessage(BaseModel):
    role: str
    content: str


class ExistingMemoryHint(BaseModel):
    """Opaque reference to an existing memory passed to the scorer.

    `index` is an integer rendered as string ("0", "1", ...) scoped to this
    single scoring call. The server maps the indices the LLM returns back
    onto real memory ids before persisting.
    """

    index: str
    content: str


class EntityDraft(BaseModel):
    """Named entity mentioned by a memory (Stage 2 will persist these)."""

    name: str
    entity_type: str = Field(default="OTHER", alias="type")

    class Config:
        populate_by_name = True


class ExtractEntitiesResponse(BaseModel):
    entities: list[EntityDraft] = Field(default_factory=list)


class ScoreTurnRequest(BaseModel):
    agent_id: str
    user_uid: Optional[str] = None
    channel_uid: Optional[str] = None
    session_uid: Optional[str] = None
    scope: str
    source: str
    messages: list[TurnMessage]
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Stage 1 additive context fields.
    last_k_events: list[TurnMessage] = Field(default_factory=list)
    recently_extracted: list[str] = Field(default_factory=list)
    existing_memories: list[ExistingMemoryHint] = Field(default_factory=list)
    observation_date: Optional[str] = None


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
    # Stage 1 additions: attribution + linking + entity pass-through.
    attributed_to: Optional[str] = None
    linked_existing_indices: list[str] = Field(default_factory=list)
    entities: list[EntityDraft] = Field(default_factory=list)
    valid_at: Optional[str] = None


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


class DuplicateGroup(BaseModel):
    """Stage 3 duplicate cluster — `keep_id` wins, `drop_ids` get superseded."""

    keep_id: int
    drop_ids: list[int] = Field(default_factory=list)
    reason: Optional[str] = None


class ContradictionEntry(BaseModel):
    """Stage 3 contradiction — invalidate `old_id`. Optionally points to a
    replacement: either an existing memory (`new_id`) or a freshly-authored
    summary at `new_summary_idx` in this same response's `summary_memories`."""

    old_id: int
    new_id: Optional[int] = None
    new_summary_idx: Optional[int] = None
    invalid_at: Optional[str] = None
    reason: Optional[str] = None


class ReflectResponse(BaseModel):
    summary_memories: list[MemoryDraft] = Field(default_factory=list)
    retire_memory_ids: list[int] = Field(default_factory=list)
    state_patch: Optional[AgentStatePatch] = None
    report: dict[str, Any] = Field(default_factory=dict)
    # Stage 3 additions.
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)
    contradictions: list[ContradictionEntry] = Field(default_factory=list)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    embeddings = await _call_embedding_api([text])
    return EmbedResponse(embedding=embeddings[0])


@app.post("/v1/embed/batch", response_model=EmbedBatchResponse)
async def embed_batch(req: EmbedBatchRequest) -> EmbedBatchResponse:
    """Batched embedding for Stage 2 entity pass.

    Input: `{ "texts": ["..."] }`. Empty strings are filtered out before the
    upstream call; the response preserves the input order by splicing zero-
    length vectors back in at the filtered positions.
    """
    if not req.texts:
        return EmbedBatchResponse(embeddings=[])

    # Indices of non-empty strings so we can splice the result back.
    keep_indices: list[int] = []
    kept_texts: list[str] = []
    for idx, text in enumerate(req.texts):
        if text.strip():
            keep_indices.append(idx)
            kept_texts.append(text.strip())

    if not kept_texts:
        return EmbedBatchResponse(embeddings=[[] for _ in req.texts])

    embeddings = await _call_embedding_api(kept_texts)
    if len(embeddings) != len(kept_texts):
        raise HTTPException(
            status_code=502,
            detail=f"embedding upstream returned {len(embeddings)} vectors for {len(kept_texts)} inputs",
        )

    out: list[list[float]] = [[] for _ in req.texts]
    for idx, emb in zip(keep_indices, embeddings, strict=True):
        out[idx] = emb
    return EmbedBatchResponse(embeddings=out)


@app.post("/v1/tasks/extract-entities", response_model=ExtractEntitiesResponse)
async def extract_entities(req: ExtractEntitiesRequest) -> ExtractEntitiesResponse:
    """Extract named entities from a recall-time query string.

    Degrades to an empty list if the LLM is not configured or the response is
    malformed — recall should still work with just `semantic + bm25`.
    """
    query = req.query.strip()
    if not query:
        return ExtractEntitiesResponse()

    client = OpenAICompatClient.from_env(prefix="PMW_LLM")
    if client is None:
        return ExtractEntitiesResponse()

    data = await client.chat_json(_EXTRACT_ENTITIES_SYSTEM_PROMPT, query)
    if not isinstance(data, dict):
        return ExtractEntitiesResponse()

    raw_entities = data.get("entities") or []
    if not isinstance(raw_entities, list):
        return ExtractEntitiesResponse()

    entities: list[EntityDraft] = []
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        etype_raw = item.get("entity_type") or item.get("type") or "OTHER"
        entities.append(EntityDraft(name=name, entity_type=str(etype_raw).strip() or "OTHER"))

    return ExtractEntitiesResponse(entities=entities)


_EXTRACT_ENTITIES_SYSTEM_PROMPT = """你是 shore-memory 的命名实体抽取器。
从用户的检索 query 中抽取值得用于记忆检索的命名实体（人名、地点、作品、品牌、产品、组织、事件、专有名词等）。

规则：
1. 只抽实实在在的命名实体，不抽泛指词（例如「我」「今天」「食物」）。
2. 保留原始大小写和拼写，不翻译。
3. 最多输出 6 个实体，按重要性排序。
4. entity_type 取值: PERSON / PLACE / ORG / PRODUCT / WORK / BRAND / EVENT / OTHER。
5. 如果 query 里没有可抽的实体，返回 {"entities": []}。

输出严格 JSON（不要 markdown 包裹）：
{"entities": [{"name": "...", "entity_type": "..."}]}
"""


async def _call_embedding_api(texts: list[str]) -> list[list[float]]:
    """Call the upstream OpenAI-compatible embeddings endpoint once for a batch.

    Returns one embedding per input text, in the same order. Raises
    `HTTPException` (502/503) on upstream failure.
    """
    if not texts:
        return []

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
    payload = {"model": model, "input": texts}

    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"embedding upstream error: {exc.response.text}",
            ) from exc
        data = response.json()

    items = data.get("data") or []
    if len(items) != len(texts):
        raise HTTPException(
            status_code=502,
            detail=f"embedding upstream returned {len(items)} items for {len(texts)} inputs",
        )

    embeddings: list[list[float]] = []
    for item in items:
        vec = item.get("embedding")
        if not isinstance(vec, list) or not vec:
            raise HTTPException(status_code=502, detail="embedding upstream returned empty vector")
        embeddings.append([float(x) for x in vec])
    return embeddings


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


_SCORE_TURN_SYSTEM_PROMPT = """你是 shore-memory 的记忆抽取器。任务是从一段多轮对话里抽取值得长期保留的事实、偏好、计划、关系、事件等。

# 输入（user 消息是一个 JSON 对象）
- identity: 身份上下文（agent_id / scope / source / user_uid / channel_uid / session_uid），用于回填你抽取出的每条记忆。
- observation_date: 当前对话发生的时间（ISO-8601），是唯一的时间锚点。
- new_messages: 当前 turn 的消息数组，格式 [{"role": "user"/"assistant", "content": "..."}]。只从这里抽取。
- last_k_events: 同一 session 里更早的消息（时间升序，最早在前），用来解析指代和背景。不要从这里抽记忆。
- recently_extracted: 同一 session 近期已抽取过的记忆内容列表。如果新消息里的事实已经在这里，视为重复，不再抽。
- existing_memories: 与当前话题语义相关的既有记忆（假索引 "0", "1", ... 和文本）。用于两个目的：
  (1) 去重：若 new_messages 的事实已经在这里，不要再抽；
  (2) 链接：如果你要抽的新记忆和某条既有记忆相关（同一个人、同一个话题、偏好更新、事件延续等），把对应的假索引放进 `linked_existing_indices`。不要捏造假索引。
- metadata: 传入方附带的元信息，必要时可以合并进新记忆的 metadata。

# 核心规则
1. **忠于来源**：只写 new_messages 里出现过的信息。严禁臆造、推断未明说的身份、性别、年龄。
2. **去重优先**：如果事实已在 `recently_extracted` 或 `existing_memories`，不要重复抽；可以通过 `linked_existing_indices` 引用既有记忆。
3. **保留具体细节**：专有名词、数字、日期、品牌、角色名要原封不动保留。不要把「Ferrari 488 GTB」泛化成「跑车」，不要把「3 miles」写成「几英里」。
4. **时间锚点**：把「昨天」「上周」「明天」等相对时间，基于 `observation_date` 解析成具体日期。`valid_at` 缺省时就用 `observation_date` 的日期部分。
5. **No Echo**：如果 assistant 只是在复述 user 的内容，不要为同一事实抽两次；assistant 独立给出的推荐、计划、研究结论可以抽。
6. **自包含**：每条 memory 必须可以独立理解。把代词替换成具体名称或「用户」。
7. **富上下文**：保留情感（例如「既紧张又兴奋」）、动机（「因为想陪伴母亲」）、转变（「从咖啡改喝抹茶拿铁」），不要只留干巴巴的事实。
8. **多主题都抽**：一段对话涉及多个话题时，每个话题单独抽一条记忆。
9. **中文为主**：内部语言保持与对话一致；多数场景用中文书写。

# 输出（必须严格为 JSON，不要 markdown，不要解释文字）
{
  "memories": [
    {
      "content": "自包含的、15-80 字的完整陈述",
      "attributed_to": "user" | "assistant",
      "linked_existing_indices": ["0", "3"],
      "memory_type": "preference" | "event" | "plan" | "fact" | "relationship" | "emotion" | "summary",
      "importance": 1-10 的数字,
      "sentiment": "positive" | "neutral" | "negative" | null,
      "tags": ["..."],
      "entities": [{"name": "张三", "entity_type": "PERSON"}],
      "valid_at": "YYYY-MM-DD" | null,
      "metadata": { "...": "..." },
      "scope": "private" | "group" | "shared" | "system",
      "source": "...",
      "user_uid": "...",
      "channel_uid": "...",
      "session_uid": "..."
    }
  ],
  "state_patch": {
    "mood": "...",
    "vibe": "...",
    "mind": "..."
  }
}

# 关键提醒
- 如果 new_messages 全是寒暄或没有可抽取的事实，直接返回 {"memories": []}。
- entity_type 建议使用：PERSON、PLACE、ORG、PRODUCT、WORK、BRAND、EVENT、OTHER。
- scope/source/user_uid/channel_uid/session_uid 默认直接复用 identity 的值。
- 不要在响应里输出 JSON 以外的任何内容。
"""


async def maybe_llm_score_turn(req: ScoreTurnRequest) -> Optional[ScoreTurnResponse]:
    client = OpenAICompatClient.from_env(prefix="PMW_LLM")
    if client is None:
        return None

    system_prompt = _SCORE_TURN_SYSTEM_PROMPT
    user_payload = _build_score_turn_user_payload(req)
    user_prompt = json.dumps(user_payload, ensure_ascii=False)

    data = await client.chat_json(system_prompt, user_prompt)
    if not isinstance(data, dict):
        return None

    memories: list[MemoryDraft] = []
    for item in data.get("memories", []):
        if not isinstance(item, dict) or not str(item.get("content", "")).strip():
            continue
        memories.append(_coerce_memory_draft(item, req))

    state_patch = None
    raw_state_patch = data.get("state_patch")
    if isinstance(raw_state_patch, dict):
        state_patch = AgentStatePatch(
            mood=as_optional_str(raw_state_patch.get("mood")),
            vibe=as_optional_str(raw_state_patch.get("vibe")),
            mind=as_optional_str(raw_state_patch.get("mind")),
        )

    return ScoreTurnResponse(memories=memories, state_patch=state_patch)


def _coerce_memory_draft(item: dict[str, Any], req: ScoreTurnRequest) -> MemoryDraft:
    """Best-effort conversion of a raw LLM output dict into a `MemoryDraft`.

    The helper is deliberately forgiving — LLMs often omit or mistype optional
    fields. Required fields fall back to the scoring request's identity when
    missing so a successful extraction is never dropped due to a missing
    `scope` or `source` in the LLM JSON.
    """

    entities_raw = item.get("entities") or []
    entities: list[EntityDraft] = []
    if isinstance(entities_raw, list):
        for entity in entities_raw:
            if not isinstance(entity, dict):
                continue
            name = str(entity.get("name", "")).strip()
            if not name:
                continue
            etype_raw = entity.get("entity_type") or entity.get("type") or "OTHER"
            entities.append(
                EntityDraft(name=name, entity_type=str(etype_raw).strip() or "OTHER")
            )

    linked_raw = item.get("linked_existing_indices") or []
    linked_existing_indices: list[str] = []
    if isinstance(linked_raw, list):
        for idx in linked_raw:
            text = str(idx).strip()
            if text:
                linked_existing_indices.append(text)

    return MemoryDraft(
        content=str(item.get("content", "")).strip(),
        tags=[str(tag) for tag in (item.get("tags") or []) if str(tag).strip()],
        metadata=item.get("metadata") or {},
        importance=float(item.get("importance", 5.0)),
        sentiment=as_optional_str(item.get("sentiment")),
        memory_type=str(item.get("memory_type", "event")).strip() or "event",
        scope=str(item.get("scope", req.scope)).strip() or req.scope,
        source=str(item.get("source", req.source)).strip() or req.source,
        user_uid=str(item.get("user_uid", req.user_uid or "")).strip() or req.user_uid,
        channel_uid=str(item.get("channel_uid", req.channel_uid or "")).strip() or req.channel_uid,
        session_uid=str(item.get("session_uid", req.session_uid or "")).strip() or req.session_uid,
        attributed_to=as_optional_str(item.get("attributed_to")),
        linked_existing_indices=linked_existing_indices,
        entities=entities,
        valid_at=as_optional_str(item.get("valid_at")),
    )


def _build_score_turn_user_payload(req: ScoreTurnRequest) -> dict[str, Any]:
    return {
        "identity": {
            "agent_id": req.agent_id,
            "scope": req.scope,
            "source": req.source,
            "user_uid": req.user_uid,
            "channel_uid": req.channel_uid,
            "session_uid": req.session_uid,
        },
        "observation_date": req.observation_date,
        "new_messages": [msg.model_dump() for msg in req.messages],
        "last_k_events": [msg.model_dump() for msg in req.last_k_events],
        "recently_extracted": req.recently_extracted,
        "existing_memories": [hint.model_dump() for hint in req.existing_memories],
        "metadata": req.metadata or {},
    }


_REFLECTION_SYSTEM_PROMPT = """你是 shore-memory 的记忆整理器（reflection worker）。
你会收到一组近期低权重或可疑重复的记忆，需要判定它们之间的**重复**与**矛盾**，并在必要时合成新的整合记忆。

# 输入
JSON 对象，包含：
- agent_id: 当前 agent id
- memories: 一组既有记忆 `{id, content, importance, scope, created_at}`

# 三件事你要判断（基于 Graphiti `resolve_edge` 思路）
1. **duplicate_groups**：如果多条记忆表达的事实**完全相同**（只是措辞不同），按组归并。每组只保留一个 `keep_id`，其余放到 `drop_ids`。关键差别（数字、日期、专有名词）不同 → 不算重复。
2. **contradictions**：如果一条较新的记忆**更新/覆盖/推翻**了某条较旧记忆（例如偏好改变、地点变更、计划取消），把旧记忆的 `id` 放 `old_id`，把新的放 `new_id`（从输入的 memories 里选）。如果没有现成的替代者、但事实明显不再为真（例如 "我不再喜欢 X"），就把 old_id 放进来但 new_id 留空，表示纯粹失效。
3. **summary_memories**：只有当一组相关低权重记忆能压缩成一条信息更丰富、更值得长期保留的总结，才产出 summary。不要机械合并、不要损失关键细节。`contradictions` 里可以用 `new_summary_idx` 指向本数组里的某个 summary 作为替代方。

# 核心规则
- **忠于来源**：summary 里不可臆造输入以外的内容。
- **保留细节**：日期、专有名词、数字必须保留。别把 "3 miles" 写成 "a few miles"。
- **同一事实同一组**：一条 memory 不应出现在多个 duplicate_groups 或多次作为 old_id。
- **顺序**：duplicate_groups 和 contradictions 各自独立考虑；一个对象可以既是某组重复又是某矛盾的 old，但尽量不要同时。
- **默认保守**：如果没把握，宁可空数组。宁缺勿错。
- **valid_at**：contradiction 的 `invalid_at` 用 ISO 8601 日期，可省略（默认现在）。

# 输出（严格 JSON，不要 markdown，不要解释文字）
{
  "summary_memories": [
    {
      "content": "中文，15-80 字，自包含",
      "memory_type": "summary" | "fact" | "preference" | ...,
      "importance": 1-10,
      "sentiment": "positive" | "neutral" | "negative" | null,
      "tags": ["..."],
      "scope": "shared" | "private" | "group" | "system",
      "source": "reflection",
      "user_uid": null,
      "channel_uid": null,
      "session_uid": null,
      "metadata": {}
    }
  ],
  "duplicate_groups": [
    {"keep_id": 123, "drop_ids": [124, 125], "reason": "三条都在说用户喜欢拿铁"}
  ],
  "contradictions": [
    {"old_id": 101, "new_id": 130, "invalid_at": "2026-04-10", "reason": "偏好翻转"},
    {"old_id": 102, "new_summary_idx": 0, "invalid_at": null, "reason": "通过 summary 0 取代"},
    {"old_id": 103, "reason": "用户声明不再喜欢，但未给出替代"}
  ],
  "retire_memory_ids": [],
  "state_patch": {"mood": "...", "vibe": "...", "mind": "..."},
  "report": {"mode": "llm"}
}

# 关键提醒
- 如果没有重复和矛盾，summary 也不合适，返回 `{"summary_memories": [], "duplicate_groups": [], "contradictions": [], "retire_memory_ids": []}`。
- `retire_memory_ids` 与 Stage 1 兼容，可为空。
- 只在非常确信时才 supersede，错判会把真实偏好抹掉。
"""


async def maybe_llm_reflect(req: ReflectRequest) -> Optional[ReflectResponse]:
    client = OpenAICompatClient.from_env(prefix="PMW_LLM")
    if client is None:
        return None

    user_prompt = json.dumps(
        {
            "agent_id": req.agent_id,
            "memories": [memory.model_dump() for memory in req.memories],
        },
        ensure_ascii=False,
    )

    data = await client.chat_json(_REFLECTION_SYSTEM_PROMPT, user_prompt)
    if not isinstance(data, dict):
        return None

    summary_memories: list[MemoryDraft] = []
    for item in data.get("summary_memories", []) or []:
        if not isinstance(item, dict) or not str(item.get("content", "")).strip():
            continue
        summary_memories.append(
            MemoryDraft(
                content=str(item.get("content", "")).strip(),
                tags=[str(tag) for tag in (item.get("tags") or []) if str(tag).strip()],
                metadata=item.get("metadata") or {},
                importance=float(item.get("importance", 4.0)),
                sentiment=as_optional_str(item.get("sentiment")),
                memory_type=str(item.get("memory_type", "summary")).strip() or "summary",
                scope=str(item.get("scope", "shared")).strip() or "shared",
                source=str(item.get("source", "reflection")).strip() or "reflection",
                user_uid=as_optional_str(item.get("user_uid")),
                channel_uid=as_optional_str(item.get("channel_uid")),
                session_uid=as_optional_str(item.get("session_uid")),
                valid_at=as_optional_str(item.get("valid_at")),
            )
        )

    duplicate_groups = _parse_duplicate_groups(data.get("duplicate_groups"))
    contradictions = _parse_contradictions(data.get("contradictions"), len(summary_memories))

    retire_memory_ids: list[int] = []
    for value in data.get("retire_memory_ids", []) or []:
        try:
            retire_memory_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    state_patch = None
    if isinstance(data.get("state_patch"), dict):
        state_patch = AgentStatePatch(
            mood=as_optional_str(data["state_patch"].get("mood")),
            vibe=as_optional_str(data["state_patch"].get("vibe")),
            mind=as_optional_str(data["state_patch"].get("mind")),
        )

    report = data.get("report")
    if not isinstance(report, dict):
        report = {"mode": "llm"}

    return ReflectResponse(
        summary_memories=summary_memories,
        retire_memory_ids=retire_memory_ids,
        state_patch=state_patch,
        report=report,
        duplicate_groups=duplicate_groups,
        contradictions=contradictions,
    )


def _parse_duplicate_groups(raw: Any) -> list[DuplicateGroup]:
    """Parse `duplicate_groups` with forgiving type coercion.

    Dedups `drop_ids` internally and silently drops malformed entries so a
    sloppy LLM response can't poison the supersede loop downstream.
    """
    if not isinstance(raw, list):
        return []
    out: list[DuplicateGroup] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            keep_id = int(item.get("keep_id"))
        except (TypeError, ValueError):
            continue
        drop_ids: list[int] = []
        seen: set[int] = set()
        for did in item.get("drop_ids") or []:
            try:
                did_int = int(did)
            except (TypeError, ValueError):
                continue
            if did_int == keep_id or did_int in seen:
                continue
            seen.add(did_int)
            drop_ids.append(did_int)
        if not drop_ids:
            continue
        out.append(
            DuplicateGroup(
                keep_id=keep_id,
                drop_ids=drop_ids,
                reason=as_optional_str(item.get("reason")),
            )
        )
    return out


def _parse_contradictions(raw: Any, summary_count: int) -> list[ContradictionEntry]:
    """Parse `contradictions` with forgiving type coercion and sanity checks.

    `new_summary_idx` is validated against `summary_count`; out-of-range
    values are dropped so the server never tries to resolve a dangling index.
    """
    if not isinstance(raw, list):
        return []
    out: list[ContradictionEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            old_id = int(item.get("old_id"))
        except (TypeError, ValueError):
            continue
        new_id: Optional[int] = None
        new_summary_idx: Optional[int] = None
        if item.get("new_id") is not None:
            try:
                new_id = int(item["new_id"])
            except (TypeError, ValueError):
                new_id = None
        if item.get("new_summary_idx") is not None:
            try:
                candidate = int(item["new_summary_idx"])
                if 0 <= candidate < summary_count:
                    new_summary_idx = candidate
            except (TypeError, ValueError):
                new_summary_idx = None
        out.append(
            ContradictionEntry(
                old_id=old_id,
                new_id=new_id,
                new_summary_idx=new_summary_idx,
                invalid_at=as_optional_str(item.get("invalid_at")),
                reason=as_optional_str(item.get("reason")),
            )
        )
    return out


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
