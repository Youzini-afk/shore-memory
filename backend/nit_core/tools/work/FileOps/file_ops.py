import ast
import json
import logging
import os
import re

import docx
import pypdf

from utils.workspace_utils import get_workspace_root

# 定义工作空间根目录，强制隔离所有文件操作
# backend/nit_core/tools/work/FileOps/file_ops.py -> PeroCore/pero_workspace
# [重构] 使用动态工作空间根目录
# BASE_DIR = ...
# WORKSPACE_ROOT = ...

logger = logging.getLogger(__name__)


def _get_safe_path(input_path: str) -> str:
    """
    校验路径是否逃逸出工作空间。
    如果 input_path 是绝对路径，则检查其是否在 WORKSPACE_ROOT 内。
    如果 input_path 是相对路径，则将其拼接到 WORKSPACE_ROOT 后并校验。
    """
    # 获取当前活跃 Agent 的工作空间
    workspace_root = get_workspace_root()

    # 确保根目录存在
    if not os.path.exists(workspace_root):
        os.makedirs(workspace_root, exist_ok=True)

    # 处理可能的空输入或当前目录表示
    if not input_path or input_path.strip() in [".", "./"]:
        return workspace_root

    # 统一解析为绝对路径
    # [修复] 如果 input_path 是绝对路径但不是以 workspace_root 开头，强制视为相对路径处理
    # 这样可以防止用户传入 "C:\Windows\System32" 这种路径
    # 但允许传入已经正确的绝对路径 "C:\PeroCore\pero_workspace\pero\file.txt"

    temp_abs_path = os.path.abspath(input_path) if os.path.isabs(input_path) else ""

    if temp_abs_path and temp_abs_path.startswith(workspace_root):
        target_path = temp_abs_path
    else:
        # 视为相对路径
        # 移除可能的盘符和前导斜杠
        clean_path = input_path.lstrip("/\\")
        # 如果包含冒号（盘符），也移除
        if ":" in clean_path:
            clean_path = clean_path.split(":", 1)[1].lstrip("/\\")

        target_path = os.path.abspath(os.path.join(workspace_root, clean_path))

    # 路径逃逸校验：目标路径必须以工作空间根路径开头
    if not target_path.startswith(workspace_root):
        raise PermissionError(
            f"拒绝访问：检测到路径遍历。目标: {target_path} 在 {workspace_root} 之外"
        )

    return target_path


def validate_code(file_path: str, content: str) -> list:
    """
    简单代码验证器。
    目前支持通过 ast 进行 Python 语法检查。
    返回错误消息列表。
    """
    errors = []
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".py":
        try:
            ast.parse(content)
        except SyntaxError as e:
            errors.append(f"Line {e.lineno}, Col {e.offset}: {e.msg}")
        except Exception as e:
            errors.append(f"AST Parse Error: {str(e)}")

    # 未来：如果需要，添加 JS/TS/CSS 检查，如果可用，可能会调用外部工具。

    return errors


def apply_diff_logic(original_content: str, diff_content: str) -> str:
    """
    将差异块应用于原始内容。
    支持两种格式：
    1. 标准 (7 chars): <<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE
    2. 简洁 (4 chars):    <<<< SEARCH ... ==== ... >>>> REPLACE

    特性：
    - SEARCH 块中的通配符 '...' 匹配任何内容（非贪婪）。
    - 空白标准化（忽略 \\r）。
    """
    # 1. 标准化原始内容中的换行符
    # 我们在内部使用 \n 以保持匹配一致性
    original_normalized = original_content.replace("\r\n", "\n")

    # 2. 解析 Diff 内容
    start_marker_7 = "<<<<<<< SEARCH"
    start_marker_4 = "<<<< SEARCH"

    if start_marker_7 in diff_content:
        start_marker = start_marker_7
        mid_marker = "======="
        end_marker = ">>>>>>> REPLACE"
    elif start_marker_4 in diff_content:
        start_marker = start_marker_4
        mid_marker = "===="
        end_marker = ">>>> REPLACE"
    else:
        raise ValueError(
            "无效的 diff 格式: 未找到 SEARCH 块 (已检查 <<<<<<< SEARCH 和 <<<< SEARCH)。"
        )

    # 提取块
    try:
        # 按 start_marker 分割，取第二部分（第一个块）
        block = diff_content.split(start_marker, 1)[1]

        if mid_marker not in block:
            raise ValueError(f"无效的 diff 格式: 缺少 {mid_marker} 分隔符。")

        parts = block.split(mid_marker)
        search_part = parts[0]

        if end_marker not in parts[1]:
            raise ValueError(f"无效的 diff 格式: 缺少 {end_marker} 分隔符。")

        replace_part = parts[1].split(end_marker)[0]
    except IndexError:
        raise ValueError("无效的 diff 格式: 结构解析失败。") from None

    # 3. 处理搜索内容
    # 支持旧版 '-------' 分隔符
    if "-------" in search_part:
        search_content = search_part.split("-------", 1)[1]
    else:
        search_content = search_part

    # 从搜索内容的开头/结尾修剪空行，以避免严格的空白问题
    search_content = search_content.strip("\n")
    replace_content = replace_part.strip("\n")

    # 标准化搜索内容换行符
    search_content = search_content.replace("\r\n", "\n")

    # 4. 构造匹配正则
    # 转义特殊字符
    search_pattern = re.escape(search_content)

    # 将转义的 '...' 替换为非贪婪通配符
    # re.escape 可能会根据版本产生 '\.\.\.' 或 '...'
    search_pattern = search_pattern.replace(r"\.\.\.", r"[\s\S]*?")
    search_pattern = search_pattern.replace("...", r"[\s\S]*?")

    # 5. 查找并替换
    # 使用 re.search 查找范围
    match = re.search(search_pattern, original_normalized)

    if match:
        start, end = match.span()
        # 使用切片替换，比 re.sub 对于字面替换字符串更安全
        modified_content = (
            original_normalized[:start] + replace_content + original_normalized[end:]
        )
        return modified_content
    else:
        # 回退：如果未使用通配符，也许尝试精确字符串匹配以防正则表达式失败？
        # 但正则表达式应覆盖精确匹配。
        # 让我们引发带有调试信息的错误。
        raise ValueError(
            f"Diff 应用失败: 未找到 SEARCH 内容。\n搜索模式: {search_pattern[:200]}..."
        )


async def read_file_content(file_path: str, **kwargs) -> str:
    """
    读取文件内容，支持 TXT, MD, PDF, DOCX。（沙箱化）
    """
    try:
        safe_path = _get_safe_path(file_path)

        if not os.path.exists(safe_path):
            return f"错误: 在 {file_path} 未找到文件"

        if os.path.isdir(safe_path):
            return f"错误: '{file_path}' 是一个目录，请改用 list_directory。"

        _, ext = os.path.splitext(safe_path)
        ext = ext.lower()

        if ext == ".pdf":
            reader = pypdf.PdfReader(safe_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text

        elif ext in [".docx", ".doc"]:
            doc = docx.Document(safe_path)
            text = "\n".join([para.text for para in doc.paragraphs])
            return text

        else:
            # 假设为文本文件
            with open(safe_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"读取文件错误: {str(e)}"


async def list_directory(path: str = ".", **kwargs) -> str:
    """
    列出目录中的文件。（沙箱化）
    """
    try:
        safe_path = _get_safe_path(path)

        if not os.path.exists(safe_path):
            return "错误: 目录未找到。"
        if not os.path.isdir(safe_path):
            return "错误: 路径不是目录。"

        items = os.listdir(safe_path)
        return json.dumps(items, indent=2)
    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"列出目录错误: {str(e)}"


async def write_file(file_path: str, content: str, **kwargs) -> str:
    """
    将内容写入文件。（沙箱化 & 验证）
    """
    try:
        safe_path = _get_safe_path(file_path)

        # 1. 验证代码
        errors = validate_code(safe_path, content)
        validation_msg = ""
        if errors:
            validation_msg = "\n\n[警告] 代码验证问题:\n" + "\n".join(
                errors
            )
            # 我们不阻止写入，但会警告用户。

        # 2. 写入文件
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"文件已成功写入 {file_path}。{validation_msg}"

    except PermissionError as pe:
        return str(pe)
    except Exception as e:
        return f"写入文件错误: {str(e)}"


async def apply_diff(file_path: str, diff_content: str, **kwargs) -> str:
    """
    对文件应用智能差异 (Diff)。
    """
    try:
        safe_path = _get_safe_path(file_path)

        if not os.path.exists(safe_path):
            return f"错误: 在 {file_path} 未找到文件"

        # 1. 读取原始内容
        with open(safe_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        # 2. 应用 Diff
        try:
            new_content = apply_diff_logic(original_content, diff_content)
        except ValueError as ve:
            return f"Diff 错误: {str(ve)}"

        # 3. 验证新代码
        errors = validate_code(safe_path, new_content)
        validation_msg = ""
        if errors:
            validation_msg = "\n\n[警告] 代码验证问题:\n" + "\n".join(
                errors
            )

        # 4. 写回
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Diff 已成功应用到 {file_path}。{validation_msg}"

    except Exception as e:
        return f"应用 Diff 错误: {str(e)}"
