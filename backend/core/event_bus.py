import inspect
import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class EventBus:
    """
    全局事件总线 (Event Bus)
    允许 MOD 订阅系统核心事件，实现轻量级 Hook。
    支持同步和异步处理器。
    """

    _instance = None
    _listeners: Dict[str, List[Callable]] = defaultdict(list)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
        return cls._instance

    @classmethod
    def subscribe(cls, event_name: str, handler: Callable):
        """
        订阅一个事件。
        :param event_name: 事件名称 (例如 "memory.save.pre")
        :param handler: 处理函数 (可以是 async 或 sync)
        """
        if handler not in cls._listeners[event_name]:
            cls._listeners[event_name].append(handler)
            logger.debug(f"[EventBus] '{event_name}' 增加订阅者: {handler.__name__}")

    @classmethod
    def unsubscribe(cls, event_name: str, handler: Callable):
        """
        取消订阅。
        """
        if handler in cls._listeners[event_name]:
            cls._listeners[event_name].remove(handler)
            logger.debug(f"[EventBus] '{event_name}' 移除订阅者: {handler.__name__}")

    @classmethod
    async def publish(cls, event_name: str, *args, **kwargs) -> Any:
        """
        发布一个事件 (异步)。
        依次执行所有订阅者。
        如果处理器返回了值且不为 None，可能会被用作修改后的数据（取决于具体事件约定）。
        目前简单的实现是：只执行，忽略返回值（Hook 模式通常通过修改传入的可变对象来产生影响）。
        """
        listeners = cls._listeners.get(event_name, [])
        if not listeners:
            return

        # logger.debug(f"[EventBus] 触发事件: {event_name}")

        results = []
        for handler in listeners:
            try:
                if inspect.iscoroutinefunction(handler):
                    res = await handler(*args, **kwargs)
                else:
                    res = handler(*args, **kwargs)
                if res is not None:
                    results.append(res)
            except Exception as e:
                logger.error(
                    f"[EventBus] 事件 '{event_name}' 处理器 '{handler.__name__}' 执行出错: {e}",
                    exc_info=True,
                )

        return results
