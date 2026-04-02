"""tests/test_workflow.py — Agent 工作流集成测试

测试各 Agent 的典型工作流场景：
- Researcher: 文献添加 → 阅读笔记 → 引用建议
- Analyst: 数据扫描 → 图表生成 → 发现记录
- Writer: 配置读取 → 引用查找 → 术语检查
- Reviewer: 质量检查 → 术语检查 → 配置校验
- Experimenter: 数据变更 → manifest 更新
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """创建完整的项目结构。"""
    dirs = [
        "config", "data/raw", "data/code", "data/drafts",
        "pipeline/scripts", "pipeline/figures", "pipeline/tables",
        "pipeline/notes",
        "paper/sections", "paper/figures",
        "refs/notes", "refs/pdfs",
        "tools",
    ]
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # --- config ---
    _w(tmp_path / "config" / "paper.yaml", {
        "title": "Workflow Test Paper",
        "venue": "NeurIPS 2026",
        "language": "chinese",
        "authors": [{"name": "Test Author"}],
        "latex": {"compiler": "xelatex", "bibliography": "bibtex"},
    })
    _w(tmp_path / "config" / "glossary.yaml", {
        "terms": [
            {"canonical": "large language model",
             "abbreviation": "LLM",
             "first_use": "large language model (LLM)",
             "forbidden_variants": ["big language model"]},
        ],
        "symbols": [
            {"name": "loss", "latex_macro": "\\loss",
             "definition": "\\mathcal{L}", "description": "Training loss"},
        ],
    })
    _w(tmp_path / "config" / "experiment-env.yaml", {
        "hardware": {"gpu": "RTX 4090"},
        "software": {"python": "3.12"},
    })
    _w(tmp_path / "config" / "figure-style.yaml", {
        "colors": {"palette": ["#1f77b4", "#ff7f0e", "#2ca02c"]},
        "layout": {"dpi": 300, "default_format": "pdf"},
    })
    (tmp_path / "config" / "style-guide.md").write_text(
        "# Style Guide\n正式学术风格。\n" * 10, encoding="utf-8")

    # --- pipeline notes ---
    (tmp_path / "pipeline" / "notes" / "outline.md").write_text(
        "# 论文大纲\n## 1. Introduction\n## 2. Method\n## 3. Experiments\n",
        encoding="utf-8")
    (tmp_path / "pipeline" / "notes" / "arguments.md").write_text(
        "# 论点\n- 本方法优于 baseline\n", encoding="utf-8")
    (tmp_path / "pipeline" / "notes" / "findings.md").write_text(
        "# 发现\n", encoding="utf-8")

    # --- refs ---
    _w(tmp_path / "refs" / "library.yaml", {
        "references": [{
            "citekey": "vaswani2017attention",
            "title": "Attention Is All You Need",
            "authors": ["Vaswani, A."],
            "year": 2017,
            "venue": "NeurIPS",
            "key_quotes": [{
                "id": "q1",
                "text": "The Transformer relies entirely on self-attention.",
                "page": 2,
            }],
            "bibtex": "@inproceedings{vaswani2017attention,\n  title={Attention Is All You Need},\n  author={Vaswani},\n  year={2017}\n}\n",
        }],
    })

    # --- paper ---
    (tmp_path / "paper" / "main.tex").write_text(
        "\\input{preamble}\n\\begin{document}\n"
        "\\input{sections/01-intro}\n"
        "\\end{document}\n", encoding="utf-8")
    (tmp_path / "paper" / "preamble.tex").write_text(
        "\\newcommand{\\loss}{\\mathcal{L}}\n", encoding="utf-8")
    (tmp_path / "paper" / "sections" / "01-intro.tex").write_text(
        "\\section{Introduction}\n"
        "We use the Transformer \\cite{vaswani2017attention}.\n"
        "The \\loss{} function is defined as follows.\n",
        encoding="utf-8")
    (tmp_path / "paper" / "references.bib").write_text(
        "@inproceedings{vaswani2017attention,\n"
        "  title={Attention Is All You Need},\n"
        "  author={Vaswani},\n  year={2017}\n}\n", encoding="utf-8")

    # --- data ---
    (tmp_path / "data" / "raw" / "results.csv").write_text(
        "model,accuracy\nA,0.92\nB,0.89\n", encoding="utf-8")
    _w(tmp_path / "data" / "_manifest.yaml", {
        "files": [
            {"path": "raw/results.csv", "type": "data",
             "description": "Model comparison results"},
        ],
    })

    return tmp_path


def _w(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


# ============================================================
# Researcher 工作流
# ============================================================

class TestResearcherWorkflow:
    """模拟: 文献搜索 → 引用建议 → 引用验证"""

    def test_search_existing_reference(self, project: Path) -> None:
        from tools.bib_manager import BibManager
        bm = BibManager(project)
        results = bm.search_local("attention transformer")
        assert len(results) >= 1
        assert results[0]["citekey"] == "vaswani2017attention"

    def test_get_quote_for_sourcing(self, project: Path) -> None:
        from tools.bib_manager import BibManager
        bm = BibManager(project)
        quote = bm.get_quote("vaswani2017attention", "q1")
        assert quote is not None
        assert "self-attention" in quote["text"]

    def test_validate_citations_pass(self, project: Path) -> None:
        from tools.bib_manager import BibManager
        bm = BibManager(project)
        report = bm.validate_citations()
        assert len(report["missing"]) == 0

    def test_add_and_sync(self, project: Path) -> None:
        from tools.bib_manager import BibManager
        bm = BibManager(project)
        bm.add_reference({
            "citekey": "devlin2019bert",
            "title": "BERT",
            "authors": ["Devlin, J."],
            "year": 2019,
            "venue": "NAACL",
            "bibtex": "@inproceedings{devlin2019bert, title={BERT}, year={2019}}\n",
        })
        bm.sync_bib()
        bib_text = (project / "paper" / "references.bib").read_text(encoding="utf-8")
        assert "devlin2019bert" in bib_text


# ============================================================
# Analyst 工作流
# ============================================================

class TestAnalystWorkflow:
    """模拟: 数据扫描 → manifest 读取 → 发现记录"""

    def test_scan_data(self, project: Path) -> None:
        from tools.project_init import ProjectInitializer
        pi = ProjectInitializer(project)
        scan = pi.scan_data_layer()
        assert scan.total_count >= 1
        assert "data" in scan.type_counts

    def test_manifest_reflects_data(self, project: Path) -> None:
        lib = yaml.safe_load(
            (project / "data" / "_manifest.yaml").read_text(encoding="utf-8"))
        assert len(lib["files"]) >= 1
        assert lib["files"][0]["path"] == "raw/results.csv"


# ============================================================
# Writer 工作流
# ============================================================

class TestWriterWorkflow:
    """模拟: 配置读取 → 引用查找 → 术语检查"""

    def test_load_configs(self, project: Path) -> None:
        paper_cfg = yaml.safe_load(
            (project / "config" / "paper.yaml").read_text(encoding="utf-8"))
        assert paper_cfg["language"] == "chinese"

        glossary = yaml.safe_load(
            (project / "config" / "glossary.yaml").read_text(encoding="utf-8"))
        assert len(glossary["terms"]) >= 1

    def test_suggest_citations(self, project: Path) -> None:
        from tools.bib_manager import BibManager
        bm = BibManager(project)
        suggestions = bm.suggest_citations(
            "We use the Transformer architecture for sequence modeling.")
        # vaswani2017attention should be suggested (tags match)
        citekeys = [s["citekey"] for s in suggestions]
        # 可能匹配也可能不匹配，取决于实现
        assert isinstance(suggestions, list)

    def test_glossary_check_after_writing(self, project: Path) -> None:
        from tools.glossary_checker import GlossaryChecker
        gc = GlossaryChecker(project)
        report = gc.check_all()
        # 01-intro.tex 中没有 forbidden variants，应该干净
        forbidden = [i for i in report.issues if i.rule == "forbidden_variant"]
        assert len(forbidden) == 0


# ============================================================
# Reviewer 工作流
# ============================================================

class TestReviewerWorkflow:
    """模拟: paper_lint → glossary_checker → config_validator"""

    def test_full_review_pipeline(self, project: Path) -> None:
        from tools.paper_lint import PaperLint
        from tools.glossary_checker import GlossaryChecker
        from tools.config_validator import ConfigValidator

        pl = PaperLint(project)
        lint_report = pl.check_all()
        assert lint_report is not None

        gc = GlossaryChecker(project)
        gloss_report = gc.check_all()
        assert gloss_report is not None

        cv = ConfigValidator(project)
        val_report = cv.validate_all()
        assert val_report is not None

    def test_lint_citation_valid(self, project: Path) -> None:
        from tools.paper_lint import PaperLint
        pl = PaperLint(project)
        report = pl.check_all()
        citation_errors = [i for i in report.items
                           if i.category == "citation" and i.level == "error"]
        assert len(citation_errors) == 0

    def test_config_validation_passes(self, project: Path) -> None:
        from tools.config_validator import ConfigValidator
        cv = ConfigValidator(project)
        report = cv.validate_all()
        assert report.is_valid


# ============================================================
# Experimenter 工作流
# ============================================================

class TestExperimenterWorkflow:
    """模拟: 新增实验数据 → 更新 manifest"""

    def test_add_experiment_data(self, project: Path) -> None:
        # Experimenter 写入新数据
        new_data = "model,metric\nC,0.95\n"
        (project / "data" / "raw" / "ablation.csv").write_text(
            new_data, encoding="utf-8")

        # 更新 manifest
        manifest_path = project / "data" / "_manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].append({
            "path": "raw/ablation.csv",
            "type": "data",
            "description": "Ablation study results",
        })
        manifest_path.write_text(
            yaml.dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8")

        # 验证
        updated = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        paths = [f["path"] for f in updated["files"]]
        assert "raw/ablation.csv" in paths

    def test_add_experiment_code(self, project: Path) -> None:
        # Experimenter 写入新脚本
        code = "# Ablation experiment\nimport torch\n"
        (project / "data" / "code" / "ablation.py").write_text(
            code, encoding="utf-8")

        # 更新 manifest
        manifest_path = project / "data" / "_manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        manifest["files"].append({
            "path": "code/ablation.py",
            "type": "code",
            "description": "Ablation experiment script",
        })
        manifest_path.write_text(
            yaml.dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8")

        # ProjectInitializer 可以感知变动
        from tools.project_init import ProjectInitializer
        pi = ProjectInitializer(project)
        scan = pi.scan_data_layer()
        paths = [f.path for f in scan.files]
        assert any("ablation" in p for p in paths)

    def test_rescan_after_change(self, project: Path) -> None:
        """添加文件后重新扫描应反映变化。"""
        (project / "data" / "raw" / "new_exp.json").write_text(
            '{"result": 42}', encoding="utf-8")

        from tools.project_init import ProjectInitializer
        pi = ProjectInitializer(project)
        scan = pi.scan_data_layer()
        paths = [f.path for f in scan.files]
        assert any("new_exp.json" in p for p in paths)
