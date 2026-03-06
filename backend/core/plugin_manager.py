import importlib
import logging
import os
import platform
from typing import Any, Callable, Dict, List, Optional

from core.config_manager import get_config_manager
from core.nit_manager import get_nit_manager

# 配置日志
logger = logging.getLogger(__name__)


class PluginManager:
    """
    负责 PeroCore 中插件的发现、加载和注册管理。
    """

    def __init__(self, plugin_dir: str):
        """
        初始化插件管理器。

        Args:
            plugin_dir: 包含插件的绝对路径目录。
        """
        self.plugin_dir = plugin_dir
        self.plugins: Dict[str, Dict[str, Any]] = {}  # 插件名 -> 清单(Manifest)
        self.tools_map: Dict[str, Callable] = {}  # 命令ID -> 可执行函数
        self.loaded_modules: Dict[str, Any] = {}  # 插件名 -> 已加载模块对象
        self.config_manager = get_config_manager()
        self.nit_manager = get_nit_manager()

    def load_plugins(self):
        """
        通过 AssetRegistry 加载所有有效插件。
        """
        from core.asset_registry import get_asset_registry

        registry = get_asset_registry()

        logger.info("正在通过 AssetRegistry 加载插件...")

        # 获取所有插件类型的资产
        plugins = registry.get_assets_by_type("plugin")

        for asset in plugins:
            self._load_plugin_from_asset(asset)

        logger.info(
            f"插件加载完成。已加载 {len(self.plugins)} 个插件和 {len(self.tools_map)} 个命令。"
        )

    def reload_plugins(self):
        """
        清除现有插件和工具，并重新加载。
        """
        logger.info("正在重新加载所有插件...")
        self.plugins.clear()
        self.tools_map.clear()
        self.loaded_modules.clear()

        # 重新扫描资产注册表
        from core.asset_registry import get_asset_registry

        registry = get_asset_registry()
        registry.scan_all()

        self.load_plugins()

    def _load_plugin_from_asset(self, asset):
        """
        从 AssetMetadata 加载单个插件。
        """
        manifest = asset.config
        plugin_path = asset.path
        # plugin_folder_name 通常是目录名
        plugin_folder_name = os.path.basename(plugin_path)

        if not manifest:
            logger.error(f"资产 {asset.asset_id} 缺少配置信息。")
            return

        # 基础校验
        if "name" not in manifest or "entryPoint" not in manifest:
            logger.error(f"插件 {asset.asset_id} 的清单无效: 缺少 name 或 entryPoint。")
            return

        plugin_name = manifest["name"]

        # 推断分类信息 (用于 Dispatcher 过滤)
        # 简单逻辑：根据路径包含的关键字判断
        category = "general"
        norm_path = plugin_path.replace("\\", "/")
        if "nit_core/tools/core" in norm_path:
            category = "core"
        elif "nit_core/tools/work" in norm_path:
            category = "work"
        elif "nit_core/tools/group" in norm_path:
            category = "group"
        elif "nit_core/plugins" in norm_path:
            category = "plugins"
        elif asset.source == "workshop":
            category = "workshop"
        elif asset.source == "local":
            category = "custom"

        manifest["_category"] = category

        # 平台兼容性检查
        supported_platforms = manifest.get("platforms")
        if supported_platforms:
            current_platform = platform.system().lower()
            if os.environ.get("PERO_ENV") == "server":
                current_platform = "server"

            if current_platform not in [p.lower() for p in supported_platforms]:
                logger.info(
                    f"跳过插件 {plugin_name}: 当前平台 ({current_platform}) 不在支持列表 {supported_platforms} 中。"
                )
                return

        plugin_type = manifest.get("pluginType", "python-module")

        if plugin_type == "python-module":
            self._load_python_module_plugin(
                plugin_path, plugin_folder_name, manifest, category
            )
        elif plugin_type == "static":
            logger.warning(f"尚不完全支持 {plugin_name} 的静态插件类型，跳过执行逻辑。")
        else:
            logger.warning(f"{plugin_name} 的插件类型 '{plugin_type}' 未知。")

        self.plugins[plugin_name] = manifest

    def _load_python_module_plugin(
        self,
        plugin_path: str,
        plugin_folder_name: str,
        manifest: Dict[str, Any],
        category: str = None,
    ):
        """
        加载 python-module 类型的插件。
        """
        entry_point = manifest["entryPoint"]
        module_file = entry_point
        module_name = module_file[:-3] if module_file.endswith(".py") else module_file

        # 尝试构建导入路径 (仅针对官方内置插件)
        # 这样可以保持 module 的包结构正确 (例如 backend.nit_core.tools...)
        module = None

        # 只有在 backend 目录下的才尝试 import_module
        # 使用 path_resolver 判断? 或者简单的字符串检查
        if "backend" in plugin_path and "nit_core" in plugin_path:
            # 构建导入路径
            import_paths_to_try = []

            # 尝试根据分类构建
            if category == "plugins":
                # backend.nit_core.plugins.<PluginName>.<Module>
                import_paths_to_try.append(
                    f"backend.nit_core.plugins.{plugin_folder_name}.{module_name}"
                )
                import_paths_to_try.append(
                    f"nit_core.plugins.{plugin_folder_name}.{module_name}"
                )
            elif category in ["core", "work", "group"]:
                # backend.nit_core.tools.<Category>.<PluginName>.<Module>
                import_paths_to_try.append(
                    f"backend.nit_core.tools.{category}.{plugin_folder_name}.{module_name}"
                )
                import_paths_to_try.append(
                    f"nit_core.tools.{category}.{plugin_folder_name}.{module_name}"
                )

            # 旧版/通用尝试
            import_paths_to_try.append(
                f"backend.nit_core.tools.{plugin_folder_name}.{module_name}"
            )

            for path in import_paths_to_try:
                try:
                    module = importlib.import_module(path)
                    break
                except ImportError:
                    continue

        if not module:
            # 最后的尝试: sys.path hack / spec_from_file_location
            # 对于 Workshop 和 Local 插件，这将是主要加载方式
            try:
                spec = importlib.util.spec_from_file_location(
                    module_name, os.path.join(plugin_path, module_file)
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
            except Exception as e:
                logger.error(f"从 {plugin_path} 加载模块 {module_name} 失败: {e}")
                return

        # 注册功能函数
        if (
            "capabilities" in manifest
            and "invocationCommands" in manifest["capabilities"]
        ):
            for cmd in manifest["capabilities"]["invocationCommands"]:
                cmd_id = cmd["commandIdentifier"]
                if hasattr(module, cmd_id):
                    self.tools_map[cmd_id] = getattr(module, cmd_id)
                else:
                    logger.warning(
                        f"在插件 '{manifest['name']}' 的模块 '{module_name}' 中未找到函数 '{cmd_id}'。"
                    )

        self.loaded_modules[manifest["name"]] = module

    def list_plugins(self) -> List[str]:
        """
        列出所有已发现的插件名称。
        """
        return list(self.plugins.keys())

    def get_tool(self, command_identifier: str) -> Optional[Callable]:
        """
        获取指定命令 ID 对应的可调用函数。
        """
        return self.tools_map.get(command_identifier)

    def get_all_tools_map(self) -> Dict[str, Callable]:
        """
        获取完整的命令 ID 到函数的映射。
        """
        return self.tools_map

    def get_all_definitions(self) -> List[Dict[str, Any]]:
        definitions = []
        for _plugin_name, manifest in self.plugins.items():
            # 检查 invocationCommands (NIT 格式标准)
            if (
                "capabilities" in manifest
                and "invocationCommands" in manifest["capabilities"]
            ):
                definitions.extend(manifest["capabilities"]["invocationCommands"])
            elif (
                "capabilities" in manifest
                and "toolDefinitions" in manifest["capabilities"]
            ):
                definitions.extend(manifest["capabilities"]["toolDefinitions"])
        return definitions

    def get_all_manifests(self) -> List[Dict[str, Any]]:
        """
        获取所有已加载的插件清单。
        """
        return list(self.plugins.values())


_instance = None


from core.path_resolver import path_resolver  # noqa: E402


def get_plugin_manager() -> PluginManager:
    global _instance
    if _instance is None:
        # 使用 path_resolver 解析
        # Target: backend/nit_core/tools
        plugin_dir = path_resolver.resolve("@app/backend/nit_core/tools")
        _instance = PluginManager(str(plugin_dir))
        _instance.load_plugins()
    return _instance


# 全局实例，便于访问
plugin_manager = get_plugin_manager()
