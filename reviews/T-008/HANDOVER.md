# T-008 handover

| Field | Value |
| --- | --- |
| Task | T-008 |
| Owner | M1 |
| Status | wip — independent work delivered, generalized Q/p closure awaits IF1/IF2 |
| Timestamp | 2026-09-23T15:40:00+08:00 |
| Base | `87fbce3` (main) |
| HEAD | branch tip of `exp/m1-T008-generalized-scaling` |
| Branch / PR | `exp/m1-T008-generalized-scaling` / draft PR |

## Scope

Extend the accepted classic N-D law to a quality-aware generalisation, and
advance every component that does not depend on the final numerical content of
IF1/IF2. The stage was explicitly permitted to conclude that a term adds
nothing; it reaches a stronger negative conclusion than that, described below.

## Completed work

- Quality-aware law implemented as a tested callable, with marginal effects,
  elasticities, iso-loss substitution, and the two distinct capacity
  transforms: `src/scaling/quality.py`.
- 25 executable assertions over the load-bearing mathematics, including a
  deliberately invalid fixture: `scripts/selftest_quality.py`.
- Structural and provenance audit of every quality-bearing and large-model
  table, run **before** any quality law was believed:
  `results/tables/q2-quality-data-audit.md`.
- Two uncertainty diagnostics complementary to the clustered bootstrap:
  `results/tables/q2-uncertainty-robustness.md`.
- Marginal effects and substitution, with provenance carried in the artifact:
  `results/tables/q2-substitution.md`.
- Canonical specification archived: `worklog/specs/T-008.md`.

## Evidence

**Code**

- `src/scaling/quality.py`
- `scripts/q2_audit_quality_data.py`
- `scripts/q2_uncertainty.py`
- `scripts/q2_substitution.py`
- `scripts/selftest_quality.py`

**Regenerable artifacts**

- `results/tables/q2-quality-data-audit.md`
- `results/tables/q2-uncertainty-robustness.md`
- `results/tables/q2-substitution.md`

**Commands actually run**

```
python scripts/selftest_quality.py
python scripts/q2_audit_quality_data.py
python scripts/q2_uncertainty.py
python scripts/q2_substitution.py
python scripts/q2_fit_classic.py
python scripts/selftest_interfaces.py
powershell -File scripts/check_public_safe.ps1 -Mode PreCommit
```

`selftest_quality.py` reports PASS 25 / FAIL 0. The three `q2_*` scripts each
write the table named above. The classic baseline and the interface self-test
still reproduce unchanged.

## Key results

### 1. B6 and B7 are one table, not two

All 360 B6 design points appear in B7 with bit-identical losses (maximum
difference over the shared cells is exactly 0). B7 adds two quality levels and
nothing else. Counting them as separate evidence would double-count. Only B7 is
used.

### 2. B8's quality column runs in the opposite direction — a stop condition

Measured in **every** (N, D) cell rather than in cells chosen by hand:

| Table | Cells | Slope negative | Slope positive | Median `dlogL/dlogQ` |
| --- | ---: | ---: | ---: | ---: |
| B6 | 45 | 45 | 0 | -0.0537 |
| B7 | 45 | 45 | 0 | -0.0517 |
| B8 calibrated | 90 | 0 | 90 | +0.5521 |
| B8 extrapolated | 60 | 0 | 60 | +0.5318 |

The sign is unanimous within each table and opposite between them, with no
exceptions in 240 cells. In B6/B7 loss falls as `Q_score` rises; in both B8
strata it rises, with a slope an order of magnitude larger.

Under the candidate law a positive `dL/dQ` is not representable at all, so
fitting B8 does not estimate a quality exponent — it drives gamma to its lower
bound (0.001, the bound itself) and returns a number with no interpretation.
That is what the first run of the audit produced, and it is why the audit now
refuses to fit B8.

**B8 is excluded from quality-law estimation until its column semantics are
resolved.** The three tables do not share a meaning for a column with the same
name. This is a provenance question — B8's `Q_score` may be a corruption or
noise fraction, a differently-normalised score, or another quantity entirely —
and it is recorded rather than guessed.

### 3. B8 is clamped

| Table | Minimum loss | Rows at that minimum |
| --- | ---: | ---: |
| B6 | 2.016 | 1 |
| B7 | 2.016 | 1 |
| B8 calibrated | 0.5 | 129 |
| B8 extrapolated | 0.5 | 233 |

362 of B8's 1704 rows sit on an exact floor of 0.5. Those rows carry no
gradient information and would bias any fit including them. B6/B7 show no such
clamp.

### 4. The candidate form is misspecified even where it is fittable

On B6/B7 the fingerprint ratio is in the hundreds (≈865 on B7), not near 1: the
fit leaves a median relative residual of order 1.7% against a rounding quantum
of order 2e-05. Unlike the classic N-D law on B1, **this is not a generator
recovery**. The supplied quality mechanism is not the `(Q^gamma * D)`
effective-token form.

The reported gamma (≈1.19 on B7) is therefore a best approximation under a form
the data do not support exactly. It is labelled as such in the artifact and must
not be quoted as a recovered constant.

### 5. B9 and B10 roles

B9 is a *specification* of 132 real large models — identity, size, tokens,
compute, date, organisation — and carries no loss column at all, so it can never
be validation data. B10 supplies model-output losses for 128 of them; four have
none. Fitting to B10 and reporting agreement with B10 would be circular.

**Neither carries Q.** The quality-aware law cannot be evaluated on the
large-model set without a quality value supplied from outside, which is an IF1
dependency and not recoverable here.

### 6. Uncertainty

Point estimate, cluster-bootstrap interval, leave-one-trajectory-out range and
a profile identifiability scan are reported side by side for all five classic
parameters in `results/tables/q2-uncertainty-robustness.md`, so that no single
interval family is read as "the" uncertainty. Leave-one-model-family-out is
**not** computable on B1: every trajectory in it belongs to one family, so that
resampling unit has one level. That is stated in the artifact rather than
silently skipped.

## Validation

`scripts/selftest_quality.py` checks each analytic partial against a central
finite difference; asserts `dL/dN < 0`, `dL/dD < 0`, `dL/dQ < 0`; asserts the
iso-loss slope `dN/dQ < 0` and that moving along it holds loss constant to first
order; verifies both substitution transforms exactly restore the loss they
claim to; requires the equivalent-capacity boundary to raise
`InfeasibleEquivalent` rather than return NaN; and finally feeds a law with
negative gamma to confirm the sign checks actually flip. PASS 25 / FAIL 0.

Three defects were caught during development and fixed rather than papered over:

- The first audit run fitted B8 and reported a gamma of 0.001 — the optimiser
  bound — as though it were an estimate. Inspecting the data directly showed the
  inverted Q direction. The audit now refuses to fit a table whose quality
  effect it cannot represent, and says why.
- The quality fitter was originally a single-stage search over 324 cold starts
  at final tolerance and did not finish in reasonable time. It is now a coarse
  screen followed by tight refinement of the best 12, which is the same
  "cold grid finds the basin" logic already used by the classic bootstrap. The
  reported objective always comes from the refinement.
- The uncertainty table contained a sentence asserting that the
  leave-one-trajectory-out range is *wider* than the bootstrap interval for
  every parameter. Checked against the numbers it produced, it is **narrower**
  for all five — as it should be, since the bootstrap draws eight trajectories
  with replacement while the jackknife removes exactly one. The sentence had
  been written into the generator rather than computed from it. The script now
  computes and prints the width ratio, so the claim cannot go stale.

## Interfaces and downstream impact

Consumes nothing new. Produces no new interface object yet: the classic IF3 is
untouched, and **no generalized IF3 is emitted**, because its `q_term` would
rest on a misspecified form fitted to one unreplicated grid.

Downstream tasks may rely on the mathematics being correct and sign-tested, and
on the provenance findings above. They must **not** rely on a numerical quality
exponent, on B8 in any form, or on any large-model quality-aware prediction.

## Deviations from plan

The specification anticipated that a quality exponent would be identified from
the semi-synthetic tables and reported as generator recovery. Two of its
premises did not survive contact with the data: the tables do not share a
quality scale, and the candidate form does not recover the generator even where
the direction is right. The stage therefore stops short of a generalized fit
rather than producing one under assumptions the audit disproved.

## Known limitations and open risks

1. **No generalized law is adopted.** What exists is a tested implementation and
   an audit that says the candidate form is misspecified on the only usable
   table.
2. **gamma is not a measured quantity.** It is a best fit of a form the data
   reject at storage precision, on a designed unreplicated grid, in one table.
3. **B8 is unusable pending provenance.** Roughly two thirds of the
   quality-bearing rows are currently excluded.
4. **IF1/IF2 are absent** from the canonical interface location; only
   `IF3_classic.json` exists. The Q(p) versus residual-p question of B6 cannot
   be opened at all yet.
5. The classic baseline's narrow intervals remain a property of its
   near-deterministic fit table, not a statement about real model scaling. That
   finding is preserved, not weakened.

## Next action

M1 raises B8's `Q_score` semantics as a question for the problem's data
provenance, and waits for IF1/IF2 from T-007 before attempting any Q/p closure.
T-008 stays `wip`; the draft PR is a review checkpoint, not a merge candidate.
