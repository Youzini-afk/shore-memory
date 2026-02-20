import asyncio

import pytest

from services.agent.task_manager import TaskManager


class TestTaskManager:
    @pytest.fixture
    def manager(self):
        # 为每个测试重置单例
        TaskManager._instance = None
        return TaskManager()

    def test_singleton(self):
        """测试单例模式"""
        m1 = TaskManager()
        m2 = TaskManager()
        assert m1 is m2
        assert m1.tasks is m2.tasks

    def test_register_unregister(self, manager):
        """测试任务注册和注销"""
        session_id = "session_1"

        manager.register(session_id)
        assert session_id in manager.tasks
        assert manager.tasks[session_id]["status"] == "running"

        manager.unregister(session_id)
        assert session_id not in manager.tasks

    @pytest.mark.asyncio
    async def test_pause_resume(self, manager):
        """测试暂停和恢复功能"""
        session_id = "session_2"
        manager.register(session_id)

        # 初始状态: 运行中
        assert manager.get_status(session_id) == "running"

        # 暂停
        assert manager.pause(session_id) is True
        assert manager.get_status(session_id) == "paused"

        # 恢复
        assert manager.resume(session_id) is True
        assert manager.get_status(session_id) == "running"

        # 无效会话
        assert manager.pause("invalid") is False
        assert manager.resume("invalid") is False

    @pytest.mark.asyncio
    async def test_inject_instruction(self, manager):
        """测试指令注入"""
        session_id = "session_3"
        manager.register(session_id)

        instruction = "Stop generating"
        assert manager.inject_instruction(session_id, instruction) is True

        retrieved = manager.get_injected_instruction(session_id)
        assert retrieved == instruction

        # 队列现在应该为空
        assert manager.get_injected_instruction(session_id) is None

        # 无效会话
        assert manager.inject_instruction("invalid", "cmd") is False

    @pytest.mark.asyncio
    async def test_check_pause_waits(self, manager):
        """测试暂停时 check_pause 确实等待"""
        session_id = "session_wait"
        manager.register(session_id)

        # 暂停任务
        manager.pause(session_id)

        # 创建一个等待暂停的任务
        wait_task = asyncio.create_task(manager.check_pause(session_id))

        # 给它一点时间阻塞
        await asyncio.sleep(0.01)
        assert not wait_task.done()

        # 恢复并验证它完成
        manager.resume(session_id)
        # 等待任务超时，以防逻辑损坏导致挂起
        await asyncio.wait_for(wait_task, timeout=0.1)
        assert wait_task.done()
