import os
import shutil

from core.path_resolver import path_resolver
from services.agent.agent_manager import get_agent_manager

# 基础工作区目录 (统一迁移至 @data/workspace 目录下)
# 之前的逻辑是位于项目根目录的 pero_workspace
GLOBAL_WORKSPACE_ROOT = path_resolver.resolve("@data/workspace")


def _migrate_workspace():
    """
    [迁移逻辑]
    将旧版位于项目根目录下的 pero_workspace 迁移至新的 @data 目录下。
    """
    try:
        # 探测旧目录 (backend/../../pero_workspace)
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        old_workspace_root = os.path.join(base_dir, "pero_workspace")

        if (
            os.path.exists(old_workspace_root)
            and os.path.isdir(old_workspace_root)
            and not os.path.exists(GLOBAL_WORKSPACE_ROOT)
        ):
            # 确保父目录存在
            os.makedirs(os.path.dirname(GLOBAL_WORKSPACE_ROOT), exist_ok=True)

            # 移动目录
            shutil.move(old_workspace_root, GLOBAL_WORKSPACE_ROOT)
            print(
                f"[Workspace] 已将旧工作区从 {old_workspace_root} 迁移至 {GLOBAL_WORKSPACE_ROOT}"
            )
    except Exception as e:
        print(f"[Workspace] 迁移工作区失败: {e}")


# 执行迁移
_migrate_workspace()


def get_workspace_root(agent_id: str = None) -> str:
    """
    获取特定 Agent 的工作区根目录。
    如果未提供 agent_id，则使用当前活跃的 Agent。

    结构:
    - pero_workspace/
      - {agent_id}/  <-- 返回的路径
    """
    if not agent_id:
        try:
            manager = get_agent_manager()
            agent = manager.get_active_agent()
            agent_id = agent.id if agent else "pero"
        except Exception:
            agent_id = "pero"  # 如果管理器失败（例如初始化期间），则回退

    # 将 agent_id 规范化为小写
    agent_id = str(agent_id).lower()

    # 目标目录
    target_path = os.path.join(GLOBAL_WORKSPACE_ROOT, agent_id)

    if not os.path.exists(target_path):
        os.makedirs(target_path, exist_ok=True)

    return target_path


def get_global_workspace_root() -> str:
    """
    获取工作空间文件夹的物理根目录（所有 Agent 文件夹的父目录）。
    对于系统级操作很有用。
    """
    if not os.path.exists(GLOBAL_WORKSPACE_ROOT):
        os.makedirs(GLOBAL_WORKSPACE_ROOT, exist_ok=True)
    return GLOBAL_WORKSPACE_ROOT
