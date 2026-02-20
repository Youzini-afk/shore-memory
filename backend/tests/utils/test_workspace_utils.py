import os
import shutil
from unittest.mock import MagicMock, patch

import pytest

from utils.workspace_utils import (
    GLOBAL_WORKSPACE_ROOT,
    get_global_workspace_root,
    get_workspace_root,
)


class TestWorkspaceUtils:
    @pytest.fixture
    def mock_agent_manager(self):
        with patch("utils.workspace_utils.get_agent_manager") as mock_get:
            mock_manager = MagicMock()
            mock_agent = MagicMock()
            mock_agent.id = "test_agent"
            mock_manager.get_active_agent.return_value = mock_agent
            mock_get.return_value = mock_manager
            yield mock_get

    def test_get_global_workspace_root(self):
        """测试获取全局工作区根目录"""
        root = get_global_workspace_root()
        assert root == GLOBAL_WORKSPACE_ROOT
        assert os.path.exists(root)

    def test_get_workspace_root_with_id(self):
        """测试获取特定 Agent ID 的工作区"""
        agent_id = "CustomAgent"
        path = get_workspace_root(agent_id)

        expected_path = os.path.join(GLOBAL_WORKSPACE_ROOT, "customagent")
        assert path == expected_path
        assert os.path.exists(path)

        # 清理
        if os.path.exists(path):
            shutil.rmtree(path)

    def test_get_workspace_root_active_agent(self, mock_agent_manager):
        """测试获取当前活跃 Agent 的工作区"""
        path = get_workspace_root()

        expected_path = os.path.join(GLOBAL_WORKSPACE_ROOT, "test_agent")
        assert path == expected_path
        assert os.path.exists(path)

        # 清理
        if os.path.exists(path):
            shutil.rmtree(path)

    def test_get_workspace_root_fallback(self):
        """测试管理器失败时回退到 'pero'"""
        with patch(
            "utils.workspace_utils.get_agent_manager", side_effect=Exception("Error")
        ):
            path = get_workspace_root()
            expected_path = os.path.join(GLOBAL_WORKSPACE_ROOT, "pero")
            assert path == expected_path
