from core.component_container import ComponentContainer
from core.interfaces import (
    IPostprocessorManager,
    IPreprocessorManager,
)
from core.mod_manager import ModManager

# 导入默认实现类
from services.postprocessor.manager import PostprocessorManager
from services.preprocessor.manager import PreprocessorManager


def bootstrap():
    """
    系统启动引导程序。
    负责注册核心组件、加载 Mod。

    仅 PreprocessorManager 和 PostprocessorManager 通过 IoC 容器管理，
    支持 MOD 通过 register() 插入处理节点或通过 override() 整体替换。
    其他核心服务（PromptManager, MemoryService 等）由各自使用方直接实例化。
    """
    print("[Bootstrap] 开始初始化核心组件...")

    # 注册 PreprocessorManager
    def create_preprocessor_manager():
        pm = PreprocessorManager()
        from services.preprocessor.implementations import (
            ConfigPreprocessor,
            GraphFlashbackPreprocessor,
            HistoryPreprocessor,
            PerceptionPreprocessor,
            RAGPreprocessor,
            SystemPromptPreprocessor,
            UserInputPreprocessor,
        )

        pm.register(UserInputPreprocessor())
        pm.register(HistoryPreprocessor())
        pm.register(RAGPreprocessor())
        pm.register(GraphFlashbackPreprocessor())
        pm.register(ConfigPreprocessor())
        pm.register(PerceptionPreprocessor())
        pm.register(SystemPromptPreprocessor())
        return pm

    ComponentContainer.register(IPreprocessorManager, create_preprocessor_manager)

    # 注册 PostprocessorManager
    def create_postprocessor_manager():
        pm = PostprocessorManager()
        from services.postprocessor.implementations import (
            NITFilterPostprocessor,
            ThinkingFilterPostprocessor,
        )

        pm.register(NITFilterPostprocessor())
        pm.register(ThinkingFilterPostprocessor())
        return pm

    ComponentContainer.register(IPostprocessorManager, create_postprocessor_manager)

    # 加载 Mods (允许 Mod 覆盖上述组件或注册 EventBus Hook)
    ModManager.load_mods()

    print("[Bootstrap] 核心组件初始化完成。")
