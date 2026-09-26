"""Executable checks for the T-010 Q3 allocation lane.

Covers T-010 v1 section 15 and v2 section 7 through the production boundaries
themselves: the accepted-interface loaders, the explicit input allowlist, the
process-wide input guard (exercised in child processes, because an audit hook
cannot be removed), the receipt loader, the solver, the regime analysis, the
LOO and quality modules and the provenance-ledger validator.  Every guard is
also shown to fail on a deliberately invalid fixture.  Fixtures are temporary
files or in-memory objects; accepted interfaces, source inputs and generated
artifacts are never modified.  Neither PDF is touched: PDF guards are probed
with harmless temporary files that merely carry the quarantined names.

Run through the declared environment:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_selftest.py
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable
from xml.etree import ElementTree as ET

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scipy.optimize import brentq  # noqa: E402

from src.alloc import (  # noqa: E402
    ACCEPTED_CLASSIC_IF3_SHA256,
    ACCEPTED_INTERFACE_SHA256,
    AUTHORIZED_Q3_INPUTS,
    B8_PATH,
    C7_PATH,
    CONTINUATION,
    DOCX_PATH,
    SOURCE_SUPPORTED,
    AcceptedIF3HashMismatch,
    AcceptedInterfaceError,
    AcceptedInterfaceHashMismatch,
    BaselineCompute,
    BaselineScopeError,
    ClassicIF3ContractError,
    ForbiddenQ3Input,
    IF2ScopeError,
    IdentityOnlyInterfaceError,
    InterfaceIdentityReceipt,
    LOORobustnessError,
    NoValidityBoxAllocation,
    ProvenanceError,
    PublishedParameterVector,
    SensitivityClassicLaw,
    SourceReceiptError,
    SourceVerificationError,
    UnauthorizedQ3Input,
    analyze_regime_thresholds,
    baseline_closed_form,
    build_loo_sensitivity_models,
    classic_loss,
    cost_breakdown,
    load_accepted_interface,
    load_all_accepted_interfaces,
    load_classic_if3,
    load_loo_robustness,
    load_source_receipt,
    pure_nd_oracle,
    raw_family_analysis,
    reject_forbidden_q3_input,
    require_authorized_q3_input,
    rounding_corner_laws,
    sha256_authorized_q3_input,
    solve_baseline,
    solve_baseline_numeric,
    stationary_threshold,
    validate_ledger,
    verify_accepted_hash_receipts,
    verify_source_values,
)
from src.alloc.loo import _parse_vectors  # noqa: E402
from src.alloc.regime import probe_budget  # noqa: E402
from src.alloc.robustness import require_published_full_fit_matches  # noqa: E402
from src.alloc.sourcedocx import SourceCheck, _record, parse_decimal, read_docx_blocks  # noqa: E402
from src.paths import ATT_C, TABLES  # noqa: E402

RESULTS: list[tuple[str, bool]] = []
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

PROBE = """
import json, os, sys
sys.path.insert(0, sys.argv[1])
from src.alloc import ForbiddenQ3Input, UnauthorizedQ3Input, install_q3_input_guard
install_q3_input_guard()
action, target = sys.argv[2], sys.argv[3]
try:
    if action == "open_read":
        with open(target, "rb") as handle:
            handle.read(1)
    elif action == "open_readwrite":
        handle = open(target, "r+b")
        handle.close()
    elif action == "hash":
        import hashlib
        with open(target, "rb") as handle:
            hashlib.sha256(handle.read()).hexdigest()
    elif action == "listdir":
        os.listdir(target)
    elif action == "scandir":
        list(os.scandir(target))
    elif action == "workflow":
        from src.alloc import (BaselineCompute, guard_record, load_all_accepted_interfaces, load_classic_if3,
                               load_loo_robustness, load_source_receipt, solve_baseline, verify_source_values)
        verify_source_values()
        load_all_accepted_interfaces()
        classic = load_classic_if3()
        receipt = load_source_receipt()
        load_loo_robustness()
        result = solve_baseline(classic, BaselineCompute.create(receipt, 1e24, 4096))
        print("RECORD " + json.dumps({"guard": guard_record(), "regime": result.regime}))
    print("NO_EXCEPTION")
except ForbiddenQ3Input:
    print("FORBIDDEN")
except UnauthorizedQ3Input:
    print("UNAUTHORIZED")
except Exception as exc:
    print("OTHER " + type(exc).__name__)
"""


def check(name: str, condition: object) -> None:
    RESULTS.append((name, bool(condition)))


def expect_raise(name: str, fn: Callable[[], object], exc_type: type[BaseException]) -> None:
    try:
        fn()
    except exc_type:
        check(name, True)
    except Exception as exc:  # the wrong failure is still a failure of the check
        check(name + " [raised " + type(exc).__name__ + "]", False)
    else:
        check(name + " [no exception]", False)


def close(left: float, right: float, rel: float = 1e-12) -> bool:
    return math.isclose(left, right, rel_tol=rel, abs_tol=0.0)


def probe(action: str, target: Path | str) -> tuple[str, dict[str, Any] | None]:
    completed = subprocess.run([sys.executable, "-c", PROBE, str(REPO), action, str(target)],
                               capture_output=True, text=True, cwd=REPO)
    lines = completed.stdout.strip().splitlines()
    record = None
    for line in lines:
        if line.startswith("RECORD "):
            record = json.loads(line[len("RECORD "):])
    return (lines[-1] if lines else "NO_OUTPUT " + completed.stderr[-200:]), record


def temp_json(directory: Path, name: str, payload: object) -> tuple[Path, str]:
    path = directory / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def accepted_payload(kind: str) -> dict[str, Any]:
    entry = {"IF1": "accepted_if1", "IF2": "accepted_if2", "IF3": "accepted_if3"}[kind]
    path = next(item.path for item in AUTHORIZED_Q3_INPUTS if item.key == entry)
    return json.loads(require_authorized_q3_input(path).read_text(encoding="utf-8"))


def mutate_docx(target: Path, paragraph: int, old: str, new: str) -> bool:
    """Write a copy of the canonical DOCX with one math text run changed."""
    with zipfile.ZipFile(require_authorized_q3_input(DOCX_PATH)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(entries["word/document.xml"])
    paragraphs = [child for child in root.find(W_NS + "body") if child.tag == W_NS + "p"]
    changed = False
    for text in paragraphs[paragraph - 1].iter(M_NS + "t"):
        if text.text == old:
            text.text = new
            changed = True
            break
    entries["word/document.xml"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(target, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return changed


def fixture_law(n_box: tuple[float, float], d_box: tuple[float, float]) -> SensitivityClassicLaw:
    """alpha = beta = 1/2, A = B = 1: the stationary path is N_s = D_s = sqrt(C/kappa)."""
    return SensitivityClassicLaw("self_test_fixture", {"E": 1.0, "A": 1.0, "alpha": 0.5, "B": 1.0, "beta": 0.5},
                                 {"N": n_box, "D": d_box, "Q": (1.0, 1.0)}, "self-test fixture", "exact")


def main() -> int:
    directory_handle = tempfile.TemporaryDirectory()
    temp = Path(directory_handle.name)
    classic = load_classic_if3()
    receipt = load_source_receipt()
    interfaces = load_all_accepted_interfaces()

    # ---- accepted interfaces: identity, contract, scope and the identity-only boundary
    check("accepted IF3 hash", classic.sha256 == ACCEPTED_CLASSIC_IF3_SHA256)
    check("all three interfaces carry their accepted hashes",
          {kind: item.sha256 for kind, item in interfaces.items()} == ACCEPTED_INTERFACE_SHA256)
    check("IF1 and IF2 are released as identity receipts only",
          isinstance(interfaces["IF1"], InterfaceIdentityReceipt) and isinstance(interfaces["IF2"], InterfaceIdentityReceipt))
    expect_raise("IF1 content cannot reach Q3 (no IF1 quality coordinate)", lambda: interfaces["IF1"].payload,
                 IdentityOnlyInterfaceError)
    expect_raise("IF2 content cannot reach Q3 (no canonical-loss or cross-scale use)", lambda: interfaces["IF2"].interface,
                 IdentityOnlyInterfaceError)
    check("IF1 keeps unmapped domains unimputed", interfaces["IF1"].scope["unmapped_mixture_domains"] > 0
          and interfaces["IF1"].scope["coverage_fraction"] < 1.0)
    check("IF2 scope receipt is 1M-only", interfaces["IF2"].scope["fit_scale"] == "1M"
          and interfaces["IF2"].scope["absolute_use_outside_1M"] == "PROHIBITED")
    check("accepted hashes are published in tracked upstream receipts", set(verify_accepted_hash_receipts()) == {"IF1", "IF2", "IF3"})

    if2 = accepted_payload("IF2")
    if2["fit_scale"] = "10B"
    path, digest = temp_json(temp, "if2-10b.json", if2)
    expect_raise("IF2 declared outside 1M is rejected", lambda: load_accepted_interface("IF2", path, expected_sha256=digest),
                 IF2ScopeError)
    if2 = accepted_payload("IF2")
    if2["validation"]["scope_release"]["limitations"]["absolute_use_outside_1M"] = "ALLOWED"
    path, digest = temp_json(temp, "if2-outside.json", if2)
    expect_raise("IF2 absolute use outside 1M cannot be enabled", lambda: load_accepted_interface("IF2", path, expected_sha256=digest),
                 IF2ScopeError)
    if1 = accepted_payload("IF1")
    if1["mixture_to_quality"] = {domain: target or "imputed" for domain, target in if1["mixture_to_quality"].items()}
    path, digest = temp_json(temp, "if1-imputed.json", if1)
    expect_raise("IF1 with imputed unmapped domains is rejected", lambda: load_accepted_interface("IF1", path, expected_sha256=digest),
                 AcceptedInterfaceError)
    if3 = accepted_payload("IF3")
    if3["validity_box"]["Q"] = [0.5, 1.0]
    path, digest = temp_json(temp, "if3-q.json", if3)
    expect_raise("IF3 Q box must stay the [1, 1] no-quality sentinel", lambda: load_classic_if3(path, expected_sha256=digest),
                 ClassicIF3ContractError)
    for kind in ("IF1", "IF2", "IF3"):
        source = next(item.path for item in AUTHORIZED_Q3_INPUTS if item.key == "accepted_" + kind.lower())
        altered = temp / (kind + "-altered.json")
        altered.write_bytes(require_authorized_q3_input(source).read_bytes() + b"\n")
        expect_raise(kind + " altered bytes are rejected before parsing", lambda altered=altered, kind=kind: load_accepted_interface(kind, altered),
                     AcceptedInterfaceHashMismatch)
    expect_raise("altered IF3 is rejected by the classic loader", lambda: load_classic_if3(temp / "IF3-altered.json"),
                 AcceptedIF3HashMismatch)
    expect_raise("a missing interface is rejected", lambda: load_accepted_interface("IF1", temp / "absent.json"), AcceptedInterfaceError)
    receipt_text = (TABLES / "q1-if1-summary.md").read_text(encoding="utf-8").replace(ACCEPTED_INTERFACE_SHA256["IF1"], "0" * 64)
    (temp / "if1-summary.md").write_text(receipt_text, encoding="utf-8")
    expect_raise("an upstream receipt lacking the accepted hash is rejected",
                 lambda: verify_accepted_hash_receipts({"IF1": temp / "if1-summary.md"}), AcceptedInterfaceError)

    # ---- raw units and the IF3 sentinel
    box = classic.validity_box
    check("IF3 N box is in raw parameters", box["N"] == (70542000.0, 11965825000.0))
    check("IF3 D box is in raw tokens", close(box["D"][0], 1.34e8) and box["D"][1] == 299893000000.0)
    loo = load_loo_robustness()
    check("LOO trajectory labels are the IF3 N bounds in billions",
          close(float(loo.vectors[0].label) * 1e9, box["N"][0]) and close(float(loo.vectors[-1].label) * 1e9, box["N"][1]))
    p = classic.params
    check("classic loss uses raw N and D", close(classic_loss(classic, 1e9, 1e10),
                                                 p["E"] + p["A"] * 1e9 ** -p["alpha"] + p["B"] * 1e10 ** -p["beta"]))
    for label, quality in (("0.5", 0.5), ("1.0 (the IF3 sentinel value)", 1.0), ("'1'", "1"), ("True", True)):
        expect_raise("numeric quality " + label + " is rejected", lambda quality=quality: BaselineCompute.create(receipt, 1e22, 4096, quality=quality),
                     BaselineScopeError)

    # ---- source verification against the canonical DOCX
    fresh = verify_source_values()
    check("fresh DOCX verification equals the receipt", fresh == receipt.payload["source_verification"])
    check("every source record is VERIFIED", all(record["status"] == "VERIFIED" for record in fresh["records"]))
    check("receipt budgets are the verified 1e19, 1e22, 1e24", receipt.budgets_flops == (1e19, 1e22, 1e24))
    check("receipt eta and coefficient are verified", receipt.eta == 2e-4 and receipt.base_coefficient == 6.0)
    check("receipt families are verified", receipt.quality_families == {
        "exponential": {"gamma": 1e7, "lambda": 6.0}, "power": {"gamma": 5e9, "lambda": 4.0},
        "logarithmic": {"gamma": 2e9, "lambda": 10.0}})
    check("receipt contexts are the full observed C7 grid", receipt.contexts_tokens == (2048, 4096, 8192, 32768, 131072))
    for label, paragraph, old, new in (("eta exponent", 34, "4", "5"), ("lambda 6.0", 49, "6.0", "7.0"),
                                       ("budget exponent", 29, "24", "25")):
        target = temp / ("mutated-" + str(paragraph) + ".docx")
        check("DOCX fixture changed " + label, mutate_docx(target, paragraph, old, new))
        expect_raise("a changed source " + label + " fails verification", lambda target=target: verify_source_values(target),
                     SourceVerificationError)
    expect_raise("DOCX verification rejects a PDF path", lambda: verify_source_values(temp / "problem.pdf"), ForbiddenQ3Input)
    blocks = read_docx_blocks()
    inconsistent = SourceCheck("fixture_lambda", "w:body/w:p[49]", "fixture", (), "λ=6.0",
                               lambda zone: parse_decimal(zone.split("=", 1)[1]), 7.0)
    expect_raise("a parsed source value that differs from its expectation is rejected",
                 lambda: _record(inconsistent, blocks), SourceVerificationError)

    def receipt_mutation(name: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        payload = json.loads(json.dumps(receipt.payload))
        mutate(payload)
        path, _ = temp_json(temp, "receipt-" + str(len(RESULTS)) + ".json", payload)
        expect_raise(name, lambda: load_source_receipt(path), SourceReceiptError)

    def term(payload: dict[str, Any], name: str) -> dict[str, Any]:
        return next(item for item in payload["terms"] if item["name"] == name)["supported_value_or_grid"]

    # These fixtures keep the 6/eta parity term consistent, so only the source-value cross-check can catch them.
    receipt_mutation("receipt eta mutation is rejected", lambda item: (
        term(item, "attention_compute").update(eta=3e-4), term(item, "attention_cost_parity_identity").update(parity_tokens=20000.0)))
    receipt_mutation("receipt coefficient mutation is rejected", lambda item: (
        term(item, "base_training_compute").update(coefficient=8), term(item, "attention_cost_parity_identity").update(parity_tokens=40000.0)))
    receipt_mutation("receipt budget mutation is rejected",
                     lambda item: term(item, "compute_budget").update(representative_budgets_flops=[1e19, 1e22, 1e25]))
    receipt_mutation("receipt family mutation is rejected", lambda item: term(item, "quality_cost_families")["power"].update(gamma=6e9))
    receipt_mutation("receipt domain mutation is rejected", lambda item: term(item, "quality_domain").update(lower_inclusive=True))
    receipt_mutation("receipt numeric Q0 is rejected", lambda item: term(item, "quality_baseline_Q0").update(numeric_global_Q0=0.5))
    receipt_mutation("an UNVERIFIED source record is rejected",
                     lambda item: item["source_verification"]["records"][0].update(status="UNVERIFIED"))
    receipt_mutation("a receipt bound to another DOCX is rejected",
                     lambda item: item["source_verification"].update(docx_sha256="0" * 64))
    receipt_mutation("a dropped source record is rejected", lambda item: item["source_verification"]["records"].pop())
    receipt_mutation("the baseline gate cannot be blocked",
                     lambda item: item["gates"]["canonical_baseline_nd_allocation"].update(result="BLOCKED"))
    receipt_mutation("the nonbaseline gate cannot be opened",
                     lambda item: item["gates"]["nonbaseline_quality_cost_scenarios"].update(result="PASS"))
    receipt_mutation("the cross-scale gate cannot be opened",
                     lambda item: item["gates"]["cross_scale_quality_benefit"].update(result="PASS"))

    # ---- input allowlist and the process-wide guard
    expect_raise("quarantined original PDF name is rejected before any access",
                 lambda: sha256_authorized_q3_input(temp / "absent" / "data_description.original.pdf"), ForbiddenQ3Input)
    expect_raise("sanitized PDF name is rejected before any access",
                 lambda: require_authorized_q3_input(temp / "absent" / "data_description.sanitized.m2.pdf"), ForbiddenQ3Input)
    expect_raise("any PDF is rejected by the interface loader", lambda: load_accepted_interface("IF3", temp / "if3.pdf"),
                 ForbiddenQ3Input)
    expect_raise("B8 is not an authorized input (rejected before any existence check)",
                 lambda: require_authorized_q3_input(B8_PATH), UnauthorizedQ3Input)
    expect_raise("a non-allowlisted tracked file is rejected", lambda: require_authorized_q3_input(REPO / "README.md"),
                 UnauthorizedQ3Input)
    check("the allowlist is exactly eight named inputs", len(AUTHORIZED_Q3_INPUTS) == 8
          and not any(str(item.path).lower().endswith(".pdf") for item in AUTHORIZED_Q3_INPUTS))
    original = temp / "data_description.original.pdf"
    sanitized = temp / "data_description.sanitized.m2.pdf"
    original.write_bytes(b"harmless fixture, not the quarantined document\n")
    sanitized.write_bytes(b"harmless fixture, not the sanitized derivative\n")
    check("guard: opening a PDF-named fixture is refused", probe("open_read", original)[0] == "FORBIDDEN")
    check("guard: hashing a PDF-named fixture is refused", probe("hash", sanitized)[0] == "FORBIDDEN")
    check("guard: control fixture with a non-PDF name opens", probe("open_read", temp / "if1-summary.md")[0] == "NO_EXCEPTION")
    check("guard: opening B8 is refused before the filesystem is touched", probe("open_read", B8_PATH)[0] == "UNAUTHORIZED")
    check("guard: listing a local input directory is refused", probe("listdir", ATT_C)[0] == "FORBIDDEN")
    check("guard: scanning a local input directory is refused", probe("scandir", ATT_C)[0] == "FORBIDDEN")
    check("guard: opening C7 for writing is refused", probe("open_readwrite", C7_PATH)[0] == "FORBIDDEN")
    status, record = probe("workflow", "-")
    reads = set(record["guard"]["reads"]) if record else set()
    check("guard: the authorized workflow runs with the guard active", status == "NO_EXCEPTION" and record is not None)
    check("guard: the workflow had no denials", record is not None and record["guard"]["denied"] == [])
    check("guard: the workflow opened only allowlisted inputs",
          reads and reads <= {item.key for item in AUTHORIZED_Q3_INPUTS} and "canonical_problem_statement_docx" in reads
          and "accepted_q2_loo_evidence" in reads)
    check("guard: the workflow reaches the corrected 1e24 regime", record is not None and record["regime"] == "SLACK:N_max+D_max")

    # ---- compute semantics, closed form and the stationary identity
    compute = BaselineCompute.create(receipt, 1e19, 2048)
    interior = solve_baseline(classic, compute)
    cost = cost_breakdown(compute, interior.n_parameters, interior.d_tokens)
    check("kappa = 6 + eta L_ctx", compute.kappa == 6.0 + 2e-4 * 2048)
    check("components reconcile with kappa N D", close(cost["base_flops"] + cost["attention_flops"], compute.kappa * interior.n_parameters * interior.d_tokens))
    check("quality compute and share are exactly zero at Q0", cost["quality_flops"] == 0.0 and cost["quality_share_of_spent"] == 0.0
          and compute.delta_g_flops_per_token == 0.0)
    check("shares of spent compute sum to one", close(cost["base_share_of_spent"] + cost["attention_share_of_spent"], 1.0))
    check("base share of spent is 6/kappa", close(cost["base_share_of_spent"], 6.0 / compute.kappa))
    check("cost parity identity 6/eta = 30000 gives equal shares", receipt.parity_tokens == 30000.0
          and close(6.0 / (6.0 + receipt.eta * receipt.parity_tokens), 0.5))
    check("interior budget saturates", interior.regime == "SATURATED:interior" and close(interior.spent_flops, 1e19))
    oracle = pure_nd_oracle(classic, compute.budget_flops, compute.kappa)
    check("closed form equals the independent src.scaling oracle",
          close(interior.n_parameters, oracle["N_star"]) and close(interior.d_tokens, oracle["D_star"]))
    alpha, beta, a, b = p["alpha"], p["beta"], p["A"], p["B"]
    budget, kappa = compute.budget_flops, compute.kappa

    def slice_derivative(log_n: float) -> float:
        n_value = math.exp(log_n)
        return -alpha * a * n_value ** -alpha + beta * b * (budget / (kappa * n_value)) ** -beta

    root = math.exp(brentq(slice_derivative, math.log(1e6), math.log(1e12), xtol=1e-15, rtol=4.0 * 2.0**-52))
    check("numerical root of the stationary condition equals the closed form", close(root, interior.n_parameters, 1e-12))
    check("closed form satisfies N^(alpha+beta) = alpha A/(beta B) (C/kappa)^beta",
          close(interior.n_parameters ** (alpha + beta), alpha * a / (beta * b) * (budget / kappa) ** beta, 1e-12))
    check("relative stationary residual vanishes at the interior optimum", abs(interior.stationary_residual_relative) < 1e-12)
    for budget_value, expected in ((1e19, "SATURATED:interior"), (1e22, "SATURATED:D_max"), (1e24, "SLACK:N_max+D_max")):
        agreement = solve_baseline_numeric(classic, BaselineCompute.create(receipt, budget_value, 4096))
        check("numerical search agrees at " + format(budget_value, ".0e"),
              agreement.analytic.regime == expected and agreement.n_relative_difference <= 1e-6
              and agreement.d_relative_difference <= 1e-6 and agreement.loss_relative_difference <= 1e-11
              and agreement.analytic_not_improved)

    # ---- corrected budget inequality on the accepted law
    high = solve_baseline(classic, BaselineCompute.create(receipt, 1e24, 4096))
    c_box = high.allocation_box.c_box_flops
    check("1e24 is the upper corner with budget slack", high.regime == "SLACK:N_max+D_max"
          and high.n_parameters == box["N"][1] and high.d_tokens == box["D"][1])
    check("1e24 unused budget is 1e24 - C_box", close(high.unused_budget_flops, 1e24 - c_box) and close(high.compute_utilization, c_box / 1e24))
    check("1e24 shares of spent differ from fractions of budget", close(high.cost["base_fraction_of_budget"],
                                                                       high.cost["base_share_of_spent"] * c_box / 1e24))
    check("1e24 stationary point is outside the box and diagnostic only", not high.stationary_point_in_validity_box
          and high.stationary_residual_relative is None)
    medium = solve_baseline(classic, BaselineCompute.create(receipt, 1e22, 4096))
    check("1e22 at 4096 is D_max-bound and saturating", medium.regime == "SATURATED:D_max" and medium.d_tokens == box["D"][1]
          and close(medium.n_parameters, 1e22 / (medium.compute.kappa * box["D"][1])))
    check("1e22 stationary point lies outside the box", not medium.stationary_point_in_validity_box)
    previous = math.inf
    monotone, feasible = True, True
    for index in range(201):
        value = 1e19 * 10.0 ** (5.0 * index / 200.0)
        try:
            result = solve_baseline(classic, BaselineCompute.continuation(receipt, value, 4096))
        except NoValidityBoxAllocation:
            feasible = False
            continue
        monotone = monotone and result.predicted_loss <= previous * (1.0 + 1e-15)
        previous = result.predicted_loss
    check("every budget in the declared span is feasible", feasible)
    check("minimum loss is non-increasing in the budget", monotone)

    # ---- fixture optimizer: every single bound, both corners, infeasibility and slack
    context = 2048
    kappa_fixture = receipt.kappa(context)

    def fixture_solve(law: SensitivityClassicLaw, ratio: float):
        return solve_baseline(law, BaselineCompute(receipt, ratio * kappa_fixture, context, kappa_fixture, "self_test_fixture"))

    n_max_law = fixture_law((1.0, 4.0), (0.5, 9.0))
    d_max_law = fixture_law((0.5, 9.0), (1.0, 4.0))
    for law, ratio, regime, n_expected, d_expected in (
        (n_max_law, 9.0, "SATURATED:interior", 3.0, 3.0),
        (n_max_law, 25.0, "SATURATED:N_max", 4.0, 6.25),
        (n_max_law, 0.75, "SATURATED:N_min", 1.0, 0.75),
        (d_max_law, 25.0, "SATURATED:D_max", 6.25, 4.0),
        (d_max_law, 0.75, "SATURATED:D_min", 0.75, 1.0),
        (n_max_law, 0.5, "SATURATED:N_min+D_min", 1.0, 0.5),
        (n_max_law, 36.0, "SATURATED:N_max+D_max", 4.0, 9.0),
        (n_max_law, 72.0, "SLACK:N_max+D_max", 4.0, 9.0),
    ):
        result = fixture_solve(law, ratio)
        agreement = solve_baseline_numeric(law, BaselineCompute(receipt, ratio * kappa_fixture, context, kappa_fixture, "self_test_fixture"))
        check("fixture C/kappa=" + format(ratio, "g") + " gives " + regime,
              result.regime == regime and close(result.n_parameters, n_expected, 1e-9) and close(result.d_tokens, d_expected, 1e-9)
              and agreement.n_relative_difference <= 1e-6 and agreement.analytic_not_improved)
    slack = fixture_solve(n_max_law, 72.0)
    check("fixture slack keeps half the budget unused", close(slack.unused_budget_flops, 36.0 * kappa_fixture) and close(slack.compute_utilization, 0.5))
    expect_raise("fixture below C_min is genuinely infeasible", lambda: fixture_solve(n_max_law, 0.49), NoValidityBoxAllocation)
    previous, monotone = math.inf, True
    for index in range(301):
        result = fixture_solve(n_max_law, 0.5 * 10.0 ** (3.0 * index / 300.0))
        monotone = monotone and result.predicted_loss <= previous * (1.0 + 1e-15)
        previous = result.predicted_loss
    check("fixture minimum loss is non-increasing from C_min to beyond C_box", monotone)

    # ---- regime identification: production and fixtures
    for context_value in receipt.contexts_tokens:
        analysis = analyze_regime_thresholds(classic, receipt, context_value)
        retained = [(item.name, item.below["regime"], item.above["regime"]) for item in analysis.retained]
        check("L_ctx=" + str(context_value) + ": transitions are the D_max onset and the C_box slack onset",
              retained == [("stationary_reaches_D_max", "SATURATED:interior", "SATURATED:D_max"),
                           ("C_box", "SATURATED:D_max", "SLACK:N_max+D_max")])
        check("L_ctx=" + str(context_value) + ": numerical elasticities match each regime",
              all(abs(interval.numeric_n_elasticity - interval.analytic_n_elasticity) < 1e-6
                  and abs(interval.numeric_d_elasticity - interval.analytic_d_elasticity) < 1e-6 for interval in analysis.regime_map))
        dispositions = {item.name: item.disposition for item in analysis.thresholds}
        check("L_ctx=" + str(context_value) + ": out-of-span candidates are recorded, not analysed",
              dispositions["C_min"] == dispositions["stationary_reaches_N_min"] == "OUTSIDE_DECLARED_SPAN_NOT_ANALYSED")
    analysis = analyze_regime_thresholds(classic, receipt, 4096)
    threshold = next(item for item in analysis.retained if item.name == "stationary_reaches_D_max")
    check("D_max threshold equals its closed form", close(threshold.budget_flops, stationary_threshold(p, receipt.kappa(4096), "D", box["D"][1])))
    check("a budget inside one regime is not reported as a transition", probe_budget(classic, receipt, 4096, 1e20)[3] is False
          and probe_budget(classic, receipt, 4096, threshold.budget_flops)[3] is True)
    expect_raise("continuation below the declared span is refused", lambda: BaselineCompute.continuation(receipt, 1e18, 4096), SourceReceiptError)
    expect_raise("continuation above the declared span is refused", lambda: BaselineCompute.continuation(receipt, 2e24, 4096), SourceReceiptError)
    check("continuation budgets are labelled", BaselineCompute.continuation(receipt, 2e20, 4096).budget_role == CONTINUATION
          and BaselineCompute.create(receipt, 1e22, 4096).budget_role == SOURCE_SUPPORTED)
    expect_raise("an unsupported primary budget is refused", lambda: BaselineCompute.create(receipt, 2e20, 4096), SourceReceiptError)
    expect_raise("an unobserved context is refused", lambda: BaselineCompute.create(receipt, 1e22, 30000), SourceReceiptError)
    expect_raise("continuation cannot extend the context grid", lambda: BaselineCompute.continuation(receipt, 1e22, 262144), SourceReceiptError)
    fixture_receipt = dataclasses.replace(receipt, budgets_flops=(0.25 * kappa_fixture, 10.0 * kappa_fixture, 100.0 * kappa_fixture))
    for law, expected in (
        (n_max_law, [("C_min", "INFEASIBLE", "SATURATED:N_min"), ("stationary_reaches_N_min", "SATURATED:N_min", "SATURATED:interior"),
                     ("stationary_reaches_N_max", "SATURATED:interior", "SATURATED:N_max"), ("C_box", "SATURATED:N_max", "SLACK:N_max+D_max")]),
        (d_max_law, [("C_min", "INFEASIBLE", "SATURATED:D_min"), ("stationary_reaches_D_min", "SATURATED:D_min", "SATURATED:interior"),
                     ("stationary_reaches_D_max", "SATURATED:interior", "SATURATED:D_max"), ("C_box", "SATURATED:D_max", "SLACK:N_max+D_max")]),
    ):
        fixture_analysis = analyze_regime_thresholds(law, fixture_receipt, context)
        found = [(item.name, item.below["regime"], item.above["regime"]) for item in fixture_analysis.retained]
        check("fixture transitions and both neighbouring regimes (" + expected[2][0] + ")", found == expected)
        check("fixture regime map starts infeasible below C_min", fixture_analysis.regime_map[0].regime == "INFEASIBLE")
        at_corners = [item.at["regime"] for item in fixture_analysis.retained if item.name in ("C_min", "C_box")]
        low_bound = "N_min" if law is n_max_law else "D_min"
        check("fixture corners are exactly saturating (" + low_bound + ")", at_corners[0] == "SATURATED:N_min+D_min"
              and at_corners[1] == "SATURATED:N_max+D_max")

    # ---- LOO evidence and robustness laws
    markdown = loo.path.read_text(encoding="utf-8")
    check("LOO: eight complete ordered vectors", len(loo.vectors) == 8 and all(tuple(v.parameters) == ("E", "A", "alpha", "B", "beta") for v in loo.vectors))
    check("LOO: label states published precision", loo.precision_label == "leave-one-trajectory-out robustness at published parameter precision")
    check("LOO: half unit of 406.26 is 0.0005 (six significant digits)",
          close(next(v for v in loo.vectors if v.published_strings["A"] == "406.26").half_units()["A"], 0.0005))
    check("LOO: limitation rejects a probabilistic reading", "not a confidence interval" in loo.limitation and "B1" in loo.limitation)
    models = build_loo_sensitivity_models(classic, loo)
    check("LOO: nominal model is the accepted object itself", models[0].law is classic)
    check("LOO: alternative fits are not presented as the accepted IF3",
          all(not model.law.is_accepted_if3 and not hasattr(model.law, "sha256") for model in models[1:]))
    check("LOO: alternatives keep the accepted validity box", all(model.law.validity_box == classic.validity_box for model in models[1:]))
    check("LOO: 32 rounding corners per vector", len(rounding_corner_laws(classic, loo.vectors[0])) == 32)
    lines = markdown.splitlines()
    rows = [index for index, line in enumerate(lines) if line.startswith("| 0.070542 ") or line.startswith("| 0.162405 ")]
    swapped = list(lines)
    swapped[rows[0]], swapped[rows[1]] = swapped[rows[1]], swapped[rows[0]]
    expect_raise("LOO: reordered vectors are rejected", lambda: _parse_vectors("\n".join(swapped)), LOORobustnessError)
    expect_raise("LOO: a missing vector is rejected", lambda: _parse_vectors("\n".join(line for index, line in enumerate(lines) if index != rows[0])),
                 LOORobustnessError)
    expect_raise("LOO: a non-canonical printed value is rejected",
                 lambda: _parse_vectors(markdown.replace("| 406.636 |", "| 406.6360 |")), LOORobustnessError)
    wrong_fit = dataclasses.replace(loo, published_full_fit=PublishedParameterVector(
        "published_full_fit", {**loo.published_full_fit.parameters, "E": 1.68983},
        {**loo.published_full_fit.published_strings, "E": "1.68983"}))
    expect_raise("LOO: a full fit that is not the accepted IF3 is rejected", lambda: require_published_full_fit_matches(classic, wrong_fit),
                 LOORobustnessError)
    loo_payload = json.loads((TABLES / "q3-loo-robustness.json").read_text(encoding="utf-8"))
    check("LOO artifact: 150 individual outcomes and 15 summaries", len(loo_payload["rows"]) == 150 and len(loo_payload["summaries"]) == 15)
    check("LOO artifact: classified as robustness, not confidence", "not confidence" in loo_payload["claim_level"])
    check("LOO artifact: every primary point has one regime across all fits", all(item["regime_agreement"] for item in loo_payload["summaries"]))
    check("LOO artifact: upper-corner N and D ranges are degenerate",
          all(item["n_parameters_raw"]["rounding"]["verdict"] == "DEGENERATE_FIXED_BY_BOUNDS"
              for item in loo_payload["summaries"] if item["budget_flops"] == 1e24))

    # ---- raw quality-cost families: exact crossings and separation from blocked lanes
    analysis_q = raw_family_analysis(receipt.quality_families, receipt.quality_domain)
    check("quality: exactly one crossing per pair", [pair["crossing_count"] for pair in analysis_q["pairs"]] == [1, 1, 1])
    check("quality: crossings are roots to rounding", all(item["relative_residual"] < 1e-12 for pair in analysis_q["pairs"] for item in pair["crossings"]))
    check("quality: four ordering intervals on (0, 1]", len(analysis_q["interval_ordering"]) == 4)
    check("quality: the Q->0+ limits are analytic", analysis_q["families"]["exponential"]["limit_q_to_0_plus_flops_per_token"] == 1e7
          and analysis_q["families"]["power"]["limit_q_to_0_plus_flops_per_token"] == 0.0)
    two_roots = raw_family_analysis({**receipt.quality_families, "exponential": {"gamma": 1.5e7, "lambda": 6.0}}, receipt.quality_domain)
    check("quality: a convex pair with two crossings is fully resolved", two_roots["pairs"][0]["crossing_count"] == 2)
    near_one = raw_family_analysis({**receipt.quality_families, "power": {"gamma": 2e9 * math.log(11.0) * (1.0 + 1e-9), "lambda": 4.0}},
                                   receipt.quality_domain)
    check("quality: a crossing within 1e-9 of Q = 1 is found", near_one["pairs"][2]["crossing_count"] == 1
          and 1.0 - near_one["pairs"][2]["crossings"][0]["q"] < 1e-8)
    expect_raise("quality: a domain admitting Q = 0 is refused",
                 lambda: raw_family_analysis(receipt.quality_families, {**receipt.quality_domain, "lower_inclusive": True}), ValueError)
    quality_payload = json.loads((TABLES / "q3-quality-cost-sensitivity.json").read_text(encoding="utf-8"))
    check("quality: raw comparison done while nonbaseline allocation stays blocked",
          quality_payload["raw_g_comparison"] == "DONE" and quality_payload["nonbaseline_gate"]["result"] == "BLOCKED_UNTIL_Q0_DECLARED"
          and quality_payload["numeric_nonbaseline_scenarios_ran"] is False and quality_payload["quality_optimization_ran"] is False)

    # ---- provenance ledger
    ledger = json.loads((TABLES / "q3-provenance-ledger.json").read_text(encoding="utf-8"))["items"]
    check("ledger: generated ledger validates", validate_ledger(ledger) == len(ledger) and len(ledger) > 30)

    def ledger_mutation(name: str, mutate: Callable[[list[dict[str, Any]]], None]) -> None:
        items = json.loads(json.dumps(ledger))
        mutate(items)
        expect_raise(name, lambda: validate_ledger(items), ProvenanceError)

    def only_source(kind: str, path: str) -> Callable[[list[dict[str, Any]]], None]:
        return lambda items: items[0].update(sources=[{"kind": kind, "path": path, "sha256": "0" * 64}])

    ledger_mutation("ledger: PDF-only provenance is rejected", only_source("pdf", "docs_local/problem-f/source/data_description.original.pdf"))
    ledger_mutation("ledger: a PDF path relabelled as the DOCX is rejected", only_source("canonical_docx", "docs_local/problem-f/audit/data_description.sanitized.m2.pdf"))
    ledger_mutation("ledger: screenshot-only provenance is rejected", only_source("screenshot", "scratch/capture.png"))
    ledger_mutation("ledger: an AI-produced intermediate is rejected", only_source("ai_intermediate", "scratch/notes.md"))
    ledger_mutation("ledger: an absolute path is rejected", only_source("canonical_docx", "/fixture-root/problem_statement.docx"))
    ledger_mutation("ledger: an UNVERIFIED item blocks acceptance", lambda items: items[0].update(status="UNVERIFIED"))
    ledger_mutation("ledger: a missing limitation is rejected", lambda items: items[0].pop("limitation"))
    ledger_mutation("ledger: a purely derived item cannot claim VERIFIED",
                    lambda items: next(item for item in items if item["id"] == "C2").update(status="VERIFIED"))

    # ---- corrected artifacts
    allocation = json.loads((TABLES / "q3-allocation.json").read_text(encoding="utf-8"))
    regimes = {row["budget_flops"]: row["regime"] for row in allocation["allocations"]}
    check("artifact: canonical regimes at 1e19/1e22/1e24", regimes == {1e19: "SATURATED:interior", 1e22: "SATURATED:D_max",
                                                                     1e24: "SLACK:N_max+D_max"})
    check("artifact: every numerical check passed", all(row["numerical_check"]["result"] == "PASS" for row in allocation["allocations"]))
    artifact_text = "".join(path.read_text(encoding="utf-8") for path in sorted(TABLES.glob("q3-*")))
    check("artifact: the withdrawn NO_VALIDITY_BOX_ALLOCATION disposition is gone", "NO_VALIDITY_BOX_ALLOCATION" not in artifact_text)
    context_payload = json.loads((TABLES / "q3-context-sensitivity.json").read_text(encoding="utf-8"))
    check("artifact: observed contexts bracket the 1e22 D_max change", [
        (item["budget_flops"], item["lower_observed_context_tokens"], item["upper_observed_context_tokens"])
        for item in context_payload["observed_context_brackets"]] == [(1e22, 4096, 8192)])
    record = json.loads((TABLES / "q3-reproduction.json").read_text(encoding="utf-8"))
    check("artifact: last reproduction ran with zero guard denials", record["guard_denials"] == 0 and record["only_allowlisted_inputs_read"])
    check("reject_forbidden_q3_input is lexical", reject_forbidden_q3_input(temp / "plain.json") == temp / "plain.json")

    directory_handle.cleanup()
    expected = 170
    for name, passed in RESULTS:
        print(("PASS " if passed else "FAIL ") + name)
    failures = [name for name, passed in RESULTS if not passed]
    if len(RESULTS) != expected:
        print("FAIL assertion count: expected " + str(expected) + ", got " + str(len(RESULTS)), file=sys.stderr)
        return 1
    if failures:
        print("FAIL " + str(len(failures)) + " of " + str(len(RESULTS)) + " assertions", file=sys.stderr)
        return 1
    print("PASS " + str(len(RESULTS)) + " assertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
