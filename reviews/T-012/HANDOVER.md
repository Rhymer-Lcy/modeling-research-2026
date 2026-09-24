# T-012 handover — pre-integration readiness

| Field | Value |
| --- | --- |
| Task | T-012 |
| Owner | M1 |
| Status | **pre-integration readiness complete; final T-012 remains dependency-blocked** |
| Timestamp | 2026-09-24T11:30:00+08:00 |
| Base | `87fbce3` (accepted `main`) |
| Branch / PR | `chore/m1-T012-preintegration` / draft PR |

**This package describes preparatory work only.** No scientific integration was
performed. T-012 stays `todo` in `TASKS.md`, and the dependency
`T-010 + T-011 -> T-012` is unchanged.

## Scope

Prepare the integration architecture, evidence map, acceptance gates,
manuscript plan and reproducibility checklist before the scientific
dependencies complete, so that final integration is a matter of executing a
declared plan rather than improvising under time pressure.

## What was inspected

Branch cut from accepted `main` at `87fbce3`, **not** from any task branch.

Read: `README.md`, `AGENTS.md`, `CLAUDE.md`, `TASKS.md`, `src/interfaces.py`,
`src/paths.py`, `reviews/README.md`, `reviews/HANDOVER_TEMPLATE.md`,
`worklog/specs/README.md`, `worklog/specs/PROMPT_SPEC_TEMPLATE.md`,
`worklog/M1.md`, `paper/main.tex`, `paper/FORMAT_2026.md`,
`paper/references.bib`, every `paper/sections/*.tex`, and the three accepted
results tables on `main`.

Branch and PR **metadata** were inspected to establish that pending work
exists: task branches for T-007, T-008 and T-009, and one open draft PR (#8,
T-008, a frozen review checkpoint). Their contents are treated as
**UNREVIEWED / NON-AUTHORITATIVE / NOT FOR MANUSCRIPT CLAIMS**.

## Deliverables

| Artifact | Contents |
| --- | --- |
| `paper/INTEGRATION_PLAN.md` | IF1-IF4 interface matrix; evidence-to-claim map; claim hierarchy; figure/table inventory; section readiness; gates G1-G12; handoff order; reproducibility checklist |
| `results/tables/t012-integration-readiness.md` | 15-row units/scales/direction audit, plus the rows needing a decision |
| `worklog/specs/T-012.md` | canonical v1 specification, machine-independent |
| `reviews/T-012/HANDOVER.md` | this package |

## Interface readiness summary

| Interface | Producer | Readiness | Gate |
| --- | --- | --- | --- |
| IF1 domain quality | T-007 | **PENDING REVIEW** | G1 |
| IF2 mixture response | T-007 | **PENDING REVIEW** | G1 |
| IF3 classic | T-008 | exists locally, Q pinned to `[1,1]`; **T-008 not closed** | G2 |
| IF3 generalized | T-008 | **NOT YET EMITTED — blocked on reviewed IF1/IF2 and T-008 closure** | G2 |
| IF4 bridge | T-011 | **NOT YET PRODUCED** | G5 |

No interface object is tracked in Git; all are local-only by design, so
readiness refers to review status rather than file existence.

## Manuscript readiness summary

All twelve sections are placeholders. None contains accepted scientific
content, and none is in a `PREMATURE / MUST NOT FINALIZE YET` state **because
none has been written**. The guarded risk is the opposite one: writing them
before their evidence is accepted. Eligibility triggers are recorded per
section, with the abstract written last, after all four questions have accepted
results.

Two structural defects were found and **recorded rather than fixed**, since
`paper/sections/` is not an allowed path for this stage:

1. `00-abstract.tex` enumerates three problems while the problem has four.
2. `02-analysis.tex` has three analysis subsections, missing Q4.

Both are template staleness left over from T-014, which added the Q4 model
section without touching these two files. Neither is a scientific error. Owner
M1, to be corrected before those sections are written.

## Unit and scale audit summary

Fifteen conventions audited. Three findings worth a reviewer's attention:

1. **Two unit regimes coexist inside Q2.** The classic law is fitted in raw
   parameters and raw tokens (validity box N 7.054e+07 to 1.197e+10, D
   1.340e+08 to 2.999e+11) while the quality-bearing tables are handled in
   billions. Both are internally consistent; a future cross-comparison that
   mixes them would be wrong by 1e9 in each of two dimensions and would still
   look plausible.
2. **Indicator direction is the highest-risk row.** The accepted contract
   records native directions as 15 higher-is-better, 4 lower-is-better, 3
   non-monotone (sum 22), *and separately* requires standardization to a common
   higher-is-better scale. `IF1.indicator_directions` records the native
   direction. Reading it as "all higher-is-better" would invert four indicators
   with nothing downstream looking wrong.
3. **Three declarations are outstanding and were deliberately NOT resolved
   here**: the time basis (publication vs evaluation date); the context-length
   **analysis scope** — its unit is settled as tokens, see the v2 delta below;
   and whether the declared benchmark score scale is higher-is-better. Each is
   assigned to the task that first needs it. Resolving any of them here would
   be a scientific decision taken inside an integration-planning task.

## Final acceptance gate status

| Gate | State |
| --- | --- |
| G1 T-007 accepted | **NOT MET** (`wip`) |
| G2 T-008 closed | **NOT MET** (`wip`, draft PR open) |
| G3 T-010 accepted | **NOT MET** (`todo`) |
| G4 T-009 accepted | **NOT MET** (`wip`) |
| G5 T-011 accepted | **NOT MET** (`todo`) |
| G6 interface validation | **PARTIAL** — self-test passes; only classic IF3 exists |
| G7 numerical reproduction | **NOT TESTABLE YET** — no numbers in the manuscript |
| G8 provenance consistency | **NOT MET** — pending content |
| G9 uncertainty consistency | **NOT MET** — pending content |
| G10 manuscript format | **PASSES EMPTY** — must be re-run with content |
| G11 public safety | **PASSING** |
| G12 final PDF visual audit | **NOT MET** — pending content |

G10 and G12 currently pass on an empty manuscript, which proves nothing about
the finished one. Both must be re-run after scientific content exists.

## What was deliberately NOT done

* No scientific integration, and no manuscript conclusion written.
* **No unreviewed M2 or M3 scientific result was adopted.** Nothing was merged,
  cherry-picked or copied from `exp/m2-T007-q1-modeling`,
  `exp/m3-T009-q4-panel` or `exp/m1-T008-generalized-scaling`.
* No T-008 modelling continued; no T-008 code or PR content modified.
* No scientific implementation code touched; no other member's worklog, review
  package or branch touched.
* No interface schema changed, and no new shared field proposed.
* T-012 not marked `done` or `review`; dependency graph unchanged.
* Two manuscript-skeleton defects found but not fixed, being outside this
  stage's allowed paths.

## Unresolved dependencies

Final T-012 is blocked on **G1 through G5**: T-007 review, T-008 closure,
T-010, T-009 review and T-011. The binding constraint is the graph itself, not
this plan.

Three convention decisions (time basis, context length, benchmark direction)
are open and assigned; none blocks the *plan*, each blocks a specific future
claim.

## Validation

`scripts/selftest_interfaces.py` passes 21 assertions. `git diff --check`
clean. `scripts/check_public_safe.ps1 -Mode PreCommit` passes. Every factual
claim in the readiness audit was re-derived from the source rather than
asserted: the compute convention `kappa = 6.0`, the `1e9` unit conversion in
the fit script, both validity-box ranges, the panel rescaling formula and the
15/4/3 direction totals were each read back from `src/` or from the accepted
tables.

## v2 supervisory delta (2026-09-24)

Documentation and integration-governance only. No scientific modelling; no
unreviewed branch result consumed. v1 sections above are unchanged except where
this delta corrects them, and the v1 specification block is preserved untouched.

### 1. Q4 readiness corrected — was wrong in v1

v1 recorded "Detailed-task reconciliation" as **READY**. That was incorrect.
Accepted `main` carries a **partial** reconciliation: 4 of 6 dimensions
reproduce (BBH, IFEval, MMLU-PRO, MUSR) and **GPQA and MATH Lvl 5 are
quarantined there**. The artifact's own verdict is `PARTIAL`.

The map now splits the claim:

| Claim | State |
| --- | --- |
| C8/C1 scale convention — raw accuracy and baseline-rescaled score are distinct quantities requiring explicit rescaling | **READY** (retained; independent of which dimensions reconcile) |
| Detailed-task reconciliation, overall | **PENDING REVIEW** (gate G4) |

Figure inventory item **T4** moved from READY to PENDING REVIEW, gains
dependency G4, is marked *partial (4/6)*, and must show which dimensions are
quarantined. Section 04's eligibility narrowed from "T1 and T4" to **T1 only**.

A later GPQA correction is understood to exist **only on the unreviewed T-009
branch**. It is **not** adopted, not reproduced, and not counted toward
readiness here.

### 2. Context-length convention corrected

v1 filed this as an ambiguous *unit*. The unit is not ambiguous: it is
**tokens**, and that is retained as canonical in both documents.

What is genuinely open is the **analysis scope** — the feasible C7-supported
range, the representative regimes, and the sensitivity grid used for the Q3
critical-context analysis. The risk is not a wrong unit; it is reporting a
critical context length without saying over which range it was searched, which
turns a grid endpoint into a discovered threshold. Owner M2 (T-010), gate G3.

### 3. G2 strengthened — new unit-regime conditions (G2-U)

The Q2 unit-regime hazard was recorded in v1's audit but no gate defended
against it. G2 now requires **G2-U**, four conditions on any final or
generalized IF3:

| # | Condition |
| --: | --- |
| U1 | Externally emitted IF3 uses one canonical convention consistent with the classic IF3: **raw parameter count, raw token count** |
| U2 | An internal fit may use billions for conditioning, but parameters **and** validity box must be transformed consistently before emission |
| U3 | An executable **unit-equivalence check**: prediction at the same physical `(N, D, Q)` point must be invariant across internal-billions vs external-raw representation, to a stated tolerance |
| U4 | An IF3 whose parameter units and validity-box units disagree is **rejected**, not repaired at the consumer |

U3 is deliberately an invariance check on a *prediction* rather than an
assertion about parameters: a scale factor applied consistently to `N` and `D`
is absorbed into `A` and `B` by the functional form, so emitted parameter values
alone cannot reveal which regime produced them.

Scope: U3 describes a check to be written at T-008 closure; it does not exist
yet and is not claimed to. **`src/interfaces.py` is not changed** — U1–U4 are
review-time acceptance conditions, not new schema fields.

### Validation of the delta

`selftest_interfaces.py` 21 assertions pass; `git diff --check` clean;
public-safety gate passes. T-012 remains `todo`; the dependency graph is
unchanged; PR #9 remains draft and unmerged. No scientific code, numerical
artifact, `TASKS.md` entry, another member's path, or PR #8 was touched.

## Next action — exact trigger for resuming T-012

**T-012 final integration resumes when G1 through G5 have all passed**, i.e.
when T-007 and T-009 are reviewed and accepted, T-008 is closed with a final
IF3 or an explicitly justified alternative, and T-010 and T-011 are accepted.

The immediate next action in the project is **not** T-012: it is **T-007
review**, which unblocks T-008 closure. Until then this branch is a preparatory
checkpoint and its draft PR must not be merged as though integration were done.
