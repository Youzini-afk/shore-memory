import logging
import os
from enum import Enum
from typing import Dict, List, Optional

from huggingface_hub import snapshot_download

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ModelManager")


class ModelType(Enum):
    WHISPER = "whisper"
    EMBEDDING = "embedding"
    RERANKER = "reranker"


class ModelInfo:
    def __init__(
        self, key: str, type: ModelType, repo_id: str, files: List[str] = None
    ):
        self.key = key
        self.type = type
        self.repo_id = repo_id
        # 用于验证模型是否完整的关键文件列表
        self.files = files or ["config.json"]


class ModelManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # 确定数据目录
        # 默认使用 backend/data 目录
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.environ.get(
            "PERO_DATA_DIR",
            os.path.join(backend_dir, "data"),
        )
        self.models_cache_dir = os.path.join(self.data_dir, "models_cache")

        # 确保目录存在
        os.makedirs(self.models_cache_dir, exist_ok=True)

        logger.info(f"模型缓存目录已初始化: {self.models_cache_dir}")

        # 设置环境变量
        if "HF_ENDPOINT" not in os.environ:
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        # 定义支持的模型
        self.models: Dict[str, ModelInfo] = {
            "tiny": ModelInfo(
                "tiny",
                ModelType.WHISPER,
                "systran/faster-whisper-tiny",
                ["model.bin", "config.json"],
            ),
            "base": ModelInfo(
                "base",
                ModelType.WHISPER,
                "systran/faster-whisper-base",
                ["model.bin", "config.json"],
            ),
            "small": ModelInfo(
                "small",
                ModelType.WHISPER,
                "systran/faster-whisper-small",
                ["model.bin", "config.json"],
            ),
            "medium": ModelInfo(
                "medium",
                ModelType.WHISPER,
                "systran/faster-whisper-medium",
                ["model.bin", "config.json"],
            ),
            "large-v3": ModelInfo(
                "large-v3",
                ModelType.WHISPER,
                "systran/faster-whisper-large-v3",
                ["model.bin", "config.json"],
            ),
            "embedding": ModelInfo(
                "embedding",
                ModelType.EMBEDDING,
                "sentence-transformers/all-MiniLM-L6-v2",
                ["config.json", "pytorch_model.bin", "tokenizer.json"],
            ),
            "reranker": ModelInfo(
                "reranker",
                ModelType.RERANKER,
                "BAAI/bge-reranker-v2-m3",
                ["config.json", "pytorch_model.bin", "tokenizer.json"],
            ),
        }

    def get_model_path(self, model_key: str) -> str:
        """获取模型的本地存储路径"""
        if model_key not in self.models:
            raise ValueError(f"Unknown model key: {model_key}")

        model = self.models[model_key]
        # 使用 HuggingFace 标准的缓存结构
        # models--owner--repo_name
        repo_dir_name = f"models--{model.repo_id.replace('/', '--')}"
        return os.path.join(self.models_cache_dir, repo_dir_name)

    def check_model_exists(self, model_key: str) -> bool:
        """检查模型是否已下载且完整"""
        try:
            path = self.get_model_path(model_key)

            # 检查快照目录
            snapshots_dir = os.path.join(path, "snapshots")
            if not os.path.exists(snapshots_dir):
                return False

            # 获取最新的快照
            snapshots = os.listdir(snapshots_dir)
            if not snapshots:
                return False

            # 假设最新的快照是有效的
            latest_snapshot = os.path.join(snapshots_dir, snapshots[0])

            # 检查关键文件
            model_info = self.models[model_key]
            for file in model_info.files:
                if not os.path.exists(os.path.join(latest_snapshot, file)):
                    # 尝试查找 .safetensors 版本
                    if file == "pytorch_model.bin" and os.path.exists(
                        os.path.join(latest_snapshot, "model.safetensors")
                    ):
                        continue
                    if file == "model.bin" and os.path.exists(
                        os.path.join(latest_snapshot, "model.safetensors")
                    ):
                        continue
                    return False

            return True
        except Exception as e:
            logger.error(f"Error checking model {model_key}: {e}")
            return False

    def get_actual_model_path(self, model_key: str) -> Optional[str]:
        """获取模型实际加载路径（指向具体的 snapshot 目录）"""
        if not self.check_model_exists(model_key):
            return None

        path = self.get_model_path(model_key)
        snapshots_dir = os.path.join(path, "snapshots")
        snapshots = os.listdir(snapshots_dir)
        if not snapshots:
            return None

        return os.path.join(snapshots_dir, snapshots[0])

    def download_model(self, model_key: str, force: bool = False) -> str:
        """下载模型"""
        if model_key not in self.models:
            raise ValueError(f"Unknown model key: {model_key}")

        model = self.models[model_key]

        if not force and self.check_model_exists(model_key):
            logger.info(f"Model {model_key} already exists.")
            return self.get_actual_model_path(model_key)

        logger.info(f"Downloading model {model_key} from {model.repo_id}...")

        try:
            # 使用 huggingface_hub 下载
            path = snapshot_download(
                repo_id=model.repo_id,
                cache_dir=self.models_cache_dir,
                local_files_only=False,
                # resume_download=True,  # Deprecated in newer versions
            )
            logger.info(f"Model {model_key} downloaded successfully to {path}")
            return path
        except Exception as e:
            logger.error(f"Failed to download model {model_key}: {e}")
            raise e


# 全局单例
model_manager = ModelManager()
