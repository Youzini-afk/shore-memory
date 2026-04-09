import asyncio
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Dict, List, Optional

try:
    import triviumdb
    _TRIVIUM_AVAILABLE = True
except (ImportError, OSError) as _trivium_err:
    triviumdb = None
    _TRIVIUM_AVAILABLE = False
    # 此处 log 极其关键，能直接告诉便携版用户是否缺少 VC++ 运行库 DLL
    print(f"[TriviumStore] ⚠️ triviumdb 原生扩展加载失败（可能缺少 VC++ 运行库 DLL）: {_trivium_err}")

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
        self._db: Optional[Any] = None  # 支持 triviumdb 为 None 时的降级状态
        self._initialized = True

    def _open_db(self, dim: int = 1536):
        return triviumdb.TriviumDB(self.db_path, dim=dim, dtype="f32", sync_mode="normal")

    def _enable_auto_compaction(self):
        if self._db:
            self._db.enable_auto_compaction(interval_secs=300)

    def _ensure_loaded(self, dim: int = 1536):
        """确保 TriviumDB 已被加载"""
        # 降级保护：triviumdb 模块未加载时直接返回，不报错
        if not _TRIVIUM_AVAILABLE:
            return
        if self._db is None:
            print(f"[TriviumStore] 初始化 TriviumDB，维度={dim}，路径={self.db_path}")
            # 捕获可能的损坏异常
            try:
                self._db = self._open_db(dim)
            except Exception as e:
                print(f"[TriviumStore] ⚠️ 加载失败，检测到文件可能损坏: {e}")
                print("[TriviumStore] 正在备份受损数据并自动恢复底层引擎...")
                import time

                try:
                    # 备份整个目录然后重建它
                    from pathlib import Path

                    parent_dir = Path(self.data_dir).parent
                    new_rel = Path(self.data_dir).name + f"_corrupt_{int(time.time())}"
                    backup_dir = parent_dir / new_rel
                    shutil.move(self.data_dir, str(backup_dir))
                    os.makedirs(self.data_dir, exist_ok=True)
                    self._db = self._open_db(dim)
                    print(
                        f"[TriviumStore] ✅ 已完成自动重置恢复。受损数据已备份至: {backup_dir}"
                    )
                except Exception as backup_error:
                    print(f"[TriviumStore] ❌ 底层恢复失败: {backup_error}")
                    raise e from backup_error

            self._enable_auto_compaction()

    async def _run(self, fn, *args, **kwargs):
        """在线程池中运行同步函数"""
        loop = asyncio.get_event_loop()
        pfunc = partial(fn, *args, **kwargs)
        return await loop.run_in_executor(_executor, pfunc)

    def _build_agent_filter(self, agent_id: str) -> Dict[str, Any]:
        """构建 agent 隔离过滤条件"""
        return {"agent_id": agent_id}

    def _should_use_hybrid_search(
        self,
        query_text: Optional[str],
        enable_text_hybrid: bool,
        enable_dpp: bool,
    ) -> bool:
        """判断当前请求是否适合直接走 search_hybrid"""
        return bool(query_text and enable_text_hybrid and not enable_dpp)

    def _should_use_basic_search(
        self,
        query_text: Optional[str],
        enable_text_hybrid: bool,
        enable_dpp: bool,
    ) -> bool:
        """判断当前请求是否适合直接走基础 search"""
        return bool(not query_text and not enable_text_hybrid and not enable_dpp)

    async def _search_basic(
        self,
        query_vector: List[float],
        top_k: int,
        expand_depth: int,
        payload_filter: Dict[str, Any],
    ):
        """基础向量召回：只走 search"""
        return await self._run(
            self._db.search,
            query_vector,
            top_k,
            expand_depth,
            0.05,
            payload_filter,
        )

    async def _search_hybrid(
        self,
        query_vector: List[float],
        query_text: str,
        top_k: int,
        expand_depth: int,
        text_boost: float,
        payload_filter: Dict[str, Any],
    ):
        """混合召回：优先走 search_hybrid"""
        # search_hybrid 用 hybrid_alpha 控制向量占比，这里复用现有 text_boost 语义做近似映射
        hybrid_alpha = max(0.1, min(0.95, 1.0 - text_boost / 3.0))
        return await self._run(
            self._db.search_hybrid,
            query_vector,
            query_text,
            top_k,
            expand_depth,
            0.05,
            hybrid_alpha,
            payload_filter,
        )

    async def _search_advanced(
        self,
        query_vector: List[float],
        top_k: int,
        expand_depth: int,
        query_text: Optional[str],
        enable_text_hybrid: bool,
        text_boost: float,
        enable_sparse: bool,
        enable_dpp: bool,
        dpp_weight: float,
        payload_filter: Dict[str, Any],
    ):
        """高级召回：显式走 0.5.0 的完整高级签名"""
        return await self._run(
            self._db.search_advanced,
            query_vector,
            top_k,
            expand_depth,
            0.05,
            0.0,
            True,
            enable_sparse,
            0.1,
            0.3,
            enable_dpp,
            dpp_weight,
            False,
            bool(query_text and enable_text_hybrid),
            text_boost,
            0.05,
            query_text,
            payload_filter,
            False,
        )

    async def insert(
        self, memory_id: int, vector: List[float], payload: Dict[str, Any]
    ):
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
                    await self._run(
                        self._db.index_keyword, memory_id, f"cluster_{clean_c}"
                    )

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
        统一检索入口：按场景优先走 TriviumDB 更稳定的高层 API，
        仅在需要 DPP / 稀疏残差等高级能力时回落到 search_advanced。
        """
        if self._db is None:
            self._ensure_loaded(len(query_vector))

        payload_filter = self._build_agent_filter(agent_id)
        use_hybrid_search = self._should_use_hybrid_search(
            query_text, enable_text_hybrid, enable_dpp
        )
        use_basic_search = self._should_use_basic_search(
            query_text, enable_text_hybrid, enable_dpp
        )

        if use_hybrid_search:
            hits = await self._search_hybrid(
                query_vector,
                query_text,
                top_k,
                expand_depth,
                text_boost,
                payload_filter,
            )
        elif use_basic_search:
            hits = await self._search_basic(
                query_vector,
                top_k,
                expand_depth,
                payload_filter,
            )
        else:
            hits = await self._search_advanced(
                query_vector,
                top_k,
                expand_depth,
                query_text,
                enable_text_hybrid,
                text_boost,
                enable_sparse,
                enable_dpp,
                dpp_weight,
                payload_filter,
            )

        return [{"id": h.id, "score": h.score, "payload": h.payload} for h in hits]

    async def link(
        self, src: int, dst: int, label: str = "associative", weight: float = 0.5
    ):
        """建立时间链接或概念链接"""
        if self._db is None:
            self._ensure_loaded()
        await self._run(self._db.link, src, dst, label, weight)

    async def get_neighbors(self, node_id: int) -> List[Any]:
        """获取目标节点的相连邻居"""
        if self._db is None:
            self._ensure_loaded()
        try:
            # TriviumDB 0.5.0 的 Python 绑定明确返回邻居 ID 列表
            return await self._run(self._db.neighbors, node_id)
        except Exception as e:
            print(f"[TriviumStore] 获取邻居失败: {e}")
            return []

    async def has_link(self, src: int, dst: int) -> bool:
        """检查从 src 到 dst 的链接是否存在"""
        neighbors = await self.get_neighbors(src)
        if not neighbors:
            return False

        return dst in neighbors

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

    async def reset_storage(self, dim: int = 1536):
        """重置底层存储，用于从 SQLite 全量回放重建 TriviumDB。"""
        if not _TRIVIUM_AVAILABLE:
            return

        if self._db is not None:
            try:
                await self._run(self._db.flush)
            except Exception as e:
                print(f"[TriviumStore] 重置前 flush 失败，继续重建: {e}")

        self._db = None

        if os.path.isdir(self.data_dir):
            shutil.rmtree(self.data_dir, ignore_errors=True)
        os.makedirs(self.data_dir, exist_ok=True)

        self._db = self._open_db(dim)
        self._enable_auto_compaction()

    def count(self) -> int:
        if not _TRIVIUM_AVAILABLE:
            return 0
        if self._db is None:
            self._ensure_loaded()
        return self._db.node_count() if self._db else 0

    # --- 兼容模式接口 ---
    async def add_memory(
        self,
        memory_id: int,
        content: str,
        embedding: List[float],
        metadata: Dict[str, Any],
    ):
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
