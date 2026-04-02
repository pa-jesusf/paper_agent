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
