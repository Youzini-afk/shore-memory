"""
[LEGACY/FALLBACK] Python AST 节点定义。
注意：当 Rust 扩展不可用时，或者用于 Python 回退路径中的类型提示时，将使用这些定义。
Rust 实现 (rust_binding/src/ast.rs) 镜像了此结构。
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union


@dataclass
class ASTNode:
    pass


@dataclass
class ValueNode(ASTNode):
    pass


@dataclass
class LiteralNode(ValueNode):
    value: Union[str, int, float, bool]


@dataclass
class VariableRefNode(ValueNode):
    name: str


@dataclass
class ListNode(ValueNode):
    elements: List[ValueNode]


@dataclass
class CallNode(ASTNode):
    tool_name: str
    args: Dict[str, ValueNode]
    is_async: bool = False
    callback: Optional[str] = None  # 用于异步回调任务名称


@dataclass
class AssignmentNode(ASTNode):
    target_var: str
    expression: CallNode


@dataclass
class PipelineNode(ASTNode):
    statements: List[Union[AssignmentNode, CallNode]]
