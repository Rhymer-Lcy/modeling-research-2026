"""Deterministic receipt-bound optimizer for the classic baseline law."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from scipy.optimize import minimize_scalar

from .classic import AcceptedClassicIF3, baseline_closed_form, classic_loss
from .constraint import BaselineCompute, cost_breakdown
from .validity import AllocationBox


@dataclass(frozen=True)
class AllocationResult:
    """One valid, model-conditional baseline allocation result."""

    compute: BaselineCompute
    allocation_box: AllocationBox
    n_parameters: float
    d_tokens: float
    predicted_loss: float
    unconstrained_n_parameters: float
    unconstrained_d_tokens: float
    unconstrained_predicted_loss: float
    constrained: bool
    active_boundary: str
    stationary_residual: float
    budget_saturation_residual_flops: float
    cost: Mapping[str, float]

    @property
    def validity_labels(self) -> Mapping[str, object]:
        """Return the retained raw-box provenance for the canonical point."""
        return self.allocation_box.point_labels(self.n_parameters)

    @property
    def feasibility_label(self) -> str:
        """Describe whether the canonical optimum is interior or boundary-bound."""
        return "interior" if self.active_boundary == "none" else "active_validity_boundary"


@dataclass(frozen=True)
class SolverAgreement:
    """Comparison of analytic and bounded numerical baseline solutions."""

    analytic: AllocationResult
    numeric_n_parameters: float
    numeric_d_tokens: float
    numeric_predicted_loss: float
    n_relative_difference: float
    d_relative_difference: float
    loss_relative_difference: float


def _positive_finite(value: object, label: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(label + " must be numeric") from exc
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise ValueError(label + " must be finite and strictly positive")
    return numeric


def _relative_difference(left: float, right: float) -> float:
    denominator = max(abs(left), abs(right), 1.0)
    return abs(left - right) / denominator


def _reduced_loss(classic: AcceptedClassicIF3, compute: BaselineCompute, n_parameters: object) -> float:
    n_value = _positive_finite(n_parameters, "N")
    d_value = compute.budget_flops / (compute.kappa * n_value)
    return classic_loss(classic, n_value, d_value)


def _stationary_residual(
    classic: AcceptedClassicIF3,
    compute: BaselineCompute,
    n_parameters: object,
) -> float:
    """Return dL/dlog(N), which is scale-stable at the interior optimum."""
    n_value = _positive_finite(n_parameters, "N")
    d_value = compute.budget_flops / (compute.kappa * n_value)
    p = classic.params
    return float(-p["alpha"] * p["A"] * n_value ** (-p["alpha"])
                 + p["beta"] * p["B"] * d_value ** (-p["beta"]))


def _candidate_result(
    classic: AcceptedClassicIF3,
    compute: BaselineCompute,
    allocation_box: AllocationBox,
    unconstrained_n: float,
    unconstrained_d: float,
    unconstrained_loss: float,
    n_parameters: float,
) -> AllocationResult:
    d_value = allocation_box.d_for_n(n_parameters)
    cost = cost_breakdown(compute, n_parameters, d_value)
    return AllocationResult(
        compute=compute,
        allocation_box=allocation_box,
        n_parameters=float(n_parameters),
        d_tokens=d_value,
        predicted_loss=classic_loss(classic, n_parameters, d_value),
        unconstrained_n_parameters=unconstrained_n,
        unconstrained_d_tokens=unconstrained_d,
        unconstrained_predicted_loss=unconstrained_loss,
        constrained=not math.isclose(
            n_parameters, unconstrained_n, rel_tol=1e-12, abs_tol=1e-9
        ),
        active_boundary=allocation_box.active_boundary(n_parameters),
        stationary_residual=_stationary_residual(classic, compute, n_parameters),
        budget_saturation_residual_flops=cost["budget_residual_flops"],
        cost=cost,
    )


def solve_baseline(classic: AcceptedClassicIF3, compute: BaselineCompute) -> AllocationResult:
    """Solve the accepted, receipt-approved baseline allocation deterministically."""
    allocation_box = AllocationBox.derive(classic, compute)
    unconstrained_n, unconstrained_d = baseline_closed_form(
        classic, compute.budget_flops, compute.kappa
    )
    unconstrained_loss = classic_loss(classic, unconstrained_n, unconstrained_d)
    candidates = [allocation_box.n_lower, allocation_box.n_upper]
    if allocation_box.contains_n(unconstrained_n):
        candidates.append(unconstrained_n)
    n_value = min(candidates, key=lambda candidate: (_reduced_loss(classic, compute, candidate), candidate))
    return _candidate_result(
        classic,
        compute,
        allocation_box,
        unconstrained_n,
        unconstrained_d,
        unconstrained_loss,
        n_value,
    )


def solve_baseline_numeric(
    classic: AcceptedClassicIF3,
    compute: BaselineCompute,
) -> SolverAgreement:
    """Compare the analytic solution to bounded scalar numerical minimization."""
    analytic = solve_baseline(classic, compute)
    allocation_box = analytic.allocation_box
    if allocation_box.n_lower == allocation_box.n_upper:
        numeric_n = allocation_box.n_lower
    else:
        result = minimize_scalar(
            lambda n_value: _reduced_loss(classic, compute, n_value),
            bounds=(allocation_box.n_lower, allocation_box.n_upper),
            method="bounded",
            options={"xatol": max(1e-6, allocation_box.n_lower * 1e-12)},
        )
        if not result.success or not math.isfinite(result.x):
            raise RuntimeError("bounded numerical baseline allocation did not converge")
        candidates = (allocation_box.n_lower, allocation_box.n_upper, float(result.x))
        numeric_n = min(candidates, key=lambda candidate: (_reduced_loss(classic, compute, candidate), candidate))
    numeric_d = allocation_box.d_for_n(numeric_n)
    numeric_loss = classic_loss(classic, numeric_n, numeric_d)
    return SolverAgreement(
        analytic=analytic,
        numeric_n_parameters=numeric_n,
        numeric_d_tokens=numeric_d,
        numeric_predicted_loss=numeric_loss,
        n_relative_difference=_relative_difference(analytic.n_parameters, numeric_n),
        d_relative_difference=_relative_difference(analytic.d_tokens, numeric_d),
        loss_relative_difference=_relative_difference(analytic.predicted_loss, numeric_loss),
    )


__all__ = [
    "AllocationResult",
    "SolverAgreement",
    "solve_baseline",
    "solve_baseline_numeric",
]
