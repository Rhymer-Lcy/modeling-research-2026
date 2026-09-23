# T-009 handover

| Field | Value |
| --- | --- |
| Task | T-009 |
| Owner | M3 |
| Status | wip |
| Timestamp | 2026-09-24T00:59:39+08:00 |
| Base | `d9ded87` |
| HEAD | `28cf330` |
| Branch / PR | direct to `main` (all touched paths are owned by T-009) |

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

## Completed work

- Root-caused both reconciliation failures: GPQA fixed (pooled vs averaged
  rescale); MATH quarantined as a C1/C8 source mismatch, not a normalisation
  error. The tolerance was left at 0.5 pt, never lowered to force a pass.
- Canonical C1/C2/C3/C4 loaders that preserve each table's provenance and
  column origin.
- Deterministic join policy (exact → normalised → explicit alias map; no fuzzy
  matching), applied to the leaderboard↔C4 linkage.
- Model-type strata A–E with per-stratum coverage counts.
- Open-model eligibility fields and rules (positive-signal only), reported as
  counts rather than as a chosen population.
- Explicit date convention (Epoch publication date primary, leaderboard
  submission date fallback), with a per-row `date_source`/`date_confidence`.
- Quantified the C1/C2/C3 relationship and duplicate structure.
- Preserved the C8 reconciliation and added one genuinely detailed task-level
  aggregation: a one-way variance decomposition of the per-subtask scores.
- Assembled the panel (4,497 unique models, 48 columns) and wrote the derived
  CSV to `data_local/problem-f/derived/q4-panel.csv`.

## Evidence

**Code**

- `src/panel/leaderboard.py` — C8 parser, `max(0,(raw-baseline)/(1-baseline))*100`
  rescale, grouped-task handling, `subtask_scores`.
- `src/panel/sources.py` — C1/C2/C3/C4 loaders with canonical column maps.
- `src/panel/matching.py` — model-name normalisation used by every join.
- `src/panel/config.py` — type→stratum mapping, open-licence and test-pattern sets.
- `src/panel/strata.py` — A–E stratum assignment.
- `src/panel/dates.py` — publication-primary / submission-fallback convention.
- `src/panel/eligibility.py` — open-model eligibility fields and rules.
- `src/panel/c4_link.py` — deterministic leaderboard↔C4 linkage.
- `src/panel/panel.py` — panel assembly and CSV write.
- `src/panel/detail.py` — per-subtask extraction and variance decomposition.

**Regenerable artifacts**

- `results/tables/q4-c8-reconciliation.md`
- `results/tables/q4-c8-diagnosis.md`
- `results/tables/q4-panel-schema.md`
- `results/tables/q4-panel-coverage.md`
- `results/tables/q4-model-strata.md`
- `results/tables/q4-date-coverage.md`
- `results/tables/q4-c4-metadata-coverage.md`
- `results/tables/q4-eligibility.md`
- `results/tables/q4-detailed-task-analysis.md`

**Commands actually run**

```
python scripts/q4_panel_reconcile.py     # verdict PARTIAL: 5/6 reconciled, MATH quarantined
python scripts/q4_panel_diagnose.py      # writes q4-c8-diagnosis.md
python scripts/q4_panel_build.py         # writes the six panel-coverage artifacts + CSV
python scripts/q4_panel_detail.py        # writes q4-detailed-task-analysis.md
python scripts/q4_panel_selftest.py      # PASS (20 assertions)
python scripts/selftest_interfaces.py    # PASS (21 assertions)
powershell -File scripts/check_public_safe.ps1 -Mode PreCommit   # PASS (74 files)
git diff --check                         # clean
```

## Key results

- **Reconciliation**: five of six dimensions reproduce the published summary
  within 0.5 pt (IFEval, BBH, GPQA, MUSR, MMLU-PRO). MATH Lvl 5 is quarantined:
  154 models carry `exact_match = 0` in every C8 MATH subtask, 119 of them
  scored above zero by the summary — a source mismatch, not a normalisation
  error (see `q4-c8-diagnosis.md`).
- **Panel**: 4,497 unique models, 48 columns; C2 is C1 plus three Epoch columns
  (same rows, same order), C1/C3 share 4,494 models with 0 score mismatches.
- **C4 linkage**: 94 models linked deterministically (50 `hf_id`, 6 `org`, 38
  `name`), 4,403 unlinked; linkage is concentrated in stratum A (19.8%).
- **Strata**: A = 324 (7.2%), B = 695 (15.4%), C = 1,752 (39.0%), D = 1,712
  (38.1%), E = 14 (0.3%).
- **Dates**: primary (Epoch publication) 465 (10.3%), fallback (submission)
  4,021 (89.4%), none 11 (0.2% — genuine missing source data, verified).
- **Detailed task analysis**: per-subtask score variance is 41.0% between models
  for BBH, 60.4% for MATH Lvl 5, 51.6% for MUSR (one-way ICC).
- **Eligibility**: 1,939 models satisfy open weights AND params AND all six
  scores AND a date — a ceiling count, not an adopted population.

## Validation

- `scripts/q4_panel_selftest.py` — 20-assertion mutation self-test: each
  assertion breaks-and-recovers its target (normalisation, rescale, stratum,
  C4-link exactness, panel invariants), so the checks demonstrably can fail.
- `scripts/selftest_interfaces.py` — 21 assertions, PASS (T-009 consumes
  interfaces without breaking the shared contract).
- `scripts/check_public_safe.ps1 -Mode PreCommit` — PASS, 74 files.
- `git diff --check` — clean.

## Interfaces and downstream impact

- Consumes: C1/C2/C3/C4 under `data_local/problem-f/raw/…` (via `src/paths.py`),
  the shared leaderboard interfaces.
- Produces: `data_local/problem-f/derived/q4-panel.csv` (ignored, regenerable
  from `scripts/q4_panel_build.py`); nine tracked `results/tables/q4-*.md`.

What T-011 can rely on: the model-type stratum, the analysis date (with its
source recorded), the open-weights eligibility field, the C4 metadata where
linked, and five of six dimensions' per-task records (IFEval, BBH, GPQA, MUSR,
MMLU-PRO).

What T-011 must **not** rely on: the MATH Lvl 5 *per-subtask* records (the
summary score is fine; the subtasks describe a different evaluation run); the
C3 timeseries as a leaderboard panel (it is reported but not folded in); the
4,403 unlinked C4 rows as though their metadata were missing-at-random; the
training-compute field (non-null in only 62 rows).

## Deviations from plan

- Committed directly to `main` rather than a branch+PR: every touched path
  (`src/panel/`, `scripts/q4_panel_*`, `results/`, `reviews/T-009/`,
  `worklog/M3.md`) is owned by T-009, which AGENTS.md routes to direct commit.

## Negative results and rejected alternatives

- **GPQA**: the first pass rescale-and-average per subtask, which shifted the
  score by ~0.4 pt (median) because the three subtasks have very different
  sample sizes. The harness pools first, then rescales; adopting that reproduces
  the published value. Recorded in `q4-c8-diagnosis.md`.
- **MATH Lvl 5**: the all-zero `exact_match` pattern is irreconcilable by any
  normalisation and points to two different upstream datasets
  (`open-llm-leaderboard-old/results` for C1 vs `open-llm-leaderboard/results`
  for C8). Not fixed, deliberately quarantined.
- **Fuzzy matching for C4**: rejected in favour of the deterministic ladder;
  a fuzzy match would manufacture links and inflate coverage without provenance.
- **C9 parquet** (`data_local/problem-f/raw/…`): unreadable without `pyarrow`
  and redundant with C1, so the panel uses C1/C2/C3/C4.

## Known limitations and open risks

- MATH Lvl 5 per-subtask records are not usable for per-task analysis; the
  quarantine must be resolved (likely by re-deriving C8 from the same dataset
  as C1) before T-011 can use MATH subtasks.
- C4 linkage is 2.09% by design (deterministic names only); most fine-tunes and
  merges (strata C/D) are absent from Epoch AI under a matching name.
- Training-compute is non-null for only 62 rows, bounding any
  compute-conditioned forecast.
- 11 models have no date of any kind (genuine missing source data, e.g. the
  `granite-3.0-*` series, `dbrx-base`, `OLMo-1.7-7B-hf`).
- **Push is blocked**: `origin` is the read-only `gitclone.com` mirror
  (`https://gitclone.com/github.com/Rhymer-Lcy/modeling-research-2026.git`),
  which returns 504 on push; a direct `github.com` connection resets and SSH is
  blocked. The commits are local until a writable remote is available.

## Next action

Provide a writable upstream (or a proxy) for `github.com/Rhymer-Lcy/
modeling-research-2026` so these commits can be pushed and reviewed; then M3
moves to T-011 with the panel as its input.
