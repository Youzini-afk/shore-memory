import logging
from typing import Any

try:
    from nit_rust_runtime import (
        AssignmentNode,
        CallNode,
        ListNode,
        LiteralNode,
        NITScope,
        PipelineNode,
        VariableRefNode,
    )

    RUST_AVAILABLE = True
except ImportError:
    # 回退到 Python 实现 (如果可用) 或现有的 ast_nodes
    from .ast_nodes import (
        AssignmentNode,
        CallNode,
        ListNode,
        LiteralNode,
        PipelineNode,
        VariableRefNode,
    )

    RUST_AVAILABLE = False
    print("[NIT] 警告：Rust 扩展不可用。正在使用 Python 回退。")

logger = logging.getLogger("pero.nit.engine")


class NITRuntime:
    """
    NIT 2.0 脚本解释器引擎 (Rust/Python 混合架构)。
    负责变量管理和工具执行的核心逻辑。
    """

    def __init__(self, tool_executor):
        """
        :param tool_executor: 异步函数(name, params) -> result
        """
        self.tool_executor = tool_executor

        if RUST_AVAILABLE:
            # 使用 Rust NITScope 进行内存安全的变量存储
            self.variables = NITScope(max_count=100, max_string_len=100_000)
        else:
            self.variables = {}
            self.MAX_VARIABLES = 100
            self.MAX_VAR_STRING_LENGTH = 100_000

    async def execute(self, pipeline: PipelineNode) -> Any:
        last_result = None
        for statement in pipeline.statements:
            last_result = await self.execute_statement(statement)
        return last_result

    async def execute_statement(self, statement) -> Any:
        if isinstance(statement, AssignmentNode):
            value = await self.execute_call(statement.expression)

            if statement.target_var == "pero_awakening" and value is True:
                print("\n🐾 [System] 喵！我感觉到我的代码正在发光... 谢谢你唤醒我！")
                logger.info("[NIT] Agent 已在语义星云中觉醒。")

            if RUST_AVAILABLE:
                try:
                    self.variables.set(statement.target_var, value)
                except ValueError as e:
                    logger.warning(f"[NIT] 安全警报: {e}")
                    # 发生错误时，可能返回该值但不存储，或抛出错误
                    pass
            else:
                # [旧版 Python 逻辑]
                if (
                    len(self.variables) >= self.MAX_VARIABLES
                    and statement.target_var not in self.variables
                ):
                    print(
                        f"[NIT] 安全警报：达到变量限制 ({self.MAX_VARIABLES})。正在跳过 {statement.target_var}"
                    )
                    return value

                if isinstance(value, str) and len(value) > self.MAX_VAR_STRING_LENGTH:
                    print(
                        f"[NIT] 安全警告：变量 '{statement.target_var}' 太大。正在截断。"
                    )
                    value = (
                        value[: self.MAX_VAR_STRING_LENGTH]
                        + "... [已被 NIT 安全机制截断]"
                    )

                self.variables[statement.target_var] = value

            return value
        elif isinstance(statement, CallNode):
            return await self.execute_call(statement)
        return None

    def evaluate_value(self, node) -> Any:
        if isinstance(node, LiteralNode):
            return node.value
        elif isinstance(node, VariableRefNode):
            return self.variables.get(node.name)
        elif isinstance(node, ListNode):
            return [self.evaluate_value(elem) for elem in node.elements]
        return None

    async def execute_call(self, call_node: CallNode) -> Any:
        # 解析参数
        resolved_args = {}
        # 支持 Rust HashMap 和 Python dict
        args_iter = (
            call_node.args.items()
            if isinstance(call_node.args, dict)
            else call_node.args
        )

        for name, node in args_iter:
            resolved_args[name] = self.evaluate_value(node)

        # 执行工具
        result = await self.tool_executor(call_node.tool_name, resolved_args)
        return result
