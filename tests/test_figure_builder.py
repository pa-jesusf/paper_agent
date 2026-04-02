"""
tests/test_figure_builder.py — FigureBuilder 单元测试

注: 仅测试配置加载和元信息逻辑。
     实际图表生成测试需要 matplotlib。
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from tools.figure_builder import FigureBuilder, FigureMeta


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture()
def project(tmp_path: Path) -> FigureBuilder:
    (tmp_path / "config").mkdir()
    (tmp_path / "pipeline" / "figures").mkdir(parents=True)
    return FigureBuilder(project_root=tmp_path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


# ============================================================
# 1. Style config
# ============================================================

class TestStyleConfig:

    def test_default_palette(self, project: FigureBuilder):
        palette = project.get_palette()
        assert len(palette) >= 5
        assert all(p.startswith("#") for p in palette)

    def test_custom_palette(self, tmp_path: Path):
        _write(tmp_path / "config" / "figure-style.yaml", """\
            colors:
              palette: ["#ff0000", "#00ff00"]
        """)
        builder = FigureBuilder(project_root=tmp_path)
        assert builder.get_palette() == ["#ff0000", "#00ff00"]

    def test_default_format(self, project: FigureBuilder):
        fmt = project.get_default_format()
        assert fmt in ("pdf", "png", "svg")

    def test_custom_format(self, tmp_path: Path):
        _write(tmp_path / "config" / "figure-style.yaml", """\
            layout:
              default_format: "svg"
        """)
        builder = FigureBuilder(project_root=tmp_path)
        assert builder.get_default_format() == "svg"

    def test_no_config_file(self, tmp_path: Path):
        (tmp_path / "config").mkdir(exist_ok=True)
        (tmp_path / "pipeline" / "figures").mkdir(parents=True, exist_ok=True)
        builder = FigureBuilder(project_root=tmp_path)
        # Should not crash, use defaults
        assert builder.style_config == {}
        assert len(builder.get_palette()) >= 5

    def test_corrupt_config(self, tmp_path: Path):
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "figure-style.yaml").write_text("{{bad", encoding="utf-8")
        builder = FigureBuilder(project_root=tmp_path)
        assert builder.style_config == {}


# ============================================================
# 2. FigureMeta
# ============================================================

class TestFigureMeta:

    def test_to_dict(self):
        meta = FigureMeta(
            save_path="pipeline/figures/fig_01.pdf",
            caption_draft="Test caption",
            source_data="data/raw/results.csv",
        )
        d = meta.to_dict()
        assert d["save_path"] == "pipeline/figures/fig_01.pdf"
        assert d["caption_draft"] == "Test caption"
        assert d["source_data"] == "data/raw/results.csv"


# ============================================================
# 3. 需要 matplotlib 的测试
# ============================================================

try:
    import matplotlib
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


@pytest.mark.skipif(not HAS_MPL, reason="matplotlib not installed")
class TestPlotting:

    def test_plot_bar(self, project: FigureBuilder):
        meta = project.plot_bar(
            data={"A": [1, 2, 3], "B": [3, 2, 1]},
            labels=["X", "Y", "Z"],
            title="Test Bar",
            save_as="test_bar.png",
            caption="Test bar chart.",
        )
        assert Path(project.root / meta.save_path).exists()
        assert meta.caption_draft == "Test bar chart."

        # Meta yaml should also be saved
        meta_yaml = project.figures_dir / "test_bar_meta.yaml"
        assert meta_yaml.exists()

    def test_plot_line(self, project: FigureBuilder):
        meta = project.plot_line(
            data={"Series": [10, 20, 30]},
            x_values=[1, 2, 3],
            save_as="test_line.png",
        )
        assert Path(project.root / meta.save_path).exists()

    def test_plot_heatmap(self, project: FigureBuilder):
        meta = project.plot_heatmap(
            matrix=[[1, 2], [3, 4]],
            row_labels=["A", "B"],
            col_labels=["X", "Y"],
            save_as="test_heatmap.png",
        )
        assert Path(project.root / meta.save_path).exists()

    def test_auto_naming(self, project: FigureBuilder):
        meta = project.plot_bar(
            data={"A": [1]},
            labels=["X"],
        )
        assert "fig_" in meta.save_path
