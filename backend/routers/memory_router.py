from fastapi import APIRouter, Depends, HTTPException, Body
from sqlmodel.ext.asyncio.session import AsyncSession
from database import get_session
from services.memory_importer import MemoryImporter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/memory", tags=["memory"])

class ImportStoryRequest(BaseModel):
    story: str
    agent_id: Optional[str] = "pero"

@router.post("/import_story")
async def import_story(
    request: ImportStoryRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Import a story/diary to initialize long-term memory.
    Extracts events using LLM and saves them as a sequential memory chain.
    """
    importer = MemoryImporter(session)
    result = await importer.import_story(request.story, request.agent_id)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result
