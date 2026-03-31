from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class QQMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    msg_id: str = Field(index=True)
    session_id: str = Field(index=True)  # 群号或用户 ID
    session_type: str  # group 或 private
    sender_id: str
    sender_name: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    raw_event_json: str = Field(default="{}")
    is_summarized: bool = Field(default=False)  # 新增：标记该消息是否已被总结过
    agent_id: str = Field(default="pero", index=True)  # 所属 Agent ID


class QQUser(SQLModel, table=True):
    user_id: str = Field(primary_key=True)
    nickname: str
    remark: Optional[str] = None
    last_seen: datetime = Field(default_factory=datetime.now)


class QQGroup(SQLModel, table=True):
    group_id: str = Field(primary_key=True)
    group_name: str
    last_active: datetime = Field(default_factory=datetime.now)


class SocialMemory(SQLModel, table=True):
    """
    社交专用长记忆表
    只存储会话总结 (Conversation Summary)
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    content: str  # 记忆内容 (80字左右的总结)

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    source_session_id: str = Field(index=True)  # 来源会话ID (群号或QQ号)
    source_session_type: str  # group 或 private

    # 关键词 (用于串线)
    keywords: str = ""  # 逗号分隔的关键词，如 "上海,漫展,UserB"

    # 向量备份
    embedding_json: str = "[]"

    # 关联消息范围 (用于溯源)
    msg_start_id: Optional[int] = None  # 对应 QQMessage.id
    msg_end_id: Optional[int] = None
    agent_id: str = Field(default="pero", index=True)  # 所属 Agent ID
