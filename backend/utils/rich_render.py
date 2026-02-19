from typing import Any, Optional

from rich.console import Console
from rich.text import Text
from rich.tree import Tree


def build_rich_tree(
    data: Any, tree: Optional[Tree] = None, label: str = "Root"
) -> Tree:
    """
    Recursively builds a Rich Tree from a dictionary or list.
    Handles strings with newlines by using Rich's Text object.

    Args:
        data: The data to render (dict, list, or other).
        tree: The parent tree node (used for recursion).
        label: The label for the root node if tree is None.

    Returns:
        A Rich Tree object ready for printing.
    """
    if tree is None:
        tree = Tree(label)

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                branch = tree.add(f"[bold cyan]{key}[/]")
                build_rich_tree(value, branch)
            else:
                # Leaf node: render value
                _add_leaf_node(tree, key, value)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            if isinstance(item, (dict, list)):
                branch = tree.add(f"[bold magenta]#{index}[/]")
                build_rich_tree(item, branch)
            else:
                # List item leaf
                _add_leaf_node(tree, f"#{index}", item)
    else:
        # Fallback for simple types passed directly as root
        tree.add(Text(str(data), style="green"))

    return tree


def _add_leaf_node(tree: Tree, key: str, value: Any):
    """Helper to add a leaf node with proper styling."""
    text_content = Text(str(value))
    # You can customize styles based on value type or content here if needed
    text_content.stylize("green")

    # Combine key and value
    # We use Text.assemble or just + operator
    label = Text(f"{key}: ", style="bold cyan") + text_content
    tree.add(label)


def print_rich_tree(data: Any, label: str = "Root"):
    """
    Convenience function to print data as a Rich Tree.
    """
    console = Console()
    tree = build_rich_tree(data, label=label)
    console.print(tree)
