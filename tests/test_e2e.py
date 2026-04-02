"""tests/test_e2e.py — 端到端集成测试

完整场景: 从原始数据 → 初始化 → 文献管理 → 术语检查 → 质量检查 → 配置校验 → 命令调度。
验证所有工具在完整项目结构中协同工作。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


# ============================================================
# Fixture: 完整项目
# ============================================================

@pytest.fixture()
def full_project(tmp_path: Path) -> Path:
    """创建一个内容完整的模拟项目，模拟真实使用场景。"""
    dirs = [
        "config", "data/raw", "data/code", "data/drafts",
        "pipeline/scripts", "pipeline/figures", "pipeline/tables",
        "pipeline/notes",
        "paper/sections", "paper/figures",
        "refs/notes", "refs/pdfs",
    ]
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # === 数据层 (Layer 0) ===
    (tmp_path / "data" / "raw" / "results.csv").write_text(
        "model,accuracy,f1\nBERT,0.91,0.89\nGPT,0.93,0.91\nOurs,0.96,0.95\n",
        encoding="utf-8")
    (tmp_path / "data" / "code" / "train.py").write_text(
        "import torch\nmodel = torch.nn.Linear(768, 10)\n", encoding="utf-8")
    (tmp_path / "data" / "drafts" / "old_intro.md").write_text(
        "# Old Introduction Draft\nSome rough thoughts...\n", encoding="utf-8")

    # === 配置层 ===
    _w(tmp_path / "config" / "paper.yaml", {
        "title": "An Improved Transformer for Text Classification",
        "venue": "ACL 2026",
        "language": "chinese",
        "authors": [
            {"name": "张三", "affiliation": "北京大学", "email": "zhang@pku.edu.cn"},
        ],
        "page_limit": 8,
        "style": {
            "tone": "formal-academic",
            "person": "first-plural",
        },
        "latex": {
            "compiler": "xelatex",
            "bibliography": "bibtex",
        },
    })
    _w(tmp_path / "config" / "glossary.yaml", {
        "terms": [
            {
                "canonical": "large language model",
                "abbreviation": "LLM",
                "first_use": "large language model (LLM)",
                "forbidden_variants": ["big language model", "large-scale language model"],
            },
            {
                "canonical": "fine-tuning",
                "forbidden_variants": ["finetuning", "fine tuning"],
            },
        ],
        "symbols": [
            {"name": "loss", "latex_macro": "\\loss",
             "definition": "\\mathcal{L}", "description": "Training loss"},
            {"name": "params", "latex_macro": "\\params",
             "definition": "\\theta", "description": "Model parameters"},
        ],
    })
    _w(tmp_path / "config" / "experiment-env.yaml", {
        "hardware": {"gpu": "NVIDIA A100 80GB × 4", "cpu": "AMD EPYC 7763"},
        "software": {"os": "Ubuntu 22.04", "python": "3.10.12", "pytorch": "2.1.0"},
        "training": {"total_time": "~12 hours", "batch_size": 32},
    })
    _w(tmp_path / "config" / "figure-style.yaml", {
        "colors": {"palette": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]},
        "fonts": {"family": "serif", "title_size": 12, "label_size": 10},
        "layout": {"dpi": 300, "default_format": "pdf",
                    "single_column_width": 3.5, "double_column_width": 7.0},
    })
    (tmp_path / "config" / "style-guide.md").write_text(
        "# 写作风格指南\n\n"
        "## 段落结构\n每段首句为主题句。\n\n"
        "## 引用格式\n使用 `如图~\\ref{fig:xxx}~所示`。\n\n"
        "## 禁止用语\n- 近年来\n- 众所周知\n\n"
        "## 中英文混排\n中文与英文之间保留空格。\n" * 3,
        encoding="utf-8")

    # === Pipeline Notes ===
    (tmp_path / "pipeline" / "notes" / "outline.md").write_text(
        "# 论文大纲\n\n"
        "## 00-abstract\n摘要\n\n"
        "## 01-intro\n引言：背景、动机、贡献\n\n"
        "## 02-related\n相关工作\n\n"
        "## 03-method\n方法描述\n\n"
        "## 04-experiments\n实验设置与结果\n\n"
        "## 05-conclusion\n结论\n",
        encoding="utf-8")
    (tmp_path / "pipeline" / "notes" / "arguments.md").write_text(
        "# 论点梳理\n\n"
        "## 01-intro\n- 现有方法在长文本分类上效果不佳\n"
        "- 本文提出改进的 Transformer 架构\n\n"
        "## 03-method\n- 引入局部注意力窗口\n"
        "- 保持全局建模能力\n",
        encoding="utf-8")
    (tmp_path / "pipeline" / "notes" / "findings.md").write_text(
        "# 关键发现\n\n"
        "- 模型准确率 0.96，超过 BERT (0.91) 和 GPT (0.93)\n"
        "- F1 指标同样领先\n",
        encoding="utf-8")

    # === 参考文献 ===
    _w(tmp_path / "refs" / "library.yaml", {
        "references": [
            {
                "citekey": "vaswani2017attention",
                "title": "Attention Is All You Need",
                "authors": ["Vaswani, A.", "Shazeer, N."],
                "year": 2017,
                "venue": "NeurIPS",
                "tags": ["transformer", "attention"],
                "key_quotes": [{
                    "id": "q1",
                    "text": "The Transformer is the first transduction model relying entirely on self-attention.",
                    "page": 2,
                }],
                "bibtex": "@inproceedings{vaswani2017attention,\n  title={Attention Is All You Need},\n  author={Vaswani, A.},\n  year={2017}\n}\n",
            },
            {
                "citekey": "devlin2019bert",
                "title": "BERT: Pre-training of Deep Bidirectional Transformers",
                "authors": ["Devlin, J."],
                "year": 2019,
                "venue": "NAACL",
                "tags": ["bert", "pretraining"],
                "key_quotes": [{
                    "id": "q1",
                    "text": "BERT is designed to pre-train deep bidirectional representations.",
                    "page": 1,
                }],
                "bibtex": "@inproceedings{devlin2019bert,\n  title={BERT},\n  author={Devlin, J.},\n  year={2019}\n}\n",
            },
        ],
    })

    # === 论文层 ===
    (tmp_path / "paper" / "preamble.tex").write_text(
        "\\newcommand{\\loss}{\\mathcal{L}}\n"
        "\\newcommand{\\params}{\\theta}\n",
        encoding="utf-8")
    (tmp_path / "paper" / "main.tex").write_text(
        "\\input{preamble}\n"
        "\\begin{document}\n"
        "\\input{sections/00-abstract}\n"
        "\\input{sections/01-intro}\n"
        "\\input{sections/02-related}\n"
        "\\input{sections/03-method}\n"
        "\\input{sections/04-experiments}\n"
        "\\input{sections/05-conclusion}\n"
        "\\bibliographystyle{plain}\n"
        "\\bibliography{references}\n"
        "\\end{document}\n",
        encoding="utf-8")
    (tmp_path / "paper" / "references.bib").write_text(
        "@inproceedings{vaswani2017attention,\n"
        "  title={Attention Is All You Need},\n"
        "  author={Vaswani, A.},\n  year={2017}\n}\n\n"
        "@inproceedings{devlin2019bert,\n"
        "  title={BERT},\n"
        "  author={Devlin, J.},\n  year={2019}\n}\n",
        encoding="utf-8")

    # 章节文件
    (tmp_path / "paper" / "sections" / "00-abstract.tex").write_text(
        "\\begin{abstract}\n"
        "本文提出了一种改进的 Transformer 架构。\n"
        "\\end{abstract}\n",
        encoding="utf-8")
    (tmp_path / "paper" / "sections" / "01-intro.tex").write_text(
        "\\section{引言}\n"
        "Transformer \\cite{vaswani2017attention} 已成为 NLP 的基础架构。\n"
        "BERT \\cite{devlin2019bert} 进一步推动了预训练范式。\n"
        "本文的 \\loss{} 函数设计如下。\n",
        encoding="utf-8")
    (tmp_path / "paper" / "sections" / "02-related.tex").write_text(
        "\\section{相关工作}\n"
        "注意力机制 \\cite{vaswani2017attention} 是本文方法的基础。\n",
        encoding="utf-8")
    (tmp_path / "paper" / "sections" / "03-method.tex").write_text(
        "\\section{方法}\n"
        "我们优化 \\loss{} 关于 \\params{} 的梯度。\n"
        "\\label{sec:method}\n",
        encoding="utf-8")
    (tmp_path / "paper" / "sections" / "04-experiments.tex").write_text(
        "\\section{实验}\n"
        "如表~\\ref{tab:results}~所示，我们的方法优于基线。\n"
        "\\begin{table}\n\\label{tab:results}\n\\end{table}\n",
        encoding="utf-8")
    (tmp_path / "paper" / "sections" / "05-conclusion.tex").write_text(
        "\\section{结论}\n"
        "本文提出了一种改进方法。\n",
        encoding="utf-8")

    return tmp_path


def _w(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


# ============================================================
# 端到端测试
# ============================================================

class TestEndToEnd:
    """完整流程: 初始化 → 检查 → 验证"""

    def test_initialization_pipeline(self, full_project: Path) -> None:
        """Phase 0: 项目初始化"""
        from tools.project_init import ProjectInitializer

        pi = ProjectInitializer(full_project)
        # 1. 扫描数据
        scan = pi.scan_data_layer()
        assert scan.total_count >= 3  # results.csv, train.py, old_intro.md
        assert "data" in scan.type_counts
        assert "code" in scan.type_counts

        # 2. 生成 manifest
        manifest = pi.generate_manifest(scan)
        pi.save_manifest(manifest)
        assert (full_project / "data" / "_manifest.yaml").exists()

        # 3. 检查完备性
        report = pi.check_completeness()
        assert report.overall_readiness > 0.5

        # 4. 生成报告
        text = pi.generate_init_report(scan, report)
        assert "扫描" in text
        assert "配置" in text

    def test_config_validation_pipeline(self, full_project: Path) -> None:
        """配置校验全通过"""
        from tools.config_validator import ConfigValidator

        cv = ConfigValidator(full_project)
        report = cv.validate_all()
        # 完整项目不应有 error
        assert report.is_valid, f"Errors found:\n{report.summary()}"

    def test_reference_management(self, full_project: Path) -> None:
        """文献管理全流程"""
        from tools.bib_manager import BibManager

        bm = BibManager(full_project)

        # 搜索已有文献
        results = bm.search_local("transformer attention")
        assert len(results) >= 1

        # 获取引用溯源
        quote = bm.get_quote("vaswani2017attention", "q1")
        assert quote is not None
        assert "self-attention" in quote["text"]

        # 验证引用完整性
        val = bm.validate_citations()
        assert len(val["missing"]) == 0

        # 同步 bib
        bm.sync_bib()
        bib_text = (full_project / "paper" / "references.bib").read_text(
            encoding="utf-8")
        assert "vaswani2017" in bib_text
        assert "devlin2019" in bib_text

    def test_glossary_check(self, full_project: Path) -> None:
        """术语一致性检查"""
        from tools.glossary_checker import GlossaryChecker

        gc = GlossaryChecker(full_project)
        report = gc.check_all()
        # 不应有 forbidden variant 问题（正文未使用禁止变体）
        forbidden = [i for i in report.issues if i.rule == "forbidden_variant"]
        assert len(forbidden) == 0

    def test_paper_lint(self, full_project: Path) -> None:
        """论文质量检查"""
        from tools.paper_lint import PaperLint

        pl = PaperLint(full_project)
        report = pl.check_all()
        # 不应有 citation error（所有 cite 都在 bib 中）
        citation_errors = [i for i in report.items
                           if i.category == "citation" and i.level == "error"]
        assert len(citation_errors) == 0

        # 不应有未引用的 label
        ref_errors = [i for i in report.items
                      if i.category == "figure_ref" and i.level == "error"]
        assert len(ref_errors) == 0

    def test_command_dispatcher(self, full_project: Path) -> None:
        """命令调度器端到端"""
        from tools.commands import CommandDispatcher

        d = CommandDispatcher(full_project)

        # 检查全文
        result = d.execute("检查全文")
        assert result.success, f"Failed:\n{result.report()}"
        assert len(result.steps) == 3

        # 检查配置
        result = d.execute("检查配置")
        assert result.success

        # 同步文献
        result = d.execute("同步文献")
        assert result.success

        # 写章节（上下文加载）
        result = d.execute("写 introduction")
        assert result.success
        assert any("outline" in s.name.lower() or "大纲" in s.name
                    for s in result.steps)

    def test_cross_tool_consistency(self, full_project: Path) -> None:
        """交叉验证: 配置校验 + paper_lint + glossary 结果一致"""
        from tools.config_validator import ConfigValidator
        from tools.paper_lint import PaperLint
        from tools.glossary_checker import GlossaryChecker

        # 配置校验: glossary 中的宏应在 preamble 中
        cv = ConfigValidator(full_project)
        cv_report = cv.validate_all()
        cross_issues = [i for i in cv_report.issues if "preamble" in i.file]
        assert len(cross_issues) == 0, "Glossary macros not in preamble"

        # Paper lint: 引用完整
        pl = PaperLint(full_project)
        pl_report = pl.check_all()
        assert pl_report.error_count == 0

        # Glossary: 术语一致
        gc = GlossaryChecker(full_project)
        gc_report = gc.check_all()
        errors = [i for i in gc_report.issues if i.level == "error"]
        assert len(errors) == 0

    def test_experimenter_then_analyst(self, full_project: Path) -> None:
        """Experimenter 添加数据 → Analyst 可以扫描到"""
        # Experimenter 新增实验数据
        (full_project / "data" / "raw" / "ablation.csv").write_text(
            "variant,accuracy\nno_local,0.93\nno_global,0.90\n",
            encoding="utf-8")

        # Analyst 重新扫描
        from tools.project_init import ProjectInitializer
        pi = ProjectInitializer(full_project)
        scan = pi.scan_data_layer()
        paths = [f.path for f in scan.files]
        assert any("ablation" in p for p in paths)

    def test_full_command_sequence(self, full_project: Path) -> None:
        """模拟完整用户交互: 初始化 → 检查配置 → 写章节 → 检查全文"""
        from tools.commands import CommandDispatcher

        d = CommandDispatcher(full_project)

        # Step 1: 初始化
        r1 = d.execute("初始化")
        assert isinstance(r1.steps, list)

        # Step 2: 检查配置
        r2 = d.execute("检查配置")
        assert r2.success

        # Step 3: 写章节（获取上下文）
        r3 = d.execute("写 method")
        assert r3.success

        # Step 4: 检查全文
        r4 = d.execute("检查全文")
        assert r4.success
