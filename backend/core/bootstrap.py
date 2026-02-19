from core.component_container import ComponentContainer
from core.mod_manager import ModManager

# 注意：LLMService 通常是动态实例化的（依赖配置），这里我们注册工厂函数
from interfaces.core import (
    IPostprocessorManager,
    IPreprocessorManager,
    IPromptManager,
)
from interfaces.memory import IMemoryService

# 导入默认实现类
from services.core.prompt_service import PromptManager
from services.memory.memory_service import MemoryService
from services.postprocessor.manager import PostprocessorManager
from services.preprocessor.manager import PreprocessorManager


def bootstrap():
    """
    系统启动引导程序。
    负责注册核心组件、加载 Mod。
    """
    print("[Bootstrap] 开始初始化核心组件...")

    # 1. 注册默认的核心组件
    # 注意：MemoryService 目前使用静态方法，其实例也支持调用这些静态方法
    ComponentContainer.register(IMemoryService, lambda: MemoryService())

    # 注册 PromptManager
    ComponentContainer.register(IPromptManager, lambda: PromptManager())

    # 注册 PreprocessorManager
    # 注意：PreprocessorManager 默认会注册一系列处理器，Mod 可以在此基础上 add/remove
    def create_preprocessor_manager():
        pm = PreprocessorManager()
        # 这里为了保持原有逻辑，我们让 AgentService 初始化时负责 register 具体处理器
        # 或者在这里注册默认的处理器（推荐）
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

    # 2. 加载 Mods (允许 Mod 覆盖上述组件)
    ModManager.load_mods()

    print("[Bootstrap] 核心组件初始化完成。")
