"""
pipeline/scripts/00_thesis_plot_style.py
─────────────────────────────────────────
共享绘图样式模块：读取 config/figure-style.yaml，返回 matplotlib rcParams。
所有后续图表脚本 import 此模块以保证风格统一。

输入: config/figure-style.yaml
输出: 无文件输出（被其他脚本 import）
"""
import yaml
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "figure-style.yaml"

def load_style():
    """加载 figure-style.yaml 并返回 parsed dict."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def apply_thesis_style():
    """将 figure-style.yaml 配置应用为 matplotlib rcParams."""
    cfg = load_style()
    colors = cfg.get("colors", {})
    fonts = cfg.get("fonts", {})
    layout = cfg.get("layout", {})

    # 基础样式
    plt.rcParams.update({
        "figure.dpi": layout.get("dpi", 300),
        "savefig.dpi": layout.get("dpi", 300),
        "figure.figsize": (layout.get("single_column_width", 6.0), 4.0),
        "font.family": fonts.get("family", "serif"),
        "font.size": fonts.get("label_size", 11),
        "axes.titlesize": fonts.get("title_size", 12),
        "axes.labelsize": fonts.get("label_size", 11),
        "xtick.labelsize": fonts.get("tick_size", 10),
        "ytick.labelsize": fonts.get("tick_size", 10),
        "legend.fontsize": fonts.get("legend_size", 10),
        "axes.facecolor": colors.get("background", "white"),
        "figure.facecolor": colors.get("background", "white"),
        "axes.grid": layout.get("grid_visible", False),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,  # TrueType，确保 PDF 中文字可搜索
        "ps.fonttype": 42,
    })

    # 尝试加载中文字体
    for zh_font in ["SimSun", "STSong", "Songti SC", "Noto Serif CJK SC"]:
        matches = fm.findSystemFonts(fontpaths=None)
        if any(zh_font.lower().replace(" ", "") in p.lower().replace(" ", "") for p in matches):
            plt.rcParams["font.serif"] = [zh_font, "Times New Roman", "DejaVu Serif"]
            break

    return cfg


# 常用颜色快捷访问
def get_palette():
    cfg = load_style()
    return cfg.get("colors", {}).get("palette", [])

def get_color(key):
    cfg = load_style()
    return cfg.get("colors", {}).get(key, "#333333")


# 图表保存辅助
FIGURES_DIR = ROOT / "pipeline" / "figures"
TABLES_DIR = ROOT / "pipeline" / "tables"
PAPER_FIGURES_DIR = ROOT / "paper" / "figures"

def save_figure(fig, name, chapter=None, also_paper=True):
    """保存图表到 pipeline/figures/ 并可选复制到 paper/figures/."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"fig_{chapter:02d}_" if chapter else "fig_"
    stem = f"{prefix}{name}"
    
    pdf_path = FIGURES_DIR / f"{stem}.pdf"
    png_path = FIGURES_DIR / f"{stem}.png"
    
    fig.savefig(pdf_path, bbox_inches="tight", pad_inches=0.05)
    fig.savefig(png_path, bbox_inches="tight", pad_inches=0.05)
    print(f"  Saved: {pdf_path.relative_to(ROOT)}")
    
    if also_paper:
        PAPER_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(pdf_path, PAPER_FIGURES_DIR / f"{stem}.pdf")
        print(f"  Copied to: paper/figures/{stem}.pdf")
    
    # 生成 _meta.yaml
    meta = {
        "name": stem,
        "source_script": None,  # 由调用者填充
        "chapter": chapter,
        "format": ["pdf", "png"],
        "width": f'{plt.rcParams["figure.figsize"][0]:.1f}in',
    }
    meta_path = FIGURES_DIR / f"{stem}_meta.yaml"
    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)
    
    return pdf_path


if __name__ == "__main__":
    cfg = apply_thesis_style()
    print("Thesis plot style loaded successfully.")
    print(f"  DPI: {plt.rcParams['figure.dpi']}")
    print(f"  Figure size: {plt.rcParams['figure.figsize']}")
    print(f"  Font family: {plt.rcParams['font.family']}")
    print(f"  Font serif: {plt.rcParams.get('font.serif', 'default')}")
    print(f"  Palette: {get_palette()[:5]}...")
