from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# 适配不同的运行环境
try:
    from models import AIModelConfig, Config
except ImportError:
    try:
        from backend.models import AIModelConfig, Config
    except ImportError:
        raise

from services.agent.agent_service import AgentService


class TestAgentService:
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
    def agent_service(self, session):
        # Patch services.agent.agent_service 命名空间中的依赖项
        with (
            patch("services.agent.agent_service.ComponentContainer") as MockContainer,
            patch("services.agent.agent_service.ScorerService"),
            patch("services.agent.agent_service.task_manager"),
            patch("services.agent.agent_service.get_nit_manager"),
            patch("services.agent.agent_manager.get_agent_manager") as mock_get_manager,
            patch("services.agent.agent_service.get_active_windows", return_value=[]),
        ):
            # 设置 ComponentContainer 模拟
            mock_container = MockContainer
            mock_container.get.return_value = MagicMock()

            # 设置 agent manager 模拟
            mock_manager = MagicMock()
            mock_manager.active_agent_id = "pero"
            mock_get_manager.return_value = mock_manager

            service = AgentService(session)
            yield service

    @pytest.mark.asyncio
    async def test_get_reflection_config_disabled(self, session, agent_service):
        """测试禁用时的反思配置"""
        session.add(Config(key="reflection_enabled", value="false"))
        await session.commit()

        config = await agent_service.config_loader.get_reflection_config()
        assert config is None

    @pytest.mark.asyncio
    async def test_get_reflection_config_enabled(self, session, agent_service):
        """测试启用时的反思配置"""
        # 设置数据
        session.add(Config(key="reflection_enabled", value="true"))
        session.add(Config(key="reflection_model_id", value="1"))
        session.add(Config(key="global_llm_api_key", value="sk-global"))

        model_config = AIModelConfig(
            id=1,
            name="Reflection",
            base_url="http://api",
            api_key="sk-model",
            model_id="gpt-4",
            is_active=True,
        )
        session.add(model_config)
        await session.commit()

        config = await agent_service.config_loader.get_reflection_config()
        assert config is not None
        assert config["model"] == "gpt-4"
        # 优先级：如果设置了全局 key，则优先于模型 key？
        # _get_reflection_config 中的逻辑：
        # api_key = configs.get("global_llm_api_key") or model_config.api_key
        assert config["api_key"] == "sk-global"

    @pytest.mark.asyncio
    async def test_get_llm_config_fallback(self, session, agent_service):
        """测试没有活跃模型时的回退配置"""
        # 数据库中没有活跃模型

        # 如果需要，patch 回退逻辑，或依赖默认值
        # 服务是否使用 LLMService.get_service_config 作为回退？
        # 不，它构建了一个默认字典。

        config = await agent_service.config_loader.get_llm_config()

        # 默认回退通常是 gpt-3.5-turbo 或类似的硬编码值
        # 检查实现：
        # fallback_config = { ... "model": "gpt-3.5-turbo" ... }
        assert config["model"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_get_llm_config_current_model(self, session, agent_service):
        """测试获取当前 Agent 模型的配置"""
        # 使用模型配置设置 Agent 配置文件
        # 这需要模拟 AgentManager.get_agent 或类似方法。
        # 但 AgentService.get_llm_config 逻辑：
        # 1. 检查 Agent 配置文件的 model_config
        # 2. 检查 DB 中的活跃模型
        # 3. 回退

        # 让我们测试 DB 活跃模型路径
        session.add(Config(key="current_model_id", value="2"))
        model_config = AIModelConfig(
            id=2,
            name="Main",
            base_url="http://main",
            api_key="sk-main",
            model_id="gpt-4-turbo",
            is_active=True,
        )
        session.add(model_config)
        await session.commit()

        # 确保 Agent 配置文件不覆盖
        # fixture 中设置的 mock_agent_manager 返回一个 agent。
        # 我们需要确保该 agent 的 model_config 为空或已处理。

        config = await agent_service.config_loader.get_llm_config()
        assert config["model"] == "gpt-4-turbo"
