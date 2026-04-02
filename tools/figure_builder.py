"""
Paper Agent — 图表生成工具

核心职责:
1. 加载 config/figure-style.yaml 中的全局图表风格
2. 提供高层 API 生成常见学术图表（柱状图、折线图、消融表等）
3. 确保每张图表风格一致
4. 生成图表元信息 _meta.yaml

设计原则:
- 优先继承用户导入的原始图表风格
- 统一使用 config/figure-style.yaml 中的配色、字体、布局
- 每张图自动附带 meta 信息

依赖: matplotlib — 需要 `pip install matplotlib`
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    import matplotlib
    matplotlib.use("Agg")  # 非交互后端
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ============================================================
# 常量
# ============================================================

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent


# ============================================================
# 数据类
# ============================================================

@dataclass
class FigureMeta:
    """图表元信息。"""
    save_path: str
    caption_draft: str = ""
    source_data: str = ""
    source_script: str = ""
    used_in: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "save_path": self.save_path,
            "caption_draft": self.caption_draft,
            "source_data": self.source_data,
            "source_script": self.source_script,
            "used_in": self.used_in,
        }


# ============================================================
# 核心类
# ============================================================

class FigureBuilder:
    """学术图表生成器。

    从 config/figure-style.yaml 加载全局风格配置，
    生成统一风格的学术图表。
    """

    def __init__(self, project_root: str | Path | None = None):
        self.root = Path(project_root) if project_root else PROJECT_ROOT
        self.config_dir = self.root / "config"
        self.figures_dir = self.root / "pipeline" / "figures"
        self.style_config = self._load_style_config()

    # ----------------------------------------------------------
    # 0. 风格管理
    # ----------------------------------------------------------

    def apply_style(self) -> None:
        """将 figure-style.yaml 的配置应用到 matplotlib。"""
        self._check_mpl()
        cfg = self.style_config

        colors = cfg.get("colors", {})
        fonts = cfg.get("fonts", {})
        layout = cfg.get("layout", {})

        rcParams["figure.dpi"] = layout.get("dpi", 300)
        rcParams["savefig.dpi"] = layout.get("dpi", 300)

        family = fonts.get("family", "serif")
        rcParams["font.family"] = family
        rcParams["font.size"] = fonts.get("label_size", 10)
        rcParams["axes.titlesize"] = fonts.get("title_size", 12)
        rcParams["axes.labelsize"] = fonts.get("label_size", 10)
        rcParams["xtick.labelsize"] = fonts.get("tick_size", 9)
        rcParams["ytick.labelsize"] = fonts.get("tick_size", 9)
        rcParams["legend.fontsize"] = fonts.get("legend_size", 9)

        rcParams["figure.facecolor"] = colors.get("background", "white")
        rcParams["axes.facecolor"] = colors.get("background", "white")

        grid_visible = layout.get("grid_visible", False)
        rcParams["axes.grid"] = grid_visible
        if grid_visible:
            rcParams["grid.color"] = colors.get("grid_color", "#e0e0e0")

        # Spine 可见性
        visible_spines = set(layout.get("spine_visible", ["bottom", "left"]))
        for spine in ("top", "bottom", "left", "right"):
            rcParams[f"axes.spines.{spine}"] = spine in visible_spines

    def get_palette(self) -> list[str]:
        """获取当前配色方案。"""
        return self.style_config.get("colors", {}).get(
            "palette",
            ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"],
        )

    def get_default_format(self) -> str:
        """获取默认图表输出格式。"""
        return self.style_config.get("layout", {}).get("default_format", "pdf")

    # ----------------------------------------------------------
    # 1. 柱状图
    # ----------------------------------------------------------

    def plot_bar(self, data: dict[str, list[float]], labels: list[str],
                 title: str = "", xlabel: str = "", ylabel: str = "",
                 save_as: str | None = None,
                 caption: str = "", **kwargs: Any) -> FigureMeta:
        """生成分组柱状图。

        Args:
            data: {"Group A": [v1, v2, ...], "Group B": [v1, v2, ...]}
            labels: x 轴刻度标签
            save_as: 保存路径（相对于 pipeline/figures/）
        """
        self._check_mpl()
        self.apply_style()

        palette = self.get_palette()
        fig, ax = plt.subplots(figsize=self._default_figsize(**kwargs))

        n_groups = len(labels)
        n_series = len(data)
        bar_width = 0.8 / max(n_series, 1)

        import numpy as np
        x = np.arange(n_groups)

        for i, (series_name, values) in enumerate(data.items()):
            color = palette[i % len(palette)]
            offset = (i - n_series / 2 + 0.5) * bar_width
            ax.bar(x + offset, values, bar_width, label=series_name, color=color)

        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        if n_series > 1:
            ax.legend()

        plt.tight_layout()

        meta = self._save_figure(fig, save_as, caption)
        plt.close(fig)
        return meta

    # ----------------------------------------------------------
    # 2. 折线图
    # ----------------------------------------------------------

    def plot_line(self, data: dict[str, list[float]], x_values: list[Any],
                  title: str = "", xlabel: str = "", ylabel: str = "",
                  save_as: str | None = None,
                  caption: str = "", **kwargs: Any) -> FigureMeta:
        """生成折线图。

        Args:
            data: {"Series A": [y1, y2, ...], "Series B": [y1, y2, ...]}
            x_values: x 轴数值列表
        """
        self._check_mpl()
        self.apply_style()

        palette = self.get_palette()
        fig, ax = plt.subplots(figsize=self._default_figsize(**kwargs))

        for i, (series_name, values) in enumerate(data.items()):
            color = palette[i % len(palette)]
            ax.plot(x_values[:len(values)], values, label=series_name,
                    color=color, marker="o", markersize=4)

        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        if len(data) > 1:
            ax.legend()

        plt.tight_layout()
        meta = self._save_figure(fig, save_as, caption)
        plt.close(fig)
        return meta

    # ----------------------------------------------------------
    # 3. 热力图
    # ----------------------------------------------------------

    def plot_heatmap(self, matrix: list[list[float]],
                     row_labels: list[str], col_labels: list[str],
                     title: str = "", save_as: str | None = None,
                     caption: str = "", **kwargs: Any) -> FigureMeta:
        """生成热力图。"""
        self._check_mpl()
        self.apply_style()

        fig, ax = plt.subplots(figsize=self._default_figsize(**kwargs))

        import numpy as np
        arr = np.array(matrix)
        im = ax.imshow(arr, cmap="YlOrRd", aspect="auto")

        ax.set_xticks(range(len(col_labels)))
        ax.set_xticklabels(col_labels, rotation=45, ha="right")
        ax.set_yticks(range(len(row_labels)))
        ax.set_yticklabels(row_labels)

        # 添加数值标注
        for i in range(len(row_labels)):
            for j in range(len(col_labels)):
                ax.text(j, i, f"{arr[i, j]:.2f}", ha="center", va="center", fontsize=8)

        fig.colorbar(im, ax=ax)
        if title:
            ax.set_title(title)

        plt.tight_layout()
        meta = self._save_figure(fig, save_as, caption)
        plt.close(fig)
        return meta

    # ----------------------------------------------------------
    # 内部辅助方法
    # ----------------------------------------------------------

    def _save_figure(self, fig: Any, save_as: str | None, caption: str) -> FigureMeta:
        """保存图表到 pipeline/figures/ 并生成 meta 文件。"""
        self.figures_dir.mkdir(parents=True, exist_ok=True)

        if save_as is None:
            # 自动命名
            existing = list(self.figures_dir.glob(f"fig_*"))
            idx = len(existing) + 1
            fmt = self.get_default_format()
            save_as = f"fig_{idx:02d}.{fmt}"

        save_path = self.figures_dir / save_as
        fmt = save_path.suffix.lstrip(".")
        fig.savefig(str(save_path), format=fmt, bbox_inches="tight")

        # 生成 meta
        meta = FigureMeta(
            save_path=str(save_path.relative_to(self.root)).replace("\\", "/"),
            caption_draft=caption,
        )

        meta_path = save_path.with_name(save_path.stem + "_meta.yaml")
        with open(meta_path, "w", encoding="utf-8") as fp:
            yaml.dump(meta.to_dict(), fp, default_flow_style=False, allow_unicode=True)

        return meta

    def _default_figsize(self, **kwargs: Any) -> tuple[float, float]:
        layout = self.style_config.get("layout", {})
        width = kwargs.get("width", layout.get("single_column_width", 3.5))
        height = kwargs.get("height", width * 0.75)
        return (width, height)

    def _load_style_config(self) -> dict[str, Any]:
        path = self.config_dir / "figure-style.yaml"
        if not path.exists():
            return {}
        try:
            with open(path, encoding="utf-8") as fp:
                return yaml.safe_load(fp) or {}
        except yaml.YAMLError:
            return {}

    @staticmethod
    def _check_mpl():
        if not HAS_MPL:
            raise ImportError("matplotlib 未安装。请运行: pip install matplotlib")


# ============================================================
# CLI 入口
# ============================================================

def main():
    """示例: 生成一张测试图。"""
    builder = FigureBuilder()

    demo_data = {
        "Model A": [85.2, 91.3, 78.5],
        "Model B": [88.1, 89.7, 82.3],
        "Model C": [90.5, 93.1, 85.0],
    }
    labels = ["CIFAR-10", "MNIST", "ImageNet"]

    meta = builder.plot_bar(
        data=demo_data,
        labels=labels,
        title="Model Comparison",
        ylabel="Accuracy (%)",
        save_as="fig_demo_comparison.pdf",
        caption="Comparison of test accuracy across three models.",
    )
    print(f"已保存: {meta.save_path}")


if __name__ == "__main__":
    main()
