# T-007 handover

| Field | Value |
| --- | --- |
| Task | T-007 |
| Owner | M2 |
| Status | wip; existing infrastructure checkpoint; real IF1/IF2 BLOCKED |
| Timestamp | 2026-09-24T16:22:00+08:00 |
| Base | 87fbce3a612b7245ad28a965fb262ff839446718 |
| HEAD | Initial WIP checkpoint commit containing this package; parent 87fbce3 |
| Branch / PR | exp/m2-T007-q1-modeling; no PR yet |

## Current continuation and checkpoint verification

The new M1 continuation supersedes the earlier missingness decision request:
the primary analysis must exclude only the confirmed raw-NaN records;
0, 0.5 and 1 are sensitivity scenarios with explicit missingness flags.
This policy is authorized but not yet implemented in this checkpoint.
The historical configuration proposal below is not an operational config;
its `reject` policy and old missingness alternatives are superseded.
`configs/q1.yaml` is absent. The canonical specification explicitly protects
`configs/`. M1 explicitly instructed this continuation to keep `configs/`
protected and stop after securing WIP. No configuration file or shared path
has been changed. Real-data fitting, sensitivity and IF1/IF2 release remain
blocked; this checkpoint is infrastructure evidence only.

The active continuation was verified from session metadata as GPT-6-Astra,
extra-high reasoning (`gpt-6-astra`, `xhigh`) at
2026-09-24T16:18:48.799+08:00. Earlier preflight turns reported `high` and
stopped without scientific execution. No model substitution was made.
As reported in M1's continuation instruction, the earlier formal execution
began with Fable 5.1 API and continued with Sonnet 5 after quota exhaustion.
That differs from M1's requested model/effort and is an execution and
reproducibility deviation; it does not by itself invalidate scientific output.

All A1-A16 logical IDs resolve to nonempty canonical files. The official DOCX
passes ZIP/XML integrity checks. The complete raw audit reproduced its
existing report byte-for-byte, exited 2 for the known 19-record literal-NaN
defect, and verified identical before/after hashes of all 16 inputs and DOCX.
Raw-input audit: **KNOWN INPUT DEFECT**. Infrastructure validation: **PASS**;
this is not real scientific validation or interface release.

Validation in this continuation: 9 Q1 tests, 21 infrastructure tests and 21
shared-interface assertions pass. `git diff --check` passes. PreCommit passes
on 77 candidate files. The plain PowerShell invocation is blocked by local
execution policy; process-scoped `-NoProfile -ExecutionPolicy Bypass` executes
the unchanged checker successfully.

`python --version`: 3.13.9. `where.exe python` resolves the Anaconda base
interpreter first and an MSYS2 UCRT64 interpreter second. `pip --version`:
26.2.1 for the base Python 3.13. The default interpreter's Q1 self-test exits 1
without test output. No registered Conda environment uses Python 3.11 and the
canonical project environment is absent. Scientific checks above use the
existing Conda environment `label-studio`: Python 3.13.9, NumPy 2.4.2,
SciPy 1.17.0, PyYAML 6.0.3, pandas 3.0.0, pip 25.3. No dependency was installed;
this checkpoint does not certify the declared Python 3.11 environment.
Exact interpreter selection without a machine-specific path:
`conda run -n label-studio python scripts/q1_selftest.py` (the checks here
invoked that environment's interpreter directly).

The existing repository-local Git author and committer addresses were checked
and both use the approved noreply suffix. Local agent directories and raw
inputs remain unstaged. `TASKS.md` and canonical specifications are unchanged.

## Scope

Continue the four inherited untracked modules under `src/mixture/` and
`src/quality/pipeline.py`. Preserve the validated 22-indicator scalarization.
The target remains the IF1/IF2 checkpoint specified in `worklog/specs/T-007.md`.
This is a WIP audit, not a request to accept either interface.

## Completed work

- Verified checkout, remote, task ownership, branch and base commit.
- Inspected every inherited module and the tracked scalarization contract.
- Reproduced two defects before repair: a constant vector received Spearman
  correlation approximately 1; a mixture with no mapped mass received Q=0.
- Re-read the official DOCX without modifying it. A1-A16 are identifiers for
  actual files, not subdirectory names. The contaminated PDF was not used.
- Ran the existing scalarization entry point on all 51,230 A1 records; all
  eight list widths passed and the canonical representation retained 22 fields.
- Read every A2/A3 record through the existing scalarizer: arxiv 17,523;
  github 203,752. Both extensions lack `_source_domain`, so their domain must
  come from the explicit file-to-domain assignment.
- Added a complete input audit that hashes all A1-A16 inputs and the official
  DOCX before and after reading, reports mixture structure and mapping
  coverage, and returns failure when quality signals are non-finite.
- Repaired tied ranks, undefined correlations, undefined zero-coverage Q,
  finite-value guards, separation of negative/positive correlations and
  consistent row normalization without changing stored mixtures. Added
  explicit relative-absolute-error reporting and strict CSV schema checks.
- Removed default seed, tuning-grid, fold-count, bootstrap-count and conflict
  threshold literals from the inherited callable APIs. Callers must supply
  approved configuration settings; no new model was fitted on real data.

Code: `src/quality/pipeline.py`, `src/mixture/data.py`,
`src/mixture/mapping.py`, `src/mixture/model.py`, `scripts/q1_selftest.py`,
`scripts/q1_audit_inputs.py`.
Regenerable artifact: `results/tables/q1-input-audit.md`.
The inherited four modules remain untracked, with targeted repairs in place;
their structure and reusable implementation have been preserved.

### Continuation after the first takeover checkpoint

- Rechecked actual Git state; HEAD is still `87fbce3`. Reproduced the previous
  input audit byte-for-byte before extending it. No staged files or interface
  outputs existed; the proposed shared configuration was still absent.
- Located every defective record by input, decompressed line number and line
  SHA-256, without publishing record IDs or content. Classified defects before
  reduction and separately checked transform-created non-finite values.
- Quality preprocessing now requires explicit directions and non-monotone
  intervals. Family aggregation requires an explicit partition of all 22
  indicators. The inherited provisional directions remain labelled as such
  and are no longer silent defaults. Expected-rating and argmax paths both
  reject invalid raw logits before reduction.
- Added domain bootstrap summaries, tied domain ranks, all 231 descriptive
  indicator associations, conflict-threshold effects on aggregation, and a
  union-record bootstrap preserving A1/extension overlap. These routines were
  validated with synthetic inputs; no final organizer Q was calculated.
- Extended the existing ridge implementation with one second-order pairwise
  mixture candidate. Added A4/A5-only deterministic selection, frozen-model
  fingerprints, train-design overlap rejection, per-target/macro metrics,
  separate centered shape diagnostics, paired A6/A8 scale analysis, and
  explicitly non-validation reference comparisons. Tests confirm that changing
  held-out targets cannot alter the frozen model and coefficient mutation is
  detected. CV remains a selection statistic, not an unbiased nested estimate.
- Added IF1/IF2 builders using the unchanged shared classes and their actual
  `.validate()` methods, plus strict deterministic JSON encoding. Synthetic
  objects were validated in memory only. No canonical interface file was written.
- Added configured analysis entry points and deterministic report renderers.
  Both entry points fail before fitting when `configs/q1.yaml` is absent.
  The quality entry point also rejects any unimplemented missing-signal policy.

Additional code:

- Quality: `src/quality/diagnostics.py`, `analysis.py`, `configuration.py`,
  `handoff.py`; entry point `scripts/q1_quality.py`.
- Mixture: `src/mixture/validation.py`, `handoff.py`; entry point
  `scripts/q1_mixture.py`.
- Synthetic checks: `scripts/q1_selftest_infrastructure.py`.

The mixture entry point intentionally ends at frozen composition validation.
Choosing/fitting the 10B/70B extrapolator depends on that real validation result
and has not been preselected with synthetic data. The quality entry point emits
analysis evidence only; release of IF1 still requires the scientific assessment.

## Evidence and validation

Commands already run (using an installed Python with NumPy/SciPy):

```
python scripts/q1_scalarize.py
python scripts/q1_audit_inputs.py
python scripts/q1_selftest.py
python scripts/q1_selftest_infrastructure.py
python scripts/selftest_interfaces.py
python scripts/q1_quality.py
python scripts/q1_mixture.py
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PreCommit
```

Scalarization passed and regenerated its existing table with no semantic diff.
The complete input audit returned nonzero at the quality finiteness gate and
wrote the negative result. Nine existing Q1 tests, 21 new infrastructure tests,
and all 21 shared-interface mutation assertions passed. The two analysis entry
points were invoked by the synthetic test runner as subprocesses: both returned
2 with an explicit missing-configuration message, before fitting or writing
analysis outputs. `git diff --check` passed.
The mixture entry point also ran end-to-end against synthetic loaders, writing
only inside a temporary fixture directory and regenerating identical report
bytes. The quality entry point was tested with an injected raw defect and wrote
no report. These fixture settings are explicitly labelled in the tests; no
temporary configuration file was created under `configs/`.
Public-safety passed on 77 candidate files. Untracked-whitespace and ownership
checks passed; there are no staged changes and no shared path was changed.
The plain PowerShell invocation was prevented by local execution
policy; the process-scoped invocation above ran the unchanged checker.
The default Python failed while importing NumPy; an existing alternative
environment supplies working numerical libraries. No dependency was installed.
Validation runtime: Python 3.13.9 with NumPy 2.4.2, SciPy 1.17.0 and PyYAML 6.0.3.
The repository-declared Python 3.11 environment was not available under its
canonical environment name; this run does not certify that exact environment.
The full audit was regenerated and a subprocess check asserted both its
expected exit status 2 and byte-identical output. Report SHA-256:
`f7fe64558fa4381068d29db30814975044f63475c1cc8fc061f80febc7fe11e6`.
This is the expanded audit; the prior report was verified before extension.

## Input findings and stop condition

The canonical files contain non-finite model logits:

| Input | Affected records | Fields | Domains |
| --- | ---: | --- | --- |
| A1 | 18 | professionalism 5; reasoning 13 | commoncrawl 4; wikipedia 14 |
| A2 | 0 | none | none |
| A3 | 1 | professionalism 1 | github 1 |

The inherited quality preprocessor could convert a missing score into an
apparently valid rank through `searchsorted`; the repaired preprocessor rejects
the real A1 input before fitting. No row was removed, no signal was imputed,
and no raw input was modified. The existing scalarizer's successful execution
checks widths, not finiteness. This is a new blocker, not evidence that all
three complete populations are ready for aggregation.

The continuation resolved the proximate cause: **literal NaN tokens are already
stored in the raw JSONL**. A1 contains 108 such tokens and A3 contains 6; every
affected vector contains six NaNs. A2 has none. There are no observed positive
or negative infinities, missing fields, null values, nonnumeric components,
wrong list widths, or additional non-finite values created from finite raw
inputs by scalarization. The exact 19 record locators and byte fingerprints are
in `results/tables/q1-input-audit.md`.

This establishes upstream unavailability of entire classifier outputs, not its
ultimate cause. The local evidence cannot distinguish upstream inference failure,
serialization failure or another earlier process. It does not establish missing
at random. `argmax` alone would return a valid-looking zero for all-NaN logits;
the failure-first test reproduces that trap and verifies the preprocessor rejects it.

A2 contains all 1,419 A1 arxiv source/record identities; A3 contains all 10,000
A1 github identities. Signals agree on all overlaps. Independent-sample
uncertainty calculations for those comparisons would ignore this overlap.

A4/A5 contain 512 paired rows; A6/A7 and A8/A9 each 256; A10/A11 64;
A12/A13 and A14/A15 each 63. A6=A8 exactly. Both extrapolation designs are
exact indexed subsets of A4. There is no exact A4/A6 or A4/A10 design overlap.
All 13 target columns are finite; none was used for selection or fitting.

A16 has six usable mappings. Across unit-mass A4 designs, the mean mapped mass
is 0.564636, with range 0 through 1 and median 0.600401. This cannot support a
whole-corpus quality claim. Full counts, zero prevalence, normalization
diagnostics and input fingerprints are in the generated audit.

## Negative results and inherited defects

- The inherited A4 loader fails at its hard-coded 0.002 row-sum tolerance.
  Actual A4 sums are 0.996 through 1.003. Mixture values are stored on a 0.001
  grid; a rounding-derived bound is 17 * 0.001 / 2 = 0.0085, conditional on
  nearest rounding. A revised tolerance must be explicit and retain the
  original residuals; increasing it just to suppress the failure is not valid.
- Rank helpers assigned different ranks to ties based on record order.
- Mapping returned a finite Q for zero mapped mass.
- Non-finite raw indicators could be hidden by ECDF search and clipping.
- The conflict report could call a negative association redundant because it
  sorted by absolute correlation.
- The three provisional directional overrides are not established findings.
  In particular, monotonically increasing mean word length conflicts with
  published interval-based natural-language filtering practice.
- Hyperparameter grid, fold count, bootstrap count and threshold choices are
  hard-coded in the inherited modules rather than supplied by `configs/` at
  takeover; their defaults have now been removed pending approved settings.

## Interfaces and downstream impact

No IF1 or IF2 has been emitted by this takeover. No scientific Q definition or
held-out model result is certified. Consumers must not infer completion from
the presence of reusable module code. Original A16 rows with `(none)` retain
their `inferred` mapping type and have no usable quality mapping.
Intended filenames, once real results justify export, are
`data_local/problem-f/interfaces/q1-if1-domain-quality.json` and
`data_local/problem-f/interfaces/q1-if2-mixture-response.json`.
Their actual SHA-256 values are unavailable because those files do not exist.
Synthetic JSON determinism does not certify actual interface regeneration.
IF2 stores the intercept as `__intercept__` and optional pairwise coefficients
as `interaction:left*right`, with the encoding and reference interpretation in
its validation metadata; the shared schema itself was not changed.

## Proposed configuration change requiring M1 authorization

`AGENTS.md` section 5 requires result-affecting constants in `configs/`.
`worklog/specs/T-007.md` sections 3 and 27 prohibit modifying `configs/`
without explicit M1 approval. The existing shared file supplies the seed but
no Q1 analysis settings. Proposed new file: `configs/q1.yaml`, leaving
`configs/default.yaml` and its seed unchanged. This block is a proposal,
not an operational substitute for an approved configuration file. The proposal
below now makes directions and family membership explicit to match the tested
APIs; none of these additions or the earlier settings is authorized yet.

```yaml
quality:
  bootstrap_replicates: 1000
  confidence: 0.95
  conflict_thresholds: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
  material_rank_correlation: 0.3
  direction_overrides:
    rps_doc_unigram_entropy: higher_better
    rps_lines_numerical_chars_fraction: lower_better
  desirability_intervals:
    rps_doc_mean_word_length: [3.0, 10.0]
  missing_signal_policy: reject
  aggregators: [equal_indicator, family_balanced, robust_median]
  primary_aggregator: family_balanced
  families:
    dsir: [dsir_books, dsir_wiki, dsir_math]
    rps:
      - rps_doc_word_count
      - rps_doc_num_sentences
      - rps_doc_unigram_entropy
      - rps_doc_frac_unique_words
      - rps_doc_frac_no_alph_words
      - rps_doc_frac_chars_top_2gram
      - rps_doc_frac_chars_top_3gram
      - rps_lines_uppercase_letter_fraction
      - rps_lines_ending_with_terminal_punctution_mark
      - rps_lines_numerical_chars_fraction
      - rps_doc_mean_word_length
    fineweb: [fineweb_edu]
    wanjuan: [fluency_en, ad_en]
    qurating: [qurater]
    modernbert:
      - modernbert_cleanliness
      - modernbert_readability
      - modernbert_reasoning
      - modernbert_professionalism
mixture:
  stored_decimal_places: 3
  row_sum_tolerance: 0.0085
  cv_folds: 5
  ridge_alphas: [0.00000001, 0.000001, 0.0001, 0.01, 0.1, 1.0, 10.0]
  candidates: [linear, pairwise_interactions]
```

The tolerance is to be checked against the observed decimal grid. Both model
candidates use raw proportions normalized by row sum, an unpenalized
intercept and a dropped reference chosen on A4. Selection uses only A4/A5;
A6-A11 remain outside tuning. No scale extrapolation settings are proposed
until the required validation freeze.
The primary aggregator entry is a proposed candidate, not an accepted final Q;
the analysis entry point compares all three without using Loss. The six-family
proposal would give the four ModernBERT fields one group vote rather than four
separate upstream-model votes. Numeric-character direction remains an explicit
natural-language heuristic whose effect on code/math domains needs sensitivity.
All other raw directions inherit the existing tracked scalarization contract.

Mean-word-length evidence: Gopher, Appendix A.1, describes a desirable range
of 3-10 characters for web-text filtering. Transferring that heuristic to code
and scientific documents requires explicit sensitivity, not a universal
quality claim: <https://arxiv.org/pdf/2112.11446>.
RedPajama defines unigram entropy as lexical diversity but supplies no
universal interior quality optimum:
<https://github.com/togethercomputer/RedPajama-Data/blob/main/app/src/core/quality_signals/natural_language.py>.

## Known limitations and next action

The implementation now covers quality summaries/conflict/stability, model
candidates, frozen validation, and interface construction, but actual full-record
quality results, actual model comparison/validation, scale extrapolation, final
robustness findings, IF1/IF2 outputs and complete review evidence remain absent.
No synthetic result is offered as a substitute. Further entry-point sensitivity
or extrapolation wiring will follow the approved settings and observed outcomes;
those scientific choices have not been prejudged. The exact Python 3.11
environment is also not certified by this run.
No A13/A15 value has been used as observed validation or fitting data.

M1 decisions needed:

1. Authorize the concrete configuration proposal (or provide corrected
   settings) before result-affecting settings move into the protected path.
2. Choose between retaining the strict stop while authoritative replacement
   signals are sought, or authorizing a documented neutral-rank treatment:
   retain every record and all 22 canonical fields, fit each affected indicator's
   reference ECDF on finite A1 observations only, assign missing normalized
   signals 0.5 with an explicit missingness mask, and bound sensitivity by
   assigning those signals 0 and 1. Neutral rank is an assumption, not recovery
   of the missing logits or a claim of unbiasedness. It has **not** been
   implemented or executed. Row deletion conflicts with required full-record
   use; argmax-zero substitution is invalid. More complex learned imputation is
   not proposed without evidence about the missingness mechanism.

The second decision is requested under the explicit stop condition in
`worklog/specs/T-007.md` section 27 (required data structurally inconsistent),
with the official full-record requirement preserved. M1 maintains any needed
specification addendum; this run did not edit `worklog/specs/`.
The first decision follows sections 3 and 27's protected-path restriction.

Smallest actionable request: approve/revise the configuration proposal (the
mixture section may be approved separately), and select **keep rejecting** or
**neutral rank plus endpoint sensitivity** for the 19 records. Config approval
alone unlocks real A4/A5 selection and A6-A11 frozen validation. After examining
those results, M2 can decide the limited real-scale extrapolation and complete
A13/A15 reference comparisons. Missing-signal guidance plus quality settings
unlocks implementation of the selected policy, full A1/A2/A3 scoring, robustness
assessment and, only if justified, IF1 export. No new architectural or shared
interface change is requested.

No files were staged or committed; no branch was pushed and no PR was opened.
`TASKS.md` is unchanged; T-007 remains WIP and has not entered formal review.
Local agent state was not modified or used as project source.
