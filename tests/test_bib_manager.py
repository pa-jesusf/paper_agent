"""
tests/test_bib_manager.py — BibManager 单元测试
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from tools.bib_manager import BibManager


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> BibManager:
    (tmp_path / "refs").mkdir()
    (tmp_path / "paper" / "sections").mkdir(parents=True)
    return BibManager(project_root=tmp_path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def _sample_entry(citekey: str = "doe2024test", **overrides: object) -> dict:
    entry = {
        "citekey": citekey,
        "title": "A Test Paper",
        "authors": ["Doe, J.", "Smith, A."],
        "year": 2024,
        "venue": "NeurIPS",
        "tags": ["test", "deep-learning"],
        "abstract_summary": "This paper proposes a test method.",
        "relevance": "Baseline comparison in experiments.",
        "key_quotes": [
            {"id": "q1", "text": "Our method achieves 95% accuracy.", "page": 5}
        ],
        "bibtex": "@inproceedings{doe2024test,\n  title={A Test Paper},\n  author={Doe, J. and Smith, A.},\n  year={2024},\n  booktitle={NeurIPS},\n}",
    }
    entry.update(overrides)
    return entry


# ============================================================
# 1. CRUD
# ============================================================

class TestCRUD:

    def test_empty_library(self, project: BibManager):
        assert project.list_references() == []

    def test_add_and_get(self, project: BibManager):
        entry = _sample_entry()
        project.add_reference(entry)

        refs = project.list_references()
        assert len(refs) == 1
        assert refs[0]["citekey"] == "doe2024test"

        ref = project.get_reference("doe2024test")
        assert ref is not None
        assert ref["title"] == "A Test Paper"

    def test_add_without_citekey_raises(self, project: BibManager):
        with pytest.raises(ValueError, match="citekey"):
            project.add_reference({"title": "No key"})

    def test_update_existing(self, project: BibManager):
        project.add_reference(_sample_entry())
        project.add_reference(_sample_entry(title="Updated Title"))

        refs = project.list_references()
        assert len(refs) == 1
        assert refs[0]["title"] == "Updated Title"

    def test_remove(self, project: BibManager):
        project.add_reference(_sample_entry())
        assert project.remove_reference("doe2024test") is True
        assert project.list_references() == []

    def test_remove_nonexistent(self, project: BibManager):
        assert project.remove_reference("nope") is False

    def test_get_nonexistent(self, project: BibManager):
        assert project.get_reference("nope") is None

    def test_multiple_entries(self, project: BibManager):
        project.add_reference(_sample_entry("a2024"))
        project.add_reference(_sample_entry("b2025"))

        assert len(project.list_references()) == 2
        assert project.get_reference("a2024") is not None
        assert project.get_reference("b2025") is not None


# ============================================================
# 2. BibTeX 同步
# ============================================================

class TestSyncBib:

    def test_sync_creates_bib(self, project: BibManager):
        project.add_reference(_sample_entry())
        bib_path = project.sync_bib()

        assert bib_path.exists()
        content = bib_path.read_text(encoding="utf-8")
        assert "doe2024test" in content
        assert "A Test Paper" in content

    def test_sync_empty_library(self, project: BibManager):
        bib_path = project.sync_bib()
        assert bib_path.exists()
        content = bib_path.read_text(encoding="utf-8")
        assert "Auto-generated" in content

    def test_sync_auto_generate_bibtex(self, project: BibManager):
        entry = _sample_entry(bibtex="")
        project.add_reference(entry)
        bib_path = project.sync_bib()

        content = bib_path.read_text(encoding="utf-8")
        assert "@inproceedings{doe2024test" in content
        assert "NeurIPS" in content


# ============================================================
# 3. 引用溯源
# ============================================================

class TestQuotes:

    def test_get_quote(self, project: BibManager):
        project.add_reference(_sample_entry())
        q = project.get_quote("doe2024test", "q1")
        assert q is not None
        assert "95% accuracy" in q["text"]

    def test_get_quote_nonexistent(self, project: BibManager):
        project.add_reference(_sample_entry())
        assert project.get_quote("doe2024test", "q99") is None
        assert project.get_quote("nope", "q1") is None

    def test_get_all_quotes(self, project: BibManager):
        project.add_reference(_sample_entry())
        quotes = project.get_all_quotes("doe2024test")
        assert len(quotes) == 1

    def test_reference_summary(self, project: BibManager):
        project.add_reference(_sample_entry())
        summary = project.get_reference_summary("doe2024test")
        assert "A Test Paper" in summary
        assert "doe2024test" in summary
        assert "关键原文" in summary

    def test_summary_nonexistent(self, project: BibManager):
        summary = project.get_reference_summary("nope")
        assert "未找到" in summary


# ============================================================
# 4. 文献搜索
# ============================================================

class TestSearch:

    def test_search_by_title(self, project: BibManager):
        project.add_reference(_sample_entry())
        results = project.search_local("Test Paper")
        assert len(results) == 1

    def test_search_by_tag(self, project: BibManager):
        project.add_reference(_sample_entry())
        results = project.search_local("deep-learning")
        assert len(results) == 1

    def test_search_no_results(self, project: BibManager):
        project.add_reference(_sample_entry())
        results = project.search_local("quantum computing")
        assert len(results) == 0

    def test_suggest_citations(self, project: BibManager):
        project.add_reference(_sample_entry(tags=["transformer", "attention"]))
        suggestions = project.suggest_citations("We use a transformer-based attention mechanism")
        assert len(suggestions) >= 1


# ============================================================
# 5. 引用验证
# ============================================================

class TestValidation:

    def test_validate_all_valid(self, project: BibManager):
        project.add_reference(_sample_entry())
        project.sync_bib()

        tex = project.root / "paper" / "sections" / "01-intro.tex"
        _write(tex, r"As shown in \cite{doe2024test}, the method works.")

        result = project.validate_citations()
        assert result["missing"] == []
        assert "doe2024test" in result["valid"]

    def test_validate_missing_citation(self, project: BibManager):
        project.add_reference(_sample_entry())
        project.sync_bib()

        tex = project.root / "paper" / "sections" / "01-intro.tex"
        _write(tex, r"See \cite{nonexistent2024}.")

        result = project.validate_citations()
        assert len(result["missing"]) == 1
        assert result["missing"][0]["citekey"] == "nonexistent2024"

    def test_validate_uncited(self, project: BibManager):
        project.add_reference(_sample_entry())

        result = project.validate_citations()
        assert "doe2024test" in result["uncited"]

    def test_validate_specific_file(self, project: BibManager):
        project.add_reference(_sample_entry())
        project.sync_bib()

        tex = project.root / "paper" / "sections" / "01-intro.tex"
        _write(tex, r"\cite{doe2024test}")

        result = project.validate_citations(tex_path=tex)
        assert result["missing"] == []

    def test_validate_multiple_cites(self, project: BibManager):
        project.add_reference(_sample_entry("a2024"))
        project.add_reference(_sample_entry("b2025"))
        project.sync_bib()

        tex = project.root / "paper" / "sections" / "01-intro.tex"
        _write(tex, r"\cite{a2024, b2025}")

        result = project.validate_citations()
        assert result["missing"] == []
        assert result["total_citations"] == 2


# ============================================================
# 6. 边界场景
# ============================================================

class TestBibEdgeCases:

    def test_corrupt_library(self, tmp_path: Path):
        (tmp_path / "refs").mkdir()
        (tmp_path / "paper").mkdir()
        (tmp_path / "refs" / "library.yaml").write_text("{{bad", encoding="utf-8")

        bm = BibManager(project_root=tmp_path)
        assert bm.list_references() == []

    def test_no_library_file(self, tmp_path: Path):
        (tmp_path / "refs").mkdir()
        (tmp_path / "paper").mkdir()

        bm = BibManager(project_root=tmp_path)
        assert bm.list_references() == []
        bm.sync_bib()  # should not crash
