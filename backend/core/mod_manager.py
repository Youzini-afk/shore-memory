"""
ModManager — PeroCore 三层扩展系统加载器
========================================

扫描 backend/mods/ 目录，加载所有 MOD。

MOD 目录约定：
    mods/
    ├── _external_plugins/      # _ 前缀：系统基础设施（不作为用户 MOD 加载）
    └── my_mod/
        ├── mod.toml            # 可选：声明式元数据
        ├── main.py             # 必须：入口文件，包含 init() 函数
        ├── hooks.py            # 可选：EventBus Hook 处理函数
        ├── processors.py       # 可选：管道处理器
        └── external/           # 可选：外部插件独立服务（不被主进程加载）
            └── server.py

加载规则：
  - 跳过 _ 前缀的目录（系统基础设施）
  - 跳过没有 main.py 的目录
  - 读取 mod.toml（如果存在）获取元数据
  - 调用 main.py 中的 init() 函数
"""

import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModInfo:
    """MOD 元数据（字段与 asset.json 对齐）"""

    id: str
    name: str
    asset_id: str = ""          # 资产联邦 ID (如 com.perocore.mod.xxx)
    display_name: str = ""      # 显示名称
    version: str = "0.0.1"
    description: str = ""
    author: str = ""
    path: str = ""

    # 声明使用的扩展层
    uses_eventbus: bool = False
    uses_pipeline: bool = False
    uses_external: bool = False
    external_url: str = ""

    # 运行时状态
    loaded: bool = False
    error: Optional[str] = None


class ModManager:
    """
    Mod 管理器。
    负责发现、加载用户 Mod，并记录其元数据。
    """

    MODS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mods"
    )

    # 已加载的 MOD 信息
    _loaded_mods: Dict[str, ModInfo] = {}

    @classmethod
    def load_mods(cls):
        """扫描并加载所有 Mod。"""
        if not os.path.exists(cls.MODS_DIR):
            logger.info(f"[ModManager] Mod 目录不存在: {cls.MODS_DIR}，正在创建...")
            os.makedirs(cls.MODS_DIR, exist_ok=True)
            return

        logger.info(f"[ModManager] 正在扫描 Mod 目录: {cls.MODS_DIR}")

        for item in sorted(os.listdir(cls.MODS_DIR)):
            mod_path = os.path.join(cls.MODS_DIR, item)

            # 跳过非目录
            if not os.path.isdir(mod_path):
                continue

            # 跳过 _ 前缀目录（系统基础设施）
            if item.startswith("_"):
                logger.debug(f"[ModManager] 跳过系统目录: {item}")
                continue

            cls._load_single_mod(mod_path, item)

        loaded_count = sum(1 for m in cls._loaded_mods.values() if m.loaded)
        total_count = len(cls._loaded_mods)
        logger.info(f"[ModManager] MOD 加载完成: {loaded_count}/{total_count} 成功")

    @classmethod
    def _load_single_mod(cls, mod_path: str, mod_name: str):
        """加载单个 Mod：读取元数据 → 执行 init()"""

        # 查找入口文件
        main_py = os.path.join(mod_path, "main.py")
        if not os.path.exists(main_py):
            main_py = os.path.join(mod_path, "__init__.py")
            if not os.path.exists(main_py):
                logger.warning(
                    f"[ModManager] Mod {mod_name} 缺少 main.py 或 __init__.py，跳过。"
                )
                return

        # 读取 mod.toml 元数据（可选）
        mod_info = cls._read_mod_toml(mod_path, mod_name)
        cls._loaded_mods[mod_info.id] = mod_info

        try:
            spec = importlib.util.spec_from_file_location(f"mods.{mod_name}", main_py)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"mods.{mod_name}"] = module
                spec.loader.exec_module(module)

                if hasattr(module, "init"):
                    logger.info(
                        f"[ModManager] 正在初始化 Mod: {mod_info.name} "
                        f"(v{mod_info.version})"
                    )
                    module.init()
                    mod_info.loaded = True
                else:
                    logger.warning(
                        f"[ModManager] Mod {mod_name} 没有 init() 函数，可能无法生效。"
                    )
                    mod_info.loaded = True  # 模块已加载，只是没有 init
            else:
                mod_info.error = "无法创建 module spec"
                logger.error(f"[ModManager] 无法加载 Mod {mod_name} spec。")
        except Exception as e:
            mod_info.error = str(e)
            logger.error(f"[ModManager] 加载 Mod {mod_name} 失败: {e}", exc_info=True)

    @classmethod
    def _read_mod_toml(cls, mod_path: str, mod_name: str) -> ModInfo:
        """读取 mod.toml 元数据。如果不存在，返回默认值。"""
        toml_path = os.path.join(mod_path, "mod.toml")

        # 默认值
        info = ModInfo(id=mod_name, name=mod_name, path=mod_path)

        if not os.path.exists(toml_path):
            return info

        try:
            # Python 3.11+ 内置 tomllib
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore

            with open(toml_path, "rb") as f:
                data = tomllib.load(f)

            mod_section = data.get("mod", {})
            info.id = mod_section.get("asset_id", mod_name).split(".")[-1]  # 从 asset_id 提取短 ID
            info.asset_id = mod_section.get("asset_id", "")
            info.name = mod_section.get("display_name", mod_name)
            info.display_name = mod_section.get("display_name", mod_name)
            info.version = mod_section.get("version", "0.0.1")
            info.description = mod_section.get("description", "")
            info.author = mod_section.get("author", "")

            layers = data.get("layers", {})
            info.uses_eventbus = layers.get("eventbus", False)
            info.uses_pipeline = layers.get("pipeline", False)
            info.uses_external = layers.get("external", False)
            info.external_url = layers.get("external_url", "")

            logger.debug(f"[ModManager] 已读取 {mod_name}/mod.toml")

        except Exception as e:
            logger.warning(f"[ModManager] 读取 {mod_name}/mod.toml 失败: {e}")

        return info

    @classmethod
    def get_loaded_mods(cls) -> Dict[str, ModInfo]:
        """获取所有已加载 MOD 的信息"""
        return cls._loaded_mods.copy()

    @classmethod
    def get_mod_info(cls, mod_id: str) -> Optional[ModInfo]:
        """获取单个 MOD 信息"""
        return cls._loaded_mods.get(mod_id)
