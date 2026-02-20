import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from services.core.session_service import enter_work_mode, exit_work_mode

router = APIRouter(prefix="/api/ide", tags=["ide"])


class FileNode(BaseModel):
    name: str
    path: str
    type: str  # "file" 或 "directory"
    children: Optional[List["FileNode"]] = None


class WorkModeRequest(BaseModel):
    task_name: str


class ReadFileRequest(BaseModel):
    path: str


class CreateFileRequest(BaseModel):
    path: str
    is_directory: bool = False


class WriteFileRequest(BaseModel):
    path: str
    content: str


class DeleteFileRequest(BaseModel):
    path: str


class RenameFileRequest(BaseModel):
    path: str
    new_name: str


class ChatRequest(BaseModel):
    messages: List[Dict[str, Any]]
    source: str = "ide"
    session_id: str = "default"


class SkipCommandRequest(BaseModel):
    pid: int


@router.post("/tools/terminal/skip")
async def skip_terminal_command(request: SkipCommandRequest):
    from services.core.realtime_session_manager import realtime_session_manager

    success = realtime_session_manager.skip_command(request.pid)
    if not success:
        raise HTTPException(status_code=404, detail="未找到命令或命令未激活")
    return {"status": "ok"}


@router.post("/chat")
async def chat(request: ChatRequest, session: AsyncSession = Depends(get_session)):  # noqa: B008
    from sqlmodel import select

    from models import Config
    from services.agent.agent_manager import get_agent_manager
    from services.agent.agent_service import AgentService

    agent_service = AgentService(session)
    agent_manager = get_agent_manager()
    agent_id = agent_manager.active_agent_id

    # 检查工作模式状态及是否覆盖session_id
    if request.session_id == "current_work_session":
        session_key = f"current_session_id_{agent_id}"
        config_id = (
            await session.exec(select(Config).where(Config.key == session_key))
        ).first()

        # 未找到则回退到全局（兼容性）
        if not config_id:
            config_id = (
                await session.exec(
                    select(Config).where(Config.key == "current_session_id")
                )
            ).first()

        if config_id and config_id.value.startswith("work_"):
            request.session_id = config_id.value
        else:
            request.session_id = "default"

    # [特性] 实时ReAct广播
    # 广播思考状态至前端(ChatInterface/PetView)
    # 这确保了即使是 IDE 聊天，我们也能通过 WebSocket 获得实时可视化。
    from services.core.realtime_session_manager import realtime_session_manager

    async def on_status(status_type: str, content: str):
        # 广播思考步骤至所有客户端
        if status_type == "thinking":
            await realtime_session_manager.broadcast(
                {
                    "type": "status",
                    "content": "thinking",
                    "detail": content,  # 传递详细思考内容
                }
            )

    # 使用流式响应
    async def generate():
        async for chunk in agent_service.chat(
            request.messages,
            source=request.source,
            session_id=request.session_id,
            on_status=on_status,
        ):
            if chunk:
                yield chunk

        # 生成后重置状态为空闲
        await realtime_session_manager.broadcast({"type": "status", "content": "idle"})

    return StreamingResponse(generate(), media_type="text/plain")


# [重构] 使用workspace_utils支持多代理
from utils.workspace_utils import get_workspace_root  # noqa: E402

# def get_workspace_root(): ... (Removed)


@router.get("/image")
async def get_workspace_image(path: str):
    # 路径相对于工作区 (如 uploads/...)
    # 防止目录遍历
    safe_path = os.path.normpath(path)
    if safe_path.startswith("..") or os.path.isabs(safe_path):
        raise HTTPException(status_code=403, detail="Access denied")

    # [重构] 上传文件移至 backend/data/uploads
    # 检查是否以uploads开头
    if safe_path.startswith("uploads") and (
        len(safe_path) == 7 or safe_path[7] in [os.sep, "/"]
    ):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(current_dir)
        base_dir = os.environ.get("PERO_DATA_DIR", os.path.join(backend_dir, "data"))
    else:
        # 其他图像使用活跃代理工作区
        base_dir = get_workspace_root()

    target_path = os.path.join(base_dir, safe_path)

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(target_path)


@router.get("/files", response_model=List[FileNode])
async def list_files(path: Optional[str] = None):
    """
    列出目录文件，path为空则列出根目录。
    """
    base_dir = get_workspace_root()

    if path:
        target_dir = os.path.abspath(os.path.join(base_dir, path))
        # 防目录遍历安全检查
        if not target_dir.startswith(base_dir):
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        target_dir = base_dir

    if not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail="Directory not found")

    items = []
    try:
        with os.scandir(target_dir) as entries:
            for entry in entries:
                # 跳过隐藏文件和忽略文件夹
                if entry.name.startswith(".") or entry.name in [
                    "__pycache__",
                    "node_modules",
                    "venv",
                    "dist",
                ]:
                    continue

                node = FileNode(
                    name=entry.name,
                    path=os.path.relpath(entry.path, base_dir),
                    type="directory" if entry.is_dir() else "file",
                )
                items.append(node)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None

    # 目录优先排序
    items.sort(key=lambda x: (x.type != "directory", x.name.lower()))
    return items


@router.post("/file/read")
async def read_file(request: ReadFileRequest):
    base_dir = get_workspace_root()
    target_path = os.path.abspath(os.path.join(base_dir, request.path))

    if not target_path.startswith(base_dir):
        raise HTTPException(status_code=403, detail="拒绝访问")

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="未找到文件")

    try:
        # 检查文件大小 (限1MB防卡死)
        if os.path.getsize(target_path) > 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件过大")

        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="不支持二进制文件") from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from None


@router.post("/file/create")
async def create_file_or_dir(request: CreateFileRequest):
    base_dir = get_workspace_root()
    target_path = os.path.abspath(os.path.join(base_dir, request.path))

    if not target_path.startswith(base_dir):
        raise HTTPException(status_code=403, detail="拒绝访问")

    if os.path.exists(target_path):
        raise HTTPException(status_code=400, detail="路径已存在")

    try:
        if request.is_directory:
            os.makedirs(target_path)
        else:
            # 自动创建父目录
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("")
        return {"status": "success", "path": request.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/file/write")
async def write_file(request: WriteFileRequest):
    base_dir = get_workspace_root()
    target_path = os.path.abspath(os.path.join(base_dir, request.path))

    if not target_path.startswith(base_dir):
        raise HTTPException(status_code=403, detail="拒绝访问")

    try:
        # 自动创建父目录
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(request.content)
        return {"status": "success", "path": request.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/file/delete")
async def delete_file(request: DeleteFileRequest):
    base_dir = get_workspace_root()
    target_path = os.path.abspath(os.path.join(base_dir, request.path))

    if not target_path.startswith(base_dir):
        raise HTTPException(status_code=403, detail="拒绝访问")

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="未找到路径")

    try:
        if os.path.isdir(target_path):
            import shutil

            shutil.rmtree(target_path)
        else:
            os.remove(target_path)
        return {"status": "success", "path": request.path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/file/rename")
async def rename_file(request: RenameFileRequest):
    base_dir = get_workspace_root()
    target_path = os.path.abspath(os.path.join(base_dir, request.path))

    if not target_path.startswith(base_dir):
        raise HTTPException(status_code=403, detail="拒绝访问")

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail="未找到路径")

    parent_dir = os.path.dirname(target_path)
    new_path = os.path.join(parent_dir, request.new_name)

    if os.path.exists(new_path):
        raise HTTPException(status_code=400, detail="新名称已存在")

    try:
        os.rename(target_path, new_path)
        return {
            "status": "success",
            "old_path": request.path,
            "new_path": request.new_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/work_mode/enter")
async def api_enter_work_mode(
    request: WorkModeRequest,
    session: AsyncSession = Depends(get_session),  # noqa: B008
):
    # 注入Session至SessionOps上下文
    from services.core.session_service import set_current_session_context

    set_current_session_context(session)

    result = await enter_work_mode(request.task_name)
    return {"message": result}


@router.post("/work_mode/exit")
async def api_exit_work_mode(session: AsyncSession = Depends(get_session)):  # noqa: B008
    # 注入Session
    from services.core.session_service import set_current_session_context

    set_current_session_context(session)

    result = await exit_work_mode()
    return {"message": result}


@router.post("/work_mode/abort")
async def api_abort_work_mode(session: AsyncSession = Depends(get_session)):  # noqa: B008
    """
    退出工作模式不生成总结（静默退出）。
    """
    from sqlmodel import select

    from core.nit_manager import get_nit_manager
    from models import Config
    from services.agent.agent_manager import get_agent_manager

    try:
        agent_manager = get_agent_manager()
        agent_id = agent_manager.active_agent_id
        session_key = f"current_session_id_{agent_id}"

        config_id = (
            await session.exec(select(Config).where(Config.key == session_key))
        ).first()

        # 兜底策略
        if not config_id:
            config_id = (
                await session.exec(
                    select(Config).where(Config.key == "current_session_id")
                )
            ).first()

        if config_id and config_id.value.startswith("work_"):
            config_id.value = "default"
            await session.commit()

            # [NIT] 停用工作工具链
            try:
                get_nit_manager().set_category_status("work", False)
            except Exception as nit_e:
                print(f"[IDE Router] 停用 NIT 工作分类失败: {nit_e}")

            return {"message": "工作模式已中止（未生成总结）"}
        else:
            return {"message": "不在工作模式中"}
    except Exception as e:
        return {"message": f"中止工作模式出错: {e}"}
