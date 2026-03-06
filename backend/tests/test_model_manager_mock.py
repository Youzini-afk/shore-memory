import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.model_manager import ModelInfo, ModelManager, ModelType


class TestModelManagerIntegration:
    def setup_method(self):
        # Reset singleton if needed, but patching usually handles external deps
        # We can also just modify the instance directly since it's a singleton
        self.mm = ModelManager()

    @patch("core.asset_registry.get_asset_registry")
    def test_get_model_from_registry(self, mock_get_registry):
        # Setup mock registry
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry

        # Create a fake asset
        fake_asset = MagicMock()
        fake_asset.type = "model"
        fake_asset.path = "/fake/registry/model/path"

        mock_registry.get_asset.return_value = fake_asset

        # Test get_model_path
        path = self.mm.get_model_path("test_model")
        assert path == "/fake/registry/model/path"
        mock_registry.get_asset.assert_called_with("test_model")

        # Test check_model_exists (mock os.path.exists)
        with patch("os.path.exists", return_value=True):
            assert self.mm.check_model_exists("test_model") is True

        # Test get_actual_model_path
        with patch("os.path.exists", return_value=True):
            assert (
                self.mm.get_actual_model_path("test_model")
                == "/fake/registry/model/path"
            )

    @patch("core.asset_registry.get_asset_registry")
    def test_get_model_fallback_hf(self, mock_get_registry):
        # Setup mock registry to return nothing
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        mock_registry.get_asset.return_value = None

        # Add a test model to known models
        self.mm.models["test_hf_model"] = ModelInfo(
            "test_hf_model", ModelType.WHISPER, "test/repo"
        )

        # Test get_model_path (should return HF cache path)
        path = self.mm.get_model_path("test_hf_model")
        # Depending on OS, path separator might differ, but it should contain the repo dir name
        assert "models--test--repo" in path

        # Test check_model_exists (mock failures)
        with patch("os.path.exists", return_value=False):
            assert self.mm.check_model_exists("test_hf_model") is False
