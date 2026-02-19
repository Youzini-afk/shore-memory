import json
import os

from utils.workspace_utils import get_workspace_root

# Define the workspace root relative to this file
# backend/nit_core/tools/work/WorkspaceOps/workspace_ops.py -> PeroCore/pero_workspace
# [重构] 使用动态工作空间根目录
# BASE_DIR = ...
# WORKSPACE_ROOT = ...


def _ensure_workspace():
    # 默认使用活跃 Agent 的工作空间
    root = get_workspace_root()
    if not os.path.exists(root):
        os.makedirs(root)


def _is_safe_path(file_path):
    # 确保路径在工作空间内
    # 解析相对路径
    try:
        workspace_root = get_workspace_root()
        # 将工作空间根目录与提供的路径连接
        # 注意：os.path.join 处理第二个参数中的绝对路径时会丢弃第一个参数，
        # 所以如果存在，我们必须去掉前导斜杠或盘符（虽然不太可能来自 LLM）
        # 但为了安全起见，我们将其视为相对路径。
        file_path = file_path.lstrip("/\\")
        abs_path = os.path.abspath(os.path.join(workspace_root, file_path))
        return abs_path.startswith(workspace_root)
    except Exception:
        return False


def write_workspace_file(filename: str, content: str) -> str:
    """
    将内容写入工作空间中的文件。
    """
    _ensure_workspace()
    if not _is_safe_path(filename):
        return "错误: 拒绝访问。你只能写入工作空间内的文件。"

    try:
        workspace_root = get_workspace_root()
        filename = filename.lstrip("/\\")
        full_path = os.path.join(workspace_root, filename)
        # 如果目录不存在则创建
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功写入 {filename}"
    except Exception as e:
        return f"写入文件错误: {str(e)}"


def read_workspace_file(filename: str) -> str:
    """
    从工作空间中的文件读取内容。
    """
    _ensure_workspace()
    if not _is_safe_path(filename):
        return "错误: 拒绝访问。你只能读取工作空间内的文件。"

    try:
        workspace_root = get_workspace_root()
        filename = filename.lstrip("/\\")
        full_path = os.path.join(workspace_root, filename)
        if not os.path.exists(full_path):
            return "错误: 未找到文件。"

        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取文件错误: {str(e)}"


def list_workspace_files(subdir: str = "") -> str:
    """
    列出工作空间中的文件。
    """
    _ensure_workspace()
    workspace_root = get_workspace_root()

    if subdir:
        if not _is_safe_path(subdir):
            return "错误: 拒绝访问。"
        target_dir = os.path.join(workspace_root, subdir.lstrip("/\\"))
    else:
        target_dir = workspace_root

    if not os.path.exists(target_dir):
        return "错误: 目录未找到。"

    try:
        file_list = []
        for root, _, filenames in os.walk(target_dir):
            for filename in filenames:
                # 获取相对于 WORKSPACE_ROOT 的相对路径
                abs_file = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_file, workspace_root)
                file_list.append(rel_path)

        if not file_list:
            return "工作空间为空。"

        return json.dumps(file_list, indent=2)
    except Exception as e:
        return f"列出文件错误: {str(e)}"


# 定义
write_workspace_file_definition = {
    "type": "function",
    "function": {
        "name": "write_workspace_file",
        "description": "在你的个人工作空间中创建或覆盖文本文件。使用此功能保存笔记、代码或任何文本内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "文件的相对路径 (例如 'notes.txt' 或 'code/script.py')。",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的文本内容。",
                },
            },
            "required": ["filename", "content"],
        },
    },
}

read_workspace_file_definition = {
    "type": "function",
    "function": {
        "name": "read_workspace_file",
        "description": "从你的个人工作空间读取文件内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "文件的相对路径。",
                }
            },
            "required": ["filename"],
        },
    },
}

list_workspace_files_definition = {
    "type": "function",
    "function": {
        "name": "list_workspace_files",
        "description": "列出当前存储在你的个人工作空间中的所有文件。",
        "parameters": {
            "type": "object",
            "properties": {
                "subdir": {
                    "type": "string",
                    "description": "要列出的可选子目录 (默认为根目录)。",
                    "default": "",
                }
            },
        },
    },
}
