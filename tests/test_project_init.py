"""
tests/test_project_init.py — ProjectInitializer 单元测试

覆盖范围:
- scan_data_layer: 文件扫描、类型识别、框架检测
- generate_manifest / save_manifest: manifest 生成与保留已有描述
- check_completeness: 6 个配置文件完备性检查
- generate_init_report: 报告生成
- parse_requirements: requirements.txt 解析
- 边界场景: 空目录、损坏 YAML、缺失文件
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from tools.project_init import (
    CompletenessReport,
    FileInfo,
    ProjectInitializer,
    ScanResult,
)


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> ProjectInitializer:
    """创建一个最小化的项目骨架并返回 Initializer。"""
    (tmp_path / "data").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "pipeline" / "notes").mkdir(parents=True)
    (tmp_path / "paper").mkdir()
    (tmp_path / "refs").mkdir()
    return ProjectInitializer(project_root=tmp_path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


# ============================================================
# 1. scan_data_layer
# ============================================================

class TestScanDataLayer:

    def test_empty_data_dir(self, project: ProjectInitializer):
        result = project.scan_data_layer()
        assert result.total_count == 0
        assert result.files == []
        assert result.type_counts == {}

    def test_no_data_dir(self, tmp_path: Path):
        """data/ 目录不存在时应返回空结果。"""
        init = ProjectInitializer(project_root=tmp_path)
        result = init.scan_data_layer()
        assert result.total_count == 0

    def test_basic_file_detection(self, project: ProjectInitializer):
        root = project.data_dir
        (root / "train.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        (root / "model.py").write_text("print('hi')\n", encoding="utf-8")
        (root / "plot.png").write_bytes(b"\x89PNG")
        (root / "config.yaml").write_text("x: 1\n", encoding="utf-8")

        result = project.scan_data_layer()
        assert result.total_count == 4
        assert result.type_counts.get("data") == 1
        assert result.type_counts.get("code") == 1
        assert result.type_counts.get("figure") == 1
        assert result.type_counts.get("config") == 1

    def test_skip_files(self, project: ProjectInitializer):
        """_manifest.yaml 和 .gitkeep 等应被跳过。"""
        root = project.data_dir
        (root / "_manifest.yaml").write_text("files: []\n", encoding="utf-8")
        (root / ".gitkeep").write_text("", encoding="utf-8")
        (root / "real.csv").write_text("a\n1\n", encoding="utf-8")

        result = project.scan_data_layer()
        assert result.total_count == 1
        paths = [f.path for f in result.files]
        assert "real.csv" in paths
        assert "_manifest.yaml" not in paths
        assert ".gitkeep" not in paths

    def test_nested_directories(self, project: ProjectInitializer):
        sub = project.data_dir / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "file.json").write_text("{}", encoding="utf-8")

        result = project.scan_data_layer()
        assert result.total_count == 1
        assert result.files[0].path == "sub/deep/file.json"
        assert result.files[0].type == "data"

    def test_unknown_extension(self, project: ProjectInitializer):
        (project.data_dir / "model.onnx").write_bytes(b"\x00")
        result = project.scan_data_layer()
        assert result.total_count == 1
        assert result.files[0].type == "other"

    def test_requirements_detection(self, project: ProjectInitializer):
        _write(project.data_dir / "requirements.txt", "torch>=2.0")
        result = project.scan_data_layer()
        assert result.has_requirements is True
        assert result.requirements_path == "requirements.txt"

    def test_framework_detection_pytorch(self, project: ProjectInitializer):
        _write(project.data_dir / "train.py", """\
            import torch
            import torch.nn as nn
            model = nn.Linear(10, 1)
        """)
        result = project.scan_data_layer()
        assert "pytorch" in result.detected_frameworks

    def test_framework_detection_multiple(self, project: ProjectInitializer):
        _write(project.data_dir / "analysis.py", """\
            import numpy as np
            import pandas as pd
            from sklearn.ensemble import RandomForestClassifier
        """)
        result = project.scan_data_layer()
        assert "numpy" in result.detected_frameworks
        assert "pandas" in result.detected_frameworks
        assert "sklearn" in result.detected_frameworks

    def test_framework_detection_no_code(self, project: ProjectInitializer):
        (project.data_dir / "data.csv").write_text("a\n1\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.detected_frameworks == []

    def test_scan_result_summary(self, project: ProjectInitializer):
        (project.data_dir / "a.csv").write_text("x\n", encoding="utf-8")
        (project.data_dir / "b.py").write_text("pass\n", encoding="utf-8")
        result = project.scan_data_layer()
        summary = result.summary()
        assert "共发现 2 个文件" in summary
        assert "data: 1" in summary
        assert "code: 1" in summary

    def test_file_info_size(self, project: ProjectInitializer):
        content = b"hello world\n"
        (project.data_dir / "test.txt").write_bytes(content)
        result = project.scan_data_layer()
        assert result.files[0].size_bytes == len(content)


# ============================================================
# 2. generate_manifest / save_manifest
# ============================================================

class TestManifest:

    def test_generate_from_scan(self, project: ProjectInitializer):
        (project.data_dir / "a.csv").write_text("x\n", encoding="utf-8")
        scan = project.scan_data_layer()
        manifest = project.generate_manifest(scan)

        assert "files" in manifest
        assert len(manifest["files"]) == 1
        assert manifest["files"][0]["path"] == "a.csv"
        assert manifest["files"][0]["type"] == "data"
        assert manifest["files"][0]["description"] == ""

    def test_preserve_existing_descriptions(self, project: ProjectInitializer):
        """已有 manifest 中的 description 应被保留。"""
        (project.data_dir / "a.csv").write_text("x\n", encoding="utf-8")

        existing = {
            "files": [
                {"path": "a.csv", "type": "data", "description": "训练数据集"}
            ]
        }
        manifest_path = project.data_dir / "_manifest.yaml"
        with open(manifest_path, "w", encoding="utf-8") as fp:
            yaml.dump(existing, fp, allow_unicode=True)

        scan = project.scan_data_layer()
        manifest = project.generate_manifest(scan)
        assert manifest["files"][0]["description"] == "训练数据集"

    def test_save_manifest_creates_file(self, project: ProjectInitializer):
        manifest = {"files": [{"path": "a.csv", "type": "data", "description": ""}]}
        saved = project.save_manifest(manifest)
        assert saved.exists()

        with open(saved, encoding="utf-8") as fp:
            loaded = yaml.safe_load(fp)
        assert loaded["files"][0]["path"] == "a.csv"

    def test_save_manifest_overwrites(self, project: ProjectInitializer):
        manifest_v1 = {"files": [{"path": "a.csv", "type": "data", "description": ""}]}
        project.save_manifest(manifest_v1)

        manifest_v2 = {"files": [{"path": "b.json", "type": "data", "description": "new"}]}
        saved = project.save_manifest(manifest_v2)

        with open(saved, encoding="utf-8") as fp:
            loaded = yaml.safe_load(fp)
        assert len(loaded["files"]) == 1
        assert loaded["files"][0]["path"] == "b.json"

    def test_generate_manifest_empty_scan(self, project: ProjectInitializer):
        scan = ScanResult()
        manifest = project.generate_manifest(scan)
        assert manifest == {"files": []}

    def test_corrupt_existing_manifest(self, project: ProjectInitializer):
        """损坏的 manifest 不应阻止新 manifest 生成。"""
        (project.data_dir / "_manifest.yaml").write_text(
            "{{invalid yaml", encoding="utf-8"
        )
        (project.data_dir / "a.csv").write_text("x\n", encoding="utf-8")

        scan = project.scan_data_layer()
        manifest = project.generate_manifest(scan)
        assert len(manifest["files"]) == 1
        assert manifest["files"][0]["description"] == ""


# ============================================================
# 3. check_completeness
# ============================================================

class TestCheckCompleteness:

    def test_all_missing(self, tmp_path: Path):
        """所有配置文件缺失时，完备性为 0。"""
        (tmp_path / "data").mkdir()
        (tmp_path / "config").mkdir()
        (tmp_path / "pipeline" / "notes").mkdir(parents=True)
        init = ProjectInitializer(project_root=tmp_path)
        report = init.check_completeness()

        assert report.overall_readiness == 0.0
        assert len(report.incomplete_files) == 6

    def test_paper_yaml_complete(self, project: ProjectInitializer):
        _write(project.config_dir / "paper.yaml", """\
            title: "深度学习最优化算法研究"
            venue: "NeurIPS 2025"
            authors:
              - name: "张三"
                affiliation: "某大学"
        """)
        item = project._check_paper_yaml()
        assert item.is_complete is True
        assert item.missing_fields == []

    def test_paper_yaml_missing_title(self, project: ProjectInitializer):
        _write(project.config_dir / "paper.yaml", """\
            venue: "NeurIPS 2025"
            authors:
              - name: "张三"
        """)
        item = project._check_paper_yaml()
        assert item.is_complete is False
        assert any("title" in f for f in item.missing_fields)

    def test_paper_yaml_not_exist(self, project: ProjectInitializer):
        item = project._check_paper_yaml()
        assert item.is_complete is False
        assert "文件不存在" in item.missing_fields

    def test_glossary_complete(self, project: ProjectInitializer):
        _write(project.config_dir / "glossary.yaml", """\
            terms:
              - key: "transformer"
                chinese: "变压器模型"
                english: "Transformer"
            symbols: []
        """)
        item = project._check_glossary_yaml()
        assert item.is_complete is True

    def test_glossary_empty_lists(self, project: ProjectInitializer):
        _write(project.config_dir / "glossary.yaml", """\
            terms: []
            symbols: []
        """)
        item = project._check_glossary_yaml()
        assert item.is_complete is False

    def test_experiment_env_complete(self, project: ProjectInitializer):
        _write(project.config_dir / "experiment-env.yaml", """\
            hardware:
              gpu: "NVIDIA A100 80GB"
              gpu_count: 4
            software:
              python: "3.10"
              cuda: "12.1"
        """)
        item = project._check_experiment_env()
        assert item.is_complete is True

    def test_experiment_env_missing_gpu(self, project: ProjectInitializer):
        _write(project.config_dir / "experiment-env.yaml", """\
            hardware:
              cpu: "Intel Xeon"
            software:
              python: "3.10"
        """)
        item = project._check_experiment_env()
        assert item.is_complete is False
        assert any("gpu" in f.lower() for f in item.missing_fields)

    def test_figure_style_complete(self, project: ProjectInitializer):
        _write(project.config_dir / "figure-style.yaml", """\
            source_style:
              inherited_from: "user_plots/sample.png"
              analysis_notes: "蓝色主色调"
        """)
        item = project._check_figure_style()
        assert item.is_complete is True

    def test_figure_style_no_source(self, project: ProjectInitializer):
        _write(project.config_dir / "figure-style.yaml", """\
            colors:
              primary: "#1f77b4"
        """)
        item = project._check_figure_style()
        assert item.is_complete is False

    def test_style_guide_complete(self, project: ProjectInitializer):
        long_content = "# 写作风格指南\n\n" + "详细要求。" * 50
        (project.config_dir / "style-guide.md").write_text(
            long_content, encoding="utf-8"
        )
        item = project._check_style_guide()
        assert item.is_complete is True

    def test_style_guide_too_short(self, project: ProjectInitializer):
        (project.config_dir / "style-guide.md").write_text("x", encoding="utf-8")
        item = project._check_style_guide()
        assert item.is_complete is False

    def test_outline_complete(self, project: ProjectInitializer):
        _write(project.pipeline_dir / "notes" / "outline.md", """\
            # 论文大纲

            ## 1. Introduction
            本章介绍研究背景和动机，阐述问题的重要性和挑战。

            ## 2. Related Work
            综述相关工作，指出现有方法的局限性。

            ## 3. Method
            详细描述本文提出的方法。
        """)
        item = project._check_outline()
        assert item.is_complete is True

    def test_outline_only_template(self, project: ProjectInitializer):
        _write(project.pipeline_dir / "notes" / "outline.md", """\
            # 论文大纲

            <!-- 请在此填写大纲 -->
            > 提示：每个章节列出要点
        """)
        item = project._check_outline()
        assert item.is_complete is False

    def test_completeness_report_properties(self, project: ProjectInitializer):
        """CompletenessReport 辅助属性测试。"""
        report = CompletenessReport()
        assert report.overall_readiness == 0.0

        from tools.project_init import CompletenessItem
        report.items.append(CompletenessItem(file="a", is_complete=True))
        report.items.append(CompletenessItem(file="b", is_complete=False, missing_fields=["x"]))
        assert report.overall_readiness == 0.5
        assert report.complete_files == ["a"]
        assert report.incomplete_files == ["b"]

    def test_completeness_to_dict(self, project: ProjectInitializer):
        from tools.project_init import CompletenessItem
        report = CompletenessReport()
        report.items.append(
            CompletenessItem(
                file="config/paper.yaml",
                is_complete=False,
                missing_fields=["title"],
                suggested_question="请提供标题",
            )
        )
        d = report.to_dict()
        assert d["overall_readiness"] == 0.0
        assert len(d["incomplete"]) == 1
        assert d["incomplete"][0]["file"] == "config/paper.yaml"

    def test_completeness_summary(self, project: ProjectInitializer):
        from tools.project_init import CompletenessItem
        report = CompletenessReport()
        report.items.append(CompletenessItem(file="a.yaml", is_complete=True))
        report.items.append(
            CompletenessItem(file="b.yaml", is_complete=False, missing_fields=["x"])
        )
        summary = report.summary()
        assert "✓ a.yaml" in summary
        assert "✗ b.yaml" in summary
        assert "缺失: x" in summary


# ============================================================
# 4. generate_init_report
# ============================================================

class TestGenerateInitReport:

    def test_report_contains_sections(self, project: ProjectInitializer):
        scan = ScanResult()
        completeness = project.check_completeness()
        report = project.generate_init_report(scan, completeness)

        assert "项目初始化报告" in report
        assert "数据层" in report
        assert "配置完备性" in report
        assert "建议下一步" in report

    def test_report_with_data(self, project: ProjectInitializer):
        (project.data_dir / "train.csv").write_text("x\n1\n", encoding="utf-8")
        scan = project.scan_data_layer()
        completeness = project.check_completeness()
        report = project.generate_init_report(scan, completeness)
        assert "train.csv" in report


# ============================================================
# 5. parse_requirements
# ============================================================

class TestParseRequirements:

    def test_no_requirements(self, project: ProjectInitializer):
        result = project.parse_requirements()
        assert result == []

    def test_basic_requirements(self, project: ProjectInitializer):
        code_dir = project.data_dir / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        _write(code_dir / "requirements.txt", """\
            torch==2.1.0
            numpy>=1.24
            pandas
            # comment line
            transformers~=4.30.0
        """)
        result = project.parse_requirements()
        names = [r["name"] for r in result]
        assert "torch" in names
        assert "numpy" in names
        assert "pandas" in names
        assert "transformers" in names

        torch_entry = next(r for r in result if r["name"] == "torch")
        assert torch_entry["version"] == "2.1.0"

        pandas_entry = next(r for r in result if r["name"] == "pandas")
        assert pandas_entry["version"] == ""

    def test_requirements_in_root(self, project: ProjectInitializer):
        """requirements.txt 可能在 data/ 根目录。"""
        _write(project.data_dir / "requirements.txt", "torch==2.0\n")
        result = project.parse_requirements()
        assert len(result) == 1
        assert result[0]["name"] == "torch"

    def test_skip_flags_and_blanks(self, project: ProjectInitializer):
        _write(project.data_dir / "code" / "requirements.txt", """\
            -f https://example.com/simple
            --extra-index-url https://example.com

            torch
        """)
        code_dir = project.data_dir / "code"
        code_dir.mkdir(parents=True, exist_ok=True)
        _write(code_dir / "requirements.txt", """\
            -f https://example.com/simple
            --extra-index-url https://example.com

            torch
        """)
        result = project.parse_requirements()
        assert len(result) == 1
        assert result[0]["name"] == "torch"


# ============================================================
# 6. FileInfo
# ============================================================

class TestFileInfo:

    def test_to_manifest_entry(self):
        fi = FileInfo(
            path="sub/file.csv",
            abs_path="/tmp/data/sub/file.csv",
            type="data",
            size_bytes=1024,
            extension=".csv",
        )
        entry = fi.to_manifest_entry()
        assert entry == {"path": "sub/file.csv", "type": "data", "description": ""}


# ============================================================
# 7. 边界场景
# ============================================================

class TestEdgeCases:

    def test_corrupt_yaml_in_completeness(self, project: ProjectInitializer):
        """损坏的 YAML 应被安全处理（不崩溃）。"""
        (project.config_dir / "paper.yaml").write_text(
            "{{[invalid", encoding="utf-8"
        )
        item = project._check_paper_yaml()
        # safe_load 返回 None → 视为空文件
        assert item.is_complete is False

    def test_empty_yaml_in_completeness(self, project: ProjectInitializer):
        """空 YAML 文件应视为不完整。"""
        (project.config_dir / "paper.yaml").write_text("", encoding="utf-8")
        item = project._check_paper_yaml()
        assert item.is_complete is False

    def test_safe_load_yaml_returns_none_for_missing(self, project: ProjectInitializer):
        result = ProjectInitializer._safe_load_yaml(
            project.config_dir / "nonexistent.yaml"
        )
        assert result is None

    def test_safe_load_yaml_returns_dict(self, project: ProjectInitializer):
        _write(project.config_dir / "test.yaml", "key: value")
        result = ProjectInitializer._safe_load_yaml(project.config_dir / "test.yaml")
        assert result == {"key": "value"}

    def test_full_workflow(self, project: ProjectInitializer):
        """端到端工作流测试: 扫描 → 生成manifest → 完备性检查 → 报告。"""
        # 准备数据
        _write(project.data_dir / "train.csv", "x,y\n1,2")
        _write(project.data_dir / "model.py", "import torch\nmodel = torch.nn.Linear(1,1)")

        # 准备完整配置
        _write(project.config_dir / "paper.yaml", """\
            title: "测试论文"
            venue: "NeurIPS 2025"
            authors:
              - name: "张三"
        """)
        _write(project.config_dir / "glossary.yaml", """\
            terms:
              - key: "transformer"
                chinese: "变压器模型"
            symbols: []
        """)
        _write(project.config_dir / "experiment-env.yaml", """\
            hardware:
              gpu: "A100"
            software:
              python: "3.10"
        """)
        _write(project.config_dir / "figure-style.yaml", """\
            source_style:
              inherited_from: "user_plots/sample.png"
              analysis_notes: "蓝色主色调"
        """)
        (project.config_dir / "style-guide.md").write_text(
            "# 写作风格\n" + "详细的写作指南内容。" * 30, encoding="utf-8"
        )
        _write(project.pipeline_dir / "notes" / "outline.md", """\
            # 大纲

            ## 1. Introduction
            介绍研究背景和动机，附带详细说明。

            ## 2. Method
            本文提出的方法及其细节描述。
        """)

        # 执行完整流程
        scan = project.scan_data_layer()
        assert scan.total_count == 2
        assert "pytorch" in scan.detected_frameworks

        manifest = project.generate_manifest(scan)
        saved = project.save_manifest(manifest)
        assert saved.exists()

        report = project.check_completeness()
        assert report.overall_readiness == 1.0

        init_report = project.generate_init_report(scan, report)
        assert "项目初始化报告" in init_report


# ============================================================
# 8. 智能分类增强
# ============================================================

class TestSmartClassification:
    """测试内容级智能分类、临时文件检测、用途推断。"""

    # ---- 临时文件检测 ----

    def test_temp_prefix(self, project: ProjectInitializer):
        (project.data_dir / "temp_output.csv").write_text("x\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is True

    def test_tmp_prefix(self, project: ProjectInitializer):
        (project.data_dir / "tmp-cache.pkl").write_bytes(b"\x80")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is True

    def test_debug_prefix(self, project: ProjectInitializer):
        (project.data_dir / "debug_run1.log").write_text("ok\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is True

    def test_checkpoint_anywhere(self, project: ProjectInitializer):
        (project.data_dir / "model_checkpoint.pkl").write_bytes(b"\x80")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is True

    def test_bak_suffix(self, project: ProjectInitializer):
        (project.data_dir / "data.csv.bak").write_text("x\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is True

    def test_old_suffix(self, project: ProjectInitializer):
        (project.data_dir / "script_old.py").write_text("pass\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is True

    def test_backup_suffix(self, project: ProjectInitializer):
        (project.data_dir / "config_backup.yaml").write_text("x: 1\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is True

    def test_normal_file_not_temporary(self, project: ProjectInitializer):
        (project.data_dir / "results.csv").write_text("x\n1\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is False

    def test_log_files_temporary(self, project: ProjectInitializer):
        (project.data_dir / "train.log").write_text("epoch 1\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.files[0].is_temporary is True

    # ---- PDF 分类 ----

    def test_pdf_reference_detection(self, project: ProjectInitializer):
        """含有 abstract/references 关键词的 PDF 应识别为参考文献。"""
        content = b"%PDF-1.4 " + b"abstract " + b"references " + b"introduction"
        (project.data_dir / "paper.pdf").write_bytes(content)
        result = project.scan_data_layer()
        f = result.files[0]
        assert f.type == "reference"
        assert f.purpose == "参考文献"
        assert f.suggested_location == "refs/pdfs/"

    def test_pdf_figure_by_name(self, project: ProjectInitializer):
        """不含学术关键词但文件名含 fig 的 PDF 应为图表。"""
        (project.data_dir / "fig_comparison.pdf").write_bytes(b"%PDF-1.4 blank")
        result = project.scan_data_layer()
        f = result.files[0]
        assert f.type == "figure"
        assert f.purpose == "图表"

    def test_pdf_ambiguous(self, project: ProjectInitializer):
        """既无学术关键词也无图表关键词的 PDF。"""
        (project.data_dir / "unknown.pdf").write_bytes(b"%PDF-1.4 blank")
        result = project.scan_data_layer()
        f = result.files[0]
        assert f.type == "figure"  # 默认由扩展名决定
        assert "不明" in f.content_hint

    # ---- Python 用途推断 ----

    def test_py_training(self, project: ProjectInitializer):
        _write(project.data_dir / "train.py", """\
            import torch
            model.train()
            loss.backward()
            optimizer.step()
        """)
        result = project.scan_data_layer()
        f = result.files[0]
        assert f.purpose == "training"
        assert "training" in f.content_hint

    def test_py_visualization(self, project: ProjectInitializer):
        _write(project.data_dir / "plot.py", """\
            import matplotlib.pyplot as plt
            plt.figure()
            plt.savefig("output.png")
        """)
        result = project.scan_data_layer()
        f = result.files[0]
        assert f.purpose == "visualization"

    def test_py_preprocessing(self, project: ProjectInitializer):
        _write(project.data_dir / "clean.py", """\
            import pandas as pd
            df = pd.read_csv("data.csv")
            df = df.dropna()
        """)
        result = project.scan_data_layer()
        f = result.files[0]
        assert "preprocessing" in f.content_hint

    def test_py_evaluation(self, project: ProjectInitializer):
        _write(project.data_dir / "eval.py", """\
            from sklearn.metrics import accuracy_score, f1_score
            acc = accuracy_score(y_true, y_pred)
        """)
        result = project.scan_data_layer()
        f = result.files[0]
        assert "evaluation" in f.content_hint

    def test_py_no_match(self, project: ProjectInitializer):
        _write(project.data_dir / "utils.py", """\
            def helper(x):
                return x + 1
        """)
        result = project.scan_data_layer()
        f = result.files[0]
        assert f.content_hint == "Python 脚本"

    # ---- CSV 嗅探 ----

    def test_csv_header_detection(self, project: ProjectInitializer):
        _write(project.data_dir / "results.csv", """\
            epoch,loss,accuracy,lr
            1,0.5,0.8,0.001
            2,0.3,0.85,0.001
            3,0.2,0.9,0.0005
        """)
        result = project.scan_data_layer()
        f = result.files[0]
        assert "epoch" in f.content_hint
        assert "loss" in f.content_hint
        assert f.purpose == "数据表"

    def test_tsv_header_detection(self, project: ProjectInitializer):
        _write(project.data_dir / "data.tsv", "name\tscore\trank\nA\t90\t1\n")
        result = project.scan_data_layer()
        f = result.files[0]
        assert "name" in f.content_hint
        assert "score" in f.content_hint

    # ---- TeX 嗅探 ----

    def test_tex_full_document(self, project: ProjectInitializer):
        _write(project.data_dir / "draft.tex", r"""\documentclass{article}
            \begin{document}
            Hello world
            \end{document}
        """)
        result = project.scan_data_layer()
        f = result.files[0]
        assert f.purpose == "完整草稿"

    def test_tex_section_fragment(self, project: ProjectInitializer):
        _write(project.data_dir / "method.tex", r"""
            \section{Method}
            We propose a novel approach.
        """)
        result = project.scan_data_layer()
        f = result.files[0]
        assert f.purpose == "章节片段"

    # ---- 建议位置 ----

    def test_suggested_location_data(self, project: ProjectInitializer):
        (project.data_dir / "results.csv").write_text("x\n1\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert result.files[0].suggested_location == "data/raw/"

    def test_suggested_location_code(self, project: ProjectInitializer):
        _write(project.data_dir / "train.py", "pass")
        result = project.scan_data_layer()
        assert result.files[0].suggested_location == "data/code/"

    def test_suggested_location_reference(self, project: ProjectInitializer):
        content = b"%PDF-1.4 abstract references introduction"
        (project.data_dir / "paper.pdf").write_bytes(content)
        result = project.scan_data_layer()
        assert result.files[0].suggested_location == "refs/pdfs/"

    # ---- Manifest 增强字段 ----

    def test_manifest_includes_purpose(self, project: ProjectInitializer):
        _write(project.data_dir / "train.py", """\
            import torch
            model.train()
            loss.backward()
        """)
        scan = project.scan_data_layer()
        manifest = project.generate_manifest(scan)
        entry = manifest["files"][0]
        assert "purpose" in entry
        assert entry["purpose"] == "training"

    def test_manifest_includes_content_hint(self, project: ProjectInitializer):
        _write(project.data_dir / "data.csv", "col_a,col_b\n1,2\n")
        scan = project.scan_data_layer()
        manifest = project.generate_manifest(scan)
        entry = manifest["files"][0]
        assert "content_hint" in entry

    def test_manifest_includes_is_temporary(self, project: ProjectInitializer):
        (project.data_dir / "temp_out.csv").write_text("x\n", encoding="utf-8")
        scan = project.scan_data_layer()
        manifest = project.generate_manifest(scan)
        entry = manifest["files"][0]
        assert entry.get("is_temporary") is True

    def test_manifest_no_temporary_flag_for_normal(self, project: ProjectInitializer):
        (project.data_dir / "results.csv").write_text("x\n1\n", encoding="utf-8")
        scan = project.scan_data_layer()
        manifest = project.generate_manifest(scan)
        entry = manifest["files"][0]
        assert "is_temporary" not in entry

    def test_manifest_preserves_manual_purpose(self, project: ProjectInitializer):
        """手动设置的 purpose 应在重扫后保留。"""
        _write(project.data_dir / "script.py", "pass")
        # 先有一个带手动 purpose 的 manifest
        existing = {
            "files": [
                {"path": "script.py", "type": "code", "description": "",
                 "purpose": "手动标注的工具"}
            ]
        }
        with open(project.data_dir / "_manifest.yaml", "w", encoding="utf-8") as fp:
            yaml.dump(existing, fp, allow_unicode=True)

        scan = project.scan_data_layer()
        manifest = project.generate_manifest(scan)
        # 自动推断为空时，应保留手动标注
        assert manifest["files"][0].get("purpose") in ("手动标注的工具", "utility", "")

    # ---- ScanResult 新属性 ----

    def test_scan_result_temporary_files(self, project: ProjectInitializer):
        (project.data_dir / "temp_x.csv").write_text("x\n", encoding="utf-8")
        (project.data_dir / "real.csv").write_text("x\n1\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert len(result.temporary_files) == 1
        assert result.temporary_files[0].path == "temp_x.csv"

    def test_scan_result_reference_files(self, project: ProjectInitializer):
        content = b"%PDF-1.4 abstract references"
        (project.data_dir / "paper.pdf").write_bytes(content)
        (project.data_dir / "plot.png").write_bytes(b"\x89PNG")
        result = project.scan_data_layer()
        assert len(result.reference_files) == 1

    def test_summary_mentions_temporary(self, project: ProjectInitializer):
        (project.data_dir / "temp_out.csv").write_text("x\n", encoding="utf-8")
        result = project.scan_data_layer()
        assert "临时文件" in result.summary()

    def test_summary_mentions_references(self, project: ProjectInitializer):
        content = b"%PDF-1.4 abstract references"
        (project.data_dir / "paper.pdf").write_bytes(content)
        result = project.scan_data_layer()
        assert "参考文献" in result.summary()

    # ---- 报告增强 ----

    def test_report_file_details_section(self, project: ProjectInitializer):
        _write(project.data_dir / "train.py", "import torch\nmodel.train()")
        (project.data_dir / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        scan = project.scan_data_layer()
        report = project.generate_init_report(scan, project.check_completeness())
        assert "文件详情" in report
        assert "[code]" in report
        assert "[data]" in report

    def test_report_temp_warning(self, project: ProjectInitializer):
        (project.data_dir / "temp_debug.csv").write_text("x\n", encoding="utf-8")
        scan = project.scan_data_layer()
        report = project.generate_init_report(scan, project.check_completeness())
        assert "临时文件" in report

    def test_report_reference_suggestion(self, project: ProjectInitializer):
        content = b"%PDF-1.4 abstract references introduction"
        (project.data_dir / "paper.pdf").write_bytes(content)
        scan = project.scan_data_layer()
        report = project.generate_init_report(scan, project.check_completeness())
        assert "refs/pdfs/" in report


# ============================================================
# 9. 混乱文件夹综合场景
# ============================================================

class TestMessyFolder:
    """模拟用户把所有文件混在一个目录下的场景。"""

    def test_messy_raw_folder(self, project: ProjectInitializer):
        raw = project.data_dir / "raw"
        raw.mkdir()

        # 训练代码
        _write(raw / "train.py", """\
            import torch
            model.train()
            loss.backward()
            optimizer.step()
        """)
        # 画图脚本
        _write(raw / "plot_results.py", """\
            import matplotlib.pyplot as plt
            plt.figure()
            plt.savefig("out.png")
        """)
        # 数据
        _write(raw / "results.csv", "epoch,loss,acc\n1,0.5,0.8\n2,0.3,0.9\n")
        (raw / "embeddings.npy").write_bytes(b"\x00" * 100)
        # 参考论文 PDF
        (raw / "attention_paper.pdf").write_bytes(
            b"%PDF-1.4 abstract references introduction related work"
        )
        # 图表 PNG
        (raw / "loss_curve.png").write_bytes(b"\x89PNG fake")
        # 图表 PDF (无学术关键词)
        (raw / "fig_architecture.pdf").write_bytes(b"%PDF-1.4 blank figure")
        # 旧草稿 tex
        _write(raw / "draft_v2.tex", r"\documentclass{article}\begin{document}Hello\end{document}")
        # 临时文件
        (raw / "temp_checkpoint.pkl").write_bytes(b"\x80\x05" * 50)
        (raw / "debug_output.log").write_text("error\n", encoding="utf-8")
        # 训练配置
        _write(raw / "config.yaml", "lr: 0.001\nbatch_size: 32")

        scan = project.scan_data_layer()

        # 检查文件总数
        assert scan.total_count == 11

        # 按 path 索引
        by_path = {f.path: f for f in scan.files}

        # 训练代码应识别用途
        train = by_path["raw/train.py"]
        assert train.type == "code"
        assert train.purpose == "training"

        # 画图脚本
        plot = by_path["raw/plot_results.py"]
        assert plot.type == "code"
        assert plot.purpose == "visualization"

        # 参考论文 PDF 应重分类
        paper = by_path["raw/attention_paper.pdf"]
        assert paper.type == "reference"
        assert paper.suggested_location == "refs/pdfs/"

        # 图表 PDF 保持 figure
        fig_pdf = by_path["raw/fig_architecture.pdf"]
        assert fig_pdf.type == "figure"

        # CSV 应有表头摘要
        csv_f = by_path["raw/results.csv"]
        assert "epoch" in csv_f.content_hint
        assert csv_f.purpose == "数据表"

        # 临时文件应标记
        temp = by_path["raw/temp_checkpoint.pkl"]
        assert temp.is_temporary is True
        debug = by_path["raw/debug_output.log"]
        assert debug.is_temporary is True

        # 草稿应识别
        draft = by_path["raw/draft_v2.tex"]
        assert draft.type == "draft"
        assert draft.purpose == "完整草稿"

        # ScanResult 属性
        assert len(scan.temporary_files) >= 2
        assert len(scan.reference_files) == 1

        # 框架检测
        assert "pytorch" in scan.detected_frameworks

        # 报告不应崩溃且包含关键信息
        completeness = project.check_completeness()
        report = project.generate_init_report(scan, completeness)
        assert "参考文献" in report or "reference" in report
        assert "临时文件" in report
        assert "文件详情" in report
