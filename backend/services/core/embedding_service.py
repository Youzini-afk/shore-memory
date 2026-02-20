import os
from typing import List, Optional

import numpy as np

from core.model_manager import model_manager

# 为了避免在导入时就下载模型，我们使用延迟加载
# 并且设置本地缓存目录
os.environ["SENTENCE_TRANSFORMERS_HOME"] = model_manager.models_cache_dir
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
                    # print(f"[Embedding] 调试: 正在检查基础路径: {base_path}", flush=True)
                    if not os.path.exists(base_path):
                        continue

                    # 策略 1: 检查 snapshots 目录并找到最新的快照
                    snapshots_dir = os.path.join(base_path, "snapshots")
                    if os.path.exists(snapshots_dir):
                        snapshots = os.listdir(snapshots_dir)
                        # print(f"[Embedding] 调试: 在 {base_path} 中发现快照: {snapshots}", flush=True)
                        if snapshots:
                            # 简单地取第一个找到的快照
                            snapshot_path = os.path.join(snapshots_dir, snapshots[0])
                            # 验证快照是否包含 config.json
                            config_path = os.path.join(snapshot_path, "config.json")
                            if os.path.isdir(snapshot_path) and os.path.exists(
                                config_path
                            ):
                                # print(f"[Embedding] 调试: 发现有效配置于 {config_path}", flush=True)
                                return snapshot_path
                            # else:
                            # print(f"[Embedding] 调试: 在 {config_path} 未找到配置", flush=True)

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
            import logging

            # 暂时禁用日志以保持输出清洁
            logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

            from sentence_transformers import SentenceTransformer

            # model_name = "BAAI/bge-small-zh-v1.5"
            # 使用 ModelManager 中定义的嵌入模型
            model_key = "embedding"

            try:
                # 尝试从 ModelManager 获取路径
                if model_manager.check_model_exists(model_key):
                    local_path = model_manager.get_actual_model_path(model_key)
                    self._model = SentenceTransformer(local_path, device="cpu")
                else:
                    # 如果不存在，尝试下载（使用 ModelManager）
                    print("[Embedding] 嵌入模型未找到，尝试下载...", flush=True)
                    local_path = model_manager.download_model(model_key)
                    self._model = SentenceTransformer(local_path, device="cpu")
            except Exception as e:
                print(f"[Embedding] 加载模型失败: {e}", flush=True)
                # 最后的降级方案，尝试在线加载默认名称
                default_name = model_manager.models[model_key].repo_id
                self._model = SentenceTransformer(default_name, device="cpu")

    def _load_reranker(self):
        if self._cross_encoder is None:
            print(
                "[Embedding] 正在加载重排序模型...",
                flush=True,
            )
            from sentence_transformers import CrossEncoder

            model_key = "reranker"

            try:
                # 尝试从 ModelManager 获取路径
                if model_manager.check_model_exists(model_key):
                    local_path = model_manager.get_actual_model_path(model_key)
                    self._cross_encoder = CrossEncoder(local_path)
                    print("[Embedding] 已从本地缓存路径加载重排序模型。", flush=True)
                    return
                else:
                    print("[Embedding] Reranker 模型未找到，尝试下载...", flush=True)
                    local_path = model_manager.download_model(model_key)
                    self._cross_encoder = CrossEncoder(local_path)
                    print("[Embedding] 重排序模型下载并加载完成。", flush=True)
                    return
            except Exception as e:
                print(f"[Embedding] 加载重排序模型失败: {e}", flush=True)
                # 尝试在线加载
                try:
                    default_name = model_manager.models[model_key].repo_id
                    self._cross_encoder = CrossEncoder(
                        default_name, trust_remote_code=True
                    )
                except Exception as net_e:
                    print(
                        f"[Embedding] 致命错误: 无法下载重排序模型: {net_e}", flush=True
                    )
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

            # [性能] BGE-Reranker-v2-M3 性能开销较大
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
