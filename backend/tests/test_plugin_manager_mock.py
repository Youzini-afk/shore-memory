import os
import sys
from unittest.mock import MagicMock, patch

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.asset_registry import AssetMetadata
from core.plugin_manager import PluginManager


class TestPluginManagerIntegration:
    @patch("core.asset_registry.get_asset_registry")
    def test_load_plugins_via_registry(self, mock_get_registry):
        # Setup mock registry
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry

        # Create a fake asset
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

        # Mock importlib inside PluginManager
        # Note: We need to patch where it is used. Since PluginManager imports importlib at top level,
        # we patch 'core.plugin_manager.importlib'
        with patch("core.plugin_manager.importlib") as mock_importlib:
            # Mock module loading
            mock_module = MagicMock()
            mock_module.test_cmd = lambda: "success"

            # Setup import_module to return our mock module
            mock_importlib.import_module.return_value = mock_module

            # Setup spec_from_file_location fallback
            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_importlib.util.spec_from_file_location.return_value = mock_spec
            mock_importlib.util.module_from_spec.return_value = mock_module

            # Instantiate PluginManager
            # We can pass a dummy path since it won't be used for scanning anymore
            pm = PluginManager("/dummy/path")

            # Run load_plugins
            pm.load_plugins()

            # Assertions
            mock_registry.get_assets_by_type.assert_called_with("plugin")

            # Verify plugin loaded
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

        # Now reload
        pm.reload_plugins()

        # Verify scan_all was called
        mock_registry.scan_all.assert_called_once()
