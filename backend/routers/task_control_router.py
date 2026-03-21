from typing import Dict

from fastapi import APIRouter, Body, HTTPException

from services.agent.task_manager import task_manager

router = APIRouter(prefix="/api/task", tags=["task_control"])


@router.post("/{session_id}/pause")
async def pause_task(session_id: str):
    success = task_manager.pause(session_id)
    if success:
        return {"status": "success", "message": "任务已暂停"}
    raise HTTPException(status_code=404, detail="未找到任务")


@router.post("/{session_id}/resume")
async def resume_task(session_id: str):
    success = task_manager.resume(session_id)
    if success:
        return {"status": "success", "message": "任务已恢复"}
    raise HTTPException(status_code=404, detail="未找到任务")


@router.post("/{session_id}/stop")
async def stop_task(session_id: str):
    success = task_manager.stop(session_id)
    if success:
        return {"status": "success", "message": "任务停止请求已发送"}
    raise HTTPException(status_code=404, detail="未找到任务")


@router.post("/{session_id}/inject")
async def inject_instruction(session_id: str, payload: Dict[str, str] = Body(...)):  # noqa: B008
    instruction = payload.get("instruction")
    if not instruction:
        raise HTTPException(status_code=400, detail="必须提供指令")

    success = task_manager.inject_instruction(session_id, instruction)
    if success:
        return {"status": "success", "message": "指令已注入"}
    raise HTTPException(status_code=404, detail="未找到任务")


@router.get("/{session_id}/status")
async def get_task_status(session_id: str):
    status = task_manager.get_status(session_id)
    if status:
        return {"status": status}
    # 未找到则假定idle/completed
    return {"status": "idle"}
