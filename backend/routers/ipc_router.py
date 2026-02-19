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
    # Support both raw body list or wrapped args
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

    # Default: Log and return None (or error if strict)
    # Returning None simulates Electron's void return
    return None
