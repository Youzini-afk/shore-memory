import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# 模拟依赖项
mock_llm_service = MagicMock()
mock_mdp = MagicMock()

modules_to_patch = {
    "services.core.llm_service": mock_llm_service,
    "services.mdp.manager": mock_mdp,
}


# 适配不同的运行环境
try:
    from models import AIModelConfig, Config, ConversationLog
except ImportError:
    try:
        from backend.models import AIModelConfig, Config, ConversationLog
    except ImportError:
        raise

with patch.dict(sys.modules, modules_to_patch):
    from services.memory.reflection_service import ReflectionService


class TestReflectionService:
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

    @pytest.fixture
    def service(self, session):
        return ReflectionService(session)

    @pytest.mark.asyncio
    async def test_get_reflection_config_default(self, session, service):
        """测试默认反思配置"""
        # 设置最小配置
        session.add(Config(key="global_llm_api_key", value="sk-global"))
        await session.commit()

        config = await service._get_reflection_config()
        assert config["model"] == "gpt-4o"  # 默认回退
        assert config["api_key"] == "sk-global"

    @pytest.mark.asyncio
    async def test_get_reflection_config_explicit(self, session, service):
        """测试显式反思配置"""
        session.add(Config(key="reflection_model_id", value="1"))
        session.add(
            AIModelConfig(
                id=1,
                name="Reflection",
                model_id="gpt-4-turbo",
                provider_type="custom",
                api_key="sk-reflection",
            )
        )
        await session.commit()

        config = await service._get_reflection_config()
        assert config["model"] == "gpt-4-turbo"
        assert config["api_key"] == "sk-reflection"

    @pytest.mark.asyncio
    async def test_backfill_failed_scorer_tasks(self, session, service):
        """测试回填失败的任务"""
        # 1. 设置失败日志
        # 我们需要确保 retry_count < 3
        log1 = ConversationLog(
            session_id="s1",
            role="user",
            content="hi",
            pair_id="p1",
            analysis_status="failed",
            source="test",
            retry_count=0,
        )
        session.add(log1)
        await session.commit()

        # 为该方法模拟依赖项
        mock_engine = MagicMock()
        mock_scorer_cls = MagicMock()
        mock_scorer_instance = MagicMock()
        mock_scorer_cls.return_value = mock_scorer_instance
        mock_scorer_instance.retry_interaction = AsyncMock()

        # 创建模拟数据库模块
        mock_database = MagicMock()
        mock_database.engine = mock_engine

        # 为 'database' 和 'services.memory.scorer_service' 打补丁 sys.modules
        # 并为 sessionmaker 打补丁 (来自 sqlalchemy.orm)

        # 我们需要小心不要破坏其他 sqlalchemy 用法。
        # 但由于我们在测试方法内部，我们可以使用 patch。

        mock_session_factory = MagicMock()
        mock_local_session = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_local_session

        with (
            patch.dict(
                sys.modules,
                {
                    "database": mock_database,
                    "services.memory.scorer_service": MagicMock(
                        ScorerService=mock_scorer_cls
                    ),
                },
            ),
            patch("sqlalchemy.orm.sessionmaker", return_value=mock_session_factory),
        ):
            await service.backfill_failed_scorer_tasks()

        # 验证
        mock_scorer_instance.retry_interaction.assert_called()
        call_args = mock_scorer_instance.retry_interaction.call_args
        assert call_args[0][0] == log1.id
