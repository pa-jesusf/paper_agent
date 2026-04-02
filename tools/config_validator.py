"""
Paper Agent — 配置文件校验与自动补全工具

核心职责:
1. 深度校验所有配置文件的结构和语义合法性
2. 交叉校验配置之间的一致性（如 glossary ↔ preamble）
3. 自动补全缺失的可推断字段
4. 生成修复建议

输入: config/ 全部文件 + paper/preamble.tex + refs/library.yaml
输出: 校验报告 + 自动修复结果
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

# 允许的枚举值
_VALID_LANGUAGES = {"chinese", "english"}
_VALID_TONES = {"formal-academic", "technical-concise", "expository"}
_VALID_PERSONS = {"first-plural", "passive", "third-person"}
_VALID_COMPILERS = {"xelatex", "pdflatex", "lualatex"}
_VALID_BIBTOOLS = {"bibtex", "biber"}
_VALID_FORMATS = {"pdf", "svg", "png"}


# ============================================================
# 数据类
# ============================================================

@dataclass
class ValidationIssue:
    """单条校验问题。"""
    level: str          # error | warn | info
    file: str           # 配置文件相对路径
    field: str          # 字段路径
    message: str        # 问题描述
    auto_fix: str = ""  # 自动修复建议（空表示无法自动修复）

    def __str__(self) -> str:
        prefix = f"[{self.level.upper()}]"
        s = f"{prefix} {self.file} → {self.field}: {self.message}"
        if self.auto_fix:
            s += f" (自动修复: {self.auto_fix})"
        return s


@dataclass
class ValidationReport:
    """校验报告。"""
    issues: list[ValidationIssue] = field(default_factory=list)
    auto_fixed: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warn_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "warn")

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "info")

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0

    def summary(self) -> str:
        lines = [f"校验结果: {self.error_count} errors, {self.warn_count} warnings, {self.info_count} info"]
        if self.auto_fixed:
            lines.append(f"自动修复: {len(self.auto_fixed)} 项")
            for fix in self.auto_fixed:
                lines.append(f"  ✓ {fix}")
        for issue in self.issues:
            lines.append(f"  {issue}")
        return "\n".join(lines)


# ============================================================
# 辅助函数
# ============================================================

def _safe_load_yaml(path: Path) -> dict | None:
    """安全加载 YAML，返回 dict 或 None。"""
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else None
    except (yaml.YAMLError, OSError):
        return None


def _get_nested(data: dict, key_path: str, default: Any = None) -> Any:
    """按 'a.b.c' 路径获取嵌套值。"""
    keys = key_path.split(".")
    current = data
    for k in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(k, default)
        if current is default:
            return default
    return current


# ============================================================
# 核心类
# ============================================================

class ConfigValidator:
    """配置文件校验与自动补全。

    校验维度:
    1. 结构校验（必填字段、类型检查）
    2. 值域校验（枚举值、范围检查）
    3. 交叉校验（配置之间的一致性）
    4. 自动补全（可推断的缺失字段）
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.config_dir = self.root / "config"
        self.paper_dir = self.root / "paper"
        self.refs_dir = self.root / "refs"

    # ----------------------------------------------------------
    # 公开接口
    # ----------------------------------------------------------

    def validate_all(self, auto_fix: bool = False) -> ValidationReport:
        """校验所有配置文件，返回综合报告。"""
        report = ValidationReport()
        self._validate_paper_yaml(report, auto_fix)
        self._validate_glossary_yaml(report, auto_fix)
        self._validate_experiment_env(report)
        self._validate_figure_style(report, auto_fix)
        self._validate_style_guide(report)
        self._cross_validate_glossary_preamble(report)
        self._cross_validate_bib_library(report)
        return report

    def validate_paper_yaml(self, auto_fix: bool = False) -> ValidationReport:
        """仅校验 paper.yaml。"""
        report = ValidationReport()
        self._validate_paper_yaml(report, auto_fix)
        return report

    def validate_glossary(self, auto_fix: bool = False) -> ValidationReport:
        """仅校验 glossary.yaml。"""
        report = ValidationReport()
        self._validate_glossary_yaml(report, auto_fix)
        return report

    # ----------------------------------------------------------
    # paper.yaml 校验
    # ----------------------------------------------------------

    def _validate_paper_yaml(self, report: ValidationReport, auto_fix: bool) -> None:
        path = self.config_dir / "paper.yaml"
        fname = "config/paper.yaml"
        data = _safe_load_yaml(path)
        if data is None:
            report.issues.append(ValidationIssue(
                "error", fname, "(root)", "文件不存在或格式错误"))
            return

        # 必填字段
        for f in ("title", "venue", "language"):
            val = data.get(f)
            if not val or (isinstance(val, str) and not val.strip()):
                report.issues.append(ValidationIssue(
                    "error", fname, f, "必填字段缺失或为空"))

        # language 枚举
        lang = data.get("language", "")
        if lang and lang not in _VALID_LANGUAGES:
            report.issues.append(ValidationIssue(
                "error", fname, "language",
                f"不合法的值 '{lang}'，应为 {_VALID_LANGUAGES}"))

        # authors 检查
        authors = data.get("authors")
        if not authors or not isinstance(authors, list):
            report.issues.append(ValidationIssue(
                "warn", fname, "authors", "作者信息缺失"))
        elif authors:
            for i, author in enumerate(authors):
                if isinstance(author, dict) and not author.get("name"):
                    report.issues.append(ValidationIssue(
                        "warn", fname, f"authors[{i}].name", "作者姓名缺失"))

        # style 子节
        style = data.get("style", {})
        if isinstance(style, dict):
            tone = style.get("tone", "")
            if tone and tone not in _VALID_TONES:
                report.issues.append(ValidationIssue(
                    "warn", fname, "style.tone",
                    f"不合法的值 '{tone}'，建议 {_VALID_TONES}"))
            person = style.get("person", "")
            if person and person not in _VALID_PERSONS:
                report.issues.append(ValidationIssue(
                    "warn", fname, "style.person",
                    f"不合法的值 '{person}'，建议 {_VALID_PERSONS}"))

        # latex 子节
        latex = data.get("latex", {})
        if isinstance(latex, dict):
            compiler = latex.get("compiler", "")
            if compiler and compiler not in _VALID_COMPILERS:
                report.issues.append(ValidationIssue(
                    "error", fname, "latex.compiler",
                    f"不合法的编译器 '{compiler}'，应为 {_VALID_COMPILERS}"))
            bibtool = latex.get("bibliography", "")
            if bibtool and bibtool not in _VALID_BIBTOOLS:
                report.issues.append(ValidationIssue(
                    "warn", fname, "latex.bibliography",
                    f"不合法的值 '{bibtool}'，应为 {_VALID_BIBTOOLS}"))

        # page_limit 范围
        page_limit = data.get("page_limit")
        if page_limit is not None:
            if not isinstance(page_limit, (int, float)) or page_limit <= 0:
                report.issues.append(ValidationIssue(
                    "warn", fname, "page_limit",
                    "页数限制应为正数"))

        # 自动补全: 如果 language 存在但缺少 i18n
        if auto_fix and lang and "i18n" not in data:
            data["i18n"] = {
                "primary": lang,
                "secondary": "english" if lang == "chinese" else "chinese",
                "abstract_bilingual": lang == "chinese",
                "term_original_annotation": lang == "chinese",
            }
            path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False),
                            encoding="utf-8")
            report.auto_fixed.append(f"{fname}: 自动补全 i18n 配置")

    # ----------------------------------------------------------
    # glossary.yaml 校验
    # ----------------------------------------------------------

    def _validate_glossary_yaml(self, report: ValidationReport, auto_fix: bool) -> None:
        path = self.config_dir / "glossary.yaml"
        fname = "config/glossary.yaml"
        data = _safe_load_yaml(path)
        if data is None:
            report.issues.append(ValidationIssue(
                "warn", fname, "(root)", "文件不存在或格式错误"))
            return

        # terms 检查
        terms = data.get("terms", [])
        if not isinstance(terms, list):
            report.issues.append(ValidationIssue(
                "error", fname, "terms", "terms 应为列表"))
        else:
            seen_canonical = set()
            for i, term in enumerate(terms):
                if not isinstance(term, dict):
                    continue
                canonical = term.get("canonical", "")
                if not canonical:
                    report.issues.append(ValidationIssue(
                        "error", fname, f"terms[{i}].canonical",
                        "术语缺少 canonical 名称"))
                elif canonical.lower() in seen_canonical:
                    report.issues.append(ValidationIssue(
                        "warn", fname, f"terms[{i}].canonical",
                        f"重复的术语 '{canonical}'"))
                else:
                    seen_canonical.add(canonical.lower())

                # 检查 forbidden_variants 不包含 canonical
                variants = term.get("forbidden_variants", [])
                if isinstance(variants, list):
                    for v in variants:
                        if isinstance(v, str) and v.lower() == canonical.lower():
                            report.issues.append(ValidationIssue(
                                "error", fname, f"terms[{i}].forbidden_variants",
                                f"forbidden_variants 包含了 canonical 自身 '{canonical}'"))

        # symbols 检查
        symbols = data.get("symbols", [])
        if not isinstance(symbols, list):
            if symbols is not None:
                report.issues.append(ValidationIssue(
                    "error", fname, "symbols", "symbols 应为列表"))
        else:
            seen_macros = set()
            for i, sym in enumerate(symbols):
                if not isinstance(sym, dict):
                    continue
                macro = sym.get("latex_macro", "")
                defn = sym.get("definition", "")
                if not macro:
                    report.issues.append(ValidationIssue(
                        "error", fname, f"symbols[{i}].latex_macro",
                        "符号缺少 latex_macro"))
                elif macro in seen_macros:
                    report.issues.append(ValidationIssue(
                        "error", fname, f"symbols[{i}].latex_macro",
                        f"重复的宏 '{macro}'"))
                else:
                    seen_macros.add(macro)
                if not defn:
                    report.issues.append(ValidationIssue(
                        "warn", fname, f"symbols[{i}].definition",
                        "符号缺少 definition"))

    # ----------------------------------------------------------
    # experiment-env.yaml 校验
    # ----------------------------------------------------------

    def _validate_experiment_env(self, report: ValidationReport) -> None:
        path = self.config_dir / "experiment-env.yaml"
        fname = "config/experiment-env.yaml"
        data = _safe_load_yaml(path)
        if data is None:
            report.issues.append(ValidationIssue(
                "warn", fname, "(root)", "文件不存在或格式错误"))
            return

        # hardware 检查
        hw = data.get("hardware", {})
        if not isinstance(hw, dict) or not hw:
            report.issues.append(ValidationIssue(
                "warn", fname, "hardware", "硬件信息缺失"))
        else:
            if not hw.get("gpu"):
                report.issues.append(ValidationIssue(
                    "info", fname, "hardware.gpu", "GPU 信息缺失"))

        # software 检查
        sw = data.get("software", {})
        if not isinstance(sw, dict) or not sw:
            report.issues.append(ValidationIssue(
                "warn", fname, "software", "软件环境信息缺失"))
        else:
            if not sw.get("python"):
                report.issues.append(ValidationIssue(
                    "info", fname, "software.python", "Python 版本未指定"))

    # ----------------------------------------------------------
    # figure-style.yaml 校验
    # ----------------------------------------------------------

    def _validate_figure_style(self, report: ValidationReport, auto_fix: bool) -> None:
        path = self.config_dir / "figure-style.yaml"
        fname = "config/figure-style.yaml"
        data = _safe_load_yaml(path)
        if data is None:
            report.issues.append(ValidationIssue(
                "warn", fname, "(root)", "文件不存在或格式错误"))
            return

        # colors.palette
        colors = data.get("colors", {})
        if isinstance(colors, dict):
            palette = colors.get("palette", [])
            if isinstance(palette, list) and len(palette) < 2:
                report.issues.append(ValidationIssue(
                    "warn", fname, "colors.palette",
                    "调色板颜色数量过少，建议至少 3 种"))
            # 校验颜色格式
            for i, c in enumerate(palette if isinstance(palette, list) else []):
                if isinstance(c, str) and not re.match(r"^#[0-9a-fA-F]{6}$", c):
                    report.issues.append(ValidationIssue(
                        "warn", fname, f"colors.palette[{i}]",
                        f"颜色 '{c}' 格式不标准，建议 #RRGGBB"))

        # layout.dpi
        layout = data.get("layout", {})
        if isinstance(layout, dict):
            dpi = layout.get("dpi")
            if dpi is not None and (not isinstance(dpi, (int, float)) or dpi < 72):
                report.issues.append(ValidationIssue(
                    "warn", fname, "layout.dpi",
                    f"DPI 值 {dpi} 过低，建议至少 150"))
            fmt = layout.get("default_format", "")
            if fmt and fmt not in _VALID_FORMATS:
                report.issues.append(ValidationIssue(
                    "warn", fname, "layout.default_format",
                    f"不支持的格式 '{fmt}'，建议 {_VALID_FORMATS}"))

        # 自动补全: 缺少 layout 时补默认值
        if auto_fix and "layout" not in data:
            data["layout"] = {
                "dpi": 300,
                "single_column_width": 3.5,
                "double_column_width": 7.0,
                "default_format": "pdf",
            }
            path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False),
                            encoding="utf-8")
            report.auto_fixed.append(f"{fname}: 自动补全 layout 默认配置")

    # ----------------------------------------------------------
    # style-guide.md 校验
    # ----------------------------------------------------------

    def _validate_style_guide(self, report: ValidationReport) -> None:
        path = self.config_dir / "style-guide.md"
        fname = "config/style-guide.md"
        if not path.exists():
            report.issues.append(ValidationIssue(
                "warn", fname, "(root)", "写作风格指南不存在"))
            return
        content = path.read_text(encoding="utf-8", errors="ignore")
        # 检查是否仍是模板内容
        if len(content.strip()) < 100:
            report.issues.append(ValidationIssue(
                "info", fname, "(content)", "内容过少，建议补充写作规范细节"))

    # ----------------------------------------------------------
    # 交叉校验: glossary ↔ preamble
    # ----------------------------------------------------------

    def _cross_validate_glossary_preamble(self, report: ValidationReport) -> None:
        """检查 glossary.yaml 中的符号宏是否在 preamble.tex 中定义。"""
        glossary = _safe_load_yaml(self.config_dir / "glossary.yaml")
        preamble_path = self.paper_dir / "preamble.tex"

        if not glossary or not preamble_path.exists():
            return

        preamble_text = preamble_path.read_text(encoding="utf-8", errors="ignore")

        symbols = glossary.get("symbols", [])
        if not isinstance(symbols, list):
            return

        for sym in symbols:
            if not isinstance(sym, dict):
                continue
            macro = sym.get("latex_macro", "")
            if not macro:
                continue
            # 去掉反斜杠前缀来搜索 \newcommand{\macro}
            macro_name = macro.lstrip("\\")
            if macro_name and f"\\{macro_name}" not in preamble_text:
                report.issues.append(ValidationIssue(
                    "error", "config/glossary.yaml ↔ paper/preamble.tex",
                    f"symbols.{macro}",
                    f"宏 {macro} 在 glossary.yaml 中定义但未在 preamble.tex 中声明"))

    # ----------------------------------------------------------
    # 交叉校验: references.bib ↔ library.yaml
    # ----------------------------------------------------------

    def _cross_validate_bib_library(self, report: ValidationReport) -> None:
        """检查 references.bib 和 library.yaml 的同步状态。"""
        lib_path = self.refs_dir / "library.yaml"
        bib_path = self.paper_dir / "references.bib"

        lib_data = _safe_load_yaml(lib_path)
        if not lib_data:
            return

        refs = lib_data.get("references", [])
        if not isinstance(refs, list):
            return

        lib_keys = set()
        for ref in refs:
            if isinstance(ref, dict) and ref.get("citekey"):
                lib_keys.add(ref["citekey"])

        if not bib_path.exists():
            if lib_keys:
                report.issues.append(ValidationIssue(
                    "warn", "paper/references.bib",
                    "(file)", f"references.bib 不存在，但 library.yaml 中有 {len(lib_keys)} 条文献"))
            return

        bib_text = bib_path.read_text(encoding="utf-8", errors="ignore")
        bib_keys = set(re.findall(r"@\w+\{(\w+),", bib_text))

        # library.yaml 中有但 bib 中没有
        missing_in_bib = lib_keys - bib_keys
        for key in sorted(missing_in_bib):
            report.issues.append(ValidationIssue(
                "warn", "refs/library.yaml ↔ paper/references.bib",
                key, f"文献 {key} 在 library.yaml 中但不在 references.bib 中，需要 sync"))

        # bib 中有但 library.yaml 中没有
        extra_in_bib = bib_keys - lib_keys
        for key in sorted(extra_in_bib):
            report.issues.append(ValidationIssue(
                "info", "refs/library.yaml ↔ paper/references.bib",
                key, f"文献 {key} 在 references.bib 中但不在 library.yaml 中"))


# ============================================================
# CLI 入口
# ============================================================

def main() -> None:
    import sys

    auto_fix = "--fix" in sys.argv
    validator = ConfigValidator()
    report = validator.validate_all(auto_fix=auto_fix)
    print(report.summary())
    sys.exit(0 if report.is_valid else 1)


if __name__ == "__main__":
    main()
