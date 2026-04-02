"""tests/test_commands.py — 快捷命令调度器测试"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tools.commands import CommandDispatcher, CommandResult, StepResult


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """创建最小项目结构以支持命令执行。"""
    for d in ("config", "data", "paper/sections", "pipeline/notes",
              "pipeline/scripts", "pipeline/figures", "pipeline/tables",
              "refs/notes", "refs/pdfs"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # paper.yaml
    (tmp_path / "config" / "paper.yaml").write_text(
        yaml.dump({
            "title": "Test Paper", "venue": "TEST", "language": "chinese",
            "latex": {"compiler": "xelatex", "bibliography": "bibtex"},
        }, allow_unicode=True), encoding="utf-8")

    # glossary.yaml
    (tmp_path / "config" / "glossary.yaml").write_text(
        yaml.dump({
            "terms": [{"canonical": "LLM", "forbidden_variants": ["big LM"]}],
            "symbols": [],
        }, allow_unicode=True), encoding="utf-8")

    # outline.md
    (tmp_path / "pipeline" / "notes" / "outline.md").write_text(
        "# Outline\n## 1. Introduction\n## 2. Method\n", encoding="utf-8")

    # arguments.md
    (tmp_path / "pipeline" / "notes" / "arguments.md").write_text(
        "# Arguments\n- 论点 A\n", encoding="utf-8")

    # findings.md
    (tmp_path / "pipeline" / "notes" / "findings.md").write_text(
        "# Findings\n", encoding="utf-8")

    # style-guide.md
    (tmp_path / "config" / "style-guide.md").write_text(
        "# Writing Style Guide\n" + "内容。\n" * 20, encoding="utf-8")

    # figure-style.yaml
    (tmp_path / "config" / "figure-style.yaml").write_text(
        yaml.dump({
            "colors": {"palette": ["#1f77b4", "#ff7f0e", "#2ca02c"]},
            "layout": {"dpi": 300, "default_format": "pdf"},
        }, allow_unicode=True), encoding="utf-8")

    # experiment-env.yaml
    (tmp_path / "config" / "experiment-env.yaml").write_text(
        yaml.dump({
            "hardware": {"gpu": "RTX 4090"},
            "software": {"python": "3.12"},
        }, allow_unicode=True), encoding="utf-8")

    # refs/library.yaml
    (tmp_path / "refs" / "library.yaml").write_text(
        yaml.dump({"references": []}, allow_unicode=True), encoding="utf-8")

    # paper/references.bib
    (tmp_path / "paper" / "references.bib").write_text("", encoding="utf-8")

    # paper/main.tex
    (tmp_path / "paper" / "main.tex").write_text(
        r"\input{sections/01-intro}", encoding="utf-8")

    # paper/preamble.tex
    (tmp_path / "paper" / "preamble.tex").write_text("", encoding="utf-8")

    return tmp_path


# ============================================================
# 命令解析测试
# ============================================================

class TestParsing:
    def test_parse_exact_match(self) -> None:
        d = CommandDispatcher()
        cmd, params = d.parse("初始化")
        assert cmd is not None
        assert cmd.name == "初始化"

    def test_parse_with_target(self) -> None:
        d = CommandDispatcher()
        cmd, params = d.parse("写 introduction")
        assert cmd is not None
        assert cmd.name == "写章节"
        assert params["target"] == "introduction"

    def test_parse_add_reference(self) -> None:
        d = CommandDispatcher()
        cmd, params = d.parse('添加文献 "attention is all you need"')
        assert cmd is not None
        assert cmd.name == "添加文献"
        assert "attention" in params["target"]

    def test_parse_analyze(self) -> None:
        d = CommandDispatcher()
        cmd, params = d.parse("分析 raw/results.csv")
        assert cmd is not None
        assert cmd.name == "分析数据"
        assert params["target"] == "raw/results.csv"

    def test_parse_unknown(self) -> None:
        d = CommandDispatcher()
        cmd, params = d.parse("不存在的命令")
        assert cmd is None

    def test_parse_compile(self) -> None:
        d = CommandDispatcher()
        cmd, _ = d.parse("编译论文")
        assert cmd is not None
        assert cmd.name == "编译论文"

    def test_parse_quick_compile(self) -> None:
        d = CommandDispatcher()
        cmd, _ = d.parse("快速编译")
        assert cmd is not None
        assert cmd.name == "快速编译"

    def test_parse_sync_refs(self) -> None:
        d = CommandDispatcher()
        cmd, _ = d.parse("同步文献")
        assert cmd is not None
        assert cmd.name == "同步文献"


# ============================================================
# 命令列表测试
# ============================================================

class TestListCommands:
    def test_list_not_empty(self) -> None:
        d = CommandDispatcher()
        cmds = d.list_commands()
        assert len(cmds) >= 8

    def test_list_has_name_and_desc(self) -> None:
        d = CommandDispatcher()
        for cmd in d.list_commands():
            assert "name" in cmd
            assert "description" in cmd
            assert len(cmd["name"]) > 0


# ============================================================
# 命令执行测试
# ============================================================

class TestExecution:
    def test_unknown_command(self, project: Path) -> None:
        d = CommandDispatcher(project)
        result = d.execute("不存在的命令")
        assert not result.success or "未识别" in result.summary

    def test_check_config(self, project: Path) -> None:
        d = CommandDispatcher(project)
        result = d.execute("检查配置")
        assert isinstance(result, CommandResult)
        assert len(result.steps) == 2
        assert result.steps[0].name == "完备性检查"
        assert result.steps[1].name == "配置校验"

    def test_check_full(self, project: Path) -> None:
        d = CommandDispatcher(project)
        result = d.execute("检查全文")
        assert len(result.steps) == 3
        # 所有步骤应该成功（项目结构完整）
        for step in result.steps:
            assert step.success, f"{step.name} failed: {step.error}"

    def test_sync_refs(self, project: Path) -> None:
        d = CommandDispatcher(project)
        result = d.execute("同步文献")
        assert len(result.steps) == 1
        assert result.steps[0].success

    def test_write_section_context(self, project: Path) -> None:
        d = CommandDispatcher(project)
        result = d.execute("写 introduction")
        assert result.success
        # 应加载大纲、论点、配置
        assert len(result.steps) == 3
        outline_step = result.steps[0]
        assert outline_step.success
        assert "Outline" in str(outline_step.output)

    def test_analyze_context(self, project: Path) -> None:
        # 创建 manifest
        (project / "data" / "_manifest.yaml").write_text(
            yaml.dump({"files": []}, allow_unicode=True), encoding="utf-8")
        d = CommandDispatcher(project)
        result = d.execute("分析 raw/results.csv")
        assert result.success

    def test_init_command(self, project: Path) -> None:
        d = CommandDispatcher(project)
        result = d.execute("初始化")
        assert isinstance(result, CommandResult)
        # 应有 4 个步骤
        assert len(result.steps) == 4


# ============================================================
# StepResult / CommandResult 数据类
# ============================================================

class TestDataModels:
    def test_step_result_str(self) -> None:
        s = StepResult(name="Test", tool="t", method="m", success=True)
        assert "✓" in str(s)

    def test_step_result_failure(self) -> None:
        s = StepResult(name="Test", tool="t", method="m",
                       success=False, error="boom")
        assert "✗" in str(s)
        assert "boom" in str(s)

    def test_command_result_success(self) -> None:
        r = CommandResult(command="test", steps=[
            StepResult(name="a", tool="t", method="m", success=True),
            StepResult(name="b", tool="t", method="m", success=True),
        ])
        assert r.success
        assert len(r.failed_steps) == 0

    def test_command_result_failure(self) -> None:
        r = CommandResult(command="test", steps=[
            StepResult(name="a", tool="t", method="m", success=True),
            StepResult(name="b", tool="t", method="m", success=False, error="err"),
        ])
        assert not r.success
        assert len(r.failed_steps) == 1

    def test_report_format(self) -> None:
        r = CommandResult(
            command="检查配置",
            steps=[StepResult(name="a", tool="t", method="m", success=True)],
            summary="完成 1/1 步骤",
        )
        text = r.report()
        assert "检查配置" in text
        assert "成功" in text
