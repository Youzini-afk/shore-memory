import unittest

from backend.core.path_resolver import get_path_resolver


class TestPathResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = get_path_resolver()
        # Mock 环境变量 (可选，根据实际需求)

    def test_roots_initialization(self):
        """测试根目录是否正确初始化"""
        self.assertIn("@app", self.resolver.roots)
        self.assertIn("@data", self.resolver.roots)
        self.assertIn("@workshop", self.resolver.roots)
        self.assertIn("@temp", self.resolver.roots)

        # 验证 @app 路径是否存在 (假设在开发环境中运行)
        app_path = self.resolver.get_root("@app")
        self.assertTrue(app_path.exists())
        self.assertTrue((app_path / "backend").exists())

    def test_resolve_logic(self):
        """测试路径解析逻辑"""
        # 测试 @app 前缀
        path1 = self.resolver.resolve("@app/backend/main.py")
        # Windows 路径兼容性修复: 使用 Path.parts 或 normalize
        self.assertTrue(str(path1).replace("\\", "/").endswith("backend/main.py"))

        # 测试 @data 前缀
        path2 = self.resolver.resolve("@data/config.json")
        self.assertTrue(str(path2).replace("\\", "/").endswith("config.json"))

        # 测试 @workshop 前缀
        path3 = self.resolver.resolve("@workshop/content/123456/asset.json")
        self.assertTrue(
            str(path3).replace("\\", "/").endswith("content/123456/asset.json")
        )

    def test_search_paths(self):
        """测试多层回退搜索路径生成"""
        search_list = self.resolver.get_asset_search_paths("models/rossi")

        # 验证顺序: custom -> workshop -> app
        self.assertEqual(len(search_list), 3)
        # Windows 路径兼容性修复
        self.assertTrue(
            str(search_list[0]).replace("\\", "/").endswith("data/custom/models/rossi")
        )
        # 默认情况下，@workshop 映射到 workshop_debug
        self.assertTrue(
            str(search_list[1])
            .replace("\\", "/")
            .endswith("workshop_debug/models/rossi")
        )

        # @app 映射到项目根目录 (通常是 PeroCore)
        # 所以路径不包含 "app/"，而是直接是项目根目录下的 models/rossi
        # 我们这里只检查相对路径部分
        self.assertTrue(
            str(search_list[2]).replace("\\", "/").endswith("/models/rossi")
        )
        # 也可以验证它确实是在 @app 下
        app_root = self.resolver.get_root("@app")
        self.assertEqual(search_list[2], app_root / "models/rossi")


if __name__ == "__main__":
    unittest.main()
