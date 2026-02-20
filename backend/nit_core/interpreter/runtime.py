import contextlib
import uuid
from datetime import datetime

# --- runtime.py 的原始内容（为兼容性保留的错位函数） ---
from sqlmodel import select

from .ast_nodes import (
    AssignmentNode,
    CallNode,
    ListNode,
    LiteralNode,
    VariableRefNode,
)

# from .engine import NITRuntime

try:
    from models import Config, ConversationLog

    # from services.mdp.manager import MDPManager
    from services.memory.memory_service import MemoryService
except ImportError:
    from backend.models import Config, ConversationLog
    from backend.services.memory.memory_service import MemoryService

# 尝试导入 AgentManager 以支持多 Agent
try:
    from services.agent.agent_manager import get_agent_manager
except ImportError:
    try:
        from backend.services.agent.agent_manager import get_agent_manager
    except ImportError:
        get_agent_manager = None

# 全局变量，用于保存会话引用 (由 AgentService 注入)
# 这有点权宜之计，但对于 tool-to-service 通信是有效的
_CURRENT_SESSION_CONTEXT = {}


def set_current_session_context(session):
    _CURRENT_SESSION_CONTEXT["db_session"] = session


async def enter_work_mode(task_name: str = "Unknown Task") -> str:
    """
    进入 'Work Mode' (隔离模式)。
    为编码或复杂任务创建一个临时的、隔离的会话。
    此会话的历史记录不会干扰主聊天，但稍后会被汇总。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session:
        return "错误: 数据库会话不可用。"

    try:
        # 1. 生成新 Session ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_session_id = f"work_{timestamp}_{uuid.uuid4().hex[:4]}"

        # 2. 更新 Config
        # current_session_id: 用于日志的实际会话 ID
        # work_mode_task: 任务名称

        # 更新 current_session_id
        config_id = (
            await session.exec(select(Config).where(Config.key == "current_session_id"))
        ).first()
        if not config_id:
            config_id = Config(key="current_session_id", value=work_session_id)
            session.add(config_id)
        else:
            config_id.value = work_session_id

        # 更新 work_mode_task
        config_task = (
            await session.exec(select(Config).where(Config.key == "work_mode_task"))
        ).first()
        if not config_task:
            config_task = Config(key="work_mode_task", value=task_name)
            session.add(config_task)
        else:
            config_task.value = task_name

        await session.commit()
        return f"已进入工作模式。新隔离会话: {work_session_id}。任务: {task_name}"

    except Exception as e:
        await session.rollback()
        return f"进入工作模式时发生错误: {e}"


async def exit_work_mode() -> str:
    """
    退出 'Work Mode'。
    将整个工作会话汇总为 '手写日志' 并保存到长期记忆中。
    恢复主聊天会话。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session:
        return "错误: 数据库会话不可用。"

    config_id = None
    try:
        # 1. 获取当前工作信息
        config_id = (
            await session.exec(select(Config).where(Config.key == "current_session_id"))
        ).first()
        config_task = (
            await session.exec(select(Config).where(Config.key == "work_mode_task"))
        ).first()

        if not config_id or not config_id.value.startswith("work_"):
            return "错误: 当前不在工作模式。"

        work_session_id = config_id.value
        task_name = config_task.value if config_task else "未命名任务"

        # 2. 获取此会话的所有日志
        logs = (
            await session.exec(
                select(ConversationLog)
                .where(ConversationLog.session_id == work_session_id)
                .order_by(ConversationLog.timestamp)
            )
        ).all()

        if not logs:
            return "已退出工作模式 (无日志可汇总)。"

        # 3. 通过 ScorerService 进行总结
        from services.memory.scorer_service import ScorerService

        global_config = {
            c.key: c.value for c in (await session.exec(select(Config))).all()
        }
        bot_name = global_config.get("bot_name", "Pero")

        scorer_service = ScorerService(session)
        log_text = "\n".join([f"{log.role}: {log.content}" for log in logs])

        summary_content = await scorer_service.generate_work_log_summary(
            task_name=task_name, log_text=log_text, agent_name=bot_name
        )

        if not summary_content:
            summary_content = f"工作模式总结失败。任务: {task_name}。"

        # 获取活跃 Agent
        agent_id = "pero"
        if get_agent_manager:
            with contextlib.suppress(Exception):
                active_agent = get_agent_manager().active_agent_id
                if active_agent:
                    agent_id = active_agent

        # 4. 保存到记忆 (长期)
        await MemoryService.save_memory(
            session=session,
            content=summary_content,
            tags="work_log,summary,coding",
            clusters="[工作记录]",
            importance=8,
            memory_type="work_log",
            source="system",
            agent_id=agent_id,
        )
        return f"已退出工作模式。\n\n[已生成总结]:\n{summary_content}\n\n(已保存到长期记忆)"

    except Exception as e:
        await session.rollback()
        return f"退出工作模式时出错: {e}"
    finally:
        # 始终尝试将会话状态恢复为 'default'
        if config_id and config_id.value.startswith("work_"):
            try:
                config_id.value = "default"
                await session.commit()
            except Exception as final_e:
                print(f"[Runtime] 恢复会话时发生严重错误: {final_e}")


class NITRuntime:
    def __init__(self, tool_executor):
        self.tool_executor = tool_executor
        self.variables = {}

    async def execute(self, pipeline):
        last_result = None
        for statement in pipeline.statements:
            last_result = await self.execute_statement(statement)
        return last_result

    async def execute_statement(self, statement):
        if isinstance(statement, AssignmentNode):
            value = await self.execute_call(statement.expression)
            self.variables[statement.target_var] = value
            return value
        elif isinstance(statement, CallNode):
            return await self.execute_call(statement)

    def evaluate_value(self, node):
        if isinstance(node, LiteralNode):
            return node.value
        elif isinstance(node, VariableRefNode):
            return self.variables.get(node.name)
        elif isinstance(node, ListNode):
            return [self.evaluate_value(elem) for elem in node.elements]
        return None

    async def execute_call(self, call_node):
        args = {}
        for name, node in call_node.args.items():
            args[name] = self.evaluate_value(node)

        # 工具执行逻辑
        result = await self.tool_executor(call_node.tool_name, args)
        return result


# Tool Definitions
enter_work_mode_definition = {
    "type": "function",
    "function": {
        "name": "enter_work_mode",
        "description": "激活“工作模式”（隔离模式）。在开始复杂的编码任务或项目时使用。它会隔离对话历史记录，以防止污染日常聊天上下文。",
        "parameters": {
            "type": "object",
            "properties": {
                "task_name": {
                    "type": "string",
                    "description": "任务的名称或描述（例如，“重构记忆服务”）。",
                }
            },
            "required": ["task_name"],
        },
    },
}

exit_work_mode_definition = {
    "type": "function",
    "function": {
        "name": "exit_work_mode",
        "description": "停用“工作模式”。在任务完成时使用。它会自动将会话汇总为“工作日志”并保存到记忆中。",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}
