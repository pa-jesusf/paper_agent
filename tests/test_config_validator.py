"""tests/test_config_validator.py — 配置校验工具测试"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from tools.config_validator import ConfigValidator, ValidationIssue, ValidationReport


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """创建最小项目结构。"""
    for d in ("config", "paper", "refs"):
        (tmp_path / d).mkdir()
    return tmp_path


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


# ============================================================
# paper.yaml 校验
# ============================================================

class TestPaperYaml:
    def test_valid(self, project: Path) -> None:
        _write_yaml(project / "config" / "paper.yaml", {
            "title": "My Paper",
            "venue": "NeurIPS 2026",
            "language": "chinese",
            "authors": [{"name": "Alice", "affiliation": "MIT"}],
        })
        v = ConfigValidator(project)
        r = v.validate_paper_yaml()
        assert r.is_valid

    def test_missing_title(self, project: Path) -> None:
        _write_yaml(project / "config" / "paper.yaml", {
            "venue": "ICML", "language": "english",
        })
        v = ConfigValidator(project)
        r = v.validate_paper_yaml()
        errors = [i for i in r.issues if i.level == "error"]
        fields = [i.field for i in errors]
        assert "title" in fields

    def test_invalid_language(self, project: Path) -> None:
        _write_yaml(project / "config" / "paper.yaml", {
            "title": "T", "venue": "V", "language": "french",
        })
        v = ConfigValidator(project)
        r = v.validate_paper_yaml()
        assert not r.is_valid
        assert any("language" in i.field for i in r.issues)

    def test_invalid_compiler(self, project: Path) -> None:
        _write_yaml(project / "config" / "paper.yaml", {
            "title": "T", "venue": "V", "language": "english",
            "latex": {"compiler": "latex2e"},
        })
        v = ConfigValidator(project)
        r = v.validate_paper_yaml()
        assert any("compiler" in i.field for i in r.issues)

    def test_no_authors_warns(self, project: Path) -> None:
        _write_yaml(project / "config" / "paper.yaml", {
            "title": "T", "venue": "V", "language": "english",
        })
        v = ConfigValidator(project)
        r = v.validate_paper_yaml()
        warns = [i for i in r.issues if i.level == "warn"]
        assert any("authors" in i.field for i in warns)

    def test_negative_page_limit(self, project: Path) -> None:
        _write_yaml(project / "config" / "paper.yaml", {
            "title": "T", "venue": "V", "language": "english",
            "page_limit": -1,
        })
        v = ConfigValidator(project)
        r = v.validate_paper_yaml()
        assert any("page_limit" in i.field for i in r.issues)

    def test_auto_fix_i18n(self, project: Path) -> None:
        _write_yaml(project / "config" / "paper.yaml", {
            "title": "T", "venue": "V", "language": "chinese",
        })
        v = ConfigValidator(project)
        r = v.validate_paper_yaml(auto_fix=True)
        assert any("i18n" in fix for fix in r.auto_fixed)
        # 验证文件已被修改
        data = yaml.safe_load(
            (project / "config" / "paper.yaml").read_text(encoding="utf-8"))
        assert data["i18n"]["primary"] == "chinese"

    def test_missing_file(self, project: Path) -> None:
        v = ConfigValidator(project)
        r = v.validate_paper_yaml()
        assert not r.is_valid

    def test_invalid_style_tone(self, project: Path) -> None:
        _write_yaml(project / "config" / "paper.yaml", {
            "title": "T", "venue": "V", "language": "english",
            "style": {"tone": "casual"},
        })
        v = ConfigValidator(project)
        r = v.validate_paper_yaml()
        assert any("tone" in i.field for i in r.issues)


# ============================================================
# glossary.yaml 校验
# ============================================================

class TestGlossaryYaml:
    def test_valid_glossary(self, project: Path) -> None:
        _write_yaml(project / "config" / "glossary.yaml", {
            "terms": [
                {"canonical": "LLM", "forbidden_variants": ["big LM"]},
            ],
            "symbols": [
                {"name": "loss", "latex_macro": "\\loss", "definition": "\\mathcal{L}"},
            ],
        })
        v = ConfigValidator(project)
        r = v.validate_glossary()
        assert r.error_count == 0

    def test_duplicate_term(self, project: Path) -> None:
        _write_yaml(project / "config" / "glossary.yaml", {
            "terms": [
                {"canonical": "LLM"},
                {"canonical": "llm"},
            ],
        })
        v = ConfigValidator(project)
        r = v.validate_glossary()
        assert any("重复" in i.message for i in r.issues)

    def test_canonical_in_forbidden(self, project: Path) -> None:
        _write_yaml(project / "config" / "glossary.yaml", {
            "terms": [
                {"canonical": "LLM", "forbidden_variants": ["LLM", "big LM"]},
            ],
        })
        v = ConfigValidator(project)
        r = v.validate_glossary()
        assert any("canonical 自身" in i.message for i in r.issues)

    def test_missing_canonical(self, project: Path) -> None:
        _write_yaml(project / "config" / "glossary.yaml", {
            "terms": [{"forbidden_variants": ["a"]}],
        })
        v = ConfigValidator(project)
        r = v.validate_glossary()
        assert any("canonical" in i.field for i in r.issues)

    def test_duplicate_macro(self, project: Path) -> None:
        _write_yaml(project / "config" / "glossary.yaml", {
            "symbols": [
                {"latex_macro": "\\loss", "definition": "A"},
                {"latex_macro": "\\loss", "definition": "B"},
            ],
        })
        v = ConfigValidator(project)
        r = v.validate_glossary()
        assert any("重复" in i.message for i in r.issues)

    def test_missing_macro(self, project: Path) -> None:
        _write_yaml(project / "config" / "glossary.yaml", {
            "symbols": [{"name": "x", "definition": "x"}],
        })
        v = ConfigValidator(project)
        r = v.validate_glossary()
        assert any("latex_macro" in i.field for i in r.issues)

    def test_no_glossary_file(self, project: Path) -> None:
        v = ConfigValidator(project)
        r = v.validate_glossary()
        assert any("不存在" in i.message for i in r.issues)


# ============================================================
# experiment-env.yaml 校验
# ============================================================

class TestExperimentEnv:
    def test_valid(self, project: Path) -> None:
        _write_yaml(project / "config" / "experiment-env.yaml", {
            "hardware": {"gpu": "A100", "cpu": "EPYC"},
            "software": {"python": "3.10"},
        })
        v = ConfigValidator(project)
        r = v.validate_all()
        env_issues = [i for i in r.issues if "experiment-env" in i.file]
        assert all(i.level != "error" for i in env_issues)

    def test_missing_gpu(self, project: Path) -> None:
        _write_yaml(project / "config" / "experiment-env.yaml", {
            "hardware": {"cpu": "EPYC"},
            "software": {"python": "3.10"},
        })
        v = ConfigValidator(project)
        r = v.validate_all()
        assert any("gpu" in i.field for i in r.issues if "experiment-env" in i.file)


# ============================================================
# figure-style.yaml 校验
# ============================================================

class TestFigureStyle:
    def test_valid(self, project: Path) -> None:
        _write_yaml(project / "config" / "figure-style.yaml", {
            "colors": {"palette": ["#1f77b4", "#ff7f0e", "#2ca02c"]},
            "layout": {"dpi": 300, "default_format": "pdf"},
        })
        v = ConfigValidator(project)
        r = v.validate_all()
        fig_issues = [i for i in r.issues if "figure-style" in i.file]
        assert all(i.level != "error" for i in fig_issues)

    def test_bad_color_format(self, project: Path) -> None:
        _write_yaml(project / "config" / "figure-style.yaml", {
            "colors": {"palette": ["red", "#abc"]},
        })
        v = ConfigValidator(project)
        r = v.validate_all()
        assert any("格式不标准" in i.message for i in r.issues)

    def test_low_dpi(self, project: Path) -> None:
        _write_yaml(project / "config" / "figure-style.yaml", {
            "layout": {"dpi": 50},
        })
        v = ConfigValidator(project)
        r = v.validate_all()
        assert any("DPI" in i.message for i in r.issues)

    def test_invalid_format(self, project: Path) -> None:
        _write_yaml(project / "config" / "figure-style.yaml", {
            "layout": {"default_format": "bmp"},
        })
        v = ConfigValidator(project)
        r = v.validate_all()
        assert any("格式" in i.message for i in r.issues if "figure-style" in i.file)

    def test_auto_fix_layout(self, project: Path) -> None:
        _write_yaml(project / "config" / "figure-style.yaml", {
            "colors": {"palette": ["#aabbcc", "#ddeeff", "#112233"]},
        })
        v = ConfigValidator(project)
        r = v.validate_all(auto_fix=True)
        assert any("layout" in fix for fix in r.auto_fixed)
        data = yaml.safe_load(
            (project / "config" / "figure-style.yaml").read_text(encoding="utf-8"))
        assert data["layout"]["dpi"] == 300


# ============================================================
# style-guide.md 校验
# ============================================================

class TestStyleGuide:
    def test_exists_with_content(self, project: Path) -> None:
        (project / "config" / "style-guide.md").write_text(
            "# Style Guide\n" + "规范内容。\n" * 20, encoding="utf-8")
        v = ConfigValidator(project)
        r = v.validate_all()
        sg_issues = [i for i in r.issues if "style-guide" in i.file]
        # 应该没有 warn / error
        assert all(i.level == "info" or i.level not in ("error", "warn")
                    for i in sg_issues)

    def test_missing_file(self, project: Path) -> None:
        v = ConfigValidator(project)
        r = v.validate_all()
        assert any("style-guide" in i.file and "不存在" in i.message for i in r.issues)

    def test_too_short(self, project: Path) -> None:
        (project / "config" / "style-guide.md").write_text("# Style", encoding="utf-8")
        v = ConfigValidator(project)
        r = v.validate_all()
        assert any("内容过少" in i.message for i in r.issues)


# ============================================================
# 交叉校验: glossary ↔ preamble
# ============================================================

class TestCrossGlossaryPreamble:
    def test_macro_in_preamble(self, project: Path) -> None:
        _write_yaml(project / "config" / "glossary.yaml", {
            "symbols": [
                {"latex_macro": "\\loss", "definition": "\\mathcal{L}"},
            ],
        })
        (project / "paper" / "preamble.tex").write_text(
            r"\newcommand{\loss}{\mathcal{L}}", encoding="utf-8")
        v = ConfigValidator(project)
        r = v.validate_all()
        cross = [i for i in r.issues if "preamble" in i.file]
        assert len(cross) == 0

    def test_macro_missing_from_preamble(self, project: Path) -> None:
        _write_yaml(project / "config" / "glossary.yaml", {
            "symbols": [
                {"latex_macro": "\\loss", "definition": "\\mathcal{L}"},
            ],
        })
        (project / "paper" / "preamble.tex").write_text(
            r"\newcommand{\params}{\theta}", encoding="utf-8")
        v = ConfigValidator(project)
        r = v.validate_all()
        cross = [i for i in r.issues if "preamble" in i.file]
        assert len(cross) == 1
        assert "loss" in cross[0].message


# ============================================================
# 交叉校验: bib ↔ library
# ============================================================

class TestCrossBibLibrary:
    def test_in_sync(self, project: Path) -> None:
        _write_yaml(project / "refs" / "library.yaml", {
            "references": [{"citekey": "vaswani2017", "title": "Attention"}],
        })
        (project / "paper" / "references.bib").write_text(
            "@article{vaswani2017, title={Attention}}\n", encoding="utf-8")
        v = ConfigValidator(project)
        r = v.validate_all()
        cross = [i for i in r.issues if "references.bib" in i.file]
        assert len(cross) == 0

    def test_missing_in_bib(self, project: Path) -> None:
        _write_yaml(project / "refs" / "library.yaml", {
            "references": [
                {"citekey": "vaswani2017", "title": "A"},
                {"citekey": "devlin2019", "title": "B"},
            ],
        })
        (project / "paper" / "references.bib").write_text(
            "@article{vaswani2017, title={A}}\n", encoding="utf-8")
        v = ConfigValidator(project)
        r = v.validate_all()
        cross = [i for i in r.issues if "devlin2019" in i.field]
        assert len(cross) == 1
        assert "sync" in cross[0].message

    def test_extra_in_bib(self, project: Path) -> None:
        _write_yaml(project / "refs" / "library.yaml", {
            "references": [],
        })
        (project / "paper" / "references.bib").write_text(
            "@article{unknown2025, title={X}}\n", encoding="utf-8")
        v = ConfigValidator(project)
        r = v.validate_all()
        assert any("unknown2025" in i.field for i in r.issues)

    def test_no_bib_file(self, project: Path) -> None:
        _write_yaml(project / "refs" / "library.yaml", {
            "references": [{"citekey": "a2024", "title": "A"}],
        })
        v = ConfigValidator(project)
        r = v.validate_all()
        assert any("不存在" in i.message for i in r.issues
                    if "references.bib" in i.file)


# ============================================================
# ValidationReport 数据类
# ============================================================

class TestReportModel:
    def test_empty_report(self) -> None:
        r = ValidationReport()
        assert r.is_valid
        assert r.error_count == 0
        assert r.warn_count == 0

    def test_counts(self) -> None:
        r = ValidationReport(issues=[
            ValidationIssue("error", "a", "b", "msg"),
            ValidationIssue("warn", "a", "c", "msg"),
            ValidationIssue("info", "a", "d", "msg"),
            ValidationIssue("error", "a", "e", "msg"),
        ])
        assert r.error_count == 2
        assert r.warn_count == 1
        assert r.info_count == 1
        assert not r.is_valid

    def test_issue_str(self) -> None:
        i = ValidationIssue("error", "f.yaml", "x.y", "问题", auto_fix="修复")
        s = str(i)
        assert "[ERROR]" in s
        assert "修复" in s

    def test_summary(self) -> None:
        r = ValidationReport(
            issues=[ValidationIssue("warn", "a", "b", "msg")],
            auto_fixed=["fixed something"],
        )
        s = r.summary()
        assert "0 errors" in s
        assert "1 warnings" in s
        assert "fixed something" in s
