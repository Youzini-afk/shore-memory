from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .social_service import get_social_service
import logging
import json

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
        logger.info("[Social] WebSocket connected (No X-Self-ID, using as default/fallback).")
    
    try:
        while True:
            data = await websocket.receive_text()
            # 仅打印简短日志证明收到数据，避免刷屏
            if len(data) > 0:
                # 尝试简单解析一下类型，方便调试
                try:
                    preview = json.loads(data)
                    ptype = preview.get("post_type", "unknown")
                    
                    # 尝试细化 unknown 类型的显示 (例如 meta_event)
                    sub_type = ""
                    if ptype == "meta_event":
                        sub_type = f" ({preview.get('meta_event_type', '')})"
                    elif ptype == "notice":
                        sub_type = f" ({preview.get('notice_type', '')})"
                    elif ptype == "request":
                        sub_type = f" ({preview.get('request_type', '')})"
                    
                    if ptype != "meta_event": # 忽略心跳
                        logger.info(f"[Social-WS] 收到事件: {ptype}{sub_type}, length={len(data)}")
                    else:
                        # 对于心跳，仅使用 debug 级别，防止刷屏
                        logger.debug(f"[Social-WS] 收到心跳: {preview.get('meta_event_type')}")
                except:
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
