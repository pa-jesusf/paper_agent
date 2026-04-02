"""
tests/test_glossary_checker.py — GlossaryChecker 单元测试
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from tools.glossary_checker import GlossaryChecker


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> GlossaryChecker:
    (tmp_path / "config").mkdir()
    (tmp_path / "paper" / "sections").mkdir(parents=True)
    return GlossaryChecker(project_root=tmp_path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def _write_glossary(config_dir: Path, terms: list | None = None, symbols: list | None = None):
    data: dict = {}
    if terms is not None:
        data["terms"] = terms
    if symbols is not None:
        data["symbols"] = symbols
    _write(config_dir / "glossary.yaml", yaml.dump(data, allow_unicode=True))


# ============================================================
# 1. 禁止变体
# ============================================================

class TestForbiddenVariants:

    def test_detects_forbidden_variant(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, terms=[{
            "canonical": "fine-tuning",
            "forbidden_variants": ["finetuning", "fine tuning"],
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "We apply finetuning to the model.")

        report = project.check_all()
        warns = [i for i in report.issues if i.rule == "forbidden-variant"]
        assert len(warns) == 1
        assert "fine-tuning" in warns[0].message

    def test_no_false_positive(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, terms=[{
            "canonical": "fine-tuning",
            "forbidden_variants": ["finetuning"],
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "We use fine-tuning for the model.")

        report = project.check_all()
        warns = [i for i in report.issues if i.rule == "forbidden-variant"]
        assert len(warns) == 0

    def test_skips_comments(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, terms=[{
            "canonical": "fine-tuning",
            "forbidden_variants": ["finetuning"],
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "% finetuning is mentioned in comments only")

        report = project.check_all()
        warns = [i for i in report.issues if i.rule == "forbidden-variant"]
        assert len(warns) == 0


# ============================================================
# 2. 缩写展开
# ============================================================

class TestAbbreviationExpansion:

    def test_detects_unexpanded_abbreviation(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, terms=[{
            "canonical": "large language model",
            "abbreviation": "LLM",
            "first_use": "large language model (LLM)",
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "LLM is a powerful tool for NLP tasks.")

        report = project.check_all()
        warns = [i for i in report.issues if i.rule == "abbreviation-expand"]
        assert len(warns) == 1
        assert "LLM" in warns[0].message

    def test_no_warning_when_expanded(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, terms=[{
            "canonical": "large language model",
            "abbreviation": "LLM",
            "first_use": "large language model (LLM)",
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "A large language model (LLM) is powerful. LLM can be fine-tuned.")

        report = project.check_all()
        warns = [i for i in report.issues if i.rule == "abbreviation-expand"]
        assert len(warns) == 0


# ============================================================
# 3. 符号宏检查
# ============================================================

class TestSymbolMacros:

    def test_detects_raw_definition(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, symbols=[{
            "name": "loss function",
            "latex_macro": "\\loss",
            "definition": "\\mathcal{L}",
        }])
        _write(project.paper_dir / "sections" / "02-method.tex",
               "The loss is $\\mathcal{L}(\\theta)$.")

        report = project.check_all()
        warns = [i for i in report.issues if i.rule == "symbol-macro"]
        assert len(warns) == 1
        assert "\\loss" in warns[0].message

    def test_no_warning_when_using_macro(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, symbols=[{
            "name": "loss function",
            "latex_macro": "\\loss",
            "definition": "\\mathcal{L}",
        }])
        _write(project.paper_dir / "sections" / "02-method.tex",
               "The loss is $\\loss(\\theta)$.")

        report = project.check_all()
        warns = [i for i in report.issues if i.rule == "symbol-macro"]
        assert len(warns) == 0


# ============================================================
# 4. 中文术语英文标注
# ============================================================

class TestChineseAnnotation:

    def test_detects_missing_english(self, project: GlossaryChecker):
        _write(project.config_dir / "paper.yaml", """\
            language: "chinese"
            i18n:
              primary: "chinese"
              term_original_annotation: true
        """)
        _write_glossary(project.config_dir, terms=[{
            "canonical": "Transformer",
            "chinese": "变压器模型",
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "本文使用变压器模型进行序列建模。")

        report = project.check_all()
        infos = [i for i in report.issues if i.rule == "chinese-annotation"]
        assert len(infos) == 1
        assert "Transformer" in infos[0].message

    def test_no_warning_when_annotated(self, project: GlossaryChecker):
        _write(project.config_dir / "paper.yaml", """\
            language: "chinese"
            i18n:
              primary: "chinese"
              term_original_annotation: true
        """)
        _write_glossary(project.config_dir, terms=[{
            "canonical": "Transformer",
            "chinese": "变压器模型",
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "本文使用变压器模型 (Transformer) 进行序列建模。")

        report = project.check_all()
        infos = [i for i in report.issues if i.rule == "chinese-annotation"]
        assert len(infos) == 0

    def test_disabled_when_english(self, project: GlossaryChecker):
        _write(project.config_dir / "paper.yaml", """\
            language: "english"
        """)
        _write_glossary(project.config_dir, terms=[{
            "canonical": "Transformer",
            "chinese": "变压器模型",
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "本文使用变压器模型进行序列建模。")

        report = project.check_all()
        infos = [i for i in report.issues if i.rule == "chinese-annotation"]
        assert len(infos) == 0


# ============================================================
# 5. 边界场景
# ============================================================

class TestGlossaryEdgeCases:

    def test_no_glossary(self, project: GlossaryChecker):
        report = project.check_all()
        assert any(i.rule == "glossary-exists" for i in report.issues)

    def test_no_tex_files(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, terms=[], symbols=[])
        # Remove sections dir
        import shutil
        sections = project.paper_dir / "sections"
        if sections.exists():
            shutil.rmtree(sections)
        report = project.check_all()
        assert any(i.rule == "tex-exists" for i in report.issues)

    def test_empty_glossary(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, terms=[], symbols=[])
        _write(project.paper_dir / "sections" / "01-intro.tex", "Some text.")
        report = project.check_all()
        # No crashes, no issues from empty glossary
        assert report.error_count == 0

    def test_report_summary(self, project: GlossaryChecker):
        _write_glossary(project.config_dir, terms=[{
            "canonical": "fine-tuning",
            "forbidden_variants": ["finetuning"],
        }])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "We apply finetuning.")

        report = project.check_all()
        summary = report.summary()
        assert "warnings" in summary
