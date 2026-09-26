# T-010 handover

| Field | Value |
| --- | --- |
| Task | T-010 — Q3 compute-constrained resource optimization |
| Owner | M4 (execution transferred from M2 by T-010 v3) |
| Status | wip — awaiting supervisory review |
| Timestamp | 2026-09-27T00:38:50+08:00 |
| Specification | `worklog/specs/T-010.md` v1 (scientific), v2 (authoritative correction), v3 (ownership / controlled draft handoff) |
| Synchronized main | `583b8db6660ac852e62642e7f9c38f1773b9a528` (unchanged at the last fetch before this package) |
| Branch | `exp/m4-T010-q3-allocation` (replacement Draft PR; number reported after creation, not in this file) |

## Four states, kept apart

| State | Reference | Standing |
| --- | --- | --- |
| Historical M2 checkpoint | Draft PR #17 head `2047c336bf7ac75bf4020b3d79806cc9249bc6b1` | Reviewed v1 checkpoint; untouched, Draft, unmerged |
| Frozen unreviewed M2 draft | local package `scratch/t010-m2-takeover/` (M2 local HEAD `30143c35d69ca4b2dd363dc1a07c18560210e615`) | Implementation material only; no result, test or conclusion inherited |
| M4-reviewed implementation | code `37803c5`, regenerated tables `4a39d6e`, on base `4558cd8` (= `2047c33` + normal merge of main `583b8db`) | The evidence this package describes |
| Final live branch head | reported separately after push | Includes this package; not self-referenced here |

## Takeover record

The four package files were verified against the M2-reported SHA-256 values and the manifest byte counts:

| File | SHA-256 | Bytes |
| --- | --- | ---: |
| `STATUS.txt` | `175a6f0208b298b05ae7985d74032ec9e0e0a01418b06752c2077b4ab443296e` | 5586 |
| `m2-local-head.bundle` | `5cf38f121354fe5f0c7ca7ab3fe0bf39baaa22807a4edfa2577335eed3a5ed27` | 749972 |
| `m2-working-tree.patch` | `93ce66a7772384f851a809dc6a0dd16d73531931be1bfc3eca18932c0ae27c2c` | 165545 |
| `m2-untracked-owned.tar` | `a5ea7e63dfae29395790143b4e6bf2eb241effc4238407b7461358af7787b7e0` | 286720 |

`MANIFEST.sha256` (itself `9f2ed337f045bc376a10f53aab1d5156a0d8760395bf5fc5db1593e672454a50`) was read as a receipt; all ten TAR member hashes in it matched the extracted files. The package was already at `scratch/t010-m2-takeover/` and no root-level `t010-m2-takeover/` existed when M4 started, so M4 did not perform the relocation and has no pre-move observation; the hashes above were taken at the destination (see Deviations). The bundle was kept as a forensic receipt and not imported. The package is not in Git.

Before import: all 21 patch targets and all 10 TAR members were inside T-010-owned paths (`src/alloc/`, `scripts/q3_*`, `results/tables/q3-*`); no mode, rename, binary, absolute-path, `..`, symlink, `.claude/`, `MANIFEST.txt`, `scripts/_inspect_docx.py`, `docs_local/`, `data_local/` or scratch entry appeared; `git apply --check` passed; no TAR target pre-existed. The patch applied cleanly and the TAR extracted exactly those ten files.

### Disposition of the imported draft

| Imported path | Disposition |
| --- | --- |
| `src/alloc/validity.py`, core of `src/alloc/solver.py` | **Retained after independent verification**: the `D_best(N) = min(D_max, C/(kappa N))` reduction and its candidate set are complete (reduced loss strictly decreasing on the `D_max` branch, strictly convex in `log N` when saturated). Labels, residual and the numerical comparator were corrected. |
| `src/alloc/classic.py` | **Retained** (IF3 routed through the unified hash/contract loader); docstrings widened to sensitivity laws. |
| `src/alloc/receipts.py` | **Corrected**: the draft recorded paths through `os.path.normcase`, which lowercases on Windows (`c_efficiency_evolution`) and made artifacts platform-dependent; its IF1/IF2/B8 "guards" were helpers that no production path could trigger. Replaced by an allowlist with recorded roles, a lexical PDF rule, and identity-only IF1/IF2 receipts. |
| `src/alloc/robustness.py`, `src/alloc/loo.py` | **Corrected**: the draft built each LOO fit by cloning the accepted IF3 object, so a modified fit kept the accepted path and SHA-256. Replaced by a separate `SensitivityClassicLaw`; published precision and the published full fit are now captured. |
| `src/alloc/regime.py`, `scripts/q3_regime_analysis.py` | **Corrected**: the draft bypassed the budget guard with `dataclasses.replace`, analysed candidates below the declared span (`C_min`, `N_min` onset) as transitions, and its table hid the active set (`SATURATING -> SATURATING`). |
| `src/alloc/constraint.py`, `src/alloc/__init__.py` | **Corrected**: receipt values must equal their DOCX verification; explicit continuation constructor; cost shares with explicit denominators. |
| `scripts/q3_source_receipt.py` | **Rewritten**: the draft checked flattened formula-name anchors while every numeric value was hard-coded. |
| `scripts/q3_reproduce.py`, `scripts/q3_selftest.py` | **Rewritten**: runtime pins were recorded but not enforced; "PDF consumption ZERO" was asserted, not measured; 92 assertions left several v2 items untested. |
| `scripts/q3_allocate.py`, `scripts/q3_context_sensitivity.py`, `scripts/q3_quality_cost_sensitivity.py`, `scripts/q3_loo_robustness.py` | **Corrected / rewritten** as described under Key results. |
| all 14 imported `results/tables/q3-*` files | **Discarded as evidence**; every table was regenerated from M4's code. |

New in M4's implementation: `src/alloc/inputguard.py`, `sourcedocx.py`, `quality.py`, `provenance.py`, `report.py`, `scripts/q3_provenance_ledger.py`, `results/tables/q3-provenance-ledger.*`.

## Evidence

**Code**: `src/alloc/` and `scripts/q3_*.py`.

**Regenerable artifacts** (all from `scripts/q3_reproduce.py`):
`results/tables/q3-source-receipt.*`, `q3-allocation.*`, `q3-context-sensitivity.*`, `q3-regime-thresholds.*`, `q3-quality-cost-sensitivity.*`, `q3-loo-robustness.*`, `q3-provenance-ledger.*`, `q3-reproduction.*`.

**Commands actually run** (at `4a39d6e`, runtime Python 3.11.16, NumPy 2.4.6, SciPy 1.17.1, pandas 3.0.6, PyYAML 6.0.3):

```text
conda run -n modeling-research-2026 --no-capture-output python scripts/q3_reproduce.py
# two passes identical: True; LF-only: True; inputs unchanged: True;
# interfaces unchanged: True; guard denials: 0; runtime matches pins: True
conda run -n modeling-research-2026 --no-capture-output python scripts/q3_selftest.py
# PASS 170 assertions
conda run -n modeling-research-2026 --no-capture-output python scripts/selftest_interfaces.py
# RESULT: PASS (21 assertions)
git diff --check
# clean
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PreCommit
# RESULT: PASS (before each commit)
```

## Key results

All results are model-conditional consequences of the accepted classic IF3 law inside its raw-N/raw-D validity box, at the semantic baseline `Q = Q0`; none is an observation or developer guidance.

**Corrected budget inequality.** The problem solved is `min L(N, D)` subject to `kappa N D <= C`, `N_min <= N <= N_max`, `D_min <= D <= D_max`, `kappa = 6 + eta L_ctx`. With `C_min = kappa N_min D_min` and `C_box = kappa N_max D_max`: no feasible point below `C_min`; the optimum saturates the budget for `C_min <= C < C_box`; at `C_box` it is the saturating upper corner; above `C_box` it is `(N_max, D_max)` with unused budget `C - C_box`. The closed form is used only where the stationary point lies inside the box ([q3-allocation.md](../../results/tables/q3-allocation.md)).

**Corrected 1e24 disposition.** At every observed context, `1e24` gives `SLACK:N_max+D_max`: N = 1.1965825e10, D = 2.99893e11, predicted loss 2.0933829, spent `C_box` (2.300e22 at 2048 to 1.156e23 at 131072 tokens), utilization 0.0230–0.1156. The former `NO_VALIDITY_BOX_ALLOCATION` disposition is withdrawn. This does not identify an optimum beyond the box or a physical limit on useful compute; the remainder is not extrapolated. At `L_ctx = 4096`: `1e19` is `SATURATED:interior` (N 2.152e8, D 6.814e9), `1e22` is `SATURATED:D_max` (N 4.890e9). Base and attention shares of spent compute are `6/kappa` and `eta L_ctx/kappa` at every budget; fractions of the budget differ from them only in slack rows.

**Structural regimes.** `R(C)` = `INFEASIBLE` below `C_min`, otherwise (saturation status, complete active bound set); a structural transition is a change of `R`, equivalently a jump of `d log N*/d log C` and `d log D*/d log C`. Candidates (`C_min`, `C_box`, stationary path reaching each bound) are retained only when the constrained optimizer changes regime between probes at relative `-/+1e-6`; continuation is confined to the declared span `[1e19, 1e24]`. At every observed context the span holds exactly two transitions ([q3-regime-thresholds.md](../../results/tables/q3-regime-thresholds.md)):

| L_ctx | interior -> D_max (C, FLOPs) | D_max -> slack at C_box (C, FLOPs) |
| ---: | ---: | ---: |
| 2048 | 9.3260067e21 | 2.3000639e22 |
| 4096 | 9.9219772e21 | 2.4470475e22 |
| 8192 | 1.1113918e22 | 2.7410148e22 |
| 32768 | 1.8265564e22 | 4.5048181e22 |
| 131072 | 4.6872147e22 | 1.1560032e23 |

Elasticities: interior 0.451526 (N) / 0.548474 (D); `D_max` regime 1 / 0; slack corner 0 / 0; numerical checks agree within 1e-6. `C_min` (6.06e16–3.05e17) and the `N_min` exit (7.95e17–3.99e18) lie below `1e19` and are recorded, not analysed; every budget in the span is feasible. The first transition is a validity-boundary active-set transition, the second the onset of slack at the validity ceiling; the span ends are analysis/source-support boundaries; **no empirical physical transition is established**. `L_ctx = 6/eta = 30000` tokens is base/attention cost parity only. At `1e22`, the observed contexts 4096 and 8192 bracket the `D_max`-to-interior change; no continuous context threshold is identified and the C7 grid is not extended.

**LOO robustness** ([q3-loo-robustness.md](../../results/tables/q3-loo-robustness.md)) — *leave-one-trajectory-out robustness at published parameter precision*. Source `results/tables/q2-uncertainty-robustness.md`, SHA-256 `b169f358d25c8864fad96573a6c1545f703efd971c27982a2611f8c68f387f43`, eight complete vectors printed with `format(x, ".6g")`; no accepted full-precision LOO object exists. Where N*/D* are free, LOO relative spreads are 1.6e-4 to 3.8e-4 and resolved at published precision; under an active bound they are fixed. Predicted-loss spreads (3.1e-6 to 1.8e-5) are **not resolved**: six-digit rounding of one vector moves the loss by as much (the nominal and the published full fit already differ by about 3.5e-6). The `D_max` threshold's LOO spread is 7.0e-4 relative and resolved; no LOO range contains a representative budget, so all fits agree on every primary-grid regime. These are robustness ranges, not confidence, bootstrap or posterior intervals; bootstrap marginals and profile ratios are kept separate and not propagated; the B1 generator-recovery caveat applies.

**Raw quality-cost families** ([q3-quality-cost-sensitivity.md](../../results/tables/q3-quality-cost-sensitivity.md)). On `Q in (0, 1]`, in FLOPs per token, each pair crosses exactly once: exponential/logarithmic at Q = 5.0277e-4, exponential/power at 0.36638, power/logarithmic at 0.98855. Ascending order: `(0, 5.03e-4)` power < logarithmic < exponential; `(5.03e-4, 0.366)` power < exponential < logarithmic; `(0.366, 0.989)` exponential < power < logarithmic; `(0.989, 1]` exponential < logarithmic < power. Counts are exact by analytic monotone-piece argument (not a grid); `Q -> 0+` values are analytic limits.

**Nonbaseline quality.** Nonbaseline `D [g(Q) - g(Q0)]_+` allocation remains `BLOCKED_UNTIL_Q0_DECLARED`; nontrivial Q optimization is unsupported by classic IF3; cross-scale quality benefit is prohibited. Baseline quality compute is exactly zero. This is a property of the accepted model, not a claim that data quality is unimportant.

## Sources, interfaces and source security

**Authorized-source ledger.** [q3-source-receipt.md](../../results/tables/q3-source-receipt.md) verifies 30 statements at exact DOCX locators with OMML exponent structure preserved: budget inequality `w:body/w:p[35]`; budgets `w:body/w:p[29]/m:oMath[7..9]`; coefficient 6 `w:body/w:p[30]/m:oMath[1]`; eta `w:body/w:p[34]/m:oMath[2]`; g(Q) families `w:body/w:p[49..51]`; Q domain `w:body/w:p[31]/m:oMath[3]`; Q0 source semantics `w:body/w:p[31]`; exogenous context `w:body/w:p[29]` and `[45]`; structural-transition requirement `w:body/w:p[35]`. The DOCX SHA-256 `89f1b27c…3b6a7` is checked first. No canonical value contradicted the specification. [q3-provenance-ledger.md](../../results/tables/q3-provenance-ledger.md) itemizes 42 load-bearing items (18 VERIFIED, 14 DERIVED, 10 MODEL_CONDITIONAL, 0 UNVERIFIED, 0 PDF-dependent); the generator refuses any PDF-, screenshot-, transcription- or AI-intermediate-only item.

**Narrowed input inventory** (the complete allowlist; eight files):
`docs_local/problem-f/source/problem_statement.docx`; `data_local/problem-f/raw/real_attachments/C_efficiency_evolution/model_architecture_metadata.csv` (`ee24622c…12ffc`); `data_local/problem-f/raw/real_attachments/source_manifest.json` (`34e81dab…323db`); `data_local/problem-f/raw/attachment_sha256_manifest.tsv` (T-006 intake record, which independently matches the C7 and manifest hashes); the three accepted interfaces; `results/tables/q2-uncertainty-robustness.md`. The historical 1,977-file snapshot of the reviewed checkpoint was not revalidated and is not carried forward.

**Interfaces.** IF1 `b8ec99ca38f2e466b427fd1a7d88858048924cc590bbe881a966d141eb9bdeb8`, IF2 `9f2a83da45633858822c8416b5fa70a9537a06b07ac9056e50d871492b16ff91`, IF3 `720efea859d3be3b39ac2ee1976f8adaf7a31b8b5b1a71eb72e8ee8f987c8514`: accepted bytes, shared contracts and IF2's 1M-only scope are verified before and after reproduction and cross-checked against `q1-if1-summary.md`, `q1-if2-summary.md` and `q2-final-closure.md`. IF1 (11 of 17 mixture domains unmapped) and IF2 are released to Q3 as identity receipts whose content is inaccessible, so neither can become a quality coordinate, a canonical-loss input or a cross-scale coefficient. IF3's `Q = [1, 1]` remains a no-quality sentinel. B8 is not an input.

**Source security.** Every generator runs under an audit-hook guard that raises before the operating system opens any `*.pdf` (including for hashing), any non-allowlisted local file, or any input for writing, and before any listing under `data_local/` or `docs_local/`; reproduction recorded 0 denials and only allowlisted reads, and the self-test proves each refusal with harmless temporary fixtures. Neither `data_description.original.pdf` nor `data_description.sanitized.m2.pdf` was opened, parsed, hashed or otherwise consumed by M4 or by any T-010 code in this execution, and M4 did not list the directories that hold them. No load-bearing dependency on either PDF was found. **Reported operational deviation:** the user reports that M2 manually opened the original PDF in an editor. M4 has no further facts about that event and does not infer text extraction, AI ingestion or reliance from it; because every load-bearing value is independently traced to authorized sources, it remains an operational deviation only.

## Validation

`scripts/q3_selftest.py` (170 assertions) exercises the production boundaries: hash, contract, scope and missing/altered-interface rejection for IF1/IF2/IF3; identity-only IF1/IF2; the IF3 sentinel and numeric-Q0 rejection (including `1.0` and `True`); DOCX value verification and three mutated-DOCX fixtures; twelve forbidden receipt mutations; allowlist and B8 rejection before any filesystem access; guard refusals in child processes (PDF open and hash, B8, directory listing and scanning, write intent) and the guarded authorized workflow; closed form against `src/scaling` and a Brent root of the stationary condition (1e-12); independent numerical search at every primary budget; single-bound, corner, infeasible and slack fixtures; feasibility and non-increasing minimum loss over the span; production and fixture transitions with both neighbouring regimes; LOO parsing, precision and non-CI classification; exact raw-g crossings including a two-root and a near-`Q = 1` fixture; ledger rejection of PDF, screenshot, AI-intermediate, absolute-path and UNVERIFIED provenance.

The checks were shown to fail on purpose. A scratch mutation pass injected fifteen production defects into the committed code one at a time, ran the self-test, and restored each file with its SHA-256 re-verified. Fourteen were detected: guard disabled (7 failing checks), IF1/IF2 content released (2), the old equality-only high-budget rule (self-test aborts, exit 1), PDF rule narrowed (2), kink candidate dropped (10), IF2 scope skipped (1), ledger source check disabled (5), eta, coefficient and verification-status cross-checks removed (1 each), DOCX value comparison disabled (1), regime-change test forced true (1), LOO format check disabled (1), near-zero bracketing removed (4). The survivor, dropping the ledger's forbidden-kind list, is still rejected by its allowed-kind list, by design. Earlier passes had exposed two undetected mutations and one test that could not isolate its target; the tests were sharpened before commit. Committed T-010 blobs were checked byte-for-byte to be LF-only, and all fourteen committed artifacts match the reproduction receipt.

## Interfaces and downstream impact — T-012 claim boundary

T-012 **may** consume, as model-conditional statements with their sources:

1. the verified compute model `C_total = D[(6 + eta L_ctx) N + [g(Q) - g(Q0)]_+] <= C`, `eta = 2e-4`, the three representative budgets, the observed C7 grid and their DOCX/C7 locators;
2. the baseline allocations above, including the corrected `1e24` upper-corner-with-slack disposition and the explicit denominators of shares and fractions;
3. the regime definition, the two in-span transitions per context with the values in the table, their categories and elasticities, and the 7.0e-4 LOO spread of the `D_max` threshold;
4. the LOO robustness ranges of N* and D*, labelled as above, and the statement that loss ranges are not resolved at published precision;
5. the raw g(Q) crossings and interval orderings on `(0, 1]` as a sensitivity analysis of cost expressions;
6. the quality-lane status: zero baseline quality compute, nonbaseline allocation blocked, Q optimization unsupported, cross-scale benefit prohibited;
7. `L_ctx = 30000` as a cost-parity identity only.

T-012 **must not**: present any result as empirical or as guidance for real training, or use causal language; claim an optimum beyond the box, a physical limit on useful compute, or a use for the unused budget; call either transition an empirical physical transition; call 30000 tokens an optimal, critical or transition context; infer a continuous context threshold from the observed bracket; read LOO ranges as confidence, bootstrap or posterior intervals, synthesize joint bootstrap draws, turn profile ratios into allocation limits, or claim loss resolution beyond published precision; use IF1 as `Q0` or impute unmapped quality; use IF2 outside 1M or in any loss; use B8; order `delta_g` by raw g or claim any Q optimum; claim data quality is unimportant; or cite either PDF.

## Deviations from plan

- The launcher expected the package at the repository root; it was already at `scratch/t010-m2-takeover/` when M4 began. Hashes were verified in place; the move was not performed or observed by M4.
- T-010 v2 requests executable enforcement of IF1/IF2/B8 restrictions. M4 enforces them structurally (identity-only receipts, allowlist, audit-hook guard) and removed the draft's guard helpers, which no production path could trigger.
- Observed outside T-010's paths, not changed: `src/paths.require()` raises `ValueError` rather than `RawDataMissing` for a missing path outside the repository root (its message calls `relative_to`). T-010 fixture loading checks existence itself.

## Known limitations and open risks

- Every allocation, threshold and range is conditional on the accepted classic IF3, whose fit is a generator recovery on B1; the validity-box transitions describe where the law was identified, not how training behaves beyond it.
- LOO propagation is limited to published six-digit precision; loss robustness is not resolved at that precision.
- No numeric `Q0` exists, so no nonbaseline quality scenario was evaluated; the quality conclusion is a property of the accepted model.
- Context results are confined to five observed C7 values; a regime change between them is bracketed, not located.
- The guard covers file access from Python in Q3 processes; it is not an operating-system sandbox.

## Next action

M1: supervisory review of the replacement Draft PR from `exp/m4-T010-q3-allocation`. T-010 remains `wip` and unmerged; PR #17 stays Draft and unmerged as the historical M2 checkpoint; T-012 is not started.
