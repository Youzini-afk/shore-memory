import logging
import os
from datetime import datetime

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    基于 APScheduler 的统一调度服务。
    管理定时任务（提醒、闹钟、系统维护）。
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchedulerService, cls).__new__(cls)
            cls._instance.scheduler = None
        return cls._instance

    def initialize(self):
        """使用数据库作业存储初始化调度器"""
        if self.scheduler:
            return

        # Configure job stores
        # We use the existing SQLAlchemy engine but APScheduler needs a URL or engine
        # SQLAlchemyJobStore works best with a direct URL string usually, but let's try engine if supported or separate
        # To avoid conflict with async engine, we might need a sync URL or a separate connection.
        # For simplicity in MVP, let's use MemoryJobStore or SQLite file for now if async engine is tricky.
        # But Phase 2 requires persistence.

        # NOTE: APScheduler 3.x SQLAlchemyJobStore is synchronous.
        # We need to provide a sync database URL.
        # Assuming sqlite:///./backend/data/pero.db

        db_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "pero.db"
        )
        db_url = f"sqlite:///{db_path}"

        jobstores = {"default": SQLAlchemyJobStore(url=db_url)}

        self.scheduler = AsyncIOScheduler(jobstores=jobstores)
        self.scheduler.start()
        logger.info("调度服务已初始化并启动。")

    def add_reminder(
        self,
        trigger_time: datetime,
        content: str,
        repeat: str = None,
        agent_id: str = None,
    ):
        """
        添加提醒任务。
        :param trigger_time: 触发时间
        :param content: 提醒内容
        :param repeat: 重复规则 ('daily', 'weekly', 或 'cron: * * * * *')
        :param agent_id: 归属的 Agent ID (可选，默认为全局)
        """
        trigger = None

        if repeat:
            repeat = repeat.lower().strip()
            if repeat == "daily":
                trigger = CronTrigger(
                    hour=trigger_time.hour,
                    minute=trigger_time.minute,
                    second=trigger_time.second,
                )
            elif repeat == "weekly":
                trigger = CronTrigger(
                    day_of_week=trigger_time.weekday(),
                    hour=trigger_time.hour,
                    minute=trigger_time.minute,
                    second=trigger_time.second,
                )
            elif repeat.startswith("cron:"):
                # Simple cron parsing "cron: * * * * *"
                cron_str = repeat[5:].strip()
                trigger = CronTrigger.from_crontab(cron_str)
            else:
                # Fallback to date trigger if unknown repeat format or if it's just a one-time request
                trigger = DateTrigger(run_date=trigger_time)
        else:
            trigger = DateTrigger(run_date=trigger_time)

        job = self.scheduler.add_job(
            SchedulerService._trigger_reminder,
            trigger=trigger,
            args=[content, agent_id],
            name=f"提醒: {content[:20]}",
            replace_existing=False,
        )
        logger.info(
            f"已添加提醒任务 {job.id} 于 {trigger_time} (重复: {repeat}, Agent: {agent_id})"
        )

        # Broadcast update
        self._broadcast_update(
            "add",
            {
                "id": job.id,
                "content": content,
                "next_run_time": str(job.next_run_time),
                "agent_id": agent_id,
            },
        )

        return job.id

    def list_jobs(self, agent_id: str = None):
        """列出所有活动任务，支持按 Agent ID 过滤"""
        if not self.scheduler:
            return []
        all_jobs = self.scheduler.get_jobs()

        if agent_id:
            filtered_jobs = []
            for job in all_jobs:
                # job.args format: [content, agent_id]
                if len(job.args) >= 2 and job.args[1] == agent_id:
                    filtered_jobs.append(job)
            return filtered_jobs

        return all_jobs

    def remove_job(self, job_id: str):
        """根据 ID 移除任务"""
        if self.scheduler:
            try:
                self.scheduler.remove_job(job_id)
                self._broadcast_update("remove", {"id": job_id})
            except Exception as e:
                logger.warning(f"移除任务 {job_id} 失败: {e}")

    def _broadcast_update(self, operation: str, data: dict):
        """广播调度更新事件"""
        try:
            import asyncio
            import time
            import uuid

            from peroproto import perolink_pb2
            from services.gateway_client import gateway_client

            # Ensure we are in an event loop (this might be called from sync code)
            # APScheduler callbacks are usually in thread pool if sync, but here we are in service methods.
            # Assuming add_reminder is called from async context (FastAPI).

            async def _send():
                envelope = perolink_pb2.Envelope()
                envelope.id = str(uuid.uuid4())
                envelope.source_id = "scheduler"
                envelope.target_id = "broadcast"
                envelope.timestamp = int(time.time() * 1000)

                envelope.request.action_name = "schedule_update"
                envelope.request.params["operation"] = operation
                envelope.request.params["data"] = str(
                    data
                )  # Simple JSON string or just fields

                await gateway_client.send(envelope)

            # Check if there is a running loop
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_send())
            except RuntimeError:
                # No running loop, create one (rare case for service methods called from scripts)
                asyncio.run(_send())
        except Exception as e:
            logger.error(f"广播调度更新失败: {e}")

    @staticmethod
    async def _trigger_reminder(content: str, agent_id: str = None):
        """
        提醒触发时的回调。
        向网关广播 'action:reminder_trigger'。
        """
        logger.info(f"触发提醒: {content} (Agent: {agent_id})")

        import time
        import uuid

        from peroproto import perolink_pb2
        from services.gateway_client import gateway_client

        envelope = perolink_pb2.Envelope()
        envelope.id = str(uuid.uuid4())
        envelope.source_id = "scheduler"
        envelope.target_id = "broadcast"
        envelope.timestamp = int(time.time() * 1000)

        # Construct ActionRequest for reminder
        envelope.request.action_name = "reminder_trigger"
        envelope.request.params["content"] = content
        envelope.request.params["timestamp"] = datetime.now().isoformat()
        if agent_id:
            envelope.request.params["agent_id"] = agent_id

        await gateway_client.send(envelope)


scheduler_service = SchedulerService()
