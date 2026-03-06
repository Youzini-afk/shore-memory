import sys
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

# 适配不同的运行环境
try:
    from models import AIModelConfig, Config, ConversationLog
except ImportError:
    try:
        from backend.models import AIModelConfig, Config, ConversationLog
    except ImportError:
        raise

from services.memory.scorer_service import ScorerService

# 模拟依赖项
mock_mdp = MagicMock()
mock_memory_service = MagicMock()

modules_to_patch = {
    "services.mdp.manager": mock_mdp,
    "services.memory.memory_service": mock_memory_service,
}


class TestScorerService:
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
    def scorer(self, session):
        with patch.dict(sys.modules, modules_to_patch):
            return ScorerService(session)

    @pytest.mark.asyncio
    async def test_smart_clean_text(self, scorer):
        """测试文本清洗逻辑"""
        # 1. 移除系统注入标签
        text1 = "Start <FILE_RESULTS>data</FILE_RESULTS> End"
        assert (
            await scorer._smart_clean_text(text1)
            == "Start [FILE_RESULTS Data Omitted] End"
        )

        # 2. 移除 Thinking 块
        text2 = "Hello 【Thinking: hmm】 World"
        assert await scorer._smart_clean_text(text2) == "Hello  World"

        text3 = "Hello [Monologue: hmm] World"
        assert await scorer._smart_clean_text(text3) == "Hello  World"

        # 3. 保留 NIT 协议
        text4 = "[[[NIT_CALL]]] action [[[NIT_END]]]"
        assert (
            await scorer._smart_clean_text(text4)
            == "[[[NIT_CALL]]] action [[[NIT_END]]]"
        )

    @pytest.mark.asyncio
    async def test_get_scorer_config_secretary(self, session, scorer):
        """测试选取 'secretary' 模型配置"""
        # 设置数据
        config = AIModelConfig(
            name="秘书",
            model_id="gpt-4-turbo",
            provider_type="custom",
            api_key="sk-test",
            base_url="https://api.openai.com",
        )
        session.add(config)
        await session.commit()

        config = await scorer._get_scorer_config()
        assert config["model"] == "gpt-4-turbo"
        assert config["api_key"] == "sk-test"

    @pytest.mark.asyncio
    async def test_get_scorer_config_fallback_global(self, session, scorer):
        """测试无秘书模型时回退到全局配置"""
        # 设置全局配置
        session.add(Config(key="global_llm_api_key", value="sk-global"))
        session.add(Config(key="global_llm_api_base", value="https://global.api"))
        await session.commit()

        config = await scorer._get_scorer_config()
        assert config["model"] == "gpt-4o-mini"  # 默认回退
        assert config["api_key"] == "sk-global"
        assert config["api_base"] == "https://global.api"

    @pytest.mark.asyncio
    async def test_update_log_status(self, session, scorer):
        """测试更新对话日志状态"""
        # 设置日志
        log = ConversationLog(
            session_id="s1",
            role="user",
            content="hi",
            pair_id="p1",
            analysis_status="pending",
            source="test",
        )
        session.add(log)
        await session.commit()

        await scorer._update_log_status("p1", "completed")

        updated_log = (
            await session.exec(
                select(ConversationLog).where(ConversationLog.pair_id == "p1")
            )
        ).first()
        assert updated_log.analysis_status == "completed"

    @pytest.mark.asyncio
    async def test_update_log_status_with_error(self, session, scorer):
        """测试更新带错误的日志"""
        log = ConversationLog(
            session_id="s1",
            role="user",
            content="hi",
            pair_id="p2",
            analysis_status="pending",
            source="test",
        )
        session.add(log)
        await session.commit()

        await scorer._update_log_status("p2", "failed", error="Something wrong")

        updated_log = (
            await session.exec(
                select(ConversationLog).where(ConversationLog.pair_id == "p2")
            )
        ).first()
        assert updated_log.analysis_status == "failed"
        assert "Something wrong" in updated_log.last_error
