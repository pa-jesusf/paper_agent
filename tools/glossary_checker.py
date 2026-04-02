"""
Paper Agent — 术语与符号一致性检查工具

核心职责:
1. 扫描 .tex 文件，检查术语拼写变体
2. 检查首次使用缩写是否展开
3. 检查数学符号是否使用了 preamble 中定义的宏
4. 检查中文论文中术语首现是否附注英文

输入: paper/sections/*.tex + config/glossary.yaml + paper/preamble.tex
输出: 诊断报告（warnings 列表）
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
class LintIssue:
    """单条诊断结果。"""
    level: str        # "error" | "warn" | "info"
    file: str         # 相对路径
    line: int         # 行号
    message: str      # 诊断信息
    rule: str         # 规则名称

    def __str__(self) -> str:
        tag = {"error": "ERROR", "warn": "WARN", "info": "INFO"}.get(self.level, "?")
        return f"[{tag}] {self.file}:{self.line} — {self.message}"


@dataclass
class CheckReport:
    """检查报告。"""
    issues: list[LintIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warn_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "warn")

    def summary(self) -> str:
        lines = [f"术语一致性检查: {self.error_count} errors, {self.warn_count} warnings"]
        for issue in self.issues:
            lines.append(f"  {issue}")
        if not self.issues:
            lines.append("  ✓ 所有术语和符号使用一致")
        return "\n".join(lines)


# ============================================================
# 核心类
# ============================================================

class GlossaryChecker:
    """术语与符号一致性检查器。

    读取 config/glossary.yaml 中的术语和符号定义，
    扫描 paper/sections/ 下的 .tex 文件，检查一致性。
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.config_dir = self.root / "config"
        self.paper_dir = self.root / "paper"

    def check_all(self) -> CheckReport:
        """运行所有检查规则。"""
        report = CheckReport()

        glossary = self._load_glossary()
        if glossary is None:
            report.issues.append(LintIssue(
                level="warn", file="config/glossary.yaml", line=0,
                message="术语表文件不存在或为空", rule="glossary-exists",
            ))
            return report

        tex_files = self._collect_tex_files()
        if not tex_files:
            report.issues.append(LintIssue(
                level="info", file="paper/sections/", line=0,
                message="未找到 .tex 文件", rule="tex-exists",
            ))
            return report

        for tex_file in tex_files:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
            rel_path = str(tex_file.relative_to(self.root)).replace("\\", "/")

            self._check_forbidden_variants(content, rel_path, glossary, report)
            self._check_abbreviation_expansion(content, rel_path, glossary, report)
            self._check_symbol_macros(content, rel_path, glossary, report)
            self._check_chinese_annotation(content, rel_path, glossary, report)

        return report

    # ----------------------------------------------------------
    # 检查规则 1: 禁止变体
    # ----------------------------------------------------------

    def _check_forbidden_variants(self, content: str, file: str,
                                  glossary: dict, report: CheckReport) -> None:
        """检查是否使用了 forbidden_variants 中的术语变体。"""
        terms = glossary.get("terms", [])
        if not terms:
            return

        lines = content.split("\n")
        for term_def in terms:
            canonical = term_def.get("canonical", "")
            variants = term_def.get("forbidden_variants", [])
            for variant in variants:
                pattern = re.compile(re.escape(variant), re.IGNORECASE)
                for i, line in enumerate(lines):
                    # 跳过注释行
                    if line.lstrip().startswith("%"):
                        continue
                    if pattern.search(line):
                        report.issues.append(LintIssue(
                            level="warn", file=file, line=i + 1,
                            message=f'"{variant}" → 应使用 "{canonical}"',
                            rule="forbidden-variant",
                        ))

    # ----------------------------------------------------------
    # 检查规则 2: 缩写展开
    # ----------------------------------------------------------

    def _check_abbreviation_expansion(self, content: str, file: str,
                                      glossary: dict, report: CheckReport) -> None:
        """检查首次使用缩写时是否展开了全称。"""
        terms = glossary.get("terms", [])
        if not terms:
            return

        # 收集所有有缩写的术语
        abbr_terms = [
            t for t in terms
            if t.get("abbreviation") and t.get("first_use")
        ]

        lines = content.split("\n")
        for term_def in abbr_terms:
            abbr = term_def["abbreviation"]
            first_use = term_def["first_use"]

            # 找缩写首次出现的位置（非注释行）
            first_occurrence = None
            for i, line in enumerate(lines):
                if line.lstrip().startswith("%"):
                    continue
                # 搜索独立的缩写（作为单词）
                if re.search(r"\b" + re.escape(abbr) + r"\b", line):
                    first_occurrence = i
                    break

            if first_occurrence is not None:
                # 检查这一行是否包含完整的 first_use 格式
                if first_use not in lines[first_occurrence]:
                    # 检查之前的行是否有展开
                    preceded = "\n".join(lines[:first_occurrence])
                    if first_use not in preceded:
                        report.issues.append(LintIssue(
                            level="warn", file=file, line=first_occurrence + 1,
                            message=f'首次使用 "{abbr}" 未展开全称，应写为 "{first_use}"',
                            rule="abbreviation-expand",
                        ))

    # ----------------------------------------------------------
    # 检查规则 3: 符号宏使用
    # ----------------------------------------------------------

    def _check_symbol_macros(self, content: str, file: str,
                             glossary: dict, report: CheckReport) -> None:
        """检查数学符号是否使用了 preamble 中定义的宏。"""
        symbols = glossary.get("symbols", [])
        if not symbols:
            return

        lines = content.split("\n")
        for sym_def in symbols:
            macro = sym_def.get("latex_macro", "")
            definition = sym_def.get("definition", "")
            name = sym_def.get("name", "")

            if not macro or not definition:
                continue

            # 检查是否直接使用了定义而非宏
            # 例如直接写 \mathcal{L} 而非 \loss
            escaped_def = re.escape(definition)
            for i, line in enumerate(lines):
                if line.lstrip().startswith("%"):
                    continue
                # 检查是否直接使用了底层定义
                if re.search(escaped_def, line):
                    # 确认同一行不是也使用了宏（允许在 preamble 中定义）
                    if macro not in line:
                        report.issues.append(LintIssue(
                            level="warn", file=file, line=i + 1,
                            message=f'直接使用 "{definition}"，应使用宏 "{macro}" ({name})',
                            rule="symbol-macro",
                        ))

    # ----------------------------------------------------------
    # 检查规则 4: 中文论文术语英文标注
    # ----------------------------------------------------------

    def _check_chinese_annotation(self, content: str, file: str,
                                  glossary: dict, report: CheckReport) -> None:
        """检查中文论文中术语首现是否附注英文原文。

        仅在 config/paper.yaml 中 language 为 chinese 时激活。
        """
        paper_yaml = self.config_dir / "paper.yaml"
        if not paper_yaml.exists():
            return

        try:
            with open(paper_yaml, encoding="utf-8") as fp:
                paper_config = yaml.safe_load(fp) or {}
        except yaml.YAMLError:
            return

        lang = paper_config.get("language", "")
        i18n = paper_config.get("i18n", {})
        if lang != "chinese" and i18n.get("primary") != "chinese":
            return

        if not i18n.get("term_original_annotation", True):
            return

        terms = glossary.get("terms", [])
        if not terms:
            return

        lines = content.split("\n")
        # 只检查有中文别名的术语
        for term_def in terms:
            canonical = term_def.get("canonical", "")
            chinese = term_def.get("chinese", "")
            if not chinese or not canonical:
                continue

            # 查找中文术语首次出现
            for i, line in enumerate(lines):
                if line.lstrip().startswith("%"):
                    continue
                if chinese in line:
                    # 检查同一行或前后行是否有英文原文标注
                    context_start = max(0, i - 1)
                    context_end = min(len(lines), i + 2)
                    context = " ".join(lines[context_start:context_end])

                    if canonical.lower() not in context.lower():
                        report.issues.append(LintIssue(
                            level="info", file=file, line=i + 1,
                            message=f'中文术语 "{chinese}" 首次出现，建议附注英文 "{canonical}"',
                            rule="chinese-annotation",
                        ))
                    break  # 只检查首次出现

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------

    def _load_glossary(self) -> dict | None:
        path = self.config_dir / "glossary.yaml"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
            return data
        except yaml.YAMLError:
            return None

    def _collect_tex_files(self) -> list[Path]:
        """收集所有需要检查的 .tex 文件。"""
        files: list[Path] = []
        sections = self.paper_dir / "sections"
        if sections.exists():
            files.extend(sorted(sections.glob("*.tex")))
        main = self.paper_dir / "main.tex"
        if main.exists():
            files.append(main)
        return files


# ============================================================
# CLI 入口
# ============================================================

def main():
    checker = GlossaryChecker()
    report = checker.check_all()
    print(report.summary())


if __name__ == "__main__":
    main()
