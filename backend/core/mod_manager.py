import importlib.util
import logging
import os
import sys

logger = logging.getLogger(__name__)


class ModManager:
    """
    Mod 管理器。
    负责发现和加载用户 Mod。
    """

    MODS_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mods"
    )

    @classmethod
    def load_mods(cls):
        """
        加载所有 Mod。
        """
        if not os.path.exists(cls.MODS_DIR):
            logger.info(f"[ModManager] Mod 目录不存在: {cls.MODS_DIR}，正在创建...")
            os.makedirs(cls.MODS_DIR, exist_ok=True)
            return

        logger.info(f"[ModManager] 正在扫描 Mod 目录: {cls.MODS_DIR}")

        for item in os.listdir(cls.MODS_DIR):
            mod_path = os.path.join(cls.MODS_DIR, item)
            if os.path.isdir(mod_path):
                cls._load_single_mod(mod_path, item)

    @classmethod
    def _load_single_mod(cls, mod_path: str, mod_name: str):
        """
        加载单个 Mod。
        查找 main.py 并执行其中的 init() 函数。
        """
        main_py = os.path.join(mod_path, "main.py")
        if not os.path.exists(main_py):
            # 尝试 init.py
            main_py = os.path.join(mod_path, "__init__.py")
            if not os.path.exists(main_py):
                logger.warning(
                    f"[ModManager] Mod {mod_name} 缺少 main.py 或 __init__.py，跳过。"
                )
                return

        try:
            spec = importlib.util.spec_from_file_location(f"mods.{mod_name}", main_py)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[f"mods.{mod_name}"] = module
                spec.loader.exec_module(module)

                # 尝试调用 init()
                if hasattr(module, "init"):
                    logger.info(f"[ModManager] 正在初始化 Mod: {mod_name}")
                    module.init()
                else:
                    logger.warning(
                        f"[ModManager] Mod {mod_name} 没有 init() 函数，可能无法生效。"
                    )
            else:
                logger.error(f"[ModManager] 无法加载 Mod {mod_name} spec。")
        except Exception as e:
            logger.error(f"[ModManager] 加载 Mod {mod_name} 失败: {e}", exc_info=True)
