import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from services.memory.memory_service import MemoryService

class TestMemoryService:
    @pytest_asyncio.fixture(name="session")
    async def session_fixture(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            yield session

    @pytest.mark.asyncio
    @patch("services.core.embedding_service.embedding_service.encode_one", new_callable=AsyncMock)
    @patch("core.event_bus.EventBus.publish", new_callable=AsyncMock)
    async def test_save_memory_success(self, mock_publish, mock_encode, session):
        """测试成功保存记忆"""
        mock_encode.return_value = [0.1] * 384
        
        memory = await MemoryService.save_memory(
            session, content="Test memory", tags="test", agent_id="agent1"
        )

        assert memory is not None
        assert memory.content == "Test memory"
        assert memory.agent_id == "agent1"
        assert memory.embedding_json is not None

        # 验证 EventBus 调用 (至少一次 pre-hook)
        assert mock_publish.call_count >= 1
        # 检查首次调用参数
        args, _ = mock_publish.call_args_list[0]
        assert args[0] == "memory.save.pre"
        assert args[1]["content"] == "Test memory"

    @pytest.mark.asyncio
    @patch("services.core.embedding_service.embedding_service.encode_one", new_callable=AsyncMock)
    @patch("core.event_bus.EventBus.publish", new_callable=AsyncMock)
    async def test_save_memory_cancelled(self, mock_publish, mock_encode, session):
        """测试记忆保存被 hook 取消"""
        
        async def cancel_hook(event, ctx):
            ctx["cancel"] = True

        mock_publish.side_effect = cancel_hook

        memory = await MemoryService.save_memory(
            session, content="Cancelled memory"
        )

        assert memory is None

        # 验证数据库为空
        memories = (
            await session.exec(SQLModel.metadata.tables["memory"].select())
        ).all()
        assert len(memories) == 0

    @pytest.mark.asyncio
    @patch("services.core.embedding_service.embedding_service.encode_one", new_callable=AsyncMock)
    @patch("core.event_bus.EventBus.publish", new_callable=AsyncMock)
    async def test_memory_chaining(self, mock_publish, mock_encode, session):
        """测试新记忆链接到前一个记忆"""
        mock_encode.return_value = [0.1] * 384
        
        # 1. 保存第一个记忆
        mem1 = await MemoryService.save_memory(session, "First", agent_id="agent1")
        assert mem1.prev_id is None

        # 2. 保存第二个记忆
        mem2 = await MemoryService.save_memory(session, "Second", agent_id="agent1")
        assert mem2.prev_id == mem1.id

        # 3. 为不同的 Agent 保存记忆 (不应链接到 agent1)
        mem3 = await MemoryService.save_memory(session, "Third", agent_id="agent2")
        assert mem3.prev_id is None

        # 4. 为 agent1 保存第四个记忆 (应链接到 mem2)
        mem4 = await MemoryService.save_memory(session, "Fourth", agent_id="agent1")
        assert mem4.prev_id == mem2.id
