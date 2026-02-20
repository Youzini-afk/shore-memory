import os
import platform

import psutil
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/ipc", tags=["ipc"])


class IpcPayload(BaseModel):
    args: list = []


@router.post("/{command}")
async def handle_ipc_command(command: str, payload: list | None = None):
    # 支持原始 body 列表或包装的 args
    # args = payload if payload else []

    if command == "get_system_stats":
        return {
            "cpu": psutil.cpu_percent(interval=None),
            "memory": psutil.virtual_memory().percent,
            "platform": platform.system(),
            "arch": platform.machine(),
        }

    if command == "get-app-version":
        return "0.6.3-docker"

    if command == "get-platform":
        return (
            "linux"
            if os.environ.get("PERO_ENV") == "server"
            else platform.system().lower()
        )

    if command == "ping":
        return "pong"

    # 默认: 记录日志并返回 None (如果严格模式则报错)
    # 返回 None 模拟 Electron 的 void 返回
    return None
