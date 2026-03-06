import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# 适配不同的运行环境
try:
    from models import Config, ConversationLog
except ImportError:
    try:
        from backend.models import Config, ConversationLog
    except ImportError:
        # 如果都失败，可能是在 tests 目录下运行且未将 backend 加入 path
        # 这里我们可以 mock 它们，或者报错
        raise

from services.core.session_service import (
    _CURRENT_SESSION_CONTEXT,
    enter_work_mode,
    exit_work_mode,
    set_current_session_context,
)

# Mock 依赖模块
mock_config_manager_mod = MagicMock()
mock_agent_manager_mod = MagicMock()
mock_nit_manager_mod = MagicMock()
mock_scorer_service_mod = MagicMock()

# 设置默认模拟
mock_config_mgr = MagicMock()
mock_config_manager_mod.get_config_manager.return_value = mock_config_mgr
mock_config_mgr.get.side_effect = lambda k, d=None: d  # 返回默认值

mock_agent_mgr = MagicMock()
mock_agent_manager_mod.get_agent_manager.return_value = mock_agent_mgr
mock_agent_mgr.active_agent_id = "test_agent"

mock_scorer = AsyncMock()
mock_scorer_service_mod.ScorerService.return_value = mock_scorer
mock_scorer.generate_work_log_summary.return_value = "Work summary"

modules_to_patch = {
    "core.config_manager": mock_config_manager_mod,
    "services.agent.agent_manager": mock_agent_manager_mod,
    "core.nit_manager": mock_nit_manager_mod,
    "services.memory.scorer_service": mock_scorer_service_mod,
}


class TestSessionService:
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

    @pytest_asyncio.fixture(autouse=True)
    async def setup_context(self, session):
        set_current_session_context(session, "test_agent")
        # 重置模拟
        mock_config_mgr.get.side_effect = lambda k, d=None: d
        mock_agent_mgr.active_agent_id = "test_agent"
        yield
        _CURRENT_SESSION_CONTEXT.clear()

    @pytest.mark.asyncio
    async def test_enter_work_mode_success(self, session):
        """测试成功进入工作模式"""
        with patch.dict(sys.modules, modules_to_patch):
            result = await enter_work_mode("Test Task")

        assert "已进入工作模式" in result

        # 验证 Config 更新
        session_config = (
            await session.exec(
                select(Config).where(Config.key == "current_session_id_test_agent")
            )
        ).first()
        task_config = (
            await session.exec(
                select(Config).where(Config.key == "work_mode_task_test_agent")
            )
        ).first()

        assert session_config is not None
        assert session_config.value.startswith("work_test_agent_")
        assert task_config is not None
        assert task_config.value == "Test Task"

    @pytest.mark.asyncio
    async def test_enter_work_mode_conflict(self, session):
        """测试模式冲突阻止进入工作模式"""
        # 模拟启用轻量模式
        mock_config_mgr.get.side_effect = lambda k, d=None: (
            True if k == "lightweight_mode" else d
        )

        with patch.dict(sys.modules, modules_to_patch):
            result = await enter_work_mode("Test Task")

        assert "无法进入工作模式" in result
        assert "轻量模式" in result

        # 验证没有 Config 更新
        session_config = (
            await session.exec(
                select(Config).where(Config.key == "current_session_id_test_agent")
            )
        ).first()
        assert session_config is None

    @pytest.mark.asyncio
    async def test_exit_work_mode_success(self, session):
        """测试退出工作模式并保存总结"""
        # 1. 设置工作模式状态
        work_session_id = "work_test_agent_12345"
        session.add(Config(key="current_session_id_test_agent", value=work_session_id))
        session.add(Config(key="work_mode_task_test_agent", value="Test Task"))

        # 2. 添加一些日志
        session.add(
            ConversationLog(
                session_id=work_session_id,
                role="user",
                content="do this",
                timestamp=datetime.now(),
                source="user",
            )
        )
        session.add(
            ConversationLog(
                session_id=work_session_id,
                role="assistant",
                content="done",
                timestamp=datetime.now(),
                source="ai",
            )
        )
        await session.commit()

        # 3. 模拟退出工作模式
        with patch.dict(sys.modules, modules_to_patch):
            result = await exit_work_mode()

        assert "已退出工作模式" in result
        assert "Test Task" in result or "已恢复" in result

        # 验证已调用总结生成
        mock_scorer.generate_work_log_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_exit_work_mode_not_in_work(self, session):
        """测试非工作模式下退出"""
        # 正常会话
        session.add(Config(key="current_session_id_test_agent", value="normal_session"))
        await session.commit()

        with patch.dict(sys.modules, modules_to_patch):
            result = await exit_work_mode()

        assert "当前不在工作模式" in result
