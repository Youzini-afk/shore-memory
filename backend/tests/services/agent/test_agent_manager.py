import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from services.agent.agent_manager import AgentManager, AgentProfile

# 示例配置数据
SAMPLE_AGENT_CONFIG = {
    "name": "Test Agent",
    "description": "A test agent",
    "personas": {"work": "personas/work.md", "social": "personas/social.md"},
    "traits": {"work": ["diligent"], "social": ["friendly"]},
    "model_config": {"model_id": "gpt-4"},
    "social": {"use_stickers": True},
    "tool_policies": {"allow_shell": False},
}


class TestAgentManager:
    @pytest.fixture
    def manager(self):
        # 重置单例
        AgentManager._instance = None
        # 模拟目录以避免实际文件系统访问
        with (
            patch("os.path.exists", return_value=True),
            patch("os.makedirs"),
            patch("services.agent.agent_manager.AgentManager._scan_and_load_agents"),
        ):
            mgr = AgentManager()
            # 清除任何已加载的代理
            mgr.agents = {}
            mgr.enabled_agents = set()
            return mgr

    def test_singleton(self):
        AgentManager._instance = None
        m1 = AgentManager()
        m2 = AgentManager()
        assert m1 is m2

    def test_load_agent_config_success(self, manager):
        """测试加载有效的代理配置"""
        agent_id = "test_agent"
        config_path = "/data/agents/test_agent/config.json"
        prompt_path = "/data/agents/test_agent/system_prompt.md"

        # 模拟
        mock_file_content = json.dumps(SAMPLE_AGENT_CONFIG)

        def mock_open_side_effect(file, *args, **kwargs):
            if file == config_path:
                return mock_open(read_data=mock_file_content).return_value
            elif file.endswith("work.md"):
                return mock_open(read_data="Work Persona Content").return_value
            elif file.endswith("social.md"):
                return mock_open(read_data="Social Persona Content").return_value
            return mock_open(read_data="").return_value

        with (
            patch("builtins.open", side_effect=mock_open_side_effect),
            patch("os.path.exists", return_value=True),
        ):
            profile = manager._load_agent_config(agent_id, config_path, prompt_path)

        assert isinstance(profile, AgentProfile)
        assert profile.id == agent_id
        assert profile.name == "Test Agent"
        assert profile.work_custom_persona == "Work Persona Content"
        assert profile.social_custom_persona == "Social Persona Content"
        assert profile.work_traits == ["diligent"]
        assert profile.use_stickers is True
        assert profile.model_config["model_id"] == "gpt-4"

    def test_load_agent_config_legacy(self, manager):
        """测试加载旧版配置格式"""
        legacy_config = {
            "name": "Legacy Agent",
            "work_custom_persona": "Legacy Work",
            "social_custom_persona": "Legacy Social",
            "work_traits": ["old"],
            "social_traits": ["older"],
        }

        agent_id = "legacy_agent"
        config_path = "/data/legacy/config.json"

        with (
            patch("builtins.open", mock_open(read_data=json.dumps(legacy_config))),
            patch("os.path.exists", return_value=True),
        ):
            profile = manager._load_agent_config(agent_id, config_path, "prompt.md")

        assert profile.work_custom_persona == "Legacy Work"
        assert profile.work_traits == ["old"]

    def test_scan_and_load_agents(self, manager):
        """测试扫描目录并加载代理"""
        base_dir = "/agents"

        # 模拟 scandir 条目
        entry1 = MagicMock()
        entry1.is_dir.return_value = True
        entry1.name = "agent1"
        entry1.path = "/agents/agent1"

        entry2 = MagicMock()
        entry2.is_dir.return_value = True
        entry2.name = "agent2"
        entry2.path = "/agents/agent2"

        # Mock _load_agent_config 返回虚拟配置
        with (
            patch("os.scandir", return_value=[entry1, entry2]),
            patch("os.path.exists", return_value=True),
            patch.object(manager, "_load_agent_config") as mock_load,
        ):
            mock_load.side_effect = [
                AgentProfile(id="agent1", name="Agent 1"),
                AgentProfile(id="agent2", name="Agent 2"),
            ]

            manager._scan_and_load_agents(base_dir, is_user_dir=False)

            assert len(manager.agents) == 2
            assert "agent1" in manager.agents
            assert "agent2" in manager.agents
            assert manager.agents["agent1"].name == "Agent 1"

    def test_reload_agents(self, manager):
        """测试完整重新加载流程"""
        # 恢复原始方法以进行此测试，因为我们在 fixture 中模拟了它
        with (
            patch.object(
                AgentManager, "_scan_and_load_agents", autospec=True
            ) as mock_scan,
            patch("os.path.exists", return_value=True),
        ):
            manager.reload_agents()

            assert mock_scan.call_count == 2  # 内置 + 用户
            # 第一次调用：内置
            assert mock_scan.call_args_list[0][0][1] == manager.agents_dir
            assert mock_scan.call_args_list[0][1]["is_user_dir"] is False
            # 第二次调用：用户
            assert mock_scan.call_args_list[1][0][1] == manager.user_agents_dir
            assert mock_scan.call_args_list[1][1]["is_user_dir"] is True
