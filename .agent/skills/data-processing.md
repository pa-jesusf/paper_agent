# Skill: 数据处理

> 从 `data/` 原始数据生成 `pipeline/` 中间产物。

## 触发条件

用户请求分析数据、处理数据、提取特征等。

## 工作步骤

1. 读取 `data/_manifest.yaml` 定位目标数据文件
2. 分析数据格式和内容
3. 编写处理脚本，保存到 `pipeline/scripts/{序号}_{用途}.py`
4. 执行脚本，将结果保存到 `pipeline/tables/` 或 `pipeline/figures/`
5. 更新 `pipeline/notes/findings.md` 记录关键发现

## 规范

- 脚本应有清晰的输入/输出路径注释
- 原则上不修改 `data/` 下的文件；发现数据问题时记录到 `findings.md`
- 输出图表时优先读取 `config/figure-style.yaml`；配置不存在时使用合理默认样式
