from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from models import ScheduledTask


@pytest.mark.asyncio
async def test_sync_reminders(client):
    with patch("routers.scheduler_router.scheduler_service") as mock_service:
        mock_service.add_reminder.return_value = "job_123"

        # 未来时间
        future_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")

        payload = {
            "source": "test",
            "reminders": [{"content": "drink water", "time": future_time}],
        }

        response = await client.post("/sync", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "completed"
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "success"
        assert result["results"][0]["job_id"] == "job_123"


@pytest.mark.asyncio
async def test_get_tasks(client, mock_session):
    # 使用真实的 ScheduledTask 对象以满足 Pydantic 验证
    task = ScheduledTask(
        id=1,
        type="reminder",
        time="2023-01-01 12:00:00",
        content="task1",
        is_triggered=False,
        agent_id="pero",
        created_at=datetime.now(),
    )

    # mock_session.exec 返回 MagicMock (在 conftest 中配置)
    # .all() 返回列表
    mock_session.exec.return_value.all.return_value = [task]

    response = await client.get("/tasks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["content"] == "task1"


@pytest.mark.asyncio
async def test_delete_task(client, mock_session):
    # 模拟 session.get 的返回值
    mock_task = MagicMock()
    mock_session.get.return_value = mock_task

    response = await client.delete("/tasks/1")
    assert response.status_code == 200
    assert response.json() == {"status": "success"}
    mock_session.delete.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_check_tasks(client, mock_session):
    # 模拟过期任务
    past_time = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")

    task = ScheduledTask(
        id=1,
        type="reminder",
        time=past_time,
        content="test reminder",
        is_triggered=False,
        agent_id="pero",
        created_at=datetime.now(),
    )

    mock_session.exec.return_value.all.return_value = [task]

    response = await client.post("/check")
    assert response.status_code == 200
    result = response.json()
    assert "prompts" in result
    assert len(result["prompts"]) > 0
    assert "test reminder" in result["prompts"][0]

    # 检查任务是否已更新
    assert task.is_triggered is True
    mock_session.add.assert_called()
    mock_session.commit.assert_called()
