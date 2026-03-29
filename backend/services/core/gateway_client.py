"""
Gateway Client — Hub 代理层
原来通过 WebSocket 连接到独立 Go Gateway (ws://localhost:14747/ws)，
现在改为直接代理到进程内的 GatewayHub 单例。

保持对外 API 不变，所有调用方（agent_service, scheduler_service 等）无需修改。
"""

import logging

from services.core.gateway_hub import gateway_hub

logger = logging.getLogger(__name__)


class GatewayClient:
    """
    Gateway 客户端 — 现在是 gateway_hub 的薄代理。
    保留原有的公开接口，所有调用方无需改动。
    """

    def __init__(self, uri: str = None, token: str = None):
        self.running = False
        self._device_id = "python-backend"
        if token:
            self.set_token(token)
        if uri:
            logger.info(f"[GatewayClient] 正在以外部连接模式初始化: {uri}")

    @property
    def device_id(self):
        return self._device_id

    @device_id.setter
    def device_id(self, value):
        self._device_id = value

    def set_token(self, token: str):
        """设置认证令牌 — 直接设置到 Hub"""
        gateway_hub.auth_token = token

    def on(self, event_name: str, callback):
        """注册事件监听器 — 委托给 Hub"""
        gateway_hub.on(event_name, callback)

    async def start(self):
        """启动 — Hub 是被动的 WebSocket 端点，无需主动连接"""
        self.running = True
        logger.info("[GatewayClient] 已启动（嵌入式 Hub 模式）")

    def start_background(self):
        """后台启动 — Hub 模式下无需操作"""
        self.running = True

    async def send(self, envelope):
        """发送封包 — 委托给 Hub 广播"""
        try:
            await gateway_hub.broadcast(envelope)
        except Exception as e:
            logger.error(f"发送封包失败: {e}")

    async def stop(self):
        """停止"""
        self.running = False

    async def broadcast_pet_state(self, state_dict: dict):
        """向所有客户端广播 PetState 更新"""
        try:
            await gateway_hub.broadcast_pet_state(state_dict)
        except Exception as e:
            logger.error(f"广播 PetState 失败: {e}")

    async def broadcast_text_response(self, content: str, target: str = "all"):
        """向前端客户端广播 LLM 文本响应"""
        try:
            await gateway_hub.broadcast_text_response(content, target)
        except Exception as e:
            logger.error(f"广播文本响应失败: {e}")

    async def broadcast_error(
        self, message: str, title: str = "错误", error_type: str = "error"
    ):
        """向前端广播错误通知"""
        try:
            await gateway_hub.broadcast_error(message, title, error_type)
        except Exception as e:
            logger.error(f"广播错误失败: {e}")

    async def broadcast_notification(
        self,
        title: str,
        body: str = "",
        level: str = "info",
        duration: int = 5000,
        actions: list = None,
        source: str = "mod",
    ):
        """向前端广播通用通知（供 MOD / 外部插件使用）"""
        try:
            await gateway_hub.broadcast_notification(
                title=title, body=body, level=level,
                duration=duration, actions=actions, source=source,
            )
        except Exception as e:
            logger.error(f"广播通知失败: {e}")


gateway_client = GatewayClient()
