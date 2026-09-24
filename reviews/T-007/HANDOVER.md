# T-007 handover

| Field | Value |
| --- | --- |
| Task / owner | T-007 / M2 |
| Status | WIP; IF1 READY FOR REVIEW; IF2 READY FOR REVIEW — 1M SCOPE ONLY |
| Updated | 2026-09-24 |
| Branch | exp/m2-T007-q1-modeling |
| PR | [Draft PR #12](https://github.com/Rhymer-Lcy/modeling-research-2026/pull/12), base `main`; unmerged |

## Scope and decision boundary

T-007 now emits IF2 only as a frozen 1M composition-response interface. This
is a scope restriction based on retained negative validation evidence, not a
claim of broad scientific acceptance. A4/A5 remains the sole fitting and
deterministic selection source; no A6-A11 Loss value changed candidate choice,
coefficients, penalties, or the frozen fingerprint.

The unchanged frozen fingerprint is
`2d16545756f181bf399cb2b36e2a1a0b840c8f15f23057525ce9b24584ef45b5`.
The interface has `fit_scale: "1M"`, a passed A6/A7 held-out same-scale
receipt, and an explicit prohibition on absolute use outside 1M. The generic
shared interface schema was not changed.

## Inputs and roles

The input audit at [q1-input-audit.md](../../results/tables/q1-input-audit.md)
confirms that all A1-A16 inputs and the official DOCX match the secured
checkpoint. Raw quality input retains its known defect: 19 records have six
literal NaNs in required reduced fields. The strict raw audit remains exit 2
with `KNOWN INPUT DEFECT`; the primary quality analysis uses only confirmed
complete cases and does not repair raw data.

| Pair | Rows | Role |
| --- | ---: | --- |
| A4/A5 | 512 | Fitting and deterministic training-only CV at 1M |
| A6/A7 | 256 | Frozen held-out same-scale validation at 1M |
| A8/A9 | 256 | Paired cross-scale validation at 60M |
| A10/A11 | 64 | Frozen out-of-design validation at 1B |
| A12/A13 | 63 | Repeated training-design subset and estimated 10B reference |
| A14/A15 | 63 | Repeated training-design subset and estimated 70B reference |

A13/A15 are labelled estimated-reference diagnostics only: neither is fitting
data nor observed validation. Exact mixture boundary zeros are retained, and
rows are divided by their positive stored sums without a pseudocount.

## Frozen validation and released scope

The generated [mixture validation](../../results/tables/q1-mixture-validation.md)
keeps each target separate. Its macro results are:

| Partition | RMSE | R2 | Spearman | Mean absolute relative error | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| A6/A7 | 0.394429 | 0.725399 | 0.871799 | 0.071868 | Passed frozen same-scale 1M gate |
| A8/A9 | 1.521465 | -7.509086 | 0.874576 | 0.432211 | Failed 60M absolute transfer |
| A10/A11 | 2.896422 | -620.386395 | 0.849193 | 1.454130 | Failed 1B out-of-design shape gate |

The A10 centered normalized-RMSE is unchanged at
`2.207985640835773`, above the predeclared `2.0` maximum. Therefore:

- broad `release_pass` remains `false`;
- `scale_invariance_supported` remains `false`;
- A8/A9 absolute transfer is not certified;
- A10/A11 out-of-design shape transfer is not certified;
- no scale correction, held-out-driven reselection, or fitted 10B/70B
  extrapolation was released.

The generated [IF2 summary](../../results/tables/q1-if2-summary.md) records
`READY FOR REVIEW — 1M SCOPE ONLY`, its local object hash
`9f2a83da45633858822c8416b5fa70a9537a06b07ac9056e50d871492b16ff91`, and
`validate: PASS`. Its scope receipt binds the frozen fingerprint, A4/A5 fit
sources, A6/A7 release-validation role, and these limitations:

```text
absolute use outside 1M: PROHIBITED
scale invariance: unsupported
A8/A9 absolute transfer: not certified
A10/A11 out-of-design shape: not certified
fitted 10B/70B extrapolation: NOT RELEASED
```

## Quality and IF1 evidence

IF1 remains READY FOR REVIEW and validates. The complete-case quality analysis,
conflict analysis, extension comparison, coverage analysis, missingness
sensitivity, and method sensitivity are all generated under `results/tables/`.
They retain the previously reported limitations: one observed source shard per
quality domain, unequal domain shares, method-sensitive intermediate ranks, and
unknown missingness mechanism. IF1 does not establish a causal quality effect
on mixture Loss.

## Implementation and reproducibility evidence

Relevant owned implementation surfaces are:

- `src/mixture/closure.py` separates broad acceptance from the explicit narrow
  1M scope-release receipt and leaves extrapolation gated by broad acceptance.
- `src/mixture/handoff.py` rejects an IF2 export with a missing, altered, or
  internally inconsistent receipt.
- `scripts/q1_mixture.py` invokes the approved closure path without test-set
  tuning.
- `scripts/q1_reproduce.py` validates the local IF2 receipt in addition to the
  generic interface contract and verifies two complete byte-identical passes.
- `scripts/q1_selftest_infrastructure.py` and
  `scripts/q1_selftest_closure.py` cover valid and invalid receipt fixtures,
  frozen-model integrity, role isolation, and retained failure states.

Commands actually run in the project Conda environment:

```powershell
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_reproduce.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_mixture.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_selftest.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_selftest_infrastructure.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_selftest_closure.py
conda run -n modeling-research-2026 --no-capture-output python scripts/selftest_interfaces.py
conda run -n modeling-research-2026 --no-capture-output python scripts/q1_audit_inputs.py
```

Results: full two-pass reproduction passed; the Q1 suite passed (9 tests),
infrastructure suite passed (21 tests), closure suite passed (7 tests), and
shared-interface self-test passed (21 assertions). The raw-input audit returned
its expected exit code 2 and `KNOWN INPUT DEFECT`; this is distinct from and
does not turn into broad scientific acceptance.

[q1-reproduction.md](../../results/tables/q1-reproduction.md) records the
deterministic artifact hashes and shows both IF1 and the narrowly scoped IF2
as `READY FOR REVIEW`, while explicitly retaining the raw-audit defect.

## Remaining review boundary

T-007 remains WIP pending review. Draft PR #12 remains draft and unmerged.
Review should assess the limited IF2 only within its stated 1M absolute-use
scope, alongside the retained A8/A9 and A10/A11 failures. No T-010 work was
started, and no raw input, `TASKS.md`, canonical execution specification, or
shared interface schema was modified.
