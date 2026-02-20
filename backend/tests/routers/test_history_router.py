from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_chat_history(client, mock_session):
    with patch("routers.memory_router.MemoryService") as MockService:
        service = MockService.return_value

        # 模拟返回的日志
        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.role = "user"
        mock_log.content = "hello"
        mock_log.raw_content = "hello"
        mock_log.timestamp = 123
        mock_log.metadata_json = "{}"
        mock_log.sentiment = None
        mock_log.importance = None
        mock_log.pair_id = None

        async def async_query(*args, **kwargs):
            return [mock_log]

        service.query_logs.side_effect = async_query

        response = await client.get("/api/history/chat/sess_1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["content"] == "hello"


@pytest.mark.asyncio
async def test_retry_log_analysis(client, mock_session):
    # 此端点添加后台任务
    # 我们可以 patch BackgroundTasks 或者让它运行（但需要 session）
    # 端点调用 session.get(ConversationLog, log_id)

    # 模拟数据库获取
    mock_log = MagicMock()
    mock_log.id = 1
    mock_session.get.return_value = mock_log

    response = await client.post("/api/history/1/retry_analysis")
    assert response.status_code == 200
    assert response.json() == {"status": "queued", "message": "分析重试已在后台启动"}


@pytest.mark.asyncio
async def test_delete_chat_log(client, mock_session):
    with (
        patch("routers.memory_router.MemoryService") as MockService,
        patch("routers.memory_router.gateway_client") as mock_gateway,
    ):
        service = MockService.return_value
        service.delete_log = AsyncMock()
        mock_gateway.send = AsyncMock()

        response = await client.delete("/api/history/1")
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        service.delete_log.assert_called_once()
        mock_gateway.send.assert_called_once()


@pytest.mark.asyncio
async def test_update_chat_log(client, mock_session):
    with patch("routers.memory_router.gateway_client") as mock_gateway:
        mock_gateway.send = AsyncMock()

        # 模拟数据库获取
        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.content = "old content"
        mock_session.get.return_value = mock_log

        payload = {"content": "new content"}
        response = await client.patch("/api/history/1", json=payload)
        assert response.status_code == 200
        assert mock_log.content == "new content"
        mock_gateway.send.assert_called_once()
