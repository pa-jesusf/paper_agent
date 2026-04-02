"""
Paper Agent — 文献管理工具

核心职责:
1. 文献增删查改（library.yaml）
2. 自动同步 references.bib
3. 引用溯源（通过 key_quotes）
4. 文献搜索（本地语义匹配）
5. 验证 .tex 中的 \\cite{} 引用

设计原则:
- library.yaml 是 Single Source of Truth
- references.bib 由本工具自动生成，禁止手动编辑
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


# ============================================================
# 常量
# ============================================================

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent


# ============================================================
# 核心类
# ============================================================

class BibManager:
    """文献管理器。

    以 refs/library.yaml 为 Single Source of Truth，
    提供增删查改、同步 .bib、引用溯源等功能。
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.refs_dir = self.root / "refs"
        self.library_path = self.refs_dir / "library.yaml"
        self.bib_path = self.root / "paper" / "references.bib"

    # ----------------------------------------------------------
    # 1. 文献 CRUD
    # ----------------------------------------------------------

    def list_references(self) -> list[dict[str, Any]]:
        """列出所有文献条目。"""
        return self._load_references()

    def get_reference(self, citekey: str) -> dict[str, Any] | None:
        """根据 citekey 获取单条文献。"""
        for ref in self._load_references():
            if ref.get("citekey") == citekey:
                return ref
        return None

    def add_reference(self, entry: dict[str, Any]) -> None:
        """添加或更新文献条目。

        如果 citekey 已存在则更新，否则追加。
        """
        if "citekey" not in entry:
            raise ValueError("文献条目必须包含 citekey 字段")

        refs = self._load_references()
        existing_idx = None
        for i, ref in enumerate(refs):
            if ref.get("citekey") == entry["citekey"]:
                existing_idx = i
                break

        if existing_idx is not None:
            refs[existing_idx] = entry
        else:
            refs.append(entry)

        self._save_references(refs)

    def remove_reference(self, citekey: str) -> bool:
        """删除文献条目。返回是否成功删除。"""
        refs = self._load_references()
        new_refs = [r for r in refs if r.get("citekey") != citekey]
        if len(new_refs) == len(refs):
            return False
        self._save_references(new_refs)
        return True

    # ----------------------------------------------------------
    # 2. BibTeX 同步
    # ----------------------------------------------------------

    def sync_bib(self) -> Path:
        """从 library.yaml 同步生成 references.bib。"""
        refs = self._load_references()
        lines = [
            "% Auto-generated from refs/library.yaml",
            "% 请勿手动编辑此文件，使用 bib_manager.py 管理文献",
            "",
        ]

        for ref in refs:
            bibtex = ref.get("bibtex", "").strip()
            if bibtex:
                lines.append(bibtex)
                lines.append("")
            else:
                # 从字段自动生成
                lines.append(self._generate_bibtex(ref))
                lines.append("")

        self.bib_path.parent.mkdir(parents=True, exist_ok=True)
        self.bib_path.write_text("\n".join(lines), encoding="utf-8")
        return self.bib_path

    # ----------------------------------------------------------
    # 3. 引用溯源
    # ----------------------------------------------------------

    def get_quote(self, citekey: str, quote_id: str) -> dict[str, Any] | None:
        """获取指定文献的指定原文摘录。"""
        ref = self.get_reference(citekey)
        if not ref:
            return None
        for q in ref.get("key_quotes", []):
            if q.get("id") == quote_id:
                return q
        return None

    def get_all_quotes(self, citekey: str) -> list[dict[str, Any]]:
        """获取指定文献的所有 key_quotes。"""
        ref = self.get_reference(citekey)
        if not ref:
            return []
        return ref.get("key_quotes", [])

    def get_reference_summary(self, citekey: str) -> str:
        """获取文献摘要信息，供 Agent 决策引用时使用。"""
        ref = self.get_reference(citekey)
        if not ref:
            return f"未找到文献: {citekey}"

        lines = [
            f"## {ref.get('title', '无标题')}",
            f"- citekey: {citekey}",
        ]
        if ref.get("authors"):
            lines.append(f"- 作者: {', '.join(ref['authors'][:3])}")
        if ref.get("year"):
            lines.append(f"- 年份: {ref['year']}")
        if ref.get("abstract_summary"):
            lines.append(f"- 摘要: {ref['abstract_summary']}")
        if ref.get("relevance"):
            lines.append(f"- 相关性: {ref['relevance']}")
        if ref.get("tags"):
            lines.append(f"- 标签: {', '.join(ref['tags'])}")

        quotes = ref.get("key_quotes", [])
        if quotes:
            lines.append(f"- 关键原文: {len(quotes)} 条")
            for q in quotes[:3]:
                lines.append(f"  [{q['id']}] p.{q.get('page', '?')}: {q['text'][:80]}...")

        return "\n".join(lines)

    # ----------------------------------------------------------
    # 4. 文献搜索
    # ----------------------------------------------------------

    def search_local(self, query: str) -> list[dict[str, Any]]:
        """在已有文献中按关键词搜索。

        搜索范围: title, abstract_summary, tags, relevance, key_quotes
        """
        refs = self._load_references()
        query_lower = query.lower()
        query_words = query_lower.split()

        scored: list[tuple[float, dict]] = []
        for ref in refs:
            score = self._search_score(ref, query_lower, query_words)
            if score > 0:
                scored.append((score, ref))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ref for _, ref in scored]

    def suggest_citations(self, text: str) -> list[dict[str, Any]]:
        """给定一段文本，建议可插入的引用。

        通过匹配文献的 tags、title 关键词和 relevance 描述来推荐。
        """
        refs = self._load_references()
        text_lower = text.lower()
        text_words = set(re.findall(r"\b\w{3,}\b", text_lower))

        scored: list[tuple[float, dict]] = []
        for ref in refs:
            score = 0.0
            # 标签匹配
            for tag in ref.get("tags", []):
                if tag.lower() in text_lower:
                    score += 3.0

            # 标题词匹配
            title_words = set(re.findall(r"\b\w{3,}\b", ref.get("title", "").lower()))
            overlap = title_words & text_words
            score += len(overlap) * 1.0

            # 相关性描述匹配
            rel = ref.get("relevance", "").lower()
            rel_words = set(re.findall(r"\b\w{3,}\b", rel))
            score += len(rel_words & text_words) * 0.5

            if score > 0:
                scored.append((score, ref))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ref for _, ref in scored[:5]]

    # ----------------------------------------------------------
    # 5. 引用验证
    # ----------------------------------------------------------

    def validate_citations(self, tex_path: str | Path | None = None) -> dict[str, Any]:
        """检查 .tex 文件中所有 \\cite{} 是否在 library.yaml 中存在。

        若不指定 tex_path，检查 paper/sections/ 下所有 .tex 文件。
        """
        if tex_path:
            tex_files = [Path(tex_path)]
        else:
            sections_dir = self.root / "paper" / "sections"
            if sections_dir.exists():
                tex_files = list(sections_dir.glob("*.tex"))
            else:
                tex_files = []
            main_tex = self.root / "paper" / "main.tex"
            if main_tex.exists():
                tex_files.append(main_tex)

        known_keys = {r.get("citekey") for r in self._load_references()}
        cite_pattern = re.compile(r"\\cite[tp]?\{([^}]+)\}")

        missing: list[dict[str, Any]] = []
        valid: list[str] = []
        all_cited: set[str] = set()

        for tex_file in tex_files:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            for m in cite_pattern.finditer(content):
                keys = [k.strip() for k in m.group(1).split(",")]
                for key in keys:
                    all_cited.add(key)
                    if key not in known_keys:
                        # 找到行号
                        pos = m.start()
                        line_no = content[:pos].count("\n") + 1
                        rel_path = str(tex_file.relative_to(self.root)).replace("\\", "/")
                        missing.append({
                            "citekey": key,
                            "file": rel_path,
                            "line": line_no,
                        })
                    elif key not in valid:
                        valid.append(key)

        # 检查未被引用的文献
        uncited = [k for k in known_keys if k not in all_cited]

        return {
            "valid": valid,
            "missing": missing,
            "uncited": uncited,
            "total_citations": len(all_cited),
        }

    # ----------------------------------------------------------
    # 内部辅助方法
    # ----------------------------------------------------------

    def _load_references(self) -> list[dict[str, Any]]:
        if not self.library_path.exists():
            return []
        try:
            with open(self.library_path, encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
            refs = data.get("references", [])
            return refs if isinstance(refs, list) else []
        except yaml.YAMLError:
            return []

    def _save_references(self, refs: list[dict[str, Any]]) -> None:
        self.library_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"references": refs}
        with open(self.library_path, "w", encoding="utf-8") as fp:
            yaml.dump(data, fp, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)

    @staticmethod
    def _generate_bibtex(ref: dict[str, Any]) -> str:
        key = ref.get("citekey", "unknown")
        title = ref.get("title", "")
        authors = ", ".join(ref.get("authors", []))
        year = ref.get("year", "")
        venue = ref.get("venue", "")
        doi = ref.get("doi", "")

        entry_type = "article"
        if venue:
            vl = venue.lower()
            if any(kw in vl for kw in ("conf", "proc", "workshop", "neurips", "icml", "iclr", "aaai", "acl", "emnlp", "cvpr", "iccv", "eccv")):
                entry_type = "inproceedings"

        lines = [f"@{entry_type}{{{key},"]
        if title:
            lines.append(f"  title={{{title}}},")
        if authors:
            lines.append(f"  author={{{authors}}},")
        if year:
            lines.append(f"  year={{{year}}},")
        if venue:
            field_name = "booktitle" if entry_type == "inproceedings" else "journal"
            lines.append(f"  {field_name}={{{venue}}},")
        if doi:
            lines.append(f"  doi={{{doi}}},")
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _search_score(ref: dict, query_lower: str, query_words: list[str]) -> float:
        score = 0.0
        # 标题匹配
        title = ref.get("title", "").lower()
        for w in query_words:
            if w in title:
                score += 3.0

        # 摘要匹配
        abstract = ref.get("abstract_summary", "").lower()
        for w in query_words:
            if w in abstract:
                score += 1.0

        # 标签匹配
        for tag in ref.get("tags", []):
            if tag.lower() in query_lower or query_lower in tag.lower():
                score += 2.0

        # 相关性匹配
        relevance = ref.get("relevance", "").lower()
        for w in query_words:
            if w in relevance:
                score += 1.5

        # key_quotes 匹配
        for q in ref.get("key_quotes", []):
            if query_lower in q.get("text", "").lower():
                score += 2.0
                break

        return score


# ============================================================
# CLI 入口
# ============================================================

def main():
    import sys

    bm = BibManager()

    if len(sys.argv) < 2:
        print("用法:")
        print("  python bib_manager.py list")
        print("  python bib_manager.py sync")
        print("  python bib_manager.py search <query>")
        print("  python bib_manager.py validate")
        print("  python bib_manager.py summary <citekey>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        for ref in bm.list_references():
            print(f"  {ref.get('citekey', '?')}: {ref.get('title', '无标题')}")

    elif cmd == "sync":
        path = bm.sync_bib()
        print(f"已同步: {path}")

    elif cmd == "search" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        results = bm.search_local(query)
        for r in results:
            print(f"  {r.get('citekey')}: {r.get('title', '')}")

    elif cmd == "validate":
        report = bm.validate_citations()
        if report["missing"]:
            for m in report["missing"]:
                print(f"  [MISS] {m['file']}:{m['line']} — \\cite{{{m['citekey']}}}")
        if report["uncited"]:
            print(f"  [WARN] 未被引用: {', '.join(report['uncited'])}")
        print(f"  总引用数: {report['total_citations']}")

    elif cmd == "summary" and len(sys.argv) > 2:
        print(bm.get_reference_summary(sys.argv[2]))

    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()
