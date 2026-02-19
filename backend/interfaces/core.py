from typing import Any, AsyncIterable, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class ILLMService(Protocol):
    """LLM 服务接口"""

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        tools: List[Dict] = None,
        response_format: Optional[Dict] = None,
        timeout: float = 300.0,
    ) -> Dict[str, Any]: ...


@runtime_checkable
class IPromptManager(Protocol):
    """提示词管理接口"""

    async def get_system_prompt(
        self,
        agent_id: str = "pero",
        variables: Dict[str, Any] = None,
        session_context: Dict[str, Any] = None,
    ) -> str: ...


@runtime_checkable
class IScorerService(Protocol):
    """评分与总结服务接口"""

    async def score_and_summarize(self, log_id: int, agent_id: str = "pero"): ...


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
