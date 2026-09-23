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
| T-002 | M1 | public release finalization | 字体回退对照、检查器改为结构化邮箱校验、文档同步 | done | 2026-09-22 |
| T-003 | M1 | final audit cleanup | README.md · worklog/M1.md · main 分支保护配置 | done | 2026-09-22 |
| T-004 | M1 | refine Git email safety policy | configs/git-email-policy.txt · scripts/ · README.md · AGENTS.md · worklog/M1.md | done | 2026-09-22 |
| T-005 | M1 | Problem-F intake guard and public-safety checker repair | .gitignore · scripts/check_public_safe.ps1 · scripts/selftest_checker.ps1 · README.md · TASKS.md · worklog/M1.md | wip | 2026-09-23 |
| T-006 | M2 | Problem-F local archive migration, integrity closure, audit import | docs_local/problem-f/ · data_local/problem-f/ · worklog/M2.md | todo | 2026-09-23 |
| T-007 | M2 | Q1 quality/conflict/domain-mixture modeling | src/quality/ · src/mixture/ · scripts/q1_* · results/ · worklog/M2.md | todo | 2026-09-23 |
| T-008 | M1 | Q2 generalized scaling law | src/scaling/ · scripts/q2_* · results/ · worklog/M1.md | todo | 2026-09-23 |
| T-009 | M3 | Q4 panel/eligibility/C8 pipeline | src/panel/ · scripts/q4_panel_* · results/ · worklog/M3.md | todo | 2026-09-23 |
| T-010 | M2 | Q3 compute-constrained resource optimization | src/alloc/ · scripts/q3_* · results/ · worklog/M2.md | todo | 2026-09-23 |
| T-011 | M3 | Q4 decomposition/bridge/frontier forecast | src/evolution/ · scripts/q4_* · results/ · worklog/M3.md | todo | 2026-09-23 |
| T-012 | M1 | cross-question integration/validation/manuscript integration | paper/ · results/ · worklog/M1.md | todo | 2026-09-23 |

## Problem-F dependency graph

前一问的输出是后一问的输入，任务依赖如下（箭头表示「必须先完成」）：

```
T-005 -> 仓库可安全操作
T-006 -> 所有建模任务可依赖规范本地路径
T-007 -> T-008
T-008 -> T-010
T-008 + T-009 -> T-011
T-010 + T-011 -> T-012
```

说明：

- T-008 的经典 N-D 基线在 T-006 交付规范 B 数据路径后即可开始，但在消费 T-007
  的接口（IF1/IF2）之前不得关闭。
- T-010 的求解器可先对解析夹具开发；在 T-008 交付 IF3 之前不产出任何 Q3 科学结论。
- 接口契约 IF1-IF4 由 M1 负责其模式定义，由各自实现者负责其数值内容。
