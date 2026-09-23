# T-009 handover

| Field | Value |
| --- | --- |
| Task | T-009 |
| Owner | M3 |
| Status | wip |
| Timestamp | 2026-09-24T02:00:00+08:00 |
| Base | `d9ded87` |
| HEAD | `bbef60f` |
| Branch / PR | `exp/m3-T009-q4-panel` (no PR: push blocked, see Known limitations) |

## Scope

Q4 (Problem F) needs a defensible, reproducible foundation before any
frontier or decomposition can be built on it: a panel of open model release
points carrying dates, parameters and the six leaderboard dimensions, plus the
per-task evidence that sits *under* the summary table. T-009's job is to (1)
reconstruct the six summary dimensions from the raw C8 per-task records so the
per-task corpus is trusted before anything finer uses it, (2) assemble the
canonical panel from C1/C2/C3/C4 with deterministic joins and explicit
provenance, and (3) define model-type strata and an open-model eligibility
framework. It explicitly does **not** choose T-011's population or do any
forecasting.

This package is the *corrective review checkpoint*: the first checkpoint's
primary detailed-task table still displayed a quarantined MATH ICC. That has
been made executable (quarantined MATH cannot enter the primary extraction),
the GPQA and MATH evidence surfaces were strengthened, and the C4 join, strata
and C3 provenance were audited rather than inflated.

## Completed work

- Root-caused both reconciliation failures: GPQA fixed (pooled vs averaged
  rescale); MATH quarantined as a C1/C8 source mismatch. The tolerance is
  unchanged at 0.5 pt, never lowered to force a pass.
- Canonical C1/C2/C3/C4 loaders that preserve each table's provenance.
- Deterministic join policy (exact → normalised → explicit alias map; no fuzzy
  matching). C4 identity keys that are duplicated in C4 are now **ambiguous and
  left unlinked** instead of taking the first row.
- Model-type strata A–E with per-stratum coverage, plus the raw organizer
  `Type` distribution proving each stratum's origin.
- Open-model eligibility fields and rules (positive-signal only), reported as
  counts rather than as a chosen population.
- Explicit date convention (Epoch publication date primary, leaderboard
  submission date fallback), with per-row `date_source`/`date_confidence`; the
  11 no-date rows are verified source missingness, not join loss.
- Quantified the C1/C2/C3 relationship, C3 duplicates, and C3's stable-key
  failure (duplicate rows have distinct score vectors).
- Per-dimension reconciliation status table (reconciled / source-mismatch /
  unresolved) with paired-delta distributions for all six dimensions.
- Detailed task-level analysis: per-subtask availability/median/IQR/variance,
  one-way between/within-model variance decomposition (ICC) and within-model
  imbalance for the reconciled subtask dimensions BBH and MUSR **only**; MATH
  is excluded by construction and shown in a quarantine appendix.
- Assembled the panel (4,497 unique models, 48 columns) and wrote the derived
  CSV to `data_local/problem-f/derived/q4-panel.csv`.

## Evidence

**Code**

- `src/panel/leaderboard.py` — C8 parser, `max(0,(raw-baseline)/(1-baseline))*100`
  rescale, grouped-task handling, GPQA pooled rule, `subtask_scores`.
- `src/panel/detail.py` — `RECONCILED_DIMENSIONS` / `QUARANTINED_DIMENSIONS`
  allowlists, `extract_subtasks(include_quarantined=…)`, `subtask_profile`,
  `within_model_imbalance`, `variance_decomposition`.
- `src/panel/c4_link.py` — deterministic linkage, uniqueness enforcement,
  `_candidate_audit` sequential ambiguity accounting.
- `src/panel/sources.py`, `matching.py`, `config.py`, `strata.py`, `dates.py`,
  `eligibility.py`, `panel.py` — loaders, keys, strata, dates, eligibility,
  assembly.

**Regenerable artifacts**

- `results/tables/q4-c8-reconciliation.md` — acceptance test (PARTIAL by design:
  MATH quarantined).
- `results/tables/q4-c8-diagnosis.md` — per-dimension status, GPQA pooled-vs-
  averaged evidence, MATH source-mismatch metadata audit.
- `results/tables/q4-detailed-task-analysis.md` — primary BBH/MUSR subtask
  profile + variance decomposition; MATH quarantine appendix.
- `results/tables/q4-panel-schema.md`, `q4-panel-coverage.md`,
  `q4-model-strata.md`, `q4-date-coverage.md`, `q4-c4-metadata-coverage.md`,
  `q4-eligibility.md` — panel provenance, C4 join audit, strata, dates, C4
  metadata coverage, eligibility counts.

**Commands actually run**

```
python scripts/q4_panel_reconcile.py     # PARTIAL: 5/6 reconciled, MATH quarantined (exit 1 by design)
python scripts/q4_panel_diagnose.py      # writes q4-c8-diagnosis.md
python scripts/q4_panel_build.py         # writes the six panel artifacts + CSV
python scripts/q4_panel_detail.py        # writes q4-detailed-task-analysis.md (BBH/MUSR only)
python scripts/q4_panel_selftest.py      # PASS (28 assertions)
python scripts/selftest_interfaces.py    # PASS (21 assertions)
powershell -File scripts/check_public_safe.ps1 -Mode PreCommit   # PASS (75 files)
git diff --check                         # clean
```

## Key results

- **Dimension status** (0.5 pt rule, unchanged): IFEval 97.6%, BBH 98.3%, MUSR
  98.1%, MMLU-PRO 98.3%, GPQA 98.0% within tolerance → reconciled. MATH Lvl 5
  15.4% → **source-mismatch**: 154 models carry `exact_match = 0` in every C8
  MATH child, 119 of them have a positive C1 summary score (max |delta|
  62.5). C8 MATH metadata audit records metric name (`exact_match,none`),
  effective sample counts, baselines, task version/hash, harness git hash,
  evaluation timestamps — none of which reconcile the contradiction.
- **GPQA rule**: pooled-then-rescaled reproduces C1 (median abs. delta 0.0000,
  98.0% within 0.5 pt, n=1,852); the rejected rescale-then-unweighted-average
  fails (median abs. 0.3952, 59.1% within). The fixed rule is the general
  harness aggregation (pool the three children, rescale against the 4-way
  baseline); no per-model offset or fitted correction exists anywhere. Status
  **reconciled** under the unchanged acceptance rule.
- **Detailed task analysis (primary)**: BBH ICC 0.410 (1,860 models, 24
  subtasks, 44,640 observations; median within-model SD 19.52, IQR 8.45);
  MUSR ICC 0.516 (1,856 models, 3 subtasks, 5,568 observations; median
  within-model SD 5.56, IQR 5.30). MUSR has 4 missing models per subtask
  (0.2%). MATH is absent from the primary tables by construction.
- **Panel**: 4,497 unique models, 48 columns; C2 is C1 plus three Epoch columns
  (same rows, same order); C1/C3 share 4,494 models with 0 score mismatches.
- **C4 join**: 94 linked (50 `hf_id`, 6 `org`, 38 `name`, 0 alias), 4,403
  unlinked. Sequential audit: 1 row ambiguous in C4 (`Apollo 7B` vs
  `Apollo-7B` duplicate rows), 7 rows ambiguous on the leaderboard name side,
  4,395 truly unmatched. Linkage concentrated in stratum A (19.8%).
- **Strata**: A = 324, B = 695, C = 1,752, D = 1,712, E = 14; D is exactly the
  organizer's `base merges and moerges` label (1,712 rows), not keyword
  inference. Raw `Type` distribution is reproduced in `q4-model-strata.md`.
- **C3 provenance**: 4,599 rows = 4,573 Open LLM Leaderboard + 26 Historical;
  years 2019–2025; 79 duplicate `(model, year, source)` key rows, and all 79
  duplicate-model groups carry **distinct score vectors** — C3 has no unique
  evaluation key and stays an auxiliary timeseries, not panel rows.
- **Dates**: primary (Epoch publication) 465 (10.3%), fallback (submission)
  4,021 (89.4%), none 11 (0.2% — all three date columns NaN together; C1 has 12
  blank submission dates → 11 unique models; models listed in the artifact).
- **Eligibility**: 1,939 models satisfy open weights AND params AND all six
  scores AND a date — a ceiling count, not an adopted population.

## Validation

- `scripts/q4_panel_selftest.py` — 28-assertion mutation self-test (was 20):
  new checks prove quarantined MATH cannot enter the primary extraction, an
  ambiguous duplicated C4 identity key stays unlinked, the sequential audit
  accounts for every panel row, and the GPQA pooled rule equals the fixed
  formula rather than the unweighted child average. One new assertion genuinely
  failed during development (wrong `_gpqa` call signature in the test itself)
  and was fixed — the checks demonstrably can fail.
- `scripts/selftest_interfaces.py` — 21 assertions, PASS.
- `scripts/check_public_safe.ps1 -Mode PreCommit` — PASS, 75 files.
- `git diff --check` — clean.
- All nine tracked result artifacts regenerate from their scripts; no value is
  hand-edited into an artifact.

## Interfaces and downstream impact

- Consumes: C1/C2/C3/C4 under `data_local/problem-f/raw/…` (via `src/paths.py`),
  the shared leaderboard interfaces.
- Produces: `data_local/problem-f/derived/q4-panel.csv` (ignored, regenerable
  from `scripts/q4_panel_build.py`); nine tracked `results/tables/q4-*.md`.

What T-011 can rely on: the model-type stratum, the analysis date (with its
source recorded), the open-weights eligibility field, the C4 metadata where
linked, and five of six dimensions' per-task evidence (IFEval, BBH, GPQA, MUSR,
MMLU-PRO) — with BBH and MUSR the only dimensions having a valid per-subtask
matrix for detailed task-level analysis.

What T-011 must **not** rely on: MATH Lvl 5 *per-subtask* records (the C1
summary score is fine; C8 MATH children describe a different source/run); C4
linkage as representative coverage (94/4,497, concentrated in stratum A — a
C4-conditioned analysis must report the linked subset explicitly); C3 as panel
rows (duplicate keys, distinct score vectors); the training-compute field
(non-null in only 62 rows); the 11 no-date rows.

## Deviations from plan

- The original execution specified a branch+push+PR; the work landed on
  `main` locally first (two commits `28cf330`, `25febc5`). The corrective
  round moved the review surface to branch `exp/m3-T009-q4-panel` (now at
  `bbef60f`) and made all further commits there. Local `main` still points at
  `25febc5` and has **not** been reset or force-pushed; M1 decides whether to
  move it.

## Negative results and rejected alternatives

- **GPQA**: the first pass rescale-and-average per child shifted the score by
  ~0.4 pt (median) because main/diamond/extended have very different sample
  sizes (448/198/546). The harness pools first, then rescales; adopting that
  reproduces the published value. Recorded in `q4-c8-diagnosis.md`.
- **MATH Lvl 5**: the all-zero `exact_match` pattern is irreconcilable by any
  normalisation and points to two different upstream datasets
  (`open-llm-leaderboard-old/results` for C1 vs `open-llm-leaderboard/results`
  for C8). Not fixed, deliberately quarantined.
- **First-row fallback for ambiguous C4 identity keys**: rejected. A duplicated
  C4 key (e.g. `Apollo 7B` / `Apollo-7B`) is now reported ambiguous and left
  unlinked rather than silently choosing the first row.
- **Fuzzy matching for C4**: rejected in favour of the deterministic ladder; a
  fuzzy match would manufacture links and inflate coverage without provenance.
- **C9 parquet**: unreadable without `pyarrow` and redundant with C1, so the
  panel uses C1/C2/C3/C4.

## Known limitations and open risks

- MATH Lvl 5 per-subtask records remain unusable; resolving the quarantine
  needs a C8 derived from the same dataset as C1 (T-011 must not consume C8
  MATH children before then).
- C4 linkage is 2.09% by design (deterministic keys only) and is not
  missing-at-random: any compute/scale decomposition that conditions on C4
  fields is limited to the 94 linked rows (62 with training compute) and must
  say so.
- 11 models have no date of any kind (genuine source missingness, listed).
- `src/panel/detail.py` hard-codes the quarantine as module constants
  (`QUARANTINED_DIMENSIONS`); if the MATH source issue is later resolved, those
  constants and the selftest must change in the same commit.
- **Push is blocked**: `origin` is the read-only `gitclone.com` mirror
  (`https://gitclone.com/github.com/Rhymer-Lcy/modeling-research-2026.git`),
  which returns 502/504 on push; a direct `github.com` connection resets and
  SSH is blocked. All five commits exist only locally on
  `exp/m3-T009-q4-panel`; no PR can be opened until a writable remote is
  available.

## Next action

Provide a writable upstream (or a proxy) for `github.com/Rhymer-Lcy/
modeling-research-2026` so `exp/m3-T009-q4-panel` can be pushed and a Draft PR
opened; then M3 moves to T-011 with the panel and the BBH/MUSR task-level
evidence as input.
