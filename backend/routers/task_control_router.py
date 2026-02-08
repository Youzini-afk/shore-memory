from typing import Dict

from fastapi import APIRouter, Body, HTTPException

from services.task_manager import task_manager

router = APIRouter(prefix="/api/task", tags=["task_control"])


@router.post("/{session_id}/pause")
async def pause_task(session_id: str):
    success = task_manager.pause(session_id)
    if success:
        return {"status": "success", "message": "Task paused"}
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/{session_id}/resume")
async def resume_task(session_id: str):
    success = task_manager.resume(session_id)
    if success:
        return {"status": "success", "message": "Task resumed"}
    raise HTTPException(status_code=404, detail="Task not found")


@router.post("/{session_id}/inject")
async def inject_instruction(session_id: str, payload: Dict[str, str] = Body(...)):
    instruction = payload.get("instruction")
    if not instruction:
        raise HTTPException(status_code=400, detail="Instruction is required")

    success = task_manager.inject_instruction(session_id, instruction)
    if success:
        return {"status": "success", "message": "Instruction injected"}
    raise HTTPException(status_code=404, detail="Task not found")


@router.get("/{session_id}/status")
async def get_task_status(session_id: str):
    status = task_manager.get_status(session_id)
    if status:
        return {"status": status}
    # If not found, assume idle/completed
    return {"status": "idle"}
