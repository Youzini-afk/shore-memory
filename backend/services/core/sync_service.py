import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

from peroproto import perolink_pb2
from services.core.gateway_client import GatewayClient

logger = logging.getLogger(__name__)


class SyncService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SyncService, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        self.initialized = True

        # 从环境变量获取初始值（如果数据库中有值，将被覆盖）
        self.cloud_url = os.getenv("CLOUD_GATEWAY_URL", "")
        self.cloud_token = os.getenv("CLOUD_GATEWAY_TOKEN", "")
        self.mode = os.getenv("CLOUD_SYNC_MODE", "client")  # "client" or "server"
        self.enabled = os.getenv("CLOUD_SYNC_ENABLED", "false").lower() == "true"

        self.client: Optional[GatewayClient] = None
        self.running = False
        self.pending_updates = []

    async def load_config(self):
        """从 ConfigManager (数据库) 加载配置。"""
        from core.config_manager import get_config_manager

        cm = get_config_manager()

        # ConfigManager 在启动时已经从数据库加载
        # 我们检查特定的键是否存在，否则回退到当前值 (环境变量)

        # 安全获取配置的辅助函数
        def get_conf(key, default):
            val = cm.get(key)
            return val if val is not None else default

        self.cloud_url = get_conf("cloud_sync_url", self.cloud_url)
        self.cloud_token = get_conf("cloud_sync_token", self.cloud_token)
        self.mode = get_conf("cloud_sync_mode", self.mode)
        self.enabled = (
            str(get_conf("cloud_sync_enabled", str(self.enabled))).lower() == "true"
        )

        if self.enabled:
            logger.info(
                f"[Sync] Loaded Config: enabled={self.enabled}, mode={self.mode}, url={self.cloud_url}"
            )
        else:
            logger.debug(
                f"[Sync] Loaded Config: enabled={self.enabled}, mode={self.mode}, url={self.cloud_url}"
            )

    async def reload(self):
        """重新加载配置并重启服务。"""
        await self.stop()
        await self.load_config()
        if self.enabled:
            self.start()

    def start(self):
        """如果已配置，则启动同步服务。"""
        # 确保在禁用或缺少配置时不启动
        if not self.enabled:
            logger.debug("[Sync] Service disabled.")
            return

        if self.mode == "server":
            logger.info("☁️ [Sync] Running in SERVER mode (Passive).")
            # 在服务器模式下，我们不连接到另一个网关。
            # 我们只是等待连接（由主网关处理）。
            self.running = True
            return

        if self.cloud_url and self.cloud_token:
            logger.info("☁️ [Sync] 启动云端同步服务 (Client Mode)...")
            logger.info(f"☁️ [Sync] 目标网关: {self.cloud_url}")

            # 为云连接创建一个专用客户端
            self.client = GatewayClient(uri=self.cloud_url)
            self.client.set_token(self.cloud_token)

            # 为同步客户端使用不同的设备 ID 以避免混淆
            # 添加 -sync 后缀
            self.client.device_id = f"{self.client.device_id}-sync"

            # 注册处理程序
            self.client.on("connect", self.on_connect)
            self.client.on("disconnect", self.on_disconnect)
            self.client.on("action:sync_push", self.handle_sync_push)

            # 启动客户端
            self.client.start_background()
            self.running = True
        else:
            logger.debug("[Sync] 未配置云端同步 (CLOUD_GATEWAY_URL/TOKEN 未设置)")

    async def stop(self):
        if self.client:
            await self.client.stop()
            self.running = False

    async def on_connect(self):
        logger.info("☁️ [Sync] 已连接到云端网关!")
        # 示例: 发送 hello/sync-init 消息
        await self.push_update("sync_init", {"status": "connected"})

    async def on_disconnect(self):
        logger.warning("☁️ [Sync] 与云端网关断开连接")

    async def handle_sync_push(self, envelope):
        """处理来自云端的传入数据推送。"""
        try:
            req = envelope.request
            payload_str = req.params.get("payload", "{}")
            data_type = req.params.get("type", "unknown")

            try:
                payload = json.loads(payload_str)
            except Exception:
                payload = payload_str

            logger.info(f"☁️ [Sync] 收到云端推送 [{data_type}]: {str(payload)[:50]}...")

            # 分发到适当的处理程序（待实现）
            # if data_type == "pet_state": ...

        except Exception as e:
            logger.error(f"☁️ [Sync] 处理推送失败: {e}")

    async def push_update(self, data_type: str, payload: Dict[str, Any]):
        """将本地更新推送到云端。"""
        if not self.running or not self.client:
            return

        try:
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = self.client.device_id
            envelope.target_id = "master"  # 通常以云端的主节点为目标
            envelope.timestamp = int(time.time() * 1000)

            envelope.request.action_name = "sync_push"
            envelope.request.params["type"] = data_type

            if isinstance(payload, (dict, list)):
                envelope.request.params["payload"] = json.dumps(
                    payload, ensure_ascii=False
                )
            else:
                envelope.request.params["payload"] = str(payload)

            await self.client.send(envelope)
            logger.debug(f"☁️ [Sync] 已推送更新 [{data_type}]")
        except Exception as e:
            logger.error(f"☁️ [Sync] 推送更新失败: {e}")


# 全局实例
sync_service = SyncService()
