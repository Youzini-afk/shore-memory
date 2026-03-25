"""
管道处理器
==========
第二层扩展：在预处理/后处理管道中插入处理节点。
"""

import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger("pero.mod.memory_tagger")


class TimeTagPreprocessor:
    """
    预处理器：在用户输入的 variables 中注入当前时间标签。
    用于让 LLM 感知到当前时间（如果其他预处理器没有做）。

    实现 IPreprocessorManager.register() 要求的接口：
    - 必须有 process(context) -> context 方法
    - 可选 priority 属性（数值越小越先执行）
    """

    priority = 90  # 靠后执行，不干扰核心预处理器

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        variables = context.setdefault("variables", {})

        # 只在没有时间信息时注入
        if "current_time" not in variables:
            variables["current_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.debug("[MemoryTagger] Preprocessor → 注入 current_time")

        return context
