"""
记忆标注器 — 外部插件服务
==========================
第三层扩展：独立运行的 HTTP 服务。

此文件不会被 PeroCore 主进程加载，需要独立启动：
    python mods/memory_tagger/external/server.py

功能：
  1. 监听 memory.save.post 事件 → 将保存成功的记忆同步到本地日志
  2. 提供独立的查询端点 → /stats, /logs
  3. 健康检查 → /health
"""

import time
from typing import Dict, List

import httpx
import uvicorn
from fastapi import FastAPI

# ─── 配置 ───
PLUGIN_ID = "memory_tagger_ext"
PLUGIN_NAME = "记忆标注器-外部服务"
PLUGIN_URL = "http://localhost:9527"
PERO_URL = "http://localhost:9120"

# ─── 状态 ───
app = FastAPI(title=PLUGIN_NAME)
sync_log: List[Dict] = []


# ─── 生命周期 ───


@app.on_event("startup")
async def register_to_pero():
    """启动时向 PeroCore 注册"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{PERO_URL}/api/plugins/register",
                json={
                    "plugin_id": PLUGIN_ID,
                    "name": PLUGIN_NAME,
                    "url": PLUGIN_URL,
                    "description": "记忆标注器的外部数据同步服务",
                    "version": "1.0.0",
                    "hooks": [],
                    "events": ["memory.save.post"],
                },
            )
            if resp.status_code == 200:
                print(f"✔ 已向 PeroCore 注册: {resp.json()}")
            else:
                print(f"✖ 注册失败: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"✖ 无法连接 PeroCore: {e}")
            print("  请确保 PeroCore 正在运行。插件将在心跳恢复后自动重连。")


# ─── 事件端点（PeroCore 会调用这些）───


@app.post("/event/memory.save.post")
async def on_memory_saved(body: dict):
    """事件通知：记忆保存后"""
    ctx = body.get("ctx", {})
    sync_log.append(
        {
            "action": "memory_saved",
            "content_preview": str(ctx)[:100],
            "timestamp": time.time(),
        }
    )
    print(f"[{PLUGIN_NAME}] 收到记忆保存通知")
    return {"status": "ok"}


# ─── 插件自己的独立功能 ───


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "plugin_id": PLUGIN_ID}


@app.get("/stats")
async def get_stats():
    """查询同步统计"""
    return {
        "total_synced": len(sync_log),
        "recent": sync_log[-10:],
    }


@app.get("/logs")
async def get_logs():
    """查询所有日志"""
    return {"logs": sync_log}


# ─── 启动 ───

if __name__ == "__main__":
    print(f"🐱 {PLUGIN_NAME} 正在启动...")
    print(f"   插件地址: {PLUGIN_URL}")
    print(f"   PeroCore: {PERO_URL}")
    uvicorn.run(app, host="0.0.0.0", port=9527)
