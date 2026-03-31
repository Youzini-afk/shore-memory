"""
External Plugin Router
=======================
提供外部插件的注册、注销、查询 API 端点。
"""

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mods._external_plugins.service import get_external_plugin_registry

router = APIRouter(prefix="/api/plugins", tags=["external-plugins"])


class PluginRegisterRequest(BaseModel):
    """外部插件注册请求体"""

    plugin_id: str = Field(..., description="插件唯一标识符")
    name: str = Field(..., description="插件名称")
    url: str = Field(..., description="插件的 HTTP 基地址")
    description: str = Field(default="", description="插件描述")
    version: str = Field(default="0.0.1", description="插件版本号")
    hooks: List[str] = Field(
        default_factory=list,
        description="要订阅的 Hook 事件（可修改 ctx），如 memory.save.pre",
    )
    events: List[str] = Field(
        default_factory=list,
        description="要订阅的只读事件（仅通知），如 memory.save.post",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "plugin_id": "my_reminder",
                    "name": "定时提醒插件",
                    "url": "http://localhost:9527",
                    "description": "一个简单的提醒插件",
                    "version": "1.0.0",
                    "hooks": ["memory.save.pre"],
                    "events": ["memory.save.post"],
                }
            ]
        }
    }


@router.post("/register")
async def register_plugin(req: PluginRegisterRequest):
    """
    注册一个外部插件。

    外部插件是一个独立的 HTTP 服务进程，通过此接口向 PeroCore 注册。
    注册后：
    - hooks 中的事件会通过 POST {url}/hook/{event_name} 调用，插件可修改 ctx
    - events 中的事件会通过 POST {url}/event/{event_name} 通知，插件不可修改 ctx
    - PeroCore 会定期访问 GET {url}/health 检测插件是否在线
    """
    registry = get_external_plugin_registry()
    plugin = await registry.register(req.model_dump())
    return {
        "status": "success",
        "message": f"插件 {plugin.name} ({plugin.plugin_id}) 注册成功",
        "plugin": registry.get_plugin(plugin.plugin_id),
    }


@router.delete("/unregister/{plugin_id}")
async def unregister_plugin(plugin_id: str):
    """注销一个外部插件"""
    registry = get_external_plugin_registry()
    success = await registry.unregister(plugin_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"插件 {plugin_id} 未找到")
    return {"status": "success", "message": f"插件 {plugin_id} 已注销"}


@router.get("/list")
async def list_plugins():
    """列出所有已注册的外部插件"""
    registry = get_external_plugin_registry()
    return {"plugins": registry.list_plugins()}


@router.get("/info/{plugin_id}")
async def get_plugin_info(plugin_id: str):
    """获取单个插件的详细信息"""
    registry = get_external_plugin_registry()
    info = registry.get_plugin(plugin_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"插件 {plugin_id} 未找到")
    return info


class NotificationRequest(BaseModel):
    """通知推送请求体"""

    title: str = Field(..., description="通知标题")
    body: str = Field(default="", description="通知正文")
    level: str = Field(
        default="info", description="级别: info | success | warning | error"
    )
    duration: int = Field(default=5000, description="显示时长(ms)，0 = 不自动关闭")
    actions: List[dict] = Field(
        default_factory=list,
        description='操作按钮 [{"label": "查看", "url": "/memory"}]',
    )
    source: str = Field(default="external_plugin", description="来源标识")


@router.post("/notify")
async def push_notification(req: NotificationRequest):
    """
    向前端推送通知。

    MOD 和外部插件均可调用此接口，在前端弹出非模态通知框。
    """
    from services.core.gateway_hub import gateway_hub

    await gateway_hub.broadcast_notification(
        title=req.title,
        body=req.body,
        level=req.level,
        duration=req.duration,
        actions=req.actions if req.actions else None,
        source=req.source,
    )
    return {"status": "success", "message": "通知已推送"}
