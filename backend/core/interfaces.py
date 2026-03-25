"""
核心接口定义
============
MOD 第二层扩展（管道注册）所依赖的接口约定。
仅 PreprocessorManager 和 PostprocessorManager 通过 IoC 容器管理。
"""

from typing import Any, AsyncIterable, Dict, Protocol, runtime_checkable


@runtime_checkable
class IPreprocessorManager(Protocol):
    """预处理器管理接口"""

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]: ...
    def register(self, preprocessor: Any): ...


@runtime_checkable
class IPostprocessorManager(Protocol):
    """后处理器管理接口"""

    async def process(self, content: str, context: Dict[str, Any]) -> str: ...
    async def process_stream(
        self, stream: AsyncIterable[str], context: Dict[str, Any]
    ) -> AsyncIterable[str]: ...
    def register(self, postprocessor: Any): ...
