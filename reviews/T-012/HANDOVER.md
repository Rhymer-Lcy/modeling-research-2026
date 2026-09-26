# T-012 handover

| Field | Value |
| --- | --- |
| Task | T-012 |
| Owner | M1 |
| Status | `todo` in `TASKS.md`. **Stage A (v3) manuscript fast-track complete; T-012 final integration remains blocked on T-010.** |
| Specification | `worklog/specs/T-012.md` v3 (L3), archived prospectively on this branch |
| Timestamp | 2026-09-27T01:40:37+08:00 (Stage A) |
| Base | `583b8db` (accepted `main`; unchanged at the end of Stage A) |
| Branch / PR | `docs/m1-T012-manuscript-stage-a` / Draft PR (opened after the push; see the PR itself for its number) |

**T-012 final integration remains blocked on T-010.** Stage A drafts only what
accepted evidence supports and resolves the 2026 LaTeX template question. It is
not final integration: no final abstract, no Question 3 content, no
cross-question synthesis. The dependency `T-010 + T-011 -> T-012` is unchanged.

## Stage A (T-012 v3)

### A. Scope

Two objectives, per v3: (1) arbitrate the 2026 LaTeX implementation among the
current `gmcmthesis` build, the M3-contributed template and a hybrid, against
the two official 2026 organizer files; (2) draft every manuscript component
that accepted evidence supports, without consuming pending Question 3 work.

### B. Accepted evidence consumed

All from accepted `main` at `583b8db`:

- Q1 (T-007): `reviews/T-007/HANDOVER.md`; `results/tables/q1-scalarization-contract.md`,
  `q1-transform-contract.md`, `q1-quality-analysis.md`, `q1-a1-a3-comparison.md`,
  `q1-a16-coverage.md`, `q1-conflict-analysis.md`, `q1-method-sensitivity.md`,
  `q1-missingness-sensitivity.md`, `q1-input-audit.md`, `q1-mixture-selection.md`,
  `q1-mixture-validation.md`, `q1-cross-scale.md`, `q1-extrapolation.md`,
  `q1-mixture-effects.md`, `q1-if1-summary.md`, `q1-if2-summary.md`; `configs/q1.yaml`
  (family definition, selection rule).
- Q2 (T-008): `reviews/T-008/HANDOVER.md`; `results/tables/q2-classic-fit.md`,
  `q2-uncertainty-robustness.md`, `q2-final-closure.md`, `q2-quality-data-audit.md`,
  `q2-substitution.md` (analytical identities only; its B7-based numbers are not used).
- Q4 panel (T-009): `results/tables/q4-model-strata.md`, `q4-eligibility.md`,
  `q4-c8-reconciliation.md`, `q4-detailed-task-analysis.md`.
- Q4 (T-011): `reviews/T-011/HANDOVER.md` (including its T-012 consume / preserve /
  must-not contract); `results/tables/q4-evolution-population.md`, `q4-bridge.md`,
  `q4-decomposition.md`, `q4-frontier-forecast.md`, `q4-forecast-robustness.md`.
- Official problem wording: the canonical local problem statement (DOCX), read for
  the restatement only.

Two accepted-artifact facts a reader should know:

- The model-clustered bootstrap intervals in `q2-classic-fit.md` and
  `q2-uncertainty-robustness.md` differ slightly (e.g. A: [405.541, 406.784] vs
  [405.477, 406.776]). Both scripts request 400 replicates but use different
  seeds (the configured seed vs `20260923`); the difference is Monte Carlo, the
  point estimates are identical. The manuscript quotes
  `q2-uncertainty-robustness.md` throughout, as the T-008 handover designates.
  Not a load-bearing disagreement.
- The C8 reconciliation on `main` now reproduces **five** of six dimensions
  (GPQA included); `paper/INTEGRATION_PLAN.md` still records the older "4 of 6".

### C. Pending evidence deliberately NOT consumed

- T-010 in any form: the M4 branch `exp/m4-T010-q3-allocation` (observed to exist
  on the remote; **not opened, not read**), the old Draft PR #17 and its M2
  branch, and the M2 frozen handoff draft. **No Question 3 number, method or
  conclusion entered the manuscript.**
- The quarantined original data-description PDF and the sanitized derivative
  PDF (neither opened).
- Social-media screenshots and other teams' estimates.

### D. Root-file archival receipts

| Incoming root file | Bytes | SHA-256 | Canonical destination | Action |
| --- | ---: | --- | --- | --- |
| official format specification (DOCX) | 93,167 | `46d2e2a8…0e16` | `docs_local/gmcm-2026/source/paper_format_specification.official.docx` | byte-identical to the T-014 canonical copy; canonical kept, root copy removed |
| official Word template (DOC) | 894,976 | `195b06cf…2e29` | `docs_local/gmcm-2026/source/paper_template.official.doc` | byte-identical to the T-014 canonical copy; canonical kept, root copy removed |
| M3 LaTeX template (ZIP) | 2,145,953 | `71f4b24c…586c` | `docs_local/gmcm-2026/contrib/m3_latex_template.contributed.zip` | new; copied, re-hashed equal, root copy removed |

All three canonical files re-hashed equal after archival. None of the three
original filenames remains at the repository root; none was ever staged. No
conflict, so `incoming-conflict/` was not needed.

### E. M3 package

Hash equals the supervisor-inspected reference (`71f4b24c…586c`,
2,145,953 bytes). 33 members, 29 files: sources (`main.tex`, `setup.tex`,
`config.tex`, `fonts.tex`, `fonts-overleaf.tex`, `latexmkrc`, `README.md`,
five `sections/*.tex`), four `assets/*` images, `fonts/README.md` (no fonts
shipped), build output (`main.pdf/.log/.aux/.out`), and eight `(1)` duplicates
(seven byte-identical, `config(1).tex` empty). Extracted only to
`docs_local/gmcm-2026/audit/m3-latex-template/`. Classified as contributed,
unofficial implementation evidence. Its geometry values were treated as
unverified; its placeholder references and prose were not used.

### F-H. Template decision: **HYBRID**

Full comparison in `paper/TEMPLATE_DECISION_2026.md`. In short: the current
build already met every explicit textual rule (re-tested); its one deviation
from the official cover was the missing four-logo row. M3 surfaced that row;
the four images were verified against the official Word template (two
byte-identical embedded images, the sponsor mark as its exact embedded stream,
the 2026 host-university seal as a lossless crop of the embedded composite; no
stale edition, no text layer, no team identity) and then **extracted directly
from the official template** into the ignored
`docs_local/gmcm-2026/cover-assets/`. Rendered at 300 dpi, the row matches the
official cover within 0.7 mm (positions) and 1.4 mm (widths). Everything else
M3 offers is equivalent or rests on unverified values and manual reference
ordering, so ADOPT M3 CORE was rejected.

Files changed: `paper/format_2026.tex` (optional official logo row replacing the
stale class row; explicit empty PDF metadata), `scripts/build_paper.ps1`
(`-Submission` mode; readiness report on every build; a submission build is
always clean), `paper/FORMAT_2026.md` (2026 update section; T-014 history kept),
`paper/TEMPLATE_DECISION_2026.md` (new). `scripts/setup_template.ps1` unchanged.

### I. Rendered-build audit

- `scripts/build_paper.ps1 -Clean`: exit 0, **17 pages**, 0 undefined references
  or citations, 0 `Missing character`, 0 overfull boxes.
- Every page rendered and inspected. Defects found and fixed during the audit:
  a decomposition table clipped at the right margin (transposed); three further
  overfull tables (fixed column widths / shorter labels); justified CJK text in
  fixed-width columns (ragged-right); appendix numbering printing "1.1" and
  "表 1.10" (appendix-local numbering); a BibTeX stack error from an
  `@inproceedings` entry (re-entered in the journal pattern PMLR itself uses).
- Submission gate: with a temporary fixture `paper/team.tex` (deleted
  afterwards), `-Submission` passed every check; the five fixture identity
  strings appeared on page 1 only, and in neither the document metadata nor
  the bookmarks. The asset guard was mutation-tested (a hidden asset fires both
  the hash check and the "row not drawn" check on a clean build; the cover then
  has no row at all).
- Text layer: no previous edition, no previous host, no fixture residue.
- F1-F16: all satisfied for a local submission build, **except that the
  AI-use section cannot yet be written** (see M). F15 verified: a clean clone
  builds with no logo row and says so.

### J. Sections drafted (all from accepted evidence)

| Section | Content | Evidence |
| --- | --- | --- |
| 01 restatement | background, four questions, evidence classes | problem statement |
| 02 analysis | Q1, Q2, Q4 analysis (Q3 subsection empty) | problem statement; the accepted handovers |
| 03 assumptions | seven assumptions; notation | the accepted rules they encode |
| 04 preprocessing | indicator scalarisation and direction; recipe data; B-table roles; panel, C8 reconciliation, MATH quarantine, C3 audit, C4 coverage | T-007, T-008, T-009, T-011 tables |
| 05-1 Q1 | quality model and domain Q; conflict definition, measurement, rule, extension check; mixture model, selection, validation by role, 1M effects; Q with p; extrapolation | T-007 tables, `q2-final-closure.md` (Q(p)) |
| 05-2 Q2 | classic fit with three uncertainty families; generator-recovery finding; external validation and validity box; candidate quality form, gates, **not adopted**; marginal effects, elasticities and the parameter-equivalence condition as analytical identities | T-008 tables |
| 05-4 Q4 | population and the four required declarations; loss-to-score mapping (degenerate, no slope); parameter vs compute decomposition; the three forecast kinds with date-clock sensitivity beside the headline; uncertainty components and backtest; BBH/MUSR task-level analysis; C3/C4 statements | T-009 and T-011 tables and the T-011 contract |
| 06 validation | evidence-type table; sensitivity; error analysis | as above |
| 07 evaluation | strengths, weaknesses, extensions (Q1/Q2/Q4) | as above |
| 08 appendix | reproduction entry points; AI-use subsection as structure only | repository |
| references | 8 verified entries, all cited | Crossref, arXiv API, PMLR page |

The T-011 contract was followed item by item: 50.89 / 60.80 are the historical
continuation (not a compute-slowdown answer); the parameter-scale scenarios are
labelled non-binding; the compute answer is only "在给定转移假设下的敏感性结果";
IF4 is degenerate with no slope; no bridge-based forecast; C3, C4 (94 / 62) and
T-009 BBH/MUSR are all stated; MATH C8 children are excluded; the frontier-set
split is labelled post-failure.

### K. Still blocked on T-010

`05-3-model-q3.tex` (six subsection headings, comments only), the Question 3
subsection of `02-analysis.tex`, the Question 3 rows of the validation tables,
`00-abstract.tex` (not finalized; placeholders only), and any cross-question
conclusion in `07-evaluation.tex`. A local-only abstract scaffold with a
`Q3 BLOCKED` slot exists outside the repository.

### L. Page count

17 pages in the current build (mechanical fact).

### M. Remaining manuscript risks

1. **AI-use disclosure.** The organizer's 2026 AI-use regulation is not in the
   local archive of official material, so appendix A.2 is structure only and no
   declaration is written. The official document must be obtained before
   submission.
2. **Conflict causes.** The accepted Q1 artifacts measure conflict thoroughly
   but contain no pair-level cause analysis; the manuscript states the observed
   pattern and labels the construct explanation as untested.
3. **References.** Two candidate references (quantile regression, block
   bootstrap) were omitted because their full page ranges could not be verified.
   The problem statement's own reference list misattributes RegMix (actual
   authors Liu, Zheng, Muennighoff et al.; ICLR 2025) and pairs the arXiv title
   of Hoffmann et al. with the NeurIPS venue, whose published title differs; the
   manuscript cites the verified arXiv records instead.
4. **No figures.** No accepted figure exists (T-011 had no plotting library).
   Stage B may add figures only through an `environment.yml` decision.
5. **Decorative cover labels** still fall back to FandolHei where LiSu is absent
   (T-014 retained ambiguity 2, unchanged).
6. **Number trace is local.** The manuscript-to-artifact number check
   (283/283 tokens matched; two planted errors caught) and the identifier scan
   live in ignored `scratch/`; Stage B should decide whether to track them for
   gate G7. The trace cannot detect a valid artifact number placed in the wrong
   clause; that relationship was reviewed by hand.
7. `paper/INTEGRATION_PLAN.md` gate states are stale (written before T-007,
   T-008, T-009 and T-011 closed); refresh at Stage B.

### N. Stage B trigger

**T-010 accepted and merged to `main` after independent supervisory review.**
Then: write Question 3, the Question 3 rows and subsections, the final abstract
(at most two pages) and the cross-question synthesis; refresh the integration
plan; re-run the full format, number-trace and visual audit; build with
`-Submission`.

### Validation actually run

`git diff --check` clean before every commit; `scripts/check_public_safe.ps1`
PreCommit PASS before every commit and PrePush PASS before the push;
`scripts/build_paper.ps1 -Clean` and `-Submission` (fixture identity) as in I;
number trace (283/283, mutation-tested); visible-text identifier scan (0 hits,
mutation-tested); a review of every Chinese-numeral quantity against what it
counts (one miscount fixed).

---

# Earlier stages (v1 / v2): pre-integration readiness — historical record

The sections below are the accepted pre-integration record, retained unchanged.
Their gate states describe `main` as of 2026-09-24.

| Field | Value |
| --- | --- |
| Status then | **PRE-INTEGRATION CHECKPOINT REVIEWED — ACCEPTED FOR MERGE** |
| Disposition | Supervisory review passed at `36abefc`. |
| Timestamp | 2026-09-24T11:30:00+08:00 |
| Base | `87fbce3` |
| Branch / PR | `chore/m1-T012-preintegration` / draft PR |

**This part describes preparatory work only.** No scientific integration was
performed.

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

## Final disposition

**PRE-INTEGRATION CHECKPOINT REVIEWED — ACCEPTED FOR MERGE.**

Supervisory review of the checkpoint passed at `36abefc`. The checkpoint is
merged as **integration governance**. What that does and does not mean, stated
explicitly so the merge cannot later be read as more than it is:

* **Merging this checkpoint does NOT start final T-012 integration.**
* **T-012 remains `todo`** in `TASKS.md`, which is unchanged by this closeout.
* **G1-G5 remain unmet** exactly as recorded above: T-007 `wip`, T-008 `wip`
  with a draft PR open, T-010 `todo`, T-009 `wip`, T-011 `todo`.
* **Final T-012 still requires T-010 + T-011.** The dependency
  `T-010 + T-011 -> T-012` is unchanged and remains authoritative.
* No scientific content, readiness conclusion, evidence state or gate state was
  altered by this closeout. It records a disposition only.

## Next action — exact trigger for resuming T-012

**T-012 final integration resumes when G1 through G5 have all passed**, i.e.
when T-007 and T-009 are reviewed and accepted, T-008 is closed with a final
IF3 or an explicitly justified alternative, and T-010 and T-011 are accepted.

The immediate next action in the project is **not** T-012: it is **T-007
review**, which unblocks T-008 closure. Until then this branch is a preparatory
checkpoint and its draft PR must not be merged as though integration were done.
