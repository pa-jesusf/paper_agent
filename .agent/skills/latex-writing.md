# Skill: LaTeX 撰写

> 撰写和编辑 LaTeX 论文正文。

## 触发条件

用户请求撰写、修改、扩展论文章节。

## 撰写前（建议，非必须）

> 以下文件如不存在，跳过即可。缺失信息用 `\todo{}` 标记。

1. 读取 `config/paper.yaml` — 语言、风格
2. 读取 `config/glossary.yaml` — 术语/符号约束
3. 读取 `config/style-guide.md` — 写作规范
4. 读取 `pipeline/notes/outline.md` — 定位章节
5. 读取 `pipeline/notes/arguments.md` — 获取论点

## 撰写规范

- 数学符号优先使用 `preamble.tex` 中的宏；需要新符号时可直接定义
- 术语首次出现建议附注英文原文
- 引用尽量有 `key_quotes` 溯源；尚未收录的文献用 `\todo{补充文献}` 占位
- 不确定内容用 `\todo{}` 或 `\confirm{}` 标记
- 章节文件命名: `{NN}-{slug}.tex`

## 完成后

- 尽量同步 `main.tex` 中的 `\input{}` 列表
- 尽量同步 `outline.md` 结构（如文件不存在，可跳过）
