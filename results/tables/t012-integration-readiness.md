# T-012 integration readiness: units, scales and direction conventions

**This is a readiness audit, not a scientific-results table.** It contains no
finding. It records the conventions currently encoded in accepted `main`, so
that a quantity crossing a question boundary cannot change meaning silently.

Hand-maintained, unlike the generated `q*-` tables in this directory. It is
part of T-012 pre-integration; **final T-012 integration remains blocked by
T-010 and T-011.**

Where a contract does not fix a convention, the row says so. **No ambiguous
convention is resolved here** — resolving one would be a scientific decision
taken inside an integration-planning task, which is exactly what this stage
must not do.

## Convention audit

| # | Quantity | Canonical representation | Source contract | Known conversion | Downstream risk | Acceptance check |
| --: | --- | --- | --- | --- | --- | --- |
| 1 | **N**, parameter count | **Raw parameters** in `IF3ScalingLaw.validity_box` and in the fitted law | `src/scaling/law.py`, `scripts/q2_fit_classic.py` | Source B tables store **billions** (`N_params_B`); the fit script multiplies by `1e9` before fitting | A consumer reading the validity box as billions is off by 1e9 and would judge every real model out of box | Validity box lower bound is of order 1e7, not 1e-2 |
| 2 | **D**, token count | **Raw tokens** in the fitted law and validity box | same | Source tables store **billions** (`D_tokens_B`); multiplied by `1e9` | As row 1 | Validity box upper bound is of order 1e11 |
| 3 | **N, D inside quality tables** | **Billions**, as stored | quality-table loaders | none applied | The quality work operates in billions while the classic law operates in raw units. **Two different unit regimes coexist in the same task.** | Any cross-use states which regime it is in |
| 4 | **Loss** | Validation cross-entropy, **lower is better** | B tables; `IF3ScalingLaw` | none | Sign errors in any optimization that maximizes by default | `dL/dN < 0`, `dL/dD < 0` hold in the adopted form |
| 5 | **Q**, quality | `[0,1]`, **higher is better**, enforced | `IF1DomainQuality.validate()` | none | Mixing with a native indicator direction — see row 6 | Contract rejects values outside `[0,1]` |
| 6 | **Indicator direction** | `higher_better` / `lower_better` / `non_monotone`, recording the **native** direction | `IF1DomainQuality.indicator_directions`; `results/tables/q1-scalarization-contract.md` | Accepted contract records **15 / 4 / 3** of 22; all are standardized to a common higher-is-better scale before modelling | **Highest-risk row.** Reading `indicator_directions` as "all higher-is-better" inverts 4 indicators and mis-handles 3 non-monotone ones, with nothing downstream looking wrong | The three counts sum to 22, and the standardization step is named separately from the native direction |
| 7 | **p**, mixture vector | 17-domain simplex; components non-negative, summing to 1 | `IF2MixtureResponse` | `renormalisation` field records any applied | A renormalized p compared against a raw p | `renormalisation` and `zero_policy` both declared |
| 8 | **Mixture coefficients** | Identified only up to an additive constant | `IF2MixtureResponse.contrast_basis` | none — the basis is the interpretation | A coefficient read as an absolute domain value is meaningless per the contract | `contrast_basis` non-empty; coefficients missing only the reference domain |
| 9 | **coverage_fraction** | Empirical **mapped mixture mass** in `[0,1]` | `IF1DomainQuality` | **Not** a ratio of domain counts | Reporting a count ratio as coverage overstates reach | Value is not reconstructible from domain counts alone |
| 10 | **Benchmark score** | Scale declared by `score_scale`; direction not fixed by the contract | `IF4LossBenchmarkBridge.score_scale` | Accepted panel artifact rescales raw accuracy as `max(0, (raw - baseline)/(1 - baseline)) * 100`, baseline read per subtask | **Two scales exist**: raw accuracy and baseline-rescaled score. Reproducing one from the other is the panel acceptance test, not an identity | `score_scale` states which scale, and whether higher is better |
| 11 | **Compute** | FLOPs | `supplementary_large_models.csv` (`FLOPs` column) | `compute_optimal` in `src/scaling/law.py` uses `kappa = 6.0` as the C ~ kappa*N*D convention | A different kappa silently rescales every budget | Any compute claim names its kappa |
| 12 | **Time** | Calendar date | `publication_date` in the large-model table | **No conversion exists** to evaluation or submission date | **AMBIGUOUS — NOT RESOLVED HERE.** Publication date is not evaluation date; a frontier-over-time claim depends on which is meant | T-011 must declare which date defines its time axis before any forecast |
| 13 | **Context length** | **Tokens** — the unit is settled, not ambiguous | C7 attachment semantics | none; a context length is a token count | Risk is **not** the unit. It is reporting a critical context length without saying over which range it was searched, which turns a grid endpoint into a discovered threshold | T-010 states the feasible C7-supported range, the representative regimes and the sensitivity grid alongside any critical-length value |
| 14 | **Uncertainty type** | Named per estimate | `IF3` bootstrap block; `IF1` per-domain interval; `IF4` prediction error | none — the types are not interchangeable | Confidence interval, prediction interval and model-sensitivity range presented as one quantity | Every headline estimate names its type; `IF3` rejects any bootstrap unit other than `model` |
| 15 | **Validity box** | Per-dimension `[lo, hi]` for N, D, Q | `IF3ScalingLaw.validate()` requires all three keys | none | Evaluation outside the box reported as interpolation | Classic IF3 pins **Q = [1,1]**, so any Q-dependent use of it is out of box by construction |

## Rows needing a decision before final integration

Three rows need a declaration before final integration. None is a defect in
`main`. Rows 12 and 10 are conventions no accepted contract fixes yet; row 13
is different — **its unit is settled (tokens)** and what is open is the
analysis scope. Each is owned by the task that will first need it.

| Row | Quantity | Decision needed | Owner | Gate |
| --: | --- | --- | --- | --- |
| 12 | Time basis | publication vs evaluation/submission date for the time axis | M3 (T-011) | G5 |
| 13 | Context length **analysis scope** (the unit, tokens, is already settled) | the feasible C7-supported range, the representative regimes, and the sensitivity grid used for the Q3 critical-context analysis | M2 (T-010) | G3 |
| 10 | Benchmark direction | whether the declared score scale is higher-is-better | M3 (T-011) | G5 |

## Unit-regime warning

Row 3 is worth stating on its own. **Within Q2 alone, two unit regimes
coexist**: the classic law is fitted in raw parameters and raw tokens, while
the quality-bearing tables are handled in billions. Both are internally
consistent. The risk is a future cross-comparison that mixes them, which would
be wrong by a factor of 1e9 in each of two dimensions and would still produce
finite, plausible-looking numbers.

Any artifact combining the two must state its regime in the same table as the
numbers.

This hazard is now closed at review time by **gate G2-U** in
`paper/INTEGRATION_PLAN.md`: an externally emitted IF3 must use the canonical
raw-parameter / raw-token convention; an internal fit may use billions but must
transform its parameters **and** its validity box consistently before emission;
an executable unit-equivalence check must show that prediction at the same
physical `(N, D, Q)` point is invariant across the two representations; and an
IF3 whose parameter units and validity-box units disagree is rejected rather
than repaired downstream.

Worth stating explicitly, because it is why G2-U checks a *prediction* and not
the parameters: a scale factor applied consistently to `N` and `D` is absorbed
into `A` and `B` by the functional form, so the emitted parameter values alone
cannot reveal which regime produced them.
