from datetime import datetime
from typing import Any, Dict, List, Optional

import dateparser
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import ScheduledTask
from services.scheduler_service import scheduler_service

router = APIRouter()


@router.post("/sync")
async def sync_reminders(payload: Dict[str, Any] = Body(...)):
    """
    接收移动端/其他端同步过来的 XML 解析结果，将其注册到后端调度器。
    Payload example:
    {
        "source": "mobile",
        "reminders": [
            {
                "content": "提醒我喝水",
                "time": "2024-01-01 12:00:00"
            }
        ]
    }
    """
    reminders = payload.get("reminders", [])
    source = payload.get("source", "unknown")

    results = []

    for item in reminders:
        content = item.get("content")
        time_str = item.get("time")
        repeat = item.get("repeat")  # Optional repeat rule

        if not content or not time_str:
            continue

        try:
            # 解析时间
            trigger_time = dateparser.parse(time_str)
            if not trigger_time:
                results.append(
                    {"status": "error", "message": f"Invalid time format: {time_str}"}
                )
                continue

            if trigger_time <= datetime.now() and not repeat:
                results.append({"status": "skipped", "message": "Time is in the past"})
                continue

            # 添加到调度器
            job_id = scheduler_service.add_reminder(
                trigger_time, content, repeat=repeat
            )
            results.append({"status": "success", "job_id": job_id, "content": content})

        except Exception as e:
            results.append({"status": "error", "message": str(e)})

    return {"status": "completed", "results": results}


@router.get("/tasks", response_model=List[ScheduledTask])
async def get_tasks(
    agent_id: Optional[str] = None, session: AsyncSession = Depends(get_session)
):
    statement = select(ScheduledTask).where(ScheduledTask.is_triggered == False)
    if agent_id:
        statement = statement.where(ScheduledTask.agent_id == agent_id)
    return (await session.exec(statement)).all()


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: int, session: AsyncSession = Depends(get_session)):
    try:
        task = await session.get(ScheduledTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        await session.delete(task)
        await session.commit()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check")
async def check_tasks(session: AsyncSession = Depends(get_session)):
    now = datetime.now()
    tasks = (
        await session.exec(
            select(ScheduledTask).where(ScheduledTask.is_triggered == False)
        )
    ).all()
    triggered_prompts = []

    due_reminders = [
        t
        for t in tasks
        if t.type == "reminder"
        and datetime.fromisoformat(t.time.replace("Z", "+00:00")).replace(tzinfo=None)
        <= now
    ]
    if due_reminders:
        task = due_reminders[0]
        triggered_prompts.append(
            f"【管理系统提醒：Pero，你与主人的约定时间已到，请主动提醒主人。约定内容：{task.content}】"
        )
        task.is_triggered = True
        session.add(task)

    if not triggered_prompts:
        due_topics = [
            t
            for t in tasks
            if t.type == "topic"
            and datetime.fromisoformat(t.time.replace("Z", "+00:00")).replace(
                tzinfo=None
            )
            <= now
        ]
        if due_topics:
            topic_list_str = "\n".join([f"- {t.content}" for t in due_topics])
            triggered_prompts.append(
                f"【管理系统提醒：Pero，以下是你之前想找主人聊的话题（已汇总）：\n{topic_list_str}\n\n请将这些话题自然地融合在一起，作为一次主动的聊天开场。】"
            )

            for t in due_topics:
                t.is_triggered = True
                session.add(t)

    if not triggered_prompts:
        # Check for idle time? (Logic from main.py)
        # But this function returns prompts for triggering chat.
        pass

    await session.commit()
    return {"prompts": triggered_prompts}
