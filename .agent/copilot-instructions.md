# Paper Agent — 全局行为准则

> 此文件定义 Agent 在本项目中的全局行为规范。
> Agent 在执行任何任务前必须遵守以下准则。

---

## 项目结构

本项目是一个论文撰写框架，分为三层数据架构：

- `data/` (Layer 0) — 原始数据层，通过 `_manifest.yaml` 索引。仅 **Experimenter Agent** 有写入权限，其他 Agent 只读
- `pipeline/` (Layer 1) — 中间处理层：脚本、图表、论点笔记
- `paper/` (Layer 2) — LaTeX 输出层，每小节一个 `.tex` 文件

配置层 `config/` 存放全局约束，`refs/` 管理参考文献，`tools/` 提供自动化工具。

记忆层 `memory/` 持久化项目状态，所有 Agent 均可读写：
- `memory/progress.yaml` — 阶段进度、章节状态、图表状态、文献统计
- `memory/preferences.yaml` — 用户偏好（写作风格、交互习惯等）
- `memory/decisions.yaml` — 关键决策及理由
- `memory/sessions/` — 每次会话的摘要

## 核心工作流

1. **每次会话开始时**，先读取 `memory/progress.yaml`（了解项目进度）和 `memory/preferences.yaml`（了解用户偏好），以及最近的会话摘要 `memory/sessions/`
2. **任何写作任务前**，先读取 `config/` 下的全部配置文件（`paper.yaml`, `glossary.yaml`, `experiment-env.yaml`, `figure-style.yaml`, `style-guide.md`）
3. **撰写前**检查 `pipeline/notes/outline.md`（大纲）和 `pipeline/notes/arguments.md`（论点）
4. **使用符号时**只使用 `config/glossary.yaml` 中定义的宏，对应 `paper/preamble.tex` 中的 `\newcommand`
5. **引用文献时**先搜索 `refs/library.yaml`，确认有对应的 `key_quotes` 溯源
6. **完成章节后**运行 `tools/glossary_checker.py` 和 `tools/paper_lint.py` 验证一致性
7. **生成图表时**读取 `config/figure-style.yaml`，确保视觉风格一致
8. **完成任何实质性工作后**，更新 `memory/progress.yaml`（章节/图表/文献状态）
9. **做出重要决策后**（如结构调整、方法选择），记录到 `memory/decisions.yaml`
10. **发现用户偏好后**（如写作风格、交互习惯），保存到 `memory/preferences.yaml`
11. **会话结束前**，在 `memory/sessions/` 创建会话摘要（做了什么、改了哪些文件、下一步建议）

## 禁止事项

- **禁止编造实验数据**或引用未在 `data/` 中存在的结果
- **禁止使用** `glossary.yaml` 中 `forbidden_variants` 列出的术语变体
- **禁止在正文中硬编码数学符号**（必须使用 `preamble.tex` 中的宏）
- **禁止引用**不存在于 `paper/references.bib` 中的文献
- **禁止引用时编造**原文未提及的论断（必须有 `key_quotes` 溯源）
- **中文论文中术语首次出现时**必须附注英文原文，格式：`中文术语（English Term, 缩写）`
- **非 Experimenter 角色禁止修改** `data/` 下的文件（Experimenter 修改时须更新 `_manifest.yaml` 并告知用户）

## 文件变更规范

- 新增/删除/重排章节时，**同步更新** `paper/main.tex` 和 `pipeline/notes/outline.md`
- 新增数学符号时，**同步更新** `config/glossary.yaml` 和 `paper/preamble.tex`
- 新增文献时，**同步更新** `refs/library.yaml` 和 `paper/references.bib`
- 完成数据分析后，**更新** `pipeline/notes/findings.md`

## 标记约定

在正文中使用以下标记表示需要用户确认的内容：

- `\todo{描述}` — 待完成的内容
- `\confirm{描述}` — 需要用户确认的内容
- `% FEEDBACK: ...` — 用户在 `.tex` 文件中给出的修改意见（Agent 应识别并处理）

## 写作语言

本项目**优先使用中文撰写**。术语首次出现时附注英文原文。摘要生成中英双语版本。
Agent 应参考 `config/style-guide.md` 中的具体写作规范。
