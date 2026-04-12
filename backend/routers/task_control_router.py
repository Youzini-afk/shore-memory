from schemas import InjectInstructionRequest, StandardResponse

router = APIRouter(prefix="/api/tasks", tags=["task_control"])


@router.post("/{session_id}/pause", response_model=StandardResponse)
async def pause_task(session_id: str):
    success = task_manager.pause(session_id)
    if success:
        return StandardResponse(message="任务已暂停")
    raise HTTPException(status_code=404, detail="未找到任务")


@router.post("/{session_id}/resume", response_model=StandardResponse)
async def resume_task(session_id: str):
    success = task_manager.resume(session_id)
    if success:
        return StandardResponse(message="任务已恢复")
    raise HTTPException(status_code=404, detail="未找到任务")


@router.post("/{session_id}/stop", response_model=StandardResponse)
async def stop_task(session_id: str):
    success = task_manager.stop(session_id)
    if success:
        return StandardResponse(message="任务停止请求已发送")
    raise HTTPException(status_code=404, detail="未找到任务")


@router.post("/{session_id}/inject", response_model=StandardResponse)
async def inject_instruction(session_id: str, payload: InjectInstructionRequest):  # noqa: B008
    success = task_manager.inject_instruction(session_id, payload.instruction)
    if success:
        return StandardResponse(message="指令已注入")
    raise HTTPException(status_code=404, detail="未找到任务")


@router.get("/{session_id}/status")
async def get_task_status(session_id: str):
    status = task_manager.get_status(session_id)
    if status:
        return {"status": status}
    # 未找到则假定idle/completed
    return {"status": "idle"}
