"""
pipeline/scripts/03_extract_results.py
──────────────────────────────────────
从 evaluation/ 目录提取关键实验结果数据，生成汇总 CSV 和 JSON。

输入: data/raw/evaluation/RQ2/results/, RQ5/data/, RQ6/data/
输出: pipeline/tables/results_summary.yaml
"""
import json
import csv
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_DIR = ROOT / "data" / "raw" / "evaluation"
OUT_DIR = ROOT / "pipeline" / "tables"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_rq2_results():
    """RQ2: 识别有效性 — 从 JSON 结果文件提取。"""
    rq2_dir = EVAL_DIR / "RQ2" / "results"
    if not rq2_dir.exists():
        return {}
    
    results = {}
    for jf in sorted(rq2_dir.glob("*.json")):
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        results[jf.stem] = data
    
    return results


def extract_rq5_ablation():
    """RQ5: 消融实验 — 从 JSON 结果文件提取。"""
    rq5_dir = EVAL_DIR / "RQ5" / "data"
    if not rq5_dir.exists():
        return {}
    
    results = {}
    for jf in sorted(rq5_dir.glob("*.json")):
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        results[jf.stem] = data
    
    return results


def extract_rq6_efficiency():
    """RQ6: 效率 — 从 CSV/JSON 提取。"""
    rq6_dir = EVAL_DIR / "RQ6" / "data"
    if not rq6_dir.exists():
        return {}
    
    results = {}
    for f in sorted(rq6_dir.iterdir()):
        if f.suffix == ".json":
            with open(f, "r", encoding="utf-8") as fh:
                results[f.stem] = json.load(fh)
        elif f.suffix == ".csv":
            with open(f, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                results[f.stem] = [row for row in reader]
    
    return results


def extract_family_stats():
    """Ch4: 家族分析统计 — 从 results/ 目录提取。"""
    family_dir = ROOT / "data" / "raw" / "chapter2_family_analysis" / "results"
    if not family_dir.exists():
        return {}
    
    results = {}
    for f in sorted(family_dir.glob("*.csv")):
        with open(f, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = [row for row in reader]
            results[f.stem] = {
                "num_rows": len(rows),
                "columns": list(rows[0].keys()) if rows else [],
                "sample": rows[:3] if rows else [],
            }
    
    return results


def main():
    print("=" * 60)
    print("提取实验结果数据")
    print("=" * 60)
    
    summary = {}
    
    # RQ2
    print("\n── RQ2: 识别有效性 ──")
    rq2 = extract_rq2_results()
    print(f"  提取 {len(rq2)} 个结果文件")
    for k in list(rq2.keys())[:5]:
        print(f"    {k}")
    if len(rq2) > 5:
        print(f"    ... 共 {len(rq2)} 个")
    summary["RQ2_effectiveness"] = {
        "num_results": len(rq2),
        "result_files": list(rq2.keys()),
    }
    
    # RQ5
    print("\n── RQ5: 消融实验 ──")
    rq5 = extract_rq5_ablation()
    print(f"  提取 {len(rq5)} 个消融配置")
    for k in rq5:
        print(f"    {k}")
    summary["RQ5_ablation"] = {
        "num_configs": len(rq5),
        "configs": list(rq5.keys()),
    }
    
    # RQ6
    print("\n── RQ6: 效率 ──")
    rq6 = extract_rq6_efficiency()
    print(f"  提取 {len(rq6)} 个效率数据文件")
    for k in rq6:
        print(f"    {k}")
    summary["RQ6_efficiency"] = {
        "num_files": len(rq6),
        "files": list(rq6.keys()),
    }
    
    # Family analysis
    print("\n── Ch4: 家族分析统计 ──")
    family = extract_family_stats()
    print(f"  提取 {len(family)} 个统计结果文件")
    for k, v in family.items():
        print(f"    {k}: {v['num_rows']} rows × {len(v['columns'])} cols")
    summary["Ch4_family_analysis"] = {
        "num_files": len(family),
        "files": {k: {"rows": v["num_rows"], "cols": len(v["columns"])} for k, v in family.items()},
    }
    
    # 保存汇总
    out_path = OUT_DIR / "results_summary.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(summary, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    print(f"\n汇总已保存: {out_path.relative_to(ROOT)}")
    
    return summary


if __name__ == "__main__":
    main()
