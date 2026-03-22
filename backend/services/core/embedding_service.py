from typing import Any, List, Optional

import numpy as np

from core.model_manager import model_manager
from services.core.embedding_provider import (
    ApiEmbeddingProvider,
    EmbeddingProvider,
    LocalEmbeddingProvider,
)


class EmbeddingService:
    _instance = None
    _provider: Optional[EmbeddingProvider] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # 默认初始化为本地 Provider 喵~ 🏠
        self._provider = LocalEmbeddingProvider(model_manager)

    async def refresh_config(self, session: Any = None):
        """
        根据数据库配置更新 Provider 喵~ 🔄
        """
        from sqlmodel import select

        from database import get_session
        from models import Config

        async def _do_refresh(sess):
            # 1. 获取所有配置
            statement = select(Config)
            configs = {c.key: c.value for c in (await sess.exec(statement)).all()}

            provider_type = configs.get("embedding_provider", "local")

            if provider_type == "api":
                model_id = configs.get("embedding_model_id")
                reranker_id = configs.get("reranker_model_id")

                # Embedding 专属配置喵~ 🌸
                emb_api_key = configs.get("embedding_api_key") or configs.get(
                    "global_llm_api_key", ""
                )
                emb_api_base = configs.get("embedding_api_base") or configs.get(
                    "global_llm_api_base", "https://api.openai.com"
                )

                # Reranker 专属配置喵~ 🎯
                rerank_api_key = configs.get("reranker_api_key") or configs.get(
                    "global_llm_api_key", ""
                )
                rerank_api_base = configs.get("reranker_api_base") or configs.get(
                    "global_llm_api_base", "https://api.openai.com"
                )

                if model_id:
                    dim = int(configs.get("embedding_dimension", "1536"))

                    self._provider = ApiEmbeddingProvider(
                        api_key=emb_api_key,
                        api_base=emb_api_base,
                        model_id=model_id,
                        dimension=dim,
                        reranker_model_id=reranker_id,
                        reranker_api_key=rerank_api_key,
                        reranker_api_base=rerank_api_base,
                    )
                    print(
                        f"[Embedding] 已切换到 API Provider: {model_id} ({dim}维)",
                        flush=True,
                    )
                    return

            # 回退到本地
            self._provider = LocalEmbeddingProvider(model_manager)
            print("[Embedding] 已切换到 Local Provider", flush=True)

        if session:
            await _do_refresh(session)
        else:
            async for sess in get_session():
                await _do_refresh(sess)

    def warm_up(self):
        """
        预热模型 (仅对本地 Provider 有意义喵~)
        """
        if isinstance(self._provider, LocalEmbeddingProvider):
            print("[Embedding] 正在预热本地模型...", flush=True)
            self._provider._load_model()
            self._provider._load_reranker()
            print("[Embedding] 预热流程结束。", flush=True)

    async def encode(self, texts: List[str]) -> List[List[float]]:
        """
        生成文本向量
        """
        if not self._provider:
            return []
        return await self._provider.encode(texts)

    async def encode_one(self, text: str) -> List[float]:
        """生成单条文本向量"""
        result = await self.encode([text])
        return result[0] if result else []

    def get_dimension(self) -> int:
        """获取当前模型的维度喵~ 📏"""
        if not self._provider:
            return 384
        return self._provider.get_dimension()

    def get_model_key(self) -> str:
        """
        获取当前模型的唯一标识，用于区分不同的向量索引喵~ 🔑
        """
        if isinstance(self._provider, LocalEmbeddingProvider):
            return "local_384"
        elif isinstance(self._provider, ApiEmbeddingProvider):
            # 使用模型 ID 和维度作为标识
            import hashlib

            raw_key = f"{self._provider.model_id}_{self._provider.dimension}"
            return hashlib.md5(raw_key.encode()).hexdigest()[:12]
        return "default"

    def compute_similarity(
        self, query_embedding: List[float], doc_embeddings: List[List[float]]
    ) -> List[float]:
        """
        计算余弦相似度 (通用数学运算)
        """
        if not doc_embeddings:
            return []

        q = np.array(query_embedding)
        docs = np.array(doc_embeddings)

        norm_q = np.linalg.norm(q)
        norm_docs = np.linalg.norm(docs, axis=1)

        if norm_q == 0:
            return [0.0] * len(doc_embeddings)

        norm_docs[norm_docs == 0] = 1e-9
        dot_products = np.dot(docs, q)
        similarities = dot_products / (norm_docs * norm_q)
        return similarities.tolist()

    async def rerank(
        self, query: str, docs: List[str], top_k: int = None
    ) -> List[dict]:
        """
        使用重排序模型喵~ 🎯
        """
        if not self._provider:
            return []
        return await self._provider.rerank(query, docs, top_k)


# 全局单例
embedding_service = EmbeddingService()
