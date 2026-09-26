# T-010 handover

| Field | Value |
| --- | --- |
| Task | T-010 — Q3 compute-constrained resource optimization |
| Owner | M4 (execution transferred from M2 by T-010 v3) |
| Status | wip — awaiting supervisory review |
| Timestamp | 2026-09-27T03:11:00+08:00 |
| Specification | `worklog/specs/T-010.md` v1 (scientific), v2 (authoritative correction), v3 (ownership / controlled draft handoff); remediation of the supervisory re-audit is an L1 instruction (not archived) |
| Synchronized main | `583b8db6660ac852e62642e7f9c38f1773b9a528` (unchanged at the last fetch before this package) |
| Branch | `exp/m4-T010-q3-allocation`; no replacement PR yet (the supervisor audits the pushed head directly) |
| Scientific validation candidate | `21cc4cd0ced7a7d2aec6ffc1cec7be7b0ba15de2` (all code and artifacts; this package is the receipt commit after it; supersedes candidate `f262ceb`) |

## Four states, kept apart

| State | Reference | Standing |
| --- | --- | --- |
| Historical M2 checkpoint | Draft PR #17 head `2047c336bf7ac75bf4020b3d79806cc9249bc6b1` | Reviewed v1 checkpoint; untouched, Draft, unmerged |
| Frozen unreviewed M2 draft | local package `scratch/t010-m2-takeover/` (M2 local HEAD `30143c35d69ca4b2dd363dc1a07c18560210e615`) | Implementation material only; no result, test or conclusion inherited |
| M4-reviewed implementation | code `37803c5`, tables `4a39d6e`, package `b589f22`, on base `4558cd8` (= `2047c33` + normal merge of main `583b8db`) | Audited; blocked on four v2-compliance findings |
| M4 remediation | `c6d17d0`, `5f5060f`, `ae5427f`, `17aca9f`, `21138f6`, candidate `f262ceb`, package `68f8905` | Audited; two validation defects found |
| M4 validation correction | `ef0369d`, candidate `21cc4cd` | The evidence this package describes |
| Final live branch head | reported separately after push | Includes this package; not self-referenced here |

## Supervisory re-audit of `b589f22`: findings and dispositions

| # | Finding | Disposition | Evidence |
| --- | --- | --- | --- |
| 1 | The source receipt authenticated itself: eta, its `verified_value` and parity could be forged together, and `262144` added to the context grid could reach the solver | **CLOSED** (`5f5060f`) | `load_source_receipt`, used by every allocation script, now re-verifies the DOCX and re-derives the C7 grid itself; forgeries A1-A8 are rejected by the self-test and, through the real scripts, by probes P01-P10 of [q3-mutation-validation.md](../../results/tables/q3-mutation-validation.md); mutants M10-M12 restore the old behaviour and are killed |
| 2 | The LOO receipt recorded `ac21054b…`, a hash of the CRLF working copy, as the Git blob id | **CLOSED** (`5f5060f`) | Now bound to Git blob `d32cdfd87f5fea9ac56f68aef0f9fc8d574c2020` of accepted T-008 commit `b18967c76395ab7d9a336f957e74cd6b4e8d3a99`, obtained with `git rev-parse b18967c…:results/tables/q2-uncertainty-robustness.md`; vectors are parsed from the Git object; probe P13 and mutants M13-M15 |
| 3 | The mutation validation and PrePush evidence were prose only | **CLOSED** (`ae5427f`, `17aca9f`, `21138f6`; corrected by `ef0369d`, candidate `21cc4cd`) | `scripts/q3_mutation_validation.py` produces [q3-mutation-validation.md](../../results/tables/q3-mutation-validation.md) inside the two-pass reproduction; the PrePush receipts are under Gate record below |
| 4 | The ledger stated "saturation holds only for C < C_box" | **CLOSED** (`c6d17d0`) | Ledger item S1 and `q3-allocation.md` now state saturation for `C_min <= C <= C_box`, the saturating upper corner at `C = C_box`, and slack above; an artifact check and mutant M22 guard it |

**No core scientific number changed.** Compared with `b589f22` as parsed JSON, the allocation rows, context rows and brackets, regime analyses, raw-g analysis, LOO rows, summaries, thresholds and parameter vectors, source-verification records and receipt terms are all identical; only the provenance identities (`loo_evidence`, `authorized_inputs`), the ledger wording and the new validation artifacts changed.

## Validation correction (re-check of `68f8905`)

| # | Defect | Disposition | Evidence |
| --- | --- | --- | --- |
| V1 | M17 (DOCX whole-file SHA-256 pin skipped) was declared a redundant survivor, but its only detector, probe P12, fed the allocation consumer an old receipt; the receipt generator uses the same verifier and, without the pin, records the changed DOCX hash, so the consumer's receipt/DOCX hash comparison is not an independent second anchor | **CLOSED** (`ef0369d`) | New probe P14 feeds a value-preserving DOCX byte change to `scripts/q3_source_receipt.py` itself: unmutated, it fails closed with `SourceVerificationError` before touching its outputs; with the M17 mutation it accepts the input and M17 is now KILLED. P12 is kept and described as receipt/source consistency. M18 stays killed via P12; M08 is the only redundant survivor, backed by the independent allowed-kind list |
| V2 | `run_mutant` did not fail closed: a redundant survivor passed on any "not killed" result (including exit 1 with no report), and probe-detected mutants discarded the probe's exception, output-integrity and restoration evidence | **CLOSED** (`ef0369d`) | A self-test survivor now needs exit 0, no failed check, a complete successful report of the baseline size and verified restoration. Probe evidence is classified as `ACCEPTED`, `REJECTED_AS_DECLARED` (exact exception, outputs unchanged), `UNEXPECTED_REJECTION` or `INTEGRITY_FAILURE`, and kept in full in each mutant record; consumer outputs as well as inputs are restored and verified. 20 runner self-checks, recorded in the artifact, feed synthetic records through the same functions; the exit-1/empty-report survivor and the wrong-exception probe both yield an overall FAIL. With the previous classification swapped back in (a scratch check), 9 of the 20 runner checks fail |

Only `results/tables/q3-mutation-validation.*` and `results/tables/q3-reproduction.*` changed; every other Q3 artifact is byte-identical to `68f8905`, and all scientific arrays and numbers are identical as parsed JSON.

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

New in M4's implementation: `src/alloc/inputguard.py`, `sourcedocx.py`, `quality.py`, `provenance.py`, `report.py`, `c7.py` (remediation), `scripts/q3_provenance_ledger.py`, `scripts/q3_mutation_validation.py` (remediation), `results/tables/q3-provenance-ledger.*`, `results/tables/q3-mutation-validation.*`.

## Evidence

**Code**: `src/alloc/` and `scripts/q3_*.py`.

**Regenerable artifacts** (all from `scripts/q3_reproduce.py`):
`results/tables/q3-source-receipt.*`, `q3-allocation.*`, `q3-context-sensitivity.*`, `q3-regime-thresholds.*`, `q3-quality-cost-sensitivity.*`, `q3-loo-robustness.*`, `q3-provenance-ledger.*`, `q3-mutation-validation.*`, `q3-reproduction.*`.

**Commands actually run** on the candidate's content (runtime Python 3.11.16, NumPy 2.4.6, SciPy 1.17.1, pandas 3.0.6, PyYAML 6.0.3):

```text
conda run -n modeling-research-2026 --no-capture-output python scripts/q3_reproduce.py
# (sources at ef0369d; its outputs are the artifacts committed as 21cc4cd; exit 0)
# two passes identical: True; LF-only: True; inputs unchanged: True;
# interfaces unchanged: True; guard denials: 0; runtime matches pins: True
# includes scripts/q3_mutation_validation.py in both passes:
# mutants killed 24/25 (outcomes KILLED 24, SURVIVED_CLEAN 1 = M08); data probes passed 15/15;
# runner checks passed 20/20; overall: PASS
conda run -n modeling-research-2026 --no-capture-output python scripts/q3_selftest.py
# CATEGORIES {"ARTIFACT": 13, "BOUNDARY": 75, "CONSISTENCY": 7, "ORACLE": 56, "REGRESSION": 36}
# PASS 187 checks
conda run -n modeling-research-2026 --no-capture-output python scripts/selftest_interfaces.py
# RESULT: PASS (21 assertions)
git diff --check
# clean
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PreCommit
# RESULT: PASS (before every commit)
```

## Key results

All results are model-conditional consequences of the accepted classic IF3 law inside its raw-N/raw-D validity box, at the semantic baseline `Q = Q0`; none is an observation or developer guidance.

**Corrected budget inequality.** The problem solved is `min L(N, D)` subject to `kappa N D <= C`, `N_min <= N <= N_max`, `D_min <= D <= D_max`, `kappa = 6 + eta L_ctx`. With `C_min = kappa N_min D_min` and `C_box = kappa N_max D_max`: no feasible point below `C_min`; for `C_min <= C <= C_box` an optimum saturates the budget, and at `C = C_box` it is the saturating upper corner; for `C > C_box` the optimum is the upper corner `(N_max, D_max)` with unused budget `C - C_box`. The closed form is used only where the stationary point lies inside the box ([q3-allocation.md](../../results/tables/q3-allocation.md)).

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

**LOO robustness** ([q3-loo-robustness.md](../../results/tables/q3-loo-robustness.md)) — *leave-one-trajectory-out robustness at published parameter precision*. Source `results/tables/q2-uncertainty-robustness.md`, Git blob `d32cdfd87f5fea9ac56f68aef0f9fc8d574c2020` at accepted T-008 commit `b18967c76395ab7d9a336f957e74cd6b4e8d3a99` (blob-content SHA-256 `636481ae810a449b814a7817d3559174745eb70abd0bec03bfbd857e707ce133`), eight complete vectors printed with `format(x, ".6g")`, parsed from the Git object; no accepted full-precision LOO object exists. The published vectors are unchanged by the identity correction. Where N*/D* are free, LOO relative spreads are 1.6e-4 to 3.8e-4 and resolved at published precision; under an active bound they are fixed. Predicted-loss spreads (3.1e-6 to 1.8e-5) are **not resolved**: six-digit rounding of one vector moves the loss by as much (the nominal and the published full fit already differ by about 3.5e-6). The `D_max` threshold's LOO spread is 7.0e-4 relative and resolved; no LOO range contains a representative budget, so all fits agree on every primary-grid regime. These are robustness ranges, not confidence, bootstrap or posterior intervals; bootstrap marginals and profile ratios are kept separate and not propagated; the B1 generator-recovery caveat applies.

**Raw quality-cost families** ([q3-quality-cost-sensitivity.md](../../results/tables/q3-quality-cost-sensitivity.md)). On `Q in (0, 1]`, in FLOPs per token, each pair crosses exactly once: exponential/logarithmic at Q = 5.0277e-4, exponential/power at 0.36638, power/logarithmic at 0.98855. Ascending order: `(0, 5.03e-4)` power < logarithmic < exponential; `(5.03e-4, 0.366)` power < exponential < logarithmic; `(0.366, 0.989)` exponential < power < logarithmic; `(0.989, 1]` exponential < logarithmic < power. Counts are exact by analytic monotone-piece argument (not a grid); `Q -> 0+` values are analytic limits.

**Nonbaseline quality.** Nonbaseline `D [g(Q) - g(Q0)]_+` allocation remains `BLOCKED_UNTIL_Q0_DECLARED`; nontrivial Q optimization is unsupported by classic IF3; cross-scale quality benefit is prohibited. Baseline quality compute is exactly zero. This is a property of the accepted model, not a claim that data quality is unimportant.

## Sources, interfaces and source security

**Authorized-source ledger.** [q3-source-receipt.md](../../results/tables/q3-source-receipt.md) verifies 30 statements at exact DOCX locators with OMML exponent structure preserved: budget inequality `w:body/w:p[35]`; budgets `w:body/w:p[29]/m:oMath[7..9]`; coefficient 6 `w:body/w:p[30]/m:oMath[1]`; eta `w:body/w:p[34]/m:oMath[2]`; g(Q) families `w:body/w:p[49..51]`; Q domain `w:body/w:p[31]/m:oMath[3]`; Q0 source semantics `w:body/w:p[31]`; exogenous context `w:body/w:p[29]` and `[45]`; structural-transition requirement `w:body/w:p[35]`. The DOCX SHA-256 `89f1b27c…3b6a7` is checked first. No canonical value contradicted the specification.

**Source-binding design (finding 1).** The receipt is a record, never an authority. `load_source_receipt` (the single consumer used by every allocation script) first re-runs the structured DOCX/OMML verifier on the allowlisted canonical DOCX, which pins the accepted whole-file SHA-256, and re-derives the C7 support from the accepted C7 bytes, which are bound to the T-006 intake SHA-256 record, the organizer manifest byte count and its row-count note (`src/alloc/c7.py`). It then requires the receipt's verification block to equal that regeneration exactly (same keys in the same order, locators, statuses, verified values and modes; no extra, missing or duplicated records), requires every term value (coefficient 6, eta, the three budgets and the inequality, the six g(Q) coefficients, the Q domain, the Q0 options, parity `6/eta`) and the whole C7 context-support block to equal the independently derived values, and builds the returned lane from the derived values only. A forged receipt therefore fails before any allocation can use it. [q3-provenance-ledger.md](../../results/tables/q3-provenance-ledger.md) itemizes 42 load-bearing items (18 VERIFIED, 14 DERIVED, 10 MODEL_CONDITIONAL, 0 UNVERIFIED, 0 PDF-dependent); the generator refuses any PDF-, screenshot-, transcription- or AI-intermediate-only item.

**Narrowed input inventory** (the complete allowlist; eight files):
`docs_local/problem-f/source/problem_statement.docx`; `data_local/problem-f/raw/real_attachments/C_efficiency_evolution/model_architecture_metadata.csv` (`ee24622c…12ffc`); `data_local/problem-f/raw/real_attachments/source_manifest.json` (`34e81dab…323db`); `data_local/problem-f/raw/attachment_sha256_manifest.tsv` (T-006 intake record, which independently matches the C7 and manifest hashes); the three accepted interfaces; `results/tables/q2-uncertainty-robustness.md`, identified by its accepted Git blob (its accepted-commit, `HEAD` and working-tree Git identities must all equal the pinned blob; working-copy bytes are never hashed as its identity). The historical 1,977-file snapshot of the reviewed checkpoint was not revalidated and is not carried forward.

**Interfaces.** IF1 `b8ec99ca38f2e466b427fd1a7d88858048924cc590bbe881a966d141eb9bdeb8`, IF2 `9f2a83da45633858822c8416b5fa70a9537a06b07ac9056e50d871492b16ff91`, IF3 `720efea859d3be3b39ac2ee1976f8adaf7a31b8b5b1a71eb72e8ee8f987c8514`: accepted bytes, shared contracts and IF2's 1M-only scope are verified before and after reproduction and cross-checked against `q1-if1-summary.md`, `q1-if2-summary.md` and `q2-final-closure.md`. IF1 (11 of 17 mixture domains unmapped) and IF2 are released to Q3 as identity receipts whose content is inaccessible, so neither can become a quality coordinate, a canonical-loss input or a cross-scale coefficient. IF3's `Q = [1, 1]` remains a no-quality sentinel. B8 is not an input.

**Source security.** Every generator runs under an audit-hook guard that raises before the operating system opens any `*.pdf` (including for hashing), any non-allowlisted local file, or any input for writing, and before any listing under `data_local/` or `docs_local/`; reproduction recorded 0 denials and only allowlisted reads, and the self-test proves each refusal with harmless temporary fixtures. Neither `data_description.original.pdf` nor `data_description.sanitized.m2.pdf` was opened, parsed, hashed or otherwise consumed by M4 or by any T-010 code in this execution, and M4 did not list the directories that hold them. No load-bearing dependency on either PDF was found. **Reported operational deviation:** the user reports that M2 manually opened the original PDF in an editor. M4 has no further facts about that event and does not infer text extraction, AI ingestion or reliance from it; because every load-bearing value is independently traced to authorized sources, it remains an operational deviation only.

## Validation

**The 187 self-test checks do not carry equal weight.** Each check in `scripts/q3_selftest.py` is labelled, and the baseline classification is recorded in [q3-mutation-validation.md](../../results/tables/q3-mutation-validation.md):

| Category | Checks | Role |
| --- | ---: | --- |
| ORACLE | 56 | Supports acceptance: result against an independent expectation — `src/scaling`'s closed form, a Brent root of the stationary condition, a derivative-free search, a 1201x1201 brute-force grid over the raw box (at 1e19, 1e22 and 1e24, and on both sides of each transition at `L_ctx = 4096`), hand-derived fixtures for every single bound, corner, infeasible and slack case, independent `git rev-parse` of the LOO blob, an independent read of the C7 grid, independent dense-grid root finding for g(Q), the specification's stated constants |
| BOUNDARY | 75 | Supports the input contract: a production consumer or guard rejects a forged, altered, forbidden or out-of-scope input (receipt forgeries A1-A8, interface mutations, PDF/B8/traversal/write refusals in child processes, ledger provenance), with an unmodified-receipt control |
| ARTIFACT | 13 | Guards generated tables (regimes, LOO counts, ledger wording, withdrawn dispositions) |
| CONSISTENCY | 7 | Same code path compared with itself (for example the receipt's verification block against a fresh verification); regression detection only |
| REGRESSION | 36 | Smoke checks of current labels and constants; regression detection only |

Acceptance rests on the ORACLE and BOUNDARY checks. The previous package's figure of 170 assertions mixed these categories; the self-comparisons it contained now count as CONSISTENCY or REGRESSION only.

**Executable mutation validation.** `scripts/q3_mutation_validation.py` runs in a temporary detached Git worktree whose sources are verified byte-identical to their committed blobs, supplied with copies of the local-only allowlisted inputs; the working tree is never modified, and every mutated file or probed input is restored and verified by SHA-256 and `git diff`. Classification fails closed (see Validation correction). Result, reproduced identically in both reproduction passes: 25 code mutants, 24 expected killed and 24 killed by their declared detectors; M08 (the ledger's forbidden-kind list) is the only redundant layer, survives cleanly with a complete 187-check report, and its full-removal pair M09 is killed. 15 data probes feed forged receipts (A1-A8, A6 also to the context script), a C7 file with a `262144` row, a value-preserving DOCX change (to the allocation consumer, P12, and to the receipt generator, P14) and an altered LOO working copy to the real scripts; every forged input is rejected with the exact expected exception (`SourceReceiptError`, `SourceVerificationError` or `TrackedInputIdentityError`), leaves the consumer's outputs untouched and is restored by hash, and the unforged control succeeds. The DOCX whole-file SHA-256 pin is the only accepted-source identity anchor for the DOCX; P12's remaining receipt/DOCX hash comparison is receipt/source consistency. 20 of 20 runner self-checks pass. Overall: **PASS**. The first runs of the suite exposed two defects in the suite itself (a CRLF worktree checkout, a non-unique probe row), fixed in `17aca9f` and `21138f6`; the supervisory re-check exposed V1 and V2, fixed in `ef0369d`.

Committed T-010 blobs at the candidate were checked byte-for-byte: all 16 artifacts match the reproduction receipt and contain no CR.

## Gate record

| Gate | Exact command | Tested head | Started (UTC+8) | Exit | Result |
| --- | --- | --- | --- | ---: | --- |
| PrePush on the superseded candidate | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PrePush` | `f262cebbd03e02a5c119e359fdcba7802950e830` | 2026-09-27T02:15:58+08:00 | 0 | `RESULT: PASS` — 214 files examined, 65 commits scanned, 7 addresses checked (4 by approved suffix, 2 by approved exact rule), 1 of 1 listed history exception waived |
| PrePush on the current scientific candidate | `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_public_safe.ps1 -Mode PrePush` | `21cc4cd0ced7a7d2aec6ffc1cec7be7b0ba15de2` | 2026-09-27T03:10:28+08:00 | 0 | `RESULT: PASS` — 214 files examined, 75 commits scanned, 7 addresses checked (4 by approved suffix, 2 by approved exact rule), 1 of 1 listed history exception waived |

This package is committed after the candidate; PreCommit runs on this receipt commit and PrePush runs again on the final live head before push, and those two results are reported with the pushed head rather than recorded here (to avoid a self-referencing SHA).

## Interfaces and downstream impact — T-012 claim boundary

T-012 remains **blocked** from consuming T-010 until supervisory acceptance. After acceptance, T-012 **may** consume, as model-conditional statements with their sources:

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
- Remediation of the re-audit ran under an L1 instruction; it added no scientific scope and changed no scientific number.

## Known limitations and open risks

- Every allocation, threshold and range is conditional on the accepted classic IF3, whose fit is a generator recovery on B1; the validity-box transitions describe where the law was identified, not how training behaves beyond it.
- LOO propagation is limited to published six-digit precision; loss robustness is not resolved at that precision.
- No numeric `Q0` exists, so no nonbaseline quality scenario was evaluated; the quality conclusion is a property of the accepted model.
- Context results are confined to five observed C7 values; a regime change between them is bracketed, not located.
- The guard covers file access from Python in Q3 processes; it is not an operating-system sandbox. The LOO Git binding runs `git` subprocesses, whose reads of the object store and of the tracked working file the Python guard does not see.
- The LOO and receipt bindings need `git` and the repository history (commit `b18967c`) to be present; without them loading fails closed.
- The mutation suite shows that the listed defects are detected; it is not a proof that no other defect exists. Its code mutants are killed by the self-test or by named data probes; three layers of the C7 binding (intake hash, manifest byte count, row-count note) are exercised together by probe P11, not one at a time.
- The canonical DOCX has a single accepted-source identity anchor, its pinned whole-file SHA-256; the receipt's recorded DOCX hash only ties a receipt to the DOCX it was generated from.
- Receipt-forgery evidence covers the listed forgeries and any receipt that differs from the independent regeneration; it relies on the canonical DOCX and C7 bytes themselves being the accepted ones, which their pinned SHA-256 values establish.

## Next action

M1 (supervisor): fresh re-audit of the pushed head of `exp/m4-T010-q3-allocation`. No replacement PR has been created. T-010 remains `wip` and unmerged; PR #17 stays Draft and unmerged as the historical M2 checkpoint; T-012 is not started and may not yet consume T-010.
