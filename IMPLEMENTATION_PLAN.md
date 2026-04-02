# Paper Agent —— 论文撰写智能体框架实现计划

> 版本: v1.0 | 日期: 2026-04-02 | 全部 Phase 完成

---

## 一、项目目标

构建一套**面向 LLM Agent 的论文撰写框架**，使 Agent 能够：

- 从原始数据/代码出发，经过中间处理，最终生成结构化的 LaTeX 论文
- 在整个撰写过程中保持**术语、符号、语言风格**的全局一致性
- 正确、主动地使用和管理参考文献
- 通过标准化的工具接口与用户高效协作

---

## 二、整体架构概览

```
paper_agent/
├── .agent/                          # Agent 指令层（Copilot / LLM 指令文件）
│   ├── copilot-instructions.md      # 全局行为准则
│   ├── skills/                      # 可调用的技能定义
│   │   ├── data-processing.md       # 数据处理技能
│   │   ├── figure-generation.md     # 图表生成技能
│   │   ├── latex-writing.md         # LaTeX 撰写技能
│   │   ├── reference-management.md  # 文献管理技能
│   │   ├── review-polish.md         # 审校润色技能
│   │   └── experiment-management.md # 实验管理技能
│   └── agents/                      # 子 Agent 定义
│       ├── researcher.md            # 文献调研 Agent
│       ├── analyst.md               # 数据分析 Agent
│       ├── writer.md                # 论文撰写 Agent
│       ├── reviewer.md              # 审校 Agent
│       └── experimenter.md          # 实验管理 Agent
│
├── config/                          # 全局配置层
│   ├── paper.yaml                   # 论文元信息与全局设置
│   ├── glossary.yaml                # 符号 / 术语表
│   ├── style-guide.md               # 写作风格指南
│   ├── figure-style.yaml            # 图表视觉风格配置
│   └── experiment-env.yaml          # 实验环境描述
│
├── data/                            # 底层数据层（Layer 0）
│   ├── raw/                         # 原始数据文件
│   ├── code/                        # 原始实验 / 算法代码
│   └── drafts/                      # 用户导入的草稿 / 混乱文本
│
├── pipeline/                        # 中层过程层（Layer 1）
│   ├── scripts/                     # 数据处理 / 分析脚本
│   ├── figures/                     # 生成的图表（PDF/PNG/SVG）
│   ├── tables/                      # 生成的表格数据（CSV/LaTeX）
│   └── notes/                       # 分析笔记 / 简要论点
│       ├── findings.md              # 关键发现
│       ├── arguments.md             # 论点梳理
│       └── outline.md               # 论文大纲
│
├── paper/                           # 论文层（Layer 2）— LaTeX
│   ├── main.tex                     # 主入口文件（通过 \input 串联各章节）
│   ├── preamble.tex                 # 宏包 / 命令定义
│   ├── sections/                    # 按章节拆分（结构由 outline.md 驱动，不预设固定章节）
│   │   ├── {NN}-{slug}.tex          # 命名约定：{两位序号}-{章节短名}.tex
│   │   └── ...                      # 示例: 00-abstract.tex, 01-intro.tex, 03-2-loss-design.tex
│   ├── figures/                     # 论文引用的图表（软链或复制）
│   └── references.bib               # BibTeX 文献库
│
├── refs/                            # 参考文献管理层
│   ├── library.yaml                 # 文献元数据 + 摘要索引
│   ├── pdfs/                        # 文献 PDF 存档
│   └── notes/                       # 单篇文献阅读笔记
│       └── {citekey}.md
│
├── tools/                           # 工具层
│   ├── bib_manager.py               # 文献管理工具
│   ├── pdf_extractor.py             # PDF 文献解析与摘录工具
│   ├── figure_builder.py            # 图表生成工具
│   ├── latex_compiler.py            # LaTeX 编译工具
│   ├── glossary_checker.py          # 术语一致性检查
│   ├── paper_lint.py                # 论文质量检查
│   ├── project_init.py              # 交互式项目初始化工具
│   ├── config_validator.py          # 配置校验与自动补全
│   └── commands.py                  # 快捷命令调度器
│
├── IMPLEMENTATION_PLAN.md           # ← 本文件
└── readme.md
```

---

## 三、各层详细设计

### 3.1 底层数据层（Layer 0 — `data/`）

| 子目录 | 用途 | 典型文件 |
|--------|------|---------|
| `raw/` | 实验产出的原始数据 | CSV, JSON, HDF5, 日志文件 |
| `code/` | 算法/实验源码 | Python, C++, Jupyter Notebook |
| `drafts/` | 用户丢进来的草稿和零散笔记 | Markdown, Word 导出文本, 截图 |

**设计原则：**
- 此层文件默认**只读**，仅 **Experimenter Agent** 有写入权限（新增实验、修正数据错误等）
- 任何对 `data/` 的修改必须同步更新 `_manifest.yaml` 并告知用户
- 每个文件建议附带一行描述注释或一个 `_manifest.yaml` 索引文件，帮助 Agent 快速理解文件用途
- 支持用户随时丢入新文件，Agent 通过 manifest 感知变动

```yaml
# data/_manifest.yaml 示例
files:
  - path: raw/experiment_results_v3.csv
    description: "模型A/B/C在CIFAR-10上的accuracy/loss，5次重复实验"
    columns: [model, epoch, accuracy, loss, run_id]
  - path: code/train.py
    description: "主训练脚本，使用PyTorch，含数据增强逻辑"
  - path: drafts/old_intro.md
    description: "之前写的introduction草稿，需要重写"
```

---

### 3.2 中层过程层（Layer 1 — `pipeline/`）

这是 Agent 的**核心工作区**，连接原始数据与最终论文。

#### 3.2.1 处理脚本 (`pipeline/scripts/`)

- 由 Agent 生成或用户提供的数据处理代码
- 每个脚本应有清晰的输入输出注释
- 命名约定：`{序号}_{用途}.py`，如 `01_parse_results.py`、`02_plot_accuracy.py`

#### 3.2.2 图表 (`pipeline/figures/`)

- Agent 生成的所有可视化输出
- 命名约定：`fig_{章节}_{描述}.{格式}`，如 `fig_04_accuracy_comparison.pdf`
- 每张图附带 `_meta.yaml` 记录：数据来源、生成脚本、caption 草案

```yaml
# pipeline/figures/fig_04_accuracy_comparison_meta.yaml
source_script: pipeline/scripts/02_plot_accuracy.py
source_data: data/raw/experiment_results_v3.csv
caption_draft: "Comparison of test accuracy across three models on CIFAR-10."
used_in: paper/sections/05-results.tex
```

#### 3.2.3 分析笔记 (`pipeline/notes/`)

- `outline.md` — 论文大纲，是撰写的核心路线图
- `arguments.md` — 每个章节的核心论点，Agent 撰写前必须参考
- `findings.md` — 数据分析中的关键发现，供 Agent 在写作时引用

---

### 3.3 论文层（Layer 2 — `paper/`）

#### 3.3.1 文件组织

| 文件 | 说明 |
|------|------|
| `main.tex` | 仅做 `\input{}` 串联，不含正文 |
| `preamble.tex` | 所有 `\usepackage`、自定义命令 (`\newcommand`)、符号宏 |
| `sections/{NN}-{slug}.tex` | 每小节一个文件，以数字前缀排序，**结构由 `pipeline/notes/outline.md` 驱动** |
| `references.bib` | 由工具从 `refs/library.yaml` 自动同步生成 |

**章节划分原则：**
- 不预设固定章节列表，由用户在 `outline.md` 中定义实际结构
- 命名约定：`{两位序号}-{短名}.tex`，支持子章节如 `03-1-overview.tex`、`03-2-loss-design.tex`
- `main.tex` 中的 `\input{}` 顺序与 `outline.md` 保持同步
- 新增/删除/重排章节时，Agent 同步更新 `main.tex` 和 `outline.md`

#### 3.3.2 LaTeX 约定

- 所有符号必须使用 `preamble.tex` 中定义的宏，禁止在正文中硬编码数学符号
  - 例：定义 `\newcommand{\loss}{\mathcal{L}}` 后，正文使用 `\loss` 而非 `\mathcal{L}`
- 图表使用 `\label{fig:xxx}` / `\ref{fig:xxx}`，由 Agent 维护引用一致性
- 引用使用 `\cite{citekey}`，citekey 必须存在于 `references.bib`

---

### 3.4 全局配置层（`config/`）

#### 3.4.1 论文元配置 (`config/paper.yaml`)

```yaml
# 论文基本信息
title: "Your Paper Title"
authors:
  - name: "Author Name"
    affiliation: "University"
    email: "author@example.edu"
venue: "NeurIPS 2026"          # 投稿会议/期刊，影响格式要求
language: "chinese"             # 撰写语言（chinese | english）
page_limit: 9                   # 正文页数限制（不含参考文献）

# 多语言设置
i18n:
  primary: "chinese"            # 主要撰写语言
  secondary: "english"          # 辅助语言（摘要双语、术语原文标注等）
  abstract_bilingual: true      # 是否生成中英双语摘要
  term_original_annotation: true # 首次出现术语时附注英文原文

# 写作风格
style:
  tone: "formal-academic"       # formal-academic | technical-concise | expository
  person: "first-plural"       # first-plural ("我们") | passive | third-person
  tense: "present"             # 方法/结果描述的默认时态
  paragraph_style: "topic-sentence-first"  # 每段首句概括观点

# LaTeX 编译
latex:
  compiler: "xelatex"          # 使用 xelatex 以支持中文
  bibliography: "bibtex"       # bibtex | biber
  template: "neurips_2026"     # 模版名称
  cjk_package: "ctex"          # 中文支持宏包
```

#### 3.4.2 术语 / 符号表 (`config/glossary.yaml`)

```yaml
# 术语统一 —— Agent 在写作时必须使用统一的术语
terms:
  - canonical: "large language model"
    abbreviation: "LLM"
    first_use: "large language model (LLM)"    # 首次出现的写法
    forbidden_variants:                         # 禁止使用的表述
      - "big language model"
      - "large-scale language model"
    
  - canonical: "fine-tuning"
    forbidden_variants:
      - "finetuning"
      - "fine tuning"

# 数学符号 —— 与 preamble.tex 中的 \newcommand 对应
symbols:
  - name: "loss function"
    latex_macro: "\\loss"
    definition: "\\mathcal{L}"
    description: "The overall training loss"
    
  - name: "model parameters"
    latex_macro: "\\params"
    definition: "\\theta"
    description: "Learnable parameters of the model"
    
  - name: "dataset"
    latex_macro: "\\dataset"
    definition: "\\mathcal{D}"
    description: "The training dataset"

# Agent 可提议新增术语/符号，但需经用户确认后写入此文件
```

#### 3.4.3 实验环境 (`config/experiment-env.yaml`)

```yaml
hardware:
  gpu: "NVIDIA A100 80GB × 4"
  cpu: "AMD EPYC 7763 64-Core"
  memory: "512 GB"
  
software:
  os: "Ubuntu 22.04"
  python: "3.10.12"
  pytorch: "2.1.0"
  cuda: "12.1"
  key_libraries:
    - name: transformers
      version: "4.35.0"
    - name: numpy
      version: "1.24.3"

training:
  total_time: "~48 hours"
  batch_size: 64
  optimizer: "AdamW"
  learning_rate: 3e-4
  
# Agent 在撰写实验部分时必须引用此文件中的信息
```

#### 3.4.4 图表视觉风格配置 (`config/figure-style.yaml`)

**核心原则：优先继承用户导入的原始数据中已有的图表风格**，确保新生成图表与已有图表视觉一致。

```yaml
# 图表视觉风格配置
# Agent 在首次处理用户导入的图表时，应分析其风格并自动填充此文件

source_style:
  inherited_from: "data/raw/original_figures/"  # 风格参考来源
  analysis_notes: >                              # Agent 分析原始图表后的风格总结
    用户原始图表使用蓝-橙配色，无网格线，
    标题使用 12pt 加粗，坐标轴标签 10pt。

colors:
  palette: ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
  background: "white"
  grid_color: "#e0e0e0"
  
fonts:
  family: "serif"             # 与 LaTeX 正文字体一致
  title_size: 12
  label_size: 10
  tick_size: 9
  legend_size: 9

layout:
  dpi: 300
  single_column_width: 3.5    # 英寸
  double_column_width: 7.0
  default_format: "pdf"       # pdf | svg | png
  grid_visible: false
  spine_visible: ["bottom", "left"]

# Agent 在生成图表时必须读取此配置
# 当用户导入新图表时，Agent 应比对并提议更新此配置
```

#### 3.4.5 写作风格指南 (`config/style-guide.md`)

以自然语言撰写的详细写作规范，内容包括但不限于：

- 段落结构偏好（先结论后论据、Topic sentence 开头等）
- 过渡句使用策略
- 数字/百分比的表示方式（"5%" vs "百分之五"）
- 表格/图表引用的措辞模板
- 禁止使用的短语清单（如"近年来"等套话）
- 各章节的长度指导
- 中文学术写作规范（标点使用、中英文混排间距等）
- 术语首次出现时的英文原文标注格式
- 特殊行文偏好（由用户迭代补充）

---

### 3.5 参考文献管理（`refs/`）

#### 3.5.1 核心数据结构 (`refs/library.yaml`)

```yaml
references:
  - citekey: "vaswani2017attention"
    title: "Attention Is All You Need"
    authors: ["Vaswani, A.", "Shazeer, N.", "Parmar, N.", "..."]
    year: 2017
    venue: "NeurIPS"
    doi: "10.48550/arXiv.1706.03762"
    
    # 以下字段是核心价值：帮助 Agent 决定何时引用
    abstract_summary: >
      提出 Transformer 架构，完全基于注意力机制，
      摒弃了 RNN/CNN，在机器翻译任务上取得 SOTA。
    relevance: >
      本文方法的基础架构。在 Method 和 Related Work 中必须引用。
    tags: ["transformer", "attention", "architecture", "foundational"]
    
    # 关键原文摘录 —— 防止 LLM 引用时无中生有
    key_quotes:
      - id: "q1"
        text: "The Transformer is the first transduction model relying entirely on self-attention to compute representations of its input and output without using sequence-aligned RNNs or convolution."
        page: 2
        context: "架构创新点的核心声明"
      - id: "q2"
        text: "Multi-head attention allows the model to jointly attend to information from different representation subspaces at different positions."
        page: 4
        context: "多头注意力机制的定义"
    
    pdf_path: "refs/pdfs/vaswani2017attention.pdf"  # 本地 PDF 路径
    
    # BibTeX 原始条目（用于同步到 references.bib）
    bibtex: |
      @inproceedings{vaswani2017attention,
        title={Attention is all you need},
        author={Vaswani, Ashish and Shazeer, Noam and ...},
        booktitle={NeurIPS},
        year={2017}
      }
```

#### 3.5.2 文献阅读笔记 (`refs/notes/{citekey}.md`)

```markdown
# vaswani2017attention — Attention Is All You Need

## 核心贡献
- 提出 Transformer，首个纯注意力序列转换模型
- Multi-head attention 机制
- Positional encoding 处理序列位置信息

## 与本文的关系
- 本文方法基于 Transformer 架构进行改进
- 可在 Introduction 中作为背景引用
- 在 Method 3.1 节中需详细对比

## 可引用的关键数据
- WMT 2014 EN-DE: 28.4 BLEU
- WMT 2014 EN-FR: 41.0 BLEU

## 关键原文与引用映射
| 引用场景 | 原文摘录 (quote id) | 我们论文中的表述建议 |
|---------|---------------------|----------------------|
| Method 3.1: 说明基于 Transformer | q1 | "本文方法基于 Transformer 架构 \cite{vaswani2017attention}，其完全依赖自注意力机制..." |
| Related Work: 多头注意力 | q2 | "多头注意力机制 (Multi-head Attention) 允许模型在不同表示子空间中联合关注信息 \cite{vaswani2017attention}" |

> **注意**：每条引用必须能追溯到 key_quotes 中的原文。禁止编造原文未提及的论断。

## 引用建议
- Related Work: 介绍 Transformer 架构背景
- Method: 对比本文与原始 Transformer 的差异
```

#### 3.5.3 文献管理工具 (`tools/bib_manager.py`)

提供以下核心功能：

| 功能 | 说明 |
|------|------|
| `add_reference(bibtex, summary, relevance)` | 添加文献到 library.yaml 并同步 .bib |
| `add_from_pdf(pdf_path)` | 从 PDF 自动提取元信息、摘要、关键原文，创建完整文献条目 |
| `search_local(query)` | 在已有文献中语义搜索，返回相关文献 |
| `search_online(query)` | 调用 Semantic Scholar / CrossRef API 搜索新文献 |
| `sync_bib()` | 从 library.yaml 同步生成 references.bib |
| `suggest_citations(text)` | 给定一段文本，建议可插入的引用（附带 key_quotes 溯源） |
| `validate_citations(tex_file)` | 检查 tex 文件中所有 \cite{} 是否存在于 .bib 中 |
| `get_reference_summary(citekey)` | 获取文献摘要、关键原文和引用建议 |
| `get_quote(citekey, quote_id)` | 获取指定文献的指定原文摘录，用于引用溯源 |

---

### 3.6 工具层（`tools/`）

#### 3.6.1 工具清单

| 工具 | 功能 | Agent 调用场景 |
|------|------|---------------|
| `bib_manager.py` | 文献增删查改、同步 .bib、引用溯源 | 写作过程中需要引用时 |
| `pdf_extractor.py` | PDF 解析、关键原文提取、元信息抽取 | 导入新文献 PDF 时 |
| `figure_builder.py` | 封装 matplotlib/seaborn 图表生成（自动继承风格） | 从数据生成论文图表 |
| `latex_compiler.py` | 编译 LaTeX（xelatex），返回错误信息 | 完成章节后验证编译 |
| `glossary_checker.py` | 扫描 tex 文件，检查术语/符号一致性 | 每次撰写完成后自动运行 |
| `paper_lint.py` | 综合质量检查（引用完整性、图表引用、引用溯源等） | 提交前全面检查 |
| `project_init.py` | 交互式初始化 + 配置完备性检查 + 回归追问 | 项目初始化、任意时刻检查配置 |

#### 3.6.2 图表生成工具 (`tools/figure_builder.py`)

```python
# 设计思路：提供高层 API，Agent 只需描述意图
class FigureBuilder:
    def __init__(self, style_config="config/figure-style.yaml"):
        """初始化时加载全局图表风格配置"""
        ...
    
    def analyze_user_figures(self, figure_dir="data/raw/"):
        """分析用户导入的原始图表，提取风格特征，更新 figure-style.yaml"""
        ...
    
    def plot_comparison_bar(self, data, x, y, hue, caption, save_as): ...
    def plot_line_chart(self, data, x, y, series, caption, save_as): ...
    def plot_ablation_table(self, data, metrics, caption, save_as): ...
    def plot_architecture_diagram(self, spec, caption, save_as): ...
    
    # 统一风格：自动应用论文级排版
    # - 从 figure-style.yaml 读取配色方案、字体、布局等
    # - 优先继承用户已有图表的视觉风格
    # - 新图表与已有图表保持一致
    # - 当用户导入新图表时，自动比对并提议更新风格配置
```

#### 3.6.3 PDF 文献解析工具 (`tools/pdf_extractor.py`)

从文献 PDF 中自动提取结构化信息，是防止 LLM 引用时"无中生有"的关键工具。

```python
class PDFExtractor:
    def extract_metadata(self, pdf_path) -> dict:
        """提取标题、作者、年份、DOI 等元信息"""
        ...
    
    def extract_abstract(self, pdf_path) -> str:
        """提取摘要文本"""
        ...
    
    def extract_key_quotes(self, pdf_path, focus_topics=None) -> list:
        """提取关键原文段落，保留页码和上下文
        
        返回格式:
        [{
            "id": "q1",
            "text": "原文内容...",
            "page": 3,
            "section": "3.2 Method",
            "context": "该段落讨论的主题"
        }]
        """
        ...
    
    def extract_figures_tables(self, pdf_path) -> list:
        """提取图表的 caption 和位置信息"""
        ...
    
    def build_library_entry(self, pdf_path) -> dict:
        """一键生成完整的 library.yaml 条目（含 key_quotes）"""
        ...
```

**引用溯源链路：**
```
PDF 原文  ──提取──→  key_quotes (library.yaml)
                           ↓
                    refs/notes/{citekey}.md 引用映射表
                           ↓
                    paper/sections/*.tex 中的 \cite{}
```

Agent 在写作中每次使用 `\cite{}` 时，必须能指出对应的 `key_quote` ID，确保引用有据可查。

#### 3.6.4 术语一致性检查 (`tools/glossary_checker.py`)

```
输入: paper/sections/*.tex + config/glossary.yaml
输出: 
  [WARN] sections/03-method.tex:42 — "finetuning" → 应使用 "fine-tuning"
  [WARN] sections/04-experiments.tex:18 — 首次使用 "LLM" 未展开全称
  [WARN] sections/05-results.tex:7 — 直接使用 "\mathcal{L}"，应使用 "\loss" 宏
  [OK] 所有符号宏使用一致 ✓
```

---

## 四、Agent 指令层设计（`.agent/`）

### 4.1 全局指令 (`.agent/copilot-instructions.md`)

为 Agent 定义全局行为准则：

```markdown
## 核心工作流
1. 任何写作任务前，先读取 config/ 下的全部配置
2. 撰写前检查 pipeline/notes/outline.md 和 arguments.md
3. 使用符号时只使用 glossary.yaml 中定义的宏
4. 引用文献时先搜索 refs/library.yaml，不确定时调用搜索工具
5. 完成章节后运行 glossary_checker 和 paper_lint

## 禁止事项
- 禁止编造实验数据或未在 data/ 中存在的结果
- 禁止使用 glossary.yaml 中 forbidden_variants 列出的术语
- 禁止在正文中硬编码数学符号（必须使用 preamble.tex 中的宏）
- 禁止引用不存在于 references.bib 中的文献
- 禁止引用时编造原文未提及的论断（必须有 key_quotes 溯源）
- 中文论文中术语首次出现时必须附注英文原文
```

### 4.2 子 Agent 角色

| Agent | 职责 | 主要操作范围 |
|-------|------|-------------|
| **Researcher** | 文献调研、阅读、生成阅读笔记 | `refs/`, `pipeline/notes/` |
| **Analyst** | 数据处理、生成图表与表格 | `data/` → `pipeline/` |
| **Writer** | 撰写 LaTeX 正文 | `pipeline/notes/` → `paper/sections/` |
| **Reviewer** | 审校润色、一致性检查、质量报告 | `paper/`, `config/`, `tools/` |

---

## 五、用户交互设计

### 5.0 交互式项目初始化（`初始化` 命令）

用户首次导入数据/代码后，Agent 启动**多轮交互式初始化流程**，帮助用户快速配置项目。

#### 5.0.1 初始化流程

```
用户执行: 初始化
         │
         ▼
┌─ Round 1: 自动分析 ──────────────────────────────────┐
│  Agent 扫描 data/ 下所有文件                           │
│  → 识别数据类型、代码框架、已有草稿                      │
│  → 自动生成 data/_manifest.yaml                       │
│  → 推断论文可能的研究方向和领域                          │
└──────────────────────────────────────────────────────┘
         │
         ▼
┌─ Round 2: 核心问题（必答） ──────────────────────────────┐
│  Q1. 论文标题（或暂定方向）                               │
│  Q2. 投稿目标（会议/期刊/学位论文）                        │
│  Q3. 撰写语言偏好（中文/英文/双语）                        │
│  Q4. 作者信息                                            │
│  Q5. 论文大致章节结构（或选择"由 Agent 建议"）             │
│  → 用户回答后，Agent 填充 config/paper.yaml              │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Round 3: 基于分析的追问（Agent 自主决定） ─────────────────┐
│  Agent 根据 Round 1 的数据分析结果和 Round 2 的回答，       │
│  动态生成需要进一步确认的问题，例如：                        │
│                                                           │
│  [若检测到实验代码] → 询问实验环境细节、关键超参数            │
│  [若检测到多组结果] → 询问哪些是主实验、哪些是消融实验         │
│  [若检测到已有图表] → 展示并确认图表风格是否要继承            │
│  [若检测到草稿文本] → 询问哪些内容要保留、哪些要重写          │
│  [若研究领域明确]   → 提议初始术语表，请用户确认/修改         │
│  [若有 PDF 文献]    → 询问是否自动提取并建立文献库            │
│                                                           │
│  → 填充对应配置文件                                        │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌─ Round 4..N: 回归追问循环 ────────────────────────────────┐
│  Agent 检查所有配置文件的完成度，决定是否还需追问：           │
│                                                           │
│  completeness_check():                                    │
│    - paper.yaml    → 必填字段是否完整？                     │
│    - glossary.yaml → 是否有初始术语/符号？                  │
│    - experiment-env.yaml → 实验环境是否已记录？              │
│    - figure-style.yaml   → 是否确定了图表风格？              │
│    - style-guide.md      → 写作风格是否有特殊偏好？          │
│    - outline.md          → 大纲是否已生成？                  │
│                                                           │
│  若有缺失 → 生成针对性问题继续询问                           │
│  若已完备 → 生成初始化摘要报告，结束初始化                    │
└──────────────────────────────────────────────────────────┘
         │
         ▼
┌─ 初始化完成 ─────────────────────────────────────────────┐
│  输出: 项目初始化报告                                      │
│  ┌─────────────────────────────────────────────────┐     │
│  │ ✓ 数据层: 识别 12 个文件，manifest 已生成          │     │
│  │ ✓ 配置层: paper.yaml, glossary.yaml 等已填充      │     │
│  │ ✓ 论文层: main.tex 骨架已创建，含 7 个章节        │     │
│  │ ✓ 文献库: 从 3 篇 PDF 中提取了初始文献条目         │     │
│  │ ⚠ 待完善: experiment-env.yaml 中 GPU 型号待确认    │     │
│  │ 建议下一步: "写大纲" 或 "分析 raw/results.csv"     │     │
│  └─────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────┘
```

#### 5.0.2 回归追问机制

Agent 内置一个**配置完备性检查器**，在初始化过程中和后续任意时刻均可调用：

```python
# tools/project_init.py 核心逻辑

class ProjectInitializer:
    def scan_data_layer(self) -> dict:
        """扫描 data/ 下所有文件，推断类型和用途"""
        ...
    
    def generate_core_questions(self, scan_result) -> list:
        """根据扫描结果生成 Round 2 核心问题"""
        ...
    
    def generate_followup_questions(self, scan_result, user_answers) -> list:
        """根据已有信息动态生成 Round 3 追问
        
        Agent (LLM) 在此步骤中分析：
        1. 扫描到了什么类型的数据 → 需要询问什么
        2. 用户已经回答了什么 → 还缺什么
        3. 哪些配置文件还有空白字段 → 如何引导用户补充
        """
        ...
    
    def check_completeness(self) -> dict:
        """检查所有配置的完备性，返回缺失项和建议问题
        
        返回格式:
        {
            "complete": ["paper.yaml", "glossary.yaml"],
            "incomplete": [
                {
                    "file": "experiment-env.yaml",
                    "missing": ["gpu", "training.total_time"],
                    "suggested_question": "请提供训练使用的 GPU 型号和总训练时长"
                }
            ],
            "overall_readiness": 0.85  # 0-1，项目就绪度
        }
        """
        ...
    
    def generate_init_report(self) -> str:
        """生成初始化摘要报告"""
        ...
```

#### 5.0.3 设计要点

- **渐进式而非一次性问卷**：不会一次抛出 20 个问题，而是分轮次、根据上下文动态追问
- **可中断可恢复**：用户可以随时中断初始化，已回答的内容已写入配置文件；下次执行 `初始化` 时自动从断点继续
- **智能跳过**：对于已有信息（如代码中的 `requirements.txt` 可推断软件环境），Agent 直接填充并请用户确认，而非重新询问
- **后续可重入**：项目进行中任何时候执行 `检查配置` 命令，Agent 重新运行 `check_completeness()` 并补充追问

### 5.1 快捷命令体系

为用户提供简洁的高层指令，Agent 自动编排底层操作：

| 用户指令 | Agent 行为 |
|---------|-----------|
| `初始化` | 扫描 data/ → 交互式多轮问答 → 填充所有配置 → 生成报告 |
| `检查配置` | 运行 completeness_check → 补充追问缺失项 |
| `写 introduction` | 读取 outline + arguments → 查找相关文献 → 撰写对应 .tex |
| `分析 raw/results.csv` | 读取数据 → 生成处理脚本 → 产出图表 → 记录发现 |
| `添加文献 "attention is all you need"` | 在线搜索 → 获取 BibTeX → 生成摘要 → 写入 library.yaml → 同步 .bib |
| `检查全文` | 运行 glossary_checker + paper_lint → 输出诊断报告 |
| `编译论文` | 调用 latex_compiler → 返回编译结果/错误 |
| `更新术语表` | 扫描全文 → 发现不一致 → 提议修改 → 等待用户确认 |
| `补充实验 X` | 定位实验章节 → 从数据中提取结果 → 更新图表和正文 |

### 5.2 渐进式写作工作流

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 0: 项目初始化（交互式）                                 │
│  用户导入数据/代码 → Agent 扫描分析 → 多轮交互问答             │
│  → 填充配置文件 → 回归追问直到配置完备 → 生成初始化报告         │
├─────────────────────────────────────────────────────────────┤
│  Phase 1: 调研与规划                                          │
│  Researcher Agent 调研文献 → 构建 outline.md + arguments.md   │
├─────────────────────────────────────────────────────────────┤
│  Phase 2: 数据处理                                            │
│  Analyst Agent 处理数据 → 生成图表/表格 → 记录 findings.md     │
├─────────────────────────────────────────────────────────────┤
│  Phase 3: 分章撰写                                            │
│  Writer Agent 按大纲逐章撰写 → 插入引用和图表引用              │
├─────────────────────────────────────────────────────────────┤
│  Phase 4: 审校迭代                                            │
│  Reviewer Agent 全面检查 → 生成修改建议 → 用户审批 → 修订      │
├─────────────────────────────────────────────────────────────┤
│  Phase 5: 终稿输出                                            │
│  最终编译 → 格式检查 → 页数限制检查 → 输出 PDF                 │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 反馈循环机制

- **Agent → 用户**：每完成一个章节，自动生成摘要，标注不确定之处（用 `[TODO]` / `[CONFIRM]` 标记）
- **用户 → Agent**：用户在 tex 文件中用 `% FEEDBACK: ...` 注释给出修改意见，Agent 识别并处理
- **自动检查点**：关键节点（大纲确定、每章完成、全文审校）自动暂停等待用户确认

---

## 六、实现路线图

### Phase 1 — 骨架搭建（基础可用） ✅

- [x] 创建完整目录结构
- [x] 实现 `project_init.py`（交互式初始化 + 配置完备性检查 + 回归追问）
- [x] 编写配置文件模板（paper.yaml, glossary.yaml, experiment-env.yaml, figure-style.yaml）
- [x] 编写 style-guide.md 模板
- [x] 创建 LaTeX 骨架（main.tex, preamble.tex）
- [x] 创建 `data/_manifest.yaml` 模板
- [x] 编写 Agent 全局指令文件

### Phase 2 — 工具开发 ✅

- [x] 实现 `pdf_extractor.py`（PDF 解析 + 关键原文提取 + 元信息抽取）
- [x] 实现 `bib_manager.py`（文献增删查改 + .bib 同步 + 引用溯源）
- [x] 实现 `glossary_checker.py`（术语/符号一致性扫描）
- [x] 实现 `latex_compiler.py`（xelatex 编译封装 + 错误解析）
- [x] 实现 `figure_builder.py`（风格继承 + 统一图表生成）
- [x] 实现 `paper_lint.py`（综合质量检查 + 引用溯源验证）

### Phase 3 — Agent 角色定义 ✅

- [x] 编写 Researcher / Analyst / Writer / Reviewer / Experimenter 的 Agent 定义文件
- [x] 定义各 Agent 的 Skill 文件（含 experiment-management）
- [x] 测试 Agent 在各阶段的工作流（`tests/test_workflow.py`）

### Phase 4 — 集成与优化 ✅

- [x] 端到端测试：从原始数据到 PDF 输出（`tests/test_e2e.py`）
- [x] 用户体验优化：快捷命令调度器（`tools/commands.py`）
- [x] 配置文件的校验与自动补全（`tools/config_validator.py`）

---

## 七、设计理念补充说明

### 7.1 为什么需要 `library.yaml` 而不只是 `.bib`？

BibTeX 文件只包含格式化引用信息，LLM 无法从中理解**何时该引用某篇文献**。`library.yaml` 增加了：
- `abstract_summary`：让 Agent 知道文献内容
- `relevance`：让 Agent 知道应在哪里引用
- `tags`：支持语义搜索匹配

两者通过 `sync_bib()` 保持自动同步。

### 7.2 为什么用 YAML 而不是 JSON？

- YAML 对 LLM 更友好（可读性更强，生成更自然）
- 支持多行字符串（`>`、`|`），适合存放摘要和描述
- 支持注释，方便人工审阅

### 7.3 为什么把符号定义在 `glossary.yaml` 而不只是 `preamble.tex`？

`preamble.tex` 是给 LaTeX 编译器看的，`glossary.yaml` 是给 Agent 看的。后者包含语义描述（`description`），让 Agent 理解符号含义并正确使用。两者通过约定的 `latex_macro` 字段保持同步。

### 7.4 层间数据流原则

```
data/ (Layer 0)  ──只读──→  pipeline/ (Layer 1)  ──转化──→  paper/ (Layer 2)
      ↑                           ↑                            ↑
   用户导入                   Agent 处理                   Agent 撰写
                              用户审核                     用户审校
```

- Layer 0 → Layer 1：通过 `pipeline/scripts/` 中的脚本转化
- Layer 1 → Layer 2：通过 Agent 撰写，参考 `pipeline/notes/` 中的论点和发现
- 每层变动独立追踪，用户自行控制版本管理

---

## 八、决议记录

| # | 议题 | 决议 |
|---|------|------|
| 1 | LaTeX 模板选择 | 暂不支持多模板切换，使用单一模板 |
| 2 | 编程语言偏好 | 工具层使用 **Python** 实现 |
| 3 | 图表风格 | **优先继承用户导入的原始图表风格**，风格一致性配置存入 `config/figure-style.yaml`，Agent 首次处理时自动分析并填充 |
| 4 | 多语言支持 | **优先实现中文版本**，支持中英双语（摘要双语、术语首现附注英文原文），LaTeX 使用 xelatex + ctex |
| 5 | 协作场景 | 无多人协作需求，单人使用 |
| 6 | 文献 PDF 管理 | **需要**。新增 `pdf_extractor.py` 工具，从 PDF 中提取元信息、摘要和**关键原文摘录** (`key_quotes`)，建立引用溯源映射，防止 LLM 引用时无中生有 |
| 7 | 版本控制 | 不集成 Git 工作流，用户自行管理 |

---

*计划已确认，可开始实现。*
