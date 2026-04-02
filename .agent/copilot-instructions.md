# Paper Agent — 全局行为准则

> 此文件定义 Agent 在本项目中的全局行为规范。
> 核心原则：**保证学术诚信和数据可追溯性，同时给予 Agent 充分的创作自由和灵活应变能力。**
> 遇到前置条件不满足时，优先推进工作（标记待补项），而非停下来等待。

---

## 项目结构

本项目是一个论文撰写框架，分为三层数据架构：

- `data/` (Layer 0) — 原始数据层，通过 `_manifest.yaml` 索引。原则上由 **Experimenter Agent** 负责管理，其他 Agent 只读
- `pipeline/` (Layer 1) — 中间处理层：脚本、图表、论点笔记
- `paper/` (Layer 2) — LaTeX 输出层，每小节一个 `.tex` 文件

配置层 `config/` 存放全局约束，`refs/` 管理参考文献，`tools/` 提供自动化工具。

记忆层 `memory/` 持久化项目状态，所有 Agent 均可读写：
- `memory/progress.yaml` — 阶段进度、章节状态、图表状态、文献统计
- `memory/preferences.yaml` — 用户偏好（写作风格、交互习惯等）
- `memory/decisions.yaml` — 关键决策及理由
- `memory/sessions/` — 每次会话的摘要

## 核心工作流

> 以下是推荐流程，不是刚性前置条件。如果某个文件不存在或不完整，Agent 应使用合理默认值继续工作，并用 `\todo{}` 标记待补项。

1. **每次会话开始时**，尽量读取 `memory/progress.yaml` 和 `memory/preferences.yaml`，以及最近的会话摘要 `memory/sessions/`，了解上下文
2. **写作任务前**，读取 `config/` 下可用的配置文件。缺失的配置不阻断工作，Agent 可使用合理默认值
3. **撰写前**检查 `pipeline/notes/outline.md` 和 `pipeline/notes/arguments.md`。如果不存在，Agent 可自行起草初稿或直接撰写
4. **使用符号时**优先使用 `config/glossary.yaml` 中定义的宏。如需新符号，Agent 可同时在 `glossary.yaml` 和 `preamble.tex` 中添加
5. **引用文献时**优先搜索 `refs/library.yaml` 确认溯源。如尚未收录，可先用 `\cite{citekey}` + `\todo{补充 key_quotes}` 占位，后续由 Researcher 补全
6. **完成章节后**建议运行 `tools/glossary_checker.py` 和 `tools/paper_lint.py`。工具不可用时可跳过
7. **生成图表时**读取 `config/figure-style.yaml` 保持风格一致。配置缺失时使用合理默认样式
8. **完成任何实质性工作后**，尽量更新 `memory/progress.yaml`
9. **做出重要决策后**（如结构调整、方法选择），记录到 `memory/decisions.yaml`
10. **发现用户偏好后**，保存到 `memory/preferences.yaml`
11. **会话结束前**，建议在 `memory/sessions/` 创建会话摘要

## 不可违反的底线（红线）

以下规则涉及学术诚信，**绝对不可违反**：

- **禁止编造实验数据**或引用未在 `data/` 中存在的结果
- **禁止编造文献引用**——引用论断必须有 `key_quotes` 原文支撑，不可虚构
- **禁止篡改已有实验数据**而不留记录

## 应遵守的规范（可灵活执行）

以下规则是质量保障措施，Agent 应尽力遵守，但允许在合理情况下灵活处理：

- **术语变体**：优先使用 `glossary.yaml` 中的规范术语，避免 `forbidden_variants`。如果上下文中其他表述更清晰，可以使用，但事后用 `glossary_checker` 校验
- **数学符号**：优先使用 `preamble.tex` 中的宏。如需新符号，可直接定义新宏并同步更新 `glossary.yaml`
- **文献引用**：优先使用 `references.bib` 中已有文献。如需新文献，可先用 `\todo{添加文献: xxx}` 占位
- **术语首现标注**：中文论文中术语首次出现时建议附注英文原文（如 `大语言模型（Large Language Model, LLM）`），具体格式可根据 `style-guide.md` 调整
- **角色边界**：原则上各 Agent 在自己的操作范围内工作。紧急情况下（如发现明显数据错误影响分析），Agent 可跨界做最小修改，但必须在 `memory/decisions.yaml` 中记录原因

## 文件变更规范

- 新增/删除/重排章节时，尽量同步更新 `paper/main.tex` 和 `pipeline/notes/outline.md`
- 新增数学符号时，同步更新 `config/glossary.yaml` 和 `paper/preamble.tex`
- 新增文献时，同步更新 `refs/library.yaml` 和 `paper/references.bib`
- 完成数据分析后，更新 `pipeline/notes/findings.md`
- **如果同步更新失败**（如目标文件不存在），用 `\todo{}` 标记待同步项，不阻断主任务

## 标记约定

在正文中使用以下标记表示待处理项目——这是 Agent 推进工作而非停下等待的核心工具：

- `\todo{描述}` — 待完成的内容（Agent 可先写初稿再标记需要改进的地方）
- `\confirm{描述}` — 需要用户确认的内容
- `% FEEDBACK: ...` — 用户在 `.tex` 文件中给出的修改意见（Agent 应识别并处理）

## 写作语言

本项目**优先使用中文撰写**。术语首次出现时建议附注英文原文。摘要生成中英双语版本。
Agent 应参考 `config/style-guide.md` 中的具体写作规范（如果存在）。
