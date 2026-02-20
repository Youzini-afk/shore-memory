from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_all_configs(client, mock_session):
    # 模拟数据库返回配置
    mock_config = MagicMock()
    mock_config.key = "test_key"
    mock_config.value = "test_value"

    mock_session.exec.return_value.all.return_value = [mock_config]

    response = await client.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {"test_key": "test_value"}


@pytest.mark.asyncio
async def test_update_configs_success(client, mock_session):
    # 模拟检查工作模式 (当前 session_id 不以 work_ 开头)
    mock_session.exec.return_value.first.return_value = None

    # 模拟获取现有配置
    mock_session.get.return_value = None

    payload = {"test_key": "new_value"}
    response = await client.post("/api/config", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


@pytest.mark.asyncio
async def test_update_configs_blocked(client, mock_session):
    # 模拟工作模式已启用
    mock_config = MagicMock()
    mock_config.value = "work_session_1"
    mock_session.exec.return_value.first.return_value = mock_config

    # 尝试启用轻量模式
    payload = {"lightweight_mode": "true"}
    response = await client.post("/api/config", json=payload)
    assert response.status_code == 403
    assert "无法启用" in response.json()["detail"]


@pytest.mark.asyncio
async def test_lightweight_mode(client):
    with patch("routers.config_router.get_config_manager") as mock_get_cm:
        cm = mock_get_cm.return_value
        cm.get.return_value = True

        # 测试 GET
        response = await client.get("/api/config/lightweight_mode")
        assert response.status_code == 200
        assert response.json() == {"enabled": True}

        # 测试 POST
        cm.set = AsyncMock()
        response = await client.post(
            "/api/config/lightweight_mode", json={"enabled": False}
        )
        assert response.status_code == 200
        cm.set.assert_called_with("lightweight_mode", False)


@pytest.mark.asyncio
async def test_memory_config(client):
    with patch("routers.config_router.get_config_manager") as mock_get_cm:
        cm = mock_get_cm.return_value
        cm.get_json.return_value = {"key": "value"}

        # 测试 GET
        response = await client.get("/api/config/memory")
        assert response.status_code == 200
        assert response.json() == {"key": "value"}

        # 测试 POST
        cm.set = AsyncMock()
        payload = {"new_key": "new_value"}
        response = await client.post("/api/config/memory", json=payload)
        assert response.status_code == 200
        cm.set.assert_called_once()
