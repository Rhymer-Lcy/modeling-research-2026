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
| T-005 | M1 | Problem-F intake guard and public-safety checker repair | .gitignore · scripts/check_public_safe.ps1 · scripts/selftest_checker.ps1 · README.md · TASKS.md · worklog/M1.md | done | 2026-09-23 |
| T-006 | M2 | Problem-F local archive migration, integrity closure, audit import | docs_local/problem-f/ · data_local/problem-f/ · worklog/M2.md | done | 2026-09-23 |
| T-007 | M2 | Q1 quality/conflict/domain-mixture modeling | src/quality/ · src/mixture/ · scripts/q1_* · results/ · reviews/T-007/ · worklog/M2.md | done | 2026-09-24 |
| T-008 | M1 | Q2 generalized scaling law | src/scaling/ · scripts/q2_* · results/ · reviews/T-008/ · worklog/M1.md | done | 2026-09-25 |
| T-009 | M3 | Q4 panel/eligibility/C8 pipeline | src/panel/ · scripts/q4_panel_* · results/ · reviews/T-009/ · worklog/M3.md | done | 2026-09-24 |
| T-010 | M2 | Q3 compute-constrained resource optimization | src/alloc/ · scripts/q3_* · results/tables/q3-* · results/figures/q3-* · reviews/T-010/ · worklog/M2.md | wip | 2026-09-25 |
| T-011 | M3 | Q4 decomposition/bridge/frontier forecast | src/evolution/ · scripts/q4_* · results/tables/q4-evolution-* · results/tables/q4-bridge* · results/tables/q4-decomposition* · results/tables/q4-frontier* · results/tables/q4-forecast-* · results/figures/q4-* · reviews/T-011/ · worklog/M3.md | wip | 2026-09-25 |
| T-012 | M1 | cross-question integration/validation/manuscript integration | paper/ · results/ · reviews/T-012/ · worklog/M1.md | todo | 2026-09-23 |
| T-013 | M1 | collaboration review and prompt-spec workflow | reviews/README.md · reviews/HANDOVER_TEMPLATE.md · worklog/specs/ · README.md · AGENTS.md · TASKS.md · worklog/M1.md | wip | 2026-09-23 |
| T-014 | M1 | 2026 manuscript format intake and LaTeX conformance | docs_local/gmcm-2026/ · paper/main.tex · paper/format_2026.tex · paper/FORMAT_2026.md · paper/references.bib · paper/sections/05-4-model-q4.tex · reviews/T-014/ · worklog/M1.md | done | 2026-09-23 |
| T-015 | M1 | reproducible Python environment stabilization | environment.yml · reviews/T-015/ · worklog/M1.md | done | 2026-09-25 |

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
- **T-014 同样不在上面这张科学依赖图里。** 它是稿件格式合规任务：把组委会 2026 年
  官方格式文件归档到被忽略的本地目录，并据此校正 LaTeX 实现。它既不是
  T-007…T-012 的前置，也不被它们阻塞；T-008 的科研进度不得因它而等待。官方原件
  只存在于 `docs_local/`，永不进入版本库；逐条对照结论写在 `paper/FORMAT_2026.md`。
- **T-013 是协调任务，不在上面这张科学依赖图里**，既不是 T-007…T-012 的前置，
  也不被它们阻塞。它维护的是评审包与规范提示词这两条协作约定本身；约定的细则
  写在 `AGENTS.md`，模板在 `reviews/` 与 `worklog/specs/`。T-013 在整个项目期间
  保持 `wip`，因为 M1 会持续维护这些规范。
- **T-015 也不在上面这张科学依赖图里。** 它是项目支撑任务，负责使 Python 环境
  可复现。上面的依赖图不变；但在 T-015 完成之前，T-010 与 T-011 **暂缓启动**。
  这是执行层面的暂缓，不是新增的科学依赖。
- 每个科学任务在其 `Paths` 里都列出了自己的 `reviews/T-0xx/`：评审包由该任务
  **当前的负责人**所有，与代码路径同一套归属规则，不另立一套。
