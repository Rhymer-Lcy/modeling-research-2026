# Cross-question integration plan

Technical integration document for T-012. **Not manuscript prose**, and not a
results document: nothing here is a scientific finding.

**Status: pre-integration readiness. Final T-012 integration has not started
and remains blocked by T-010 and T-011.** The dependency graph in `TASKS.md`
is authoritative and unchanged:

```
T-007 -> T-008
T-008 -> T-010
T-008 + T-009 -> T-011
T-010 + T-011 -> T-012
```

## What this document is for

A manuscript assembled late and quickly is where four specific failures happen,
all of them silent:

* a diagnostic becomes a conclusion;
* a fit to organizer-labelled semi-synthetic data becomes an empirical fact;
* an evaluation outside the identifying support becomes a validation;
* an unreviewed branch becomes accepted evidence.

Every matrix below exists to make one of those four visible before it is
written down.

## Evidence admissibility

Only artifacts on accepted `main`, or outputs of a task that has passed review,
are project evidence. Branch and pull-request metadata may be consulted to know
*that* pending work exists and what interface it will produce. No numerical or
scientific claim from an unreviewed branch is adopted here.

At the time of writing, task branches exist for T-007, T-008 and T-009, and
T-008 has a draft pull request open as a frozen review checkpoint. Their
contents are treated as
**UNREVIEWED / NON-AUTHORITATIVE / NOT FOR MANUSCRIPT CLAIMS** and none of
their scientific conclusions appear in this plan as facts.

---

# 1. Cross-question interface matrix

Interface objects are local-only by design: none is tracked in Git. Readiness
below therefore refers to *review status*, not to file existence.

## IF1 — domain quality

| Field | Value |
| --- | --- |
| Producer | T-007 (M2) |
| Consumers | T-008; T-010 where applicable |
| Contract | `IF1DomainQuality` in `src/interfaces.py` |
| Unit / scale | `q_by_domain` in [0,1], validated by the contract |
| Provenance class | to be declared by the producer |
| Validity region | only the mixture mass the mapping actually reaches |
| Uncertainty required | `q_ci_by_domain` **and** `n_by_domain`, per domain |
| Acceptance gate | G1 |
| Current readiness | **PENDING REVIEW** — not yet reviewed, not yet accepted |

Load-bearing semantics that must survive into every consumer:

1. Quality lies in [0,1]; the contract rejects anything else.
2. **Indicator direction has two distinct facts that must not be conflated.**
   The accepted scalarization contract on `main` records the *native* direction
   of each of the 22 indicators — 15 higher-is-better, 4 lower-is-better, 3
   non-monotone — and separately requires that every indicator *reach the model*
   on a common higher-is-better scale. `indicator_directions` in IF1 records the
   native direction; it is **not** an assertion that all 22 are natively
   higher-is-better. A consumer reading it as the latter would invert four
   indicators with nothing downstream looking wrong.
3. Quality domains are **not** identical to the 17 mixture domains.
4. The mapping may be **partial**; `mixture_to_quality` admits `None`.
5. `coverage_fraction` is the **empirical mapped mixture mass**, not a ratio of
   domain counts. It is not 6/17 or any similar count-based figure.
6. Domain interval and sample size travel with the score, always.

Prohibited downstream interpretation:

* treating a partial-coverage score as a corpus-wide quality;
* assigning an invented quality to an unmapped domain, including by
  imputation, a global mean, or a neighbouring domain's value;
* quoting a domain quality without its interval and sample size;
* re-deriving `coverage_fraction` from domain counts.

## IF2 — mixture response

| Field | Value |
| --- | --- |
| Producer | T-007 (M2) |
| Consumers | T-008; T-010 |
| Contract | `IF2MixtureResponse` in `src/interfaces.py` |
| Unit / scale | 17-domain simplex; coefficients on the declared `fit_scale` |
| Provenance class | to be declared by the producer |
| Validity region | the mixture region actually spanned by the fitted data |
| Uncertainty required | `validation` must record the split and its result |
| Acceptance gate | G1 |
| Current readiness | **PENDING REVIEW** |

Load-bearing semantics:

1. 17-domain simplex: components non-negative, summing to 1.
2. Under the sum-to-one constraint coefficients are identified only up to an
   additive constant, so `contrast_basis` is what makes them readable.
3. `zero_policy` changes what the coefficients mean, because many mixture cells
   are exactly zero and log-ratio transforms are undefined there.
4. `renormalisation` must be carried, not assumed.
5. `domains_without_loss` must stay visible; a domain with no loss column is
   not a domain with zero effect.

Prohibited downstream interpretation:

* reading a single coefficient as a domain's absolute value without its
  reference basis — the contract's own docstring calls this meaningless;
* comparing coefficients fitted under different zero policies or
  renormalisations;
* treating `domains_without_loss` as measured nulls.

## IF3 — scaling law

Two distinct objects share one contract and must not be confused.

| Field | Classic IF3 | Generalized IF3 |
| --- | --- | --- |
| Producer | T-008 (M1) | T-008 (M1) |
| Consumers | T-010; T-011 where justified | T-010; T-011 where justified |
| Contract | `IF3ScalingLaw` | `IF3ScalingLaw` |
| Form | `E + A*N**-alpha + B*D**-beta` | not decided |
| Quality term | **pinned: Q box = [1,1]** | would require reviewed IF1 |
| Unit / scale | N raw parameters, D raw tokens, loss cross-entropy | as classic, plus Q on the IF1 scale |
| Uncertainty required | model-clustered bootstrap; contract rejects any other unit | same, plus quality-term uncertainty |
| Acceptance gate | G2 | G2 |
| Current readiness | produced locally by T-008 work; **the T-008 task itself is not closed** | **NOT YET EMITTED — BLOCKED ON REVIEWED IF1/IF2 AND T-008 CLOSURE** |

Restrictions that must be preserved verbatim into any consumer:

1. The organizer's label for the principal training-log table and that table's
   numerical fingerprint are **two separate facts**. The label is not withdrawn
   and the fingerprint is not a re-labelling.
2. The classic fit on that table supports **estimator / generator recovery**.
   It is not evidence about how real models scale, and its very narrow
   intervals must not be read as precision about the world.
3. Empirical external support comes from independent validation: the
   cross-family table with overlapping same-family rows **excluded**, and the
   literature table. The same cross-family table with those rows included is a
   leakage contrast only.
4. The quality-bearing tables are **not** ordinary observed quality
   experiments.
5. The quarantined quality table's semantics **remain unresolved by the
   available provenance**. No candidate reading is asserted.
6. **No final empirical quality exponent exists.**
7. Candidate analytical identities — the partial-derivative signs, the iso-loss
   substitution algebra, the two capacity transforms — are exact consequences of
   a *stated candidate form*. They are **not** equivalent to an adopted
   empirical generalized law, and must be reported at Level B, never Level A.

Prohibited downstream interpretation:

* consuming the classic IF3 as though it carried quality information: its
  validity box pins Q to [1,1], so any Q-dependent use is out of box;
* presenting a candidate identity as an empirical result;
* using any quality exponent as a measured quantity.

## IF4 — loss / benchmark bridge

| Field | Value |
| --- | --- |
| Producer | T-011 (M3) |
| Consumers | T-011; T-012 manuscript integration |
| Contract | `IF4LossBenchmarkBridge` in `src/interfaces.py` |
| Unit / scale | `score_scale` must be declared explicitly |
| Provenance class | to be declared by the producer |
| Validity region | the primary stratum; other strata carried but not pooled |
| Uncertainty required | `prediction_error` is **mandatory** by the contract |
| Acceptance gate | G5 |
| Current readiness | **NOT YET PRODUCED** |

Requirements: explicit comparability strata; a declared primary stratum that is
one of them; prediction error; a positive anchor count; benchmark score scale;
provenance.

Prohibited downstream interpretation:

* **inferring IF4 from preliminary T-009 panel work.** The panel task produces
  the panel foundation, not the bridge;
* pooling strata to enlarge the anchor set;
* propagating a bridge-based forecast without its prediction error — with few
  anchor models the mapping error can dominate the forecast.

---

# 2. Evidence-to-claim map

States: `READY` (accepted evidence exists on main), `PENDING REVIEW`,
`BLOCKED`, `NOT STARTED`.

Where evidence does not exist the required text is
**`BLOCKED - DO NOT WRITE AS A RESULT`**, never a placeholder number.

## Q1

| Claim | Minimum supporting artifact | Mandatory caveat | State |
| --- | --- | --- | --- |
| Definition of the 22-indicator quality contract | `results/tables/q1-scalarization-contract.md` (on main) | 22 is the contract; 25 upstream signals exist because one field packs four criteria; component views are sensitivity only | **READY** |
| Indicator direction standardization | same artifact | native directions are 15/4/3; standardization to higher-is-better is a separate step | **READY** |
| Overall and per-domain quality Q | IF1 | partial coverage; interval and n travel with Q | PENDING REVIEW |
| Reliability / uncertainty of Q | IF1 `q_ci_by_domain`, `n_by_domain` | interval type must be named | PENDING REVIEW |
| Indicator conflict findings | T-007 | conflict is not the same as low quality | PENDING REVIEW |
| A2/A3 replication | T-007 | replication scope must be stated | PENDING REVIEW |
| Domain mapping and mapped-mass coverage | IF1 `coverage_fraction` | empirical mapped mass, not a count ratio | PENDING REVIEW |
| Mixture effects and interactions | IF2 | no coefficient without its contrast basis | PENDING REVIEW |
| Extrapolation across scale | T-007 | Level D unless the support covers it | **BLOCKED - DO NOT WRITE AS A RESULT** |

## Q2

| Claim | Minimum supporting artifact | Mandatory caveat | State |
| --- | --- | --- | --- |
| Classic N-D scaling law fitted | `results/tables/q2-classic-fit.md` (on main) | model-clustered inference; 8 trajectories | **READY** |
| Principal-table fingerprint interpretation | same artifact | organizer label and fingerprint are separate facts; supports estimator recovery, not knowledge of real scaling | **READY** |
| Observed external validation | same artifact | cross-family with overlapping rows excluded, plus literature; the included version is a leakage contrast | **READY** |
| Uncertainty of the classic parameters | T-008 checkpoint | multiple interval families; none is "the" uncertainty | PENDING REVIEW |
| Quality dependence of loss | T-008 closure + reviewed IF1 | **BLOCKED - DO NOT WRITE AS A RESULT** | **BLOCKED** |
| Quality / parameter substitution | T-008 closure | analytical identities are Level B; any number is Level C at best | **BLOCKED** |
| Large-model extrapolation | T-008 closure | Level D; neither large-model table carries Q | **BLOCKED** |

## Q3

| Claim | Minimum supporting artifact | Mandatory caveat | State |
| --- | --- | --- | --- |
| Compute-feasible optimization | T-010 | requires final IF3 | **NOT STARTED** |
| Fixed-Q analytical benchmark | T-010 | Level B, conditional on the adopted form | **NOT STARTED** |
| Optimized Q | T-010 + reviewed IF1 | **BLOCKED - DO NOT WRITE AS A RESULT** | **BLOCKED** |
| Quality budget share | T-010 | depends on an assumed quality-cost function | **BLOCKED** |
| Critical context length | T-010 | unit is **tokens** and is settled; the claim must additionally state the feasible C7-supported range, the representative regimes and the sensitivity grid it was searched over, so a grid endpoint is not read as a discovered threshold | **NOT STARTED** |
| Structural transitions | T-010 | a transition in a model is not an observed transition | **NOT STARTED** |
| Comparison of quality-cost functions | T-010 | sensitivity analysis, not a measurement | **NOT STARTED** |

## Q4

| Claim | Minimum supporting artifact | Mandatory caveat | State |
| --- | --- | --- | --- |
| C8/C1 scale convention: raw accuracy and baseline-rescaled score are distinct quantities requiring explicit rescaling | `results/tables/q4-c8-reconciliation.md` (on main) | rescaling is `max(0,(raw-baseline)/(1-baseline))*100`, baseline read from each subtask's own configuration | **READY** |
| Detailed-task reconciliation (overall) | `results/tables/q4-c8-reconciliation.md` (on main) | accepted `main` reconciles **4 of 6** dimensions (BBH, IFEval, MMLU-PRO, MUSR) and **quarantines GPQA and MATH Lvl 5**; the artifact's own verdict is **PARTIAL** | **PENDING REVIEW** |
| Panel population | T-009 | eligibility rules and exclusions must be stated | PENDING REVIEW |
| Model-type strata | T-009 | strata are not interchangeable | PENDING REVIEW |
| Loss / benchmark bridge | IF4 (T-011) | prediction error mandatory | **NOT STARTED** |
| Scale vs non-scale decomposition | T-011 | decomposition is model-conditional | **NOT STARTED** |
| Historical technical progress | T-011 | publication date is not evaluation date | **NOT STARTED** |
| 12-month frontier forecast | T-011 + IF4 | **BLOCKED - DO NOT WRITE AS A RESULT** | **BLOCKED** |
| 24-month stress forecast | T-011 + IF4 | Level D; band must include bridge error | **BLOCKED** |

### Note on the C8 reconciliation state

Accepted `main` carries a **partial** reconciliation: 4 of 6 dimensions
reproduce, and **GPQA and MATH Lvl 5 are quarantined there**. The artifact's own
verdict is `PARTIAL`, with MATH diagnosed as carrying raw `exact_match = 0` in
the per-task records and GPQA showing a small systematic offset.

A later GPQA correction is understood to exist **only on the unreviewed T-009
branch**. That correction is
**UNREVIEWED / NON-AUTHORITATIVE / NOT FOR MANUSCRIPT CLAIMS** and is **not**
adopted here, not reproduced here, and not counted toward readiness. The
overall reconciliation claim therefore sits at `PENDING REVIEW` until G4.

What *is* established and separable is the **scale convention** — that C8 raw
accuracy and C1 baseline-rescaled score are distinct quantities requiring
explicit rescaling. That is retained at `READY` because it does not depend on
which dimensions reconcile.

## Cross-cutting

| Claim class | Requirement | State |
| --- | --- | --- |
| Uncertainty | every headline estimate names its uncertainty type and why that type fits its data | enforced at G9 |
| External validity | claims about real models rest on observed independent tables only | enforced at G8 |
| Extrapolation | any evaluation outside a declared validity box is labelled Level D | enforced at G8 |
| Provenance | no semi-synthetic or generated result is presented as observed | enforced at G8 |
| Negative results | findings that a term adds nothing, or that a table is unusable, are reportable results and must not be dropped for tidiness | **READY** as policy |

---

# 3. Manuscript claim hierarchy

Every future quantitative manuscript claim must be classifiable into exactly
one level. The hierarchy describes **evidence**, not people or tasks, and is
never used to score either.

| Level | Meaning | Admissible language |
| --- | --- | --- |
| **A** | Direct supported result: accepted task output plus reproducible tracked evidence | "we measure", "we observe" |
| **B** | Model-conditional: an exact consequence, conditional on an explicitly stated model form | "under the form ..., it follows that" |
| **C** | Semi-synthetic calibration: numerical behaviour supported primarily by organizer-labelled semi-synthetic or generated data | "calibrated on ...", "recovers the supplied mechanism" |
| **D** | Extrapolation: evaluation outside the identifying support or validity region | "extrapolating beyond ..., subject to" |
| **E** | Unresolved / diagnostic only: useful for debugging or interpretation, not a conclusion | belongs in an appendix or a limitation, not a result |

Rules: a Level B statement must name its form in the same sentence; a Level C
number may never be written with Level A language; a Level D number always
carries its distance from the validity box; a Level E item is not a manuscript
conclusion.

---

# 4. Figure and table inventory

**No final figure is generated at this stage**, and no plot type is locked
before its producing task is accepted. Provenance class and uncertainty
requirements are fixed here so a later figure cannot quietly drop them.

| ID | Q | Purpose | Producer | Source | Dependency | Provenance | Uncertainty shown | Destination | Readiness |
| --- | --- | --- | --- | --- | --- | --- | :--: | --- | --- |
| T1 | Q1 | The 22-indicator contract and directions | T-007 | `q1-scalarization-contract.md` | none | observed contract | no | 04 preprocessing | **READY** |
| F1 | Q1 | Domain quality with intervals | T-007 | IF1 | G1 | per producer | **yes** | 05-1 | PENDING REVIEW |
| F2 | Q1 | Indicator conflict / stability summary | T-007 | T-007 | G1 | per producer | **yes** | 05-1 | PENDING REVIEW |
| F3 | Q1 | Mixture response / domain influence | T-007 | IF2 | G1 | per producer | **yes** | 05-1 | PENDING REVIEW |
| T2 | Q2 | Classic fit, parameters and validation | T-008 | `q2-classic-fit.md` | none | observed + diagnostic | **yes** | 05-2 | **READY** |
| T3 | Q2 | Uncertainty across interval families | T-008 | T-008 checkpoint | G2 | observed | **yes** | 05-2 / 06 | PENDING REVIEW |
| F4 | Q2 | Quality-aware analysis | T-008 | T-008 | G2 | **only if a law is adopted** | **yes** | 05-2 | **BLOCKED** |
| F5 | Q2 | Substitution / elasticity | T-008 | T-008 | G2 | Level B or C only | **yes** | 05-2 | **BLOCKED** |
| F6 | Q3 | Optimal allocation vs compute budget | T-010 | T-010 | G2, G3 | model-conditional | **yes** | 05-3 | NOT STARTED |
| F7 | Q3 | Budget share / transition diagram | T-010 | T-010 | G3 | model-conditional | **yes** | 05-3 | NOT STARTED |
| F8 | Q3 | Sensitivity across quality-cost functions | T-010 | T-010 | G3 | sensitivity | **yes** | 05-3 / 06 | NOT STARTED |
| T4 | Q4 | Detailed-task reconciliation | T-009 | `q4-c8-reconciliation.md` | G4 | observed, **partial (4/6)** | must show which dimensions are quarantined | 04 / 08 | PENDING REVIEW |
| F9 | Q4 | Historical benchmark frontier | T-011 | T-011 | G4, G5 | observed | **yes** | 05-4 | NOT STARTED |
| F10 | Q4 | Scale / non-scale decomposition | T-011 | T-011 | G5 | model-conditional | **yes** | 05-4 | NOT STARTED |
| F11 | Q4 | Forecast band | T-011 | IF4 | G5 | Level D | **yes, incl. bridge error** | 05-4 | **BLOCKED** |
| T5 | Q4 | Detailed-task heterogeneity | T-011 | T-011 | G4 | observed | **yes** | 05-4 / 08 | NOT STARTED, include only if justified |

Compactness rule: an item earns its place only if it supports a claim in the
evidence map. Items whose claim is `BLOCKED` are not drawn.

---

# 5. Manuscript section readiness

Classification of every section as it stands on accepted `main`.

| Section | Current state | Evidence owner | Eligible for final writing when |
| --- | --- | --- | --- |
| 00 abstract | STRUCTURAL PLACEHOLDER | M1 | **all four questions have accepted results** — last thing written |
| 01 restatement | STRUCTURAL PLACEHOLDER | M1 | any time; no scientific evidence needed |
| 02 analysis | STRUCTURAL PLACEHOLDER | M1 | after all four approaches are fixed |
| 03 assumptions | STRUCTURAL PLACEHOLDER | M1 | assumptions may be drafted early, finalized with the models |
| 04 preprocessing | STRUCTURAL PLACEHOLDER | M2 (Q1 contract), M3 (panel) | partially eligible now: **T1 only**. T4 needs G4 — its reconciliation is partial on `main` |
| 05-1 Q1 | STRUCTURAL PLACEHOLDER | M2 | **after T-007 review (G1)** |
| 05-2 Q2 | STRUCTURAL PLACEHOLDER | M1 | classic content after G2 review; generalized content only if a law is adopted |
| 05-3 Q3 | STRUCTURAL PLACEHOLDER | M2 | **after T-010 (G3)**, which needs final IF3 |
| 05-4 Q4 | STRUCTURAL PLACEHOLDER | M3 | **after T-011 (G5)** |
| 06 validation | STRUCTURAL PLACEHOLDER | M1 | after G8/G9; must separate interpolation, observed validation, semi-synthetic calibration and extrapolation |
| 07 evaluation | STRUCTURAL PLACEHOLDER | M1 | after all model sections |
| 08 appendix | SAFE GENERIC PROSE | M1 | any time; currently points at `src/` and `scripts/` |

Every section is a placeholder. **No section currently contains accepted
scientific content, and none is in a `PREMATURE / MUST NOT FINALIZE YET` state,
because none has been written.** The risk this table guards against is the
opposite one: writing them too early.

## Two structural defects found in the skeleton

Recorded here rather than fixed: `paper/sections/` is **not** an allowed path
for this stage.

1. **`00-abstract.tex` enumerates three problems** (`针对问题一/二/三`) while
   the problem has four. T-014 added the Q4 model section but did not touch the
   abstract template.
2. **`02-analysis.tex` has three subsections** (`问题一/二/三的分析`), missing
   the Q4 analysis subsection, for the same reason.

Both are template staleness, not scientific errors. They must be corrected
before the corresponding sections are written; owner M1, under a later task.

---

# 6. Final acceptance gates for T-012

Final integration must not begin or close until every applicable gate passes.

| Gate | Requirement | Owner | Evidence | Pass condition | Current state |
| --- | --- | --- | --- | --- | --- |
| **G1** | T-007 accepted | M2, reviewed by M1 | `reviews/T-007/HANDOVER.md`; IF1 + IF2 | both objects `.validate()`; review accepted | **NOT MET** — T-007 `wip` |
| **G2** | T-008 closed **and unit-consistent** | M1 | `reviews/T-008/HANDOVER.md`; final IF3 or a justified alternative; unit-equivalence check | explicit decision on the generalized law recorded **and G2-U below satisfied** | **NOT MET** — T-008 `wip`, draft PR open |
| **G3** | T-010 accepted | M2 | Q3 optimizer + sensitivity evidence | review accepted; consumes final IF3 | **NOT MET** — `todo` |
| **G4** | T-009 accepted | M3 | panel foundation + reconciliation limits | review accepted | **NOT MET** — `wip` |
| **G5** | T-011 accepted | M3 | decomposition, IF4, forecast, uncertainty | review accepted; IF4 validates | **NOT MET** — `todo` |
| **G6** | Interface validation | M1 | `scripts/selftest_interfaces.py` | every emitted IF `.validate()`s; schema versions compatible | **PARTIAL** — self-test passes; only classic IF3 exists |
| **G7** | Numerical reproduction | M1 | tracked scripts | every manuscript number regenerates from a tracked script | **NOT TESTABLE YET** — no numbers in the manuscript |
| **G8** | Provenance consistency | M1 | evidence map + claim levels | no semi-synthetic or generated result presented as observed | **NOT MET** — pending content |
| **G9** | Uncertainty consistency | M1 | per-claim uncertainty type | every headline estimate uses the type its data justifies | **NOT MET** — pending content |
| **G10** | Manuscript format | M1 | `paper/FORMAT_2026.md`; `scripts/build_paper.ps1` | T-014 rules still pass **after** scientific content is inserted | **PASSES EMPTY** — must be re-run with content |
| **G11** | Public safety | M1 | `scripts/check_public_safe.ps1` | no raw, private or local-only source in Git | **PASSING** |
| **G12** | Final PDF visual audit | M1 | rendered page images | pagination, figures, tables, glyphs, references, identity rules verified by looking | **NOT MET** — pending content |

G10 and G12 deserve emphasis: both currently pass or would pass on an empty
manuscript, which proves nothing about the finished one. They must be re-run
after content exists.

## G2-U — unit-regime acceptance conditions for the final IF3

Added because of the hazard recorded as row 3 of the readiness audit: within Q2
the classic law is fitted in **raw** parameters and tokens while the
quality-bearing tables are handled in **billions**. Both are internally
consistent, so a mix-up survives every existing check and still yields finite,
plausible numbers. These conditions close that path before an IF3 is emitted.

A final or generalized IF3 is **not accepted** unless all four hold.

| # | Condition |
| --: | --- |
| **U1** | Any **externally emitted** IF3 uses **one canonical N/D convention, consistent with the classic IF3: raw parameter count and raw token count.** No exceptions, including for a generalized object. |
| **U2** | An **internal** fit may use billions for numerical conditioning, but its fitted parameters **and** its validity box must be transformed consistently **before emission**. Transforming one and not the other is the specific failure this condition names. |
| **U3** | A **unit-equivalence check** must exist and pass as executable code: prediction at the same *physical* `(N, D, Q)` point must be **invariant** under the internal-billions representation versus the external-raw representation, to a stated numerical tolerance. |
| **U4** | An IF3 whose **parameter units and validity-box units disagree** must be rejected, not repaired at the consumer. |

Notes on scope: U3 describes a check to be written at T-008 closure; it does
not exist yet and is not claimed to. `src/interfaces.py` is **not** changed by
this stage — U1-U4 are acceptance conditions applied at review, not new schema
fields.

Why U3 is phrased as invariance rather than as a unit assertion: a scale factor
applied consistently to `N` and `D` is absorbed by `A` and `B` in the fitted
form, so the *parameters alone* cannot reveal which regime produced them. The
prediction at a fixed physical point can.

---

# 7. Handoff and review order

```
T-007 review ──► T-008 closure ──► T-010 ──┐
                                            ├──► final T-012 integration
T-009 review ──► T-011 ────────────────────┘
```

Explicit non-requirements, so the order is not over-serialized:

* **T-009 is not required to unblock T-008.** T-008 needs reviewed IF1/IF2 from
  T-007, nothing from M3.
* **M3 need not finish before M1 can close T-008**, once reviewed IF1/IF2
  exist.
* **T-010 must not produce scientific conclusions before the final IF3
  exists.** Solver development against analytical fixtures may proceed.
* **T-011 must not treat provisional T-008 output or unreviewed T-009
  artifacts as accepted inputs.**

---

# 8. Reproducibility checklist for final integration

To be executed at final T-012, not now:

1. Clean clone; provision the document class; build the manuscript.
2. Regenerate every tracked results table from its script; require no diff
   beyond line endings.
3. Re-emit every interface object and `.validate()` each.
4. Confirm every manuscript number appears in a tracked artifact, and every
   tracked artifact number is derivable — the check must close from **both**
   directions, since "every number I derived appears in the document" does not
   catch a figure that is wrong in one of two places.
5. Extract numbers out of the built PDF and re-check them against the
   artifacts, including quantities written in Chinese numerals, which a
   digit-shaped pattern will not see.
6. Re-run the format build and inspect every rendered page.
7. Re-run the public-safety gate in both modes.
