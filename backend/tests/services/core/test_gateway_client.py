import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from peroproto import perolink_pb2
from services.core.gateway_client import GatewayClient


class TestGatewayClient:
    @pytest.fixture
    def gateway_client(self):
        return GatewayClient(uri="ws://test-gateway")

    @pytest.mark.asyncio
    async def test_connect_and_hello(self, gateway_client):
        """测试连接建立和握手消息发送"""
        mock_ws = AsyncMock()

        # 模拟 websockets.connect 上下文管理器
        with patch("websockets.connect", new_callable=MagicMock) as mock_connect:
            mock_connect.return_value.__aenter__.return_value = mock_ws

            # 模拟 send 以验证握手消息
            mock_ws.send = AsyncMock()

            # 模拟 listen 以防止无限循环或立即退出
            # 我们让 listen 等待一会儿然后停止运行
            async def mock_listen():
                await asyncio.sleep(0.1)
                gateway_client.running = False

            gateway_client.listen = mock_listen

            # 运行 start()
            gateway_client.running = True
            await gateway_client.start()

            # 验证握手消息已发送
            assert mock_ws.send.called
            # 获取第一个调用参数 (发送的字节)
            sent_bytes = mock_ws.send.call_args_list[0][0][0]
            envelope = perolink_pb2.Envelope()
            envelope.ParseFromString(sent_bytes)

            assert envelope.target_id == "master"
            assert envelope.hello.device_name == "萌动链接：PeroperoChat！ 后端服务"
            assert envelope.hello.token == gateway_client.token

    @pytest.mark.asyncio
    async def test_event_emitter(self, gateway_client):
        """测试事件订阅和分发"""
        received_data = []

        async def async_handler(data):
            received_data.append(f"async:{data}")

        def sync_handler(data):
            received_data.append(f"sync:{data}")

        gateway_client.on("test_event", async_handler)
        gateway_client.on("test_event", sync_handler)

        gateway_client.emit("test_event", "hello")

        # 允许异步任务运行
        await asyncio.sleep(0.01)

        assert "async:hello" in received_data
        assert "sync:hello" in received_data

    @pytest.mark.asyncio
    async def test_broadcast_text_response(self, gateway_client):
        """测试广播文本响应"""
        gateway_client.websocket = AsyncMock()
        gateway_client.running = True

        await gateway_client.broadcast_text_response("hello world")

        assert gateway_client.websocket.send.called
        sent_bytes = gateway_client.websocket.send.call_args[0][0]
        envelope = perolink_pb2.Envelope()
        envelope.ParseFromString(sent_bytes)

        assert envelope.target_id == "broadcast"
        assert envelope.request.action_name == "text_response"
        assert envelope.request.params["content"] == "hello world"

    @pytest.mark.asyncio
    async def test_broadcast_error(self, gateway_client):
        """测试广播错误"""
        gateway_client.websocket = AsyncMock()
        gateway_client.running = True

        await gateway_client.broadcast_error("something went wrong")

        assert gateway_client.websocket.send.called
        sent_bytes = gateway_client.websocket.send.call_args[0][0]
        envelope = perolink_pb2.Envelope()
        envelope.ParseFromString(sent_bytes)

        assert envelope.request.action_name == "system_error"
        assert envelope.request.params["type"] == "error"
        assert envelope.request.params["message"] == "something went wrong"
