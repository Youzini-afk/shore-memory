import uuid
from datetime import datetime

from sqlmodel import select

try:
    from core.config_manager import get_config_manager
    from models import Config, ConversationLog, Memory
    from services.llm_service import LLMService
    from services.memory_service import MemoryService
except ImportError:
    from backend.models import Config, ConversationLog
    from backend.services.llm_service import LLMService

# Global variable to hold session reference (injected by AgentService)
# This is a bit hacky but works for tool-to-service communication
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

    # [Check] Block Work Mode if incompatible modes are active
    try:
        active_blockers = []

        # 1. Check Config via ConfigManager (memory cache)
        from core.config_manager import get_config_manager
        from services.agent_manager import get_agent_manager

        config_mgr = get_config_manager()
        agent_manager = get_agent_manager()
        agent_id = agent_manager.active_agent_id

        # Log current state for debugging
        print(
            f"[SessionOps] 正在检查模式冲突。当前配置: lightweight_mode={config_mgr.get('lightweight_mode')}, aura_vision={config_mgr.get('aura_vision_enabled')}, agent={agent_id}"
        )

        if config_mgr.get("lightweight_mode", False):
            active_blockers.append("lightweight_mode")

        if config_mgr.get("aura_vision_enabled", False):
            active_blockers.append("aura_vision_enabled")

        # 2. Check DB Config (Companion Mode)
        companion_config = (
            await session.exec(
                select(Config).where(Config.key == "companion_mode_enabled")
            )
        ).first()
        if companion_config and str(companion_config.value).lower() == "true":
            active_blockers.append("companion_mode")

        if active_blockers:
            # Map keys to Chinese names for better user experience
            name_map = {
                "lightweight_mode": "轻量模式",
                "companion_mode": "陪伴模式",
                "aura_vision_enabled": "主动视觉模式",
            }
            modes_str = "、".join([name_map.get(m, m) for m in active_blockers])
            return f"错误: 无法进入工作模式。检测到以下模式正在运行：{modes_str}。请先关闭它们。"

    except Exception as check_e:
        print(f"[SessionOps] 模式检查警告: {check_e}")
        # Proceed with caution or return error? Let's log and proceed if check fails to avoid lockouts,
        # or fail safe. Let's fail safe if we can't verify.
        # For now, just log.

    try:
        # 1. Generate new Session ID (Agent-Aware)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work_session_id = f"work_{agent_id}_{timestamp}_{uuid.uuid4().hex[:4]}"

        # 2. Update Config
        # current_session_id: The actual session ID to use for logs
        # work_mode_task: The name of the task

        # Update current_session_id_{agent_id}
        session_key = f"current_session_id_{agent_id}"
        config_id = (
            await session.exec(select(Config).where(Config.key == session_key))
        ).first()
        if not config_id:
            config_id = Config(key=session_key, value=work_session_id)
            session.add(config_id)
        else:
            config_id.value = work_session_id

        # Update work_mode_task_{agent_id}
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

        # [NIT] Activate Work Toolchain
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
        from services.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        agent_id = agent_manager.active_agent_id

        session_key = f"current_session_id_{agent_id}"
        task_key = f"work_mode_task_{agent_id}"

        # 1. Get current work info
        config_id = (
            await session.exec(select(Config).where(Config.key == session_key))
        ).first()
        config_task = (
            await session.exec(select(Config).where(Config.key == task_key))
        ).first()

        if not config_id or not config_id.value.startswith(f"work_{agent_id}_"):
            # Fallback for old sessions or just generic check
            if not config_id or not config_id.value.startswith("work_"):
                return "错误: 当前不在工作模式。"

        work_session_id = config_id.value
        task_name = config_task.value if config_task else "未命名任务"

        # 2. Fetch all logs for this session
        logs = (
            await session.exec(
                select(ConversationLog)
                .where(ConversationLog.session_id == work_session_id)
                .order_by(ConversationLog.timestamp)
            )
        ).all()

        if not logs:
            return "已退出工作模式 (无日志需要总结)。"

        # 3. Summarize via LLM
        global_config = {
            c.key: c.value for c in (await session.exec(select(Config))).all()
        }
        api_key = global_config.get("global_llm_api_key")
        api_base = global_config.get("global_llm_api_base")
        bot_name = global_config.get("bot_name", "Pero")

        # Initialize MDPManager
        import os

        # Path logic: backend/services/session_service.py -> backend/services/mdp/prompts
        # __file__ -> session_service.py
        # dirname -> services
        # dirname -> backend
        # join -> backend/services/mdp/prompts
        mdp_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "services",
            "mdp",
            "prompts",
        )

        if not os.path.exists(mdp_dir):
            # Fallback
            mdp_dir = os.path.join(os.getcwd(), "backend", "services", "mdp", "prompts")

        from services.mdp.manager import MDPManager

        mdp = MDPManager(mdp_dir)

        # [Unified Model Fix] Use current_model_id instead of hardcoded gpt-4o
        from models import AIModelConfig

        current_model_id = global_config.get("current_model_id")

        # Default fallback if config fails
        model_to_use = "gpt-4o"

        if current_model_id:
            model_config = await session.get(AIModelConfig, int(current_model_id))
            if model_config:
                model_to_use = model_config.model_id
                # Also ensure we use the correct API key/base if it's a custom provider
                if model_config.provider_type == "custom":
                    api_key = model_config.api_key
                    api_base = model_config.api_base

        llm = LLMService(api_key, api_base, model_to_use)
        log_text = "\n".join([f"{log.role}: {log.content}" for log in logs])

        from services.mdp.manager import mdp

        variables = {"agent_name": bot_name, "task_name": task_name, "log_text": log_text}
        from services.prompt_service import PromptManager
        pm = PromptManager()
        pm._enrich_variables(variables, is_social_mode=False, is_work_mode=True)

        prompt = mdp.render(
            "components/artifacts/work_log",
            variables,
        )

        summary = await llm.chat([{"role": "user", "content": prompt}])
        summary_content = summary["choices"][0]["message"]["content"]

        # 4. Save to Memory (DB)
        # 退出工作模式时，将总结存入数据库作为 work_log 类型的记忆
        await MemoryService.save_memory(
            session=session,
            content=summary_content,
            tags=f"work_log,summary,coding,{task_name}",
            clusters="[工作记录]",
            importance=6,
            memory_type="work_log",
            source="system",
            agent_id=agent_id
        )

        # [NIT] Deactivate Work Toolchain
        try:
            from core.nit_manager import get_nit_manager

            get_nit_manager().set_category_status("work", False)
        except Exception as nit_e:
            print(f"[SessionOps] 停用 NIT 工作分类失败: {nit_e}")

        # 5. Restore Main Session
        # Just revert the config pointer
        config_id.value = "default"
        config_task.value = ""
        await session.commit()

        return f"已退出工作模式。任务总结已存入记忆。会话已恢复。"

    except Exception as e:
        await session.rollback()
        return f"退出工作模式错误: {e}"


async def abort_work_mode() -> str:
    """
    Abort 'Work Mode' WITHOUT saving summary.
    Useful for accidental entry or if the user just wants to quit.
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session:
        return "错误: 数据库会话不可用。"

    try:
        from services.agent_manager import get_agent_manager

        agent_manager = get_agent_manager()
        agent_id = agent_manager.active_agent_id

        session_key = f"current_session_id_{agent_id}"
        task_key = f"work_mode_task_{agent_id}"

        # 1. Revert Config
        config_id = (
            await session.exec(select(Config).where(Config.key == session_key))
        ).first()
        config_task = (
            await session.exec(select(Config).where(Config.key == task_key))
        ).first()

        if config_id and config_id.value.startswith("work_"):
            # Revert to default
            config_id.value = "default"
            if config_task:
                config_task.value = ""
            await session.commit()

            # [NIT] Deactivate Work Toolchain
            try:
                from core.nit_manager import get_nit_manager

                get_nit_manager().set_category_status("work", False)
            except Exception:
                pass

            original_session_id = "default"  # Simplified
            return f"工作模式已中止。恢复至会话: {original_session_id}"
        else:
            return "当前不在工作模式。"

    except Exception as e:
        await session.rollback()
        return f"中止工作模式错误: {e}"
