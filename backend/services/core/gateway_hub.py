"""
Gateway Hub — 嵌入式 WebSocket 消息路由器
从 Go 独立 Gateway (gateway/gateway/main.go) 翻译而来。

功能：
- WebSocket 客户端连接管理（注册/注销节点）
- Hello 握手 + Token 认证
- 心跳响应
- 单播 / 广播消息路由
- Protobuf Envelope 编解码

替代了原来独立的 Go Gateway 进程（端口 14747）。
"""

import asyncio
import logging
import time
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from peroproto import perolink_pb2

logger = logging.getLogger(__name__)


class GatewayNode:
    """代表一个已连接的客户端节点"""

    def __init__(self, node_id: str, websocket: WebSocket):
        self.id = node_id
        self.websocket = websocket
        self._lock = asyncio.Lock()

    async def send(self, data: bytes):
        async with self._lock:
            await self.websocket.send_bytes(data)


class GatewayHub:
    """
    WebSocket Hub，管理所有 Gateway 连接。
    等价于原 Go Gateway 的 Hub struct + handleWebSocket + handleEnvelope。

    此实例是全局单例，同时供：
    1. WebSocket 端点 (/ws/gateway) 调用 handle_connection()
    2. 后端内部服务直接调用 broadcast() / unicast() （替代原 GatewayClient 的 WS 连接）
    """

    def __init__(self):
        self._nodes: dict[str, GatewayNode] = {}
        self._lock = asyncio.Lock()
        self._auth_token: str = ""
        # 内部事件监听器，供后端服务注册回调
        self._listeners: dict[str, list] = {}

    @property
    def auth_token(self) -> str:
        return self._auth_token

    @auth_token.setter
    def auth_token(self, token: str):
        self._auth_token = token

    # --- 事件系统（供后端内部使用） ---

    def on(self, event_name: str, callback):
        """注册内部事件监听器"""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(callback)

    def _emit(self, event_name: str, *args, **kwargs):
        """触发内部事件"""
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(*args, **kwargs))
                else:
                    try:
                        callback(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"{event_name} 监听器错误: {e}")

    # --- 连接管理 ---

    async def handle_connection(self, websocket: WebSocket):
        """
        处理单个 WebSocket 连接的完整生命周期。
        由 FastAPI WebSocket 端点调用。
        """
        await websocket.accept()
        node_id = None

        try:
            while True:
                data = await websocket.receive_bytes()

                envelope = perolink_pb2.Envelope()
                envelope.ParseFromString(data)

                # 处理 Hello 握手
                if envelope.HasField("hello"):
                    node_id = envelope.source_id
                    hello = envelope.hello

                    if hello.token != self._auth_token:
                        logger.warning(
                            f"⚠️  来自 {node_id} 的令牌无效: "
                            f"{hello.token[:8]}... (预期: {self._auth_token[:8]}...)"
                        )
                    # 即使 token 无效也允许连接（与 Go 版本行为一致）

                    async with self._lock:
                        self._nodes[node_id] = GatewayNode(node_id, websocket)
                    logger.debug(f"节点 {node_id} 已注册")
                    continue

                # 心跳 — 不转发
                if envelope.HasField("heartbeat"):
                    continue

                # 处理 request — 触发内部事件
                if envelope.HasField("request"):
                    self._emit("request", envelope)
                    self._emit(
                        f"action:{envelope.request.action_name}", envelope
                    )

                # 路由逻辑
                if envelope.target_id == "broadcast":
                    await self._broadcast(envelope)
                elif envelope.target_id != "master":
                    await self._unicast(envelope)

        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Gateway WS 错误: {e}")
        finally:
            if node_id:
                async with self._lock:
                    self._nodes.pop(node_id, None)
                logger.debug(f"节点 {node_id} 已断开连接")

    async def _broadcast(self, envelope):
        """广播消息给所有节点（排除发送者）"""
        data = envelope.SerializeToString()
        async with self._lock:
            nodes = list(self._nodes.items())

        for nid, node in nodes:
            if nid == envelope.source_id:
                continue
            try:
                await node.send(data)
            except Exception as e:
                logger.error(f"发送至 {nid} 错误: {e}")

    async def _unicast(self, envelope):
        """单播消息给指定节点"""
        async with self._lock:
            node = self._nodes.get(envelope.target_id)

        if not node:
            logger.debug(f"目标节点 {envelope.target_id} 未找到")
            return

        try:
            data = envelope.SerializeToString()
            await node.send(data)
        except Exception as e:
            logger.error(f"发送至 {envelope.target_id} 错误: {e}")

    # --- 后端直接调用的广播方法（替代原 GatewayClient 的 WS 发送） ---

    async def broadcast_envelope(self, envelope):
        """
        后端内部直接广播 Envelope（不经过 WebSocket）。
        替代原 GatewayClient.send() 方法。
        """
        data = envelope.SerializeToString()
        async with self._lock:
            nodes = list(self._nodes.items())

        for nid, node in nodes:
            if nid == envelope.source_id:
                continue
            try:
                await node.send(data)
            except Exception as e:
                logger.error(f"广播至 {nid} 错误: {e}")

    async def broadcast_pet_state(self, state_dict: dict):
        """向所有客户端广播 PetState 更新"""
        envelope = self._make_broadcast_envelope()
        envelope.request.action_name = "state_update"
        for k, v in state_dict.items():
            if v is not None:
                envelope.request.params[k] = str(v)
        await self.broadcast_envelope(envelope)
        logger.debug(f"广播 PetState 更新: {state_dict.get('mood')}")

    async def broadcast_text_response(self, content: str, target: str = "all"):
        """向前端客户端广播 LLM 文本响应"""
        envelope = self._make_broadcast_envelope()
        envelope.request.action_name = "text_response"
        envelope.request.params["content"] = content
        envelope.request.params["target"] = target
        await self.broadcast_envelope(envelope)
        logger.debug(f"已广播文本响应: {content[:30]}...")

    async def broadcast_error(
        self, message: str, title: str = "错误", error_type: str = "error"
    ):
        """向前端广播错误通知"""
        envelope = self._make_broadcast_envelope()
        envelope.request.action_name = "system_error"
        envelope.request.params["payload"] = message
        envelope.request.params["message"] = message
        envelope.request.params["title"] = title
        envelope.request.params["type"] = error_type
        await self.broadcast_envelope(envelope)
        logger.debug(f"广播错误通知: {title} - {message}")

    async def send_response(self, target_id: str, request_id: str, data: str):
        """向指定节点发送响应"""
        envelope = perolink_pb2.Envelope()
        envelope.id = str(uuid.uuid4())
        envelope.source_id = "python-backend"
        envelope.target_id = target_id
        envelope.timestamp = int(time.time() * 1000)
        envelope.response.request_id = request_id
        envelope.response.status = 0
        envelope.response.data = data

        async with self._lock:
            node = self._nodes.get(target_id)
        if node:
            try:
                await node.send(envelope.SerializeToString())
            except Exception as e:
                logger.error(f"发送响应至 {target_id} 错误: {e}")

    def _make_broadcast_envelope(self) -> perolink_pb2.Envelope:
        """创建广播信封模板"""
        envelope = perolink_pb2.Envelope()
        envelope.id = str(uuid.uuid4())
        envelope.source_id = "python-backend"
        envelope.target_id = "broadcast"
        envelope.timestamp = int(time.time() * 1000)
        return envelope

    @property
    def connected_count(self) -> int:
        return len(self._nodes)


# 全局单例
gateway_hub = GatewayHub()
