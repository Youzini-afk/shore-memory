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

        # 配置作业存储
        # 我们使用现有的 SQLAlchemy 引擎，但 APScheduler 需要 URL 或引擎
        # SQLAlchemyJobStore 通常最适合直接使用 URL 字符串，但如果是支持的或分开的，我们也可以尝试引擎
        # 为了避免与异步引擎冲突，我们可能需要一个同步 URL 或单独的连接。
        # 为了 MVP 的简单性，如果异步引擎很棘手，我们暂时使用 MemoryJobStore 或 SQLite 文件。
        # 但第二阶段需要持久化。

        # 注意: APScheduler 3.x SQLAlchemyJobStore 是同步的。
        # 我们需要提供一个同步数据库 URL。
        # 假设 sqlite:///./backend/data/pero.db

        backend_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        db_path = os.path.join(backend_dir, "data", "pero.db")
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
                # 简单的 cron 解析 "cron: * * * * *"
                cron_str = repeat[5:].strip()
                trigger = CronTrigger.from_crontab(cron_str)
            else:
                # 如果未知重复格式或只是一次性请求，回退到日期触发器
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

        # 广播更新
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
                # job.args 格式: [content, agent_id]
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
            from services.core.gateway_client import gateway_client

            # 确保我们在事件循环中 (这可能从同步代码调用)
            # APScheduler 回调如果是同步的通常在线程池中，但这里我们在服务方法中。
            # 假设 add_reminder 从异步上下文 (FastAPI) 调用。

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
                )  # 简单的 JSON 字符串或仅字段

                await gateway_client.send(envelope)

            # 检查是否有正在运行的循环
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_send())
            except RuntimeError:
                # 没有运行的循环，创建一个 (对于从脚本调用的服务方法的罕见情况)
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
        from services.core.gateway_client import gateway_client

        envelope = perolink_pb2.Envelope()
        envelope.id = str(uuid.uuid4())
        envelope.source_id = "scheduler"
        envelope.target_id = "broadcast"
        envelope.timestamp = int(time.time() * 1000)

        # 构造提醒的 ActionRequest
        envelope.request.action_name = "reminder_trigger"
        envelope.request.params["content"] = content
        envelope.request.params["timestamp"] = datetime.now().isoformat()
        if agent_id:
            envelope.request.params["agent_id"] = agent_id

        await gateway_client.send(envelope)


scheduler_service = SchedulerService()
