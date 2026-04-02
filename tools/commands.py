"""
Paper Agent — 快捷命令调度器

核心职责:
1. 解析用户高层指令（如 "初始化", "写 introduction", "检查全文"）
2. 将指令映射到工具调用序列
3. 编排多步工具调用的依赖关系
4. 收集并汇总执行结果

设计原则:
- 命令调度器本身不执行业务逻辑，只做编排
- 每个命令返回 CommandResult，包含步骤列表和最终状态
- Agent 可基于 CommandResult 向用户报告进展
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ============================================================
# 常量
# ============================================================

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent


# ============================================================
# 数据类
# ============================================================

@dataclass
class StepResult:
    """单个步骤的执行结果。"""
    name: str                    # 步骤名称
    tool: str                    # 调用的工具模块
    method: str                  # 调用的方法
    success: bool = True
    output: Any = None           # 工具返回值
    error: str = ""              # 错误信息

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        s = f"  {status} {self.name} ({self.tool}.{self.method})"
        if self.error:
            s += f" — {self.error}"
        return s


@dataclass
class CommandResult:
    """命令执行结果。"""
    command: str                              # 原始命令
    steps: list[StepResult] = field(default_factory=list)
    summary: str = ""                         # 汇总说明

    @property
    def success(self) -> bool:
        return all(s.success for s in self.steps)

    @property
    def failed_steps(self) -> list[StepResult]:
        return [s for s in self.steps if not s.success]

    def report(self) -> str:
        lines = [f"命令: {self.command}"]
        lines.append(f"状态: {'成功' if self.success else '部分失败'}")
        if self.steps:
            lines.append("步骤:")
            for s in self.steps:
                lines.append(str(s))
        if self.summary:
            lines.append(f"摘要: {self.summary}")
        return "\n".join(lines)


@dataclass
class CommandSpec:
    """命令定义。"""
    name: str               # 命令名
    pattern: str             # 匹配正则
    description: str         # 说明
    steps: list[dict]        # 步骤定义 [{"name":..., "tool":..., "method":..., "args":...}]


# ============================================================
# 核心类
# ============================================================

class CommandDispatcher:
    """快捷命令调度器。

    解析用户指令并映射到工具调用序列。
    实际执行由各工具自行完成，dispatcher 只做编排和结果收集。
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self._commands = self._register_commands()

    # ----------------------------------------------------------
    # 命令注册
    # ----------------------------------------------------------

    def _register_commands(self) -> list[CommandSpec]:
        """注册所有支持的命令。"""
        return [
            CommandSpec(
                name="初始化",
                pattern=r"^初始化$",
                description="扫描 data/ → 交互式问答 → 填充配置 → 生成报告",
                steps=[
                    {"name": "扫描数据层", "tool": "project_init", "method": "scan_data_layer"},
                    {"name": "生成 Manifest", "tool": "project_init", "method": "generate_manifest"},
                    {"name": "检查配置完备性", "tool": "project_init", "method": "check_completeness"},
                    {"name": "生成初始化报告", "tool": "project_init", "method": "generate_init_report"},
                ],
            ),
            CommandSpec(
                name="检查配置",
                pattern=r"^检查配置$",
                description="运行配置完备性检查 + 配置校验",
                steps=[
                    {"name": "完备性检查", "tool": "project_init", "method": "check_completeness"},
                    {"name": "配置校验", "tool": "config_validator", "method": "validate_all"},
                ],
            ),
            CommandSpec(
                name="检查全文",
                pattern=r"^检查全文$",
                description="运行 glossary_checker + paper_lint + config_validator",
                steps=[
                    {"name": "术语一致性检查", "tool": "glossary_checker", "method": "check_all"},
                    {"name": "论文质量检查", "tool": "paper_lint", "method": "check_all"},
                    {"name": "配置校验", "tool": "config_validator", "method": "validate_all"},
                ],
            ),
            CommandSpec(
                name="编译论文",
                pattern=r"^编译论文$",
                description="调用 LaTeX 编译器完整编译",
                steps=[
                    {"name": "完整编译", "tool": "latex_compiler", "method": "compile"},
                ],
            ),
            CommandSpec(
                name="快速编译",
                pattern=r"^快速编译$",
                description="调用 LaTeX 编译器快速编译（单次 xelatex）",
                steps=[
                    {"name": "快速编译", "tool": "latex_compiler", "method": "compile_quick"},
                ],
            ),
            CommandSpec(
                name="更新术语表",
                pattern=r"^更新术语表$",
                description="扫描全文术语不一致 → 生成修改建议",
                steps=[
                    {"name": "术语扫描", "tool": "glossary_checker", "method": "check_all"},
                ],
            ),
            CommandSpec(
                name="同步文献",
                pattern=r"^同步文献$",
                description="从 library.yaml 同步 references.bib",
                steps=[
                    {"name": "同步 .bib", "tool": "bib_manager", "method": "sync_bib"},
                ],
            ),
            CommandSpec(
                name="校验配置",
                pattern=r"^校验配置$",
                description="深度校验所有配置文件",
                steps=[
                    {"name": "配置校验", "tool": "config_validator", "method": "validate_all"},
                ],
            ),
            CommandSpec(
                name="写章节",
                pattern=r"^写\s*(.+)$",
                description="准备指定章节的写作上下文",
                steps=[
                    {"name": "加载大纲", "tool": "_context", "method": "load_outline"},
                    {"name": "加载论点", "tool": "_context", "method": "load_arguments"},
                    {"name": "加载配置", "tool": "_context", "method": "load_configs"},
                ],
            ),
            CommandSpec(
                name="分析数据",
                pattern=r"^分析\s*(.+)$",
                description="分析指定数据文件",
                steps=[
                    {"name": "加载 Manifest", "tool": "_context", "method": "load_manifest"},
                ],
            ),
            CommandSpec(
                name="添加文献",
                pattern=r"^添加文献\s*[\"\"\"']?(.+?)[\"\"\"']?$",
                description="添加新文献到 library.yaml",
                steps=[
                    {"name": "搜索文献", "tool": "bib_manager", "method": "search_local"},
                    {"name": "同步 .bib", "tool": "bib_manager", "method": "sync_bib"},
                ],
            ),
            CommandSpec(
                name="查看进度",
                pattern=r"^查看进度$",
                description="显示项目全局状态面板",
                steps=[
                    {"name": "生成状态面板", "tool": "memory_manager", "method": "get_dashboard"},
                ],
            ),
        ]

    # ----------------------------------------------------------
    # 命令解析
    # ----------------------------------------------------------

    def parse(self, user_input: str) -> tuple[CommandSpec | None, dict[str, str]]:
        """解析用户输入，返回匹配的命令和提取的参数。"""
        text = user_input.strip()
        for cmd in self._commands:
            m = re.match(cmd.pattern, text)
            if m:
                params = {}
                groups = m.groups()
                if groups:
                    params["target"] = groups[0].strip()
                return cmd, params
        return None, {}

    def list_commands(self) -> list[dict[str, str]]:
        """列出所有可用命令。"""
        return [
            {"name": cmd.name, "description": cmd.description}
            for cmd in self._commands
        ]

    # ----------------------------------------------------------
    # 命令执行
    # ----------------------------------------------------------

    def execute(self, user_input: str) -> CommandResult:
        """执行用户命令。

        解析输入 → 加载对应工具 → 按序执行步骤 → 收集结果。
        """
        cmd, params = self.parse(user_input)
        if cmd is None:
            return CommandResult(
                command=user_input,
                summary=f"未识别的命令: '{user_input}'，使用 list_commands() 查看可用命令",
            )

        result = CommandResult(command=user_input)

        for step_spec in cmd.steps:
            step = self._execute_step(step_spec, params)
            result.steps.append(step)
            # 如果关键步骤失败，停止后续执行
            if not step.success and step_spec.get("critical", False):
                break

        # 生成摘要
        ok_count = sum(1 for s in result.steps if s.success)
        total = len(result.steps)
        result.summary = f"完成 {ok_count}/{total} 步骤"

        return result

    def _execute_step(self, step_spec: dict, params: dict) -> StepResult:
        """执行单个步骤。"""
        step_name = step_spec["name"]
        tool_name = step_spec["tool"]
        method_name = step_spec["method"]

        # 上下文加载步骤（只读取文件，不调用工具）
        if tool_name == "_context":
            return self._execute_context_step(step_name, method_name, params)

        try:
            tool_instance = self._load_tool(tool_name)
            method = getattr(tool_instance, method_name, None)
            if method is None:
                return StepResult(
                    name=step_name, tool=tool_name, method=method_name,
                    success=False, error=f"方法 {method_name} 不存在")

            # 调用工具方法
            output = method()
            return StepResult(
                name=step_name, tool=tool_name, method=method_name,
                success=True, output=output)

        except Exception as e:
            return StepResult(
                name=step_name, tool=tool_name, method=method_name,
                success=False, error=str(e))

    def _load_tool(self, tool_name: str) -> Any:
        """延迟加载工具实例。"""
        if tool_name == "project_init":
            from tools.project_init import ProjectInitializer
            return ProjectInitializer(self.root)
        elif tool_name == "config_validator":
            from tools.config_validator import ConfigValidator
            return ConfigValidator(self.root)
        elif tool_name == "glossary_checker":
            from tools.glossary_checker import GlossaryChecker
            return GlossaryChecker(self.root)
        elif tool_name == "paper_lint":
            from tools.paper_lint import PaperLint
            return PaperLint(self.root)
        elif tool_name == "latex_compiler":
            from tools.latex_compiler import LaTeXCompiler
            return LaTeXCompiler(self.root)
        elif tool_name == "bib_manager":
            from tools.bib_manager import BibManager
            return BibManager(self.root)
        elif tool_name == "memory_manager":
            from tools.memory_manager import MemoryManager
            return MemoryManager(self.root)
        else:
            raise ValueError(f"未知工具: {tool_name}")

    def _execute_context_step(
        self, step_name: str, method: str, params: dict
    ) -> StepResult:
        """执行上下文加载步骤（只读文件返回内容）。"""
        try:
            if method == "load_outline":
                path = self.root / "pipeline" / "notes" / "outline.md"
                if not path.exists():
                    return StepResult(
                        name=step_name, tool="_context", method=method,
                        success=True, output="(大纲文件不存在)")
                content = path.read_text(encoding="utf-8", errors="ignore")
                return StepResult(
                    name=step_name, tool="_context", method=method,
                    success=True, output=content)

            elif method == "load_arguments":
                path = self.root / "pipeline" / "notes" / "arguments.md"
                if not path.exists():
                    return StepResult(
                        name=step_name, tool="_context", method=method,
                        success=True, output="(论点文件不存在)")
                content = path.read_text(encoding="utf-8", errors="ignore")
                return StepResult(
                    name=step_name, tool="_context", method=method,
                    success=True, output=content)

            elif method == "load_configs":
                configs = {}
                config_dir = self.root / "config"
                for name in ("paper.yaml", "glossary.yaml", "style-guide.md"):
                    p = config_dir / name
                    if p.exists():
                        configs[name] = p.read_text(encoding="utf-8", errors="ignore")
                return StepResult(
                    name=step_name, tool="_context", method=method,
                    success=True, output=configs)

            elif method == "load_manifest":
                path = self.root / "data" / "_manifest.yaml"
                if not path.exists():
                    return StepResult(
                        name=step_name, tool="_context", method=method,
                        success=True, output="(Manifest 不存在)")
                content = path.read_text(encoding="utf-8", errors="ignore")
                return StepResult(
                    name=step_name, tool="_context", method=method,
                    success=True, output=content)

            else:
                return StepResult(
                    name=step_name, tool="_context", method=method,
                    success=False, error=f"未知上下文方法: {method}")

        except Exception as e:
            return StepResult(
                name=step_name, tool="_context", method=method,
                success=False, error=str(e))


# ============================================================
# CLI 入口
# ============================================================

def main() -> None:
    import sys

    if len(sys.argv) < 2:
        dispatcher = CommandDispatcher()
        print("可用命令:")
        for cmd in dispatcher.list_commands():
            print(f"  {cmd['name']}: {cmd['description']}")
        return

    user_input = " ".join(sys.argv[1:])
    dispatcher = CommandDispatcher()
    result = dispatcher.execute(user_input)
    print(result.report())


if __name__ == "__main__":
    main()
