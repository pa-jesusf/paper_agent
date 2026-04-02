# Skill: 参考文献管理

> 搜索、添加、管理参考文献并维护引用溯源。

## 触发条件

用户请求添加文献、搜索相关论文、检查引用等。

## 功能

### 添加文献
1. 从 PDF 自动提取（`tools/pdf_extractor.py`）或在线搜索（`tools/bib_manager.py`）
2. 生成 `refs/library.yaml` 条目，包含 `abstract_summary`、`relevance`、`key_quotes`
3. 生成阅读笔记 `refs/notes/{citekey}.md`
4. 同步 `paper/references.bib`

### 引用溯源
- 每个 `key_quotes` 条目必须是原文原样摘录
- 记录页码和所在章节
- 在阅读笔记中建立「引用映射表」

### 引用检查
- `validate_citations()` 检查所有 `\cite{}` 是否有效
- 确认每条引用都有 `key_quotes` 支撑

## 关键原则

- 绝不编造原文内容
- 新增文献必须同步 `library.yaml` 和 `.bib`
- PDF 文件存放在 `refs/pdfs/`
