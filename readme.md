# Paper Agent — 论文撰写智能体框架

面向 LLM Agent 的学术论文写作框架。通过标准化的三层数据架构、严格的配置约束和自动化工具链，让 AI Agent 能从原始数据出发，协助完成一篇结构完整、引用可溯源、术语一致的学术论文。

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/pa-jesusf/paper_agent.git
cd paper_agent

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

**可选依赖：**
- `PyMuPDF` — PDF 文献解析（`pdf_extractor.py`）
- `matplotlib` — 图表生成（`figure_builder.py`）
- TeX Live / MiKTeX — LaTeX 编译（`latex_compiler.py`）

### 2. 初始化项目

#### 导入外部数据仓库（可选）

如果你的实验数据存放在独立的 Git 仓库中，可以将其作为 submodule 挂载到 `data/raw/`：

```bash
# 添加数据仓库为 submodule
git submodule add <你的数据仓库URL> data/raw

# 提交 submodule 配置
git commit -m "chore: add data/raw as submodule"
```

之后其他协作者克隆项目时，需要一并拉取 submodule：

```bash
# 方式一：克隆时直接递归拉取
git clone --recurse-submodules <paper_agent_URL>

# 方式二：已克隆后补拉
git submodule update --init
```

更新数据到最新版本：

```bash
cd data/raw
git pull origin main
cd ../..
git add data/raw
git commit -m "chore: update data/raw submodule"
```

> **说明**：`data/raw/` 作为 submodule 后，`project_init.py` 扫描时会正常识别其中的文件并生成 `_manifest.yaml`。`_manifest.yaml`、`data/code/`、`data/drafts/` 仍由主仓库管理。

如果不使用 submodule，直接将数据放入 `data/` 目录即可：

将你的实验数据、代码、草稿放入 `data/` 目录，然后在 Copilot Chat 中输入：

```
初始化
```

Agent 会自动扫描数据、生成 manifest、引导你填写配置。

也可以手动运行扫描工具：

```bash
python tools/project_init.py
```

### 3. 填写配置文件

| 配置文件 | 用途 | 必填 |
|---------|------|------|
| `config/paper.yaml` | 论文标题、作者、投稿目标、语言 | ✅ |
| `config/glossary.yaml` | 术语表 + 数学符号宏 | ✅ |
| `config/experiment-env.yaml` | 实验硬件/软件环境 | 建议 |
| `config/figure-style.yaml` | 图表配色/字体/布局 | 建议 |
| `config/style-guide.md` | 写作风格偏好 | 可选 |

填完后运行校验：

```bash
python tools/config_validator.py        # 检查配置
python tools/config_validator.py --fix  # 检查并自动补全
```

### 4. 开始写作

在 VS Code 中打开 Copilot Chat，选择对应的 Agent 开始工作：

| Agent | 适用场景 | 聊天时选择 |
|-------|----------|-----------|
| **Researcher** | 文献调研、阅读笔记、引用建议 | `@researcher` |
| **Analyst** | 数据分析、图表生成 | `@analyst` |
| **Writer** | 撰写 LaTeX 正文 | `@writer` |
| **Reviewer** | 审校、一致性检查 | `@reviewer` |
| **Experimenter** | 新增实验、修改数据 | `@experimenter` |

---

## 项目结构

```
paper_agent/
├── .agent/                  # Agent 指令层
│   ├── copilot-instructions.md  # 全局行为准则
│   ├── agents/              # 5 个 Agent 角色定义
│   └── skills/              # 6 个技能定义
├── config/                  # 全局配置
├── data/                    # 原始数据（Layer 0）
│   ├── raw/                 # 实验数据
│   ├── code/                # 实验代码
│   └── drafts/              # 草稿
├── pipeline/                # 中间处理（Layer 1）
│   ├── scripts/             # 处理脚本
│   ├── figures/             # 生成的图表
│   ├── tables/              # 生成的表格
│   └── notes/               # 大纲、论点、发现
├── paper/                   # LaTeX 输出（Layer 2）
│   ├── main.tex             # 主入口
│   ├── preamble.tex         # 宏定义
│   ├── sections/            # 按章节拆分的 .tex
│   └── references.bib       # 参考文献
├── refs/                    # 文献管理
│   ├── library.yaml         # 文献元数据 + 原文摘录
│   ├── pdfs/                # PDF 存档
│   └── notes/               # 阅读笔记
├── memory/                  # 记忆层（跨会话持久化）
│   ├── progress.yaml        # 阶段/章节/图表进度
│   ├── preferences.yaml     # 用户偏好
│   ├── decisions.yaml       # 关键决策记录
│   └── sessions/            # 会话摘要
└── tools/                   # 10 个自动化工具
```

### 三层数据架构

```
data/ (Layer 0)  →  pipeline/ (Layer 1)  →  paper/ (Layer 2)
  原始数据              处理 & 分析              LaTeX 论文
  只读 (Experimenter    脚本/图表/笔记          章节文件
  例外可写)                                     references.bib
```

---

## 工具清单

所有工具均可通过命令行独立运行：

| 工具 | 命令 | 用途 |
|------|------|------|
| `project_init.py` | `python tools/project_init.py` | 扫描数据、生成 manifest、检查配置完备性 |
| `config_validator.py` | `python tools/config_validator.py [--fix]` | 深度校验配置 + 交叉一致性检查 |
| `bib_manager.py` | `python tools/bib_manager.py` | 文献增删查改、.bib 同步、引用验证 |
| `pdf_extractor.py` | `python tools/pdf_extractor.py <pdf>` | PDF 解析、关键原文提取 |
| `glossary_checker.py` | `python tools/glossary_checker.py` | 术语/符号一致性扫描 |
| `paper_lint.py` | `python tools/paper_lint.py` | 引用完整性、图表引用、TODO 标记检查 |
| `latex_compiler.py` | `python tools/latex_compiler.py` | LaTeX 编译 + 错误解析 |
| `figure_builder.py` | `python tools/figure_builder.py` | 风格统一的图表生成 |
| `memory_manager.py` | `python tools/memory_manager.py` | 项目进度、偏好、决策、会话管理 |
| `commands.py` | `python tools/commands.py <命令>` | 快捷命令调度 |

---

## 快捷命令

在 Copilot Chat 中直接输入以下指令，Agent 自动编排底层操作：

| 命令 | 作用 |
|------|------|
| `初始化` | 扫描 data/ → 交互式问答 → 填充配置 → 生成报告 |
| `检查配置` | 完备性检查 + 配置校验 |
| `检查全文` | 术语一致性 + 论文质量 + 配置校验 |
| `编译论文` | 完整编译（xelatex → bibtex → xelatex ×2） |
| `快速编译` | 单次 xelatex |
| `同步文献` | library.yaml → references.bib |
| `更新术语表` | 扫描全文术语不一致 |
| `校验配置` | 深度校验所有配置文件 |
| `写 <章节名>` | 加载该章节所需的大纲、论点、配置上下文 |
| `分析 <文件名>` | 加载数据 manifest 准备分析 |
| `添加文献 "<标题>"` | 搜索并添加文献到 library.yaml |
| `查看进度` | 显示项目全局状态面板（阶段/章节/文献/决策） |

---

## 典型工作流

### Phase 0: 初始化

1. 将数据/代码放入 `data/`
2. 输入 `初始化`，回答 Agent 的问题
3. Agent 自动填充 `config/` 下的配置文件、生成 `data/_manifest.yaml`

### Phase 1: 调研与规划

1. 使用 `@researcher` 调研文献
2. Agent 在 `refs/library.yaml` 中建立文献库，提取关键原文 (`key_quotes`)
3. 在 `pipeline/notes/` 中生成大纲和论点

### Phase 2: 数据处理

1. 使用 `@analyst` 分析数据
2. Agent 生成处理脚本到 `pipeline/scripts/`
3. 图表输出到 `pipeline/figures/`，发现记录到 `findings.md`

### Phase 3: 撰写

1. 使用 `@writer` 逐章撰写
2. Agent 引用文献时必须有 `key_quotes` 溯源
3. 术语和符号自动遵循 `glossary.yaml`

### Phase 4: 审校

1. 使用 `@reviewer` 或输入 `检查全文`
2. Agent 运行 `glossary_checker` + `paper_lint` + `config_validator`
3. 根据报告修正问题

### Phase 5: 输出

1. 输入 `编译论文` 生成 PDF
2. 检查编译错误，迭代修正

---

## 核心设计理念

### 引用溯源

每条 `\cite{}` 必须能追溯到 `refs/library.yaml` 中的 `key_quotes`（原文摘录），杜绝 Agent 编造引用。

```
PDF 原文 → key_quotes (library.yaml) → refs/notes/ 引用映射 → paper/ 中的 \cite{}
```

### 术语一致性

`config/glossary.yaml` 定义术语规范和禁止变体，`glossary_checker` 自动扫描违规。数学符号强制使用 `preamble.tex` 中的宏。

### 权限隔离

| Agent | 可写范围 | 只读范围 |
|-------|---------|---------|
| Researcher | `refs/`, `pipeline/notes/` | `config/`, `data/` |
| Analyst | `pipeline/` | `data/`, `config/` |
| Writer | `paper/sections/`, `paper/main.tex` | `config/`, `pipeline/`, `refs/` |
| Reviewer | `paper/sections/` | `config/`, `pipeline/`, `refs/` |
| Experimenter | `data/`, `config/experiment-env.yaml` | `pipeline/notes/` |

---

## 开发

```bash
# 运行全部测试
python -m pytest tests/ -v

# 快速测试
python -m pytest tests/ -q
```

测试覆盖：233 tests, 涵盖所有 9 个工具 + 工作流集成 + 端到端场景。

---

## 许可证

MIT
