# TASKS

任务登记表，同时也是"某条路径当前归谁"的唯一记录。

规则：

- 一个任务、一条路径，同一时刻只有一个活跃负责人（Owner）。
- 只有 M1 新增或关闭行；负责人可以自行更新本人那一行的 `Status`。
- 移交负责人 = 修改 `Owner` 单元格并更新 `Updated`，同时由原负责人在自己的
  worklog 里记一条移交说明。
- `Paths` 列列出该任务在其活跃期间所拥有的路径。未列出的路径不属于该任务。

`Status` 取值：`todo` / `wip` / `review` / `done` / `blocked` / `dropped`

成员标识：`M1` 协调与集成负责人，`M2`、`M3`、`M4` 贡献者。真实姓名不进入本仓库。

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
| T-010 | M4 | Q3 compute-constrained resource optimization | src/alloc/ · scripts/q3_* · results/tables/q3-* · results/figures/q3-* · reviews/T-010/ · worklog/M4.md | done | 2026-09-27 |
| T-011 | M4 | Q4 decomposition/bridge/frontier forecast | src/evolution/ · scripts/q4_* · results/tables/q4-evolution-* · results/tables/q4-bridge* · results/tables/q4-decomposition* · results/tables/q4-frontier* · results/tables/q4-forecast-* · results/figures/q4-* · reviews/T-011/ · worklog/M4.md | done | 2026-09-25 |
| T-012 | M1 | cross-question integration/validation/manuscript integration | paper/ · results/ · scripts/paper_* · environment.yml（经 PR）· reviews/T-012/ · worklog/M1.md | done | 2026-09-28 |
| T-013 | M1 | collaboration review and prompt-spec workflow | reviews/README.md · reviews/HANDOVER_TEMPLATE.md · worklog/specs/ · README.md · AGENTS.md · TASKS.md · worklog/M1.md | done | 2026-09-28 |
| T-014 | M1 | 2026 manuscript format intake and LaTeX conformance | docs_local/gmcm-2026/ · paper/main.tex · paper/format_2026.tex · paper/FORMAT_2026.md · paper/references.bib · paper/sections/05-4-model-q4.tex · reviews/T-014/ · worklog/M1.md | done | 2026-09-23 |
| T-015 | M1 | reproducible Python environment stabilization | environment.yml · reviews/T-015/ · worklog/M1.md | done | 2026-09-25 |
| T-016 | M2 | Q1 receipt regeneration check on the T-007 machine | 无仓库路径：只读执行，不修改任何跟踪文件；产出均在仓库外（见下方说明） | done | 2026-09-30 |
| T-017 | M1 | final submission-attachment coherence remediation and acceptance | results/tables/q1-input-audit.md · results/tables/q1-reproduction.md · src/paths.py（经 PR）· docs_local/archive/（本地，不跟踪） | wip | 2026-09-30 |

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
  保持 `wip`，因为 M1 会持续维护这些规范；项目收尾完成后，于 2026-09-28 关闭。
- **T-015 也不在上面这张科学依赖图里。** 它是项目支撑任务，负责使 Python 环境
  可复现。上面的依赖图不变；但在 T-015 完成之前，T-010 与 T-011 **暂缓启动**。
  这是执行层面的暂缓，不是新增的科学依赖。
- 每个科学任务在其 `Paths` 里都列出了自己的 `reviews/T-0xx/`：评审包由该任务
  **当前的负责人**所有，与代码路径同一套归属规则，不另立一套。
- **T-016 是提交附件整改的核验任务，不在上面这张科学依赖图里，也不重新打开
  T-007。** T-007 保持 `done`，其已接受结果仍是基线。T-016 只回答一个问题：在
  T-007 原机（bound2）的数值环境上，用冻结提交附件（SHA-256
  `f12ab02d0591b4cb6f762dee3f78c6bf9e3094001168eda78b809c29ebfade9c`）中的问题一
  实现和规范题目 DOCX（35,514 字节，SHA-256
  `89f1b27c497c03ebf03335f5c9a738fa8a7f3525409bceb1ff8676794cf3b6a7`），能否在
  逐字节保持已接受问题一数值基线与 IF2 身份的前提下，重新生成更正了 DOCX 身份的
  两份回执。
  - 负责人 M2，状态 `wip`。
  - 范围：在本地 scratch 中新解压一次冻结提交附件；核验 DOCX 身份；只运行
    `python scripts/q1_reproduce.py`；把再生的问题一产物与冻结附件基线逐项比对；
    当且仅当全部通过条件成立，才把再生的 `results/tables/q1-input-audit.md` 与
    `results/tables/q1-reproduction.md` 作为仓库外交接载荷交给 M1。
  - 允许的产出：本地 scratch 实验目录；不进入跟踪文件的日志与比对证据；通过时
    的上述两份文件，交接载荷只含这两份。
  - 禁止：修改 M2 的跟踪仓库；改动科学代码或配置；在 M2 仓库提交再生的问题一
    产物；推送；重开问题一研究；改动已接受的数值结果；改动 IF1 或 IF2；手工编辑
    或合成生成的回执；运行问题二、三、四或论文图流程；看到结果后再调整 BLAS 或
    线程设置。
  - 通过条件：bound2 逐字节复现冻结的问题一数值与科学基线；IF1、IF2 不变；DOCX
    身份为上面的规范值；两份回执中只有已裁定的行不同，即 `q1-input-audit.md` 的
    DOCX SHA-256 行，以及 `q1-reproduction.md` 中 `q1-input-audit.md` 的哈希行和
    DOCX 核对表述行（打包版脚本改由入库记录核对 DOCX，因此该句改写）。
  - 失败条件：任何已接受的问题一数值或科学产物不同；IF1 或 IF2 不同；两份回执中
    出现任何其他不同的行。失败时 M2 停止并报告，不授权任何整改。
  - 收尾：M2 报告“SAFE FOR M1 P1/P2 REMEDIATION: YES / NO”后，任务交回 M1
    处置，M2 再次退出。
  - 结果（2026-09-30）：M2 报告“SAFE FOR M1 P1/P2 REMEDIATION: YES”，M1 用冻结
    提交附件独立复核一致，T-016 关闭为 `done`，M2 退出。接受的仓库外交接载荷：
    `results/tables/q1-input-audit.md` SHA-256
    `fc04e165b7225520510557c606d3256396a3a644ab8a378f883b238eca9297a1`，
    `results/tables/q1-reproduction.md` SHA-256
    `4d9818e60fb4ccdfd8430b15c8ca2103140e328a24423fe51c031026d4c9bd78`。
    核验回执留在仓库外，不进入版本库；两份文件的安装由后续的整改任务完成。
- **T-017 是提交附件的最终整改与验收任务，不在上面这张科学依赖图里，不改任何
  已接受的科学结论。** 负责人 M1。以冻结提交附件（SHA-256
  `f12ab02d0591b4cb6f762dee3f78c6bf9e3094001168eda78b809c29ebfade9c`）为基础，按
  白名单增量构建新的候选附件：安装 T-016 接受的两份问题一回执；加入四个已裁定
  缺失的脚本，字节取自冻结的复现附件；修正 `src/paths.py` 中两处面向使用者的
  提示文字；安装英文 README；重新生成 MANIFEST；在一次性解压目录中做 Windows
  全量验收，并做引用闭包、路径泄漏与一致性审计；把正当的跟踪文件修改同步到
  版本库。
  - 不包括：科学模型重设计；改动已接受的科学结论；改动论文图，包括不采纳中文
    审校的可选措辞建议；大范围的溯源措辞清理；只为文风改动与哈希耦合的溯源
    内容。
  - 冻结附件在整改期间保持不变，新候选使用新的文件名。
