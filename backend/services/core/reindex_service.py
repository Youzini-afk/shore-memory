import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import engine, init_db
from models import Memory
from services.core.embedding_service import embedding_service
from services.memory.trivium_store import trivium_store


class ReindexService:
    @staticmethod
    async def _ensure_sqlite_ready():
        await init_db()

    @staticmethod
    def _build_embedding_text(memory: Memory) -> str:
        if memory.tags:
            return f"{memory.tags} {memory.tags} {memory.content}"
        return memory.content

    @staticmethod
    def _build_payload(memory: Memory, agent_id: str) -> Dict[str, Any]:
        return {
            "id": memory.id,
            "content": memory.content,
            "type": memory.type,
            "timestamp": memory.timestamp,
            "importance": float(memory.importance or 0),
            "tags": memory.tags,
            "clusters": memory.clusters,
            "agent_id": agent_id,
        }

    @staticmethod
    def _load_embedding_from_sqlite(memory: Memory) -> Optional[List[float]]:
        if not memory.embedding_json:
            return None

        try:
            embedding = json.loads(memory.embedding_json)
        except (TypeError, json.JSONDecodeError):
            return None

        if not isinstance(embedding, list) or not embedding:
            return None

        try:
            return [float(x) for x in embedding]
        except (TypeError, ValueError):
            return None

    @staticmethod
    async def reindex_all_memories(agent_id: str = "pero"):
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            await ReindexService.reindex_memories_with_session(session, agent_id)

    @staticmethod
    async def reindex_memories_with_session(session: Any, agent_id: str = "pero"):
        print(f"[Reindex] 开始为 Agent {agent_id} 重新索引记忆...", flush=True)

        await ReindexService._ensure_sqlite_ready()

        statement = select(Memory).where(Memory.agent_id == agent_id)
        results = await session.exec(statement)
        memories = results.all()

        if not memories:
            print(f"[Reindex] 未发现 Agent {agent_id} 的任何记忆，跳过。", flush=True)
            return

        print(f"[Reindex] 发现 {len(memories)} 条记忆需要处理。", flush=True)

        batch_size = 20
        for i in range(0, len(memories), batch_size):
            batch = memories[i : i + batch_size]
            texts_to_encode = [
                ReindexService._build_embedding_text(mem) for mem in batch
            ]

            try:
                embeddings = await embedding_service.encode(texts_to_encode)

                for j, mem in enumerate(batch):
                    if j >= len(embeddings):
                        continue

                    await trivium_store.add_memory(
                        memory_id=mem.id,
                        content=mem.content,
                        embedding=embeddings[j],
                        metadata=ReindexService._build_payload(mem, agent_id),
                    )

                for j, mem in enumerate(batch):
                    if j >= len(embeddings):
                        continue

                    mem.embedding_json = json.dumps(embeddings[j])
                    session.add(mem)

                await session.commit()
                print(
                    f"[Reindex] 已完成 {min(i + batch_size, len(memories))}/{len(memories)}",
                    flush=True,
                )
            except Exception as e:
                print(f"[Reindex] 批次处理失败: {e}", flush=True)
                continue

        await trivium_store.flush()
        print(f"[Reindex] Agent {agent_id} 的重新索引任务圆满完成！喵~ ✨", flush=True)

    @staticmethod
    async def rebuild_trivium_store(agent_id: str = "pero"):
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            return await ReindexService.rebuild_trivium_store_with_session(
                session, agent_id
            )

    @staticmethod
    async def rebuild_trivium_store_with_session(session: Any, agent_id: str = "pero"):
        print(f"[Rebuild] 开始重建 Agent {agent_id} 的 TriviumDB 数据...", flush=True)

        await ReindexService._ensure_sqlite_ready()

        statement = (
            select(Memory)
            .where(Memory.agent_id == agent_id)
            .order_by(Memory.timestamp, Memory.id)
        )
        results = await session.exec(statement)
        memories = results.all()

        await trivium_store.reset_storage()

        if not memories:
            print(
                f"[Rebuild] 未发现 Agent {agent_id} 的任何记忆，已完成空库重建。",
                flush=True,
            )
            return {
                "status": "success",
                "agent_id": agent_id,
                "memory_count": 0,
                "inserted": 0,
                "reencoded": 0,
                "reused_embeddings": 0,
                "links": 0,
            }

        print(f"[Rebuild] 准备回放 {len(memories)} 条记忆。", flush=True)

        inserted = 0
        reencoded = 0
        reused_embeddings = 0
        linked_edges = 0
        previous_inserted_memory: Optional[Memory] = None
        batch_size = 20

        for i in range(0, len(memories), batch_size):
            batch = memories[i : i + batch_size]
            missing_indices: List[int] = []
            missing_texts: List[str] = []
            embeddings_by_index: Dict[int, List[float]] = {}

            for index, memory in enumerate(batch):
                cached_embedding = ReindexService._load_embedding_from_sqlite(memory)
                if cached_embedding:
                    embeddings_by_index[index] = cached_embedding
                    reused_embeddings += 1
                else:
                    missing_indices.append(index)
                    missing_texts.append(ReindexService._build_embedding_text(memory))

            if missing_texts:
                try:
                    encoded_embeddings = await embedding_service.encode(missing_texts)
                    for idx, embedding in zip(
                        missing_indices, encoded_embeddings, strict=False
                    ):
                        embeddings_by_index[idx] = embedding
                        reencoded += 1
                except Exception as e:
                    print(f"[Rebuild] 批量补算 embedding 失败: {e}", flush=True)

            for index, memory in enumerate(batch):
                embedding = embeddings_by_index.get(index)
                if not embedding:
                    print(
                        f"[Rebuild] 跳过记忆 {memory.id}，因为未能获得 embedding。",
                        flush=True,
                    )
                    continue

                await trivium_store.insert(
                    memory.id,
                    embedding,
                    ReindexService._build_payload(memory, agent_id),
                )
                inserted += 1

                memory.embedding_json = json.dumps(embedding)
                session.add(memory)

                if previous_inserted_memory is not None:
                    try:
                        await trivium_store.link(
                            memory.id,
                            previous_inserted_memory.id,
                            label="associative",
                            weight=0.2,
                        )
                        await trivium_store.link(
                            previous_inserted_memory.id,
                            memory.id,
                            label="associative",
                            weight=0.2,
                        )
                        linked_edges += 2
                    except Exception as e:
                        print(
                            f"[Rebuild] 重建时间链接失败 {previous_inserted_memory.id} <-> {memory.id}: {e}",
                            flush=True,
                        )

                previous_inserted_memory = memory

            await session.commit()
            print(
                f"[Rebuild] 已完成 {min(i + batch_size, len(memories))}/{len(memories)}",
                flush=True,
            )

        await trivium_store.flush()
        print(f"[Rebuild] Agent {agent_id} 的 TriviumDB 重建完成。", flush=True)

        return {
            "status": "success",
            "agent_id": agent_id,
            "memory_count": len(memories),
            "inserted": inserted,
            "reencoded": reencoded,
            "reused_embeddings": reused_embeddings,
            "links": linked_edges,
        }
