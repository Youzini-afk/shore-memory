from unittest.mock import MagicMock, patch

import pytest

from services.core.prompt_service import PromptManager


class TestPromptManager:
    @pytest.fixture
    def mock_dependencies(self):
        with (
            patch("services.core.prompt_service.mdp") as mock_mdp,
            patch(
                "services.core.prompt_service.get_agent_manager"
            ) as mock_get_agent_mgr,
            patch("services.core.prompt_service.get_config_manager") as mock_get_config,
        ):
            # 设置配置管理器
            mock_config_mgr = MagicMock()
            mock_config_mgr.get.side_effect = lambda k, d=None: {
                "owner_name": "TestUser"
            }.get(k, d)
            mock_get_config.return_value = mock_config_mgr

            # 设置 MDP
            mock_mdp.get_prompt.return_value = MagicMock(content="Mock Content")

            yield mock_mdp, mock_get_agent_mgr, mock_config_mgr

    def test_enrich_variables_basic(self, mock_dependencies):
        """测试基本变量丰富"""
        mock_mdp, _, _ = mock_dependencies
        manager = PromptManager()

        variables = {"existing": "value"}
        manager._enrich_variables(variables, is_social_mode=False, is_work_mode=True)

        # 检查系统提示词注入
        assert "system_prompt" in variables
        assert variables["system_prompt"] == "Mock Content"
        mock_mdp.get_prompt.assert_any_call("agents/pero/system_prompt")

        # 检查链式逻辑注入
        assert "chain_logic" in variables

        # 检查拥有者名称和用户别名
        assert variables["owner_name"] == "TestUser"
        assert variables["user"] == "TestUser"

        # 检查默认值
        assert variables["mood"] == "开心"

    def test_enrich_variables_preserve_existing(self, mock_dependencies):
        """测试现有变量不被覆盖"""
        manager = PromptManager()

        variables = {"owner_name": "CustomOwner", "mood": "Sad"}
        manager._enrich_variables(variables, is_social_mode=False, is_work_mode=True)

        assert variables["owner_name"] == "CustomOwner"
        assert variables["mood"] == "Sad"
        # 用户别名应该仍然与 owner_name 同步，除非显式设置？
        # 实现说明: variables["user"] = variables["owner_name"]
        assert variables["user"] == "CustomOwner"
