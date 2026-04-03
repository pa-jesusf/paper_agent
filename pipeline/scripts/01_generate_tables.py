"""
pipeline/scripts/01_generate_tables.py
──────────────────────────────────────
将原始论文 LaTeX 表格转换为同济学位论文格式（三线表、中文标题、按章编号）。

输入: data/raw/paper/table/*.tex
输出: pipeline/tables/*.tex  (thesis-adapted)
      paper/sections/ 中可直接 \\input{} 的表格文件
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_TABLE = ROOT / "data" / "raw" / "paper" / "table"
OUT_TABLE = ROOT / "pipeline" / "tables"
PAPER_DIR = ROOT / "paper"

OUT_TABLE.mkdir(parents=True, exist_ok=True)

# ── 表格映射：源文件 → (论文章节, 表编号, 中文标题) ──────────
TABLE_MAP = {
    "knowledge_base.tex": {
        "chapter": 3,
        "label": "tab:knowledge_base",
        "caption_zh": "知识库结构与行为证据示例",
        "caption_en": "Knowledge Base and Evidence Examples",
        "notes": "跨页表格 → 改为 table* 全宽",
    },
    "encryption_libraries.tex": {
        "chapter": 3,
        "label": "tab:encryption_libraries",
        "caption_zh": "开源加密库及其支持的加密算法",
        "caption_en": "Open-source Encryption Libraries and their Supported Encryption Algorithms",
        "notes": "注释状态的大表 → 可考虑附录或精简",
    },
    "rq_LLMs.tex": {
        "chapter": 3,
        "label": "tab:rq_llm",
        "caption_zh": "多LLM行为语义识别性能对比",
        "caption_en": "Results of LLM Evaluation",
        "notes": "三任务×五LLM → 按章编号 表3-X",
    },
    "rq_effectiveness.tex": {
        "chapter": 5,
        "label": "tab:rq_effectiveness",
        "caption_zh": "恶意软件识别有效性评估结果",
        "caption_en": "Results of Effectiveness Evaluation",
        "notes": "3设置×3比例×4基线 → 大表保持 table*",
    },
    "rq_generalizability.tex": {
        "chapter": 5,
        "label": "tab:rq_generalizability",
        "caption_zh": "泛化性评估结果（时序设置）",
        "caption_en": "Results of Generalizability Evaluation",
        "notes": "时序设置的精确率/召回率",
    },
    "rq_adversarial.tex": {
        "chapter": 5,
        "label": "tab:rq_adversarial",
        "caption_zh": "对抗攻击鲁棒性评估结果",
        "caption_en": "Results of Adversarial Attack Evaluation",
        "notes": "5类攻击 → 中文注释攻击类型",
    },
    "rq_ablation.tex": {
        "chapter": 5,
        "label": "tab:rq_ablation",
        "caption_zh": "消融实验结果",
        "caption_en": "Results of Ablation Study",
        "notes": "预处理+证据识别+架构 三类消融",
    },
}


def adapt_table(src_path: Path, meta: dict) -> str:
    """读取源表格，做基础格式适配。"""
    content = src_path.read_text(encoding="utf-8")
    
    ch = meta["chapter"]
    label = meta["label"]
    cap_zh = meta["caption_zh"]
    cap_en = meta["caption_en"]
    
    # 替换 \tool → PolarCatch
    content = content.replace(r"\tool", r"\textsc{PolarCatch}")
    
    # 替换 \todoccs{...} → 去掉标记
    import re
    content = re.sub(r"\\todoccs\{([^}]*)\}", r"\1", content)
    content = re.sub(r"\\todonew\{([^}]*)\}", r"\1", content)
    
    # 添加中文标题标头注释
    header = f"""% ============================================================
% 表 {ch}-X: {cap_zh}
% Table {ch}-X: {cap_en}
% 来源: data/raw/paper/table/{src_path.name}
% 注意: {meta.get('notes', '')}
% ============================================================
"""
    return header + content


def main():
    print("=" * 60)
    print("生成学位论文表格")
    print("=" * 60)
    
    generated = []
    for filename, meta in TABLE_MAP.items():
        src = SRC_TABLE / filename
        if not src.exists():
            print(f"  [SKIP] {filename} — 源文件不存在")
            continue
        
        adapted = adapt_table(src, meta)
        
        # 保存到 pipeline/tables/
        out_name = f"ch{meta['chapter']:02d}_{meta['label'].replace('tab:', '')}.tex"
        out_path = OUT_TABLE / out_name
        out_path.write_text(adapted, encoding="utf-8")
        
        generated.append({
            "source": filename,
            "output": out_name,
            "chapter": meta["chapter"],
            "caption_zh": meta["caption_zh"],
        })
        print(f"  [OK] {filename} → pipeline/tables/{out_name}")
    
    # 生成汇总
    print(f"\n共生成 {len(generated)} 个表格文件:")
    for g in generated:
        print(f"  Ch{g['chapter']}: {g['caption_zh']} ({g['output']})")
    
    print("\n表格章节分布:")
    from collections import Counter
    ch_count = Counter(g["chapter"] for g in generated)
    for ch, cnt in sorted(ch_count.items()):
        print(f"  第{ch}章: {cnt}个表格")
    
    return generated


if __name__ == "__main__":
    main()
