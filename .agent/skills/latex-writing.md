# Skill: LaTeX 撰写

> 撰写和编辑 LaTeX 论文正文。

## 触发条件

用户请求撰写、修改、扩展论文章节。

## 撰写前

1. 读取 `config/paper.yaml` — 语言、风格
2. 读取 `config/glossary.yaml` — 术语/符号约束
3. 读取 `config/style-guide.md` — 写作规范
4. 读取 `pipeline/notes/outline.md` — 定位章节
5. 读取 `pipeline/notes/arguments.md` — 获取论点

## 撰写规范

- 数学符号使用 `preamble.tex` 中的宏
- 术语首次出现附注英文原文
- 引用必须有 `key_quotes` 溯源
- 不确定内容用 `\todo{}` 或 `\confirm{}` 标记
- 章节文件命名: `{NN}-{slug}.tex`

## 完成后

- 同步 `main.tex` 中的 `\input{}` 列表
- 同步 `outline.md` 结构
