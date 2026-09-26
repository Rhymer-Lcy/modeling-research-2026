"""Executable checks for the receipt-bound T-010 baseline allocation lane.

The checks include deliberate in-memory and temporary-file mutations. They never
alter accepted interfaces, source inputs, or the frozen generated receipt.

Run through the declared environment:
    conda run -n modeling-research-2026 --no-capture-output python scripts/q3_selftest.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from src.alloc import (  # noqa: E402
    ACCEPTED_CLASSIC_IF3_SHA256,
    AcceptedIF3HashMismatch,
    AllocationBox,
    BaselineCompute,
    BaselineScopeError,
    NoValidityBoxAllocation,
    SourceReceiptError,
    cost_breakdown,
    describe_allocation_uncertainty,
    load_classic_if3,
    load_source_receipt,
    solve_baseline,
    solve_baseline_numeric,
)
from src.alloc.classic import baseline_closed_form, pure_nd_oracle  # noqa: E402

RESULTS: list[tuple[str, bool]] = []


def check(name: str, condition: bool) -> None:
    RESULTS.append((name, bool(condition)))


def expect_raise(name: str, fn: Callable[[], object], exc_type: type[BaseException]) -> None:
    try:
        fn()
    except exc_type:
        check(name, True)
    except Exception:
        check(name, False)
    else:
        check(name, False)


def close(left: float, right: float, rel: float = 1e-10, abs_tol: float = 1e-8) -> bool:
    return math.isclose(left, right, rel_tol=rel, abs_tol=abs_tol)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def receipt_mutation(payload: dict[str, object], mutate: Callable[[dict[str, object]], None]) -> Callable[[], object]:
    def run() -> object:
        altered = json.loads(json.dumps(payload))
        mutate(altered)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            write_json(path, altered)
            return load_source_receipt(path)
    return run


def classic_mutation(path: Path) -> Callable[[], object]:
    def run() -> object:
        altered = Path(tempfile.gettempdir()) / "t010-altered-if3.json"
        altered.write_bytes(path.read_bytes() + b"\n")
        try:
            return load_classic_if3(altered)
        finally:
            altered.unlink(missing_ok=True)
    return run


def main() -> int:
    classic = load_classic_if3()
    receipt = load_source_receipt()
    check("accepted IF3 hash", classic.sha256 == ACCEPTED_CLASSIC_IF3_SHA256)
    check("accepted IF3 raw bytes", hashlib.sha256(classic.path.read_bytes()).hexdigest() == classic.sha256)
    check("receipt supported budgets", receipt.budgets_flops == (1e19, 1e22, 1e24))
    check("receipt observed contexts", receipt.contexts_tokens == (2048, 4096, 8192, 32768, 131072))
    check("receipt parity identity", close(receipt.parity_tokens, 6.0 / receipt.eta, rel=0.0, abs_tol=1e-12))

    expect_raise("accepted IF3 byte mutation rejected", classic_mutation(classic.path), AcceptedIF3HashMismatch)
    expect_raise("unsupported budget rejected", lambda: BaselineCompute.create(receipt, 2e20, 4096), SourceReceiptError)
    expect_raise("unsupported context rejected", lambda: BaselineCompute.create(receipt, 1e22, 30000), SourceReceiptError)
    expect_raise("nonbaseline quality rejected", lambda: BaselineCompute.create(receipt, 1e22, 4096, quality=0.5), BaselineScopeError)
    expect_raise("numeric quality label rejected", lambda: BaselineCompute.create(receipt, 1e22, 4096, quality="1"), BaselineScopeError)

    receipt_payload = dict(receipt.payload)
    expect_raise(
        "receipt baseline gate mutation rejected",
        receipt_mutation(receipt_payload, lambda item: item["gates"]["canonical_baseline_nd_allocation"].update({"result": "BLOCKED"})),
        SourceReceiptError,
    )
    expect_raise(
        "receipt quality gate mutation rejected",
        receipt_mutation(receipt_payload, lambda item: item["gates"]["nonbaseline_quality_cost_scenarios"].update({"result": "PASS"})),
        SourceReceiptError,
    )
    expect_raise(
        "receipt cross-scale gate mutation rejected",
        receipt_mutation(receipt_payload, lambda item: item["gates"]["cross_scale_quality_benefit"].update({"result": "PASS"})),
        SourceReceiptError,
    )
    expect_raise(
        "receipt numeric Q0 mutation rejected",
        receipt_mutation(
            receipt_payload,
            lambda item: next(term for term in item["terms"] if term["name"] == "quality_baseline_Q0")
            ["supported_value_or_grid"].update({"numeric_global_Q0": 0.5}),
        ),
        SourceReceiptError,
    )

    compute = BaselineCompute.create(receipt, 1e22, 4096)
    result = solve_baseline(classic, compute)
    agreement = solve_baseline_numeric(classic, compute)
    breakdown = cost_breakdown(compute, result.n_parameters, result.d_tokens)
    check("baseline quality coordinate", compute.quality_coordinate == "Q0")
    check("baseline delta_g exactly zero", compute.delta_g_flops_per_token == 0.0)
    check("budget saturates", close(result.cost["total_flops"], compute.budget_flops, rel=1e-12, abs_tol=1e-3))
    check("budget residual", close(result.budget_saturation_residual_flops, 0.0, rel=0.0, abs_tol=1e-3))
    check("quality cost exactly zero", breakdown["quality_flops"] == 0.0 and breakdown["quality_share"] == 0.0)
    check("cost shares reconcile", close(breakdown["base_share"] + breakdown["attention_share"] + breakdown["quality_share"], 1.0))
    check("analytic numeric N agreement", agreement.n_relative_difference <= 1e-10)
    check("analytic numeric D agreement", agreement.d_relative_difference <= 1e-10)
    check("analytic numeric loss agreement", agreement.loss_relative_difference <= 1e-12)
    check("canonical point is valid", bool(result.validity_labels["in_validity_box"]))
    check("reported boundary is recognized", result.active_boundary in {"none", "N_min", "N_max", "D_min", "D_max"})

    unconstrained_n, unconstrained_d = baseline_closed_form(classic, compute.budget_flops, compute.kappa)
    oracle = pure_nd_oracle(classic, compute.budget_flops, compute.kappa)
    check("closed-form oracle N agreement", close(unconstrained_n, oracle["N_star"], rel=1e-12))
    check("closed-form oracle D agreement", close(unconstrained_d, oracle["D_star"], rel=1e-12))

    interior_compute = BaselineCompute.create(receipt, 1e19, 2048)
    interior = solve_baseline(classic, interior_compute)
    check("interior stationary solution exists", interior.active_boundary == "none")
    check("interior stationary residual", abs(interior.stationary_residual) <= 1e-10)

    normal_box = AllocationBox.derive(classic, compute)
    check("validity interval ordered", normal_box.n_lower <= normal_box.n_upper)

    from dataclasses import replace
    constrained_n_min = replace(classic, law=replace(classic.law, validity_box={
        "N": [result.n_parameters * 1.01, result.n_parameters * 1.02],
        "D": [1.0, 1e20],
        "Q": [1.0, 1.0],
    }))
    n_min_box = AllocationBox.derive(constrained_n_min, compute)
    check("N_min boundary classified", n_min_box.active_boundary(n_min_box.n_lower) == "N_min")

    constrained_n_max = replace(classic, law=replace(classic.law, validity_box={
        "N": [1.0, result.n_parameters * 0.99],
        "D": [1.0, 1e20],
        "Q": [1.0, 1.0],
    }))
    n_max_box = AllocationBox.derive(constrained_n_max, compute)
    check("N_max boundary classified", n_max_box.active_boundary(n_max_box.n_upper) == "N_max")

    d_max_n = result.n_parameters * 1.01
    constrained_d_max = replace(classic, law=replace(classic.law, validity_box={
        "N": [1.0, 1e20],
        "D": [1.0, compute.budget_flops / (compute.kappa * d_max_n)],
        "Q": [1.0, 1.0],
    }))
    d_max_box = AllocationBox.derive(constrained_d_max, compute)
    check("D_max boundary classified", d_max_box.active_boundary(d_max_box.n_lower) == "D_max")

    d_min_n = result.n_parameters * 0.99
    constrained_d_min = replace(classic, law=replace(classic.law, validity_box={
        "N": [1.0, 1e20],
        "D": [compute.budget_flops / (compute.kappa * d_min_n), 1e20],
        "Q": [1.0, 1.0],
    }))
    d_min_box = AllocationBox.derive(constrained_d_min, compute)
    check("D_min boundary classified", d_min_box.active_boundary(d_min_box.n_upper) == "D_min")

    impossible = replace(classic, law=replace(classic.law, validity_box={
        "N": [1.0, 2.0],
        "D": [1.0, 2.0],
        "Q": [1.0, 1.0],
    }))
    expect_raise("empty validity box rejected", lambda: AllocationBox.derive(impossible, compute), NoValidityBoxAllocation)

    uncertainty = describe_allocation_uncertainty(classic)
    check("uncertainty has marginal intervals", set(uncertainty.parameter_intervals) == {"E", "A", "alpha", "B", "beta"})
    check("uncertainty does not fabricate draws", not uncertainty.complete_parameter_vectors_released and not uncertainty.allocation_propagation_available)

    expected = 37
    for name, passed in RESULTS:
        print(("PASS" if passed else "FAIL") + " " + name)
    if len(RESULTS) != expected:
        print("FAIL assertion count: expected " + str(expected) + ", got " + str(len(RESULTS)), file=sys.stderr)
        return 1
    failures = [name for name, passed in RESULTS if not passed]
    if failures:
        print("FAIL " + str(len(failures)) + " of " + str(len(RESULTS)) + " assertions", file=sys.stderr)
        return 1
    print("PASS " + str(len(RESULTS)) + " assertions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
