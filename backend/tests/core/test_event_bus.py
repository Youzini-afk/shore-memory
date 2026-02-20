from unittest.mock import AsyncMock, Mock

import pytest

from core.event_bus import EventBus


class TestEventBus:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """在每个测试前后重置 EventBus 监听器"""
        EventBus._listeners.clear()
        yield
        EventBus._listeners.clear()

    @pytest.mark.asyncio
    async def test_subscribe_and_publish_sync(self):
        """测试同步处理程序的订阅和发布"""
        mock_handler = Mock(return_value="result")
        mock_handler.__name__ = "mock_handler"  # 修复: Mock 对象默认没有 __name__
        EventBus.subscribe("test.event", mock_handler)

        results = await EventBus.publish("test.event", "arg1", key="value")

        mock_handler.assert_called_once_with("arg1", key="value")
        # 注意: 如果处理程序返回值，EventBus 实现返回结果列表
        # 实现细节: 如果 res 不为 None，则 results.append(res)
        # 但是在显示的当前实现中 publish 返回 None？
        # 等等，代码说：return results。让我们验证一下。
        # 第 73 行: return results
        assert results == ["result"]

    @pytest.mark.asyncio
    async def test_subscribe_and_publish_async(self):
        """测试异步处理程序的订阅和发布"""
        mock_handler = AsyncMock(return_value="async_result")
        mock_handler.__name__ = "mock_async_handler"  # 修复: Mock 对象默认没有 __name__
        EventBus.subscribe("test.async", mock_handler)

        results = await EventBus.publish("test.async", 123)

        mock_handler.assert_awaited_once_with(123)
        assert results == ["async_result"]

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """测试取消订阅"""
        mock_handler = Mock()
        mock_handler.__name__ = "mock_handler"
        EventBus.subscribe("test.unsub", mock_handler)
        EventBus.unsubscribe("test.unsub", mock_handler)

        await EventBus.publish("test.unsub")

        mock_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        """测试同一事件的多个处理程序"""
        handler1 = Mock(return_value=1)
        handler1.__name__ = "handler1"
        handler2 = Mock(return_value=2)
        handler2.__name__ = "handler2"

        EventBus.subscribe("test.multi", handler1)
        EventBus.subscribe("test.multi", handler2)

        results = await EventBus.publish("test.multi")

        assert handler1.call_count == 1
        assert handler2.call_count == 1
        assert sorted(results) == [
            1,
            2,
        ]  # 顺序取决于实现，通常是插入顺序
