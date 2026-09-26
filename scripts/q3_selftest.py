"""Executable checks for the T-010 Q3 allocation lane, classified by evidential weight.

Every check carries one of five categories, and they do not carry equal weight:

``ORACLE``
    A production result compared with an independently obtained expectation:
    a different implementation (``src/scaling``, a brute-force grid search, an
    independent root finder), a hand derivation, or a value read independently
    from the authorized source.  These support scientific acceptance.
``BOUNDARY``
    A production consumer or guard rejecting an invalid, forged, forbidden or
    out-of-scope input (or, as a control, admitting the authorized workflow).
    These support the input and provenance contract.
``ARTIFACT``
    An invariant of a generated tracked artifact.
``CONSISTENCY``
    A production result compared with another output of the same code path.
    Regression detection only; never acceptance evidence on its own.
``REGRESSION``
    A smoke check that a value or label stays as currently produced.
    Regression detection only.

Checks run in sections; an unexpected exception inside a section is recorded as
a failed check naming the section and exception type, so a defect is reported
rather than silently skipping later checks.  ``--report PATH`` writes the check
list with categories and outcomes as JSON.  Fixtures are temporary files or
in-memory objects; accepted interfaces, source inputs and tracked files are never
modified.  Neither PDF is touched: PDF guards are probed with harmless temporary
files that merely carry the quarantined names.

Run through the declared environment:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_selftest.py
"""

from __future__ import annotations

import csv
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

import numpy as np  # noqa: E402
from scipy.optimize import brentq  # noqa: E402

from src.alloc import (  # noqa: E402
    ACCEPTED_CLASSIC_IF3_SHA256,
    ACCEPTED_INTERFACE_SHA256,
    ACCEPTED_TRACKED_BLOBS,
    AUTHORIZED_Q3_INPUTS,
    B8_PATH,
    C7_PATH,
    CONTINUATION,
    DOCX_PATH,
    LOO_PATH,
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
    TrackedInputIdentityError,
    UnauthorizedQ3Input,
    analyze_regime_thresholds,
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

CATEGORIES = ("ORACLE", "BOUNDARY", "ARTIFACT", "CONSISTENCY", "REGRESSION")
EXPECTED_CHECKS = 187
RESULTS: list[tuple[str, str, bool]] = []
W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
M_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
ACCEPTED_T008_COMMIT = "b18967c76395ab7d9a336f957e74cd6b4e8d3a99"
LOO_RELATIVE = "results/tables/q2-uncertainty-robustness.md"

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


# ---------------------------------------------------------------------------
# Receipt forgeries A1-A8.  Each edits receipt data only and keeps the receipt
# internally consistent (verified_value, structured math, parity, C7 support),
# so only the consumer's independent regeneration from the DOCX and the C7
# bytes can reject it.  scripts/q3_mutation_validation.py reuses this table to
# feed the same forgeries to the real allocation scripts.
# ---------------------------------------------------------------------------

def _term(payload: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in payload["terms"] if item["name"] == name)["supported_value_or_grid"]


def _record_of(payload: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in payload["source_verification"]["records"] if item["key"] == key)


def _forge_eta(payload: dict[str, Any], value: float, math_text: str) -> None:
    _term(payload, "attention_compute").update(eta=value)
    _term(payload, "attention_cost_parity_identity").update(eta=value, parity_tokens=6.0 / value)
    _record_of(payload, "attention_eta").update(verified_value=value, structured_math=math_text)


def _forge_grid(payload: dict[str, Any], grid: list[int]) -> None:
    support = _term(payload, "context_length")
    known = {regime["context_tokens"]: regime for regime in support["representative_operating_regimes"]}
    support["observed_grid_tokens"] = grid
    support["observed_range_tokens"] = [grid[0], grid[-1]]
    support["observed_frequency"] = {str(value): known[value]["observed_model_count"] if value in known else 1
                                     for value in grid}
    support["representative_operating_regimes"] = [known.get(value, {
        "context_tokens": value, "observed_model_count": 1, "observed_models": ["forged/model"],
        "provenance_status": "observed"}) for value in grid]


def _a2(payload: dict[str, Any]) -> None:
    _term(payload, "base_training_compute").update(coefficient=8)
    _term(payload, "attention_cost_parity_identity").update(parity_tokens=8 / 2e-4)
    _record_of(payload, "base_training_coefficient").update(verified_value=8, structured_math="{C}_{train}=8ND")


def _a3(payload: dict[str, Any]) -> None:
    _term(payload, "compute_budget").update(representative_budgets_flops=[1e19, 1e22, 1e25])
    _record_of(payload, "representative_budget_high").update(verified_value=1e25, structured_math="{10}^{25}")


def _a4(payload: dict[str, Any]) -> None:
    _term(payload, "quality_cost_families")["power"].update(gamma=6e9)
    _record_of(payload, "g_power_gamma").update(verified_value=6e9, structured_math="γ=6×{10}^{9}")


def _a5(payload: dict[str, Any]) -> None:
    _forge_eta(payload, 3e-4, "η=3×{10}^{−4}")
    _record_of(payload, "attention_eta").update(locator="w:body/w:p[33]", math_locator="w:body/w:p[33]/m:oMath[1]")


def _a8a(payload: dict[str, Any]) -> None:
    payload["source_verification"]["records"].append({**_record_of(payload, "attention_eta"), "verified_value": 3e-4})
    _term(payload, "attention_compute").update(eta=3e-4)
    _term(payload, "attention_cost_parity_identity").update(parity_tokens=6.0 / 3e-4)


def _a8b(payload: dict[str, Any]) -> None:
    payload["source_verification"]["records"].append(
        {**_record_of(payload, "attention_eta"), "key": "attention_eta_override", "verified_value": 3e-4})


FORGERIES: dict[str, tuple[str, Callable[[dict[str, Any]], None]]] = {
    "A1": ("eta, its verified_value and parity changed consistently", lambda item: _forge_eta(item, 3e-4, "η=3×{10}^{−4}")),
    "A2": ("base coefficient, its verified_value and parity changed consistently", _a2),
    "A3": ("one representative budget and its verified_value changed consistently", _a3),
    "A4": ("one g(Q) coefficient and its verified_value changed consistently", _a4),
    "A5": ("a canonical locator changed together with the verified value", _a5),
    "A6": ("observed context 262144 inserted into the receipt grid",
           lambda item: _forge_grid(item, [2048, 4096, 8192, 32768, 131072, 262144])),
    "A7": ("receipt context grid differs otherwise from the C7 bytes",
           lambda item: _forge_grid(item, [2048, 4096, 8192, 32768])),
    "A8a": ("duplicate verification record shadows the canonical eta record", _a8a),
    "A8b": ("unexpected verification key added", _a8b),
}


def forged_receipt(case: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``payload`` with forgery ``case`` applied."""
    forged = json.loads(json.dumps(payload))
    FORGERIES[case][1](forged)
    return forged


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def check(name: str, condition: object, category: str) -> None:
    assert category in CATEGORIES, category
    RESULTS.append((name, category, bool(condition)))


def expect_raise(name: str, fn: Callable[[], object], exc_type: type[BaseException], category: str = "BOUNDARY") -> None:
    try:
        fn()
    except exc_type:
        check(name, True, category)
    except Exception as exc:  # the wrong failure is still a failure of the check
        check(name + " [raised " + type(exc).__name__ + "]", False, category)
    else:
        check(name + " [no exception]", False, category)


def section(title: str, body: Callable[[], None]) -> None:
    """Run one section; an unexpected exception becomes an attributable failure."""
    try:
        body()
    except Exception as exc:
        check("section '" + title + "' completed [raised " + type(exc).__name__ + "]", False, "REGRESSION")


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
    return (lines[-1] if lines else "NO_OUTPUT"), record


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, check=True).stdout


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


def brute_force(law: Any, kappa: float, budget: float, points: int = 1201) -> dict[str, float]:
    """Independent oracle: the best point of a log grid over the raw box obeying kappa N D <= C.

    No reduction, candidate set or solver code is used; grid endpoints are the
    exact box bounds.
    """
    (n_low, n_high), (d_low, d_high) = law.validity_box["N"], law.validity_box["D"]
    n_axis, d_axis = np.geomspace(n_low, n_high, points), np.geomspace(d_low, d_high, points)
    n_grid, d_grid = np.meshgrid(n_axis, d_axis, indexing="ij")
    p = law.params
    loss = p["E"] + p["A"] * n_grid ** -p["alpha"] + p["B"] * d_grid ** -p["beta"]
    loss = np.where(kappa * n_grid * d_grid <= budget, loss, np.inf)
    i, j = np.unravel_index(int(np.argmin(loss)), loss.shape)
    return {"loss": float(loss[i, j]), "n": float(n_axis[i]), "d": float(d_axis[j]),
            "spent": float(kappa * n_axis[i] * d_axis[j])}


def independent_c7_grid() -> list[int]:
    """Independent oracle: sorted unique max_position_embeddings read directly from C7."""
    with require_authorized_q3_input(C7_PATH).open("r", encoding="utf-8", newline="") as handle:
        return sorted({int(row["max_position_embeddings"]) for row in csv.DictReader(handle)})


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------

def main() -> int:
    report_path = sys.argv[sys.argv.index("--report") + 1] if "--report" in sys.argv else None
    directory_handle = tempfile.TemporaryDirectory()
    temp = Path(directory_handle.name)
    classic = load_classic_if3()
    receipt = load_source_receipt()
    interfaces = load_all_accepted_interfaces()
    loo = load_loo_robustness()
    box = classic.validity_box
    p = classic.params
    context = 2048
    kappa_fixture = receipt.kappa(context)
    n_max_law = fixture_law((1.0, 4.0), (0.5, 9.0))
    d_max_law = fixture_law((0.5, 9.0), (1.0, 4.0))

    def interfaces_section() -> None:
        check("accepted IF3 hash", classic.sha256 == ACCEPTED_CLASSIC_IF3_SHA256, "REGRESSION")
        check("all three interfaces carry their accepted hashes",
              {kind: item.sha256 for kind, item in interfaces.items()} == ACCEPTED_INTERFACE_SHA256, "REGRESSION")
        check("IF1 and IF2 are released as identity receipts only",
              isinstance(interfaces["IF1"], InterfaceIdentityReceipt) and isinstance(interfaces["IF2"], InterfaceIdentityReceipt),
              "REGRESSION")
        expect_raise("IF1 content cannot reach Q3 (no IF1 quality coordinate)", lambda: interfaces["IF1"].payload,
                     IdentityOnlyInterfaceError)
        expect_raise("IF2 content cannot reach Q3 (no canonical-loss or cross-scale use)", lambda: interfaces["IF2"].interface,
                     IdentityOnlyInterfaceError)
        check("IF1 keeps unmapped domains unimputed", interfaces["IF1"].scope["unmapped_mixture_domains"] > 0
              and interfaces["IF1"].scope["coverage_fraction"] < 1.0, "REGRESSION")
        check("IF2 scope receipt is 1M-only", interfaces["IF2"].scope["fit_scale"] == "1M"
              and interfaces["IF2"].scope["absolute_use_outside_1M"] == "PROHIBITED", "REGRESSION")
        check("accepted hashes are published in independent tracked upstream receipts",
              set(verify_accepted_hash_receipts()) == {"IF1", "IF2", "IF3"}, "ORACLE")
        if2 = accepted_payload("IF2")
        if2["fit_scale"] = "10B"
        path, digest = temp_json(temp, "if2-10b.json", if2)
        expect_raise("IF2 declared outside 1M is rejected",
                     lambda: load_accepted_interface("IF2", path, expected_sha256=digest), IF2ScopeError)
        if2 = accepted_payload("IF2")
        if2["validation"]["scope_release"]["limitations"]["absolute_use_outside_1M"] = "ALLOWED"
        path2, digest2 = temp_json(temp, "if2-outside.json", if2)
        expect_raise("IF2 absolute use outside 1M cannot be enabled",
                     lambda: load_accepted_interface("IF2", path2, expected_sha256=digest2), IF2ScopeError)
        if1 = accepted_payload("IF1")
        if1["mixture_to_quality"] = {domain: target or "imputed" for domain, target in if1["mixture_to_quality"].items()}
        path3, digest3 = temp_json(temp, "if1-imputed.json", if1)
        expect_raise("IF1 with imputed unmapped domains is rejected",
                     lambda: load_accepted_interface("IF1", path3, expected_sha256=digest3), AcceptedInterfaceError)
        if3 = accepted_payload("IF3")
        if3["validity_box"]["Q"] = [0.5, 1.0]
        path4, digest4 = temp_json(temp, "if3-q.json", if3)
        expect_raise("IF3 Q box must stay the [1, 1] no-quality sentinel",
                     lambda: load_classic_if3(path4, expected_sha256=digest4), ClassicIF3ContractError)
        for kind in ("IF1", "IF2", "IF3"):
            source = next(item.path for item in AUTHORIZED_Q3_INPUTS if item.key == "accepted_" + kind.lower())
            altered = temp / (kind + "-altered.json")
            altered.write_bytes(require_authorized_q3_input(source).read_bytes() + b"\n")
            expect_raise(kind + " altered bytes are rejected before parsing",
                         lambda altered=altered, kind=kind: load_accepted_interface(kind, altered), AcceptedInterfaceHashMismatch)
        expect_raise("altered IF3 is rejected by the classic loader", lambda: load_classic_if3(temp / "IF3-altered.json"),
                     AcceptedIF3HashMismatch)
        expect_raise("a missing interface is rejected", lambda: load_accepted_interface("IF1", temp / "absent.json"),
                     AcceptedInterfaceError)
        receipt_text = (TABLES / "q1-if1-summary.md").read_text(encoding="utf-8").replace(ACCEPTED_INTERFACE_SHA256["IF1"], "0" * 64)
        (temp / "if1-summary.md").write_text(receipt_text, encoding="utf-8")
        expect_raise("an upstream receipt lacking the accepted hash is rejected",
                     lambda: verify_accepted_hash_receipts({"IF1": temp / "if1-summary.md"}), AcceptedInterfaceError)

    def units_section() -> None:
        check("IF3 N box is in raw parameters", box["N"] == (70542000.0, 11965825000.0), "REGRESSION")
        check("IF3 D box is in raw tokens", close(box["D"][0], 1.34e8) and box["D"][1] == 299893000000.0, "REGRESSION")
        check("LOO trajectory labels are the IF3 N bounds in billions (independent sources agree)",
              close(float(loo.vectors[0].label) * 1e9, box["N"][0]) and close(float(loo.vectors[-1].label) * 1e9, box["N"][1]),
              "ORACLE")
        check("classic loss uses raw N and D", close(classic_loss(classic, 1e9, 1e10),
                                                     p["E"] + p["A"] * 1e9 ** -p["alpha"] + p["B"] * 1e10 ** -p["beta"]), "ORACLE")
        for label, quality in (("0.5", 0.5), ("1.0 (the IF3 sentinel value)", 1.0), ("'1'", "1"), ("True", True)):
            expect_raise("numeric quality " + label + " is rejected",
                         lambda quality=quality: BaselineCompute.create(receipt, 1e22, 4096, quality=quality), BaselineScopeError)

    def source_section() -> None:
        fresh = verify_source_values()
        check("the receipt's verification block equals a fresh DOCX verification", fresh == receipt.payload["source_verification"],
              "CONSISTENCY")
        check("every source record is VERIFIED", all(record["status"] == "VERIFIED" for record in fresh["records"]), "CONSISTENCY")
        check("DOCX budgets equal the specification's 1e19, 1e22, 1e24", receipt.budgets_flops == (1e19, 1e22, 1e24), "ORACLE")
        check("DOCX eta and coefficient equal the specification's 2e-4 and 6",
              receipt.eta == 2e-4 and receipt.base_coefficient == 6.0, "ORACLE")
        check("DOCX g(Q) coefficients equal the specification's audit expectations", receipt.quality_families == {
            "exponential": {"gamma": 1e7, "lambda": 6.0}, "power": {"gamma": 5e9, "lambda": 4.0},
            "logarithmic": {"gamma": 2e9, "lambda": 10.0}}, "ORACLE")
        check("receipt context grid equals an independent read of the C7 CSV",
              list(receipt.contexts_tokens) == independent_c7_grid() == [2048, 4096, 8192, 32768, 131072], "ORACLE")
        for label, paragraph, old, new in (("eta exponent", 34, "4", "5"), ("lambda 6.0", 49, "6.0", "7.0"),
                                           ("budget exponent", 29, "24", "25")):
            target = temp / ("mutated-" + str(paragraph) + ".docx")
            check("DOCX fixture changed " + label, mutate_docx(target, paragraph, old, new), "REGRESSION")
            expect_raise("a changed source " + label + " fails verification", lambda target=target: verify_source_values(target),
                         SourceVerificationError)
        expect_raise("DOCX verification rejects a PDF path", lambda: verify_source_values(temp / "problem.pdf"), ForbiddenQ3Input)
        inconsistent = SourceCheck("fixture_lambda", "w:body/w:p[49]", "fixture", (), "λ=6.0",
                                   lambda zone: parse_decimal(zone.split("=", 1)[1]), 7.0)
        expect_raise("a parsed source value that differs from its expectation is rejected",
                     lambda: _record(inconsistent, read_docx_blocks()), SourceVerificationError)

    def receipt_section() -> None:
        def rejected(name: str, mutate: Callable[[dict[str, Any]], None]) -> None:
            payload = json.loads(json.dumps(receipt.payload))
            mutate(payload)
            path, _ = temp_json(temp, "receipt-" + str(len(RESULTS)) + ".json", payload)
            expect_raise(name, lambda: load_source_receipt(path), SourceReceiptError)

        for case, (description, _) in FORGERIES.items():
            rejected(case + " forged receipt rejected by the consumer: " + description,
                     lambda item, case=case: item.update(forged_receipt(case, item)))
        rejected("receipt domain mutation is rejected", lambda item: _term(item, "quality_domain").update(lower_inclusive=True))
        rejected("receipt numeric Q0 is rejected", lambda item: _term(item, "quality_baseline_Q0").update(numeric_global_Q0=0.5))
        rejected("an UNVERIFIED source record is rejected",
                 lambda item: item["source_verification"]["records"][0].update(status="UNVERIFIED"))
        rejected("a receipt bound to another DOCX is rejected", lambda item: item["source_verification"].update(docx_sha256="0" * 64))
        rejected("a dropped source record is rejected", lambda item: item["source_verification"]["records"].pop())
        rejected("the baseline gate cannot be blocked",
                 lambda item: item["gates"]["canonical_baseline_nd_allocation"].update(result="BLOCKED"))
        rejected("the nonbaseline gate cannot be opened",
                 lambda item: item["gates"]["nonbaseline_quality_cost_scenarios"].update(result="PASS"))
        rejected("the cross-scale gate cannot be opened",
                 lambda item: item["gates"]["cross_scale_quality_benefit"].update(result="PASS"))
        path, _ = temp_json(temp, "receipt-genuine.json", receipt.payload)
        check("control: an unmodified copy of the receipt is accepted", load_source_receipt(path).contexts_tokens
              == receipt.contexts_tokens, "BOUNDARY")

    def guard_section() -> None:
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
              and not any(str(item.path).lower().endswith(".pdf") for item in AUTHORIZED_Q3_INPUTS), "REGRESSION")
        original = temp / "data_description.original.pdf"
        sanitized = temp / "data_description.sanitized.m2.pdf"
        original.write_bytes(b"harmless fixture, not the quarantined document\n")
        sanitized.write_bytes(b"harmless fixture, not the sanitized derivative\n")
        check("guard: opening a PDF-named fixture is refused", probe("open_read", original)[0] == "FORBIDDEN", "BOUNDARY")
        check("guard: hashing a PDF-named fixture is refused", probe("hash", sanitized)[0] == "FORBIDDEN", "BOUNDARY")
        check("guard: control fixture with a non-PDF name opens", probe("open_read", temp / "if1-summary.md")[0] == "NO_EXCEPTION",
              "BOUNDARY")
        check("guard: opening B8 is refused before the filesystem is touched", probe("open_read", B8_PATH)[0] == "UNAUTHORIZED",
              "BOUNDARY")
        check("guard: listing a local input directory is refused", probe("listdir", ATT_C)[0] == "FORBIDDEN", "BOUNDARY")
        check("guard: scanning a local input directory is refused", probe("scandir", ATT_C)[0] == "FORBIDDEN", "BOUNDARY")
        check("guard: opening C7 for writing is refused", probe("open_readwrite", C7_PATH)[0] == "FORBIDDEN", "BOUNDARY")
        status, record = probe("workflow", "-")
        reads = set(record["guard"]["reads"]) if record else set()
        check("guard: the authorized workflow runs with the guard active", status == "NO_EXCEPTION" and record is not None, "BOUNDARY")
        check("guard: the workflow had no denials", record is not None and record["guard"]["denied"] == [], "BOUNDARY")
        check("guard: the workflow opened only allowlisted inputs, including the receipt consumer's own sources",
              reads and reads <= {item.key for item in AUTHORIZED_Q3_INPUTS}
              and {"canonical_problem_statement_docx", "c7_model_architecture_metadata", "intake_sha256_manifest"} <= reads,
              "BOUNDARY")
        check("guard: the workflow reaches the corrected 1e24 regime", record is not None and record["regime"] == "SLACK:N_max+D_max",
              "REGRESSION")

    def compute_section() -> None:
        compute = BaselineCompute.create(receipt, 1e19, 2048)
        interior = solve_baseline(classic, compute)
        cost = cost_breakdown(compute, interior.n_parameters, interior.d_tokens)
        check("kappa = 6 + eta L_ctx", compute.kappa == 6.0 + 2e-4 * 2048, "ORACLE")
        check("components reconcile with kappa N D", close(cost["base_flops"] + cost["attention_flops"],
                                                           compute.kappa * interior.n_parameters * interior.d_tokens), "ORACLE")
        check("quality compute and share are exactly zero at Q0", cost["quality_flops"] == 0.0 and cost["quality_share_of_spent"] == 0.0
              and compute.delta_g_flops_per_token == 0.0, "REGRESSION")
        check("shares of spent compute sum to one", close(cost["base_share_of_spent"] + cost["attention_share_of_spent"], 1.0),
              "CONSISTENCY")
        check("base share of spent is 6/kappa", close(cost["base_share_of_spent"], 6.0 / compute.kappa), "ORACLE")
        check("cost parity identity 6/eta = 30000 gives equal shares", receipt.parity_tokens == 30000.0
              and close(6.0 / (6.0 + receipt.eta * receipt.parity_tokens), 0.5), "ORACLE")
        check("interior budget saturates", interior.regime == "SATURATED:interior" and close(interior.spent_flops, 1e19), "REGRESSION")
        oracle = pure_nd_oracle(classic, compute.budget_flops, compute.kappa)
        check("closed form equals the independent src.scaling oracle",
              close(interior.n_parameters, oracle["N_star"]) and close(interior.d_tokens, oracle["D_star"]), "ORACLE")
        alpha, beta, a, b = p["alpha"], p["beta"], p["A"], p["B"]
        budget, kappa = compute.budget_flops, compute.kappa

        def slice_derivative(log_n: float) -> float:
            n_value = math.exp(log_n)
            return -alpha * a * n_value ** -alpha + beta * b * (budget / (kappa * n_value)) ** -beta

        root = math.exp(brentq(slice_derivative, math.log(1e6), math.log(1e12), xtol=1e-15, rtol=4.0 * 2.0**-52))
        check("numerical root of the stationary condition equals the closed form", close(root, interior.n_parameters, 1e-12), "ORACLE")
        check("closed form satisfies N^(alpha+beta) = alpha A/(beta B) (C/kappa)^beta",
              close(interior.n_parameters ** (alpha + beta), alpha * a / (beta * b) * (budget / kappa) ** beta, 1e-12), "ORACLE")
        check("relative stationary residual vanishes at the interior optimum",
              abs(interior.stationary_residual_relative) < 1e-12, "CONSISTENCY")
        for budget_value, expected in ((1e19, "SATURATED:interior"), (1e22, "SATURATED:D_max"), (1e24, "SLACK:N_max+D_max")):
            agreement = solve_baseline_numeric(classic, BaselineCompute.create(receipt, budget_value, 4096))
            check("numerical search agrees at " + format(budget_value, ".0e"),
                  agreement.analytic.regime == expected and agreement.n_relative_difference <= 1e-6
                  and agreement.d_relative_difference <= 1e-6 and agreement.loss_relative_difference <= 1e-11
                  and agreement.analytic_not_improved, "ORACLE")
            result = agreement.analytic
            grid = brute_force(classic, result.compute.kappa, budget_value)
            check("brute-force 2-D grid never beats the solver at " + format(budget_value, ".0e"),
                  result.predicted_loss <= grid["loss"] * (1.0 + 1e-12)
                  and (grid["loss"] - result.predicted_loss) / result.predicted_loss < 1e-3
                  and abs(math.log(grid["n"] / result.n_parameters)) < 0.1 and abs(math.log(grid["d"] / result.d_tokens)) < 0.1,
                  "ORACLE")

    def inequality_section() -> None:
        high = solve_baseline(classic, BaselineCompute.create(receipt, 1e24, 4096))
        kappa = receipt.kappa(4096)
        c_box = kappa * box["N"][1] * box["D"][1]
        check("1e24 is the upper corner with budget slack", high.regime == "SLACK:N_max+D_max"
              and high.n_parameters == box["N"][1] and high.d_tokens == box["D"][1], "ORACLE")
        check("1e24 unused budget is 1e24 - kappa N_max D_max", close(high.unused_budget_flops, 1e24 - c_box)
              and close(high.compute_utilization, c_box / 1e24), "ORACLE")
        check("1e24 shares of spent differ from fractions of budget",
              close(high.cost["base_fraction_of_budget"], high.cost["base_share_of_spent"] * c_box / 1e24), "CONSISTENCY")
        check("1e24 stationary point is outside the box and diagnostic only", not high.stationary_point_in_validity_box
              and high.stationary_residual_relative is None, "REGRESSION")
        medium = solve_baseline(classic, BaselineCompute.create(receipt, 1e22, 4096))
        check("1e22 at 4096 is D_max-bound and saturating", medium.regime == "SATURATED:D_max" and medium.d_tokens == box["D"][1]
              and close(medium.n_parameters, 1e22 / (kappa * box["D"][1])), "ORACLE")
        check("1e22 stationary point lies outside the box", not medium.stationary_point_in_validity_box, "REGRESSION")
        previous, monotone, feasible = math.inf, True, True
        for index in range(201):
            value = 1e19 * 10.0 ** (5.0 * index / 200.0)
            try:
                result = solve_baseline(classic, BaselineCompute.continuation(receipt, value, 4096))
            except NoValidityBoxAllocation:
                feasible = False
                continue
            monotone = monotone and result.predicted_loss <= previous * (1.0 + 1e-15)
            previous = result.predicted_loss
        check("every budget in the declared span is feasible", feasible, "REGRESSION")
        check("minimum loss is non-increasing in the budget (feasible sets are nested)", monotone, "ORACLE")

    def fixture_section() -> None:
        def fixture_solve(law: SensitivityClassicLaw, ratio: float):
            return solve_baseline(law, BaselineCompute(receipt, ratio * kappa_fixture, context, kappa_fixture, "self_test_fixture"))

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
            agreement = solve_baseline_numeric(law, BaselineCompute(receipt, ratio * kappa_fixture, context, kappa_fixture,
                                                                    "self_test_fixture"))
            check("fixture C/kappa=" + format(ratio, "g") + " gives hand-derived " + regime,
                  result.regime == regime and close(result.n_parameters, n_expected, 1e-9) and close(result.d_tokens, d_expected, 1e-9)
                  and agreement.n_relative_difference <= 1e-6 and agreement.analytic_not_improved, "ORACLE")
        slack = fixture_solve(n_max_law, 72.0)
        check("fixture slack keeps half the budget unused", close(slack.unused_budget_flops, 36.0 * kappa_fixture)
              and close(slack.compute_utilization, 0.5), "ORACLE")
        expect_raise("fixture below C_min is genuinely infeasible", lambda: fixture_solve(n_max_law, 0.49), NoValidityBoxAllocation,
                     "ORACLE")
        previous, monotone = math.inf, True
        for index in range(301):
            result = fixture_solve(n_max_law, 0.5 * 10.0 ** (3.0 * index / 300.0))
            monotone = monotone and result.predicted_loss <= previous * (1.0 + 1e-15)
            previous = result.predicted_loss
        check("fixture minimum loss is non-increasing from C_min to beyond C_box", monotone, "ORACLE")

    def regime_section() -> None:
        for context_value in receipt.contexts_tokens:
            analysis = analyze_regime_thresholds(classic, receipt, context_value)
            retained = [(item.name, item.below["regime"], item.above["regime"]) for item in analysis.retained]
            check("L_ctx=" + str(context_value) + ": transitions are the D_max onset and the C_box slack onset",
                  retained == [("stationary_reaches_D_max", "SATURATED:interior", "SATURATED:D_max"),
                               ("C_box", "SATURATED:D_max", "SLACK:N_max+D_max")], "REGRESSION")
            check("L_ctx=" + str(context_value) + ": numerical elasticities match each regime's analytic elasticities",
                  all(abs(interval.numeric_n_elasticity - interval.analytic_n_elasticity) < 1e-6
                      and abs(interval.numeric_d_elasticity - interval.analytic_d_elasticity) < 1e-6 for interval in analysis.regime_map),
                  "ORACLE")
            dispositions = {item.name: item.disposition for item in analysis.thresholds}
            check("L_ctx=" + str(context_value) + ": out-of-span candidates are recorded, not analysed",
                  dispositions["C_min"] == dispositions["stationary_reaches_N_min"] == "OUTSIDE_DECLARED_SPAN_NOT_ANALYSED", "REGRESSION")
        analysis = analyze_regime_thresholds(classic, receipt, 4096)
        threshold = next(item for item in analysis.retained if item.name == "stationary_reaches_D_max")
        check("D_max threshold equals its closed form",
              close(threshold.budget_flops, stationary_threshold(p, receipt.kappa(4096), "D", box["D"][1])), "CONSISTENCY")
        kappa = receipt.kappa(4096)
        c_box = kappa * box["N"][1] * box["D"][1]
        below, above = brute_force(classic, kappa, 0.8 * threshold.budget_flops), brute_force(classic, kappa, 1.25 * threshold.budget_flops)
        check("brute force confirms the D_max transition: D below D_max before it, D = D_max after it",
              below["d"] < 0.99 * box["D"][1] and above["d"] == box["D"][1], "ORACLE")
        before, after = brute_force(classic, kappa, 0.8 * c_box), brute_force(classic, kappa, 1.25 * c_box)
        check("brute force confirms slack onset at C_box: spends the budget before it, the corner with slack after it",
              before["spent"] > 0.99 * 0.8 * c_box and after["n"] == box["N"][1] and after["d"] == box["D"][1]
              and close(after["spent"], c_box, 1e-12), "ORACLE")
        check("a budget inside one regime is not reported as a transition", probe_budget(classic, receipt, 4096, 1e20)[3] is False
              and probe_budget(classic, receipt, 4096, threshold.budget_flops)[3] is True, "BOUNDARY")
        expect_raise("continuation below the declared span is refused", lambda: BaselineCompute.continuation(receipt, 1e18, 4096),
                     SourceReceiptError)
        expect_raise("continuation above the declared span is refused", lambda: BaselineCompute.continuation(receipt, 2e24, 4096),
                     SourceReceiptError)
        check("continuation budgets are labelled", BaselineCompute.continuation(receipt, 2e20, 4096).budget_role == CONTINUATION
              and BaselineCompute.create(receipt, 1e22, 4096).budget_role == SOURCE_SUPPORTED, "REGRESSION")
        expect_raise("an unsupported primary budget is refused", lambda: BaselineCompute.create(receipt, 2e20, 4096), SourceReceiptError)
        expect_raise("an unobserved context is refused", lambda: BaselineCompute.create(receipt, 1e22, 30000), SourceReceiptError)
        expect_raise("continuation cannot extend the context grid to 262144",
                     lambda: BaselineCompute.continuation(receipt, 1e22, 262144), SourceReceiptError)
        fixture_receipt = dataclasses.replace(receipt, budgets_flops=(0.25 * kappa_fixture, 10.0 * kappa_fixture, 100.0 * kappa_fixture))
        for law, low_bound, expected in (
            (n_max_law, "N_min", [("C_min", "INFEASIBLE", "SATURATED:N_min"),
                                  ("stationary_reaches_N_min", "SATURATED:N_min", "SATURATED:interior"),
                                  ("stationary_reaches_N_max", "SATURATED:interior", "SATURATED:N_max"),
                                  ("C_box", "SATURATED:N_max", "SLACK:N_max+D_max")]),
            (d_max_law, "D_min", [("C_min", "INFEASIBLE", "SATURATED:D_min"),
                                  ("stationary_reaches_D_min", "SATURATED:D_min", "SATURATED:interior"),
                                  ("stationary_reaches_D_max", "SATURATED:interior", "SATURATED:D_max"),
                                  ("C_box", "SATURATED:D_max", "SLACK:N_max+D_max")]),
        ):
            fixture_analysis = analyze_regime_thresholds(law, fixture_receipt, context)
            found = [(item.name, item.below["regime"], item.above["regime"]) for item in fixture_analysis.retained]
            check("fixture transitions and both neighbouring regimes match the hand derivation (" + low_bound + ")", found == expected,
                  "ORACLE")
            check("fixture regime map starts infeasible below C_min (" + low_bound + ")",
                  fixture_analysis.regime_map[0].regime == "INFEASIBLE", "ORACLE")
            at_corners = [item.at["regime"] for item in fixture_analysis.retained if item.name in ("C_min", "C_box")]
            check("fixture corners are exactly saturating, including C = C_box (" + low_bound + ")",
                  at_corners == ["SATURATED:N_min+D_min", "SATURATED:N_max+D_max"], "ORACLE")

    def loo_section() -> None:
        accepted_blob = git("rev-parse", ACCEPTED_T008_COMMIT + ":" + LOO_RELATIVE).decode("ascii").strip()
        check("LOO: bound to the Git blob of the accepted T-008 commit (independent git rev-parse)",
              loo.git_blob_id == accepted_blob == "d32cdfd87f5fea9ac56f68aef0f9fc8d574c2020"
              and loo.accepted_commit == ACCEPTED_T008_COMMIT, "ORACLE")
        blob = git("cat-file", "blob", accepted_blob)
        check("LOO: content hash is of the Git blob bytes", loo.blob_content_sha256 == hashlib.sha256(blob).hexdigest(), "ORACLE")
        expect_raise("LOO: a tracked input has no working-copy byte identity", lambda: sha256_authorized_q3_input(LOO_PATH),
                     TrackedInputIdentityError)
        other_blob = git("rev-parse", "HEAD:README.md").decode("ascii").strip()
        pinned = ACCEPTED_TRACKED_BLOBS["accepted_q2_loo_evidence"]
        try:
            ACCEPTED_TRACKED_BLOBS["accepted_q2_loo_evidence"] = (pinned[0], other_blob)
            expect_raise("LOO: an existing blob other than the pinned one is rejected", load_loo_robustness, TrackedInputIdentityError)
        finally:
            ACCEPTED_TRACKED_BLOBS["accepted_q2_loo_evidence"] = pinned
        markdown = blob.decode("utf-8")
        check("LOO: eight complete ordered vectors", len(loo.vectors) == 8
              and all(tuple(v.parameters) == ("E", "A", "alpha", "B", "beta") for v in loo.vectors), "REGRESSION")
        check("LOO: label states published precision",
              loo.precision_label == "leave-one-trajectory-out robustness at published parameter precision", "REGRESSION")
        check("LOO: half unit of 406.26 is 0.0005 (six significant digits)",
              close(next(v for v in loo.vectors if v.published_strings["A"] == "406.26").half_units()["A"], 0.0005), "ORACLE")
        check("LOO: limitation rejects a probabilistic reading", "not a confidence interval" in loo.limitation and "B1" in loo.limitation,
              "REGRESSION")
        models = build_loo_sensitivity_models(classic, loo)
        check("LOO: nominal model is the accepted object itself", models[0].law is classic, "REGRESSION")
        check("LOO: alternative fits are not presented as the accepted IF3",
              all(not model.law.is_accepted_if3 and not hasattr(model.law, "sha256") for model in models[1:]), "REGRESSION")
        check("LOO: alternatives keep the accepted validity box", all(model.law.validity_box == classic.validity_box for model in models[1:]),
              "REGRESSION")
        check("LOO: 32 rounding corners per vector", len(rounding_corner_laws(classic, loo.vectors[0])) == 32, "REGRESSION")
        lines = markdown.splitlines()
        rows = [index for index, line in enumerate(lines) if line.startswith("| 0.070542 ") or line.startswith("| 0.162405 ")]
        swapped = list(lines)
        swapped[rows[0]], swapped[rows[1]] = swapped[rows[1]], swapped[rows[0]]
        expect_raise("LOO: reordered vectors are rejected", lambda: _parse_vectors("\n".join(swapped)), LOORobustnessError)
        expect_raise("LOO: a missing vector is rejected",
                     lambda: _parse_vectors("\n".join(line for index, line in enumerate(lines) if index != rows[0])), LOORobustnessError)
        expect_raise("LOO: a non-canonical printed value is rejected",
                     lambda: _parse_vectors(markdown.replace("| 406.636 |", "| 406.6360 |")), LOORobustnessError)
        wrong_fit = dataclasses.replace(loo, published_full_fit=PublishedParameterVector(
            "published_full_fit", {**loo.published_full_fit.parameters, "E": 1.68983},
            {**loo.published_full_fit.published_strings, "E": "1.68983"}))
        expect_raise("LOO: a full fit that is not the accepted IF3 is rejected",
                     lambda: require_published_full_fit_matches(classic, wrong_fit), LOORobustnessError)
        payload = json.loads((TABLES / "q3-loo-robustness.json").read_text(encoding="utf-8"))
        check("LOO artifact: 150 individual outcomes and 15 summaries", len(payload["rows"]) == 150 and len(payload["summaries"]) == 15,
              "ARTIFACT")
        check("LOO artifact: classified as robustness, not confidence", "not confidence" in payload["claim_level"], "ARTIFACT")
        check("LOO artifact: every primary point has one regime across all fits",
              all(item["regime_agreement"] for item in payload["summaries"]), "ARTIFACT")
        check("LOO artifact: upper-corner N and D ranges are degenerate",
              all(item["n_parameters_raw"]["rounding"]["verdict"] == "DEGENERATE_FIXED_BY_BOUNDS"
                  for item in payload["summaries"] if item["budget_flops"] == 1e24), "ARTIFACT")
        check("LOO artifact: bound to the accepted Git blob", payload["loo_evidence"]["git_blob_id"] == accepted_blob, "ARTIFACT")

    def quality_section() -> None:
        analysis = raw_family_analysis(receipt.quality_families, receipt.quality_domain)
        families = receipt.quality_families
        g = {
            "exponential": lambda q: families["exponential"]["gamma"] * np.exp(families["exponential"]["lambda"] * q),
            "power": lambda q: families["power"]["gamma"] * q ** families["power"]["lambda"],
            "logarithmic": lambda q: families["logarithmic"]["gamma"] * np.log1p(families["logarithmic"]["lambda"] * q),
        }
        q_grid = np.unique(np.concatenate([np.geomspace(1e-12, 1.0, 200001), np.linspace(1e-9, 1.0, 1000001)]))
        independent: dict[str, list[float]] = {}
        for pair in analysis["pairs"]:
            left, right = pair["pair"]
            difference = g[left](q_grid) - g[right](q_grid)
            changes = np.nonzero(np.sign(difference[:-1]) * np.sign(difference[1:]) < 0)[0]
            independent[left + "/" + right] = [
                brentq(lambda q: float(g[left](q) - g[right](q)), float(q_grid[i]), float(q_grid[i + 1]), xtol=1e-15)
                for i in changes]
        check("quality: independent dense-grid root finding gives the same crossing count per pair",
              [len(independent[pair["pair"][0] + "/" + pair["pair"][1]]) for pair in analysis["pairs"]]
              == [pair["crossing_count"] for pair in analysis["pairs"]] == [1, 1, 1], "ORACLE")
        check("quality: independent roots agree with the reported crossings to 1e-9",
              all(close(found, reported["q"], 1e-9) for pair in analysis["pairs"]
                  for found, reported in zip(independent[pair["pair"][0] + "/" + pair["pair"][1]], pair["crossings"])), "ORACLE")
        check("quality: four ordering intervals on (0, 1]", len(analysis["interval_ordering"]) == 4, "CONSISTENCY")
        check("quality: the Q->0+ limits are the analytic ones", analysis["families"]["exponential"]["limit_q_to_0_plus_flops_per_token"] == 1e7
              and analysis["families"]["power"]["limit_q_to_0_plus_flops_per_token"] == 0.0, "ORACLE")
        two_roots = raw_family_analysis({**families, "exponential": {"gamma": 1.5e7, "lambda": 6.0}}, receipt.quality_domain)
        check("quality: a hand-derived convex pair with two crossings is fully resolved", two_roots["pairs"][0]["crossing_count"] == 2,
              "ORACLE")
        near_one = raw_family_analysis({**families, "power": {"gamma": 2e9 * math.log(11.0) * (1.0 + 1e-9), "lambda": 4.0}},
                                       receipt.quality_domain)
        check("quality: a hand-placed crossing within 1e-9 of Q = 1 is found", near_one["pairs"][2]["crossing_count"] == 1
              and 1.0 - near_one["pairs"][2]["crossings"][0]["q"] < 1e-8, "ORACLE")
        expect_raise("quality: a domain admitting Q = 0 is refused",
                     lambda: raw_family_analysis(families, {**receipt.quality_domain, "lower_inclusive": True}), ValueError)
        payload = json.loads((TABLES / "q3-quality-cost-sensitivity.json").read_text(encoding="utf-8"))
        check("quality: raw comparison done while nonbaseline allocation stays blocked",
              payload["raw_g_comparison"] == "DONE" and payload["nonbaseline_gate"]["result"] == "BLOCKED_UNTIL_Q0_DECLARED"
              and payload["numeric_nonbaseline_scenarios_ran"] is False and payload["quality_optimization_ran"] is False, "ARTIFACT")

    def ledger_section() -> None:
        ledger = json.loads((TABLES / "q3-provenance-ledger.json").read_text(encoding="utf-8"))["items"]
        check("ledger: generated ledger validates", validate_ledger(ledger) == len(ledger) and len(ledger) > 30, "ARTIFACT")
        s1 = next(item for item in ledger if item["id"] == "S1")
        check("ledger: budget inequality states saturation through C = C_box", "C_min <= C <= C_box" in s1["limitation"]
              and "C > C_box" in s1["limitation"], "ARTIFACT")

        def rejected(name: str, mutate: Callable[[list[dict[str, Any]]], None]) -> None:
            items = json.loads(json.dumps(ledger))
            mutate(items)
            expect_raise(name, lambda: validate_ledger(items), ProvenanceError)

        def only_source(kind: str, path: str) -> Callable[[list[dict[str, Any]]], None]:
            return lambda items: items[0].update(sources=[{"kind": kind, "path": path, "sha256": "0" * 64}])

        rejected("ledger: PDF-only provenance is rejected", only_source("pdf", "docs_local/problem-f/source/data_description.original.pdf"))
        rejected("ledger: a PDF path relabelled as the DOCX is rejected",
                 only_source("canonical_docx", "docs_local/problem-f/audit/data_description.sanitized.m2.pdf"))
        rejected("ledger: screenshot-only provenance is rejected", only_source("screenshot", "scratch/capture.png"))
        rejected("ledger: an AI-produced intermediate is rejected", only_source("ai_intermediate", "scratch/notes.md"))
        rejected("ledger: an absolute path is rejected", only_source("canonical_docx", "/fixture-root/problem_statement.docx"))
        rejected("ledger: an UNVERIFIED item blocks acceptance", lambda items: items[0].update(status="UNVERIFIED"))
        rejected("ledger: a missing limitation is rejected", lambda items: items[0].pop("limitation"))
        rejected("ledger: a purely derived item cannot claim VERIFIED",
                 lambda items: next(item for item in items if item["id"] == "C2").update(status="VERIFIED"))

    def artifact_section() -> None:
        allocation = json.loads((TABLES / "q3-allocation.json").read_text(encoding="utf-8"))
        regimes = {row["budget_flops"]: row["regime"] for row in allocation["allocations"]}
        check("artifact: canonical regimes at 1e19/1e22/1e24", regimes == {1e19: "SATURATED:interior", 1e22: "SATURATED:D_max",
                                                                         1e24: "SLACK:N_max+D_max"}, "ARTIFACT")
        check("artifact: every numerical check passed", all(row["numerical_check"]["result"] == "PASS"
                                                            for row in allocation["allocations"]), "ARTIFACT")
        text = "".join(path.read_text(encoding="utf-8") for path in sorted(TABLES.glob("q3-*"))
                       if path.name != "q3-mutation-validation.md" and path.name != "q3-mutation-validation.json")
        check("artifact: the withdrawn NO_VALIDITY_BOX_ALLOCATION disposition is gone", "NO_VALIDITY_BOX_ALLOCATION" not in text,
              "ARTIFACT")
        check("artifact: no strict C < C_box saturation wording remains", "only while `C < C_box" not in text
              and "only for C < C_box" not in text, "ARTIFACT")
        context_payload = json.loads((TABLES / "q3-context-sensitivity.json").read_text(encoding="utf-8"))
        check("artifact: observed contexts bracket the 1e22 D_max change", [
            (item["budget_flops"], item["lower_observed_context_tokens"], item["upper_observed_context_tokens"])
            for item in context_payload["observed_context_brackets"]] == [(1e22, 4096, 8192)], "ARTIFACT")
        check("reject_forbidden_q3_input is lexical", reject_forbidden_q3_input(temp / "plain.json") == temp / "plain.json",
              "REGRESSION")

    for title, body in (
        ("interfaces", interfaces_section), ("units", units_section), ("source verification", source_section),
        ("receipt forgery", receipt_section), ("input guard", guard_section), ("compute and closed form", compute_section),
        ("budget inequality", inequality_section), ("fixtures", fixture_section), ("regimes", regime_section),
        ("LOO", loo_section), ("quality", quality_section), ("ledger", ledger_section), ("artifacts", artifact_section),
    ):
        section(title, body)

    directory_handle.cleanup()
    for name, category, passed in RESULTS:
        print(("PASS" if passed else "FAIL") + " [" + category + "] " + name)
    counts = {category: sum(1 for _, item, _ in RESULTS if item == category) for category in CATEGORIES}
    print("CATEGORIES " + json.dumps(counts, sort_keys=True))
    failures = [name for name, _, passed in RESULTS if not passed]
    count_ok = len(RESULTS) == EXPECTED_CHECKS
    if report_path:
        Path(report_path).write_text(json.dumps({
            "checks": [{"name": name, "category": category, "passed": passed} for name, category, passed in RESULTS],
            "category_counts": counts, "expected_checks": EXPECTED_CHECKS, "count_ok": count_ok,
            "failures": failures}, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if not count_ok:
        print("FAIL [REGRESSION] check count: expected " + str(EXPECTED_CHECKS) + ", got " + str(len(RESULTS)))
        return 1
    if failures:
        print("FAIL " + str(len(failures)) + " of " + str(len(RESULTS)) + " checks", file=sys.stderr)
        return 1
    print("PASS " + str(len(RESULTS)) + " checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
