import os

from services.agent_manager import get_agent_manager

# Base workspace directory (PeroCore/pero_workspace)
# Assuming this file is in backend/utils/workspace_utils.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GLOBAL_WORKSPACE_ROOT = os.path.join(BASE_DIR, "pero_workspace")


def get_workspace_root(agent_id: str = None) -> str:
    """
    Get the workspace root for a specific agent.
    If agent_id is not provided, it uses the currently active agent.

    Structure:
    - pero_workspace/
      - {agent_id}/  <-- Returned path
    """
    if not agent_id:
        try:
            manager = get_agent_manager()
            agent = manager.get_active_agent()
            agent_id = agent.id if agent else "pero"
        except Exception:
            agent_id = "pero"  # Fallback if manager fails (e.g. during init)

    # Normalize agent_id to lowercase
    agent_id = str(agent_id).lower()

    # Target directory
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
