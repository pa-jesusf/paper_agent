"""
pipeline/scripts/02_collect_figures.py
──────────────────────────────────────
收集和编目论文所需图表。

策略：
- Ch4 家族分析图表：已有 data/raw/chapter2_family_analysis/figures/ (26张)，直接复制
- Ch3/Ch5 方法/实验图表：已有 data/raw/paper/fig/ (PDF)，直接复制
- Ch1 示例图：从 data/raw/paper/fig/ 复制
- 为每张图生成 _meta.yaml

输入: data/raw/paper/fig/, data/raw/chapter2_family_analysis/figures/, data/raw/evaluation/RQ1/
输出: pipeline/figures/, paper/figures/
"""
from pathlib import Path
import shutil
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_FIG = ROOT / "pipeline" / "figures"
PAPER_FIG = ROOT / "paper" / "figures"
PIPELINE_FIG.mkdir(parents=True, exist_ok=True)
PAPER_FIG.mkdir(parents=True, exist_ok=True)

# ── 图表清单 ──────────────────────────────────────────────

# Ch1 绪论
CH1_FIGURES = {
    "example.pdf": {
        "name": "fig_01_motivating_example",
        "caption_zh": "休眠勒索软件行为示例",
        "caption_en": "Motivating Example of Dormant Ransomware Behavior",
    },
}

# Ch3 知识库构建
CH3_FIGURES = {
    "overview.pdf": {
        "name": "fig_03_system_overview",
        "caption_zh": "恶意软件攻防行为知识库构建与语义识别总体框架",
        "caption_en": "Overall Framework of Knowledge Base Construction and Semantic Identification",
    },
    "encryption_behavior.pdf": {
        "name": "fig_03_encryption_behavior",
        "caption_zh": "加密行为分析示例",
        "caption_en": "Encryption Behavior Analysis Example",
    },
    "unpacking.pdf": {
        "name": "fig_03_unpacking_pipeline",
        "caption_zh": "动态解包处理流程",
        "caption_en": "Dynamic Unpacking Pipeline",
    },
    "prompt.pdf": {
        "name": "fig_03_llm_prompt",
        "caption_zh": "LLM三阶段识别提示词设计",
        "caption_en": "LLM Three-stage Identification Prompt Design",
    },
    "veen.pdf": {
        "name": "fig_03_venn_diagram",
        "caption_zh": "三层知识库覆盖范围韦恩图",
        "caption_en": "Venn Diagram of Three-layer Knowledge Base Coverage",
    },
}

# Ch5 PolarCatch
CH5_FIGURES = {
    "boxplot.pdf": {
        "name": "fig_05_feature_boxplot",
        "caption_zh": "特征可区分性箱线图",
        "caption_en": "Feature Discriminability Boxplot",
    },
    "tsne.pdf": {
        "name": "fig_05_tsne",
        "caption_zh": "t-SNE特征可视化",
        "caption_en": "t-SNE Feature Visualization",
    },
    "value.pdf": {
        "name": "fig_05_value_distribution",
        "caption_zh": "特征值分布",
        "caption_en": "Feature Value Distribution",
    },
}

# Ch4 家族分析 — 从 chapter2_family_analysis/figures/ 复制
CH4_FAMILY_FIGURES = {
    "family_phylogeny_network": {
        "name": "fig_04_family_phylogeny",
        "caption_zh": "勒索软件家族谱系网络图",
        "caption_en": "Ransomware Family Phylogeny Network",
    },
    "rq1_behavior_heatmap": {
        "name": "fig_04_rq1_behavior_heatmap",
        "caption_zh": "家族攻防行为画像热力图",
        "caption_en": "Family Behavior Profile Heatmap",
    },
    "rq1_polar_scatter": {
        "name": "fig_04_rq1_polar_scatter",
        "caption_zh": "家族攻防极性散点图",
        "caption_en": "Family O-D Polarity Scatter Plot",
    },
    "rq1_radar_chart": {
        "name": "fig_04_rq1_radar",
        "caption_zh": "代表性家族行为画像雷达图",
        "caption_en": "Representative Family Behavior Radar Chart",
    },
    "rq2_callgraph_boxplots": {
        "name": "fig_04_rq2_callgraph_boxplots",
        "caption_zh": "函数调用图拓扑指标箱线图",
        "caption_en": "Call Graph Topology Metric Boxplots",
    },
    "rq2_cv_comparison": {
        "name": "fig_04_rq2_cv_comparison",
        "caption_zh": "五折交叉验证稳定性对比",
        "caption_en": "5-Fold Cross-Validation Comparison",
    },
    "rq2_graph_scale_histogram": {
        "name": "fig_04_rq2_graph_scale",
        "caption_zh": "图规模分布直方图",
        "caption_en": "Graph Scale Distribution Histogram",
    },
    "rq2_nodes_by_family_log": {
        "name": "fig_04_rq2_nodes_by_family",
        "caption_zh": "各家族节点数量分布（对数尺度）",
        "caption_en": "Node Count by Family (Log Scale)",
    },
    "rq2_od_violin_comparison": {
        "name": "fig_04_rq2_od_violin",
        "caption_zh": "攻击性/防御性子图拓扑小提琴图",
        "caption_en": "O/D Subgraph Topology Violin Plot",
    },
    "rq3_coverage_heatmap": {
        "name": "fig_04_rq3_coverage_heatmap",
        "caption_zh": "三层知识库家族覆盖热力图",
        "caption_en": "Three-layer Knowledge Base Family Coverage Heatmap",
    },
    "rq3_feature_heatmap": {
        "name": "fig_04_rq3_feature_heatmap",
        "caption_zh": "特征值分布热力图",
        "caption_en": "Feature Value Distribution Heatmap",
    },
    "rq3_feature_importance_top20": {
        "name": "fig_04_rq3_importance_top20",
        "caption_zh": "Top-20特征判别力排序",
        "caption_en": "Top-20 Feature Discriminability Ranking",
    },
    "rq3_group_discriminability": {
        "name": "fig_04_rq3_group_discriminability",
        "caption_zh": "特征组判别力对比",
        "caption_en": "Feature Group Discriminability Comparison",
    },
}

# RQ1 evaluation figures
RQ1_FIGURES = {
    "Fig4.pdf": {
        "name": "fig_05_rq1_feature_analysis_1",
        "caption_zh": "RQ1特征分析图（一）",
        "caption_en": "RQ1 Feature Analysis Figure 1",
        "src_dir": "evaluation/RQ1",
    },
    "Fig5.pdf": {
        "name": "fig_05_rq1_feature_analysis_2",
        "caption_zh": "RQ1特征分析图（二）",
        "caption_en": "RQ1 Feature Analysis Figure 2",
        "src_dir": "evaluation/RQ1",
    },
}


def copy_figure(src_path: Path, name: str, meta: dict, chapter: int):
    """复制图表并生成元信息。"""
    if not src_path.exists():
        return False
    
    suffix = src_path.suffix
    dst_pipeline = PIPELINE_FIG / f"{name}{suffix}"
    dst_paper = PAPER_FIG / f"{name}{suffix}"
    
    shutil.copy2(src_path, dst_pipeline)
    shutil.copy2(src_path, dst_paper)
    
    # 同时复制 PNG 版本（如果有）
    png_src = src_path.with_suffix(".png")
    if png_src.exists():
        shutil.copy2(png_src, PIPELINE_FIG / f"{name}.png")
    
    # 生成 _meta.yaml
    meta_info = {
        "name": name,
        "chapter": chapter,
        "caption_zh": meta["caption_zh"],
        "caption_en": meta["caption_en"],
        "source": str(src_path.relative_to(ROOT)),
        "format": suffix.lstrip("."),
        "adaptation_needed": ["中文坐标轴标签", "全宽6.0in", f"图{chapter}-X编号"],
    }
    meta_path = PIPELINE_FIG / f"{name}_meta.yaml"
    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(meta_info, f, allow_unicode=True, default_flow_style=False)
    
    return True


def main():
    print("=" * 60)
    print("收集论文图表")
    print("=" * 60)
    
    stats = {"copied": 0, "skipped": 0}
    
    # Ch1
    print("\n── 第一章 绪论 ──")
    fig_dir = ROOT / "data" / "raw" / "paper" / "fig"
    for filename, meta in CH1_FIGURES.items():
        src = fig_dir / filename
        if copy_figure(src, meta["name"], meta, chapter=1):
            print(f"  [OK] {filename} → {meta['name']}")
            stats["copied"] += 1
        else:
            print(f"  [SKIP] {filename} — 不存在")
            stats["skipped"] += 1
    
    # Ch3
    print("\n── 第三章 知识库构建 ──")
    for filename, meta in CH3_FIGURES.items():
        src = fig_dir / filename
        if copy_figure(src, meta["name"], meta, chapter=3):
            print(f"  [OK] {filename} → {meta['name']}")
            stats["copied"] += 1
        else:
            print(f"  [SKIP] {filename} — 不存在")
            stats["skipped"] += 1
    
    # Ch4 家族分析
    print("\n── 第四章 家族分析 ──")
    family_fig_dir = ROOT / "data" / "raw" / "chapter2_family_analysis" / "figures"
    for stem, meta in CH4_FAMILY_FIGURES.items():
        # 优先 PDF，其次 PNG
        src = family_fig_dir / f"{stem}.pdf"
        if not src.exists():
            src = family_fig_dir / f"{stem}.png"
        if copy_figure(src, meta["name"], meta, chapter=4):
            print(f"  [OK] {stem} → {meta['name']}")
            stats["copied"] += 1
        else:
            print(f"  [SKIP] {stem} — 不存在")
            stats["skipped"] += 1
    
    # Ch5 PolarCatch — 源论文图
    print("\n── 第五章 PolarCatch（源论文图）──")
    for filename, meta in CH5_FIGURES.items():
        src = fig_dir / filename
        if copy_figure(src, meta["name"], meta, chapter=5):
            print(f"  [OK] {filename} → {meta['name']}")
            stats["copied"] += 1
        else:
            print(f"  [SKIP] {filename} — 不存在")
            stats["skipped"] += 1
    
    # Ch5 RQ1 evaluation figures
    print("\n── 第五章 PolarCatch（评估图）──")
    for filename, meta in RQ1_FIGURES.items():
        src_dir = ROOT / "data" / "raw" / meta.get("src_dir", "")
        src = src_dir / filename
        if copy_figure(src, meta["name"], meta, chapter=5):
            print(f"  [OK] {filename} → {meta['name']}")
            stats["copied"] += 1
        else:
            print(f"  [SKIP] {filename} — 不存在")
            stats["skipped"] += 1
    
    # 统计
    print(f"\n{'=' * 60}")
    print(f"总计: 复制 {stats['copied']} 张图, 跳过 {stats['skipped']} 张")
    
    # 章节分布
    meta_files = list(PIPELINE_FIG.glob("*_meta.yaml"))
    ch_dist = {}
    for mf in meta_files:
        with open(mf, "r", encoding="utf-8") as f:
            m = yaml.safe_load(f)
            ch = m.get("chapter", 0)
            ch_dist[ch] = ch_dist.get(ch, 0) + 1
    
    print("\n图表章节分布:")
    for ch in sorted(ch_dist):
        print(f"  第{ch}章: {ch_dist[ch]}张图")
    
    return stats


if __name__ == "__main__":
    main()
