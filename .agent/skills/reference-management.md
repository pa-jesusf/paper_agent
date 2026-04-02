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
- `key_quotes` 应是原文原样摘录，尽量标注页码和所在章节
- 阅读笔记中建议建立「引用映射表」

### 引用检查
- `validate_citations()` 检查 `\cite{}` 是否有效
- 尽量确认每条引用都有 `key_quotes` 支撑；暂时缺失的用 `\todo{补充 key_quotes}` 标记

## 关键原则

- **不可违反**：不得编造原文内容（学术诚信底线）
- 新增文献尽量同步 `library.yaml` 和 `.bib`；同步失败时用 `\todo{}` 标记
- PDF 文件存放在 `refs/pdfs/`
