"""
记忆标注器 MOD — 三层扩展体系示例
==================================

演示如何在一个 MOD 中同时使用 EventBus Hook、管道注册、外部插件三层能力。
"""

import asyncio
import logging

from core.component_container import ComponentContainer
from core.event_bus import EventBus
from core.interfaces import IPreprocessorManager

from .hooks import on_memory_save_pre, on_prompt_build_post
from .processors import TimeTagPreprocessor

logger = logging.getLogger("pero.mod.memory_tagger")


def init():
    """
    MOD 入口：一个 init()，三层全注册。
    """

    # ── 第一层：EventBus Hook ──
    # 监听记忆保存前事件，自动添加时间标签
    EventBus.subscribe("memory.save.pre", on_memory_save_pre)
    # 监听 Prompt 构建后事件，注入补充上下文
    EventBus.subscribe("prompt.build.post", on_prompt_build_post)
    logger.info("[MemoryTagger] EventBus Hook 已注册")

    # ── 第二层：管道注册 ──
    # 在预处理管道中插入一个时间标签处理器
    pm = ComponentContainer.get(IPreprocessorManager)
    pm.register(TimeTagPreprocessor())
    logger.info("[MemoryTagger] 管道处理器已注册")

    # ── 第三层：注册配套的外部插件 ──
    # 外部服务需要独立启动 (python mods/memory_tagger/external/server.py)
    # 这里只是在主进程启动时尝试注册它（如果外部服务已在运行）
    asyncio.get_event_loop().call_soon(
        lambda: asyncio.ensure_future(_try_register_external())
    )

    print("[MemoryTagger] ✔ MOD 初始化完成 (三层扩展)")


async def _try_register_external():
    """尝试注册配套的外部插件（如果它已在运行）"""
    try:
        from mods._external_plugins.service import get_external_plugin_registry

        registry = get_external_plugin_registry()
        await registry.register({
            "plugin_id": "memory_tagger_ext",
            "name": "记忆标注器-外部服务",
            "url": "http://localhost:9527",
            "description": "记忆标注器的外部数据同步服务",
            "version": "1.0.0",
            "hooks": [],
            "events": ["memory.save.post"],  # 只监听保存后事件
        })
        logger.info("[MemoryTagger] 外部插件已注册")
    except Exception as e:
        logger.debug(
            f"[MemoryTagger] 外部插件注册跳过 (可能未启动): {e}"
        )
