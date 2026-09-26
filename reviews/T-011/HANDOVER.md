# T-011 handover

| Field | Value |
| --- | --- |
| Task | T-011 - Q4 decomposition, loss/benchmark bridge and frontier forecast |
| Owner | M4 (execution transferred from M3 by `worklog/specs/T-011.md` v2) |
| Status | `wip` in `TASKS.md`; v3 correction executed, this package requests final supervisory review. Not done, not merged |
| Specification | `worklog/specs/T-011.md` v1 (scientific) + v2 (owner / worklog / branch) + v3 (supervisory forecast-interpretation and integration correction; controls where it changes an interpretation) |
| Timestamp | 2026-09-26T11:04:25+08:00 (v3); pre-v3 package 2026-09-26T02:28:11+08:00 |
| Base | `1e487fb` (branch point); synchronized with `main` `4096a97` (the T-011 v3 archival) by merge `648efaf` (merge, not rebase) |
| Reviewed pre-v3 head | `7309fa6` (Draft PR #15 as reviewed; its pre-v3 evidence HEAD was `460df14`) |
| Evidence HEAD | `d0be937` (`fix(evolution): distinguish compute and parameter slowdown [T-011]`: the v3 correction, the last commit carrying code or generated artifacts; later commits touch only this package and the worklog) |
| Branch / PR | `exp/m4-T011-q4-evolution` / Draft PR #15 (https://github.com/Rhymer-Lcy/modeling-research-2026/pull/15), unmerged |

## Scope

Q4 on top of the accepted T-009 panel and the accepted classic IF3 (T-008):
freeze a defensible analysis population and time convention; build and validate
the IF4 loss-to-benchmark bridge; decompose historical benchmark change into
scale-associated and non-scale-associated parts without causal claims; forecast
the open-model frontier at a 12-month primary and a 24-month stress horizon
with honest uncertainty. Execution restarted from synchronized `main`; no state
from M3's working copy or branch was used.

**v3 supervisory correction (this checkpoint).** v3 does not reopen the
analysis. It corrects one interpretation - **parameter-count growth is not
training-compute growth** - and adds downstream integration guards:

- the direct-score 12- and 24-month numbers (50.89, 60.80) are the
  **historical / direct-score continuation baseline**, not a compute-slowdown
  forecast;
- the log-N scenarios are **parameter-scale-growth scenarios**, and are
  non-binding for BC;
- the problem's compute-slowdown request is answered only by the
  **assumption-based transferred compute-slowdown sensitivity**;
- IF4 is stated as a degenerate, no-slope bridge;
- the frontier-set split is classified as post-failure;
- the date-clock range sits beside the headline;
- a mandatory C3 / C4 / C8 contract is added for T-012.

Every table-row number of the reviewed pre-v3 tables is preserved (checked
executably; see Validation), and the IF4 bytes are unchanged.

## Evidence

**Code** (all new; nothing under `src/panel/`, `src/scaling/`, `scripts/q4_panel_*`,
`src/interfaces.py` or `environment.yml` changed)

- `src/evolution/config.py` - every predeclared choice, with its reason
- `src/evolution/receipts.py` - input allowlist, source hashes, IF3 and T-009 receipts
- `src/evolution/population.py`, `scores.py`, `auxiliary.py` - population, score scale, C3 audit
- `src/evolution/bridge.py` - anchors, strata, candidate forms, LOAO selection, IF4 build, `bridge_predict`
- `src/evolution/estimators.py`, `dynamics.py`, `compute.py` - quantile / OLS fits, month-block
  bootstrap, frontier, decompositions, forecast, rolling origin, compute-aware subset
- `src/evolution/claims.py` (v3) - the forecast claim-language contract (historical continuation,
  parameter-scale-growth scenario, assumption-based transferred compute-slowdown sensitivity) and the
  T-012 source-coverage contract checker
- `scripts/q4_evolution_run.py` - the single generator
- `scripts/q4_evolution_selftest.py` - 78 guard assertions with mutation fixtures (22 v1 guards + 8 v3 guards
  + v3 numeric preservation)
- `scripts/q4_evolution_reproduce.py` - two-pass reproduction and input-integrity record

**Regenerable artifacts**

- `results/tables/q4-evolution-population.md` - receipts, score scale, population, time convention, C3
- `results/tables/q4-bridge.md` - anchors, strata, forms, validation, IF4 release, bridge-based translation
- `results/tables/q4-decomposition.md` - scale / non-scale decompositions, compute-aware subset
- `results/tables/q4-frontier-forecast.md` - frontier, forecasts, uncertainty, rolling origin, sensitivities
- `results/tables/q4-forecast-robustness.md` - the declared sensitivity matrix
- `results/tables/q4-evolution-reproduction.md` - two-pass record
- IF4 (local-only): `data_local/problem-f/interfaces/q4-if4-loss-benchmark-bridge.json`

No figure is produced: the pinned environment has no plotting library and T-011
may not edit `environment.yml`. The frontier series a figure would draw are in
the forecast table (see Deviations).

**Commands actually run** (in the project environment, `conda run -n modeling-research-2026 --no-capture-output python ...`)

```
scripts/q4_panel_build.py           # T-009 panel regenerated: 4,497 x 48; six tables byte-identical to HEAD
scripts/q4_panel_reconcile.py       # exit 1 by design (PARTIAL, MATH quarantined); table byte-identical
scripts/q4_panel_diagnose.py        # table byte-identical
scripts/q4_panel_detail.py          # table byte-identical
scripts/q4_panel_selftest.py        # PASS (28 assertions)
scripts/selftest_interfaces.py      # PASS (21 assertions)
scripts/q4_evolution_run.py         # writes the five tables and IF4
scripts/q4_evolution_selftest.py    # pre-v3: PASS (60); after v3: PASS (78)
scripts/q4_evolution_reproduce.py   # REPRODUCTION: PASS (pre-v3 and again after v3)
```

The first six commands are from the pre-v3 execution. After the v3 correction,
`q4_evolution_run.py`, `q4_evolution_selftest.py`, `q4_evolution_reproduce.py`,
`q4_panel_selftest.py` and `selftest_interfaces.py` were re-run on the final code.

and from the repository root: `git diff --check`; `powershell -NoProfile
-ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PreCommit`
(before every commit) and `-Mode PrePush` (before push). Results under
Validation.

## Key results

### Receipts

- **Classic IF3**: SHA-256 `720efea859d3be3b39ac2ee1976f8adaf7a31b8b5b1a71eb72e8ee8f987c8514`,
  read from the tracked `q2-final-closure.md`, not typed; `.validate()` PASS; classic
  five parameters only; raw N / raw D (box lower bounds 7.054e7 and 1.34e8); box N
  7.054e7-1.197e10, D 1.34e8-2.999e11; Q [1, 1] sentinel, and T-011's evaluator has
  no Q argument. No generalized IF3, B7 gamma, B8 or IF2 is read.
- **Source surface**: all 1,973 restored Attachment-C files match the intake
  manifest (size and SHA-256); the manifest matches the hash its receipt
  records. The organizer's problem statement (DOCX) was read for Q4
  requirements. The quarantined data-description PDF was not text-extracted, and
  `docs_local/problem-f/audit/data_description.sanitized.m2.pdf` was hashed only
  and used for nothing.
- **T-009 panel**: rebuilt through `build_panel`; 4,497 x 48, unique by model;
  every count the accepted T-009 tables record matches; all nine T-009 tables
  regenerate byte-identical to their committed blobs.

### Population and time (`q4-evolution-population.md`)

Frozen before any outcome fit, from T-009 fields: dated; params known; six
scores; not a test upload; T-009 stratum A/B/C (D merges and E other excluded);
open weights on T-009's positive signal; and a date-consistency rule (a
publication date more than 30 days after the row's own submission is not that
model's release date). **1,385 models: A (pretrained) 215; BC (chat 338 +
fine-tuned 832) 1,170**, analysed separately. Canonical time is T-009's
`analysis_date` with `date_source` retained: 318 publication-dated (295 via C2,
23 via C4), 1,067 submission-dated.

Two findings about the clock: (1) submission dates span only **2024-06-08 to
2025-03-13**, so the dense history is nine months; (2) C2's organizer
fuzzy-matched publication date on a fine-tune or merge is typically the upstream
base family's date (255 such rows share 35 dates). **Forecast anchor
2025-03-13**; the panel's latest date (2025-09-09) belongs to a date-inconsistent
row removed by the rule.

### Score scale

All six C1 dimensions are verified higher-is-better on the baseline-rescaled
0-100 scale (organizer up-arrow header; `Average` = equal-weight mean to
1.4e-14; T-009 reconciliation for five; positive cross-dimension rank
correlation for all six). **Macro score = C1 `Average`**; dimension-level results
are kept. MATH Lvl 5 enters only as its C1 summary; no C8 record is read.

### Bridge and IF4 (`q4-bridge.md`)

- Anchors: C5 (43) is contained in C6 (75) with identical values; all 75 link by
  **exact** model path, one to one. Six anchors have duplicate C1 evaluations;
  none is primary.
- Strata from organizer metadata, fixed before fitting: **S1** same family and
  validation set (7 Pythia, label High); **S2** cross-family literature (36,
  label Medium; training, validation and "final" losses mixed); **S3** expanded C6
  variants (32; 29 carry another model's loss value).
- The 7 S1 losses equal the published Chinchilla law at their own (N, D) to
  1.61e-4 - the B1 fingerprint - so S1 is on the IF3 loss scale, and its
  scores (5.07-6.06) sit at the benchmark floor.
- Forms declared first (constant; linear; logit-linear, all non-increasing);
  leave-one-anchor-out RMSE 0.424 / 0.553 / 0.536; the one-SE rule picks
  **constant**.
- **IF4 released**: primary S1, `score = c`, c = 5.66, valid only for loss
  2.0933-2.5978, LOAO RMSE 0.424 = `predictive_sd`, n = 7; path
  `data_local/problem-f/interfaces/q4-if4-loss-benchmark-bridge.json`, SHA-256
  `f4aad9dee5b0bb2b7d219232d1407911ea95407e039a6405cec7087444735d1b`; `.validate()` PASS.
- What it means: **no loss-to-score slope is identified on the IF3 loss scale**.
  S2 orders scores within a family (Spearman -1.000 to -0.232) but not across
  families (leave-one-organisation-out RMSE 10.31 linear vs 9.64 constant), so it
  is never pooled.
- **No bridge-based frontier forecast is admissible**, and none is emitted. Of
  55 compute rows with inferred D, the 33 that score off the floor are all
  outside the IF3 box, and 29 have (extrapolated) IF3 losses below the IF4
  support. Inside the support, the two non-anchor in-box rows (phi-1, phi-1.5)
  get 5.66 +/- 0.42 against observed 5.57 and 7.17; with a constant bridge the
  IF4 error is the whole band.
- **Disposition (v3).** IF4 is a **degenerate, no-slope bridge over a narrow
  primary support**. It records the benchmark floor and its out-of-fold
  prediction error, and identifies no transferable loss-to-score slope.
  Cross-family losses are not pooled. It is **not a conversion law usable for
  frontier forecasting**, and validating against the shared schema adds no
  scientific weight. The emitted object is byte-identical to the pre-v3 release
  (`f4aad9de...`); its notes already restrict use to the support.

### Decomposition (`q4-decomposition.md`)

Residual time components are **non-scale-associated historical trends**
(conditional time associations): they contain everything that moved with
calendar time at fixed parameter count, including training-data and compute
growth. No causal claim is made.

- **Mean, exact OLS split** (`g_time = g + b s`, checked to 1e-8), per year: BC
  total 5.32 [3.50, 7.18] = scale-associated 0.58 [-1.77, 2.08] + non-scale
  4.74 [2.48, 8.06] (scale share 10.9% [-35, 44]); A total 1.36 [-0.28, 3.36] =
  -1.03 + 2.39, share not reported because the total's interval includes zero.
- **Frontier**, classified for manuscript use as v3 requires:
  - the **direct frontier time trend** is the primary descriptive forecast
    trend;
  - the **frontier-set scale / non-scale split** is a post-failure,
    model-conditional decomposition, never predeclared;
  - the **additive quantile split** is a rejected diagnostic, retained as a
    negative result.

  The predeclared additive quantile decomposition **fails its own consistency
  check** (decomposed total -1.85 vs direct 9.91 for BC; -0.88 vs 5.60 for A).
  The matched-scale diagnostic shows why: BC frontier trends are 0.35 / 5.42 /
  8.60 / 24.92 pts/yr in the 0-3B / 3-10B / 10-35B / >=35B bands.

  Only after that failure was the exact OLS identity applied to the frontier
  set (models at or above their month's P90): BC 116 models, parameter-scale-
  associated -0.59 [-6.12, 1.92], non-scale 11.38 [8.92, 17.45] pts/yr. The
  frontier moved to *smaller* models while rising. A's frontier set (10) is
  below the size rule. The historical continuation does not depend on this
  split.
- **Compute-aware subset**: 94 linked, 62 with compute, 61 in the primary
  population; strata A 54, B 1, C 6, E 1; 1.4% of the panel, not representative.
  D is inferred as C/(6N) only for operation-counted compute (55 rows). Stratum
  A (n = 54): score trend 6.54 [4.58, 8.94] pts/yr = **compute-associated 4.30
  [1.75, 6.78]** + non-compute 2.24 [0.12, 4.51]; **compute share 65.7% [34, 98]**.
- **Classic IF3 decomposition**: only 6 inside-box rows (< 10), all at the
  floor, so the primary IF3 decomposition is **not supported**; the 55-row
  version (49 outside the box) is shown only as extrapolation sensitivity.
  Carried caveat: the B1 fit supports estimator / generator recovery, not
  precise real-world scaling; external support is B4 with Pythia excluded and
  B5.

The parameter-scale and compute-scale views disagree, and both are reported.
**Parameter-count growth is not training-compute growth.** By parameter count,
scale explains little of the recent change (BC mean 0.58 of 5.32 pts/yr;
frontier-set -0.59): the frontier moved to smaller models. By training compute,
which also grows with training tokens, scale explains most of the change for
the 54-row pretrained C4 subset (65.7%). No representative compute exists for
the chat / fine-tuned frontier, so the compute share reaches the forecast only
as the assumption-based transferred sensitivity.

### Frontier and forecast (`q4-frontier-forecast.md`)

Frontier = conditional 90th percentile of the macro score (quantile
regression on time); monthly P90 with counts is the descriptive frontier.
Anchor 2025-03-13; **12-month horizon 2026-03-13; 24-month stress 2027-03-13**.

Three kinds of forecast number, never interchangeable (v3):

**BC (chat / fine-tuned)**: frontier 40.99 [39.57, 41.89] at the anchor; direct
frontier trend 9.91 [8.24, 12.53] pts/yr (the primary descriptive forecast
trend).

1. **Historical / direct-score continuation baseline** - the direct trend
   continued from the anchor. This is *not* an empirically identified answer to
   a compute slowdown.
   - **12-month: 50.89**; bootstrap 90% [47.93, 54.23]; predictive 90%
     [45.72, 56.07]; predictive incl. backtest error [40.27, 61.52].
   - **24-month stress extrapolation: 60.80**; predictive [54.02, 67.57]; incl.
     backtest error [49.31, 72.28].
   - **Date clock, directly beside this headline**: 12-month point **50.89**
     (canonical mixed clock), **50.37** (publication-date-only), **65.31**
     (submission-date-only). The date-clock spread (14.94 points) is wider than
     the model-only 90% predictive band (width 10.34), and the
     submission-date-only point lies outside that band. **Date-clock sensitivity
     is materially larger than the model-only forecast uncertainty.**
     Publication date and fallback submission date stay distinct quantities; no
     clock is chosen for its result.
2. **Parameter-scale-growth scenarios** (log-N rate x0.5 and x0). These are
   *not* compute-growth scenarios, because parameter count is not training
   compute. They are **non-binding** for BC: the frontier's
   parameter-scale-associated component is -0.55 pts/yr (not positive), so
   slowing parameter-scale growth removes nothing, and both points equal 50.89
   (12 months) and 60.80 (24 months).
3. **Assumption-based transferred compute-slowdown sensitivity** - the problem's
   compute-slowdown request. Because representative historical compute is
   unavailable for the BC frontier, it transfers the compute-associated share
   estimated on the small pretrained C4 subset (94 linked, 62 with training
   compute, 54 in the stratum-A analysis). The transferred share is 65.7%
   (interval 33.7% to 97.7%, retained). It is a **scenario sensitivity, not an
   identified population effect**:

   | Horizon | Half compute growth | Zero compute growth |
   | --- | --- | --- |
   | 12 months | **47.64** [46.06, 49.23] | **44.39** [41.22, 47.56] |
   | 24-month stress | **54.29** [51.12, 57.46] | **47.78** [41.44, 54.13] |

   Ranges are over the transferred-share interval.

**A (pretrained)**: three non-sparse months and no feasible backtest, so it is
reported only as an **unvalidated extrapolation**. The 12-month continuation is
34.30 (predictive [14.50, 54.09]); the date clock gives 34.30 / 43.17 / 7.90;
the transferred compute sensitivity gives 32.46 (half) and 30.62 (zero).

**Uncertainty components** (BC, SD in points, continuation row):

| Horizon | Frontier level | Trend increment | Joint bootstrap | Monthly scatter | Total predictive |
| --- | ---: | ---: | ---: | ---: | ---: |
| 12 months | 0.81 | 1.39 | 1.97 | 2.45 | 3.14 |
| 24 months | 0.81 | 2.77 | 3.31 | 2.45 | 4.12 |

Classic IF3 and IF4 do not enter because no bridge-based forecast is
admissible; no band is conditioned on a bridge. The forecast table shows the
components for every row, so the pre-v3 figures quoted for the parameter-scale
half-rate row (1.42 / 2.00 / 3.16; bands [47.71, 54.07], [45.70, 56.09],
[40.26, 61.53]) remain visible there, unchanged (see Deviations).
- **Rolling origin**: the longest defensible horizon is **6 months** (4
  origins); no 12-month backtest is claimed. Time-only MAE 5.49, bias -5.49;
  persistence 8.89; additive quantile 6.51. Every backtest under-predicted the
  frontier, so the band with backtest error is the honest one.

### Robustness (`q4-forecast-robustness.md`)

The headline is most sensitive to the **date clock** (50.37 / 50.89 / 65.31,
above; the submission-date-only trend is 22.26 pts/yr inside the nine-month
window). Other 12-month continuation points: admitting merges gives 52.19;
relaxing open weights 47.82; strata B and C alone 55.07 and 50.17. The
robustness table's 12-month column is now labelled as the historical
continuation. Its values are unchanged, because every split in that table is
non-binding or not identified.

### Detailed-task analysis

Omitted, deliberately. T-009's accepted BBH/MUSR per-task analysis covers the
per-task requirement; the dimension-level table shows what the macro hides.
No C8 record is read.

## Validation

- `scripts/q4_evolution_selftest.py`: **PASS, 60 assertions**, covering all 22
  required guards, each with a real-data assertion and, where practical, a
  mutation that must raise its specific exception. Examples: a flipped IF3 byte,
  a billions-unit box, a Q interval or gamma in IF3, reading B8 / IF2 / C8, a
  duplicated panel row, a submission date relabelled primary, a C3 row as a
  population row, a one-character anchor typo, an empty IF4 error, the machine
  date as anchor, a zero bridge SD, and an outside-box row in the IF3
  decomposition. Two scans (fuzzy matcher, causal language) are shown to fire
  on a planted example.
- Checks failed for real during development and were fixed, not weakened:
  - the trailing-whitespace guard caught a generated line;
  - the typo mutation exposed a crash in `match_anchors` on an unmatched anchor
    (pandas stores `None` as NaN);
  - the fuzzy-matcher scan first matched the word "fuzzy" in docstrings and was
    narrowed to imports and calls, with a planted positive;
  - the causal-language scan flagged a negated disclaimer in a table, which was
    reworded.
- `scripts/q4_evolution_reproduce.py`: **PASS**. Two complete passes are
  byte-identical and LF-only; the 1,973 C files are unchanged in content, size
  and mtime; the IF3 bytes are unchanged; the 9 T-009 tables equal their blobs;
  runtime is Python 3.11.16 / NumPy 2.4.6 / SciPy 1.17.1 / pandas 3.0.6 /
  PyYAML 6.0.3, equal to `environment.yml`. Its T-009 and runtime checks were
  shown to fail on a perturbed table and a drifted version (file restored).
- `scripts/q4_panel_selftest.py` PASS (28); `scripts/selftest_interfaces.py` PASS (21).
- `git diff --check` clean; public-safety `PreCommit` PASS before each commit and `PrePush` PASS (39 commits, 6 addresses, all approved) before push.

**After the v3 correction** (final code, project environment):

- `scripts/q4_evolution_selftest.py`: **PASS, 78 assertions**. It adds the eight v3 guards,
  each with a planted violation that must be detected:
  1. parameter-scale labels are never compute-growth labels (a `compute-growth
     scenario` or bare `slowdown_half` label is refused), and the retired
     wording is gone;
  2. every compute-slowdown row and section is marked assumption-based /
     transferred (an "empirically identified BC compute share" claim is
     refused);
  3. BC's 12-month continuation row carries the recomputed direct-score point
     50.89;
  4. no bridge-based forecast row exists, and IF3 / IF4 are unused in every
     band;
  5. the C3 contract item is present;
  6. the C8 item names T-009 BBH / MUSR (removing MUSR is detected);
  7. the C8 item keeps the MATH prohibition (removing it is detected);
  8. the date-clock section directly follows the BC headline and carries
     50.89 / 50.37 / 65.31, which also appear in this package's forecast
     section.

  A **numeric-preservation guard** requires every table-row number of the five
  reviewed `7309fa6` tables to survive in the regenerated tables, and detects a
  planted 50.89 -> 50.90 change.
- `scripts/q4_evolution_reproduce.py`: **PASS** - two complete passes byte-identical and LF-only; the 1,973 C files, the IF3 bytes and the 9 T-009 tables unchanged; runtime equal to `environment.yml`. Only the four relabelled tables' hashes changed; `q4-evolution-population.md` and the IF4 bytes are unchanged.
- `scripts/q4_panel_selftest.py` PASS (28); `scripts/selftest_interfaces.py` PASS (21).
- `git diff --check` clean; public-safety `PreCommit` PASS before each v3 commit and `PrePush` PASS before the push.

## Interfaces and downstream impact

Consumes the classic IF3 (read-only, hash-checked) and the T-009 panel (rebuilt
through T-009 code). Produces IF4 (local-only, above). No shared schema
changed.

### T-012 may consume

Observed or model-conditional, as labelled:

1. Population definition, counts and exclusions; the canonical time convention
   with date sources; the anchor 2025-03-13 (observed / descriptive).
2. Macro score = C1 `Average`, all six dimensions verified higher-is-better
   (observed).
3. IF4 as a **degenerate, no-slope bridge**: on the classic-IF3 loss scale,
   within loss 2.0933-2.5978, the macro score is at floor, 5.66 +/- 0.42
   (LOAO). **No transferable loss-to-score slope is identified**, cross-family
   literature losses do not transfer, and IF4 is not a frontier conversion law
   (model-conditional, bridge-conditional).
4. Mean decomposition shares and components with their intervals, as
   **non-scale-associated historical trends** (observed association,
   non-causal).
5. The frontier moved to smaller models while rising (BC post-failure
   frontier-set parameter-scale component <= 0) (descriptive,
   model-conditional).
6. Compute-aware subset: compute share 65.7% [34, 98], **for this 54-row,
   non-representative, base-model subset only**.
7. BC **50.89** (12 months) as the **historical / direct-score continuation
   baseline**, with its bands, the adjacent date-clock sensitivity (50.37 /
   50.89 / 65.31) and the 6-month backtest bias. It is a forecast with explicit
   uncertainty and assumptions, not a compute-slowdown forecast.
8. BC **60.80** (24 months) only as a **stress extrapolation** of the same
   continuation.
9. BC compute-slowdown answer **only** as the **assumption-based transferred
   compute-slowdown sensitivity**: 47.64 / 44.39 (12 months, half / zero compute
   growth) and 54.29 / 47.78 (24-month stress), with the transferred-share
   range.

### T-012 must preserve: mandatory Q4 source coverage

The final Q4 manuscript must make each of the following visible; omitting any
of them silently drops mandatory Problem-F Q4 evidence.

- **C3** (auxiliary timeseries): used and audited as an auxiliary source, never
  as canonical frontier observations. Its `Year` is the leaderboard submission
  year; its repeated models carry distinct score vectors (duplicate keys, 79
  rows, no unique evaluation key); and its 26 historical rows are not on the
  leaderboard v2 score scale (23 have `Average` != mean of dimensions,
  unmeasured dimensions zero-filled). Those limitations are why no C3 record
  becomes a frontier observation. The manuscript must state this use.
- **C4** (Epoch AI metadata): provides training-compute metadata, data-scale
  (dataset-size) metadata where available, open-model / open-weight information
  (part of the T-009 open-weights signal), and deterministic-linkage evidence.
  Its coverage limitation must be kept: **94** panel models linked, **62** with
  training compute, concentrated in pretrained base models and not
  representative of the panel. The manuscript must carry these counts with any
  C4-based claim.
- **C8** (per-task records): the mandatory task-level Q4 requirement is met by
  the accepted **T-009** detailed-task aggregation (`q4-detailed-task-analysis.md`,
  the reconciled **BBH** and **MUSR** subtask matrices). T-011 deliberately does
  not duplicate it. The final Q4 manuscript must integrate that accepted T-009
  BBH / MUSR evidence explicitly. Quarantined C8 **MATH** Lvl 5 child records
  remain prohibited (only the C1 MATH summary score is usable), and accepted
  T-009 artifacts are not modified.

### T-012 must not

- use any bridge-based forecast (none exists);
- evaluate IF4 outside its support, or read its constant as a slope or as a
  conversion law;
- present 50.89 / 60.80 as a compute-slowdown forecast, or the parameter-scale
  scenarios as compute-growth scenarios;
- present the transferred compute sensitivity as an identified, observed or
  causal compute effect;
- present A's forecast as validated;
- call any residual time trend algorithmic, technical or causal progress;
- present the compute share as panel-wide;
- present the frontier-set split as predeclared, or use the rejected additive
  quantile split;
- treat B1 fit intervals as real-world precision.

## Deviations from plan

- **Frontier decomposition.** The predeclared additive quantile decomposition
  failed its own consistency check. The parameter-scale scenarios' split
  therefore uses the exact OLS identity on the frontier set. It was adopted
  after that failure, is not predeclared, and is classified as a post-failure
  model-conditional decomposition; the failed decomposition is kept and
  reported, and its rolling-origin error is shown. The frontier-set size rule
  (30), the non-binding treatment of a non-positive scale component, and the
  compute-aware slowdown sensitivity were added at that point too. None was
  chosen by forecast performance.
- **v3 interpretation correction (executed).**
  - The pre-v3 artifacts, `config.py` and this package called the halved
    parameter-scale rate the problem's compute-slowdown scenario. That was
    wrong: parameter count is not training compute.
  - Scenario keys and prose are relabelled (`param_scale_historical` /
    `param_scale_half` / `param_scale_frozen`). The historical continuation is
    now the headline, and the transferred compute sensitivity is the only
    compute-slowdown answer. The numerical implementation is unchanged.
  - The pre-v3 package quoted the half-rate row's bands and SDs for the
    headline. v3 reclassifies the headline as the continuation, whose own row
    (the x1 row, identical to the time-only continuation) was already in the
    reviewed table: bootstrap [47.93, 54.23], predictive [45.72, 56.07], incl.
    backtest [40.27, 61.52], SD 3.14. Both rows are unchanged; only the row
    quoted changed.
  - The forecast table now lists uncertainty components for every row rather
    than for one scenario.
  - The one numeric token no longer in any table is the multiplier `1` in the
    retired definition sentence ("historical_rate = 1, ... primary
    `slowdown_half`"), removed as v3 requires; no estimate changed.
- **Date-consistency rule (R7).** Not named in v1; a provenance rule on T-009
  fields that removes 5 rows, disclosed with the full list.
- **Figures.** Not produced (no plotting library in the pinned environment;
  `environment.yml` is outside T-011's paths). If M1 wants figures, the
  dependency is an `environment.yml` decision.
- **Worklog handoff.** Per v2, M3 made no change, so no outgoing entry exists;
  `worklog/M4.md` was initialised with the repository schema.
- **Operational.** The checkout's author email was not approved by
  `configs/git-email-policy.txt`; it was set to the owner's GitHub noreply
  address before the first commit. The host's HTTPS credential was rejected,
  so the branch was pushed over SSH to the same repository (the `origin`
  configuration is unchanged). No API credential was available, so the owner
  opened Draft PR #15 in the GitHub web interface.

## Negative results

- No loss-to-score slope is identifiable on the IF3 loss scale: the only
  comparable anchors are at the benchmark floor.
- Cross-family literature losses do not transfer across families.
- The classic-IF3 decomposition is not supported (6 inside-box rows).
- The additive quantile frontier decomposition fails its consistency check.
- A has no validatable frontier forecast.
- C3's `Year` is the submission year, and its 26 historical rows are not on the
  v2 scale (23 have `Average` != mean of dimensions).

## Known limitations and open risks

- Nine months of dense history, on a mixed clock whose fallback is an
  evaluation date. The date-clock sensitivity (12-month 50.4-65.3) is larger
  than the model band.
- The monthly P90 depends on the submission mix: a flood of 14B fine-tunes can
  move it without the best model moving. The monthly maximum rose less.
- The frontier trend is linear by assumption; the backtest shows it
  under-predicts at 6 months.
- The compute-aware slowdown transfers a subset share to the frontier: an
  assumption, not a finding.
- IF4's loss axis is formula-evaluated (B1 fingerprint), not measured loss.
- IF3 "raw parameter count" (B1 convention) and the leaderboard / C4 parameter
  counts differ for small models (e.g. Pythia-160M 1.62e8 vs 2.13e8).
- C2 publication dates for derivatives are family dates (organizer fuzzy
  match); T-009's date rule was used as accepted and not changed. Reported for
  M1 as a T-009-level observation.

## Next action

M1 final supervisory review of Draft PR #15 after the v3 correction. M4 does
not merge, does not mark T-011 done and does not start T-012.
