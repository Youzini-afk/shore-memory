import uuid
from datetime import datetime

from sqlmodel import select

try:
    from models import Config, ConversationLog
    from services.memory.memory_service import MemoryService
except ImportError:
    from backend.models import Config, ConversationLog

# 用于保存会话引用的全局变量（由 AgentService 注入）
# 这种方式有点不够优雅，但对于工具到服务的通信是有效的
_CURRENT_SESSION_CONTEXT = {}


def set_current_session_context(session, agent_id: str = "pero"):
    _CURRENT_SESSION_CONTEXT["db_session"] = session
    _CURRENT_SESSION_CONTEXT["agent_id"] = agent_id


async def enter_work_mode(task_name: str = "未知任务") -> str:
    """
    进入“工作模式”（隔离模式）。
    为编码或复杂任务创建一个临时的、隔离的会话。
    该会话的历史记录不会污染主聊天记录，但稍后会被总结。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session:
        return "错误: 数据库会话不可用。"

    # [检查] 如果有不兼容的模式处于活动状态，则阻止进入工作模式
    try:
        active_blockers = []

        # 1. 通过 ConfigManager 检查配置（内存缓存）
        from core.config_manager import get_config_manager
        from services.agent.agent_manager import get_agent_manager

        config_mgr = get_config_manager()
        agent_manager = get_agent_manager()
        agent_id = agent_manager.active_agent_id

        # 记录当前状态以便调试
        print(
            f"[SessionOps] 正在检查模式冲突。当前配置: lightweight_mode={config_mgr.get('lightweight_mode')}, aura_vision={config_mgr.get('aura_vision_enabled')}, agent={agent_id}"
        )

        if config_mgr.get("lightweight_mode", False):
            active_blockers.append("lightweight_mode")

        if config_mgr.get("aura_vision_enabled", False):
            active_blockers.append("aura_vision_enabled")

        # 2. 检查数据库配置（陪伴模式）
        companion_config = (
            await session.exec(
                select(Config).where(Config.key == "companion_mode_enabled")
            )
        ).first()
        if companion_config and str(companion_config.value).lower() == "true":
            active_blockers.append("companion_mode")

        if active_blockers:
            # 将键映射为中文名称，以获得更好的用户体验
            name_map = {
                "lightweight_mode": "轻量模式",
                "companion_mode": "陪伴模式",
                "aura_vision_enabled": "主动视觉模式",
            }
            modes_str = "、".join([name_map.get(m, m) for m in active_blockers])
            return f"错误: 无法进入工作模式。检测到以下模式正在运行：{modes_str}。请先关闭它们。"

    except Exception as check_e:
        print(f"[SessionOps] 模式检查警告: {check_e}")
        # 检查失败时仅记录日志，不阻止后续操作，以防误判导致死锁。

    try:
        # 1. 生成新的会话 ID (感知 Agent)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_session_id = f"work_{agent_id}_{timestamp}_{uuid.uuid4().hex[:4]}"

        # 2. 更新配置
        # current_session_id: 用于日志的实际会话 ID
        # work_mode_task: 任务名称

        # 更新 current_session_id_{agent_id}
        session_key = f"current_session_id_{agent_id}"
        config_id = (
            await session.exec(select(Config).where(Config.key == session_key))
        ).first()
        if not config_id:
            config_id = Config(key=session_key, value=work_session_id)
            session.add(config_id)
        else:
            config_id.value = work_session_id

        # 更新 work_mode_task_{agent_id}
        task_key = f"work_mode_task_{agent_id}"
        config_task = (
            await session.exec(select(Config).where(Config.key == task_key))
        ).first()
        if not config_task:
            config_task = Config(key=task_key, value=task_name)
            session.add(config_task)
        else:
            config_task.value = task_name

        await session.commit()

        # [NIT] 激活工作工具链
        try:
            from core.nit_manager import get_nit_manager

            get_nit_manager().set_category_status("work", True)
        except Exception as nit_e:
            print(f"[SessionOps] 激活 NIT 工作分类失败: {nit_e}")

        return f"已进入工作模式。新隔离会话: {work_session_id}. 任务: {task_name}"

    except Exception as e:
        await session.rollback()
        return f"进入工作模式错误: {e}"


async def exit_work_mode() -> str:
    """
    退出“工作模式”。
    将整个工作会话总结为“手写日志”并保存到长期记忆中。
    恢复主聊天会话。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session:
        return "错误: 数据库会话不可用。"

    config_id = None
    try:
        from services.agent.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        agent_id = agent_manager.active_agent_id

        session_key = f"current_session_id_{agent_id}"
        task_key = f"work_mode_task_{agent_id}"

        # 1. 获取当前工作信息
        config_id = (
            await session.exec(select(Config).where(Config.key == session_key))
        ).first()
        config_task = (
            await session.exec(select(Config).where(Config.key == task_key))
        ).first()

        if (not config_id or not config_id.value.startswith(f"work_{agent_id}_")) and (
            not config_id or not config_id.value.startswith("work_")
        ):
            # 针对旧会话或通用检查的回退
            return "错误: 当前不在工作模式。"

        work_session_id = config_id.value
        task_name = config_task.value if config_task else "未命名任务"

        # 2. 获取该会话的所有日志
        logs = (
            await session.exec(
                select(ConversationLog)
                .where(ConversationLog.session_id == work_session_id)
                .order_by(ConversationLog.timestamp)
            )
        ).all()

        if not logs:
            return "已退出工作模式 (无日志需要总结)。"

        # 3. 通过 ScorerService 进行总结
        from services.memory.scorer_service import ScorerService

        global_config = {
            c.key: c.value for c in (await session.exec(select(Config))).all()
        }
        bot_name = global_config.get("bot_name", "Pero")

        log_text = "\n".join([f"{log.role}: {log.content}" for log in logs])

        scorer_service = ScorerService(session)
        summary_content = await scorer_service.generate_work_log_summary(
            task_name=task_name, log_text=log_text, agent_name=bot_name
        )

        if not summary_content:
            summary_content = f"工作模式总结失败。任务: {task_name}。"

        # 4. 保存到文件 (不入库)
        try:
            import os
            from utils.workspace_utils import get_workspace_root
            
            workspace = get_workspace_root(agent_id)
            log_dir = os.path.join(workspace, "work_logs")
            os.makedirs(log_dir, exist_ok=True)
            
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            # 清理 task_name 以防非法字符
            safe_task_name = "".join([c if c.isalnum() else "_" for c in task_name])
            file_name = f"{now_str}_{safe_task_name}.md"
            file_path = os.path.join(log_dir, file_name)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(summary_content)
            print(f"[Session] 工作日志已保存: {file_path}")
            
        except Exception as e:
            print(f"[Session] 保存工作日志失败: {e}")

        # [已移除] 存入数据库
        # await MemoryService.save_memory(...)

        # [NIT] 停用工作工具链
        try:
            from core.nit_manager import get_nit_manager

            get_nit_manager().set_category_status("work", False)
        except Exception as nit_e:
            print(f"[SessionOps] 停用 NIT 工作分类失败: {nit_e}")

        # 5. 恢复主会话
        # 只需还原配置指针
        config_id.value = "default"
        config_task.value = ""
        await session.commit()

        return "已退出工作模式。任务总结已存入记忆。会话已恢复。"

    except Exception as e:
        await session.rollback()
        return f"退出工作模式错误: {e}"


async def abort_work_mode() -> str:
    """
    中止“工作模式”且不保存总结。
    适用于意外进入或用户只想退出的情况。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session:
        return "错误: 数据库会话不可用。"

    try:
        from services.agent.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        agent_id = agent_manager.active_agent_id

        session_key = f"current_session_id_{agent_id}"
        task_key = f"work_mode_task_{agent_id}"

        # 1. 还原配置
        config_id = (
            await session.exec(select(Config).where(Config.key == session_key))
        ).first()
        config_task = (
            await session.exec(select(Config).where(Config.key == task_key))
        ).first()

        if config_id and config_id.value.startswith("work_"):
            # 恢复默认值
            config_id.value = "default"
            if config_task:
                config_task.value = ""
            await session.commit()

            # [NIT] 停用工作工具链
            try:
                from core.nit_manager import get_nit_manager

                get_nit_manager().set_category_status("work", False)
            except Exception:
                pass

            original_session_id = "default"  # 简化处理
            return f"工作模式已中止。恢复至会话: {original_session_id}"
        else:
            return "当前不在工作模式。"

    except Exception as e:
        await session.rollback()
        return f"中止工作模式错误: {e}"
