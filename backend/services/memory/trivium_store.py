import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Dict, List, Optional

import triviumdb

# 创建全局线程池用于 TriviumDB 的同步调用，避免阻塞 FastAPI 事件循环
# TriviumDB 内部并发安全，但 Python 侧包装尽量限制线程数以防暴涨
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="trivium")


class TriviumMemoryStore:
    """
    TriviumDB 数据访问的异步封装层。
    统一管理内存节点、向量、图谱关系及元数据流。
    """
    _instances = {}

    def __new__(cls, store_name: str = "memory"):
        if store_name not in cls._instances:
            instance = super(TriviumMemoryStore, cls).__new__(cls)
            instance._initialized = False
            cls._instances[store_name] = instance
        return cls._instances[store_name]

    def __init__(self, store_name: str = "memory"):
        if self._initialized:
            return

        self.store_name = store_name
        env_data_dir = os.environ.get("PERO_DATA_DIR")
        if env_data_dir:
            self.data_dir = os.path.join(env_data_dir, store_name)
        else:
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            self.data_dir = os.path.join(base_dir, "data", store_name)

        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, f"{store_name}.tdb")

        # 尚未真正实例化 DB对象，采用延迟加载策略
        self._db: Optional[triviumdb.TriviumDB] = None
        self._initialized = True

    def _ensure_loaded(self, dim: int = 1536):
        """确保 TriviumDB 已被加载"""
        if self._db is None:
            print(f"[TriviumStore] 初始化 TriviumDB，维度={dim}，路径={self.db_path}")
            # 捕获可能的损坏异常
            try:
                self._db = triviumdb.TriviumDB(
                    self.db_path, dim=dim, dtype="f32", sync_mode="normal"
                )
            except Exception as e:
                print(f"[TriviumStore] ⚠️ 加载失败，检测到文件可能损坏: {e}")
                print(f"[TriviumStore] 正在备份受损数据并自动恢复底层引擎...")
                import shutil
                import time
                backup_path = f"{self.data_dir}_corrupt_{int(time.time())}"
                try:
                    # 备份整个目录然后重建它
                    from pathlib import Path
                    parent_dir = Path(self.data_dir).parent
                    new_rel = Path(self.data_dir).name + f"_corrupt_{int(time.time())}"
                    backup_dir = parent_dir / new_rel
                    shutil.move(self.data_dir, str(backup_dir))
                    os.makedirs(self.data_dir, exist_ok=True)
                    self._db = triviumdb.TriviumDB(
                        self.db_path, dim=dim, dtype="f32", sync_mode="normal"
                    )
                    print(f"[TriviumStore] ✅ 已完成自动重置恢复。受损数据已备份至: {backup_dir}")
                except Exception as backup_error:
                    print(f"[TriviumStore] ❌ 底层恢复失败: {backup_error}")
                    raise e
            
            if self._db:
                self._db.enable_auto_compaction(interval_secs=300)

    async def _run(self, fn, *args, **kwargs):
        """在线程池中运行同步函数"""
        loop = asyncio.get_event_loop()
        pfunc = partial(fn, *args, **kwargs)
        return await loop.run_in_executor(_executor, pfunc)

    async def insert(self, memory_id: int, vector: List[float], payload: Dict[str, Any]):
        """异步插入/更新向量与属性"""
        if self._db is None:
            self._ensure_loaded(len(vector))
        # TriviumDB 的 insert_with_id 支持精确指定 ID（兼容 SQLite 的 ID）
        await self._run(self._db.insert_with_id, memory_id, vector, payload)
        
        # 为了兼容纯文本检索，如果有 content 则索引它
        content = payload.get("content")
        if content:
            await self._run(self._db.index_text, memory_id, content)
            
        # 如果有 clusters 标签等也可以放入 keyword 索引
        clusters = payload.get("clusters")
        if clusters:
            for c in clusters.split(","):
                clean_c = c.replace("[", "").replace("]", "").strip()
                if clean_c:
                    await self._run(self._db.index_keyword, memory_id, f"cluster_{clean_c}")

    async def search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        expand_depth: int = 2,
        agent_id: str = "pero",
        query_text: Optional[str] = None,
        enable_dpp: bool = True,
        dpp_weight: float = 1.0,
        enable_text_hybrid: bool = False,
        text_boost: float = 1.5,
        enable_sparse: bool = True,
    ) -> List[Dict]:
        """
        全量图谱向量混合检索，自带 DPP 多样性和 FISTA 稀疏优化（PEDSA直接内置）
        """
        if self._db is None:
            self._ensure_loaded(len(query_vector))

        # 构建隔离的 agent_id Payload 过滤条件
        # TriviumDB 的 search_advanced 刚被我们添加了 payload_filter 支持
        payload_filter = {"agent_id": {"$eq": agent_id}}

        # 调用我们刚在 Rust 里扩展的 API
        # search_advanced(query_vector, top_k, expand_depth, min_score, teleport_alpha, enable_advanced_pipeline, enable_sparse_residual, fista_lambda, fista_threshold, enable_dpp, dpp_quality_weight, enable_text_hybrid_search, text_boost, custom_query_text, payload_filter)
        hits = await self._run(
            self._db.search_advanced,
            query_vector,
            top_k,
            expand_depth,
            0.05,  # min_score
            0.0,   # teleport_alpha (不需要随机游走回家)
            True,  # enable_advanced_pipeline (走L3~L6深度流形)
            enable_sparse, # 语义残差稀疏化开关
            0.1,   # fista_lambda
            0.3,   # fista_threshold
            enable_dpp, 
            dpp_weight, 
            enable_text_hybrid,
            text_boost,
            query_text,
            payload_filter,
        )
        
        # 组装返回结果
        results = []
        for h in hits:
            # h 是 PySearchHit: {id, score, payload}
            results.append({
                "id": h.id,
                "score": h.score,
                "payload": h.payload
            })
            
        return results

    async def link(self, src: int, dst: int, label: str = "associative", weight: float = 0.5):
        """建立时间链接或概念链接"""
        if self._db is None:
            self._ensure_loaded()
        await self._run(self._db.link, src, dst, label, weight)

    async def get_neighbors(self, node_id: int) -> List[Any]:
        """获取目标节点的相连邻居"""
        if self._db is None:
            self._ensure_loaded()
        try:
            # 根据测试 TriviumDB.neighbors 接收 node_id，返回邻居列表（可能包含ID、权重等）
            results = await self._run(self._db.neighbors, node_id)
            return results
        except Exception as e:
            print(f"[TriviumStore] 获取邻居失败: {e}")
            return []

    async def has_link(self, src: int, dst: int) -> bool:
        """检查从 src 到 dst 的链接是否存在"""
        neighbors = await self.get_neighbors(src)
        if not neighbors:
            return False
            
        # 视返回类型而定，如果是 PySearchHit 或者带 ID 的元组
        for nbr in neighbors:
            if hasattr(nbr, 'id') and nbr.id == dst:
                return True
            if isinstance(nbr, tuple) and nbr[0] == dst:
                return True
            if isinstance(nbr, dict) and nbr.get('id') == dst:
                return True
            if isinstance(nbr, int) and nbr == dst:
                return True
                
        return False

    async def delete(self, memory_id: int):
        """逻辑删除节点（随 compaction 物理清理）"""
        if self._db is None:
            self._ensure_loaded()
        await self._run(self._db.delete, memory_id)

    async def flush(self):
        """强制刷盘"""
        if self._db is None:
            return
        await self._run(self._db.flush)

    def count(self) -> int:
        if self._db is None:
            self._ensure_loaded()
        return self._db.node_count()

    # --- 兼容模式接口 ---
    async def add_memory(self, memory_id: int, content: str, embedding: List[float], metadata: Dict[str, Any]):
        """兼容旧的 VectorStoreService 接口"""
        payload = {"id": memory_id, "content": content}
        payload.update(metadata)
        await self.insert(memory_id, embedding, payload)

    async def delete_memory(self, memory_id: int, agent_id: str = "pero"):
        """兼容旧的 VectorStoreService 接口"""
        await self.delete(memory_id)

    def add_tag(self, tag_name: str, embedding: List[float]):
        """空实现兼容打标签"""
        pass

# 全局单例
trivium_store = TriviumMemoryStore()

