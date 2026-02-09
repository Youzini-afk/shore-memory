import contextlib
import datetime
import json
import logging
import os

from sqlmodel import desc, select

# 尝试导入数据库访问模块
try:
    from models import MaintenanceRecord, Memory, ScheduledTask
    from services.memory_service import MemoryService

    try:
        from services.session_service import _CURRENT_SESSION_CONTEXT
    except ImportError:
        try:
            from backend.services.session_service import _CURRENT_SESSION_CONTEXT
        except ImportError:
            from services.session_service import _CURRENT_SESSION_CONTEXT
except ImportError:
    try:
        from backend.models import MaintenanceRecord, Memory, ScheduledTask
        from backend.services.memory_service import MemoryService

        # 尝试从 SessionOps 导入会话上下文
        try:
            from backend.services.session_service import _CURRENT_SESSION_CONTEXT
        except ImportError:
            try:
                from services.session_service import _CURRENT_SESSION_CONTEXT
            except ImportError:
                from services.session_service import _CURRENT_SESSION_CONTEXT
    except ImportError:
        # 开发/测试环境的回退（无完整后端上下文）
        # 如果路径错误，这在生产环境中可能会失败，但我们会优雅地处理它
        logging.warning(
                "MemoryOps: 无法导入后端模块。数据库功能可能无法工作。"
            )
        _CURRENT_SESSION_CONTEXT = {}
        Memory = None
        MaintenanceRecord = None
        ScheduledTask = None
        MemoryService = None

# 尝试导入 AgentManager 以支持多 Agent
try:
    from services.agent_manager import get_agent_manager
except ImportError:
    try:
        from backend.services.agent_manager import get_agent_manager
    except ImportError:
        get_agent_manager = None

# 配置日志存储路径 (作为备份/兼容)
# Assuming file is in backend/nit_core/tools/core/MemoryOps/memory_ops.py
# 根目录是 backend (向上 4 级)
MEMORY_DIR = os.path.join(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
    ),
    "memory",
)
REFLECTION_FILE = os.path.join(MEMORY_DIR, "reflection_log.json")

logger = logging.getLogger(__name__)


def _ensure_memory_dir():
    if not os.path.exists(MEMORY_DIR):
        try:
            os.makedirs(MEMORY_DIR)
        except Exception as e:
            logger.error(f"创建记忆目录失败: {e}")


def _load_reflections_local():
    """从本地 JSON 文件加载反思记录（遗留/备份）"""
    _ensure_memory_dir()
    if not os.path.exists(REFLECTION_FILE):
        return []
    try:
        with open(REFLECTION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load reflection log: {e}")
        return []


def _save_reflections_local(logs):
    """保存反思记录到本地 JSON 文件（遗留/备份）"""
    _ensure_memory_dir()
    try:
        with open(REFLECTION_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存反思日志失败: {e}")


# --- Reflection Operations ---


async def log_reflection(category: str, content: str, level: str = "info") -> str:
    """
    记录一条自我反思日志。
    优先写入数据库 (Memory Table, type='reflection', cluster='[反思簇]')。
    同时备份到本地 JSON 文件。
    """
    # 1. 保存到数据库（主要）
    db_status = ""
    session = _CURRENT_SESSION_CONTEXT.get("db_session")

    if session and MemoryService:
        try:
            importance_map = {"info": 3, "warning": 6, "critical": 9}
            imp = importance_map.get(level, 3)

            # 获取活跃 Agent
            agent_id = "pero"
            if get_agent_manager:
                with contextlib.suppress(Exception):
                    agent_id = get_agent_manager().active_agent_id

            await MemoryService.save_memory(
                session=session,
                content=f"[{category}] {content}",
                tags=f"reflection,{category},{level}",
                clusters="[反思簇]",
                importance=imp,
                base_importance=float(imp),
                memory_type="reflection",
                source="MemoryOps",
                sentiment="neutral",  # 反思通常是中性/客观的
                agent_id=agent_id,
            )
            db_status = "(已同步至记忆数据库)"
        except Exception as e:
            db_status = f"(数据库写入失败: {e})"
            logger.error(f"MemoryOps DB Error: {e}")
    else:
        db_status = "(未连接数据库，仅本地存储)"

    # 2. 保存到本地文件（备份）
    try:
        logs = _load_reflections_local()
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "content": content,
            "level": level,
        }
        logs.insert(0, entry)
        if len(logs) > 50:
            logs = logs[:50]
        _save_reflections_local(logs)
    except Exception as e:
        logger.error(f"MemoryOps Local File Error: {e}")

    return f"已记录反思日志 [{level.upper()}] {category}: {content} {db_status}"


async def read_reflections(limit: int = 5) -> str:
    """
    查阅最近的自我反思记录。
    优先从数据库读取。
    """
    try:
        limit = int(limit)
    except Exception:
        limit = 5

    logs_text = ""
    session = _CURRENT_SESSION_CONTEXT.get("db_session")

    # 优先尝试数据库
    if session and Memory:
        try:
            # 获取活跃 Agent
            agent_id = "pero"
            if get_agent_manager:
                with contextlib.suppress(Exception):
                    agent_id = get_agent_manager().active_agent_id

            statement = (
                select(Memory)
                .where(Memory.type == "reflection")
                .where(Memory.agent_id == agent_id)
                .order_by(desc(Memory.timestamp))
                .limit(limit)
            )
            memories = (await session.exec(statement)).all()

            if memories:
                logs_text = "【我的错题本 (来自记忆数据库)】\n"
                for m in memories:
                    # 解析标签以查找级别/类别（如果可能），否则仅使用内容
                    # tags format: reflection,category,level
                    level_tag = "INFO"
                    if m.tags:
                        if "critical" in m.tags:
                            level_tag = "CRITICAL"
                        elif "warning" in m.tags:
                            level_tag = "WARNING"

                    logs_text += f"- [{m.realTime}] ({level_tag}) {m.content}\n"
                return logs_text.strip()
        except Exception as e:
            logger.error(f"MemoryOps Read DB Error: {e}")

    # 回退到本地文件
    logs = _load_reflections_local()
    recent_logs = logs[:limit]

    if not recent_logs:
        return "目前还没有反思记录哦，表现很棒！"

    result = "【我的错题本 (来自本地备份)】\n"
    for log in recent_logs:
        result += f"- [{log['timestamp']}] ({log['level'].upper()}) {log['category']}: {log['content']}\n"

    return result.strip()


async def read_diary(limit: int = 5) -> str:
    """
    阅读“熔炼后的日记” (Consolidated Memories)。
    这些是记忆秘书整理过的、优美的日记体记忆。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session or not Memory:
        return "无法连接数据库，无法读取日记。"

    try:
        limit = int(limit)
    except Exception:
        limit = 5

    try:
        # source='secretary_merge' 是我们在 memory_secretary_service.py 中看到的
        # 获取活跃 Agent
        agent_id = "pero"
        if get_agent_manager:
            with contextlib.suppress(Exception):
                agent_id = get_agent_manager().active_agent_id

        statement = (
            select(Memory)
            .where(Memory.source == "secretary_merge")
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(limit)
        )
        memories = (await session.exec(statement)).all()

        if not memories:
            return "还没有生成过日记 (Consolidated Memories)。可能需要等待记忆秘书运行一次维护任务。"

        result = "【我的日记 (Consolidated Memories)】\n"
        for m in memories:
            result += f"### {m.realTime}\n{m.content}\n\n"

        return result.strip()
    except Exception as e:
        return f"读取日记失败: {e}"


async def read_maintenance_reports(limit: int = 5) -> str:
    """
    阅读“秘书周报” (Maintenance Records)。
    查看记忆秘书最近做了哪些整理工作。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session or not MaintenanceRecord:
        return "无法连接数据库，无法读取周报。"

    try:
        limit = int(limit)
    except Exception:
        limit = 5

    try:
        statement = (
            select(MaintenanceRecord)
            .order_by(desc(MaintenanceRecord.timestamp))
            .limit(limit)
        )
        records = (await session.exec(statement)).all()

        if not records:
            return "还没有维护记录。"

        result = "【秘书工作周报 (Maintenance Records)】\n"
        for r in records:
            result += f"- [{r.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
            result += f"提取偏好:{r.preferences_extracted}, "
            result += f"重要标记:{r.important_tagged}, "
            result += f"合并记忆:{r.consolidated}, "
            result += f"清理垃圾:{r.cleaned_count}\n"

        return result.strip()
    except Exception as e:
        return f"读取周报失败: {e}"


async def read_memory_by_cluster(cluster_name: str, limit: int = 10) -> str:
    """
    根据记忆簇 (Cluster) 读取记忆。
    例如读取 "[反思簇]" 或其他自定义簇的记忆。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session or not Memory:
        return "无法连接数据库，无法读取记忆簇。"

    try:
        limit = int(limit)
    except Exception:
        limit = 10

    try:
        # 使用 contains 来匹配，因为 clusters 可能是逗号分隔的字符串
        # 获取活跃 Agent
        agent_id = "pero"
        if get_agent_manager:
            with contextlib.suppress(Exception):
                agent_id = get_agent_manager().active_agent_id

        statement = (
            select(Memory)
            .where(Memory.clusters.contains(cluster_name))
            .where(Memory.agent_id == agent_id)
            .order_by(desc(Memory.timestamp))
            .limit(limit)
        )
        memories = (await session.exec(statement)).all()

        if not memories:
            return f"在簇 '{cluster_name}' 中没有找到记忆。"

        result = f"【记忆簇: {cluster_name}】\n"
        for m in memories:
            result += f"- [{m.realTime}] {m.content}\n"

        return result.strip()
    except Exception as e:
        return f"读取记忆簇失败: {e}"


# --- Task/Schedule Operations ---


async def add_schedule_task(time: str, content: str, type: str = "reminder") -> str:
    """
    添加定时任务（提醒或主题）。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session or not ScheduledTask:
        return "错误: 数据库会话不可用。"

    try:
        # 验证时间格式
        datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")

        task = ScheduledTask(time=time, content=content, type=type, is_triggered=False)
        session.add(task)
        await session.commit()
        return f"成功添加 {type}: '{content}' 于 {time} (ID: {task.id})"
    except ValueError:
        return "错误: 无效的时间格式。请使用 'YYYY-MM-DD HH:mm:ss'。"
    except Exception as e:
        return f"添加任务错误: {str(e)}"


async def list_pending_tasks() -> str:
    """列出所有待处理的定时任务。"""
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session or not ScheduledTask:
        return "错误: 数据库会话不可用。"

    tasks = (
        await session.exec(
            select(ScheduledTask).where(not ScheduledTask.is_triggered)
        )
    ).all()
    if not tasks:
        return "没有待处理的任务。"

    result = "待处理的任务:\n"
    for t in tasks:
        result += f"- [ID: {t.id}] {t.type.upper()} at {t.time}: {t.content}\n"
    return result


async def delete_schedule_task(task_id: int) -> str:
    """按 ID 删除定时任务。"""
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session or not ScheduledTask:
        return "错误: 数据库会话不可用。"

    task = await session.get(ScheduledTask, task_id)
    if not task:
        return f"错误: 未找到 ID 为 {task_id} 的任务。"

    await session.delete(task)
    await session.commit()
    return f"成功删除任务 {task_id}。"


async def add_pre_action(delay_seconds: int, content: str) -> str:
    """
    添加预动作（反应）任务。
    这些任务在延迟后触发，但如果用户在计时器到期前进行交互，则会被取消。
    """
    session = _CURRENT_SESSION_CONTEXT.get("db_session")
    if not session or not ScheduledTask:
        return "错误: 数据库会话不可用。"

    try:
        delay_seconds = int(delay_seconds)
        if delay_seconds <= 0:
            return "错误: delay_seconds 必须为正数。"

        trigger_time = datetime.datetime.now() + datetime.timedelta(
            seconds=delay_seconds
        )
        time_str = trigger_time.strftime("%Y-%m-%d %H:%M:%S")

        task = ScheduledTask(
            time=time_str,
            content=content,
            type="reaction",  # 特殊类型，如果用户输入则会被取消
            is_triggered=False,
        )
        session.add(task)
        await session.commit()
        return f"成功添加反应: '{content}' 于 {delay_seconds} 秒后 (在 {time_str})。注意: 如果用户说话，此任务将被取消。"
    except Exception as e:
        return f"添加预动作错误: {str(e)}"
