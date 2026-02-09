from typing import Optional


class NITError(Exception):
    """NIT 解释器错误基类。"""

    def __init__(
        self, message: str, line: int, column: int, source: Optional[str] = None
    ):
        self.message = message
        self.line = line
        self.column = column
        self.source = source
        super().__init__(self.format_error())

    def format_error(self) -> str:
        error_msg = (
            f"NIT 错误 (第 {self.line} 行, 第 {self.column} 列): {self.message}\n"
        )
        if self.source:
            lines = self.source.split("\n")
            if 0 < self.line <= len(lines):
                target_line = lines[self.line - 1]
                error_msg += f"  {self.line} | {target_line}\n"
                error_msg += (
                    " " * (len(str(self.line)) + 3 + self.column) + "^--- 这里可能有错"
                )
        return error_msg


class NITLexerError(NITError):
    """词法分析过程中的错误。"""

    pass


class NITParserError(NITError):
    """解析过程中的错误。"""

    pass


class NITRuntimeError(NITError):
    """执行过程中的错误。"""

    pass
