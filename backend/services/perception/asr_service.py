import os

# [重要] 在导入使用它的库之前设置 HuggingFace 镜像
# 这必须在文件的最顶部完成
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
# 禁用 hf_transfer 以避免特定系统配置的潜在问题
if "HF_HUB_ENABLE_HF_TRANSFER" not in os.environ:
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import asyncio
import json
import time
from typing import Optional

import httpx
from faster_whisper import WhisperModel, download_model
from sqlmodel import select

from database import get_session
from models import VoiceConfig


class ASRService:
    def __init__(self):
        # 统一缓存目录，与EmbeddingService一致
        self.data_dir = os.environ.get(
            "PERO_DATA_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.models_cache_dir = os.path.join(self.data_dir, "models_cache")

        # 确保缓存目录存在
        if not os.path.exists(self.models_cache_dir):
            os.makedirs(self.models_cache_dir, exist_ok=True)

        self.device = "cpu"
        self.compute_type = "int8"
        self._model = None
        self._lock = asyncio.Lock()

    async def _get_active_config(self) -> Optional[VoiceConfig]:
        async for session in get_session():
            return (
                await session.exec(
                    select(VoiceConfig)
                    .where(VoiceConfig.type == "stt")
                    .where(VoiceConfig.is_active)
                )
            ).first()
        return None

    def _download_with_retry(self, model_name: str, max_retries: int = 3) -> str:
        """带有重试机制的模型下载"""
        # 若路径存在但无效可警告，暂信任用户显式路径
        if (os.path.exists(model_name) or os.path.isabs(model_name)) and (
            (
                os.path.isdir(model_name)
                and os.path.exists(os.path.join(model_name, "model.bin"))
            )
            or os.path.isfile(model_name)
        ):
            return model_name

        last_error = None
        for attempt in range(max_retries):
            try:
                print(
                    f"[ASR] 正在检查/下载模型 '{model_name}' (尝试 {attempt+1}/{max_retries})...",
                    flush=True,
                )
                # download_model返回模型目录路径
                model_path = download_model(
                    model_name, output_dir=self.models_cache_dir
                )

                # 验证：检查model.bin是否存在
                if not os.path.exists(os.path.join(model_path, "model.bin")):
                    raise ValueError(
                        f"下载的模型路径 '{model_path}' 不包含 model.bin 文件"
                    )

                return model_path
            except Exception as e:
                last_error = e
                print(f"[ASR] 下载失败: {e}", flush=True)

                # 清理可能损坏的目录（若为新下载）。
                # 注意：小心勿删整个缓存根目录。
                # 通常model_path为子目录，但超时可能导致未设置或无效。

                if attempt < max_retries - 1:
                    print("[ASR] 3秒后重试...", flush=True)
                    time.sleep(3)

        raise last_error

    def _load_model(self, model_path: str, device: str, compute_type: str):
        """延迟加载模型"""
        if self._model is None:
            try:
                # 先尝试确保模型已下载 (如果是远程模型名)
                # 如果是本地路径，_download_with_retry 会直接返回原路径
                real_model_path = self._download_with_retry(model_path)

                print(
                    f"正在 {device} 上加载 Whisper 模型: {real_model_path}...",
                    flush=True,
                )

                # [Optimize] 检查本地模型是否存在，如果存在则设置 local_files_only=True
                local_files_only = False
                if os.path.exists(real_model_path) and (
                    os.path.isfile(os.path.join(real_model_path, "model.bin"))
                    or os.path.isfile(os.path.join(real_model_path, "model.safetensors"))
                ):
                    local_files_only = True

                try:
                    # Explicitly set download_root to project's models_cache to avoid issues with default system cache
                    self._model = WhisperModel(
                        real_model_path,
                        device=device,
                        compute_type=compute_type,
                        download_root=self.models_cache_dir,
                        local_files_only=local_files_only,
                    )
                except Exception as e:
                    # 如果因为离线加载失败，尝试在线加载
                    if local_files_only:
                        print(f"本地模型加载失败，尝试在线加载: {e}", flush=True)
                        self._model = WhisperModel(
                            real_model_path,
                            device=device,
                            compute_type=compute_type,
                            download_root=self.models_cache_dir,
                        )
                    else:
                        raise e

                print("Whisper 模型加载成功。", flush=True)
            except Exception as e:
                print(f"模型加载失败: {e}", flush=True)
                raise e

    def warm_up(self):
        """预热模型：检查并下载默认模型"""
        try:
            print("[ASR] 正在预热 Whisper 模型...", flush=True)
            # 预热默认的 tiny 模型
            self._load_model("tiny", self.device, self.compute_type)
        except Exception as e:
            print(f"[ASR] 预热失败 (非致命): {e}", flush=True)

    async def transcribe(self, audio_path: str) -> Optional[str]:
        """
        识别音频文件
        """
        config = await self._get_active_config()
        if not config:
            # Fallback to local whisper
            return await self._transcribe_local(audio_path, {}, None)

        try:
            config_json = json.loads(config.config_json)
        except Exception:
            config_json = {}

        if config.provider == "local_whisper":
            return await self._transcribe_local(audio_path, config_json, config)
        elif config.provider == "openai_compatible":
            return await self._transcribe_openai(audio_path, config_json, config)
        else:
            return await self._transcribe_local(audio_path, config_json, config)

    async def _transcribe_local(
        self, audio_path: str, config_json: dict, config: Optional[VoiceConfig]
    ) -> Optional[str]:
        async with self._lock:
            try:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, self._transcribe_sync, audio_path, config_json
                )
            except Exception as e:
                print(f"ASR 错误: {e}")
                # 重新抛出异常，以便上层捕获并通知前端
                raise e

    def _transcribe_sync(self, audio_path: str, config_json: dict) -> str:
        device = config_json.get("device", "cpu")
        compute_type = config_json.get("compute_type", "int8")

        # 允许通过配置指定模型名称或路径，默认为 tiny
        model_name = config_json.get("model_path", "tiny")

        # 检查配置是否变更，若变更则重置模型以便重新加载
        if self._model is not None and (
            getattr(self, "_current_model_name", None) != model_name
            or getattr(self, "_current_device", None) != device
            or getattr(self, "_current_compute_type", None) != compute_type
        ):
            print("[ASR] 配置已更改，正在重新加载模型...", flush=True)
            self._model = None

        self._current_model_name = model_name
        self._current_device = device
        self._current_compute_type = compute_type

        self._load_model(model_name, device, compute_type)
        segments, info = self._model.transcribe(
            audio_path, beam_size=5, language="zh", task="transcribe"
        )

        full_text = ""
        for segment in segments:
            full_text += segment.text

        return full_text.strip()

    async def _transcribe_openai(
        self, audio_path: str, config_json: dict, config: VoiceConfig
    ) -> Optional[str]:
        try:
            url = (
                f"{config.api_base}/audio/transcriptions"
                if config.api_base
                else "https://api.openai.com/v1/audio/transcriptions"
            )

            headers = {"Authorization": f"Bearer {config.api_key}"}

            # 准备 multipart/form-data
            data = {
                "model": config.model or "whisper-1",
            }

            # 读取文件内容
            if not os.path.exists(audio_path):
                return None

            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(audio_path, "rb") as f:
                    # 使用文件名作为 file 字段 filename
                    files = {"file": (os.path.basename(audio_path), f, "audio/wav")}
                    response = await client.post(
                        url, headers=headers, data=data, files=files
                    )

                if response.status_code != 200:
                    print(f"OpenAI ASR API 错误: {response.text}")
                    return None

                result = response.json()
                return result.get("text", "")
        except Exception as e:
            print(f"OpenAI ASR 错误: {e}")
            return None


_asr_service = None


def get_asr_service() -> ASRService:
    global _asr_service
    if _asr_service is None:
        _asr_service = ASRService()
    return _asr_service
