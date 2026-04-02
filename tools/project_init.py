"""
Paper Agent — 交互式项目初始化工具

核心职责:
1. 扫描 data/ 层，识别文件类型和用途
2. 生成 data/_manifest.yaml
3. 检查所有配置文件的完备性
4. 生成初始化报告

设计原则:
- 此工具提供数据扫描和配置检查能力
- 交互式问答逻辑由 Agent（LLM）驱动，本工具只负责提供信息
- 可中断可恢复：配置状态持久化在 YAML 文件中
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ============================================================
# 常量
# ============================================================

# 项目根目录（相对于本文件所在的 tools/ 目录）
_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent

# 各层路径
DATA_DIR = PROJECT_ROOT / "data"
CONFIG_DIR = PROJECT_ROOT / "config"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
PAPER_DIR = PROJECT_ROOT / "paper"
REFS_DIR = PROJECT_ROOT / "refs"

# 配置文件路径
PAPER_YAML = CONFIG_DIR / "paper.yaml"
GLOSSARY_YAML = CONFIG_DIR / "glossary.yaml"
EXPERIMENT_ENV_YAML = CONFIG_DIR / "experiment-env.yaml"
FIGURE_STYLE_YAML = CONFIG_DIR / "figure-style.yaml"
STYLE_GUIDE_MD = CONFIG_DIR / "style-guide.md"
MANIFEST_YAML = DATA_DIR / "_manifest.yaml"
OUTLINE_MD = PIPELINE_DIR / "notes" / "outline.md"
LIBRARY_YAML = REFS_DIR / "library.yaml"

# 文件类型识别映射
_EXT_TYPE_MAP: dict[str, str] = {
    # 数据文件
    ".csv": "data", ".tsv": "data", ".json": "data", ".jsonl": "data",
    ".hdf5": "data", ".h5": "data", ".parquet": "data", ".npy": "data",
    ".npz": "data", ".pkl": "data", ".pickle": "data", ".xlsx": "data",
    ".xls": "data", ".sqlite": "data", ".db": "data", ".log": "data",
    ".txt": "data",
    # 代码文件
    ".py": "code", ".ipynb": "code", ".r": "code", ".R": "code",
    ".cpp": "code", ".c": "code", ".h": "code", ".hpp": "code",
    ".java": "code", ".sh": "code", ".bash": "code", ".m": "code",
    ".lua": "code", ".jl": "code",
    # 草稿 / 文档
    ".md": "draft", ".tex": "draft", ".docx": "draft", ".doc": "draft",
    ".rst": "draft",
    # 图表
    ".png": "figure", ".jpg": "figure", ".jpeg": "figure",
    ".svg": "figure", ".pdf": "figure", ".eps": "figure",
    ".tif": "figure", ".tiff": "figure",
    # 配置 / 依赖
    ".yaml": "config", ".yml": "config", ".toml": "config",
    ".cfg": "config", ".ini": "config",
}

# paper.yaml 必填字段
_PAPER_REQUIRED_FIELDS = ["title", "venue", "language"]

# 需要跳过的文件名
_SKIP_FILES = {"_manifest.yaml", ".gitkeep", ".DS_Store", "Thumbs.db"}

# 临时文件名模式 (大小写不敏感)
_TEMP_PATTERNS: list[re.Pattern] = [
    re.compile(r"^temp[_-]", re.IGNORECASE),
    re.compile(r"^tmp[_-]", re.IGNORECASE),
    re.compile(r"[_-]temp\.", re.IGNORECASE),
    re.compile(r"[_-]tmp\.", re.IGNORECASE),
    re.compile(r"^debug[_-]", re.IGNORECASE),
    re.compile(r"^test[_-]output", re.IGNORECASE),
    re.compile(r"checkpoint", re.IGNORECASE),
    re.compile(r"\.bak$", re.IGNORECASE),
    re.compile(r"~$"),
    re.compile(r"^\.", re.IGNORECASE),         # 隐藏文件
    re.compile(r"copy\s*\(\d+\)", re.IGNORECASE),  # Windows 副本
    re.compile(r"_old\.", re.IGNORECASE),
    re.compile(r"_backup\.", re.IGNORECASE),
]

# Python 代码用途分类关键词
_PY_PURPOSE_PATTERNS: dict[str, re.Pattern] = {
    "training": re.compile(
        r"model\.train\(|optimizer\.step|loss\.backward|fit\("
        r"|training.loop|train_epoch|Trainer\(",
        re.IGNORECASE,
    ),
    "evaluation": re.compile(
        r"model\.eval\(|evaluate|accuracy_score|f1_score"
        r"|classification_report|confusion_matrix|@torch\.no_grad",
        re.IGNORECASE,
    ),
    "preprocessing": re.compile(
        r"read_csv|load_data|preprocess|clean_data|tokeniz"
        r"|transform|normalize|DataLoader\(",
        re.IGNORECASE,
    ),
    "visualization": re.compile(
        r"import\s+matplotlib|from\s+matplotlib|import\s+seaborn"
        r"|plt\.show|plt\.savefig|plt\.figure|sns\.",
        re.IGNORECASE,
    ),
    "utility": re.compile(
        r"argparse|click\.command|def\s+main\(|if\s+__name__",
        re.IGNORECASE,
    ),
}

# PDF 文献特征
_PDF_PAPER_INDICATORS = re.compile(
    r"abstract|references|bibliography|introduction|related\s*work"
    r"|conclusion|acknowledgment|arxiv|doi",
    re.IGNORECASE,
)

# 建议目标位置映射
_SUGGESTED_LOCATIONS: dict[str, str] = {
    "data": "data/raw/",
    "code": "data/code/",
    "draft": "data/drafts/",
    "figure": "pipeline/figures/",
    "config": "data/",
    "reference": "refs/pdfs/",
    "other": "data/",
}


# ============================================================
# 数据类
# ============================================================

@dataclass
class FileInfo:
    """data/ 下单个文件的扫描信息。"""
    path: str                   # 相对于 data/ 的路径
    abs_path: str               # 绝对路径
    type: str                   # data | code | draft | figure | config | reference | other
    size_bytes: int             # 文件大小
    extension: str              # 文件扩展名
    purpose: str = ""           # 智能推断的用途 (training/visualization/preprocessing 等)
    content_hint: str = ""      # 内容摘要 (CSV 表头 / PDF 类型 / 代码主题)
    suggested_location: str = ""  # 建议的项目目标位置
    is_temporary: bool = False  # 是否为临时/调试文件

    def to_manifest_entry(self) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "path": self.path,
            "type": self.type,
            "description": "",  # 待 Agent 或用户填充
        }
        if self.purpose:
            entry["purpose"] = self.purpose
        if self.content_hint:
            entry["content_hint"] = self.content_hint
        if self.suggested_location:
            entry["suggested_location"] = self.suggested_location
        if self.is_temporary:
            entry["is_temporary"] = True
        return entry


@dataclass
class ScanResult:
    """data/ 层扫描结果。"""
    files: list[FileInfo] = field(default_factory=list)
    total_count: int = 0
    type_counts: dict[str, int] = field(default_factory=dict)
    detected_frameworks: list[str] = field(default_factory=list)
    has_requirements: bool = False
    requirements_path: str | None = None

    @property
    def temporary_files(self) -> list[FileInfo]:
        return [f for f in self.files if f.is_temporary]

    @property
    def reference_files(self) -> list[FileInfo]:
        return [f for f in self.files if f.type == "reference"]

    def summary(self) -> str:
        lines = [f"扫描完成: 共发现 {self.total_count} 个文件"]
        for ftype, count in sorted(self.type_counts.items()):
            lines.append(f"  - {ftype}: {count} 个")
        if self.detected_frameworks:
            lines.append(f"  - 检测到框架: {', '.join(self.detected_frameworks)}")
        if self.has_requirements:
            lines.append(f"  - 依赖文件: {self.requirements_path}")
        temp = self.temporary_files
        if temp:
            lines.append(f"  - ⚠ 疑似临时文件: {len(temp)} 个")
        refs = self.reference_files
        if refs:
            lines.append(f"  - 📄 检测到参考文献: {len(refs)} 个")
        return "\n".join(lines)


@dataclass
class CompletenessItem:
    """单个配置文件的完备性检查结果。"""
    file: str                        # 相对于项目根目录的路径
    is_complete: bool
    missing_fields: list[str] = field(default_factory=list)
    suggested_question: str = ""


@dataclass
class CompletenessReport:
    """所有配置的完备性检查结果。"""
    items: list[CompletenessItem] = field(default_factory=list)

    @property
    def complete_files(self) -> list[str]:
        return [item.file for item in self.items if item.is_complete]

    @property
    def incomplete_files(self) -> list[str]:
        return [item.file for item in self.items if not item.is_complete]

    @property
    def overall_readiness(self) -> float:
        if not self.items:
            return 0.0
        return len(self.complete_files) / len(self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete_files,
            "incomplete": [
                {
                    "file": item.file,
                    "missing": item.missing_fields,
                    "suggested_question": item.suggested_question,
                }
                for item in self.items
                if not item.is_complete
            ],
            "overall_readiness": round(self.overall_readiness, 2),
        }

    def summary(self) -> str:
        lines = [f"配置完备性: {self.overall_readiness:.0%}"]
        for item in self.items:
            if item.is_complete:
                lines.append(f"  ✓ {item.file}")
            else:
                lines.append(f"  ✗ {item.file}")
                for mf in item.missing_fields:
                    lines.append(f"      缺失: {mf}")
        return "\n".join(lines)


# ============================================================
# 核心类
# ============================================================

class ProjectInitializer:
    """交互式项目初始化工具。

    负责:
    - 扫描 data/ 层文件
    - 生成 / 更新 _manifest.yaml
    - 检查所有配置文件完备性
    - 生成初始化摘要报告

    交互逻辑（问答）由调用方（Agent / LLM）驱动。
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.data_dir = self.root / "data"
        self.config_dir = self.root / "config"
        self.pipeline_dir = self.root / "pipeline"
        self.paper_dir = self.root / "paper"
        self.refs_dir = self.root / "refs"

    # ----------------------------------------------------------
    # 1. 数据层扫描
    # ----------------------------------------------------------

    def scan_data_layer(self) -> ScanResult:
        """扫描 data/ 下所有文件，推断类型和用途。"""
        result = ScanResult()

        if not self.data_dir.exists():
            return result

        for root, _dirs, files in os.walk(self.data_dir):
            for fname in files:
                if fname in _SKIP_FILES:
                    continue
                abs_path = Path(root) / fname
                rel_path = str(abs_path.relative_to(self.data_dir)).replace("\\", "/")
                ext = abs_path.suffix.lower()
                ftype = _EXT_TYPE_MAP.get(ext, "other")

                info = FileInfo(
                    path=rel_path,
                    abs_path=str(abs_path),
                    type=ftype,
                    size_bytes=abs_path.stat().st_size,
                    extension=ext,
                )

                # 临时文件检测
                info.is_temporary = self._is_temporary(fname)

                # 内容级智能分类
                self._enrich_file_info(info)

                # 建议目标位置
                info.suggested_location = _SUGGESTED_LOCATIONS.get(info.type, "data/")

                result.files.append(info)

                # 检测依赖文件
                if fname.lower() in ("requirements.txt", "environment.yml",
                                     "pyproject.toml", "setup.py", "setup.cfg"):
                    result.has_requirements = True
                    result.requirements_path = rel_path

        result.total_count = len(result.files)
        result.type_counts = {}
        for f in result.files:
            result.type_counts[f.type] = result.type_counts.get(f.type, 0) + 1

        # 尝试检测框架
        result.detected_frameworks = self._detect_frameworks(result.files)

        return result

    def _detect_frameworks(self, files: list[FileInfo]) -> list[str]:
        """通过文件内容中的 import 语句推断使用的框架。"""
        frameworks: set[str] = set()
        patterns = {
            "pytorch": re.compile(r"import\s+torch|from\s+torch"),
            "tensorflow": re.compile(r"import\s+tensorflow|from\s+tensorflow"),
            "jax": re.compile(r"import\s+jax|from\s+jax"),
            "sklearn": re.compile(r"import\s+sklearn|from\s+sklearn"),
            "transformers": re.compile(r"from\s+transformers|import\s+transformers"),
            "numpy": re.compile(r"import\s+numpy|from\s+numpy"),
            "pandas": re.compile(r"import\s+pandas|from\s+pandas"),
        }

        for f in files:
            if f.type != "code" or f.extension not in (".py", ".ipynb"):
                continue
            try:
                content = Path(f.abs_path).read_text(encoding="utf-8", errors="ignore")
                # 对 notebook，只读前 50KB 减少开销
                if f.extension == ".ipynb":
                    content = content[:50_000]
                for name, pat in patterns.items():
                    if pat.search(content):
                        frameworks.add(name)
            except OSError:
                continue

        return sorted(frameworks)

    @staticmethod
    def _is_temporary(filename: str) -> bool:
        """判断文件名是否匹配临时文件模式。"""
        for pat in _TEMP_PATTERNS:
            if pat.search(filename):
                return True
        return False

    def _enrich_file_info(self, info: FileInfo) -> None:
        """基于文件内容增强分类信息。

        对不同文件类型做针对性内容嗅探:
        - PDF: 区分参考文献 vs 图表
        - Python: 推断用途 (训练/可视化/预处理/评估/工具)
        - CSV/TSV: 读取表头作为 content_hint
        - .tex: 检测是否为完整文档（草稿）
        """
        try:
            if info.extension == ".pdf":
                self._sniff_pdf(info)
            elif info.extension in (".py", ".ipynb"):
                self._sniff_python(info)
            elif info.extension in (".csv", ".tsv"):
                self._sniff_csv(info)
            elif info.extension == ".tex":
                self._sniff_tex(info)
            elif info.extension in (".log",):
                info.is_temporary = True
                info.purpose = "log"
                info.content_hint = "日志文件"
        except OSError:
            pass

    def _sniff_pdf(self, info: FileInfo) -> None:
        """区分 PDF 是参考文献还是图表。

        读取前 4KB 文本内容，搜索学术论文关键词。
        """
        try:
            with open(info.abs_path, "rb") as fp:
                head = fp.read(4096)
            text = head.decode("latin-1", errors="ignore")
            if _PDF_PAPER_INDICATORS.search(text):
                info.type = "reference"
                info.purpose = "参考文献"
                info.content_hint = "PDF 学术论文"
                info.suggested_location = "refs/pdfs/"
            else:
                # 保持 figure 类型，尝试从文件名判断
                fname_lower = Path(info.path).stem.lower()
                if any(kw in fname_lower for kw in
                       ("fig", "plot", "chart", "graph", "diagram",
                        "curve", "result", "comparison", "architecture")):
                    info.purpose = "图表"
                    info.content_hint = "PDF 图表"
                else:
                    info.content_hint = "PDF 文件 (内容不明)"
        except OSError:
            pass

    def _sniff_python(self, info: FileInfo) -> None:
        """推断 Python 文件的用途。"""
        try:
            content = Path(info.abs_path).read_text(
                encoding="utf-8", errors="ignore"
            )
            if info.extension == ".ipynb":
                content = content[:50_000]

            purposes: list[str] = []
            for purpose, pat in _PY_PURPOSE_PATTERNS.items():
                if pat.search(content):
                    purposes.append(purpose)

            if purposes:
                info.purpose = purposes[0]  # 优先级: 按字典顺序先匹配的
                info.content_hint = f"Python ({', '.join(purposes)})"
            else:
                info.content_hint = "Python 脚本"
        except OSError:
            pass

    def _sniff_csv(self, info: FileInfo) -> None:
        """读取 CSV/TSV 的表头和行数摘要。"""
        try:
            with open(info.abs_path, encoding="utf-8", errors="ignore") as fp:
                first_line = fp.readline().strip()
                # 计算行数 (最多读 10 万行避免超大文件)
                line_count = 1
                for line_count, _ in enumerate(fp, start=2):  # noqa: B007
                    if line_count > 100_000:
                        break

            sep = "\t" if info.extension == ".tsv" else ","
            columns = [c.strip().strip('"\'') for c in first_line.split(sep)]
            col_preview = ", ".join(columns[:8])
            if len(columns) > 8:
                col_preview += f" ... (+{len(columns) - 8})"
            info.content_hint = f"列: [{col_preview}], ~{line_count} 行"
            info.purpose = "数据表"
        except OSError:
            pass

    def _sniff_tex(self, info: FileInfo) -> None:
        """检测 .tex 文件是完整论文草稿还是片段。"""
        try:
            content = Path(info.abs_path).read_text(
                encoding="utf-8", errors="ignore"
            )[:8192]
            if r"\documentclass" in content:
                info.purpose = "完整草稿"
                info.content_hint = "LaTeX 完整文档"
            elif r"\section" in content or r"\subsection" in content:
                info.purpose = "章节片段"
                info.content_hint = "LaTeX 章节片段"
            else:
                info.content_hint = "LaTeX 文件"
        except OSError:
            pass

    # ----------------------------------------------------------
    # 2. Manifest 管理
    # ----------------------------------------------------------

    def generate_manifest(self, scan_result: ScanResult) -> dict[str, Any]:
        """从扫描结果生成 _manifest.yaml 内容。

        保留已有描述：如果 _manifest.yaml 中已有该文件的条目且有描述，
        则保留原有描述。同样保留已有的 purpose 等手动编辑。
        """
        existing = self._load_existing_manifest()

        entries = []
        for f in scan_result.files:
            entry = f.to_manifest_entry()
            # 保留已有描述和手动设定的字段
            if f.path in existing:
                old = existing[f.path]
                if old.get("description"):
                    entry["description"] = old["description"]
                # 保留用户手动设定的 purpose（优先于自动推断）
                if old.get("purpose") and not entry.get("purpose"):
                    entry["purpose"] = old["purpose"]
            entries.append(entry)

        manifest = {"files": entries}
        return manifest

    def save_manifest(self, manifest: dict[str, Any]) -> Path:
        """将 manifest 写入 data/_manifest.yaml。"""
        out_path = self.data_dir / "_manifest.yaml"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fp:
            yaml.dump(manifest, fp, default_flow_style=False,
                      allow_unicode=True, sort_keys=False)
        return out_path

    def _load_existing_manifest(self) -> dict[str, dict]:
        """加载现有 manifest，以 path 为键索引。"""
        manifest_path = self.data_dir / "_manifest.yaml"
        if not manifest_path.exists():
            return {}
        try:
            with open(manifest_path, encoding="utf-8") as fp:
                data = yaml.safe_load(fp) or {}
            return {entry["path"]: entry for entry in data.get("files", [])}
        except (yaml.YAMLError, KeyError, TypeError):
            return {}

    # ----------------------------------------------------------
    # 3. 配置完备性检查
    # ----------------------------------------------------------

    def check_completeness(self) -> CompletenessReport:
        """检查所有配置文件的完备性。"""
        report = CompletenessReport()

        report.items.append(self._check_paper_yaml())
        report.items.append(self._check_glossary_yaml())
        report.items.append(self._check_experiment_env())
        report.items.append(self._check_figure_style())
        report.items.append(self._check_style_guide())
        report.items.append(self._check_outline())

        return report

    def _check_paper_yaml(self) -> CompletenessItem:
        path = self.config_dir / "paper.yaml"
        item = CompletenessItem(file="config/paper.yaml", is_complete=True)

        data = self._safe_load_yaml(path)
        if data is None:
            item.is_complete = False
            item.missing_fields = ["文件不存在"]
            item.suggested_question = "请提供论文标题、投稿目标和作者信息"
            return item

        missing = []
        if not data.get("title"):
            missing.append("title (论文标题)")
        if not data.get("venue"):
            missing.append("venue (投稿目标)")
        if not data.get("authors"):
            missing.append("authors (作者信息)")

        if missing:
            item.is_complete = False
            item.missing_fields = missing
            item.suggested_question = "请提供: " + "、".join(missing)

        return item

    def _check_glossary_yaml(self) -> CompletenessItem:
        path = self.config_dir / "glossary.yaml"
        item = CompletenessItem(file="config/glossary.yaml", is_complete=True)

        data = self._safe_load_yaml(path)
        if data is None:
            item.is_complete = False
            item.missing_fields = ["文件不存在"]
            item.suggested_question = "是否需要定义初始术语表和数学符号？"
            return item

        terms = data.get("terms") or []
        symbols = data.get("symbols") or []
        if not terms and not symbols:
            item.is_complete = False
            item.missing_fields = ["terms (术语列表为空)", "symbols (符号列表为空)"]
            item.suggested_question = "请提供论文中的核心术语和数学符号，以便保持全文一致性"

        return item

    def _check_experiment_env(self) -> CompletenessItem:
        path = self.config_dir / "experiment-env.yaml"
        item = CompletenessItem(file="config/experiment-env.yaml", is_complete=True)

        data = self._safe_load_yaml(path)
        if data is None:
            item.is_complete = False
            item.missing_fields = ["文件不存在"]
            item.suggested_question = "请提供实验的硬件环境和软件版本信息"
            return item

        missing = []
        hw = data.get("hardware") or {}
        if not hw.get("gpu"):
            missing.append("hardware.gpu (GPU 型号)")
        sw = data.get("software") or {}
        if not sw.get("python"):
            missing.append("software.python (Python 版本)")

        if missing:
            item.is_complete = False
            item.missing_fields = missing
            item.suggested_question = "请提供: " + "、".join(missing)

        return item

    def _check_figure_style(self) -> CompletenessItem:
        path = self.config_dir / "figure-style.yaml"
        item = CompletenessItem(file="config/figure-style.yaml", is_complete=True)

        data = self._safe_load_yaml(path)
        if data is None:
            item.is_complete = False
            item.missing_fields = ["文件不存在"]
            item.suggested_question = "是否有已有的图表风格需要继承？"
            return item

        source = data.get("source_style") or {}
        if not source.get("inherited_from") and not source.get("analysis_notes"):
            item.is_complete = False
            item.missing_fields = ["source_style (未分析用户图表风格)"]
            item.suggested_question = "是否有已有的图表需要继承其视觉风格？"

        return item

    def _check_style_guide(self) -> CompletenessItem:
        path = self.config_dir / "style-guide.md"
        item = CompletenessItem(file="config/style-guide.md", is_complete=True)

        if not path.exists():
            item.is_complete = False
            item.missing_fields = ["文件不存在"]
            item.suggested_question = "是否有特殊的写作风格偏好？"
            return item

        content = path.read_text(encoding="utf-8")
        # 只要文件非空且超过模板长度即视为已填充
        if len(content.strip()) < 100:
            item.is_complete = False
            item.missing_fields = ["内容过少"]
            item.suggested_question = "写作风格指南内容不足，是否需要补充？"

        return item

    def _check_outline(self) -> CompletenessItem:
        path = self.pipeline_dir / "notes" / "outline.md"
        item = CompletenessItem(file="pipeline/notes/outline.md", is_complete=True)

        if not path.exists():
            item.is_complete = False
            item.missing_fields = ["文件不存在"]
            item.suggested_question = "请提供论文大致的章节结构，或让 Agent 根据研究方向建议"
            return item

        content = path.read_text(encoding="utf-8")
        # 检查是否只有模板注释，没有实际内容
        uncommented = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
        uncommented = re.sub(r"^>.*$", "", uncommented, flags=re.MULTILINE)
        uncommented = re.sub(r"^#.*$", "", uncommented, flags=re.MULTILINE)
        uncommented = re.sub(r"^-+$", "", uncommented, flags=re.MULTILINE)
        if len(uncommented.strip()) < 20:
            item.is_complete = False
            item.missing_fields = ["大纲内容为空（仅有模板）"]
            item.suggested_question = "请提供论文大致的章节结构，或让 Agent 根据研究方向建议"

        return item

    # ----------------------------------------------------------
    # 4. 报告生成
    # ----------------------------------------------------------

    def generate_init_report(self, scan_result: ScanResult,
                             completeness: CompletenessReport) -> str:
        """生成初始化摘要报告。"""
        lines = [
            "=" * 56,
            "  Paper Agent — 项目初始化报告",
            "=" * 56,
            "",
            "## 数据层",
            scan_result.summary(),
            "",
        ]

        # 文件详情（按类型分组）
        if scan_result.files:
            lines.append("## 文件详情")
            by_type: dict[str, list[FileInfo]] = {}
            for f in scan_result.files:
                by_type.setdefault(f.type, []).append(f)
            for ftype in sorted(by_type.keys()):
                lines.append(f"  [{ftype}]")
                for f in by_type[ftype]:
                    marks: list[str] = []
                    if f.is_temporary:
                        marks.append("⚠临时")
                    if f.purpose:
                        marks.append(f.purpose)
                    mark_str = f" ({', '.join(marks)})" if marks else ""
                    hint_str = f"  → {f.content_hint}" if f.content_hint else ""
                    lines.append(f"    {f.path}{mark_str}{hint_str}")
            lines.append("")

        # 重组建议
        needs_reorg: list[FileInfo] = [
            f for f in scan_result.files if f.suggested_location
        ]
        if needs_reorg:
            lines.append("## 整理建议")
            for f in needs_reorg:
                # 只有当文件不在建议位置时才提示
                current_prefix = f.path.split("/")[0] + "/" if "/" in f.path else ""
                suggested = f.suggested_location
                if not f.path.startswith(suggested.rstrip("/")):
                    lines.append(f"    {f.path} → {suggested}")
            lines.append("")

        lines.append("## 配置完备性")
        lines.append(completeness.summary())
        lines.append("")

        # 建议下一步
        lines.append("## 建议下一步")
        if completeness.incomplete_files:
            lines.append("  - 补充缺失的配置项（执行 `检查配置`）")
        if not self._outline_has_content():
            lines.append("  - 撰写论文大纲（执行 `写大纲`）")
        if scan_result.type_counts.get("data", 0) > 0:
            data_files = [f.path for f in scan_result.files if f.type == "data"]
            if data_files:
                lines.append(f"  - 分析数据（执行 `分析 {data_files[0]}`）")
        temp = scan_result.temporary_files
        if temp:
            lines.append(f"  - ⚠ 发现 {len(temp)} 个疑似临时文件，建议确认是否需要保留")
        refs = scan_result.reference_files
        if refs:
            lines.append(f"  - 发现 {len(refs)} 个参考文献 PDF，建议移至 refs/pdfs/")
        lines.append("")
        lines.append("=" * 56)

        return "\n".join(lines)

    def _outline_has_content(self) -> bool:
        path = self.pipeline_dir / "notes" / "outline.md"
        if not path.exists():
            return False
        content = path.read_text(encoding="utf-8")
        uncommented = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
        return len(uncommented.strip()) > 50

    # ----------------------------------------------------------
    # 5. 工具函数
    # ----------------------------------------------------------

    @staticmethod
    def _safe_load_yaml(path: Path) -> dict | None:
        """安全加载 YAML 文件，失败返回 None。"""
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as fp:
                return yaml.safe_load(fp) or {}
        except yaml.YAMLError:
            return None

    def parse_requirements(self) -> list[dict[str, str]]:
        """解析 requirements.txt，提取库名和版本。"""
        req_path = self.data_dir / "code" / "requirements.txt"
        if not req_path.exists():
            # 尝试在 data/ 根目录查找
            for candidate in self.data_dir.rglob("requirements.txt"):
                req_path = candidate
                break
            else:
                return []

        libraries = []
        try:
            content = req_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                # 解析 package==version 或 package>=version 等
                match = re.match(r"^([a-zA-Z0-9_-]+)\s*([><=!~]+\s*[\d.]+)?", line)
                if match:
                    name = match.group(1)
                    version = match.group(2) or ""
                    version = re.sub(r"^[><=!~]+\s*", "", version).strip()
                    libraries.append({"name": name, "version": version})
        except OSError:
            pass

        return libraries


# ============================================================
# CLI 入口（便于调试）
# ============================================================

def main():
    """命令行入口，用于独立测试。"""
    init = ProjectInitializer()

    print("--- 扫描数据层 ---")
    scan = init.scan_data_layer()
    print(scan.summary())

    print("\n--- 生成 Manifest ---")
    manifest = init.generate_manifest(scan)
    saved_path = init.save_manifest(manifest)
    print(f"已保存: {saved_path}")

    print("\n--- 配置完备性检查 ---")
    report = init.check_completeness()
    print(report.summary())

    print("\n--- 初始化报告 ---")
    full_report = init.generate_init_report(scan, report)
    print(full_report)


if __name__ == "__main__":
    main()
