"""
tests/test_paper_lint.py — PaperLint 单元测试
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from tools.paper_lint import LintItem, LintReport, PaperLint


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> PaperLint:
    (tmp_path / "config").mkdir()
    (tmp_path / "paper" / "sections").mkdir(parents=True)
    (tmp_path / "refs").mkdir()
    return PaperLint(project_root=tmp_path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def _write_library(refs_dir: Path, refs: list):
    _write(refs_dir / "library.yaml", yaml.dump({"references": refs}, allow_unicode=True))


def _write_bib(paper_dir: Path, entries: list[str]):
    content = "\n\n".join(entries)
    _write(paper_dir / "references.bib", content)


# ============================================================
# 1. 引用完整性
# ============================================================

class TestCitations:

    def test_valid_citation(self, project: PaperLint):
        _write_bib(project.paper_dir, ["@article{doe2024, title={Test}, year={2024}}"])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"See \cite{doe2024}.")

        report = project.check_all()
        citation_errors = [i for i in report.items if i.category == "citation"]
        assert len(citation_errors) == 0

    def test_missing_citation(self, project: PaperLint):
        _write_bib(project.paper_dir, ["@article{doe2024, title={Test}, year={2024}}"])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"See \cite{nonexistent2024}.")

        report = project.check_all()
        citation_errors = [i for i in report.items if i.category == "citation"]
        assert len(citation_errors) == 1
        assert "nonexistent2024" in citation_errors[0].message

    def test_citation_from_library(self, project: PaperLint):
        _write_library(project.refs_dir, [{"citekey": "lib2024", "title": "From library"}])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"See \cite{lib2024}.")

        report = project.check_all()
        citation_errors = [i for i in report.items if i.category == "citation"]
        assert len(citation_errors) == 0

    def test_citation_in_comment_skipped(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"% \cite{nope}")

        report = project.check_all()
        citation_errors = [i for i in report.items if i.category == "citation"]
        assert len(citation_errors) == 0

    def test_multiple_keys_in_cite(self, project: PaperLint):
        _write_bib(project.paper_dir, ["@article{a2024, title={A}}", "@article{b2024, title={B}}"])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"See \cite{a2024, b2024, missing2024}.")

        report = project.check_all()
        citation_errors = [i for i in report.items if i.category == "citation"]
        assert len(citation_errors) == 1
        assert "missing2024" in citation_errors[0].message


# ============================================================
# 2. 图表引用
# ============================================================

class TestFigureRefs:

    def test_valid_ref(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex", r"""
            \begin{figure}
            \label{fig:arch}
            \end{figure}
            See Figure \ref{fig:arch}.
        """)

        report = project.check_all()
        ref_errors = [i for i in report.items if i.category == "ref" and i.level == "error"]
        assert len(ref_errors) == 0

    def test_missing_label(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"See Figure \ref{fig:missing}.")

        report = project.check_all()
        ref_errors = [i for i in report.items if i.category == "ref" and i.level == "error"]
        assert len(ref_errors) == 1

    def test_unreferenced_label(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex", r"""
            \begin{figure}
            \label{fig:unused}
            \end{figure}
        """)

        report = project.check_all()
        ref_warns = [i for i in report.items if i.category == "ref" and i.level == "warn"]
        assert len(ref_warns) == 1
        assert "fig:unused" in ref_warns[0].message


# ============================================================
# 3. 引用溯源
# ============================================================

class TestCitationSourcing:

    def test_warns_no_quotes(self, project: PaperLint):
        _write_library(project.refs_dir, [{"citekey": "doe2024", "title": "Test"}])
        _write_bib(project.paper_dir, ["@article{doe2024, title={Test}}"])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"\cite{doe2024}")

        report = project.check_all()
        sourcing = [i for i in report.items if i.category == "sourcing"]
        assert len(sourcing) == 1
        assert "key_quotes" in sourcing[0].message

    def test_no_warn_with_quotes(self, project: PaperLint):
        _write_library(project.refs_dir, [{
            "citekey": "doe2024",
            "title": "Test",
            "key_quotes": [{"id": "q1", "text": "Quote text", "page": 1}],
        }])
        _write_bib(project.paper_dir, ["@article{doe2024, title={Test}}"])
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"\cite{doe2024}")

        report = project.check_all()
        sourcing = [i for i in report.items if i.category == "sourcing"]
        assert len(sourcing) == 0


# ============================================================
# 4. TODO / CONFIRM 标记
# ============================================================

class TestTodoMarks:

    def test_detects_todo(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"\todo{补充实验数据}")

        report = project.check_all()
        todos = [i for i in report.items if i.category == "todo"]
        assert len(todos) == 1

    def test_detects_confirm(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"\confirm{这个数字需要验证}")

        report = project.check_all()
        confirms = [i for i in report.items if i.category == "confirm"]
        assert len(confirms) == 1

    def test_detects_comment_todo(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "% TODO: fix this section")

        report = project.check_all()
        todos = [i for i in report.items if i.category == "todo"]
        assert len(todos) == 1


# ============================================================
# 5. 结构与内容
# ============================================================

class TestStructure:

    def test_section_not_in_main(self, project: PaperLint):
        _write(project.paper_dir / "main.tex", r"\input{sections/01-intro}")
        _write(project.paper_dir / "sections" / "01-intro.tex", "Intro content here.")
        _write(project.paper_dir / "sections" / "02-method.tex", "Method content here.")

        report = project.check_all()
        struct_warns = [i for i in report.items if i.category == "structure"]
        assert len(struct_warns) == 1
        assert "02-method" in struct_warns[0].message

    def test_empty_section(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex", "% empty")

        report = project.check_all()
        content_warns = [i for i in report.items if i.category == "content"]
        assert len(content_warns) == 1


# ============================================================
# 6. 报告
# ============================================================

class TestLintReport:

    def test_empty_report(self):
        report = LintReport()
        assert report.error_count == 0
        assert report.warn_count == 0
        assert "全部通过" in report.summary()

    def test_report_counts(self):
        report = LintReport(items=[
            LintItem(level="error", category="citation", file="a.tex", line=1, message="err"),
            LintItem(level="warn", category="ref", file="b.tex", line=2, message="warn"),
            LintItem(level="info", category="todo", file="c.tex", line=3, message="info"),
        ])
        assert report.error_count == 1
        assert report.warn_count == 1
        assert report.info_count == 1

    def test_lint_item_str(self):
        item = LintItem(level="error", category="citation", file="a.tex", line=10, message="Missing")
        s = str(item)
        assert "[ERROR]" in s
        assert "[citation]" in s
        assert "a.tex:10" in s


# ============================================================
# 7. 写作风格检查
# ============================================================

class TestStyleRules:

    def test_first_person_detected(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "我们提出了一种新方法。")

        report = project.check_all()
        style_warns = [i for i in report.items if i.category == "style"]
        assert any("第一人称" in w.message for w in style_warns)

    def test_first_person_variants(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "我们设计了框架。我认为这个方法很好。我们发现了规律。")

        report = project.check_all()
        fp = [i for i in report.items if i.category == "style" and "第一人称" in i.message]
        assert len(fp) == 3

    def test_first_person_in_comment_ignored(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "% 我们提出了一种新方法")

        report = project.check_all()
        style_warns = [i for i in report.items if i.category == "style" and "第一人称" in i.message]
        assert len(style_warns) == 0

    def test_third_person_ok(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "本文提出了一种新方法。实验结果表明该方法有效。")

        report = project.check_all()
        fp = [i for i in report.items if i.category == "style" and "第一人称" in i.message]
        assert len(fp) == 0

    def test_vague_language_detected(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "本方法大幅提升了性能。")

        report = project.check_all()
        vague = [i for i in report.items if i.category == "style" and "模糊" in i.message]
        assert len(vague) == 1
        assert "大幅提升" in vague[0].message

    def test_vague_variants(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "显著优于基线。效果非常好。实验结果令人满意。")

        report = project.check_all()
        vague = [i for i in report.items if i.category == "style" and "模糊" in i.message]
        assert len(vague) == 3

    def test_quantified_ok(self, project: PaperLint):
        _write(project.paper_dir / "sections" / "01-intro.tex",
               r"F1-score 提升了 20.9 个百分点（0.77$\to$0.93）。")

        report = project.check_all()
        vague = [i for i in report.items if i.category == "style" and "模糊" in i.message]
        assert len(vague) == 0

    def test_banned_phrases_from_style_guide(self, project: PaperLint):
        _write(project.root / "config" / "style-guide.md", """
            # 写作风格
            ## 禁止使用的套话
            以下短语禁止使用：
            - "近年来，……引起了广泛关注"
            - "众所周知"
            - "不言而喻"
        """)
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "众所周知，深度学习很重要。")

        report = project.check_all()
        banned = [i for i in report.items if i.category == "style" and "禁止套话" in i.message]
        assert len(banned) == 1
        assert "众所周知" in banned[0].message

    def test_no_style_guide_no_banned(self, project: PaperLint):
        """style-guide.md 不存在时不报错，只检查内置规则。"""
        _write(project.paper_dir / "sections" / "01-intro.tex",
               "本文提出了一种新方法。")

        report = project.check_all()
        banned = [i for i in report.items if i.category == "style" and "禁止套话" in i.message]
        assert len(banned) == 0

    def test_clean_academic_text(self, project: PaperLint):
        """规范的学术文本不触发任何风格警告。"""
        _write(project.paper_dir / "sections" / "01-intro.tex", r"""
            本文针对软件缺陷预测场景，提出了一种基于图神经网络的方法。
            实验结果表明，该方法在 F1-score 上提升了 12.3\%（0.78$\to$0.88）。
            如图~\ref{fig:arch}~所示，系统由三个模块组成。
        """)

        report = project.check_all()
        style_warns = [i for i in report.items if i.category == "style"]
        assert len(style_warns) == 0

    def test_long_style_guide_loads(self, project: PaperLint):
        """验证大型 style-guide.md（如同济风格指南）可正常加载和使用。"""
        long_guide = "# 风格指南\n\n" + "这是一段很长的写作规范。\n" * 200
        long_guide += "\n## 禁止使用的套话\n以下禁止使用：\n"
        long_guide += '- "毫无疑问"\n- "不言而喻"\n'
        _write(project.root / "config" / "style-guide.md", long_guide)

        phrases = project._load_banned_phrases()
        assert "毫无疑问" in phrases
        assert "不言而喻" in phrases

        _write(project.paper_dir / "sections" / "01-intro.tex",
               "毫无疑问，这是一个重要的研究方向。")

        report = project.check_all()
        banned = [i for i in report.items if i.category == "style" and "禁止套话" in i.message]
        assert len(banned) == 1
