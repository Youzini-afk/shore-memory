from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from services.agent.scheduler_service import SchedulerService


@pytest.fixture
def mock_apscheduler_global():
    # 在服务模块中使用类的地方打补丁
    with (
        patch(
            "services.agent.scheduler_service.AsyncIOScheduler"
        ) as mock_scheduler_cls,
        patch("services.agent.scheduler_service.SQLAlchemyJobStore") as _,
        patch("services.agent.scheduler_service.CronTrigger") as mock_cron_trigger,
        patch("services.agent.scheduler_service.DateTrigger") as mock_date_trigger,
    ):
        mock_scheduler_instance = mock_scheduler_cls.return_value
        yield {
            "scheduler_cls": mock_scheduler_cls,
            "scheduler": mock_scheduler_instance,
            "cron": mock_cron_trigger,
            "date": mock_date_trigger,
        }


class TestSchedulerService:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # 重置单例
        SchedulerService._instance = None
        yield
        SchedulerService._instance = None

    def test_singleton(self):
        s1 = SchedulerService()
        s2 = SchedulerService()
        assert s1 is s2

    def test_initialize(self, mock_apscheduler_global):
        service = SchedulerService()
        service.initialize()

        mock_apscheduler_global["scheduler_cls"].assert_called_once()
        mock_apscheduler_global["scheduler"].start.assert_called_once()
        # assert service._initialized

        # 再次调用初始化应该什么都不做
        service.initialize()
        mock_apscheduler_global["scheduler_cls"].assert_called_once()

    def test_add_reminder_date(self, mock_apscheduler_global):
        service = SchedulerService()
        service.initialize()

        trigger_time = datetime.now() + timedelta(minutes=5)
        service.add_reminder(trigger_time, "test reminder")

        mock_apscheduler_global["date"].assert_called_with(run_date=trigger_time)
        mock_apscheduler_global["scheduler"].add_job.assert_called_once()
        args, kwargs = mock_apscheduler_global["scheduler"].add_job.call_args
        assert kwargs["name"] == "提醒: test reminder"

    def test_add_reminder_daily(self, mock_apscheduler_global):
        service = SchedulerService()
        service.initialize()

        trigger_time = datetime(2023, 1, 1, 10, 30, 0)
        service.add_reminder(trigger_time, "daily meeting", repeat="daily")

        mock_apscheduler_global["cron"].assert_called()
        call_kwargs = mock_apscheduler_global["cron"].call_args[1]
        assert call_kwargs["hour"] == 10
        assert call_kwargs["minute"] == 30
        assert call_kwargs["second"] == 0

    def test_add_reminder_weekly(self, mock_apscheduler_global):
        service = SchedulerService()
        service.initialize()

        trigger_time = datetime(2023, 1, 1, 10, 30, 0)  # 周日 (weekday=6)
        service.add_reminder(trigger_time, "weekly report", repeat="weekly")

        mock_apscheduler_global["cron"].assert_called()
        call_kwargs = mock_apscheduler_global["cron"].call_args[1]
        assert call_kwargs["day_of_week"] == 6
        assert call_kwargs["hour"] == 10

    def test_add_reminder_cron(self, mock_apscheduler_global):
        service = SchedulerService()
        service.initialize()

        trigger_time = datetime.now()
        service.add_reminder(trigger_time, "cron job", repeat="cron: 0 10 * * *")

        # 验证 CronTrigger.from_crontab 被调用
        mock_apscheduler_global["cron"].from_crontab.assert_called_with("0 10 * * *")
