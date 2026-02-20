import os

from services.agent.agent_manager import get_agent_manager

# 基础工作区目录 (PeroCore/pero_workspace)
# 假设此文件位于 backend/utils/workspace_utils.py
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GLOBAL_WORKSPACE_ROOT = os.path.join(BASE_DIR, "pero_workspace")


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
