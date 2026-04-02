"""
tests/test_latex_compiler.py — LaTeXCompiler 单元测试

注: 不依赖真实 xelatex 安装，仅测试日志解析和配置加载逻辑。
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from tools.latex_compiler import CompileError, CompileResult, LaTeXCompiler


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> LaTeXCompiler:
    (tmp_path / "config").mkdir()
    (tmp_path / "paper").mkdir()
    return LaTeXCompiler(project_root=tmp_path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


# ============================================================
# 1. 日志解析
# ============================================================

class TestLogParsing:

    def test_parse_latex_error(self, project: LaTeXCompiler):
        log = textwrap.dedent("""\
            This is XeTeX, Version 3.14159265
            (./main.tex
            ! Undefined control sequence.
            l.42 \\badcommand
            )
        """)
        errors, warnings = project._parse_log(log)
        assert len(errors) >= 1
        assert any("Undefined control sequence" in e.message for e in errors)

    def test_parse_latex_warning(self, project: LaTeXCompiler):
        log = textwrap.dedent("""\
            LaTeX Warning: Reference `fig:missing' on page 3 undefined on line 15.
        """)
        errors, warnings = project._parse_log(log)
        assert len(warnings) >= 1

    def test_parse_overfull_hbox(self, project: LaTeXCompiler):
        log = textwrap.dedent("""\
            Overfull \\hbox (15.0pt too wide) in paragraph at lines 20--25
        """)
        errors, warnings = project._parse_log(log)
        assert len(warnings) >= 1
        assert any("Overfull" in w.message for w in warnings)

    def test_parse_clean_log(self, project: LaTeXCompiler):
        log = "Output written on main.pdf (10 pages).\n"
        errors, warnings = project._parse_log(log)
        assert len(errors) == 0


# ============================================================
# 2. 配置加载
# ============================================================

class TestConfig:

    def test_default_config(self, project: LaTeXCompiler):
        config = project._load_compile_config()
        assert config["compiler"] == "xelatex"
        assert config["bibliography"] == "bibtex"

    def test_custom_config(self, project: LaTeXCompiler):
        _write(project.config_dir / "paper.yaml", """\
            title: "Test"
            latex:
              compiler: "lualatex"
              bibliography: "biber"
        """)
        config = project._load_compile_config()
        assert config["compiler"] == "lualatex"
        assert config["bibliography"] == "biber"

    def test_corrupt_config(self, project: LaTeXCompiler):
        (project.config_dir / "paper.yaml").write_text("{{bad", encoding="utf-8")
        config = project._load_compile_config()
        assert config["compiler"] == "xelatex"


# ============================================================
# 3. 编译结果
# ============================================================

class TestCompileResult:

    def test_missing_main_tex(self, project: LaTeXCompiler):
        result = project.compile()
        assert result.success is False
        assert any("main.tex" in e.message for e in result.errors)

    def test_compile_result_summary(self):
        result = CompileResult(success=True, pdf_path="paper/main.pdf")
        s = result.summary()
        assert "编译成功" in s
        assert "main.pdf" in s

    def test_compile_result_failure_summary(self):
        result = CompileResult(success=False)
        result.errors.append(CompileError(
            level="error", file="main.tex", line=10, message="Bad command"
        ))
        s = result.summary()
        assert "编译失败" in s
        assert "Bad command" in s

    def test_compile_error_str(self):
        err = CompileError(level="error", file="main.tex", line=42, message="Test")
        assert "[ERROR]" in str(err)
        assert "42" in str(err)

    def test_compile_error_no_line(self):
        err = CompileError(level="warning", file="main.tex", line=None, message="Test")
        assert "[WARN]" in str(err)


# ============================================================
# 4. 清理辅助文件
# ============================================================

class TestClean:

    def test_clean_removes_aux_files(self, project: LaTeXCompiler):
        paper_dir = project.paper_dir
        (paper_dir / "main.aux").write_text("aux", encoding="utf-8")
        (paper_dir / "main.log").write_text("log", encoding="utf-8")
        (paper_dir / "main.bbl").write_text("bbl", encoding="utf-8")
        (paper_dir / "main.tex").write_text("tex", encoding="utf-8")

        removed = project.clean()
        assert "main.aux" in removed
        assert "main.log" in removed
        assert "main.bbl" in removed
        # main.tex should NOT be removed
        assert (paper_dir / "main.tex").exists()

    def test_clean_empty(self, project: LaTeXCompiler):
        removed = project.clean()
        assert removed == []
