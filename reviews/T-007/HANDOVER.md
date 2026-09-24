# T-007 handover

| Field | Value |
| --- | --- |
| Task / owner | T-007 / M2 |
| Status | WIP; IF1 READY FOR REVIEW; IF2 BLOCKED by frozen validation |
| Timestamp | 2026-09-24T17:29:27+08:00 |
| Continuation start | 823f35f7aadcb1742d3773fbf16168ddd202ccfd |
| Earlier secured implementation | fe5d30eb6165ccfb64efc5623a747c10557bbc2e; original base 87fbce3 |
| Real-data implementation HEAD | 622e93c1c7d0efb28339502d5c548cf38858eaef; quality commit e03127a |
| Package revision | This revision describes the real-data implementation and generated evidence in its Git commit |
| Branch | exp/m2-T007-q1-modeling |
| PR | [Draft PR #12](https://github.com/Rhymer-Lcy/modeling-research-2026/pull/12), base main; unmerged |

M1 authorized only configs/q1.yaml beyond the existing T-007 paths.
That supersedes the previous configuration stop. The existing checkpoint was
preserved. Full quality analysis is complete; mixture selection and frozen
validation have run, and the failed out-of-design gate stops IF2 and fitted
10B/70B extrapolation. No gate was relaxed and no replacement model was
selected after validation. This is a reviewable stopped checkpoint, not a
claim of complete scientific closure, acceptance or merge readiness.

## A. Verified raw facts

All A1-A16 logical IDs resolve to their actual attachment files, not invented
directories. The official DOCX passes ZIP/XML integrity checks. The removed
hidden/suspicious PDF content was not used as authority. Canonical paths,
file fingerprints and exact defect locators are in
[the input audit](../../results/tables/q1-input-audit.md).

| Input | Raw records | Primary complete records | Excluded | A1 overlap |
| --- | ---: | ---: | ---: | ---: |
| A1 sampled quality | 51230 | 51212 | 18 | Reference |
| A2 arxiv extension | 17523 | 17523 | 0 | 1419 |
| A3 github extension | 203752 | 203751 | 1 | 10000 |

Each affected record has six literal raw NaNs. A1 has five affected
professionalism and thirteen reasoning vectors; A3 has one professionalism
vector. A1 affected domains are commoncrawl (4) and wikipedia (14).
No infinities, malformed widths or transform-created nonfinite values were
found. Ultimate upstream cause and the missingness mechanism remain unknown.

The audit retains its failure. Complete-case exclusion removes only these
records because a required reduced indicator remains nonfinite from literal
NaNs. The scientific loader separately records source, decompressed line,
line hash, field names, literal count, reason and raw file hash in the local
quality-analysis report. Original data were not repaired or overwritten.

A2/A3 have no native _source_domain field; file identity supplies the domain.
All overlapping records have identical signals. Each quality domain has one
observed source shard: these are same-source extensions, not independent
experiments.

| Pair | Rows | Role |
| --- | ---: | --- |
| A4/A5 | 512 | Training and deterministic training CV at 1M |
| A6/A7 | 256 | Frozen in-design validation at 1M |
| A8/A9 | 256 | Paired cross-scale validation at 60M; A8 exactly equals A6 |
| A10/A11 | 64 | Primary out-of-design validation at 1B |
| A12/A13 | 63 | Indexed A4 subset and estimated 10B reference |
| A14/A15 | 63 | Indexed A4 subset and estimated 70B reference |

All indices align within pairs; there are 17 proportions and 13 Loss targets.
A4 has no duplicate design or exact composition overlap with A6/A10.
The 0.001 storage grid permits a nearest-rounding sum bound of 0.0085;
the earlier 0.002 bound would reject valid stored rows.

## B. Modeling decisions

[configs/q1.yaml](../../configs/q1.yaml) records the authorized proposal,
candidate family, sensitivity scenarios, acceptance rules and constants.
Its SHA-256 is f59d850cddc44c32a6408561a8f95e80adae96e6213bd29a0f82ee28bebf70c3.
It was written before real fitting; no parameter was chosen from held-out
performance. Seed 42 comes from configs/default.yaml.

Exactly 22 scalar indicators remain: 14 native scalars plus eight reduced
lists of widths 1/2/2/4/6/6/6/6. The native direction map remains 15/4/3.
All final indicators are higher-is-better on a common A1-complete-case
midrank ECDF reference, frozen for A2/A3 and every missingness scenario.
There is no per-domain normalization.

The predeclared non-monotone treatments are increasing entropy as diversity,
decreasing numeric-character fraction as a prose heuristic, and desirability
decreasing with distance outside mean-word-length [3,10]. First-party semantics
and the Gopher heuristic source are linked in
[the transform contract](../../results/tables/q1-transform-contract.md).
No optimum or transform was fitted to Loss. These prose heuristics are not
universal quality laws for code or mathematical text.

Primary Q averages six equally weighted indicator-family means. Equal-field
and median aggregation, expected-rating versus argmax, numeric neutralization,
word-length direction and leave-one-family-out results remain sensitivities.
Missingness scenarios replace only the affected FINAL standardized quantity
with 0, 0.5 or 1 and retain explicit flags; they never enter primary IF1.

Confidence intervals use 1000 deterministic resamples within domain, preserving
source shards where multiple shards exist. All observed domains have one shard,
so the actual fallback is a conditional document bootstrap. Effective source
count is one per domain; raw record count is not a claim of independent
information. Intervals exclude unidentified within-shard dependence,
normalization estimation and method-choice uncertainty. Extension differences
use union-record bootstrap to preserve the A1 overlap.

Mixture proportions are nonnegative and divided by their observed positive
row sum; exact boundary zeros are retained without pseudocounts. A4 selects
pile_cc as the dropped reference by nonzero prevalence times share SD.
The inverse is p_reference = 1 - sum(other proportions). Coefficients and
one-percentage-point substitutions are relative to that reference, not
absolute domain effects or effects of quality.

Selection compares linear ridge with a second-order interaction ridge
(16 versus 152 features) using five deterministic A4/A5 folds and the
declared seven-alpha grid. Nonlinear adoption requires at least 5% normalized
CV improvement and wins in at least four folds. CV is a selection statistic,
not an unbiased nested-CV estimate. The selected fit was fingerprinted before
held-out Loss was loaded.

## C. Real-data results

[Domain Q and conditional intervals](../../results/tables/q1-quality-analysis.md):

| A1 domain | Primary Q | Conditional 95% CI | Complete n |
| --- | ---: | --- | ---: |
| arxiv | 0.659430 | [0.656639, 0.662121] | 1419 |
| stackexchange | 0.539564 | [0.537881, 0.541389] | 10000 |
| c4 | 0.516461 | [0.513692, 0.519144] | 10000 |
| commoncrawl | 0.515543 | [0.513344, 0.517728] | 9636 |
| wikipedia | 0.486263 | [0.484119, 0.488467] | 9986 |
| book | 0.468062 | [0.453257, 0.482086] | 171 |
| github | 0.420638 | [0.418986, 0.422365] | 10000 |

A1 overall linear-aggregate Q = 0.5 is implied by its midrank calibration;
it is not independent evidence that the corpus has neutral absolute quality.
Observed domain shares remain unequal.

[Conflict](../../results/tables/q1-conflict-analysis.md) includes record
dispersion, pairwise ECDF gaps and disagreement about the reference median,
along with descriptive pair correlations. Across A1, mean pair gap is
0.305416, mean record SD 0.260166 and median-direction disagreement 0.481898.
There are 31 antagonistic pairs among 231 at the declared rho <= -0.3.
Across the full unchanged 0.1-0.9 threshold grid, P(indicator range >= threshold)
declines from 1 to 0.328458; there is no selected favorable threshold.

[Extension results](../../results/tables/q1-a1-a3-comparison.md):
A2 primary delta from A1 arxiv is -0.001637, conditional paired CI
[-0.004266, 0.001235]; A3 delta from A1 github is +0.000484,
CI [-0.001133, 0.001960]. Replacing the corresponding A1 domain by its
extension leaves the domain order unchanged for all three aggregators.
Maximum conflict-curve changes are 0.003984 (A2) and 0.004153 (A3);
antagonistic-pair counts remain 26 and 31 respectively.
This supports same-source sampling stability, not external replication.

[A16 coverage](../../results/tables/q1-a16-coverage.md) retains six mapped
and eleven unmapped mixture domains. IF1 coverage is empirical mean mapped
A4 mixture mass 0.564636, not 6/17. A6/A8 coverage is 0.569010,
A10 0.622612 and A12/A14 0.543489. Five A4 designs have zero mapped mass
and undefined mapped Q. No unmapped value was invented.

[Training selection](../../results/tables/q1-mixture-selection.md) chooses
pairwise interactions: normalized CV RMSE 0.085996 versus linear 0.098261,
a 12.4815% improvement, with wins in all five folds. Reference pile_cc and
per-target selected penalties are recorded in the generated table.
The chosen design is full rank but has condition number 35370, versus
45.7 for the baseline; regularization and conditional interpretation matter.

[Frozen validation](../../results/tables/q1-mixture-validation.md) reports
13 targets separately and these macro means:

| Category | RMSE | R2 | Spearman | Mean absolute relative error |
| --- | ---: | ---: | ---: | ---: |
| A6/A7 frozen in-design 1M | 0.394429 | 0.725399 | 0.871799 | 0.071868 |
| A8/A9 paired cross-scale 60M | 1.521465 | -7.509086 | 0.874576 | 0.432211 |
| A10/A11 out-of-design 1B | 2.896422 | -620.386395 | 0.849193 | 1.454130 |

A6/A7 improves RMSE over the baseline by 13.04% and passes.
A10 preserves useful ordering but fails the predeclared shape gate:
mean centered normalized RMSE 2.207986 > 2.0; centered macro R2 is
-6.773209. No centering correction is passed off as absolute validation.
The IF2 scientific gate therefore fails independently of the raw NaN audit.

## D. Robustness and sensitivity

[Missing-record sensitivity](../../results/tables/q1-missingness-sensitivity.md)
bounds the maximum Q change across all populations/aggregators/domains by
0.000150336, CI endpoint change by 0.000255230, conflict-curve change by
0.000934128 and downstream mapped-Q change by 0.000150336.
Mapped mass changes by zero. Extension-difference changes are at most
0.000001242; all domain ranks remain unchanged. The missingness gates pass.

[Method sensitivity](../../results/tables/q1-method-sensitivity.md) is larger:
numeric neutralization reverses the close c4/commoncrawl order;
different family weighting changes middle-domain ranks. Omitting DSIR changes
arxiv Q by +0.125446 and moves book from sixth to second. Arxiv stays highest
and github lowest across the declared aggregation and family variants.
IF1 carries these ranking dependencies; its narrow sampling intervals must
not be treated as method-robust ranks.

[Paired scale analysis](../../results/tables/q1-cross-scale.md) shows
A6/A8 observed Loss-order correlations 0.980090-0.998047, but systematic
60M-minus-1M shifts from -2.439605 to -0.968860 and SD ratios 0.501013-0.979193.
Same-basis post-validation diagnostic refits have 96.15% sign agreement and
mean importance-rank correlation 0.928054 for A6/A8. A6/A10 agreement falls
to 68.27% and 0.235520; the 1B comparison confounds scale and design.
No jointly resolved sign reversals were detected, which is not proof of
scale invariance given conditional, regularized uncertainty.
The 1B diagnostic has only 64 rows for 152 features (centered rank 63);
its refitted effects are identified by the fixed ridge penalty, not by
an independently full-rank 1B design.
Detailed reference-mass substitutions are in q1-mixture-effects.md.

## E. Negative results and stopping point

- Raw audit: KNOWN INPUT DEFECT, exit 2, unchanged strict finite checks.
- Q1a scientific gates: PASS for a declared partial-coverage proxy.
- Q1b frozen scientific gate: FAIL; IF2 BLOCKED. Large-scale absolute
  calibration and 1B shape transfer fail despite high ordering correlation.
- The nonlinear training winner is not promoted to a released universal
  response. The linear baseline was not selected post hoc after seeing tests.
- Fitted 10B/70B extrapolation is BLOCKED by the failed prerequisite.
  [A13/A15 diagnostics](../../results/tables/q1-extrapolation.md) compare only
  the unscaled frozen 1M predictor as a labelled stress test: RMSE 3.605560
  and 3.989112. These are neither extrapolation predictions at the target
  scales nor independent observed validation. A12/A14 remain repeated subsets;
  A13/A15 were never fitting data.
- Single-source uncertainty, domain imbalance, method-sensitive rankings and
  missing-at-random uncertainty are unresolved scientific limitations.

The canonical STOP condition on failed primary A10 validation is active.
No additional model/threshold search or scale fit followed it.

## F. Interface outputs and reproducibility

| Interface | Status | Evidence |
| --- | --- | --- |
| IF1 | READY FOR REVIEW | Real complete-case object; validate() PASS |
| IF2 | BLOCKED | Scientific release gate failed; no real object emitted |

IF1: data_local/problem-f/interfaces/q1-if1-domain-quality.json.
SHA-256: b8ec99ca38f2e466b427fd1a7d88858048924cc590bbe881a966d141eb9bdeb8,
also generated in
[q1-if1-summary.md](../../results/tables/q1-if1-summary.md).
IF2's canonical q1-if2-mixture-response.json is absent, so no real IF2
validation or release hash is claimed. Synthetic IF2 schema tests pass only
as infrastructure evidence. No generalized IF3 was created or schema changed.

Per-record standardized values, primary Q, locators, missingness flags and
scenario Q arrays are local-only under data_local/problem-f/derived/q1/.
Full numerical reports and frozen model fingerprints are there as JSON;
small regenerable summaries are tracked. The model fingerprint is
2d16545756f181bf399cb2b36e2a1a0b840c8f15f23057525ce9b24584ef45b5.
The normalization fingerprint is
b460ac12c4cd91b43d43a70f12d5871b89f959520c9d0793551c4b8dd69e1c57.

The environment.yml project environment was created without modifying that
file or adding dependencies. Scientific execution uses its activated Conda
interpreter: Python 3.11.16, NumPy 2.4.6, SciPy 1.17.1, pandas 3.0.6,
PyYAML 6.0.3, pip 26.2.1. The intended Python 3.11 requirement is now verified.
The specification does not pin every dependency/build; future re-solving is
not promised to recreate identical package builds.

Preflight actually ran python --version, where.exe python and pip --version:
the shell default remains base Python 3.13.9, with MSYS2 second on PATH.
Those are not the scientific interpreters. Direct unactivated invocation of
the new interpreter crashed during numerical tests; using conda run with
its explicit environment prefix resolved activation and all tests passed.
Commands below use the equivalent named environment rather than a machine
path. Each scientific entry/reproduction script prints its actual interpreter.

Exact regeneration/check commands (run in the project environment):

```powershell
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_reproduce.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_quality.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_mixture.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_scalarize.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_audit_inputs.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_selftest.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_selftest_infrastructure.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_selftest_closure.py
conda run -n modeling-research-2026 --no-capture-output python scripts/selftest_interfaces.py
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PreCommit
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PrePush
```

The direct Python raw-audit and mixture commands return 2 for different,
explicitly reported failures; conda run may map the child failure to exit 1.
q1_reproduce.py checks the actual child codes, release reports, raw hashes,
interface validation and artifact bytes across two complete passes. Its
reproducibility PASS does not relabel Q1b FAIL as success.
The plain PowerShell safety invocation is blocked by local execution policy;
process-scoped Bypass runs the unchanged gate.

Validation receipt: 9 original Q1 tests, 21 infrastructure tests, 7 closure
tests and 21 shared-interface assertions PASS. Invalid fixtures reject partial
NaNs, infinities, bad widths, held-out selection, role misuse, altered frozen
coefficients, invalid interfaces and failed scientific acceptance metrics.
[Full regeneration receipt](../../results/tables/q1-reproduction.md): two
complete passes are byte-identical for all sixteen scientific tables,
three standardized arrays, four analysis/freeze JSON reports and real IF1.
All sixteen raw inputs plus the official DOCX match the secured checkpoint
and remain unchanged. The raw audit retains exit 2 and the separate mixture
failure retains exit 2; IF1 exits 0. No unexpected generator failure occurred.
The new reproducibility wrapper initially caught its own attachment-ID
enumeration bug before running generators; the paired Loss-ID mapping was
corrected, then the full two-pass check passed.
PreCommit, whitespace and staged-path checks pass. PrePush passes on the
implementation HEAD above (99 candidate files, 30 reachable commits and five
permitted addresses); the documentation follow-up is gated again before push.

Code is under src/quality/{realdata,uncertainty,closure,handoff}.py and
src/mixture/{validation,closure}.py, with scripts/q1_* entry points.
The input audit and scalarization contract remain independently executable.

## Execution/reproducibility deviations

As reported by M1, prior formal execution began with Fable 5.1 API and
continued with Sonnet 5 after quota exhaustion. That differed from the
requested model/effort and remains an execution/reproducibility deviation;
it does not by itself invalidate scientific outputs. The earlier Python
3.13.9 environment deviation is historical; this continuation verified 3.11.
Canonical specifications were not edited or reconstructed.

## G. Unresolved limitations and exact next action

M1 should review Draft PR #12, especially the failed A10 gate, and issue a
canonical delta instruction deciding the permissible scale scope of IF2 or
a revised scale-dependent method and validation plan. A6-A11 are now seen
validation evidence and cannot be represented as fresh held-out evidence
for a newly selected route. Until that decision, T-008 may review IF1 but
must not assume an approved mixture-response interface exists.

The PR remains Draft and unmerged. Only configs/q1.yaml received new
configuration authorization; no other protected/shared path, TASKS.md,
canonical specification or other owner's active path was changed.
Raw inputs and .claude/ remain local-only and untouched.
