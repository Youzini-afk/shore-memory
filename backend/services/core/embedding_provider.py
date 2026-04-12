import logging
import os
from abc import ABC, abstractmethod
from typing import List, Optional

import httpx

from core.model_manager import model_manager

# --- 环境初始化喵~ 🌸 ---
# 设置本地缓存目录
os.environ["SENTENCE_TRANSFORMERS_HOME"] = model_manager.models_cache_dir
# 设置 HuggingFace 镜像，解决国内连接问题
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# 同时设置 HF_HOME，确保 huggingface_hub也能找到缓存
os.environ["HF_HOME"] = os.environ["SENTENCE_TRANSFORMERS_HOME"]
# 全局禁用 tqdm 进度条
os.environ["TQDM_DISABLE"] = "1"
# 禁止 transformers 信息/警告日志
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
# 禁用 HF Hub 进度条
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
# -------------------------


class EmbeddingProvider(ABC):
    @abstractmethod
    async def encode(self, texts: List[str]) -> List[List[float]]:
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        pass

    @abstractmethod
    async def rerank(
        self, query: str, docs: List[str], top_k: int = None
    ) -> List[dict]:
        pass


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_manager):
        self._model = None
        self._cross_encoder = None
        self.model_manager = model_manager
        self.dimension = 512

    def _resolve_local_path(self, model_name: str) -> Optional[str]:
        """
        手动从缓存解析模型路径以绕过 huggingface_hub 问题喵~ 🕵️‍♀️
        """
        try:
            search_dirs = []
            custom_cache = os.environ.get("SENTENCE_TRANSFORMERS_HOME")
            if custom_cache:
                search_dirs.append(custom_cache)

            hf_home = os.environ.get("HF_HOME")
            if hf_home and hf_home not in search_dirs:
                search_dirs.append(hf_home)

            # 改为支持 ModelScope 的直接路径
            repo_id = model_name

            for cache_dir in search_dirs:
                if not os.path.exists(cache_dir):
                    continue

                base_path = os.path.join(cache_dir, repo_id)
                if not os.path.exists(base_path):
                    continue

                config_path = os.path.join(base_path, "config.json")
                if os.path.isdir(base_path) and os.path.exists(config_path):
                    return base_path
        except Exception as e:
            print(f"[Embedding] 手动路径解析失败: {e}", flush=True)
        return None

    def _load_model(self):
        if self._model is None:
            # 暂时禁用日志以保持输出清洁
            logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
            from sentence_transformers import SentenceTransformer

            model_key = "embedding"
            repo_id = self.model_manager.models[model_key].repo_id

            try:
                # 1. 尝试从 ModelManager 获取路径
                if self.model_manager.check_model_exists(model_key):
                    local_path = self.model_manager.get_actual_model_path(model_key)
                    self._model = SentenceTransformer(local_path, device="cpu")
                else:
                    # 2. 尝试手动解析路径
                    local_path = self._resolve_local_path(repo_id)
                    if local_path:
                        self._model = SentenceTransformer(local_path, device="cpu")
                    else:
                        # 3. 如果都不存在，直接报错，让前端接管下载
                        raise RuntimeError(
                            f"模型文件 {repo_id} 不存在。请通过启动器完成模型下载。"
                        )
            except Exception as e:
                print(f"[Embedding] 加载本地模型失败: {e}", flush=True)
                self._model = SentenceTransformer(repo_id, device="cpu")

        # 探测维度
        if self._model:
            self.dimension = self._model.get_sentence_embedding_dimension()

    # (已彻底移除本地 Reranker 逻辑)
    async def encode(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        if not texts or self._model is None:
            return []
        embeddings = self._model.encode(texts)
        return embeddings.tolist()

    def get_dimension(self) -> int:
        self._load_model()
        return self.dimension

    async def rerank(
        self, query: str, docs: List[str], top_k: int = None
    ) -> List[dict]:
        # 已弃用本地 Reranker，直接按照原顺序假装打分返回
        if not docs:
            return []

        results = []
        for i, doc in enumerate(docs):
            results.append({"index": i, "score": 1.0 - (i * 0.01), "doc": doc})

        return results[:top_k] if top_k else results


class ApiEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        api_base: str,
        model_id: str,
        dimension: int = 1536,
        reranker_model_id: Optional[str] = None,
        reranker_api_key: Optional[str] = None,
        reranker_api_base: Optional[str] = None,
    ):
        self.api_key = api_key
        self.api_base = api_base
        self.model_id = model_id
        self.dimension = dimension
        self.reranker_model_id = reranker_model_id
        self.reranker_api_key = reranker_api_key or api_key
        self.reranker_api_base = reranker_api_base or api_base

    async def encode(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": self.model_id, "input": texts}

        async with httpx.AsyncClient() as client:
            url = f"{self.api_base.rstrip('/')}/embeddings"
            response = await client.post(
                url, json=payload, headers=headers, timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            # OpenAI 格式返回数据中的 embeddings
            # data['data'] 是一个列表，每个元素包含 'embedding'
            return [item["embedding"] for item in data["data"]]

    def get_dimension(self) -> int:
        return self.dimension

    async def rerank(
        self, query: str, docs: List[str], top_k: int = None
    ) -> List[dict]:
        if not self.reranker_model_id or not docs:
            return [
                {"index": i, "score": 1.0, "doc": doc}
                for i, doc in enumerate(docs[:top_k] if top_k else docs)
            ]

        headers = {"Authorization": f"Bearer {self.reranker_api_key}"}
        payload = {
            "model": self.reranker_model_id,
            "query": query,
            "documents": docs,
            "top_n": top_k or len(docs),
        }

        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.reranker_api_base.rstrip('/')}/rerank"
                response = await client.post(
                    url, json=payload, headers=headers, timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for item in data.get("results", []):
                    results.append(
                        {
                            "index": item["index"],
                            "score": item.get("relevance_score", 0.0),
                            "doc": docs[item["index"]],
                        }
                    )
                return results
            except Exception as e:
                print(f"[Embedding] 在线重排序失败: {e}", flush=True)
                return [
                    {"index": i, "score": 1.0, "doc": doc}
                    for i, doc in enumerate(docs[:top_k] if top_k else docs)
                ]
