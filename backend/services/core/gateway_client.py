import asyncio
import logging
import os
import platform
import time
import uuid

import websockets

from peroproto import perolink_pb2

logger = logging.getLogger(__name__)


class GatewayClient:
    def __init__(self, uri="ws://localhost:14747/ws"):
        self._configure_proxy_bypass()
        self.uri = uri
        self.websocket = None
        self.running = False
        self.device_id = f"python-backend-{str(uuid.uuid4())[:8]}"
        self.heartbeat_task = None
        # 优先从环境变量获取令牌，这是由 Electron 主进程传入的最新令牌
        self.token = os.getenv("GATEWAY_TOKEN", "python-token")
        self.listeners = {}  # event_name -> [callback]

    def _configure_proxy_bypass(self):
        """配置代理绕过，防止本地 VPN 拦截 localhost 连接"""
        # 获取当前的 NO_PROXY 设置
        no_proxy = os.environ.get("NO_PROXY", "")
        no_proxy_list = no_proxy.split(",") if no_proxy else []

        # 确保 localhost 和 127.0.0.1 在列表中
        updates = []
        if "localhost" not in no_proxy_list:
            updates.append("localhost")
        if "127.0.0.1" not in no_proxy_list:
            updates.append("127.0.0.1")

        if updates:
            if no_proxy:
                os.environ["NO_PROXY"] = f"{no_proxy},{','.join(updates)}"
            else:
                os.environ["NO_PROXY"] = ",".join(updates)
            logger.info(f"已更新 NO_PROXY 配置: {os.environ['NO_PROXY']}")

    def set_token(self, token):
        self.token = token

    def on(self, event_name, callback):
        """注册事件监听器。
        事件: 'request', 'action:{name}', 'stream', 'connect', 'disconnect'
        """
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        self.listeners[event_name].append(callback)

    def emit(self, event_name, *args, **kwargs):
        """向监听器发送事件。"""
        if event_name in self.listeners:
            for callback in self.listeners[event_name]:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(*args, **kwargs))
                else:
                    try:
                        callback(*args, **kwargs)
                    except Exception as e:
                        logger.error(f"{event_name} 监听器错误: {e}")

    async def start(self):
        self.running = True
        # 在后台循环中运行，以避免连接立即失败时阻塞启动
        while self.running:
            try:
                logger.debug(f"正在连接到 Gateway {self.uri}...")
                async with websockets.connect(self.uri) as websocket:
                    self.websocket = websocket
                    logger.debug("已连接到 Gateway")
                    self.emit("connect")

                    await self.send_hello()
                    await self.send_test_broadcast()

                    # 启动心跳循环
                    self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())

                    # 监听消息
                    await self.listen()
            except Exception as e:
                logger.error(f"Gateway 连接错误: {e}")
                if self.heartbeat_task:
                    self.heartbeat_task.cancel()
                self.websocket = None
                await asyncio.sleep(3)  # 重连延迟

    def start_background(self):
        asyncio.create_task(self.start())

    async def stop(self):
        self.running = False
        if self.websocket:
            await self.websocket.close()
        if self.heartbeat_task:
            self.heartbeat_task.cancel()

    async def listen(self):
        try:
            async for message in self.websocket:
                if isinstance(message, bytes):
                    envelope = perolink_pb2.Envelope()
                    envelope.ParseFromString(message)
                    await self.handle_envelope(envelope)
        except websockets.ConnectionClosed:
            logger.warning("Gateway 连接已关闭")
            self.emit("disconnect")

    async def send_hello(self):
        envelope = perolink_pb2.Envelope()
        envelope.id = str(uuid.uuid4())
        envelope.source_id = self.device_id
        envelope.target_id = "master"
        envelope.timestamp = int(time.time() * 1000)

        envelope.hello.token = self.token
        envelope.hello.device_name = "PeroCore Backend"
        envelope.hello.client_version = "1.0.0"
        envelope.hello.platform = platform.system().lower()

        await self.send(envelope)

    async def send_test_broadcast(self):
        envelope = perolink_pb2.Envelope()
        envelope.id = str(uuid.uuid4())
        envelope.source_id = self.device_id
        envelope.target_id = "broadcast"
        envelope.timestamp = int(time.time() * 1000)
        envelope.trace_id = "TEST-BROADCAST"
        envelope.request.action_name = "ping"

        logger.debug(f"正在发送广播 Ping，来自 {self.device_id}")
        await self.send(envelope)

    async def broadcast_pet_state(self, state_dict: dict):
        """向所有客户端广播 PetState 更新。"""
        if not self.websocket or not self.running:
            return

        try:
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = self.device_id
            envelope.target_id = "broadcast"
            envelope.timestamp = int(time.time() * 1000)

            envelope.request.action_name = "state_update"

            # 将所有值转换为字符串以用于 protobuf map
            for k, v in state_dict.items():
                if v is not None:
                    envelope.request.params[k] = str(v)

            await self.send(envelope)
            logger.debug(f"广播 PetState 更新: {state_dict.get('mood')}")
        except Exception as e:
            logger.error(f"广播 PetState 失败: {e}")

    async def broadcast_text_response(self, content: str, target: str = "all"):
        """向前端客户端广播 LLM 文本响应。"""
        if not self.websocket or not self.running:
            return

        try:
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = self.device_id
            envelope.target_id = "broadcast"
            envelope.timestamp = int(time.time() * 1000)

            envelope.request.action_name = "text_response"
            envelope.request.params["content"] = content
            envelope.request.params["target"] = target

            # [Fix] 如果需要，也发送 'chat' 事件以兼容旧版
            # 但前端监听 'action:text_response'，所以这没问题。
            # 但是，如果我们想要显示气泡，必须确保内容不为空。

            await self.send(envelope)
            logger.debug(f"已广播文本响应: {content[:30]}...")
        except Exception as e:
            logger.error(f"广播文本响应失败: {e}")

    async def broadcast_error(
        self, message: str, title: str = "错误", error_type: str = "error"
    ):
        """向前端广播错误通知。"""
        if not self.websocket or not self.running:
            return

        try:
            envelope = perolink_pb2.Envelope()
            envelope.id = str(uuid.uuid4())
            envelope.source_id = self.device_id
            envelope.target_id = "broadcast"
            envelope.timestamp = int(time.time() * 1000)

            envelope.request.action_name = "system_error"
            # 前端 ipcAdapter 接收到的 payload 可能是整个 params 字典，或者经过 Main Process 处理后的内容
            # 这里我们尽量多传点信息
            envelope.request.params["payload"] = message  # 兼容前端 event.payload
            envelope.request.params["message"] = message
            envelope.request.params["title"] = title
            envelope.request.params["type"] = error_type

            await self.send(envelope)
            logger.debug(f"广播错误通知: {title} - {message}")
        except Exception as e:
            logger.error(f"广播错误失败: {e}")

    async def heartbeat_loop(self):
        seq = 0
        while self.running:
            try:
                await asyncio.sleep(5)
                seq += 1
                envelope = perolink_pb2.Envelope()
                envelope.id = str(uuid.uuid4())
                envelope.source_id = self.device_id
                envelope.target_id = "master"
                envelope.timestamp = int(time.time() * 1000)
                envelope.heartbeat.seq = seq

                await self.send(envelope)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳错误: {e}")
                break

    async def send(self, envelope):
        if self.websocket:
            data = envelope.SerializeToString()
            await self.websocket.send(data)

    async def handle_envelope(self, envelope):
        # logger.info(f"收到信封: {envelope.id} 来自 {envelope.source_id}")

        if envelope.HasField("request"):
            await self.handle_request(envelope)
        elif envelope.HasField("stream"):
            self.emit("stream", envelope)
        elif envelope.HasField("response"):
            self.emit("response", envelope)

    async def handle_request(self, envelope):
        req = envelope.request
        logger.debug(f"处理请求: {req.action_name} 参数={req.params}")

        # 发送通用请求事件
        self.emit("request", envelope)
        # 发送特定动作事件
        self.emit(f"action:{req.action_name}", envelope)

        # 基本诊断的默认处理程序
        resp_envelope = perolink_pb2.Envelope()
        resp_envelope.id = str(uuid.uuid4())
        resp_envelope.source_id = self.device_id
        resp_envelope.target_id = envelope.source_id  # 回复发送者
        resp_envelope.timestamp = int(time.time() * 1000)
        resp_envelope.trace_id = envelope.trace_id

        if req.action_name == "ping":
            resp_envelope.response.request_id = envelope.id
            resp_envelope.response.status = 0
            resp_envelope.response.data = "Pong from Python!"
            await self.send(resp_envelope)
        elif req.action_name == "echo":
            resp_envelope.response.request_id = envelope.id
            resp_envelope.response.status = 0
            resp_envelope.response.data = f"Echo: {req.params.get('text', '')}"
            await self.send(resp_envelope)
        # 移除了硬编码的 'chat' 处理程序，通过事件监听器委托给 RealtimeSessionManager


gateway_client = GatewayClient()
