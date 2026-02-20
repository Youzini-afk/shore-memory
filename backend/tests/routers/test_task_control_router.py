from unittest.mock import patch

import pytest


@pytest.fixture
def mock_task_manager():
    with patch("routers.task_control_router.task_manager") as mock:
        yield mock


@pytest.mark.asyncio
async def test_pause_task_success(client, mock_task_manager):
    mock_task_manager.pause.return_value = True
    response = await client.post("/api/task/sess_1/pause")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "任务已暂停"}
    mock_task_manager.pause.assert_called_with("sess_1")


@pytest.mark.asyncio
async def test_pause_task_fail(client, mock_task_manager):
    mock_task_manager.pause.return_value = False
    response = await client.post("/api/task/sess_1/pause")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resume_task_success(client, mock_task_manager):
    mock_task_manager.resume.return_value = True
    response = await client.post("/api/task/sess_1/resume")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "任务已恢复"}
    mock_task_manager.resume.assert_called_with("sess_1")


@pytest.mark.asyncio
async def test_resume_task_fail(client, mock_task_manager):
    mock_task_manager.resume.return_value = False
    response = await client.post("/api/task/sess_1/resume")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_inject_instruction_success(client, mock_task_manager):
    mock_task_manager.inject_instruction.return_value = True
    payload = {"instruction": "stop"}
    response = await client.post("/api/task/sess_1/inject", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "success", "message": "指令已注入"}
    mock_task_manager.inject_instruction.assert_called_with("sess_1", "stop")


@pytest.mark.asyncio
async def test_inject_instruction_missing_payload(client, mock_task_manager):
    payload = {}
    response = await client.post("/api/task/sess_1/inject", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_inject_instruction_fail(client, mock_task_manager):
    mock_task_manager.inject_instruction.return_value = False
    payload = {"instruction": "stop"}
    response = await client.post("/api/task/sess_1/inject", json=payload)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_status_found(client, mock_task_manager):
    mock_task_manager.get_status.return_value = "running"
    response = await client.get("/api/task/sess_1/status")
    assert response.status_code == 200
    assert response.json() == {"status": "running"}


@pytest.mark.asyncio
async def test_get_task_status_not_found(client, mock_task_manager):
    mock_task_manager.get_status.return_value = None
    response = await client.get("/api/task/sess_1/status")
    assert response.status_code == 200
    assert response.json() == {"status": "idle"}
