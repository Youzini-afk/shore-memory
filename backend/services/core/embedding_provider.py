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
        self.dimension = 384

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

            repo_id = "models--" + model_name.replace("/", "--")

            for cache_dir in search_dirs:
                if not os.path.exists(cache_dir):
                    continue

                candidate_base_paths = [
                    os.path.join(cache_dir, repo_id),
                    os.path.join(cache_dir, "hub", repo_id),
                ]

                for base_path in candidate_base_paths:
                    if not os.path.exists(base_path):
                        continue

                    snapshots_dir = os.path.join(base_path, "snapshots")
                    if os.path.exists(snapshots_dir):
                        snapshots = os.listdir(snapshots_dir)
                        if snapshots:
                            snapshot_path = os.path.join(snapshots_dir, snapshots[0])
                            config_path = os.path.join(snapshot_path, "config.json")
                            if os.path.isdir(snapshot_path) and os.path.exists(
                                config_path
                            ):
                                return snapshot_path
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
                        # 3. 如果都不存在，尝试下载
                        print(
                            f"[Embedding] 模型 {repo_id} 未找到，尝试下载...",
                            flush=True,
                        )
                        local_path = self.model_manager.download_model(model_key)
                        self._model = SentenceTransformer(local_path, device="cpu")
            except Exception as e:
                print(f"[Embedding] 加载本地模型失败: {e}", flush=True)
                self._model = SentenceTransformer(repo_id, device="cpu")

        # 探测维度
        if self._model:
            self.dimension = self._model.get_sentence_embedding_dimension()

    def _load_reranker(self):
        if self._cross_encoder is None:
            print("[Embedding] 正在加载本地重排序模型...", flush=True)
            from sentence_transformers import CrossEncoder

            model_key = "reranker"
            repo_id = self.model_manager.models[model_key].repo_id

            try:
                if self.model_manager.check_model_exists(model_key):
                    local_path = self.model_manager.get_actual_model_path(model_key)
                    self._cross_encoder = CrossEncoder(local_path)
                else:
                    local_path = self._resolve_local_path(repo_id)
                    if local_path:
                        self._cross_encoder = CrossEncoder(local_path)
                    else:
                        print(
                            f"[Embedding] 重排序模型 {repo_id} 未找到，尝试下载...",
                            flush=True,
                        )
                        local_path = self.model_manager.download_model(model_key)
                        self._cross_encoder = CrossEncoder(local_path)
            except Exception as e:
                print(f"[Embedding] 加载本地重排序模型失败: {e}", flush=True)
                self._cross_encoder = CrossEncoder(repo_id, trust_remote_code=True)

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
        self._load_reranker()
        if not docs or self._cross_encoder is None:
            return []

        max_rerank_docs = 15
        if len(docs) > max_rerank_docs:
            docs = docs[:max_rerank_docs]

        pairs = [[query, doc] for doc in docs]
        scores = self._cross_encoder.predict(pairs)

        results = []
        for i, score in enumerate(scores):
            results.append({"index": i, "score": float(score), "doc": docs[i]})

        results.sort(key=lambda x: x["score"], reverse=True)
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
            # 降级：如果未配置在线重排，返回原始分数
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
            # 注意：SiliconFlow 或其他厂商的 rerank 接口可能不完全遵循标准，
            # 常见路径是 /rerank 或 /v1/rerank
            url = f"{self.reranker_api_base.rstrip('/')}/rerank"
            try:
                response = await client.post(
                    url, json=payload, headers=headers, timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

                # SiliconFlow 格式: data['results'] -> [{"index": 0, "relevance_score": 0.9, "document": {...}}]
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
