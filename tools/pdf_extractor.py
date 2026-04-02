"""
Paper Agent — PDF 文献解析与摘录工具

核心职责:
1. 从 PDF 中提取元信息（标题、作者、年份等）
2. 提取摘要文本
3. 提取关键原文段落（保留页码），用于引用溯源
4. 提取图表 caption
5. 一键生成 library.yaml 条目

依赖: PyMuPDF (fitz) — 需要 `pip install PyMuPDF`
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None  # type: ignore[assignment]

import yaml


# ============================================================
# 常量
# ============================================================

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent
REFS_DIR = PROJECT_ROOT / "refs"
LIBRARY_YAML = REFS_DIR / "library.yaml"


# ============================================================
# 数据类
# ============================================================

@dataclass
class KeyQuote:
    """从 PDF 中提取的关键原文摘录。"""
    id: str
    text: str
    page: int
    context: str = ""

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "text": self.text, "page": self.page}
        if self.context:
            d["context"] = self.context
        return d


@dataclass
class FigureCaption:
    """从 PDF 中提取的图表 caption。"""
    label: str        # "Figure 1" / "Table 2"
    caption: str
    page: int

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "caption": self.caption, "page": self.page}


@dataclass
class PDFMetadata:
    """从 PDF 提取的元信息。"""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    doi: str = ""
    abstract: str = ""
    key_quotes: list[KeyQuote] = field(default_factory=list)
    figures: list[FigureCaption] = field(default_factory=list)
    page_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.title:
            d["title"] = self.title
        if self.authors:
            d["authors"] = self.authors
        if self.year:
            d["year"] = self.year
        if self.doi:
            d["doi"] = self.doi
        if self.abstract:
            d["abstract"] = self.abstract
        if self.key_quotes:
            d["key_quotes"] = [q.to_dict() for q in self.key_quotes]
        if self.figures:
            d["figures"] = [f.to_dict() for f in self.figures]
        d["page_count"] = self.page_count
        return d


# ============================================================
# 核心类
# ============================================================

class PDFExtractor:
    """PDF 文献解析工具。

    从学术论文 PDF 中提取结构化信息，包括元信息、摘要、
    关键原文段落和图表 caption。
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.refs_dir = self.root / "refs"

    # ----------------------------------------------------------
    # 1. 元信息提取
    # ----------------------------------------------------------

    def extract_metadata(self, pdf_path: str | Path) -> PDFMetadata:
        """从 PDF 提取元信息（标题、作者、年份、DOI）。"""
        self._check_fitz()
        pdf_path = Path(pdf_path)
        meta = PDFMetadata()

        doc = fitz.open(str(pdf_path))
        try:
            meta.page_count = len(doc)

            # 从 PDF 元数据字段获取
            pdf_meta = doc.metadata or {}
            meta.title = (pdf_meta.get("title") or "").strip()
            author_str = (pdf_meta.get("author") or "").strip()
            if author_str:
                meta.authors = [a.strip() for a in re.split(r"[,;]", author_str) if a.strip()]

            # 如果元数据标题为空，尝试从首页提取
            if not meta.title:
                meta.title = self._extract_title_from_first_page(doc)

            # 从全文提取 DOI
            first_pages_text = self._get_pages_text(doc, max_pages=3)
            meta.doi = self._extract_doi(first_pages_text)

            # 提取年份
            meta.year = self._extract_year(pdf_meta, first_pages_text)

        finally:
            doc.close()

        return meta

    def extract_abstract(self, pdf_path: str | Path) -> str:
        """提取论文摘要。"""
        self._check_fitz()
        pdf_path = Path(pdf_path)

        doc = fitz.open(str(pdf_path))
        try:
            # 通常摘要在前 2 页
            text = self._get_pages_text(doc, max_pages=2)
        finally:
            doc.close()

        return self._find_abstract(text)

    # ----------------------------------------------------------
    # 2. 关键原文提取
    # ----------------------------------------------------------

    def extract_key_quotes(self, pdf_path: str | Path,
                           focus_topics: list[str] | None = None,
                           max_quotes: int = 10) -> list[KeyQuote]:
        """提取关键原文段落，保留页码。

        策略：
        1. 提取每页文本
        2. 按段落分割
        3. 过滤掉过短/参考文献段落
        4. 使用启发式评分（标题词、数字、关键短语等）
        5. 如有 focus_topics，额外加权包含这些词的段落

        返回按重要度排序的前 max_quotes 条。
        """
        self._check_fitz()
        pdf_path = Path(pdf_path)

        doc = fitz.open(str(pdf_path))
        try:
            candidates: list[tuple[float, str, int]] = []  # (score, text, page)

            for page_idx in range(len(doc)):
                page_text = doc[page_idx].get_text("text")
                paragraphs = self._split_paragraphs(page_text)

                for para in paragraphs:
                    if len(para) < 60 or len(para) > 2000:
                        continue
                    if self._is_reference_line(para):
                        continue

                    score = self._score_paragraph(para, focus_topics)
                    if score > 0:
                        candidates.append((score, para, page_idx + 1))

        finally:
            doc.close()

        # 排序取 top N
        candidates.sort(key=lambda x: x[0], reverse=True)
        quotes = []
        for i, (score, text, page) in enumerate(candidates[:max_quotes]):
            quotes.append(KeyQuote(
                id=f"q{i + 1}",
                text=text.strip(),
                page=page,
                context="",
            ))

        return quotes

    # ----------------------------------------------------------
    # 3. 图表 caption 提取
    # ----------------------------------------------------------

    def extract_figures_tables(self, pdf_path: str | Path) -> list[FigureCaption]:
        """提取图表的 caption 和位置信息。"""
        self._check_fitz()
        pdf_path = Path(pdf_path)

        doc = fitz.open(str(pdf_path))
        try:
            captions: list[FigureCaption] = []
            # 匹配 Figure X: ... 或 Table X: ...
            pattern = re.compile(
                r"((?:Figure|Fig\.|Table)\s+\d+[\.:]\s*.+?)(?:\n\n|\Z)",
                re.IGNORECASE | re.DOTALL,
            )

            for page_idx in range(len(doc)):
                page_text = doc[page_idx].get_text("text")
                for m in pattern.finditer(page_text):
                    raw = m.group(1).strip()
                    # 清理换行
                    raw = re.sub(r"\s+", " ", raw)
                    # 分离 label 和 caption
                    label_match = re.match(
                        r"((?:Figure|Fig\.|Table)\s+\d+)", raw, re.IGNORECASE
                    )
                    label = label_match.group(1) if label_match else raw[:20]
                    caption_text = raw[len(label):].lstrip(".:").strip() if label_match else raw

                    captions.append(FigureCaption(
                        label=label,
                        caption=caption_text,
                        page=page_idx + 1,
                    ))

        finally:
            doc.close()

        return captions

    # ----------------------------------------------------------
    # 4. 一键生成 library.yaml 条目
    # ----------------------------------------------------------

    def build_library_entry(self, pdf_path: str | Path,
                            citekey: str = "",
                            focus_topics: list[str] | None = None) -> dict[str, Any]:
        """一键生成完整的 library.yaml 条目。"""
        pdf_path = Path(pdf_path)

        meta = self.extract_metadata(pdf_path)
        abstract = self.extract_abstract(pdf_path)
        quotes = self.extract_key_quotes(pdf_path, focus_topics=focus_topics)
        figures = self.extract_figures_tables(pdf_path)

        if not citekey:
            citekey = self._generate_citekey(meta)

        entry: dict[str, Any] = {"citekey": citekey}
        if meta.title:
            entry["title"] = meta.title
        if meta.authors:
            entry["authors"] = meta.authors
        if meta.year:
            entry["year"] = meta.year
        if meta.doi:
            entry["doi"] = meta.doi
        if abstract:
            entry["abstract_summary"] = abstract
        entry["relevance"] = ""  # 待 Agent 或用户填写
        entry["tags"] = []

        if quotes:
            entry["key_quotes"] = [q.to_dict() for q in quotes]

        # PDF 相对路径
        try:
            rel = pdf_path.relative_to(self.root)
            entry["pdf_path"] = str(rel).replace("\\", "/")
        except ValueError:
            entry["pdf_path"] = str(pdf_path)

        entry["bibtex"] = self._generate_bibtex_stub(entry)

        return entry

    def add_to_library(self, entry: dict[str, Any]) -> Path:
        """将条目追加到 refs/library.yaml。"""
        lib_path = self.refs_dir / "library.yaml"
        lib_path.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, Any] = {}
        if lib_path.exists():
            try:
                with open(lib_path, encoding="utf-8") as fp:
                    data = yaml.safe_load(fp) or {}
            except yaml.YAMLError:
                data = {}

        refs = data.get("references", [])
        if not isinstance(refs, list):
            refs = []

        # 检查是否已存在相同 citekey
        existing_keys = {r.get("citekey") for r in refs if isinstance(r, dict)}
        if entry.get("citekey") in existing_keys:
            # 更新已有条目
            refs = [entry if r.get("citekey") == entry["citekey"] else r for r in refs]
        else:
            refs.append(entry)

        data["references"] = refs

        with open(lib_path, "w", encoding="utf-8") as fp:
            yaml.dump(data, fp, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)

        return lib_path

    # ----------------------------------------------------------
    # 内部辅助方法
    # ----------------------------------------------------------

    @staticmethod
    def _check_fitz():
        if fitz is None:
            raise ImportError(
                "PyMuPDF 未安装。请运行: pip install PyMuPDF"
            )

    @staticmethod
    def _get_pages_text(doc: Any, max_pages: int | None = None) -> str:
        n = len(doc) if max_pages is None else min(max_pages, len(doc))
        parts = []
        for i in range(n):
            parts.append(doc[i].get_text("text"))
        return "\n".join(parts)

    @staticmethod
    def _extract_title_from_first_page(doc: Any) -> str:
        """尝试从首页最大字号文本中提取标题。"""
        if len(doc) == 0:
            return ""
        blocks = doc[0].get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE).get("blocks", [])
        best_size = 0.0
        best_text = ""
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size", 0)
                    text = span.get("text", "").strip()
                    if size > best_size and len(text) > 5:
                        best_size = size
                        best_text = text
        return best_text

    @staticmethod
    def _extract_doi(text: str) -> str:
        m = re.search(r"(10\.\d{4,}/[^\s,;\"']+)", text)
        return m.group(1).rstrip(".") if m else ""

    @staticmethod
    def _extract_year(pdf_meta: dict, text: str) -> int | None:
        # 先看 PDF 元数据
        for key in ("creationDate", "modDate"):
            val = pdf_meta.get(key, "")
            if val:
                m = re.search(r"(\d{4})", val)
                if m:
                    year = int(m.group(1))
                    if 1900 <= year <= 2100:
                        return year
        # 再从文本中提取
        years = re.findall(r"\b((?:19|20)\d{2})\b", text)
        if years:
            # 取首页出现的最可能年份
            for y in years:
                val = int(y)
                if 2000 <= val <= 2100:
                    return val
            return int(years[0])
        return None

    @staticmethod
    def _find_abstract(text: str) -> str:
        """在文本中定位 Abstract 段落。"""
        # 匹配 Abstract 标题后面的内容
        patterns = [
            re.compile(r"(?:^|\n)\s*Abstract[\s.:—\-]*\n(.*?)(?:\n\s*(?:1[\s.]|Introduction|Keywords|Index Terms))", re.DOTALL | re.IGNORECASE),
            re.compile(r"(?:^|\n)\s*Abstract[\s.:—\-]*\n(.{100,800})", re.DOTALL | re.IGNORECASE),
        ]
        for pat in patterns:
            m = pat.search(text)
            if m:
                abstract = m.group(1).strip()
                abstract = re.sub(r"\s+", " ", abstract)
                return abstract
        return ""

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        """将页面文本按段落分割。"""
        lines = text.split("\n")
        paragraphs: list[str] = []
        current: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
            else:
                current.append(stripped)

        if current:
            paragraphs.append(" ".join(current))

        return paragraphs

    @staticmethod
    def _is_reference_line(text: str) -> bool:
        """检测是否为参考文献行。"""
        if re.match(r"^\[\d+\]", text):
            return True
        if re.match(r"^\d+\.\s*[A-Z][a-z]+.*\d{4}", text):
            return True
        return False

    @staticmethod
    def _score_paragraph(text: str, focus_topics: list[str] | None = None) -> float:
        """启发式评分：判断段落的重要度。"""
        score = 0.0

        # 包含数字结果（准确率、百分比等）
        if re.search(r"\d+\.?\d*\s*%", text):
            score += 2.0
        if re.search(r"(?:accuracy|precision|recall|F1|BLEU|ROUGE)\s*[:=]?\s*\d", text, re.IGNORECASE):
            score += 2.0

        # 包含关键学术短语
        key_phrases = [
            r"we propose", r"we introduce", r"our method", r"our approach",
            r"main contribution", r"key insight", r"novel",
            r"state.of.the.art", r"outperform", r"significant",
            r"本文提出", r"我们提出", r"主要贡献", r"创新点",
        ]
        for phrase in key_phrases:
            if re.search(phrase, text, re.IGNORECASE):
                score += 1.5

        # 段落长度适中加分
        if 100 <= len(text) <= 500:
            score += 0.5

        # focus topics 加权
        if focus_topics:
            for topic in focus_topics:
                if topic.lower() in text.lower():
                    score += 3.0

        return score

    @staticmethod
    def _generate_citekey(meta: PDFMetadata) -> str:
        """从元信息生成 citekey。"""
        first_author = ""
        if meta.authors:
            # 取姓氏
            name = meta.authors[0]
            parts = name.replace(",", " ").split()
            first_author = parts[0].lower() if parts else "unknown"
            # 只保留字母
            first_author = re.sub(r"[^a-z]", "", first_author)

        year = str(meta.year) if meta.year else "nodate"

        # 从标题取第一个实义词
        title_word = ""
        if meta.title:
            stop_words = {"a", "an", "the", "of", "for", "and", "in", "on", "to", "with", "is", "are"}
            for word in meta.title.split():
                clean = re.sub(r"[^a-z]", "", word.lower())
                if clean and clean not in stop_words:
                    title_word = clean
                    break

        return f"{first_author or 'unknown'}{year}{title_word}"

    @staticmethod
    def _generate_bibtex_stub(entry: dict[str, Any]) -> str:
        """生成 BibTeX 条目骨架。"""
        key = entry.get("citekey", "unknown")
        title = entry.get("title", "")
        authors = ", ".join(entry.get("authors", []))
        year = entry.get("year", "")
        doi = entry.get("doi", "")

        lines = [
            f"@article{{{key},",
            f"  title={{{title}}},",
            f"  author={{{authors}}},",
            f"  year={{{year}}},",
        ]
        if doi:
            lines.append(f"  doi={{{doi}}},")
        lines.append("}")
        return "\n".join(lines)


# ============================================================
# CLI 入口
# ============================================================

def main():
    import sys
    if len(sys.argv) < 2:
        print("用法: python pdf_extractor.py <pdf_path> [citekey]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    citekey = sys.argv[2] if len(sys.argv) > 2 else ""

    ext = PDFExtractor()
    entry = ext.build_library_entry(pdf_path, citekey=citekey)
    print(yaml.dump(entry, default_flow_style=False, allow_unicode=True))


if __name__ == "__main__":
    main()
