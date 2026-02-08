import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .social_service import get_social_service

router = APIRouter(prefix="/api/social", tags=["social"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_social_status():
    service = get_social_service()
    if not service.enabled:
        return {"enabled": False}

    status = await service.get_connection_status()
    return {"enabled": True, **status}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    service = get_social_service()

    # Check if social mode is enabled
    if not service.enabled:
        await websocket.close(code=1008, reason="Social mode disabled")
        return

    # [Multi-Agent Support] Extract X-Self-ID from headers
    # NapCat sends X-Self-ID to indicate which QQ account this connection belongs to.
    x_self_id = websocket.headers.get("x-self-id")

    # Register connection
    service.register_connection(x_self_id, websocket)

    if x_self_id:
        logger.info(f"[Social] WebSocket connected for QQ: {x_self_id}")
    else:
        logger.info(
            "[Social] WebSocket connected (No X-Self-ID, using as default/fallback)."
        )

    try:
        while True:
            data = await websocket.receive_text()
            # 仅打印简短日志证明收到数据，避免刷屏
            if len(data) > 0:
                # 尝试简单解析一下类型，方便调试
                try:
                    preview = json.loads(data)
                    ptype = preview.get("post_type")

                    # 尝试细化事件类型的显示
                    sub_type = ""
                    if ptype:
                        # 标准 OneBot 事件
                        if ptype == "meta_event":
                            sub_type = f" ({preview.get('meta_event_type', '')})"
                        elif ptype == "notice":
                            sub_type = f" ({preview.get('notice_type', '')})"
                        elif ptype == "request":
                            sub_type = f" ({preview.get('request_type', '')})"
                    else:
                        # 无 post_type，可能是 API 响应或其他
                        if "status" in preview:
                            ptype = "api_response"
                            echo_info = (
                                f", echo: {preview.get('echo')}"
                                if "echo" in preview
                                else ""
                            )
                            sub_type = f" (status: {preview.get('status')}{echo_info})"
                        else:
                            ptype = "unknown"
                            # 记录键名以供调试
                            keys = list(preview.keys())
                            sub_type = f" (keys: {keys})"

                    if ptype != "meta_event":  # 忽略心跳
                        logger.info(
                            f"[Social-WS] 收到事件: {ptype}{sub_type}, length={len(data)}"
                        )
                    else:
                        # 对于心跳，仅使用 debug 级别，防止刷屏
                        logger.debug(
                            f"[Social-WS] 收到心跳: {preview.get('meta_event_type')}"
                        )
                except Exception:
                    logger.debug(f"[Social-WS] 收到数据: {len(data)} chars")

            # Dispatch to service for async processing
            await service.handle_raw_event(data)

    except WebSocketDisconnect:
        logger.info(f"[Social] WebSocket disconnected (QQ: {x_self_id}).")
        service.unregister_connection(x_self_id)
    except Exception as e:
        logger.error(f"[Social] WebSocket error: {e}", exc_info=True)
        if x_self_id:
            service.unregister_connection(x_self_id)
        elif service.active_ws == websocket:
            service.active_ws = None
