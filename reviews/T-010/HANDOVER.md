# T-010 handover

| Field | Value |
| --- | --- |
| Task | T-010 |
| Owner | M2 |
| Status | wip |
| Timestamp | 2026-09-26T12:05:51+08:00 |
| Base | `2ca83455a39128d970ba588108a99ec7b3437a56` |
| HEAD | `fa458f87ce30009329eb2c84cbeec8ce70715502` |
| Branch / PR | `exp/m2-T010-q3-allocation` / Draft PR #17 |

## Scope

T-010 implements a receipt-bound, compute-constrained allocation analysis for the accepted classic raw-parameter/raw-token IF3 law. It derives and validates the semantic-`Q0` baseline N-D allocation over source-supported compute budgets and the observed C7 context grid; it does not introduce a quality-benefit law or make an empirical allocation prescription.

## Completed work

- Added an immutable accepted-classic-IF3 consumer, receipt-bound baseline compute model, raw-N/raw-D validity-box reduction, analytical solver, bounded numerical solver comparison, and uncertainty-evidence guard under `src/alloc/`.
- Added deterministic Q3 source-receipt, canonical-allocation, context-sensitivity, quality-cost-status, self-test, and two-pass reproduction entry points under `scripts/q3_*`.
- Generated the corresponding Q3 tables under `results/tables/q3-*`.
- Resolved a pre-existing local public-safety blocker without changing scientific logic: after proving an untracked recovery archive and a historical Q2 diagnostic were neither staged, declared Q3 artifacts, nor exact T-010 inputs, moved both byte-preservingly to ignored `scratch/T-010/preexisting-untracked/`. Pre- and post-move SHA-256 values and byte counts matched; no tracked file changed.

## Evidence

**Code**

- `src/alloc/classic.py` verifies the immutable classic IF3 bytes and permits only semantic `Q0`.
- `src/alloc/constraint.py` accepts only source-supported budgets, observed contexts, and baseline quality; it enforces `C_total = (6 + eta L_ctx) N D` at `Q0`.
- `src/alloc/validity.py` derives the budget-saturating feasible N interval from the accepted raw-N/raw-D validity box.
- `src/alloc/solver.py` implements the closed-form baseline solution and an independent bounded scalar numerical comparison.
- `src/alloc/uncertainty.py` records the released marginal-only bootstrap evidence without synthesizing joint draws.
- `scripts/q3_source_receipt.py`, `scripts/q3_allocate.py`, `scripts/q3_context_sensitivity.py`, `scripts/q3_quality_cost_sensitivity.py`, `scripts/q3_selftest.py`, and `scripts/q3_reproduce.py` are the reproducible task entry points.

**Regenerable artifacts**

- `results/tables/q3-source-receipt.json` and `results/tables/q3-source-receipt.md`
- `results/tables/q3-allocation.json` and `results/tables/q3-allocation.md`
- `results/tables/q3-context-sensitivity.json` and `results/tables/q3-context-sensitivity.md`
- `results/tables/q3-quality-cost-sensitivity.json` and `results/tables/q3-quality-cost-sensitivity.md`
- `results/tables/q3-reproduction.json` and `results/tables/q3-reproduction.md`

**Commands actually run**

```text
conda run -n modeling-research-2026 --no-capture-output python scripts/q3_selftest.py
# PASS 37 assertions

conda run -n modeling-research-2026 --no-capture-output python scripts/q3_reproduce.py
# two passes identical: True
# LF-only: True
# source inputs unchanged: True
# interfaces unchanged: True

powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PreCommit
# RESULT: PASS (169 files examined)
```

The Q3 self-test and two-pass reproduction preceded the unrelated local safety cleanup and were not rerun merely to address that blocker.

## Key results

The source receipt establishes, in FLOPs,

```text
C_train = 6 N D
C_attn  = eta N D L_ctx, where eta = 0.0002
C_Q     = D [g(Q) - g(Q0)]_+
C_total = D [(6 + eta L_ctx) N + delta_g(Q)] <= C
```

At the sole canonical setting, `Q = Q0`, `delta_g(Q0) = 0` exactly, so quality preprocessing compute and quality share are exactly zero. The accepted classic law is

```text
L(N, D) = E + A N^(-alpha) + B D^(-beta)
```

with raw `N` and raw `D`. At fixed baseline quality and saturated compute, the analytic stationary point is

```text
N* = [alpha A / (beta B)]^(1 / (alpha + beta))
     * (C / kappa)^(beta / (alpha + beta))
D* = C / (kappa N*)
```

where `kappa = 6 + eta L_ctx`. The implementation independently compares that solution with bounded numerical minimization, with self-test relative-difference limits of `1e-10` for N and D and `1e-12` for loss.

For the compact observed `L_ctx = 4096` presentation row, `kappa = 6.8192`, base share is `0.87986861`, attention share is `0.12013139`, and quality share is `0`.

| Budget (FLOPs) | N (raw parameters) | D (raw tokens) | Predicted loss | Validity disposition |
| ---: | ---: | ---: | ---: | --- |
| `1e19` | `2.1520643e8` | `6.8141442e9` | `3.0114367` | interior |
| `1e22` | `4.889903e9` | `2.99893e11` | `2.1475143` | `D_max` active |
| `1e24` | — | — | — | `NO_VALIDITY_BOX_ALLOCATION` |

The full observed C7 grid is `2048`, `4096`, `8192`, `32768`, and `131072` tokens. At `1e19`, every observed context row is interior. At `1e22`, 2048 and 4096 have active `D_max`; 8192, 32768, and 131072 are interior. At `1e24`, every observed context row is unavailable because no point can saturate that source-supported budget inside the accepted validity box.

`L_ctx = 30000` tokens is exactly the base/attention cost-parity identity `6 / eta`; it is not an empirical optimum, transition, critical context length, or optimizer-regime claim.

## Validation

`q3_selftest.py` passed all 37 assertions. Its deliberate mutation and invalid-input coverage checks IF3 byte immutability, receipt gate enforcement, unsupported budget/context rejection, nonbaseline-quality rejection, zero baseline quality compute, budget saturation, cost-share reconciliation, analytical/numerical agreement, validity boundaries, empty-box rejection, and marginal-only uncertainty handling.

`q3_reproduce.py` generated all declared tables twice. Its receipt records byte-identical passes, LF-only generated artifacts, unchanged source inputs (1,977 files), and unchanged IF1/IF2/IF3 interface snapshots. The accepted classic IF3 SHA-256 is `720efea859d3be3b39ac2ee1976f8adaf7a31b8b5b1a71eb72e8ee8f987c8514`.

After the controlled relocation of unrelated local files, the actual PreCommit public-safety check passed with 169 examined files. No safety rule, ignore rule, accepted interface, source input, or Q3 scientific output was modified to obtain that pass.

## Interfaces and downstream impact

T-010 consumes accepted interfaces without regenerating them:

| Interface | Accepted SHA-256 | T-010 use and boundary |
| --- | --- | --- |
| IF1 | `b8ec99ca38f2e466b427fd1a7d88858048924cc590bbe881a966d141eb9bdeb8` | Not substituted for `Q0`; its partial relative proxy and unmapped mixture mass are not imputed. |
| IF2 | `9f2a83da45633858822c8416b5fa70a9537a06b07ac9056e50d871492b16ff91` | Not consumed by the canonical allocation; any retained use is limited to its accepted 1M scope. |
| classic IF3 | `720efea859d3be3b39ac2ee1976f8adaf7a31b8b5b1a71eb72e8ee8f987c8514` | Sole canonical loss law; raw-N/raw-D validity box is enforced. Its `Q = [1, 1]` interval is a no-quality sentinel, not IF1 quality one. |

T-012 may consume only these model-conditional and validity-box-qualified claims:

1. the source-supported baseline compute formula, budgets, observed context grid, and cost-share identity;
2. the fixed-`Q0` analytical allocation derivation and bounded numerical agreement;
3. canonical allocation outcomes within the accepted classic IF3 raw-N/raw-D validity box, including explicit boundary and unavailable classifications;
4. the observed-grid context sensitivity classifications without an interior context-optimum claim;
5. the fact that canonical baseline quality compute is exactly zero and that nonbaseline numerical quality-cost analysis is blocked pending a provenance-backed global numeric `Q0`;
6. the absence of allocation uncertainty bands because only marginal IF3 bootstrap intervals, not joint parameter vectors, were released.

T-012 must not present these results as empirical allocation advice, infer a cross-scale quality benefit, infer an interior context optimum, extend IF2 beyond its 1M scope, substitute IF1 for `Q0`, or treat unavailable/out-of-box points as canonical allocations.

## Negative results and rejected alternatives

- The accepted classic IF3 law contains no quality-loss term. Nonbaseline quality-cost evaluation is therefore `BLOCKED_UNTIL_Q0_DECLARED`; a numerical global `Q0` was not invented from either listed source option.
- Cross-scale quality-benefit modeling is `PROHIBITED`: the specified `g(Q)` families are cost expressions, not an accepted loss-benefit model.
- B7/B8 are unused. IF1 quality is not fed into any B7 quality exponent, and IF2 is not transferred across scales.
- The `1e24` source-supported budget has no budget-saturating allocation inside the accepted raw-N/raw-D box; it is retained as `NO_VALIDITY_BOX_ALLOCATION`, not clipped or extrapolated.

## Known limitations and open risks

The canonical results are conditional on the accepted classic IF3 law, source receipt, source-supported inputs, and its raw-N/raw-D validity box; they are not direct observations of real-world training allocation behavior. The IF3 provenance notes limit the interpretation of its narrow bootstrap intervals, and only marginal bootstrap intervals were released. No joint allocation uncertainty band is defensible without complete joint bootstrap parameter vectors.

No global numeric `Q0` is established. Consequently, no numerical nonbaseline quality-cost scenario or quality optimization occurred. The quality conclusion is limited to the accepted model's lack of an identified benefit term; it does not assert that data quality is unimportant in reality.

The 4096-token row is an observed compact presentation row, not a preferred context setting. The 30000-token identity is cost parity only. Context results are evaluated only on the observed C7 grid and do not establish a continuous threshold or transition.

## Next action

M1 should review this evidence package and the future Draft PR. T-010 remains `wip`, unmerged, and under supervisory review; no T-012 work or task-status change is authorized by this handover.
