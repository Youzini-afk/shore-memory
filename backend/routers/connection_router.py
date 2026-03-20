import os
import socket

from fastapi import APIRouter

router = APIRouter(prefix="/api/connection", tags=["connection"])


def get_local_ip():
    """获取本机在局域网中的 IP 地址。"""
    try:
        # 创建一个 UDP 套接字，不需要真正连接
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 尝试连接到一个外部 IP (这里用 Google DNS)，不会真正发送数据
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@router.get("/info")
async def get_connection_info():
    """获取用于远程连接的信息，包括 IP 和 Token。"""
    ip = get_local_ip()
    # 优先从环境变量获取最新 Token，这是由 Electron 主进程传入的
    token = os.getenv("GATEWAY_TOKEN", "pero_default_token")

    return {
        "ip": ip,
        "port": 9120,  # 默认后端端口
        "token": token,
        "full_url": f"http://{ip}:9120",
    }
