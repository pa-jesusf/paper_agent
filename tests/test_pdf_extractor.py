"""
tests/test_pdf_extractor.py — PDFExtractor 单元测试

注: 不依赖真实 PDF 文件，仅测试辅助方法和数据类。
     涉及 fitz 的方法通过 mock 测试。
"""

from __future__ import annotations

import pytest

from tools.pdf_extractor import (
    FigureCaption,
    KeyQuote,
    PDFExtractor,
    PDFMetadata,
)


# ============================================================
# 1. 数据类
# ============================================================

class TestDataClasses:

    def test_key_quote_to_dict(self):
        q = KeyQuote(id="q1", text="Test quote", page=3, context="intro")
        d = q.to_dict()
        assert d["id"] == "q1"
        assert d["text"] == "Test quote"
        assert d["page"] == 3
        assert d["context"] == "intro"

    def test_key_quote_no_context(self):
        q = KeyQuote(id="q1", text="Test", page=1)
        d = q.to_dict()
        assert "context" not in d

    def test_figure_caption_to_dict(self):
        fc = FigureCaption(label="Figure 1", caption="Architecture overview", page=5)
        d = fc.to_dict()
        assert d["label"] == "Figure 1"
        assert d["page"] == 5

    def test_pdf_metadata_to_dict(self):
        meta = PDFMetadata(
            title="Test Paper",
            authors=["Alice", "Bob"],
            year=2024,
            doi="10.1234/test",
            page_count=10,
        )
        d = meta.to_dict()
        assert d["title"] == "Test Paper"
        assert d["year"] == 2024
        assert d["page_count"] == 10

    def test_pdf_metadata_empty(self):
        meta = PDFMetadata()
        d = meta.to_dict()
        assert d["page_count"] == 0
        assert "title" not in d


# ============================================================
# 2. 辅助方法
# ============================================================

class TestHelperMethods:

    def test_extract_doi(self):
        text = "Published at https://doi.org/10.1234/abc.def.123 in NeurIPS."
        doi = PDFExtractor._extract_doi(text)
        assert doi == "10.1234/abc.def.123"

    def test_extract_doi_none(self):
        doi = PDFExtractor._extract_doi("No DOI here.")
        assert doi == ""

    def test_extract_year_from_meta(self):
        meta = {"creationDate": "D:20240315"}
        year = PDFExtractor._extract_year(meta, "")
        assert year == 2024

    def test_extract_year_from_text(self):
        year = PDFExtractor._extract_year({}, "Published in 2023 at NeurIPS.")
        assert year == 2023

    def test_extract_year_none(self):
        year = PDFExtractor._extract_year({}, "No year here.")
        assert year is None

    def test_find_abstract(self):
        text = """
Some header text

Abstract
We propose a novel method for training deep neural networks efficiently.
Our method achieves state-of-the-art performance on multiple benchmarks.

1. Introduction
In this paper...
"""
        abstract = PDFExtractor._find_abstract(text)
        assert "novel method" in abstract
        assert "Introduction" not in abstract

    def test_find_abstract_empty(self):
        abstract = PDFExtractor._find_abstract("No abstract section here.")
        assert abstract == ""

    def test_split_paragraphs(self):
        text = "Line one.\nLine two.\n\nNew paragraph.\nMore text."
        paras = PDFExtractor._split_paragraphs(text)
        assert len(paras) == 2
        assert "Line one." in paras[0]
        assert "New paragraph." in paras[1]

    def test_is_reference_line(self):
        assert PDFExtractor._is_reference_line("[1] Smith et al., 2020")
        assert not PDFExtractor._is_reference_line("We propose a method")

    def test_score_paragraph_with_numbers(self):
        text = "Our method achieves 95.3% accuracy on CIFAR-10."
        score = PDFExtractor._score_paragraph(text)
        assert score > 0

    def test_score_paragraph_with_focus(self):
        text = "We use a transformer-based architecture."
        score_no_focus = PDFExtractor._score_paragraph(text)
        score_with_focus = PDFExtractor._score_paragraph(text, ["transformer"])
        assert score_with_focus > score_no_focus

    def test_score_paragraph_plain(self):
        text = "The weather is nice today."
        score = PDFExtractor._score_paragraph(text)
        assert score == 0

    def test_generate_citekey(self):
        meta = PDFMetadata(
            title="Attention Is All You Need",
            authors=["Vaswani, A."],
            year=2017,
        )
        key = PDFExtractor._generate_citekey(meta)
        assert "vaswani" in key
        assert "2017" in key
        assert "attention" in key

    def test_generate_citekey_no_info(self):
        meta = PDFMetadata()
        key = PDFExtractor._generate_citekey(meta)
        assert "unknown" in key

    def test_generate_bibtex_stub(self):
        entry = {
            "citekey": "test2024",
            "title": "Test Paper",
            "authors": ["Alice", "Bob"],
            "year": 2024,
        }
        bibtex = PDFExtractor._generate_bibtex_stub(entry)
        assert "@article{test2024" in bibtex
        assert "Test Paper" in bibtex

    def test_check_fitz_import_error(self):
        import tools.pdf_extractor as mod
        original = mod.fitz
        try:
            mod.fitz = None
            with pytest.raises(ImportError, match="PyMuPDF"):
                PDFExtractor._check_fitz()
        finally:
            mod.fitz = original


# ============================================================
# 3. Library 添加 (不需要 fitz)
# ============================================================

class TestAddToLibrary:

    def test_add_entry(self, tmp_path):
        ext = PDFExtractor(project_root=tmp_path)
        (tmp_path / "refs").mkdir()

        entry = {"citekey": "test2024", "title": "Test"}
        path = ext.add_to_library(entry)

        assert path.exists()
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert len(data["references"]) == 1
        assert data["references"][0]["citekey"] == "test2024"

    def test_add_duplicate_updates(self, tmp_path):
        ext = PDFExtractor(project_root=tmp_path)
        (tmp_path / "refs").mkdir()

        ext.add_to_library({"citekey": "test2024", "title": "V1"})
        ext.add_to_library({"citekey": "test2024", "title": "V2"})

        import yaml
        with open(tmp_path / "refs" / "library.yaml", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert len(data["references"]) == 1
        assert data["references"][0]["title"] == "V2"

    def test_add_multiple(self, tmp_path):
        ext = PDFExtractor(project_root=tmp_path)
        (tmp_path / "refs").mkdir()

        ext.add_to_library({"citekey": "a2024"})
        ext.add_to_library({"citekey": "b2025"})

        import yaml
        with open(tmp_path / "refs" / "library.yaml", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert len(data["references"]) == 2
