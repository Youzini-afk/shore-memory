from typing import Optional, Protocol, runtime_checkable

from sqlmodel.ext.asyncio.session import AsyncSession

from models import Memory


@runtime_checkable
class IMemoryService(Protocol):
    """
    记忆服务接口。
    负责长期记忆的存储、检索和管理。
    """

    async def save_memory(
        self,
        session: AsyncSession,
        content: str,
        tags: str = "",
        clusters: str = "",
        importance: int = 1,
        base_importance: float = 1.0,
        sentiment: str = "neutral",
        msg_timestamp: Optional[str] = None,
        source: str = "desktop",
        memory_type: str = "event",
        agent_id: str = "pero",
    ) -> Memory:
        """
        保存一条记忆。
        """
        ...
