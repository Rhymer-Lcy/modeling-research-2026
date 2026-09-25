# T-008 handover

| Field | Value |
| --- | --- |
| Task | T-008 |
| Owner | M1 |
| Status | **final review checkpoint** — v4 closure complete; generalized quality-aware IF3 NOT ADOPTED; classic IF3 is the canonical final interface. `TASKS.md` keeps T-008 `wip` until supervisory review of PR #8 |
| Timestamp | 2026-09-25T14:40:00+08:00 (v4 closure); v1/v2 sections below dated 2026-09-23 |
| Base | `87fbce3` (main, branch point); synchronized with main `94bbabe` by merge `516ef85` |
| HEAD | see "v4 final closure" below for the evidence HEAD |
| Branch / PR | `exp/m1-T008-generalized-scaling` / Draft PR #8 |

## Scope

Extend the accepted classic N-D law to a quality-aware generalisation, and
advance every component that does not depend on the final numerical content of
IF1/IF2. The stage was explicitly permitted to conclude that a term adds
nothing; it reaches a stronger negative conclusion than that, described below.

## Completed work

- Quality-aware law implemented as a tested callable, with marginal effects,
  elasticities, iso-loss substitution, and the two distinct capacity
  transforms: `src/scaling/quality.py`.
- 47 executable assertions over the load-bearing mathematics, including a
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

`selftest_quality.py` reports PASS 47 / FAIL 0. The three `q2_*` scripts each
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
name. What `Q_score` measures in B8 **remains unresolved by the available
provenance**: the official materials do not settle it, and no candidate reading
is asserted here. The fact is recorded rather than guessed.

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

### 4. The fitted candidate form does not reproduce B7 to storage precision

On B6/B7 the fingerprint ratio is in the hundreds (≈865 on B7), not near 1: the
fit leaves a median relative residual of order 1.7% against a rounding quantum
of order 2e-05. Unlike the classic N-D law on B1, **this is not a generator
recovery** — the fitted `(Q^gamma * D)` effective-token form is not the exact
mechanism behind these tables.

Stated precisely, because the distinction matters: this is a
reproduction-accuracy finding, not a statistical test. No noise model is
posited and no hypothesis is tested, so the diagnostic does **not** reject the
functional form. It establishes only that this fit is not B7's exact recovered
generator.

The reported gamma (≈1.19 on B7) is therefore an imperfect approximation under
the current fit. It is labelled as such in the artifact and must
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
negative gamma to confirm the sign checks actually flip. PASS 47 / FAIL 0.

Three defects were caught during the v1 stage and fixed rather than papered
over (the v2 delta records its own separately):

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

Consumes nothing new. Produces no new interface object: **no generalized IF3 is
emitted**, because its `q_term` would rest on a form that does not reproduce its
own source table to storage precision, fitted to one unreplicated grid.

The classic IF3's **functional form, fitted parameters, schema version and
validity box are unchanged**. Its **provenance notes were strengthened** by the
v2 delta to carry the organizer's label for B1, the numerical fingerprint
finding, the consequence that the fitted parameters support estimator and
generator recovery rather than precise empirical knowledge of real scaling, and
the statement that empirical external support comes from B4 with the
overlapping Pythia rows excluded and from B5. The organizer's `trust` category
remains `observed`. `validate()` passes.

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
   an audit showing the fitted candidate form does not reproduce the only
   usable table to its storage precision.
2. **gamma is not a measured quantity.** It is an imperfect approximation under
   the current fit, on a designed unreplicated grid, in one table. Note this is
   not a statistical rejection of the form — no such test was run.
3. **B8 is unusable pending provenance.** Roughly two thirds of the
   quality-bearing rows are currently excluded.
4. **IF1/IF2 are absent** from the canonical interface location; only
   `IF3_classic.json` exists. The Q(p) versus residual-p question of B6 cannot
   be opened at all yet.
5. The classic baseline's narrow intervals remain a property of its
   near-deterministic fit table, not a statement about real model scaling. That
   finding is preserved, not weakened.

## v2 supervisory delta (2026-09-23)

Narrowly scoped correction of three review findings plus one bounded
diagnostic. The v1 sections above are unchanged; this section records only the
delta.

### 1. Out-of-validity quality targets — fixed

The substitution scenario table multiplied a base quality by fixed factors and
so walked outside the fitted box: it printed targets of **1.05** and **1.35**
while the fitted ceiling is **Q = 1**, reporting extrapolation as though it were
interpolation.

Fixed structurally, not by deleting the offending rows. `Q_min`/`Q_max` now come
from the fitted validity box; candidates are clipped to the ceiling; only
targets satisfying `Q_base < Q_target <= Q_max` survive; duplicates created by
clipping several multipliers onto the same ceiling are collapsed; and a base
already at the ceiling yields **no** target, which the artifact states
explicitly instead of inventing one.

The construction lives in `src.scaling.quality.upward_quality_targets` so it is
importable and testable, and `scripts/q2_substitution.py` additionally raises on
the targets it actually emitted — a gate on output, not on intent. The regenerated
table now carries 7 rows (was 9; two were clipped duplicates) with every target
at or below 1.

### 2. Claim language — corrected

The artifact previously called this the adopted form and said the estimator
recovers the supplied quality mechanism. Both are withdrawn. It now states that
`(Q^gamma * D)` is a **candidate** form, not adopted, with no generalized IF3
emitted; that the fit does not reproduce B7 to that file's storage precision, so
the form is not B7's exact recovered generator; and that gamma is an imperfect
approximation under the current fit on a single designed, unreplicated,
semi-synthetic grid. The artifact also says explicitly that this is a
reproduction-accuracy statement and not a statistical rejection of the form.

The document is now split into **analytical identities** — exact consequences of
the candidate form, dataset-independent, machine-checked — and **numerical
illustrations**, explicitly labelled model-internal illustrative sensitivity and
explicitly **not the final Q2 empirical substitution result**. No mathematics
was removed and no tested sign derivation was weakened.

### 3. Classic IF3 provenance — hardened

No schema change, and the organizer's `trust` category for B1 is deliberately
left as `observed` rather than dishonestly downgraded. The provenance notes now
carry, in order: the organizer's label; the numerical fingerprint finding; the
consequence that the fitted parameters support estimator and generator recovery
rather than precise empirical knowledge of real scaling, so the narrow
intervals must not be read that way; and that empirical external support comes
from B4 with the overlapping Pythia rows excluded and from B5.

### 4. B8 reversal diagnostic — result

Appended to the existing audit rather than made a new artifact. Two reversible,
order-reversing transforms were tried on the quarantined B8 calibrated stratum.

| Variant | Cells | Slope negative | Median slope | gamma | At a bound? | Fingerprint ratio |
| --- | ---: | ---: | ---: | ---: | :--: | ---: |
| as supplied | 90 | 0 | +0.5521 | 0.001 | yes (lower) | 1.06e+04 |
| `Q' = 1 - Q` | 90 | 90 | -0.5045 | 10 | yes (**upper**) | 5874 |
| rank reversal | 90 | 90 | -0.5051 | 10 | yes (**upper**) | 6815 |

Both transforms flip the sign, as any order-reversing map must. Neither
produces an identified exponent: gamma moves from the lower bound to the
**upper** bound, and the fingerprint ratio stays in the thousands.

**Permitted conclusion recorded:** reversal is numerically consistent with a
possible opposite-oriented score **in direction only**; it does not resolve the
incompatibility of the candidate form with this table, so the result remains
ambiguous. The artifact states explicitly that nothing here establishes that
B8 means corruption, noise, or `1 - quality`, and **B8 remains quarantined**.

### A defect this delta caught in its own check

The first run of the reversal diagnostic reported "the exponent leaves its
lower bound, so the term is estimated". It had moved to the *upper* bound — my
`gamma_at_bound` test only compared against the floor. A one-directional check
reported a ceiling-pinned parameter as a successful estimate. The bounds are now
exported as `GAMMA_BOUNDS` from the module that enforces them, both ends are
tested, the report names which end, and the conclusion was downgraded
accordingly.

### Validation of the delta

`selftest_quality.py` PASS **47** / FAIL 0 (was 25; 22 new assertions cover the
target ceiling, strict improvement, de-duplication, the two specific defect
values 1.05 and 1.35, and the empty-result case). `selftest_interfaces.py` 21
assertions pass. Substitution, audit and classic-fit scripts regenerate.
`git diff --check` clean; public-safety gate passes. No raw data, interface
schema, or M2/M3 path changed.

## v4 final closure (2026-09-25)

Final IF1/IF2 consumption, unit closure, generalized-law decision, final IF3
decision and review checkpoint, per `worklog/specs/T-008.md` v4. The v1 and v2
sections above are retained as history; statements in them that this section
supersedes are listed at the end of this section.

| Field | Value |
| --- | --- |
| Task / owner | T-008 / M1 |
| Branch / PR | `exp/m1-T008-generalized-scaling` / Draft PR #8, unmerged |
| Synchronized main base | `94bbabe`, merged into the branch as `516ef85` (merge, not rebase) |
| Evidence HEAD | `7dd027c` (last commit carrying code or generated artifacts; later commits touch only this package and the worklog) |
| Canonical evidence | `results/tables/q2-final-closure.md`, regenerated by `scripts/q2_final_closure.py` |

### Execution environment and the STOP it crossed

The v4 execution began under **Claude Opus 5 + xhigh** and stopped at the
accepted-interface hash/provenance reconciliation gate: IF1 and IF2 were not
present on this machine, and IF1 regenerated here hashed differently from the
accepted object. It resumed under **Claude Opus 5.5 + xhigh** once M2's exact
producer handoff was supplied. That was an execution-environment change only;
it is not a change to the scientific specification, and it neither alters nor
strengthens any evidence below.

The handoff bytes were hashed before installation and installed into the
`src.paths` interface directory by raw byte copy: IF1 `b8ec99ca…eb8` (19,008
bytes) and IF2 `9f2a83da…f91` (369,741 bytes), both matching exactly, before and
after installation. T-007 was not re-run.

**Diagnosis of the earlier IF1 mismatch.** The preserved M1 regeneration
(`da3e83cf…136`, 19,043 bytes) was compared with the accepted object field by
field. Four top-level leaves differ. Three are load-bearing numbers
(`q_by_domain/wikipedia`, `q_ci_by_domain/c4[0]`, `q_ci_by_domain/wikipedia[1]`)
and differ by 5.55e-17 to 1.11e-16, one unit in the last place. The fourth is
`provenance/notes`, whose embedded record differs in 21 leaves: 19 numbers, each
by at most 1.11e-16, and two hashes. Of those, `configuration_sha256` is proven:
the accepted `f59d850c…` is the hash of `configs/q1.yaml` as stored in git (LF),
and the regeneration's `e9284642…` is the same file as checked out here with CRLF.
`normalization_sha256` is a byte hash over the frozen reference distributions as
`float64`, so any last-bit change in one of them changes it; the specific array
was not identified, because the continuation forbids re-running the producer.
The two runs used different runtimes (accepted: Python 3.11.16, numpy 2.4.6,
scipy 1.17.1, pandas 3.0.6; regeneration: Python 3.12.10, numpy 2.2.6, scipy
1.16.3, pandas 2.3.3).

**Classification: floating-point numerical drift**, the class governing every
load-bearing difference, accompanied by a proven provenance/runtime-metadata
drift in the configuration hash. **No substantive scientific difference**: domain
count, coverage fraction, sample counts, mapping, mapping types and indicator
directions are identical, and no value moved by more than one unit in the last
place. Recorded as a reproducibility limitation; the accepted producer object is
canonical.

### Reproducibility findings in the project environment

- The declared project environment `modeling-research-2026` existed but held
  none of its declared dependencies, so the v1 and v2 checkpoints had silently
  run on the machine's default Python 3.12. The dependencies were installed
  pinned to the exact runtime the accepted T-007 reproduction records, and the
  closure verifies that match on every run.
- The environment must be invoked **activated** (`conda run`). Calling its
  interpreter by path leaves its DLL directory off `PATH`, and scipy's L-BFGS-B
  then dies inside the optimiser with Windows code `0xc06d007f` because it
  resolves BLAS/LAPACK from another installation.
- Regenerating the v1/v2 tables in the project environment moved the printed
  classic estimates in the fifth or sixth significant figure (A 406.24 to
  406.268, alpha 0.339979 to 0.339983, B 409.748 to 409.744) and reached a
  slightly **lower** objective (1.69794e-06 to 1.69788e-06): the earlier run had
  stopped short in the flat A-alpha valley. Every qualitative conclusion is
  unchanged, including leave-one-trajectory-out being narrower than the
  bootstrap for all five parameters. The regenerated tables are the committed
  ones.
- `environment.yml` pins only Python. Without pins a future environment can
  drift in the last printed digits again. Pinning it is outside T-008's paths and
  is left as a recommendation.

### Accepted T-007 interfaces

| Check | Result |
| --- | --- |
| IF1 hash, read from the tracked accepted summary | `b8ec99ca38f2e466b427fd1a7d88858048924cc590bbe881a966d141eb9bdeb8`, match |
| IF1 contract | `.validate()` PASS; 7 quality domains; mapped mass 0.5646359074665894; 6 mixture domains mapped, 11 unmapped; native directions 15 higher / 4 lower / 3 non-monotone |
| IF2 hash, read from the tracked accepted summary | `9f2a83da45633858822c8416b5fa70a9537a06b07ac9056e50d871492b16ff91`, match |
| IF2 contract and scope | `.validate()` PASS; fit scale **1M**; fit and selection A4/A5 only; frozen fingerprint `2d16545756f181bf399cb2b36e2a1a0b840c8f15f23057525ce9b24584ef45b5` |
| IF2 retained failures | A8/A9 60M absolute transfer failed; A10/A11 1B centred normalised RMSE 2.207985640835773 > 2.0 failed; broad `release_pass` false; scale invariance unsupported; absolute use outside 1M prohibited; fitted 10B/70B extrapolation not released |

The consumer reads the expected hashes from the tracked accepted summaries
rather than typing them, refuses any byte difference, and enforces every scope
limitation before use. **IF2 is 1M only.**

### Quality-axis semantics — the decisive finding

IF1's Q is a relative midrank score against the pooled A1 reference, which sits
at **0.5 by construction**; domain values span 0.4206–0.6594. B7's `Q_score` is a
design variable on 0.1–1.0. The organizer's material describes the NQ tables
only as semi-synthetic N-D-Q points calibrated on real scaling laws plus noise,
and defines no construction, anchor or direction for `Q_score`, and no relation
to the quality signals IF1 is built from. The data-description PDF also carries
hidden cross-page text, consistent with what the T-006 security audit flagged;
it was not treated as a first-party definition, and it defines no mapping in any
case.

No first-party mapping exists, so none is declared, and the binding guard
refuses to feed IF1 Q into a law calibrated on `Q_score`. B7's gamma therefore
cannot be read as an elasticity of IF1 Q. This is a v4 STOP condition for the
generalized route, and on its own sufficient for the decision; it does not touch
the classic IF3.

### Generalized-law adoption gates

Criteria were fixed in the script before any fit ran. Evidence in
`results/tables/q2-final-closure.md`.

| Gate | Result | Evidence |
| --- | --- | --- |
| GQ1 parameter domain | PASS | on B7, in billions: alpha 0.274045, beta 0.0698836, gamma 1.18867, all interior |
| GQ2 directional stability | PASS | 45 of 45 B7 cells have dL/dQ < 0; B8 excluded |
| GQ3 internal usefulness | PASS | leave-one-Q-level-out RMSE(log L) 0.03051 vs no-Q baseline 0.04885, error reduction 0.3755; the candidate is worse on the Q = 0.5 and 0.6 folds |
| GQ4 robustness / identifiability | **FAIL** | moving gamma by 10% raises the objective by only 0.8% and 0.5%; across the profile gamma spans a factor of 4 while gamma × beta spans 1.29 — B7 constrains the product, not gamma. Block-out gammas stay interior (leave-one-Q range 0.286 of gamma-hat; leave-one-N 1.141–1.303; leave-one-D 1.129–1.543) |
| GQ5 real 1M consistency (diagnostic) | **FAIL** | Spearman(Q(p), macro 1M loss) −0.0246 overall; +0.0557, +0.024, −0.0934 by mapped-mass tercile |
| GQ6 provenance discipline | not applicable | satisfiable; nothing is emitted |
| GQ7 validity discipline | **FAIL** | the classic law fits B7 at Q = 1 (median abs. rel. error 0.01521), and the candidate's N-D component does well on B5 (0.0633 vs the classic 0.07515), but on B4 with Pythia excluded it reaches 0.09878 against a tolerance of 0.0807, the classic law's own worst external error. The Q term was also identified only for D ≥ 1e10 tokens, above the classic lower bound of 1.34e8 |

**Decision: NOT ADOPTED.** No generalized IF3 is emitted. **Gamma status:
weakly identified** — interior, but only the product gamma × beta is well
constrained by B7, and it is a semi-synthetic calibration in any case, never an
empirical property of real models.

The gamma profile uses a local optimiser from three starts per point. An
imperfect conditional optimum can only raise a profile value, so the true
profile is at most as steep as reported and the GQ4 failure is conservative.

### Q(p) and residual composition at 1M

Q(p) was built only from the A16 mapping and IF1's values, as the mapped-mass
conditional mean, on the 512 A4 fitting designs. Five have zero mapped mass;
their Q(p) is undefined and was not imputed. Only A4 was read; IF2 was evaluated
only at 1M, by a consumer evaluator that reproduces M2's own predictor to
7.99e-15.

Q(p) explains on average **0.0683** of a target's variation across the fitting
designs (0.172 with mapped mass added); its slope is negative for 3 of 13
targets. **Q is not a sufficient summary of composition at 1M.** The one target
where Q(p) explains much, arXiv (R² 0.543), is the domain with the highest IF1 Q,
so that association is confounded by domain matching rather than evidence of a
quality effect. This is a descriptive 1M finding, not causal mediation and not a
cross-scale result. **p enters the final IF3 not at all.**

### B8

Unchanged and still quarantined: dL/dQ > 0 in 90 of 90 calibrated cells and 60
of 60 extrapolated cells; 129 and 233 rows sit on the exact 0.5 loss floor;
reversal flips the sign but pins gamma to its upper bound with fingerprint
ratios 5874–6815. No gate, box or fit used B8.

### G2-U unit equivalence — PASS

The internal convention is read from the organizer's column names
(`N_params_B`, `D_tokens_B`: s_N = s_D = 1e9), not assumed, and
`src/scaling/units.py` owns every conversion: A_raw = A_int · s_N^alpha,
B_raw = B_int · s_D^beta, with E, alpha, beta and gamma unchanged and Q
dimensionless. Predictions at the same physical point agree across the two
representations to 1.86e-16 over 75 points (candidate) and 2.17e-16 over 113
points (classic, including every B4 and B5 row), against a justified tolerance of
1e-12. Parameter and validity-box round trips are exact, and the serialised
classic box equals B1's own range in raw counts. A deliberately half-converted
parameter set or box fails the check by more than three orders of magnitude.

### Final IF3

| Property | Value |
| --- | --- |
| Canonical object | classic IF3, `data_local/problem-f/interfaces/IF3_classic.json` (local-only) |
| SHA-256 | `720efea859d3be3b39ac2ee1976f8adaf7a31b8b5b1a71eb72e8ee8f987c8514` |
| Functional form | `E + A*N**-alpha + B*D**-beta` |
| Parameters | E 1.68982, A 406.268, alpha 0.339983, B 409.744, beta 0.279888 |
| External units | N raw parameter count, D raw token count |
| Validity box | N 7.054e7 – 1.197e10; D 1.34e8 – 2.999e11; Q [1, 1] is a sentinel for "no quality dimension", not a value on IF1's scale |
| Uncertainty | model-clustered bootstrap (8 clusters, 399 replicates), leave-one-trajectory-out and profile identifiability, in `q2-uncertainty-robustness.md`. They measure different things and are not interchangeable |
| Contract | `.validate()` PASS; schema 1.0; shared schema unchanged |

Its form, parameters, schema and validity box are the classic law's. Its
`q_term_provenance` was corrected: it no longer says "not yet fitted", and now
documents the Q sentinel and points to the closure decision.

### The classic law's evidence, re-verified

| Table | Status in this closure |
| --- | --- |
| B1 | principal fit. The organizer labels it observed, and its loss column is consistent with deterministic evaluation of the published law to about storage precision, so the fit supports estimator/generator recovery, not precise empirical knowledge of real scaling. The closure guard refits B1 and requires the emitted IF3 to match to 1e-9 |
| B5 | observed external validation (literature): median abs. rel. error 0.07515 |
| B4, Pythia excluded | observed external validation: 0.0807. With Pythia included it is a leakage contrast only |
| B6 / B7 | B7 contains B6 with bit-identical losses (re-verified: PASS), so B6 adds no independent evidence. Both are organizer-labelled semi-synthetic quality calibrations |
| B8 | quarantined; see below |

### Downstream permissions and prohibitions

**T-010 may consume** the classic IF3 in raw N and D inside its box; IF1 as
domain quality with its conditional intervals and partial mapping; and IF2 for
absolute use at 1M only. Q dependence is **not** part of the accepted scaling
law. IF1 and IF2 are scenario inputs for any Q3 quality/compute trade-off.

**T-010 may not** use IF2 outside 1M; feed IF1 Q into B7's gamma; read the Q
sentinel as IF1 Q = 1; treat `src/scaling/quality.py` as an adopted law (it is
analytical and sensitivity machinery only); use B8; extrapolate past the box
without declaring it; or combine these pieces into an empirically validated
cross-scale quality law.

**T-011 may compare** classic IF3 predictions in raw N and D, inside the box,
with historical and frontier data, carrying the B1 provenance caveat and the
interval families. The Q-aware term is **absent**; B7 quality behaviour is
semi-synthetic and diagnostic only; B8 is quarantined; and the 1M IF2 does not
establish cross-scale composition transfer.

### Validation actually run

All in the project environment via `conda run -n modeling-research-2026
--no-capture-output python …`:

```
scripts/q2_fit_classic.py
scripts/q2_uncertainty.py
scripts/q2_substitution.py
scripts/q2_audit_quality_data.py
scripts/q2_final_closure.py
scripts/q2_reproduce.py
scripts/selftest_quality.py
scripts/selftest_interfaces.py
scripts/selftest_q2_closure.py
```

and, from the repository root:

```
git diff --check
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PreCommit
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PrePush
```

`selftest_quality.py` PASS 47 / FAIL 0; `selftest_interfaces.py` 21
assertions PASS; `selftest_q2_closure.py` PASS 73 / FAIL 0. Between them they
cover all twenty v4 guards, most with a deliberately invalid fixture that must
fail.

**Deterministic reproduction: PASS.** `q2_reproduce.py` ran every Q2 generator
in two complete passes (`results/tables/q2-reproduction.md`). All six artifacts
are byte-identical across passes and LF-only, and the 31 raw attachment files
are unchanged in content, size and modification time. Each recorded table hash
equals the committed blob, checked independently of the script. The runtime
equals the accepted T-007 reproduction's exactly.

### Defects caught during this stage

- **A race of my own.** I edited the audit script while a background job was
  about to run it; it ran half-edited. Re-run after all edits settled.
- **An inherited v2 defect, and the more serious one.** The audit wrapped its
  reversal fits in a broad `except`. The race's `NameError` was caught, written
  into a table cell as "fit failed", the script exited **0**, and its prose still
  concluded the exponent was "parked on a BOUND" — because a missing result
  defaulted to "at bound". A crashed computation was rendered as a scientific
  finding. Now only numerical fit failures are caught; one yields "no conclusion
  / result remains ambiguous"; a programming error crashes. Both paths are
  mutation-tested.
- **Typed conclusions in generated artifacts.** My first closure renderer, and
  one sentence in the audit ("stays in the thousands"), stated results in prose
  that nothing computed. Every such sentence is now computed or conditional.
- **Input and output sharing one path variable.** The closure script used the
  same name for its output directory and for reading an accepted T-007 record;
  a render test that redirected the output also redirected the input. Split.
- **A reproduction record whose hashes could not be checked against the
  repository.** The first two-pass run passed, but three v1 generators
  (uncertainty, substitution, audit) wrote CRLF on Windows while the other two
  wrote LF. Git stores LF, so those three recorded hashes matched neither the
  committed blob nor any LF checkout, and the record's own "LF line endings"
  header was a typed claim, not a checked one. Found by hashing the committed
  blobs against the record. All generators now write LF; the reproduction
  refuses any artifact containing a carriage return (tested in both directions)
  and was re-run in full.

### Scientific limitations

- The classic fit remains estimator/generator recovery on B1; its narrow
  intervals are not precision about real scaling. External support rests on B5
  and B4 with Pythia excluded, whose median errors are about 7.5% and 8.1%.
- No quality exponent is an empirical property of real models. B7's is a
  semi-synthetic calibration, weakly identified apart from gamma × beta, on an
  axis no first-party mapping connects to IF1.
- The IF1 byte mismatch is explained as last-bit numerical drift, but the
  specific normalisation array behind `normalization_sha256` was not identified.
- GQ7's failure rests on one of three compatibility checks (B4 with Pythia
  excluded, 9.9% against 8.1%). The decision does not depend on it: the missing
  axis mapping alone stops the generalized route.

### Statements above superseded by this section

- Header "awaits IF1/IF2" and known limitation 4, "IF1/IF2 are absent": IF1 and
  IF2 are now consumed and verified.
- Known limitation 1, "No generalized law is adopted": this is now the formal
  final decision, not a pending state.
- "Produces no new interface object": still true for a generalized object; the
  classic IF3 is now declared the canonical final interface.
- The v1 command list (`python scripts/...`): run these in the activated project
  environment.
- Classic figures quoted from the v1 tables (A 406.24, alpha 0.339979,
  B 409.748): superseded by the project-environment regeneration.

## Next action

Supervisory review of Draft PR #8. T-008 stays `wip` in `TASKS.md` until that
review; PR #8 stays Draft and unmerged. T-010 and T-011 are not started and must
consume only what the downstream contract above permits.
