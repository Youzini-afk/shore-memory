import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.model_manager import ModelInfo, ModelManager, ModelType


class TestModelManagerIntegration:
    def setup_method(self):
        # 如需重置单例，但 patching 通常处理外部依赖
        # 也可以直接修改实例，因为它是单例
        self.mm = ModelManager()

    @patch("core.asset_registry.get_asset_registry")
    def test_get_model_from_registry(self, mock_get_registry):
        # 设置 mock 注册表
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry

        # 创建假资产
        fake_asset = MagicMock()
        fake_asset.type = "model"
        fake_asset.path = "/fake/registry/model/path"

        mock_registry.get_asset.return_value = fake_asset

        # 测试 get_model_path
        path = self.mm.get_model_path("test_model")
        assert path == "/fake/registry/model/path"
        mock_registry.get_asset.assert_called_with("test_model")

        # 测试 check_model_exists (mock os.path.exists)
        with patch("os.path.exists", return_value=True):
            assert self.mm.check_model_exists("test_model") is True

        # 测试 get_actual_model_path
        with patch("os.path.exists", return_value=True):
            assert (
                self.mm.get_actual_model_path("test_model")
                == "/fake/registry/model/path"
            )

    @patch("core.asset_registry.get_asset_registry")
    def test_get_model_fallback_hf(self, mock_get_registry):
        # 设置 mock 注册表 to return nothing
        mock_registry = MagicMock()
        mock_get_registry.return_value = mock_registry
        mock_registry.get_asset.return_value = None

        # 添加测试模型到已知模型
        self.mm.models["test_hf_model"] = ModelInfo(
            "test_hf_model", ModelType.WHISPER, "test/repo"
        )

        # 测试 get_model_path (should return HF cache path)
        path = self.mm.get_model_path("test_hf_model")
        # 路径分隔符可能因系统而异，但应包含仓库目录名
        assert "models--test--repo" in path

        # 测试 check_model_exists（mock 失败情况）
        with patch("os.path.exists", return_value=False):
            assert self.mm.check_model_exists("test_hf_model") is False
