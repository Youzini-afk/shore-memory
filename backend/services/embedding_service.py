import contextlib
import os
from typing import List, Optional

import numpy as np

# 为了避免在导入时就下载模型，我们使用延迟加载
# 并且设置本地缓存目录
data_dir = os.environ.get(
    "PERO_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
os.environ["SENTENCE_TRANSFORMERS_HOME"] = os.path.join(data_dir, "models_cache")
# 设置 HuggingFace 镜像，解决国内连接问题
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# 同时设置 HF_HOME，确保 huggingface_hub也能找到缓存
os.environ["HF_HOME"] = os.environ["SENTENCE_TRANSFORMERS_HOME"]

# --- 禁止日志和进度条 ---
# 全局禁用 tqdm 进度条（例如用于模型加载）
os.environ["TQDM_DISABLE"] = "1"
# 禁止 transformers 信息/警告日志
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
# ----------------------------------------


class EmbeddingService:
    _instance = None
    _model = None
    _cross_encoder = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def _resolve_local_path(self, model_name: str) -> Optional[str]:
        """
        手动从缓存解析模型路径以绕过 huggingface_hub 问题
        """
        try:
            # 要搜索模型的目录列表
            search_dirs = []

            # 1. 自定义配置路径
            custom_cache = os.environ.get("SENTENCE_TRANSFORMERS_HOME")
            if custom_cache:
                search_dirs.append(custom_cache)

            # 2. 标准 HuggingFace Hub 缓存
            hf_home = os.environ.get("HF_HOME")
            if hf_home and hf_home not in search_dirs:
                search_dirs.append(hf_home)

            default_hf_cache = os.path.join(
                os.path.expanduser("~"), ".cache", "huggingface", "hub"
            )
            if default_hf_cache not in search_dirs:
                search_dirs.append(default_hf_cache)

            # 3. 旧版 SentenceTransformers 缓存
            default_st_cache = os.path.join(
                os.path.expanduser("~"), ".cache", "torch", "sentence_transformers"
            )
            if default_st_cache not in search_dirs:
                search_dirs.append(default_st_cache)

            # print(f"[Embedding] 调试: 正在目录中搜索模型 '{model_name}': {search_dirs}", flush=True)

            repo_id = "models--" + model_name.replace("/", "--")

            for cache_dir in search_dirs:
                if not os.path.exists(cache_dir):
                    continue

                # 检查路径（根目录和 hub 子目录）
                candidate_base_paths = [
                    os.path.join(cache_dir, repo_id),
                    os.path.join(cache_dir, "hub", repo_id),
                ]

                for base_path in candidate_base_paths:
                    # print(f"[Embedding] Debug: Checking base path: {base_path}", flush=True)
                    if not os.path.exists(base_path):
                        continue

                    # 策略 1: 检查 snapshots 目录并找到最新的 snapshot
                    snapshots_dir = os.path.join(base_path, "snapshots")
                    if os.path.exists(snapshots_dir):
                        snapshots = os.listdir(snapshots_dir)
                        # print(f"[Embedding] Debug: Found snapshots in {base_path}: {snapshots}", flush=True)
                        if snapshots:
                            # 简单地取第一个找到的 snapshot
                            snapshot_path = os.path.join(snapshots_dir, snapshots[0])
                            # 验证 snapshot 是否包含 config.json
                            config_path = os.path.join(snapshot_path, "config.json")
                            if os.path.isdir(snapshot_path) and os.path.exists(
                                config_path
                            ):
                                # print(f"[Embedding] 调试: 发现有效配置于 {config_path}", flush=True)
                                return snapshot_path
                            # else:
                            # print(f"[Embedding] Debug: Config not found at {config_path}", flush=True)

                    # 策略 2 (旧版): 检查 refs/main
                    ref_path = os.path.join(base_path, "refs", "main")
                    if os.path.exists(ref_path):
                        try:
                            with open(ref_path, "r") as f:
                                commit_hash = f.read().strip()
                            snapshot_path = os.path.join(
                                base_path, "snapshots", commit_hash
                            )
                            if os.path.exists(snapshot_path):
                                return snapshot_path
                        except Exception:
                            pass

        except Exception as e:
            print(f"[Embedding] 手动路径解析失败: {e}", flush=True)
        return None

    def _load_model(self):
        if self._model is None:
            print("[Embedding] 正在加载嵌入模型 (all-MiniLM-L6-v2)...", flush=True)
            from sentence_transformers import SentenceTransformer

            # 策略：首先尝试手动路径解析（最稳健）-> 然后是库缓存 -> 然后是在线
            model_name = "sentence-transformers/all-MiniLM-L6-v2"

            # 1. 尝试手动路径解析
            local_path = self._resolve_local_path(model_name)
            if local_path:
                try:
                    # print(f"[Embedding] 发现本地缓存路径: {local_path}，尝试直接加载...", flush=True)
                    self._model = SentenceTransformer(local_path)
                    print("[Embedding] 已从本地缓存路径加载模型。", flush=True)
                    return
                except Exception as manual_e:
                    print(f"[Embedding] 手动路径加载失败: {manual_e}", flush=True)

            # 2. 尝试库本地加载（回退）
            try:
                self._model = SentenceTransformer(
                    "all-MiniLM-L6-v2", local_files_only=True
                )
                print("[Embedding] 已从本地缓存加载模型。", flush=True)
                return
            except Exception as e:
                print(
                    f"[Embedding] 本地缓存未命中 (all-MiniLM-L6-v2): {e}。准备下载...",
                    flush=True,
                )

            print("[Embedding] 正在从镜像下载...", flush=True)
            try:
                # 3. 从镜像下载
                self._model = SentenceTransformer(
                    "all-MiniLM-L6-v2", local_files_only=False
                )
                print("[Embedding] 模型下载并加载完成。", flush=True)
            except Exception as net_e:
                print(f"[Embedding] 致命错误: 无法下载模型: {net_e}", flush=True)
                raise net_e

    def _load_reranker(self):
        if self._cross_encoder is None:
            print(
                "[Embedding] 正在加载重排序模型 (BAAI/bge-reranker-v2-m3)...",
                flush=True,
            )
            from sentence_transformers import CrossEncoder

            # 策略：首先尝试手动路径解析
            model_name = "BAAI/bge-reranker-v2-m3"

            # 1. 尝试手动路径解析
            local_path = self._resolve_local_path(model_name)
            if local_path:
                try:
                    # print(f"[Embedding] 发现本地缓存路径: {local_path}，尝试直接加载...", flush=True)
                    self._cross_encoder = CrossEncoder(local_path)
                    print("[Embedding] 已从本地缓存路径加载重排序模型。", flush=True)
                    return
                except Exception as manual_e:
                    print(f"[Embedding] 手动路径加载失败: {manual_e}", flush=True)

            # 2. 尝试库本地加载（回退）严格本地模式
            with contextlib.suppress(Exception):
                # 使用 model_kwargs 代替 automodel_args（已弃用）
                # 确保将 local_files_only=True 传递给底层 transformer
                self._cross_encoder = CrossEncoder(
                    "BAAI/bge-reranker-v2-m3",
                    trust_remote_code=True,
                    automodel_args={"local_files_only": True},  # 旧版
                )

            try:
                # 尝试基于警告的“新方法”
                print("[Embedding] 尝试使用 model_kwargs 加载...", flush=True)
                self._cross_encoder = CrossEncoder(
                    "BAAI/bge-reranker-v2-m3", model_kwargs={"local_files_only": True}
                )
                print(
                    "[Embedding] 已从本地缓存加载重排序模型 (model_kwargs)。",
                    flush=True,
                )
                return
            except Exception as e:
                print(f"[Embedding] model_kwargs 加载失败: {e}", flush=True)

            try:
                # 回退到“旧方法”
                print("[Embedding] 尝试使用 automodel_args 加载...", flush=True)
                self._cross_encoder = CrossEncoder(
                    "BAAI/bge-reranker-v2-m3", automodel_args={"local_files_only": True}
                )
                print(
                    "[Embedding] 已从本地缓存加载重排序模型 (automodel_args)。",
                    flush=True,
                )
                return
            except Exception as e:
                print(f"[Embedding] automodel_args 加载失败: {e}", flush=True)

            print(
                "[Embedding] 本地缓存未命中 (BAAI/bge-reranker-v2-m3)。准备下载...",
                flush=True,
            )

            try:
                # 3. 从镜像下载
                self._cross_encoder = CrossEncoder(
                    "BAAI/bge-reranker-v2-m3", local_files_only=False
                )
                print("[Embedding] 重排序模型下载并加载完成。", flush=True)
            except Exception as net_e:
                print(f"[Embedding] 致命错误: 无法下载重排序模型: {net_e}", flush=True)
                raise net_e

    def warm_up(self):
        """
        预热模型，防止首次请求超时
        """
        print("[Embedding] 正在预热模型...", flush=True)

        # 1. 预热嵌入模型
        try:
            self._load_model()
            # 进行一次简单的推理以确保 GPU/CPU 内存完全加载
            if self._model:
                self._model.encode(["warm up"])
        except Exception as e:
            print(f"[Embedding] 嵌入模型预热失败: {e}", flush=True)

        # 2. 预热重排序模型
        try:
            self._load_reranker()
            if self._cross_encoder:
                self._cross_encoder.predict([["warm up", "test"]])
        except Exception as e:
            print(f"[Embedding] 重排序模型预热失败: {e}", flush=True)

        print("[Embedding] 预热流程结束。", flush=True)

    def encode(self, texts: List[str]) -> List[List[float]]:
        """
        生成文本向量
        """
        try:
            self._load_model()
            if not texts or self._model is None:
                return []

            embeddings = self._model.encode(texts)
            # 转换为 list
            return embeddings.tolist()
        except Exception as e:
            print(f"[Embedding] 生成向量失败: {e}", flush=True)
            return []

    def encode_one(self, text: str) -> List[float]:
        """生成单条文本向量"""
        try:
            result = self.encode([text])
            return result[0] if result else []
        except Exception:
            return []

    def compute_similarity(
        self, query_embedding: List[float], doc_embeddings: List[List[float]]
    ) -> List[float]:
        """
        计算余弦相似度
        """
        if not doc_embeddings:
            return []

        # 使用 numpy 加速
        q = np.array(query_embedding)
        docs = np.array(doc_embeddings)

        # 归一化 (MiniLM 输出通常已经归一化，但为了保险)
        norm_q = np.linalg.norm(q)
        norm_docs = np.linalg.norm(docs, axis=1)

        if norm_q == 0:
            return [0.0] * len(doc_embeddings)

        # 防止除零
        norm_docs[norm_docs == 0] = 1e-9

        # Cosine Similarity: (A . B) / (|A| * |B|)
        dot_products = np.dot(docs, q)
        similarities = dot_products / (norm_docs * norm_q)

        return similarities.tolist()

    def rerank(self, query: str, docs: List[str], top_k: int = None) -> List[dict]:
        """
        使用 Cross-Encoder 对文档进行重排序
        返回: [{"index": original_index, "score": float, "doc": str}, ...]
        """
        try:
            self._load_reranker()
            if not docs or self._cross_encoder is None:
                return []

            # [Performance] BGE-Reranker-v2-M3 性能开销较大
            # 限制输入文档数量，确保精排在 1 秒内完成
            max_rerank_docs = 15
            if len(docs) > max_rerank_docs:
                print(
                    f"[Embedding] 为了性能，将重排序输入从 {len(docs)} 截断为 {max_rerank_docs}。"
                )
                docs = docs[:max_rerank_docs]

            pairs = [[query, doc] for doc in docs]
            scores = self._cross_encoder.predict(pairs)

            results = []
            for i, score in enumerate(scores):
                results.append({"index": i, "score": float(score), "doc": docs[i]})

            # 按分数降序
            results.sort(key=lambda x: x["score"], reverse=True)

            if top_k:
                return results[:top_k]
            return results
        except Exception as e:
            print(f"[Embedding] 重排序失败: {e}", flush=True)
            # 返回原始顺序的分数（降级）
            return [
                {"index": i, "score": 1.0, "doc": doc}
                for i, doc in enumerate(docs[:top_k] if top_k else docs)
            ]


# 全局单例
embedding_service = EmbeddingService()
