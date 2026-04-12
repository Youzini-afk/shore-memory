from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# --- 通用基础模型 ---


class ToggleRequest(BaseModel):
    """通用的布尔值切换请求"""

    enabled: bool


class InjectInstructionRequest(BaseModel):
    instruction: str


class StandardResponse(BaseModel):
    """通用的操作执行响应"""

    status: str = "success"
    message: str = "操作成功"
    data: Optional[Dict[str, Any]] = None


# --- 配置域 (Config) ---


class UpdateConfigsRequest(BaseModel):
    """批量更新配置请求"""

    configs: Dict[str, str]


class SetMemoryConfigRequest(BaseModel):
    """设置记忆系统配置请求"""

    config: Dict[str, Any]


class PetStateAgentInfo(BaseModel):
    id: str
    name: str


class PetStateResponse(BaseModel):
    """宠物状态响应"""

    id: Optional[int] = None
    agent_id: str
    mood: str
    vibe: str
    mind: str
    click_messages_json: str
    idle_messages_json: str
    back_messages_json: str
    active_agent: Optional[PetStateAgentInfo] = None


# --- 模型域 (Models) ---


class CreateModelRequest(BaseModel):
    name: str
    provider: str
    api_key: str
    api_base: str
    model_name: str
    is_active: bool = False
    config_json: Optional[str] = "{}"


class UpdateModelRequest(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None
    config_json: Optional[str] = None


class FetchRemoteModelsRequest(BaseModel):
    api_key: str
    api_base: str = "https://api.openai.com"
    provider: str = "openai"


class RemoteModelsResponse(BaseModel):
    models: List[str]


# --- 聊天与记忆域 (Chat & Memory) ---


class UpdateChatLogRequest(BaseModel):
    """更新聊天记录请求"""

    content: str


class ChatLogResponse(BaseModel):
    """对话日志响应模型"""

    id: int
    session_id: str
    source: str
    role: str
    content: str
    raw_content: Optional[str] = None
    timestamp: datetime
    metadata_json: str
    pair_id: Optional[str] = None
    sentiment: Optional[str] = None
    importance: Optional[int] = None
    analysis_status: str
    retry_count: int
    last_error: Optional[str] = None


class AddMemoryRequest(BaseModel):
    """手动添加记忆请求"""

    content: str
    tags: Optional[str] = ""
    importance: Optional[int] = 1
    msgTimestamp: Optional[str] = None
    source: Optional[str] = "desktop"
    type: Optional[str] = "event"


# --- 语音域 (Voice) ---


class VoiceConfigData(BaseModel):
    """语音配置详细模型"""

    name: str
    type: str  # "stt" or "tts"
    provider: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    model: Optional[str] = None
    config_json: Optional[str] = "{}"
    is_active: Optional[bool] = False


class TTSRequest(BaseModel):
    """文字转语音请求"""

    text: str


# --- 统计与运维域 (Stats & Maintenance) ---


class StatsOverviewResponse(BaseModel):
    """统计概览响应"""

    total_memories: int
    total_logs: int
    total_tasks: int


class MaintenanceRecordResponse(BaseModel):
    """维护记录响应"""

    id: int
    timestamp: str
    operation: str
    target_count: int
    details_json: str


class ScheduledTaskResponse(BaseModel):
    """计划任务响应"""

    id: int
    type: str
    time: str
    content: str
    is_triggered: bool
    agent_id: str


# --- 资源模型 (用于返回对象列表) ---


class MemoryGraphNode(BaseModel):
    id: int
    content: str
    sentiment: Optional[str] = None
    importance: Optional[int] = 1
    category: Optional[str] = None
    value: float = 1.0
    full_content: Optional[str] = None


class MemoryGraphEdge(BaseModel):
    source: int
    target: int
    value: float = 1.0
    relation_type: Optional[str] = None


class MemoryGraphResponse(BaseModel):
    """记忆图谱响应"""

    nodes: List[MemoryGraphNode]
    edges: List[MemoryGraphEdge]


class ImportStoryRequest(BaseModel):
    """Story 导入请求"""

    story: str
    agent_id: str = "pero"
