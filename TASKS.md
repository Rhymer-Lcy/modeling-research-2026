# TASKS

任务登记表，同时也是"某条路径当前归谁"的唯一记录。

规则：

- 一个任务、一条路径，同一时刻只有一个活跃负责人（Owner）。
- 只有 M1 新增或关闭行；负责人可以自行更新本人那一行的 `Status`。
- 移交负责人 = 修改 `Owner` 单元格并更新 `Updated`，同时由原负责人在自己的
  worklog 里记一条移交说明。
- `Paths` 列列出该任务在其活跃期间所拥有的路径。未列出的路径不属于该任务。

`Status` 取值：`todo` / `wip` / `review` / `done` / `blocked` / `dropped`

成员标识：`M1` 协调与集成负责人，`M2`、`M3` 贡献者。真实姓名不进入本仓库。

日期一律使用 UTC+8（Asia/Shanghai）。

| ID | Owner | Title | Paths / Deliverable | Status | Updated |
| --- | --- | --- | --- | --- | --- |
| T-001 | M1 | repository bootstrap | 仓库骨架、忽略规则、LaTeX 构建链、公开安全检查脚本 | done | 2026-09-22 |
