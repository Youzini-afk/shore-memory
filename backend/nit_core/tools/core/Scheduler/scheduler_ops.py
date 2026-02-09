from datetime import datetime

import dateparser

from services.scheduler_service import scheduler_service

try:
    from services.session_service import _CURRENT_SESSION_CONTEXT
except ImportError:
    from backend.services.session_service import _CURRENT_SESSION_CONTEXT


async def add_reminder(time: str, content: str, repeat_rule: str = None) -> str:
    """
    添加一个定时提醒。
    :param time: 触发时间，支持自然语言（如 "10分钟后"、"明天早上8点"）
    :param content: 提醒的内容
    :param repeat_rule: 重复规则（可选）。支持 "daily" (每天), "weekly" (每周), 或 "cron: * * * * *" (Cron表达式)
    :return: 任务 ID 或错误信息
    """
    try:
        # 使用 dateparser 解析自然语言时间
        # 设置 settings={'PREFER_DATES_FROM': 'future'} 倾向于未来时间
        trigger_time = dateparser.parse(
            time,
            settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": datetime.now()},
        )

        if not trigger_time:
            return "错误: 无法解析时间，请使用更清晰的格式（如 'YYYY-MM-DD HH:MM' 或 '10分钟后'）。"

        if trigger_time <= datetime.now():
            return "错误: 触发时间必须是未来时间。"

        agent_id = _CURRENT_SESSION_CONTEXT.get("agent_id", "pero")
        job_id = scheduler_service.add_reminder(
            trigger_time, content, repeat=repeat_rule, agent_id=agent_id
        )
        return f"成功: 已添加提醒 '{content}'，将在 {trigger_time.strftime('%Y-%m-%d %H:%M:%S')} 触发 (ID: {job_id})。"
    except Exception as e:
        return f"错误: 添加提醒失败: {str(e)}"


async def list_reminders() -> str:
    """
    列出当前所有待执行的提醒。
    """
    agent_id = _CURRENT_SESSION_CONTEXT.get("agent_id", "pero")
    jobs = scheduler_service.list_jobs(agent_id=agent_id)
    if not jobs:
        return "当前没有待执行的提醒任务。"

    result = "【待执行提醒列表】:\n"
    for job in jobs:
        next_run = (
            job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            if job.next_run_time
            else "N/A"
        )
        result += f"- [{job.id}] {job.name} (触发时间: {next_run})\n"
    return result


async def delete_reminder(id: str) -> str:
    """
    删除指定的提醒任务。
    :param id: 任务 ID
    """
    try:
        # 检查所有权
        agent_id = _CURRENT_SESSION_CONTEXT.get("agent_id", "pero")
        jobs = scheduler_service.list_jobs(agent_id=agent_id)
        owned_ids = [job.id for job in jobs]

        if id not in owned_ids:
            return f"错误: 未找到 ID 为 {id} 的任务 (或无权删除)。"

        scheduler_service.remove_job(id)
        return f"成功: 已删除任务 {id}。"
    except Exception:
        return f"错误: 删除任务 {id} 失败。"
