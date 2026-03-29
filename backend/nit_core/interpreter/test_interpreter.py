import asyncio
from unittest import TestCase

import pytest

from .engine import NITRuntime
from .errors import NITLexerError, NITParserError
from .lexer import Lexer
from .parser import Parser


class TestNITInterpreter(TestCase):
    def test_lexer_error_position(self):
        source = "$var = 123 @ invalid"
        lexer = Lexer(source)
        with self.assertRaises(NITLexerError) as cm:
            lexer.tokenize()

        err = cm.exception
        self.assertEqual(err.line, 1)
        self.assertEqual(err.column, 12)
        self.assertIn("^--- 这里可能有错", str(err))

    def test_parser_error_position(self):
        source = "$var = tool_call(arg1='val'"  # 缺少右括号
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens, source)

        with self.assertRaises(NITParserError) as cm:
            parser.parse()

        err = cm.exception
        # 错误应位于 token 的末尾 (EOF)
        self.assertIn("TokenType.RPAREN", str(err))
        self.assertIn("^--- 这里可能有错", str(err))

    def test_runtime_simple_execution(self):
        """测试简单的工具调用与变量赋值。
        当 Rust 扩展可用时，AST 节点来自 Rust PyO3 类，构造签名不同于 Python dataclass。
        """
        from .engine import (
            RUST_AVAILABLE,
            AssignmentNode,
            CallNode,
            LiteralNode,
            PipelineNode,
        )

        async def mock_executor(name, args):
            if name == "add":
                return args["a"] + args["b"]
            return None

        if RUST_AVAILABLE:
            # Rust 版: LiteralNode(value, type_name), 其他节点接受 PyObject
            lit_a = LiteralNode(1, "number")
            lit_b = LiteralNode(2, "number")
            call_node = CallNode("add", {"a": lit_a, "b": lit_b})
            assignment = AssignmentNode("result", call_node)
            pipeline = PipelineNode([assignment])
        else:
            # Python 版: dataclass 关键字参数
            lit_a = LiteralNode(value=1)
            lit_b = LiteralNode(value=2)
            call_node = CallNode(tool_name="add", args={"a": lit_a, "b": lit_b})
            assignment = AssignmentNode(target_var="result", expression=call_node)
            pipeline = PipelineNode(statements=[assignment])

        runtime = NITRuntime(mock_executor)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(runtime.execute(pipeline))
        finally:
            loop.close()

        self.assertEqual(result, 3)
        # Rust NITScope 使用 .get()，Python dict 也支持 .get()
        self.assertEqual(runtime.variables.get("result"), 3)


if __name__ == "__main__":
    pytest.main([__file__])
