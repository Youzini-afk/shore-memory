from datetime import datetime
from typing import List, Optional

import dateparser
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session
from models import ScheduledTask

from services.agent.scheduler_service import scheduler_service


class ReminderItem(BaseModel):
    content: str
    time: str
    repeat: Optional[str] = None


class SyncRemindersRequest(BaseModel):
    source: str = "unknown"
    reminders: List[ReminderItem]


router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.post("/sync")
async def sync_reminders(request: SyncRemindersRequest):
    """
    接收同步结果注册至调度器。
    Payload示例:
    {
        "source": "mobile",
        "reminders": [{"content": "提醒我喝水", "time": "2024-01-01 12:00:00"}]
    }
    """
    reminders = request.reminders
    results = []

    for item in reminders:
        content = item.content
        time_str = item.time
        repeat = item.repeat

        try:
            # 解析时间
            trigger_time = dateparser.parse(time_str)
            if not trigger_time:
                results.append(
                    {"status": "error", "message": f"无效的时间格式: {time_str}"}
                )
                continue

            if trigger_time <= datetime.now() and not repeat:
                results.append({"status": "skipped", "message": "时间已过去"})
                continue

            # 添加到调度器
            job_id = scheduler_service.add_reminder(
                trigger_time, content, repeat=repeat
            )
            results.append({"status": "success", "job_id": job_id, "content": content})

        except Exception as e:
            results.append({"status": "error", "message": str(e)})

    return {"status": "completed", "results": results}


@router.post("/check")
async def check_tasks(session: AsyncSession = Depends(get_session)):  # noqa: B008
    now = datetime.now()
    tasks = (
        await session.exec(select(ScheduledTask).where(not ScheduledTask.is_triggered))
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
        # 检查空闲时间（逻辑源自main.py）
        pass

    await session.commit()
    return {"prompts": triggered_prompts}
