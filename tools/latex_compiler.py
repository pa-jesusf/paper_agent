"""
Paper Agent — LaTeX 编译工具

核心职责:
1. 调用 xelatex 编译论文
2. 运行 bibtex 处理参考文献
3. 解析编译错误和警告
4. 提供编译状态报告

设计原则:
- 支持完整编译流程: xelatex → bibtex → xelatex × 2
- 错误信息结构化，便于 Agent 理解和修复
"""

from __future__ import annotations

import os
import re
import subprocess
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
class CompileError:
    """单个编译错误或警告。"""
    level: str          # "error" | "warning"
    file: str           # 出错文件
    line: int | None    # 行号（可能为 None）
    message: str        # 错误信息

    def __str__(self) -> str:
        tag = "ERROR" if self.level == "error" else "WARN"
        loc = f"{self.file}:{self.line}" if self.line else self.file
        return f"[{tag}] {loc} — {self.message}"


@dataclass
class CompileResult:
    """编译结果。"""
    success: bool = False
    pdf_path: str = ""
    errors: list[CompileError] = field(default_factory=list)
    warnings: list[CompileError] = field(default_factory=list)
    log_output: str = ""
    return_code: int = -1

    def summary(self) -> str:
        status = "✓ 编译成功" if self.success else "✗ 编译失败"
        lines = [f"LaTeX 编译: {status}"]
        if self.success and self.pdf_path:
            lines.append(f"  PDF: {self.pdf_path}")
        if self.errors:
            lines.append(f"  错误 ({len(self.errors)}):")
            for err in self.errors:
                lines.append(f"    {err}")
        if self.warnings:
            lines.append(f"  警告 ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                lines.append(f"    {w}")
            if len(self.warnings) > 5:
                lines.append(f"    ... 还有 {len(self.warnings) - 5} 条警告")
        return "\n".join(lines)


# ============================================================
# 核心类
# ============================================================

class LaTeXCompiler:
    """LaTeX 编译器封装。

    从 config/paper.yaml 读取编译设置（compiler, bibliography 等），
    调用系统命令完成编译。
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.paper_dir = self.root / "paper"
        self.config_dir = self.root / "config"

    # ----------------------------------------------------------
    # 主编译流程
    # ----------------------------------------------------------

    def compile(self, full: bool = True, clean: bool = False) -> CompileResult:
        """编译论文。

        Args:
            full: 是否执行完整流程（xelatex → bibtex → xelatex × 2）
            clean: 编译后是否清理辅助文件
        """
        config = self._load_compile_config()
        compiler = config.get("compiler", "xelatex")
        bib_tool = config.get("bibliography", "bibtex")
        main_tex = self.paper_dir / "main.tex"

        if not main_tex.exists():
            result = CompileResult()
            result.errors.append(CompileError(
                level="error", file="paper/main.tex", line=None,
                message="主文件 main.tex 不存在",
            ))
            return result

        result = CompileResult()

        # 第一次编译
        r1 = self._run_latex(compiler, main_tex)
        result.return_code = r1.returncode
        result.log_output = r1.stdout + r1.stderr

        if full:
            # 运行 bibtex
            self._run_bibtex(bib_tool, main_tex)
            # 第二次编译
            self._run_latex(compiler, main_tex)
            # 第三次编译（解决交叉引用）
            r3 = self._run_latex(compiler, main_tex)
            result.return_code = r3.returncode
            result.log_output = r3.stdout + r3.stderr

        # 解析日志
        log_file = main_tex.with_suffix(".log")
        if log_file.exists():
            log_content = log_file.read_text(encoding="utf-8", errors="ignore")
            errors, warnings = self._parse_log(log_content)
            result.errors = errors
            result.warnings = warnings

        # 检查 PDF 是否生成
        pdf_file = main_tex.with_suffix(".pdf")
        if pdf_file.exists():
            result.success = len(result.errors) == 0
            result.pdf_path = str(pdf_file.relative_to(self.root)).replace("\\", "/")
        else:
            result.success = False

        if clean:
            self.clean()

        return result

    def compile_quick(self) -> CompileResult:
        """快速编译（仅 xelatex 一次，不处理引用）。"""
        return self.compile(full=False)

    # ----------------------------------------------------------
    # 辅助文件清理
    # ----------------------------------------------------------

    def clean(self) -> list[str]:
        """清理编译辅助文件。"""
        aux_extensions = [
            ".aux", ".log", ".bbl", ".blg", ".out", ".toc",
            ".lof", ".lot", ".fls", ".fdb_latexmk", ".synctex.gz",
            ".nav", ".snm", ".vrb",
        ]
        removed: list[str] = []

        for ext in aux_extensions:
            for f in self.paper_dir.glob(f"*{ext}"):
                f.unlink()
                removed.append(f.name)

        return removed

    # ----------------------------------------------------------
    # 日志解析
    # ----------------------------------------------------------

    def _parse_log(self, log_content: str) -> tuple[list[CompileError], list[CompileError]]:
        """解析 LaTeX 日志，提取错误和警告。"""
        errors: list[CompileError] = []
        warnings: list[CompileError] = []

        # 错误模式: ! LaTeX Error: ... 或 ! ...
        error_pattern = re.compile(
            r"^!\s+(.+?)$\n(?:l\.(\d+)\s+(.*))?",
            re.MULTILINE,
        )
        for m in error_pattern.finditer(log_content):
            msg = m.group(1).strip()
            line = int(m.group(2)) if m.group(2) else None
            errors.append(CompileError(
                level="error", file="paper/main.tex", line=line,
                message=msg,
            ))

        # 文件级错误
        file_error = re.compile(r"\(([^)]+\.tex).*?^!\s+(.+?)$", re.MULTILINE | re.DOTALL)
        for m in file_error.finditer(log_content):
            fname = m.group(1)
            msg = m.group(2).strip()
            # 避免重复
            if not any(e.message == msg for e in errors):
                errors.append(CompileError(
                    level="error", file=fname, line=None, message=msg,
                ))

        # 警告模式
        warn_patterns = [
            re.compile(r"LaTeX Warning:\s*(.+?)(?:\n|$)", re.IGNORECASE),
            re.compile(r"Package (\w+) Warning:\s*(.+?)(?:\n|$)", re.IGNORECASE),
            re.compile(r"Overfull \\hbox .+? in paragraph at lines (\d+)--(\d+)"),
            re.compile(r"Underfull \\hbox .+? in paragraph at lines (\d+)--(\d+)"),
        ]

        for pat in warn_patterns:
            for m in pat.finditer(log_content):
                msg = m.group(0).strip()
                # 提取行号
                line_match = re.search(r"line[s]?\s+(\d+)", msg)
                line = int(line_match.group(1)) if line_match else None
                warnings.append(CompileError(
                    level="warning", file="paper/main.tex", line=line,
                    message=msg[:200],
                ))

        return errors, warnings

    # ----------------------------------------------------------
    # 底层执行
    # ----------------------------------------------------------

    def _run_latex(self, compiler: str, main_tex: Path) -> subprocess.CompletedProcess:
        """运行一次 LaTeX 编译。"""
        cmd = [
            compiler,
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            main_tex.name,
        ]
        return subprocess.run(
            cmd,
            cwd=str(self.paper_dir),
            capture_output=True,
            text=True,
            timeout=120,
            env=self._get_env(),
        )

    def _run_bibtex(self, bib_tool: str, main_tex: Path) -> subprocess.CompletedProcess:
        """运行 BibTeX/Biber。"""
        stem = main_tex.stem
        cmd = [bib_tool, stem]
        return subprocess.run(
            cmd,
            cwd=str(self.paper_dir),
            capture_output=True,
            text=True,
            timeout=60,
            env=self._get_env(),
        )

    def _load_compile_config(self) -> dict[str, Any]:
        """从 config/paper.yaml 读取编译相关配置。"""
        paper_yaml = self.config_dir / "paper.yaml"
        if not paper_yaml.exists():
            return {"compiler": "xelatex", "bibliography": "bibtex"}
        try:
            with open(paper_yaml, encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
            latex_config = data.get("latex", {})
            return {
                "compiler": latex_config.get("compiler", "xelatex"),
                "bibliography": latex_config.get("bibliography", "bibtex"),
            }
        except yaml.YAMLError:
            return {"compiler": "xelatex", "bibliography": "bibtex"}

    @staticmethod
    def _get_env() -> dict[str, str]:
        """返回子进程环境变量（继承当前环境）。"""
        env = os.environ.copy()
        return env


# ============================================================
# CLI 入口
# ============================================================

def main():
    import sys

    compiler = LaTeXCompiler()

    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        removed = compiler.clean()
        print(f"已清理: {', '.join(removed) if removed else '无'}")
    elif len(sys.argv) > 1 and sys.argv[1] == "quick":
        result = compiler.compile_quick()
        print(result.summary())
    else:
        result = compiler.compile()
        print(result.summary())


if __name__ == "__main__":
    main()
