# Skill: 实验管理

> 管理 `data/` 层的实验代码、数据和环境配置。

## 触发条件

用户请求运行实验、新增实验、修改实验代码、更新数据、修复数据错误等。

## 工作步骤

1. 读取 `data/_manifest.yaml` 了解现有数据和代码布局
2. 读取 `config/experiment-env.yaml` 确认环境依赖
3. 根据需求新增或修改 `data/code/` 中的实验脚本
4. 执行实验，将产出写入 `data/raw/`
5. 更新 `data/_manifest.yaml`，记录新增/变更文件的描述和时间
6. 如有环境变化，更新 `config/experiment-env.yaml`

## 规范

- 修改已有数据前必须告知用户并说明原因
- 删除数据前必须经用户确认
- 新增文件后必须同步更新 `_manifest.yaml`
- 实验脚本须在头部注释标明用途、输入、输出和依赖
