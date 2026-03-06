import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import List

# 配置日志
logger = logging.getLogger(__name__)


class PathResolver:
    """
    虚拟路径管理器 (Virtual Path Resolver)
    负责处理逻辑路径 (@app, @data, @workshop, @temp) 到物理路径的映射，
    并提供多层回退搜索机制。
    """

    _instance = None

    def __init__(self):
        self._init_roots()
        logger.info(f"PathResolver initialized with roots: {self.roots}")

    def _init_roots(self):
        """
        初始化各个逻辑根目录
        """
        self.roots = {}

        # 1. @app/ (程序安装根目录)
        # 判断是否为打包环境 (PyInstaller)
        if getattr(sys, "frozen", False):
            # PyInstaller 打包后，sys.executable 是 exe 路径，或者 sys._MEIPASS 是解压路径
            # 这里假设 @app 指向包含 backend 的目录的上级
            # 如果是单文件 exe，sys._MEIPASS 是临时目录，通常我们需要的是 exe 所在的目录
            app_root = os.path.dirname(sys.executable)
        else:
            # 开发环境: backend/core/path_resolver.py -> backend/core -> backend -> root
            current_file = os.path.abspath(__file__)
            backend_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(current_file))
            )
            app_root = backend_dir

        self.roots["@app"] = Path(app_root).resolve()

        # 2. @data/ (用户数据目录)
        # 优先使用环境变量，否则默认为 @app/data
        data_env = os.environ.get("PERO_DATA_DIR")
        if data_env:
            self.roots["@data"] = Path(data_env).resolve()
        else:
            self.roots["@data"] = self.roots["@app"] / "data"

        # 3. @workshop/ (创意工坊目录)
        # 优先使用环境变量，否则默认为 @app/workshop_debug (开发调试用)
        workshop_env = os.environ.get("PERO_WORKSHOP_DIR")
        if workshop_env:
            self.roots["@workshop"] = Path(workshop_env).resolve()
        else:
            self.roots["@workshop"] = self.roots["@app"] / "workshop_debug"

        # 4. @temp/ (临时目录)
        temp_env = os.environ.get("PERO_TEMP_DIR")
        if temp_env:
            self.roots["@temp"] = Path(temp_env).resolve()
        else:
            self.roots["@temp"] = Path(tempfile.gettempdir()) / "PeroCore"

        # 确保基础目录存在 (除了 @app 和 @workshop，因为它们可能是只读或由 Steam 管理)
        try:
            os.makedirs(self.roots["@data"], exist_ok=True)
            os.makedirs(self.roots["@temp"], exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create default directories: {e}")

    def resolve(self, logical_path: str) -> Path:
        """
        解析逻辑路径为绝对物理路径。
        例如: "@app/backend/main.py" -> "C:/.../PeroCore/backend/main.py"
        """
        if not logical_path:
            raise ValueError("Path cannot be empty")

        # 规范化路径分隔符
        logical_path = logical_path.replace("\\", "/")

        # 检查前缀
        for prefix, root_path in self.roots.items():
            if logical_path.startswith(prefix + "/"):
                # 移除前缀 (如 "@app/")
                relative_part = logical_path[len(prefix) + 1 :]
                return (root_path / relative_part).resolve()
            elif logical_path == prefix:
                return root_path

        # 如果没有匹配的前缀，假设是相对路径，默认相对于 @app
        # 或者直接返回原路径（如果是绝对路径）
        path_obj = Path(logical_path)
        if path_obj.is_absolute():
            return path_obj

        return (self.roots["@app"] / logical_path).resolve()

    def get_asset_search_paths(self, relative_path: str) -> List[Path]:
        """
        获取资产的搜索路径列表，遵循优先级：
        1. @data/custom/<relative_path> (用户覆盖)
        2. @workshop/content/<relative_path> (创意工坊 - 注意这里结构可能需要适配)
           注意：创意工坊通常是 ID 目录，这里简化为直接映射，实际可能需要 AssetRegistry 介入
        3. @app/<relative_path> (系统内置)
        """
        search_paths = []

        # 1. 用户覆盖
        search_paths.append(self.resolve(f"@data/custom/{relative_path}"))

        # 2. 创意工坊 (由 AssetRegistry 处理 ID 映射，这里仅提供路径基准)
        # 如果调用者传递的是包含 ID 的路径，这里直接拼接
        search_paths.append(self.resolve(f"@workshop/{relative_path}"))

        # 3. 系统内置
        search_paths.append(self.resolve(f"@app/{relative_path}"))

        return search_paths

    def get_root(self, key: str) -> Path:
        """获取特定逻辑根目录"""
        return self.roots.get(key)


# 全局单例
def get_path_resolver() -> PathResolver:
    if PathResolver._instance is None:
        PathResolver._instance = PathResolver()
    return PathResolver._instance


path_resolver = get_path_resolver()
