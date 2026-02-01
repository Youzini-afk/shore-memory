import os
import logging
import asyncio
import json
import time
import uuid
from typing import Optional, Dict, Any
from services.gateway_client import GatewayClient
from peroproto import perolink_pb2

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
        
        # Initial values from ENV (will be overwritten by DB if available)
        self.cloud_url = os.getenv("CLOUD_GATEWAY_URL", "")
        self.cloud_token = os.getenv("CLOUD_GATEWAY_TOKEN", "")
        self.mode = os.getenv("CLOUD_SYNC_MODE", "client") # "client" or "server"
        self.enabled = os.getenv("CLOUD_SYNC_ENABLED", "false").lower() == "true"
        
        self.client: Optional[GatewayClient] = None
        self.running = False
        self.pending_updates = []
        
    async def load_config(self):
        """Load configuration from ConfigManager (DB)."""
        from core.config_manager import get_config_manager
        cm = get_config_manager()
        
        # ConfigManager has already loaded from DB at startup
        # We check if specific keys exist, otherwise fallback to current (ENV)
        
        # Helper to get config safely
        def get_conf(key, default):
            val = cm.get(key)
            return val if val is not None else default

        self.cloud_url = get_conf("cloud_sync_url", self.cloud_url)
        self.cloud_token = get_conf("cloud_sync_token", self.cloud_token)
        self.mode = get_conf("cloud_sync_mode", self.mode)
        self.enabled = str(get_conf("cloud_sync_enabled", str(self.enabled))).lower() == "true"
        
        logger.info(f"[Sync] Loaded Config: enabled={self.enabled}, mode={self.mode}, url={self.cloud_url}")

    async def reload(self):
        """Reload config and restart service."""
        await self.stop()
        await self.load_config()
        if self.enabled:
            self.start()

    def start(self):
        """Start the sync service if configured."""
        # Ensure we don't start if disabled or missing config
        if not self.enabled:
            logger.debug("[Sync] Service disabled.")
            return

        if self.mode == "server":
            logger.info("☁️ [Sync] Running in SERVER mode (Passive).")
            # In server mode, we don't connect to another gateway.
            # We just wait for connections (handled by main Gateway).
            self.running = True
            return

        if self.cloud_url and self.cloud_token:
            logger.info(f"☁️ [Sync] 启动云端同步服务 (Client Mode)...")
            logger.info(f"☁️ [Sync] 目标网关: {self.cloud_url}")
            
            # Create a dedicated client for Cloud connection
            self.client = GatewayClient(uri=self.cloud_url)
            self.client.set_token(self.cloud_token)
            
            # Use a distinct device ID for the sync client to avoid confusion
            # Appending -sync suffix
            self.client.device_id = f"{self.client.device_id}-sync"
            
            # Register handlers
            self.client.on("connect", self.on_connect)
            self.client.on("disconnect", self.on_disconnect)
            self.client.on("action:sync_push", self.handle_sync_push)
            
            # Start client
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
        # Example: Send a hello/sync-init message
        await self.push_update("sync_init", {"status": "connected"})

    async def on_disconnect(self):
        logger.warning("☁️ [Sync] 与云端网关断开连接")

    async def handle_sync_push(self, envelope):
        """Handle incoming data push from cloud."""
        try:
            req = envelope.request
            payload_str = req.params.get("payload", "{}")
            data_type = req.params.get("type", "unknown")
            
            try:
                payload = json.loads(payload_str)
            except:
                payload = payload_str

            logger.info(f"☁️ [Sync] 收到云端推送 [{data_type}]: {str(payload)[:50]}...")
            
            # Dispatch to appropriate handlers (to be implemented)
            # if data_type == "pet_state": ...
            
        except Exception as e:
            logger.error(f"☁️ [Sync] 处理推送失败: {e}")

    async def push_update(self, data_type: str, payload: Dict[str, Any]):
        """Push local update to cloud."""
        if not self.running or not self.client:
            return

        try:
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = self.client.device_id
            envelope.target_id = "master" # Generally targeting the master node on cloud
            envelope.timestamp = int(time.time() * 1000)
            
            envelope.request.action_name = "sync_push"
            envelope.request.params["type"] = data_type
            
            if isinstance(payload, (dict, list)):
                envelope.request.params["payload"] = json.dumps(payload, ensure_ascii=False)
            else:
                envelope.request.params["payload"] = str(payload)
            
            await self.client.send(envelope)
            logger.debug(f"☁️ [Sync] 已推送更新 [{data_type}]")
        except Exception as e:
            logger.error(f"☁️ [Sync] 推送更新失败: {e}")

# Global instance
sync_service = SyncService()
