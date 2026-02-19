import threading
from typing import Any, Callable, Dict, Type, TypeVar

T = TypeVar("T")


class ComponentContainer:
    """
    轻量级依赖注入容器 (IoC Container)。
    用于管理系统核心组件的生命周期和依赖关系，支持 Mod 在运行时替换核心组件。
    """

    _factories: Dict[Type, Callable[[], Any]] = {}
    _instances: Dict[Type, Any] = {}
    _lock = threading.RLock()

    @classmethod
    def register(
        cls, interface: Type[T], factory: Callable[[], T], singleton: bool = True
    ):
        """
        注册一个组件工厂。

        Args:
            interface: 组件的接口类型 (Protocol 或 Abstract Base Class)
            factory: 创建组件实例的函数
            singleton: 是否为单例模式 (默认 True)
        """
        with cls._lock:
            cls._factories[interface] = factory
            # 如果已存在实例且注册了新工厂，清除旧实例以便下次获取时重新创建
            if interface in cls._instances:
                del cls._instances[interface]

    @classmethod
    def get(cls, interface: Type[T]) -> T:
        """
        获取组件实例。
        如果组件未注册，抛出异常。
        """
        with cls._lock:
            if interface in cls._instances:
                return cls._instances[interface]

            if interface not in cls._factories:
                raise ValueError(
                    f"组件 {interface.__name__} 未注册。请检查是否已在 Mod 或系统初始化代码中注册。"
                )

            instance = cls._factories[interface]()

            # 默认都是单例，除非未来有特殊需求
            cls._instances[interface] = instance
            return instance

    @classmethod
    def override(cls, interface: Type[T], new_factory: Callable[[], T]):
        """
        [Mod 专用] 覆盖现有的组件实现。
        """
        cls.register(interface, new_factory)
