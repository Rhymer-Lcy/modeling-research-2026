"""Deterministic receipt-bound optimizer for the classic baseline law.

Problem (baseline ``Q = Q0``, so ``delta_g = 0``):

    minimize   L(N, D) = E + A N^-alpha + B D^-beta
    subject to kappa N D <= C,  N_min <= N <= N_max,  D_min <= D <= D_max.

With ``D_best(N) = min(D_max, C/(kappa N))`` the reduced loss is strictly
decreasing in N on the ``D_max`` branch and strictly convex in ``log N`` on the
saturated branch, whose unconstrained minimizer is the closed form

    N_s = [alpha A / (beta B)]^(1/(alpha+beta)) (C/kappa)^(beta/(alpha+beta)),
    D_s = C / (kappa N_s).

The global optimum is therefore among: the feasible N endpoints, the saturation
kink ``C/(kappa D_max)``, and ``N_s`` when ``(N_s, D_s)`` lies in the box.
:func:`solve_baseline` evaluates exactly that candidate set.
:func:`solve_baseline_numeric` is an independent derivative-free check that
knows nothing about the candidate set.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from scipy.optimize import minimize_scalar

from .classic import baseline_closed_form, classic_loss
from .constraint import BaselineCompute, cost_breakdown
from .validity import AllocationBox, is_close

#: Grid resolution of the numerical comparator's global bracketing pass.
NUMERIC_GRID_POINTS = 4097


@dataclass(frozen=True)
class AllocationResult:
    """One valid, model-conditional baseline allocation."""

    compute: BaselineCompute
    allocation_box: AllocationBox
    n_parameters: float
    d_tokens: float
    predicted_loss: float
    stationary_n_parameters: float
    stationary_d_tokens: float
    stationary_predicted_loss: float
    stationary_point_in_validity_box: bool
    active_bounds: tuple[str, ...]
    saturation: str
    regime: str
    budget_geometry: str
    stationary_residual_relative: float | None
    cost: Mapping[str, float]

    @property
    def spent_flops(self) -> float:
        return self.cost["spent_flops"]

    @property
    def unused_budget_flops(self) -> float:
        return self.cost["unused_budget_flops"]

    @property
    def compute_utilization(self) -> float:
        return self.cost["compute_utilization"]

    @property
    def validity_labels(self) -> Mapping[str, object]:
        """Return the raw-box provenance of the canonical point."""
        return self.allocation_box.point_labels(self.n_parameters, self.d_tokens)


@dataclass(frozen=True)
class SolverAgreement:
    """Comparison of the analytic candidate solution with the numerical search."""

    analytic: AllocationResult
    numeric_n_parameters: float
    numeric_d_tokens: float
    numeric_predicted_loss: float
    n_relative_difference: float
    d_relative_difference: float
    loss_relative_difference: float
    analytic_not_improved: bool


def regime_label(saturation: str, active_bounds: tuple[str, ...]) -> str:
    """Composite regime: saturation status plus the complete active bound set."""
    return saturation + ":" + ("+".join(active_bounds) if active_bounds else "interior")


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right))


def _reduced_loss(law: Any, box: AllocationBox, n_value: float) -> float:
    return classic_loss(law, n_value, box.d_best_for_n(n_value))


def _stationary_residual(law: Any, n_value: float, d_value: float) -> float:
    """Relative equality-slice condition ``(beta B D^-beta - alpha A N^-alpha) / (alpha A N^-alpha)``."""
    p = law.params
    n_term = p["alpha"] * p["A"] * n_value ** (-p["alpha"])
    d_term = p["beta"] * p["B"] * d_value ** (-p["beta"])
    return float((d_term - n_term) / n_term)


def _deduplicate(candidates: list[float]) -> list[float]:
    output: list[float] = []
    for candidate in candidates:
        if not any(is_close(candidate, kept) for kept in output):
            output.append(candidate)
    return output


def _result(law: Any, compute: BaselineCompute, box: AllocationBox, n_value: float) -> AllocationResult:
    d_value = box.d_best_for_n(n_value)
    cost = cost_breakdown(compute, n_value, d_value)
    active = box.active_bounds(n_value, d_value)
    saturated = is_close(cost["spent_flops"], compute.budget_flops)
    saturation = "SATURATED" if saturated else "SLACK"
    stationary_n, stationary_d = baseline_closed_form(law, compute.budget_flops, compute.kappa)
    return AllocationResult(
        compute=compute,
        allocation_box=box,
        n_parameters=float(n_value),
        d_tokens=float(d_value),
        predicted_loss=classic_loss(law, n_value, d_value),
        stationary_n_parameters=stationary_n,
        stationary_d_tokens=stationary_d,
        stationary_predicted_loss=classic_loss(law, stationary_n, stationary_d),
        stationary_point_in_validity_box=box.contains_point(stationary_n, stationary_d),
        active_bounds=active,
        saturation=saturation,
        regime=regime_label(saturation, active),
        budget_geometry=box.budget_geometry,
        stationary_residual_relative=_stationary_residual(law, n_value, d_value) if saturated else None,
        cost=cost,
    )


def solve_baseline(law: Any, compute: BaselineCompute) -> AllocationResult:
    """Solve the baseline problem exactly over its inequality-feasible box."""
    box = AllocationBox.derive(law, compute)
    stationary_n, stationary_d = baseline_closed_form(law, compute.budget_flops, compute.kappa)
    candidates = [box.n_lower, box.n_upper]
    if box.contains_n(box.saturation_kink_n):
        candidates.append(box.saturation_kink_n)
    if box.contains_point(stationary_n, stationary_d):
        candidates.append(stationary_n)
    best = min(_deduplicate(candidates), key=lambda n_value: (_reduced_loss(law, box, n_value), n_value))
    return _result(law, compute, box, best)


def solve_baseline_numeric(law: Any, compute: BaselineCompute) -> SolverAgreement:
    """Independently locate the optimum and compare it with :func:`solve_baseline`.

    A deterministic geometric grid of :data:`NUMERIC_GRID_POINTS` points over the
    feasible N interval brackets the global minimum of the reduced loss; bounded
    Brent then refines it inside the two neighbouring grid cells, parametrized
    on [0, 1] so that its sqrt(machine-epsilon) termination tolerance applies to
    a cell of width ~1e-3 in log N.  No analytic candidate is consulted.  The
    remaining disagreement is bounded by the flatness of a smooth minimum
    (relative N error of order sqrt(eps)), which is why N/D are compared at 1e-6
    while the loss, second-order at a smooth minimum, is compared at 1e-11.
    """
    analytic = solve_baseline(law, compute)
    box = analytic.allocation_box
    log_lower, log_upper = math.log(box.n_lower), math.log(box.n_upper)
    if is_close(box.n_lower, box.n_upper):
        numeric_n = box.n_lower
    else:
        step = (log_upper - log_lower) / (NUMERIC_GRID_POINTS - 1)
        grid = [math.exp(log_lower + index * step) for index in range(NUMERIC_GRID_POINTS)]
        grid[0], grid[-1] = box.n_lower, box.n_upper
        losses = [_reduced_loss(law, box, value) for value in grid]
        best = min(range(len(grid)), key=lambda index: (losses[index], index))
        left = math.log(grid[max(best - 1, 0)])
        right = math.log(grid[min(best + 1, len(grid) - 1)])

        def objective(fraction: float) -> float:
            n_value = min(max(math.exp(left + fraction * (right - left)), box.n_lower), box.n_upper)
            return _reduced_loss(law, box, n_value)

        refined = minimize_scalar(objective, bounds=(0.0, 1.0), method="bounded",
                                  options={"xatol": 1e-12, "maxiter": 500})
        if not refined.success or not math.isfinite(refined.x):
            raise RuntimeError("bounded numerical baseline allocation did not converge")
        refined_n = min(max(math.exp(left + refined.x * (right - left)), box.n_lower), box.n_upper)
        numeric_n = min((grid[best], refined_n), key=lambda value: (_reduced_loss(law, box, value), value))
    numeric_d = box.d_best_for_n(numeric_n)
    numeric_loss = classic_loss(law, numeric_n, numeric_d)
    return SolverAgreement(
        analytic=analytic,
        numeric_n_parameters=numeric_n,
        numeric_d_tokens=numeric_d,
        numeric_predicted_loss=numeric_loss,
        n_relative_difference=_relative_difference(analytic.n_parameters, numeric_n),
        d_relative_difference=_relative_difference(analytic.d_tokens, numeric_d),
        loss_relative_difference=_relative_difference(analytic.predicted_loss, numeric_loss),
        analytic_not_improved=analytic.predicted_loss <= numeric_loss * (1.0 + 4.0 * 2.0**-52),
    )


__all__ = [
    "AllocationResult",
    "NUMERIC_GRID_POINTS",
    "SolverAgreement",
    "regime_label",
    "solve_baseline",
    "solve_baseline_numeric",
]
