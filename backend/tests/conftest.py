import os
import sys
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# 将 backend 目录添加到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import get_session
from routers.agent_router import router as agent_router
from routers.config_router import router as config_router
from routers.memory_router import history_router, legacy_memories_router
from routers.memory_router import router as memory_router
from routers.scheduler_router import router as scheduler_router
from routers.task_control_router import router as task_control_router


@pytest.fixture(scope="session")
def app():
    """创建用于测试的 FastAPI 应用"""
    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(memory_router)
    app.include_router(history_router)
    app.include_router(legacy_memories_router)
    app.include_router(task_control_router)
    app.include_router(config_router)
    app.include_router(scheduler_router)
    return app


@pytest_asyncio.fixture
async def mock_session():
    """模拟数据库会话"""
    session = AsyncMock()
    # 确保 session.exec() 返回 MagicMock (同步结果对象)
    # 以便 .all() 和 .first() 是同步方法
    session.exec.return_value = MagicMock()
    # session.add 是同步的
    session.add = MagicMock()
    return session


@pytest_asyncio.fixture
async def client(app, mock_session) -> AsyncGenerator[AsyncClient, None]:
    """用于测试 API 端点的异步客户端"""

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
