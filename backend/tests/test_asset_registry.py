import json
import logging
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# 确保 backend 在 sys.path 中 (模拟 backend/main.py 的行为)
current_dir = os.path.dirname(os.path.abspath(__file__))
# current_dir: backend/tests
# backend_dir: backend
backend_root = os.path.dirname(current_dir)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# 确保项目根目录也在 path 中
project_root = os.path.dirname(backend_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.asset_registry import AssetRegistry  # noqa: E402
from core.path_resolver import path_resolver  # noqa: E402

# 配置日志
logging.basicConfig(level=logging.DEBUG)


class TestAssetRegistry(unittest.TestCase):
    def setUp(self):
        # 创建临时目录模拟环境
        self.test_dir = tempfile.mkdtemp()
        self.root = Path(self.test_dir)

        # 模拟各逻辑根目录
        self.app_dir = self.root / "app"
        self.data_dir = self.root / "data"
        self.workshop_dir = self.root / "workshop"

        for d in [self.app_dir, self.data_dir, self.workshop_dir]:
            d.mkdir()

        # 重新初始化 PathResolver 指向测试目录
        # 注意：这里我们修改 path_resolver 的 roots 字典，这会影响全局单例
        # 在测试结束后需要恢复吗？实际上 PathResolver 会在下次运行时重新初始化
        # 但为了安全，我们在 tearDown 中不恢复，因为这是单元测试进程
        path_resolver.roots["@app"] = self.app_dir
        path_resolver.roots["@data"] = self.data_dir
        path_resolver.roots["@workshop"] = self.workshop_dir

        self.registry = AssetRegistry()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_asset(
        self,
        root: Path,
        rel_path: str,
        asset_id: str,
        type="plugin",
        version="1.0.0",
        extra=None,
    ):
        asset_dir = root / rel_path
        asset_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "asset_id": asset_id,
            "type": type,
            "version": version,
            "display_name": f"Test Asset {asset_id}",
        }
        if extra:
            data.update(extra)

        with open(asset_dir / "asset.json", "w", encoding="utf-8") as f:
            json.dump(data, f)
        return asset_dir

    def test_scan_priority(self):
        """测试加载优先级: Local > Workshop > Official"""
        asset_id = "com.test.priority"

        # 1. 创建 Official 版本 (v1.0)
        # 模拟 Official 路径: @app/backend/nit_core/plugins/test_plugin
        self._create_asset(
            self.app_dir,
            "backend/nit_core/plugins/official_ver",
            asset_id,
            version="1.0.0",
        )

        self.registry.scan_all()
        asset = self.registry.get_asset(asset_id)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.version, "1.0.0")
        self.assertEqual(asset.source, "official")

        # 2. 创建 Workshop 版本 (v1.1)
        # 模拟 Workshop 路径: @workshop/12345
        self._create_asset(
            self.workshop_dir,
            "12345",
            asset_id,
            version="1.1.0",
            extra={"workshop_id": "12345"},
        )

        self.registry.scan_all()
        asset = self.registry.get_asset(asset_id)
        self.assertEqual(asset.version, "1.1.0")
        self.assertEqual(asset.source, "workshop")
        self.assertEqual(asset.workshop_id, "12345")

        # 3. 创建 Local 版本 (v1.2)
        # 模拟 Local 路径: @data/custom/my_plugin
        self._create_asset(self.data_dir, "custom/my_plugin", asset_id, version="1.2.0")

        self.registry.scan_all()
        asset = self.registry.get_asset(asset_id)
        self.assertEqual(asset.version, "1.2.0")
        self.assertEqual(asset.source, "local")

    def test_legacy_manifest_support(self):
        """测试对旧版 manifest.json 的兼容性"""
        # 模拟 Bedrock 模型
        model_dir = self.app_dir / "public/assets/3d/OldModel"
        model_dir.mkdir(parents=True, exist_ok=True)

        manifest = {"metadata": {"name": "OldModel", "version": "0.5.0"}}
        with open(model_dir / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f)

        self.registry.scan_all()
        # 预期生成的 ID: com.perocore.model.oldmodel
        asset = self.registry.get_asset("com.perocore.model.oldmodel")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.type, "model_3d")
        self.assertEqual(asset.source, "official")

    def test_type_index(self):
        """测试按类型索引"""
        self._create_asset(
            self.app_dir, "backend/nit_core/plugins/p1", "p1", type="plugin"
        )
        self._create_asset(
            self.app_dir, "backend/nit_core/plugins/p2", "p2", type="plugin"
        )
        self._create_asset(self.app_dir, "public/assets/3d/m1", "m1", type="model_3d")

        self.registry.scan_all()

        plugins = self.registry.get_assets_by_type("plugin")
        models = self.registry.get_assets_by_type("model_3d")

        self.assertEqual(len(plugins), 2)
        self.assertEqual(len(models), 1)

    def test_description_json_support(self):
        """测试对 description.json 的支持 (插件)"""
        plugin_dir = self.app_dir / "backend/nit_core/plugins/LegacyPlugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)

        desc = {"name": "LegacyPlugin", "entryPoint": "main.py", "version": "2.0.0"}
        with open(plugin_dir / "description.json", "w", encoding="utf-8") as f:
            json.dump(desc, f)

        self.registry.scan_all()

        # 预期 ID: com.perocore.plugin.legacyplugin
        asset = self.registry.get_asset("com.perocore.plugin.legacyplugin")
        self.assertIsNotNone(asset)
        self.assertEqual(asset.type, "plugin")
        self.assertEqual(asset.version, "2.0.0")


if __name__ == "__main__":
    unittest.main()
