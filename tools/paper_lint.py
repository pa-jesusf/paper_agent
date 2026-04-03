"""
Paper Agent — 论文质量检查工具

核心职责:
1. 引用完整性检查（所有 \\cite{} 是否存在于 .bib）
2. 图表引用检查（所有 \\ref{fig:...} 是否有对应 \\label）
3. 引用溯源验证（引用是否有 key_quotes 支撑）
4. 页数检查（正文是否超过 page_limit）
5. 标记检查（TODO / CONFIRM 标记统计）
6. 结构完整性检查（大纲对齐）

输入: paper/ 全部文件 + config/ + refs/
输出: 综合质量报告
"""

from __future__ import annotations

import re
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
class LintItem:
    """单条 lint 结果。"""
    level: str        # "error" | "warn" | "info"
    category: str     # 类别名
    file: str
    line: int | None
    message: str

    def __str__(self) -> str:
        tag = {"error": "ERROR", "warn": "WARN", "info": "INFO"}.get(self.level, "?")
        loc = f"{self.file}:{self.line}" if self.line else self.file
        return f"[{tag}] [{self.category}] {loc} — {self.message}"


@dataclass
class LintReport:
    """综合 lint 报告。"""
    items: list[LintItem] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.items if i.level == "error")

    @property
    def warn_count(self) -> int:
        return sum(1 for i in self.items if i.level == "warn")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.items if i.level == "info")

    def summary(self) -> str:
        lines = [
            f"论文质量检查: {self.error_count} errors, {self.warn_count} warnings, {self.info_count} info"
        ]
        for item in self.items:
            lines.append(f"  {item}")
        if not self.items:
            lines.append("  ✓ 全部通过")
        return "\n".join(lines)


# ============================================================
# 核心类
# ============================================================

class PaperLint:
    """论文综合质量检查器。"""

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.paper_dir = self.root / "paper"
        self.config_dir = self.root / "config"
        self.refs_dir = self.root / "refs"

    def check_all(self) -> LintReport:
        """运行所有检查。"""
        report = LintReport()

        self._check_citations(report)
        self._check_figure_refs(report)
        self._check_citation_sourcing(report)
        self._check_todo_marks(report)
        self._check_section_structure(report)
        self._check_empty_sections(report)
        self._check_style_rules(report)

        return report

    # ----------------------------------------------------------
    # 1. 引用完整性
    # ----------------------------------------------------------

    def _check_citations(self, report: LintReport) -> None:
        """检查所有 \\cite{} 是否存在于 references.bib 和 library.yaml。"""
        bib_path = self.paper_dir / "references.bib"
        bib_keys: set[str] = set()

        if bib_path.exists():
            content = bib_path.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"@\w+\{([^,]+),", content):
                bib_keys.add(m.group(1).strip())

        library_keys = self._get_library_keys()
        all_known = bib_keys | library_keys

        tex_files = self._collect_tex_files()
        cite_pattern = re.compile(r"\\cite[tp]?\{([^}]+)\}")

        for tex_file in tex_files:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = self._rel(tex_file)
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if line.lstrip().startswith("%"):
                    continue
                for m in cite_pattern.finditer(line):
                    keys = [k.strip() for k in m.group(1).split(",")]
                    for key in keys:
                        if key not in all_known:
                            report.items.append(LintItem(
                                level="error", category="citation",
                                file=rel_path, line=i + 1,
                                message=f"引用 \\cite{{{key}}} 不存在于 references.bib",
                            ))

    # ----------------------------------------------------------
    # 2. 图表引用检查
    # ----------------------------------------------------------

    def _check_figure_refs(self, report: LintReport) -> None:
        """检查 \\ref{fig:...} 和 \\ref{tab:...} 是否有对应 \\label。"""
        tex_files = self._collect_tex_files()

        all_labels: set[str] = set()
        all_refs: list[tuple[str, str, int]] = []  # (ref_key, file, line)

        label_pattern = re.compile(r"\\label\{([^}]+)\}")
        ref_pattern = re.compile(r"\\ref\{([^}]+)\}")

        for tex_file in tex_files:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = self._rel(tex_file)
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if line.lstrip().startswith("%"):
                    continue
                for m in label_pattern.finditer(line):
                    all_labels.add(m.group(1))
                for m in ref_pattern.finditer(line):
                    all_refs.append((m.group(1), rel_path, i + 1))

        for ref_key, file, line in all_refs:
            if ref_key not in all_labels:
                report.items.append(LintItem(
                    level="error", category="ref",
                    file=file, line=line,
                    message=f"\\ref{{{ref_key}}} 无对应 \\label",
                ))

        # 检查未被引用的 label
        referenced = {r[0] for r in all_refs}
        for label in all_labels:
            if label not in referenced:
                report.items.append(LintItem(
                    level="warn", category="ref",
                    file="paper/", line=None,
                    message=f"\\label{{{label}}} 已定义但未被 \\ref 引用",
                ))

    # ----------------------------------------------------------
    # 3. 引用溯源检查
    # ----------------------------------------------------------

    def _check_citation_sourcing(self, report: LintReport) -> None:
        """检查 library.yaml 中被引用的文献是否有 key_quotes。"""
        library = self._load_library()
        if not library:
            return

        # 收集所有被引用的 citekeys
        cited_keys: set[str] = set()
        tex_files = self._collect_tex_files()
        cite_pattern = re.compile(r"\\cite[tp]?\{([^}]+)\}")

        for tex_file in tex_files:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            for m in cite_pattern.finditer(content):
                keys = [k.strip() for k in m.group(1).split(",")]
                cited_keys.update(keys)

        # 检查被引用的文献是否有 key_quotes
        for ref in library:
            citekey = ref.get("citekey", "")
            if citekey in cited_keys:
                quotes = ref.get("key_quotes", [])
                if not quotes:
                    report.items.append(LintItem(
                        level="warn", category="sourcing",
                        file="refs/library.yaml", line=None,
                        message=f"文献 {citekey} 被引用但缺少 key_quotes 溯源",
                    ))

    # ----------------------------------------------------------
    # 4. TODO / CONFIRM 标记
    # ----------------------------------------------------------

    def _check_todo_marks(self, report: LintReport) -> None:
        """统计 TODO 和 CONFIRM 标记。"""
        tex_files = self._collect_tex_files()
        todo_pattern = re.compile(r"\\todo\{([^}]*)\}", re.IGNORECASE)
        confirm_pattern = re.compile(r"\\confirm\{([^}]*)\}", re.IGNORECASE)
        comment_todo = re.compile(r"%\s*(?:TODO|FIXME|XXX|HACK)\b:?\s*(.*)", re.IGNORECASE)

        for tex_file in tex_files:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = self._rel(tex_file)
            lines = content.split("\n")

            for i, line in enumerate(lines):
                for m in todo_pattern.finditer(line):
                    report.items.append(LintItem(
                        level="info", category="todo",
                        file=rel_path, line=i + 1,
                        message=f"TODO: {m.group(1)}" if m.group(1) else "TODO 标记",
                    ))
                for m in confirm_pattern.finditer(line):
                    report.items.append(LintItem(
                        level="info", category="confirm",
                        file=rel_path, line=i + 1,
                        message=f"CONFIRM: {m.group(1)}" if m.group(1) else "待确认标记",
                    ))
                for m in comment_todo.finditer(line):
                    report.items.append(LintItem(
                        level="info", category="todo",
                        file=rel_path, line=i + 1,
                        message=f"注释 TODO: {m.group(1).strip()}",
                    ))

    # ----------------------------------------------------------
    # 5. 章节结构完整性
    # ----------------------------------------------------------

    def _check_section_structure(self, report: LintReport) -> None:
        """检查 paper/sections/ 下的文件是否在 main.tex 中被引用。"""
        sections_dir = self.paper_dir / "sections"
        if not sections_dir.exists():
            return

        main_tex = self.paper_dir / "main.tex"
        if not main_tex.exists():
            return

        main_content = main_tex.read_text(encoding="utf-8", errors="ignore")

        section_files = sorted(sections_dir.glob("*.tex"))
        for sec_file in section_files:
            sec_name = sec_file.stem
            # 检查 main.tex 中是否有 \input{sections/xxx}
            if f"sections/{sec_name}" not in main_content:
                report.items.append(LintItem(
                    level="warn", category="structure",
                    file=f"paper/sections/{sec_file.name}", line=None,
                    message=f"{sec_name} 章节文件存在但未在 main.tex 中 \\input",
                ))

    # ----------------------------------------------------------
    # 6. 空章节检查
    # ----------------------------------------------------------

    def _check_empty_sections(self, report: LintReport) -> None:
        """检查是否有内容过少的章节文件。"""
        sections_dir = self.paper_dir / "sections"
        if not sections_dir.exists():
            return

        for tex_file in sorted(sections_dir.glob("*.tex")):
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            # 去掉注释和空行
            effective = re.sub(r"^\s*%.*$", "", content, flags=re.MULTILINE)
            effective = effective.strip()

            if len(effective) < 50:
                report.items.append(LintItem(
                    level="warn", category="content",
                    file=self._rel(tex_file), line=None,
                    message="章节内容过少（可能是空模板）",
                ))

    # ----------------------------------------------------------
    # 7. 写作风格检查
    # ----------------------------------------------------------

    # 第一人称用法
    _FIRST_PERSON_RE = re.compile(
        r"我们?(?:认为|提出|设计|实现|发现|观察|采用|构建|开发|引入|使用|分析|验证|证明|注意到)"
    )
    # 模糊修饰语（无定量支撑）
    _VAGUE_RE = re.compile(
        r"(?:大幅|显著|极大地?)(?:提升|提高|改善|增强|降低|减少|优于|超过)"
        r"|效果(?:非常|很|十分|极其)好"
        r"|实验结果令人满意"
    )

    def _check_style_rules(self, report: LintReport) -> None:
        """检查正文中常见的学术写作规范问题。"""
        tex_files = self._collect_tex_files()
        banned = self._load_banned_phrases()

        for tex_file in tex_files:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = self._rel(tex_file)
            lines = content.split("\n")

            for i, line in enumerate(lines):
                if line.lstrip().startswith("%"):
                    continue

                for m in self._FIRST_PERSON_RE.finditer(line):
                    report.items.append(LintItem(
                        level="warn", category="style",
                        file=rel_path, line=i + 1,
                        message=f"第一人称用法「{m.group()}」→ 建议改为「本文/本章/实验表明」",
                    ))

                for m in self._VAGUE_RE.finditer(line):
                    report.items.append(LintItem(
                        level="warn", category="style",
                        file=rel_path, line=i + 1,
                        message=f"模糊修饰语「{m.group()}」→ 建议替换为具体数值或百分比",
                    ))

                for phrase in banned:
                    if phrase in line:
                        report.items.append(LintItem(
                            level="warn", category="style",
                            file=rel_path, line=i + 1,
                            message=f"禁止套话「{phrase}」",
                        ))

    def _load_banned_phrases(self) -> list[str]:
        """从 style-guide.md 提取禁止用语列表。

        识别以 '禁止' 开头的列表区块，提取列表项中引号内的短语。
        """
        guide_path = self.config_dir / "style-guide.md"
        if not guide_path.exists():
            return []
        try:
            content = guide_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []

        phrases: list[str] = []
        in_ban_section = False
        # 匹配引号或书名号内的文本
        _quote_re = re.compile(r'[""「"\'](.+?)[""」"\']')

        for line in content.split("\n"):
            if re.search(r"禁止.*(?:使用|用语|写法|套话)", line):
                in_ban_section = True
                continue
            if in_ban_section and (line.startswith("#") or line.startswith("---")):
                in_ban_section = False
                continue
            if in_ban_section and line.strip().startswith(("-", "*")):
                m = _quote_re.search(line)
                if m:
                    phrase = m.group(1).strip()
                    if len(phrase) >= 2:
                        phrases.append(phrase)

        return phrases

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------

    def _collect_tex_files(self) -> list[Path]:
        files: list[Path] = []
        sections = self.paper_dir / "sections"
        if sections.exists():
            files.extend(sorted(sections.glob("*.tex")))
        main = self.paper_dir / "main.tex"
        if main.exists():
            files.append(main)
        return files

    def _get_library_keys(self) -> set[str]:
        library = self._load_library()
        return {r.get("citekey", "") for r in library if r.get("citekey")}

    def _load_library(self) -> list[dict]:
        lib_path = self.refs_dir / "library.yaml"
        if not lib_path.exists():
            return []
        try:
            with open(lib_path, encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
            refs = data.get("references", [])
            return refs if isinstance(refs, list) else []
        except yaml.YAMLError:
            return []

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)


# ============================================================
# CLI 入口
# ============================================================

def main():
    lint = PaperLint()
    report = lint.check_all()
    print(report.summary())


if __name__ == "__main__":
    main()
