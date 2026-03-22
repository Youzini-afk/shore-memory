import os
import sys
from unittest.mock import MagicMock, patch

# 将 backend 添加到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.asset_registry import AssetMetadata
from core.plugin_manager import PluginManager


class TestPluginManagerIntegration:
    @patch("core.asset_registry.get_asset_registry")
    def test_load_plugins_via_registry(self, mock_get_registry):
        # 设置 mock 注册表
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry

        # 创建假资产
        fake_asset = AssetMetadata(
            asset_id="test_plugin",
            type="plugin",
            source="official",
            path="/fake/path/to/plugin",
            display_name="Test Plugin",
            version="1.0.0",
            config={
                "name": "TestPlugin",
                "entryPoint": "main.py",
                "pluginType": "python-module",
                "platforms": [
                    "windows",
                    "linux",
                    "darwin",
                ],  # Add platforms to avoid filter
                "capabilities": {
                    "invocationCommands": [{"commandIdentifier": "test_cmd"}]
                },
            },
        )

        mock_registry.get_assets_by_type.return_value = [fake_asset]
        mock_registry.assets = {"test_plugin": fake_asset}  # Simulate scanned state

        # Mock PluginManager 内的 importlib
        # 注意: 需要在使用处 patch。因为 PluginManager 在顶层导入了 importlib，
        # 所以我们 patch 'core.plugin_manager.importlib'
        with patch("core.plugin_manager.importlib") as mock_importlib:
            # Mock 模块加载
            mock_module = MagicMock()
            mock_module.test_cmd = lambda: "success"

            # 设置 import_module 返回 mock 模块
            mock_importlib.import_module.return_value = mock_module

            # 设置 spec_from_file_location 回退
            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_importlib.util.spec_from_file_location.return_value = mock_spec
            mock_importlib.util.module_from_spec.return_value = mock_module

            # 实例化 PluginManager
            # 可以传虚拟路径，因为不再用于扫描
            pm = PluginManager("/dummy/path")

            # 运行 load_plugins
            pm.load_plugins()

            # 断言
            mock_registry.get_assets_by_type.assert_called_with("plugin")

            # 验证插件已加载
            assert "TestPlugin" in pm.plugins
            assert "test_cmd" in pm.tools_map
            assert pm.tools_map["test_cmd"]() == "success"

    @patch("core.asset_registry.get_asset_registry")
    def test_reload_plugins(self, mock_get_registry):
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        mock_registry.assets = {}  # Start empty

        pm = PluginManager("/dummy/path")
        pm.load_plugins()

        # 现在重新加载
        pm.reload_plugins()

        # 验证 scan_all 被调用
        mock_registry.scan_all.assert_called_once()
