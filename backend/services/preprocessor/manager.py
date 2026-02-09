import logging
from typing import Any, Dict, List

from .base import BasePreprocessor

logger = logging.getLogger(__name__)


class PreprocessorManager:
    """
    管理并执行预处理器管道。
    """

    def __init__(self):
        self.preprocessors: List[BasePreprocessor] = []

    def register(self, preprocessor: BasePreprocessor):
        """将新的预处理器注册到管道末尾。"""
        self.preprocessors.append(preprocessor)
        # logger.info(f"Registered preprocessor: {preprocessor.name}")

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        按顺序通过所有注册的预处理器运行上下文。
        """
        current_context = context
        for processor in self.preprocessors:
            try:
                # logger.debug(f"Running preprocessor: {processor.name}")
                current_context = await processor.process(current_context)
            except Exception as e:
                logger.error(f"预处理器 {processor.name} 出错: {e}", exc_info=True)
                # 决定是停止还是继续。目前我们继续但记录错误。
                # 在健壮的系统中，我们可能希望在上下文中标记这一点。
                current_context["errors"] = current_context.get("errors", []) + [
                    f"{processor.name}: {str(e)}"
                ]

        return current_context
