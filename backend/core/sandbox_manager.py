import ast
import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any, Dict

from wasmtime import Engine, Linker, Module, Store

# 配置日志
logger = logging.getLogger(__name__)


class SecurityVisitor(ast.NodeVisitor):
    """
    AST 访问器，用于静态分析 Python 代码中的风险操作。
    """

    def __init__(self):
        self.risk_level = 0
        self.reasons = []
        self.imports = set()
        self.calls = set()

        # 风险定义
        self.RISK_RULES = {
            # 模块导入风险
            "imports": {
                "os": 4,
                "subprocess": 4,
                "sys": 3,
                "shutil": 4,
                "socket": 3,
                "requests": 3,
                "urllib": 3,
                "pickle": 4,
                "marshal": 4,
                "shelve": 3,
                "ctypes": 4,
                "builtins": 4,
                "importlib": 4,
            },
            # 函数调用风险
            "calls": {
                "eval": 4,
                "exec": 4,
                "compile": 4,
                "open": 3,
                "__import__": 4,
                "globals": 3,
                "locals": 2,
                "input": 2,
                "breakpoint": 3,
                "help": 1,
                "exit": 2,
                "quit": 2,
            },
            # 特定属性访问风险 (如 os.system)
            "attributes": {
                "os.system": 4,
                "os.popen": 4,
                "os.remove": 4,
                "os.rmdir": 4,
                "os.environ": 3,
                "subprocess.run": 4,
                "subprocess.Popen": 4,
                "subprocess.call": 4,
                "sys.modules": 3,
                "sys.exit": 2,
            },
        }

    def _add_risk(self, level: int, reason: str):
        if level > self.risk_level:
            self.risk_level = level
        self.reasons.append(f"[{level}] {reason}")

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.name.split(".")[0]
            self.imports.add(name)
            if name in self.RISK_RULES["imports"]:
                level = self.RISK_RULES["imports"][name]
                self._add_risk(level, f"Import detected: {name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            module_name = node.module.split(".")[0]
            self.imports.add(module_name)
            if module_name in self.RISK_RULES["imports"]:
                level = self.RISK_RULES["imports"][module_name]
                self._add_risk(level, f"Import detected: {module_name}")
        self.generic_visit(node)

    def visit_Call(self, node):
        # 检查直接函数调用，如 eval()
        if isinstance(node.func, ast.Name):
            name = node.func.id
            self.calls.add(name)
            if name in self.RISK_RULES["calls"]:
                level = self.RISK_RULES["calls"][name]
                self._add_risk(level, f"Function call detected: {name}")

        # 检查属性调用，如 os.system()
        elif isinstance(node.func, ast.Attribute):
            # 尝试解析 value.attr 形式
            if isinstance(node.func.value, ast.Name):
                module = node.func.value.id
                method = node.func.attr
                full_name = f"{module}.{method}"
                if full_name in self.RISK_RULES["attributes"]:
                    level = self.RISK_RULES["attributes"][full_name]
                    self._add_risk(level, f"Attribute call detected: {full_name}")

        self.generic_visit(node)


# Wasm 审计器路径 (复用 TerminalExecutor 的 WASM)
# 假设 backend 根目录是工作目录，WASM 文件位于 nit_core/tools/work/TerminalExecutor/auditor.wasm
# 我们需要动态定位
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# 回退到 backend 目录
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
WASM_PATH = os.path.join(
    BACKEND_DIR, "nit_core", "tools", "work", "TerminalExecutor", "auditor.wasm"
)


class SandboxManager:
    _instance = None
    _wasm_engine = None
    _wasm_module = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SandboxManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # 确保数据目录结构
        # 使用 backend/data 目录
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = os.path.join(backend_dir, "data")
        self.sandbox_root = os.path.join(self.data_dir, "sandbox")
        os.makedirs(self.sandbox_root, exist_ok=True)

        # 修复 WASM 路径定位
        # 假设 backend 根目录是工作目录，WASM 文件位于 nit_core/tools/work/TerminalExecutor/auditor.wasm
        # 实际部署时可能需要调整
        self.wasm_path = os.path.join(
            backend_dir, "nit_core", "tools", "work", "TerminalExecutor", "auditor.wasm"
        )

        logger.info(f"Sandbox manager initialized. Root: {self.sandbox_root}")
        logger.info(f"WASM Path: {self.wasm_path}")

    def _get_wasm_module(self):
        """延迟加载 WASM 模块"""
        if self._wasm_module is None:
            if not os.path.exists(self.wasm_path):
                logger.warning(f"WASM auditor not found at {self.wasm_path}")
                # 尝试备用路径（开发环境）
                dev_path = os.path.join(
                    os.path.dirname(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    ),
                    "nit_core",
                    "tools",
                    "work",
                    "TerminalExecutor",
                    "auditor.wasm",
                )
                if os.path.exists(dev_path):
                    self.wasm_path = dev_path
                    logger.info(f"Found WASM at dev path: {self.wasm_path}")
                else:
                    return None

            try:
                logger.info(f"Loading Wasm auditor from {self.wasm_path}")
                self._wasm_engine = Engine()
                self._wasm_module = Module.from_file(self._wasm_engine, self.wasm_path)
            except Exception as e:
                logger.error(f"Failed to load Wasm module: {e}")
                return None
        return self._wasm_module

    def _audit_with_ast(self, code: str) -> Dict[str, Any]:
        """
        使用 Python AST 进行静态代码分析
        """
        try:
            tree = ast.parse(code)
            visitor = SecurityVisitor()
            visitor.visit(tree)

            # 整合风险
            risk_level = visitor.risk_level
            reasons = visitor.reasons

            # 如果没有风险，且代码不为空，视为 Safe (0) 或 Notice (1)
            # 这里简单起见，如果没有检测到风险，返回 Safe
            reason = "AST check passed" if risk_level == 0 else "; ".join(reasons)

            return {"level": risk_level, "reason": reason, "highlight": None}

        except SyntaxError as e:
            return {
                "level": 1,  # 语法错误本身不是安全风险，但在执行时会失败
                "reason": f"Syntax Error: {e}",
                "highlight": None,
            }
        except Exception as e:
            return {"level": 2, "reason": f"AST Analysis Error: {e}", "highlight": None}

    def audit_code(self, code: str) -> Dict[str, Any]:
        """
        综合审计代码风险（AST + WASM）
        """
        # 1. AST 审计 (专门针对 Python 代码)
        ast_result = self._audit_with_ast(code)

        # 2. WASM 审计 (作为补充，主要针对 Shell 命令模式)
        wasm_result = {"level": 0, "reason": ""}
        module = self._get_wasm_module()
        if module:
            try:
                store = Store(self._wasm_engine)
                linker = Linker(self._wasm_engine)
                instance = linker.instantiate(store, module)
                exports = instance.exports(store)

                memory = exports["memory"]
                alloc = exports["alloc"]
                audit_abi = exports["audit_command_abi"]

                # 截取前 1000 字符进行 POC 检查
                check_content = code[:1000]
                cmd_bytes = check_content.encode("utf-8")
                cmd_len = len(cmd_bytes)
                ptr = alloc(store, cmd_len)

                try:
                    memory.write(store, cmd_bytes, ptr)
                except Exception:
                    memory.write(store, ptr, cmd_bytes)

                packed_res = audit_abi(store, ptr, cmd_len)
                res_ptr = packed_res & 0xFFFFFFFF
                res_len = (packed_res >> 32) & 0xFFFFFFFF

                json_bytes = memory.read(store, res_ptr, res_ptr + res_len)
                json_str = bytes(json_bytes).decode("utf-8")
                result = json.loads(json_str)

                # 映射 Level
                if isinstance(result.get("level"), str):
                    level_map = {"Safe": 0, "Notice": 1, "Warn": 2, "Block": 3}
                    wasm_result["level"] = level_map.get(result["level"], 1)
                    wasm_result["reason"] = result.get("reason", "")
            except Exception as e:
                logger.error(f"Wasm execution error: {e}")

        # 3. 综合结果
        # 如果 AST 明确为 0，且 WASM <= 1，则保持 0，避免 WASM 的通用 Notice 误报
        if ast_result["level"] == 0 and wasm_result["level"] <= 1:
            final_level = 0
        else:
            final_level = max(ast_result["level"], wasm_result["level"])

        # 合并原因
        reasons = []
        if ast_result["reason"]:
            reasons.append(f"[AST] {ast_result['reason']}")
        if (
            wasm_result["reason"] and wasm_result["level"] > 1
        ):  # 只有 WASM > 1 才记录原因，或者当最终 Level > 0 时
            reasons.append(f"[WASM] {wasm_result['reason']}")
        elif (
            wasm_result["reason"] and final_level > 0
        ):  # 如果最终不是 0，记录 WASM 原因
            reasons.append(f"[WASM] {wasm_result['reason']}")

        final_reason = " | ".join(reasons) if reasons else "Safe"

        return {
            "level": final_level,
            "reason": final_reason,
            "highlight": ast_result.get("highlight") or wasm_result.get("highlight"),
        }

    async def run_python_code(self, code: str, timeout: int = 10) -> Dict[str, Any]:
        """
        在沙箱环境中运行 Python 代码。

        参数:
            code: 要运行的 Python 代码
            timeout: 超时时间（秒）

        返回:
            {
                "success": bool,
                "output": str,
                "error": str,
                "risk_level": int,
                "audit_reason": str
            }
        """
        # 1. 审计代码
        audit_result = self.audit_code(code)
        if audit_result["level"] >= 3:
            return {
                "success": False,
                "output": "",
                "error": f"Security Blocked: {audit_result['reason']}",
                "risk_level": audit_result["level"],
                "audit_reason": audit_result["reason"],
            }

        # 2. 准备沙箱环境
        session_id = str(uuid.uuid4())
        workspace_dir = os.path.join(self.sandbox_root, session_id)
        os.makedirs(workspace_dir, exist_ok=True)

        script_path = os.path.join(workspace_dir, "main.py")
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Failed to write script: {str(e)}",
                "risk_level": 0,
                "audit_reason": "File system error",
            }

        # 3. 执行代码
        # 使用 subprocess 在独立进程中运行，限制 cwd 为沙箱目录
        # 注意：这里还没有做真正的系统级隔离（如 chroot/docker），只是简单的目录隔离
        try:
            # 构造运行命令
            # 强制启用 -u (unbuffered)
            cmd = [sys.executable, "-u", "main.py"]

            # 设置环境变量，强制 UTF-8 输出
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=workspace_dir,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                output = stdout.decode("utf-8", errors="replace")
                error = stderr.decode("utf-8", errors="replace")

                return {
                    "success": process.returncode == 0,
                    "output": output,
                    "error": error,
                    "risk_level": audit_result["level"],
                    "audit_reason": audit_result["reason"],
                }

            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "output": "",
                    "error": f"Execution timed out after {timeout}s",
                    "risk_level": audit_result["level"],
                    "audit_reason": "Timeout",
                }

        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Execution failed: {str(e)}",
                "risk_level": audit_result["level"],
                "audit_reason": "Runtime error",
            }
        finally:
            # 4. 清理环境
            # 可以在这里删除 workspace_dir，或者保留作为日志
            # 目前保留以便调试，可以添加定期清理逻辑
            pass


# 全局单例
sandbox_manager = SandboxManager()
