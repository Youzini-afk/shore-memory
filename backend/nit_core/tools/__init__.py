import os
import sys

# 尝试从 backend.core 导入 PluginManager (如果从 PeroCore 根目录运行)
# 或从 core 导入 (如果从 backend 根目录运行)
try:
    from backend.core.plugin_manager import get_plugin_manager
except ImportError:
    try:
        from core.plugin_manager import get_plugin_manager
    except ImportError:
        # 回退：可能在 tools 目录？尝试将父目录添加到路径？
        # 如果环境设置正确，理想情况下不应发生这种情况。
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from core.plugin_manager import get_plugin_manager

# 使用单例创建并加载插件
plugin_manager = get_plugin_manager()
# plugin_manager.load_plugins() # get_plugin_manager 已经加载了它们

# 导出 TOOLS_MAPPING
TOOLS_MAPPING = plugin_manager.get_all_tools_map()
TOOLS_DEFINITIONS = plugin_manager.get_all_definitions()

# 用于向后兼容的旧别名
if "save_screenshot" in TOOLS_MAPPING and "take_screenshot" not in TOOLS_MAPPING:
    TOOLS_MAPPING["take_screenshot"] = TOOLS_MAPPING["save_screenshot"]

if "get_screenshot_base64" in TOOLS_MAPPING and "see_screen" not in TOOLS_MAPPING:
    TOOLS_MAPPING["see_screen"] = TOOLS_MAPPING["get_screenshot_base64"]

if "browser_type" in TOOLS_MAPPING and "browser_input" not in TOOLS_MAPPING:
    TOOLS_MAPPING["browser_input"] = TOOLS_MAPPING["browser_type"]
