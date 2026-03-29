import json
from typing import Any

from sqlmodel import select

from models import Memory
from services.core.embedding_service import embedding_service
from services.memory.trivium_store import trivium_store


class ReindexService:
    @staticmethod
    async def reindex_all_memories(session: Any, agent_id: str = "pero"):
        """
        全量重新索引所有记忆喵~ 🔄
        将 SQLite 中的文本重新生成向量并存入当前的向量索引。
        """
        print(f"[Reindex] 开始为 Agent {agent_id} 重新索引记忆...", flush=True)

        # 1. 从数据库获取所有属于该 Agent 的记忆
        statement = select(Memory).where(Memory.agent_id == agent_id)
        results = await session.exec(statement)
        memories = results.all()

        if not memories:
            print(f"[Reindex] 未发现 Agent {agent_id} 的任何记忆，跳过。", flush=True)
            return

        print(f"[Reindex] 发现 {len(memories)} 条记忆需要处理。", flush=True)

        # 2. 批量处理 (为了性能和 API 限制，分批进行)
        batch_size = 20
        for i in range(0, len(memories), batch_size):
            batch = memories[i : i + batch_size]

            # 准备编码文本
            texts_to_encode = []
            for mem in batch:
                # 使用带标签增强的文本逻辑，保持与 MemoryService 一致
                if mem.tags:
                    texts_to_encode.append(f"{mem.tags} {mem.tags} {mem.content}")
                else:
                    texts_to_encode.append(mem.content)

            try:
                # 批量生成 Embedding
                embeddings = await embedding_service.encode(texts_to_encode)

                # 写入向量库
                for j, mem in enumerate(batch):
                    if j < len(embeddings):
                        metadata_dict = {
                            "type": mem.type,
                            "timestamp": mem.timestamp,
                            "importance": float(mem.importance or 0),
                            "tags": mem.tags,
                            "clusters": mem.clusters,
                            "agent_id": agent_id,
                        }

                        # 处理簇元数据
                        if mem.clusters:
                            cluster_list = [
                                c.strip() for c in mem.clusters.split(",") if c.strip()
                            ]
                            for c in cluster_list:
                                clean_c = c.replace("[", "").replace("]", "")
                                if clean_c:
                                    metadata_dict[f"cluster_{clean_c}"] = True

                        await trivium_store.add_memory(
                            memory_id=mem.id,
                            content=mem.content,
                            embedding=embeddings[j],
                            metadata=metadata_dict,
                        )

                # 更新 SQLite 中的向量（可选，但推荐同步）
                for j, mem in enumerate(batch):
                    if j < len(embeddings):
                        mem.embedding_json = json.dumps(embeddings[j])
                        session.add(mem)

                await session.commit()
                print(
                    f"[Reindex] 已完成 {min(i + batch_size, len(memories))}/{len(memories)}",
                    flush=True,
                )

            except Exception as e:
                print(f"[Reindex] 批次处理失败: {e}", flush=True)
                # 继续处理下一批
                continue

        # 3. 保存向量库
        await trivium_store.flush()
        print(f"[Reindex] Agent {agent_id} 的重新索引任务圆满完成！喵~ ✨", flush=True)
