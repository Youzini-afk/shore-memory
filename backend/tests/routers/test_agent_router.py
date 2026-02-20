from unittest.mock import patch

import pytest

from services.agent.agent_manager import AgentProfile

# 示例数据
SAMPLE_AGENT_PROFILE = AgentProfile(
    id="test_agent", name="Test Agent", description="A test agent"
)

SAMPLE_AGENT_DICT = {
    "id": "test_agent",
    "name": "Test Agent",
    "description": "A test agent",
    "is_active": True,
    "is_enabled": True,
}


@pytest.fixture
def mock_agent_manager():
    # Patch 在 routers.agent_router 中导入的位置
    with patch("routers.agent_router.get_agent_manager") as mock:
        manager = mock.return_value
        manager.list_agents.return_value = [SAMPLE_AGENT_DICT]
        manager.get_enabled_agents.return_value = ["test_agent"]
        manager.get_active_agent.return_value = SAMPLE_AGENT_PROFILE
        manager.set_active_agent.return_value = True
        yield manager


@pytest.mark.asyncio
async def test_list_agents(client, mock_agent_manager):
    response = await client.get("/api/agents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "test_agent"
    assert mock_agent_manager.list_agents.called


@pytest.mark.asyncio
async def test_get_enabled_agents(client, mock_agent_manager):
    response = await client.get("/api/agents/enabled")
    assert response.status_code == 200
    assert response.json() == ["test_agent"]
    assert mock_agent_manager.get_enabled_agents.called


@pytest.mark.asyncio
async def test_set_enabled_agents(client, mock_agent_manager):
    payload = {"agent_ids": ["agent1", "agent2"]}
    response = await client.post("/api/agents/enabled", json=payload)
    assert response.status_code == 200
    mock_agent_manager.set_enabled_agents.assert_called_with(["agent1", "agent2"])


@pytest.mark.asyncio
async def test_get_active_agent(client, mock_agent_manager):
    response = await client.get("/api/agents/active")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test_agent"


@pytest.mark.asyncio
async def test_set_active_agent_success(client, mock_agent_manager):
    payload = {"agent_id": "test_agent"}
    response = await client.post("/api/agents/active", json=payload)
    assert response.status_code == 200
    mock_agent_manager.set_active_agent.assert_called_with("test_agent")


@pytest.mark.asyncio
async def test_set_active_agent_fail(client, mock_agent_manager):
    mock_agent_manager.set_active_agent.return_value = False
    payload = {"agent_id": "invalid_agent"}
    response = await client.post("/api/agents/active", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_preview_prompt(client, mock_session):
    # 模拟 AgentService
    with patch("routers.agent_router.AgentService") as MockService:
        service_instance = MockService.return_value

        async def async_preview(*args, **kwargs):
            return "preview content"

        service_instance.preview_prompt.side_effect = async_preview

        payload = {"session_id": "sess_1", "source": "test", "log_id": 123}
        response = await client.post("/api/agents/preview_prompt", json=payload)
        assert response.status_code == 200
        assert response.json() == "preview content"
