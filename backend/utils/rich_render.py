from typing import Any, Optional

from rich.console import Console
from rich.text import Text
from rich.tree import Tree


def build_rich_tree(
    data: Any, tree: Optional[Tree] = None, label: str = "Root"
) -> Tree:
    """
    递归地从字典或列表构建 Rich Tree。
    通过使用 Rich 的 Text 对象处理带有换行符的字符串。

    Args:
        data: 要渲染的数据（字典、列表或其他）。
        tree: 父树节点（用于递归）。
        label: 如果 tree 为 None，则作为根节点的标签。

    Returns:
        准备打印的 Rich Tree 对象。
    """
    if tree is None:
        tree = Tree(label)

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                branch = tree.add(f"[bold cyan]{key}[/]")
                build_rich_tree(value, branch)
            else:
                # 叶节点：渲染值
                _add_leaf_node(tree, key, value)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            if isinstance(item, (dict, list)):
                branch = tree.add(f"[bold magenta]#{index}[/]")
                build_rich_tree(item, branch)
            else:
                # 列表项叶节点
                _add_leaf_node(tree, f"#{index}", item)
    else:
        # 简单类型直接作为根节点回退
        tree.add(Text(str(data), style="green"))

    return tree


def _add_leaf_node(tree: Tree, key: str, value: Any):
    """添加带有适当样式的叶节点的辅助函数。"""
    text_content = Text(str(value))
    # 如果需要，可以在此处根据值类型或内容自定义样式
    text_content.stylize("green")

    # 组合键和值
    # 我们使用 Text.assemble 或仅使用 + 运算符
    label = Text(f"{key}: ", style="bold cyan") + text_content
    tree.add(label)


def print_rich_tree(data: Any, label: str = "Root"):
    """
    将数据打印为 Rich Tree 的便捷函数。
    """
    console = Console()
    tree = build_rich_tree(data, label=label)
    console.print(tree)
