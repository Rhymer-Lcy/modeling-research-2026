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
3. **Three conventions are ambiguous and were deliberately NOT resolved**: the
   time basis (publication vs evaluation date), the context-length unit and
   regime, and whether the declared benchmark score scale is higher-is-better.
   Each is assigned to the task that first needs it. Resolving any of them here
   would be a scientific decision taken inside an integration-planning task.

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

## Next action — exact trigger for resuming T-012

**T-012 final integration resumes when G1 through G5 have all passed**, i.e.
when T-007 and T-009 are reviewed and accepted, T-008 is closed with a final
IF3 or an explicitly justified alternative, and T-010 and T-011 are accepted.

The immediate next action in the project is **not** T-012: it is **T-007
review**, which unblocks T-008 closure. Until then this branch is a preparatory
checkpoint and its draft PR must not be merged as though integration were done.
