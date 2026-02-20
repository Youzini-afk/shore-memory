from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_import_story(client, mock_session):
    # 模拟 MemoryImporter
    with patch("routers.memory_router.MemoryImporter") as MockImporter:
        importer = MockImporter.return_value

        # import_story 是异步的
        async def async_import(*args, **kwargs):
            return {"success": True, "message": "Imported"}

        importer.import_story.side_effect = async_import

        payload = {"story": "Once upon a time", "agent_id": "pero"}
        response = await client.post("/api/memories/import_story", json=payload)
        assert response.status_code == 200
        assert response.json() == {"success": True, "message": "Imported"}
        MockImporter.assert_called_with(mock_session)


@pytest.mark.asyncio
async def test_run_memory_secretary(client, mock_session):
    with patch("routers.memory_router.ReflectionService") as MockService:
        service = MockService.return_value

        async def async_run(*args, **kwargs):
            return {"status": "done"}

        service.run_maintenance.side_effect = async_run

        response = await client.post("/api/memories/secretary/run")
        assert response.status_code == 200
        assert response.json() == {"status": "done"}
        MockService.assert_called_with(mock_session)


@pytest.mark.asyncio
async def test_delete_memory_by_timestamp(client, mock_session):
    with patch("routers.memory_router.MemoryService") as MockService:
        service = MockService.return_value
        service.delete_by_msg_timestamp = AsyncMock()

        ts = "1234567890"
        response = await client.delete(f"/api/memories/by_timestamp/{ts}")
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
        service.delete_by_msg_timestamp.assert_called_with(mock_session, ts)
