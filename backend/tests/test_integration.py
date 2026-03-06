import os
import sys
import unittest

# 确保 backend 在 sys.path 中 (模拟 backend/main.py 的行为)
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 同时也确保项目根目录在 sys.path 中，以便可以使用 backend.xxx
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.core.path_resolver import path_resolver  # noqa: E402
from backend.core.plugin_manager import get_plugin_manager  # noqa: E402
from backend.services.mdp.manager import get_mdp_manager  # noqa: E402


class TestIntegration(unittest.TestCase):
    def test_mdp_manager(self):
        print("\nTesting MDP Manager...")
        mdp = get_mdp_manager()
        self.assertIsNotNone(mdp)
        # 验证提示词是否加载 (假设至少有 system.md)
        self.assertTrue(len(mdp.prompts) > 0, "MDP prompts should not be empty")
        print(f"Loaded {len(mdp.prompts)} MDP prompts from {mdp.prompt_dir}")

        # 验证路径解析
        expected_path = path_resolver.resolve("@app/backend/services/mdp/prompts")
        # 路径可能是 Windows Path 对象或字符串，统一转换为字符串比较
        self.assertEqual(str(mdp.prompt_dir), str(expected_path))

    def test_plugin_manager(self):
        print("\nTesting Plugin Manager...")
        pm = get_plugin_manager()
        self.assertIsNotNone(pm)
        # 验证插件是否加载 (假设至少有一些插件)
        # 注意: 如果环境没有任何插件，这里可能会失败，但在当前项目中应该有
        print(f"Loaded {len(pm.plugins)} plugins from {pm.plugin_dir}")

        # 验证路径解析
        expected_path = path_resolver.resolve("@app/backend/nit_core/tools")
        self.assertEqual(str(pm.plugin_dir), str(expected_path))


if __name__ == "__main__":
    unittest.main()
