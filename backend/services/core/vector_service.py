from typing import Any, Dict, List

from services.core.vector_store_service import vector_store


class VectorService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VectorService, cls).__new__(cls)
        return cls._instance

    # --- 记忆操作 ---

    def add_memory(
        self,
        memory_id: int,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any] = None,
    ):
        """
        添加或更新记忆向量
        注意：元数据和内容不再存储在 VectorDB (Rust) 中。
        它们存储在由 MemoryService 管理的 SQLite 中。
        """
        if not embedding:
            return
        vector_store.add_memory(memory_id, embedding, metadata)

    def delete_memory(self, memory_id: int, agent_id: str = "pero"):
        """逻辑删除记忆向量（Tombstone 机制）。

        底层 HNSW 索引不支持原地物理删除，此方法将 memory_id 写入
        已删除集合，搜索时实时过滤，并在下一次 save() 时从持久化
        文件中物理清除，同时重建内存索引以回收空间。
        """
        vector_store.delete_memory(memory_id, agent_id)
        # 触发一次 save()，将 tombstone 标记刷到持久化文件并重建索引
        try:
            vector_store.save()
        except Exception as e:
            print(f"[VectorService] delete_memory 触发 save 失败 (非致命): {e}")

    def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filter_criteria: Dict = None,
        agent_id: str = "pero",
    ) -> List[Dict]:
        """
        向量检索
        返回: [{"id": int, "score": float}]
        注意：不再返回 "document" 和 "metadata"，调用者需要回查数据库。
        """
        if filter_criteria:
            print(
                "[VectorService] 警告: 'filter_criteria' 在 Rust 向量搜索中不受支持。已忽略。"
            )

        return vector_store.search_memory(query_embedding, limit, agent_id)

    def query_memories(
        self, limit: int = 10, filter_criteria: Dict = None
    ) -> List[Dict]:
        """
        已弃用：请改用 MemoryService.get_memories_by_filter。
        """
        print("[VectorService] 错误: query_memories 已弃用。请使用 MemoryService。")
        return []

    def count(self) -> int:
        return vector_store.count_memories()

    def get_all_ids(self) -> List[int]:
        # HNSW 不容易支持（如果不进行遍历）
        return []

    # --- 标签操作 ---

    def add_tag(self, tag_name: str, embedding: List[float]):
        vector_store.add_tag(tag_name, embedding)

    def search_tags(self, query_embedding: List[float], limit: int = 5) -> List[Dict]:
        return vector_store.search_tags(query_embedding, limit)


vector_service = VectorService()
