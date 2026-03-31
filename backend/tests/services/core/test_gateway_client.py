from unittest.mock import AsyncMock, patch

import pytest

from services.core.gateway_client import GatewayClient


class TestGatewayClient:
    @pytest.fixture
    def gateway_client(self):
        # GatewayClient 已重构为嵌入式 Hub 模式，不再接受 uri 参数
        return GatewayClient()

    @pytest.mark.asyncio
    async def test_start_sets_running(self, gateway_client):
        """测试 start() 正确设置 running 标志"""
        assert gateway_client.running is False
        await gateway_client.start()
        assert gateway_client.running is True

    @pytest.mark.asyncio
    async def test_stop_clears_running(self, gateway_client):
        """测试 stop() 正确清除 running 标志"""
        await gateway_client.start()
        assert gateway_client.running is True
        await gateway_client.stop()
        assert gateway_client.running is False

    def test_start_background(self, gateway_client):
        """测试后台启动设置 running"""
        gateway_client.start_background()
        assert gateway_client.running is True

    @pytest.mark.asyncio
    async def test_broadcast_text_response(self, gateway_client):
        """测试广播文本响应委托给 gateway_hub"""
        with patch("services.core.gateway_client.gateway_hub") as mock_hub:
            mock_hub.broadcast_text_response = AsyncMock()
            await gateway_client.broadcast_text_response("hello world")
            mock_hub.broadcast_text_response.assert_called_once_with(
                "hello world", "all"
            )

    @pytest.mark.asyncio
    async def test_broadcast_error(self, gateway_client):
        """测试广播错误委托给 gateway_hub"""
        with patch("services.core.gateway_client.gateway_hub") as mock_hub:
            mock_hub.broadcast_error = AsyncMock()
            await gateway_client.broadcast_error("something went wrong")
            mock_hub.broadcast_error.assert_called_once_with(
                "something went wrong", "错误", "error"
            )
