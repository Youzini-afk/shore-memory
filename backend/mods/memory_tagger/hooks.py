"""
EventBus Hook 处理函数
======================
第一层扩展：监听系统事件，修改或响应。
"""

import logging
from datetime import datetime

logger = logging.getLogger("pero.mod.memory_tagger")


async def on_memory_save_pre(ctx):
    """
    Hook: memory.save.pre
    记忆保存前触发。可修改 ctx 中的字段。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    existing_tags = ctx.get("tags", "")
    new_tag = f"tagged_at:{now}"

    if existing_tags:
        ctx["tags"] = f"{existing_tags},{new_tag}"
    else:
        ctx["tags"] = new_tag

    logger.debug(f"[MemoryTagger] Hook memory.save.pre → 添加标签: {new_tag}")


async def on_prompt_build_post(ctx):
    """
    Hook: prompt.build.post
    Prompt 构建后触发。可修改最终消息列表。
    """
    messages = ctx.get("messages", [])
    if not messages:
        return

    # 示例：在倒数第二条消息前插入补充信息
    note = {
        "role": "system",
        "content": f"[MemoryTagger] 当前时间: {datetime.now().strftime('%H:%M')}",
    }
    messages.insert(-1, note)
    logger.debug("[MemoryTagger] Hook prompt.build.post → 注入时间上下文")
