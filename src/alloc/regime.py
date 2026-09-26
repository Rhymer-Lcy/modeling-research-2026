"""Budget-driven regime map and transition thresholds for Q3.

Definition.  At a fixed observed context the regime of budget ``C`` is

    R(C) = INFEASIBLE                      if C < C_min,
           (saturation, active bound set)  otherwise,

where saturation is ``SATURATED`` (``kappa N* D* = C``) or ``SLACK`` and the
active set is the complete set of IF3 box bounds binding at the optimum.  A
*structural transition* is a budget at which R changes.  Within one regime the
optimal allocation is a fixed power law of C, so R changes exactly where the
budget elasticities ``d log N*/d log C`` and ``d log D*/d log C`` jump; the map
reports both the analytic elasticity of each regime and a numerical check.

Identification.  Candidate thresholds are ``C_min``, ``C_box`` and the budgets at
which the unconstrained stationary path ``(N_s(C), D_s(C))`` reaches each box
bound.  A candidate is retained only if the constrained optimizer, probed just
below, at and just above it, shows a change of R.  Probes use
:meth:`BaselineCompute.continuation`, so continuous-C analysis stays inside the
organizer's declared budget span and is labelled model-conditional; a candidate
outside that span is recorded with its value and category but is not analysed
as a transition.

Categories kept distinct: an interior smooth allocation curve (between
thresholds), a validity-boundary active-set transition, the onset of budget
slack at the validity ceiling ``C_box``, and a boundary of the analysis/source
support (the ends of the declared span).  None of these is an empirical physical
transition; the ``D_max`` and ``C_box`` transitions are properties of where the
accepted law was identified, not observations of how training behaves there.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .constraint import BaselineCompute, SourceReceipt
from .solver import AllocationResult, solve_baseline
from .validity import AllocationBox, NoValidityBoxAllocation

#: Relative budget offset of the below/above probes around a candidate.
PROBE_OFFSET = 1e-6
#: Relative half-width of the finite-difference elasticity check.
ELASTICITY_STEP = 1e-4

CATEGORY_FEASIBILITY_ONSET = "feasibility_onset_at_box_lower_corner"
CATEGORY_ACTIVE_SET = "validity_boundary_active_set_transition"
CATEGORY_SLACK_ONSET = "budget_slack_onset_at_validity_ceiling"
CATEGORY_SUPPORT_BOUNDARY = "analysis_source_support_boundary"
EMPIRICAL_TRANSITION = "no empirical physical transition is established by this model"


def stationary_threshold(params: Mapping[str, float], kappa: float, coordinate: str, bound: float) -> float:
    """Budget at which the equality-slice stationary point reaches ``coordinate = bound``.

    From ``alpha A N^-alpha = beta B D^-beta``: at ``N = n``,
    ``D = (beta B n^alpha / (alpha A))^(1/beta)``; at ``D = d``,
    ``N = (alpha A d^beta / (beta B))^(1/alpha)``; the budget is ``kappa N D``.
    """
    alpha, beta, a, b = params["alpha"], params["beta"], params["A"], params["B"]
    if coordinate == "N":
        n_value = bound
        d_value = (beta * b / (alpha * a) * n_value ** alpha) ** (1.0 / beta)
    elif coordinate == "D":
        d_value = bound
        n_value = (alpha * a / (beta * b) * d_value ** beta) ** (1.0 / alpha)
    else:
        raise ValueError("coordinate must be N or D")
    return float(kappa * n_value * d_value)


def analytic_elasticities(params: Mapping[str, float], saturation: str, active: tuple[str, ...]) -> tuple[float, float]:
    """Budget elasticities of (N*, D*) implied by one regime."""
    if saturation == "SLACK":
        return 0.0, 0.0
    n_bound = any(label.startswith("N_") for label in active)
    d_bound = any(label.startswith("D_") for label in active)
    if n_bound and d_bound:
        return 0.0, 0.0
    if n_bound:
        return 0.0, 1.0
    if d_bound:
        return 1.0, 0.0
    total = params["alpha"] + params["beta"]
    return params["beta"] / total, params["alpha"] / total


@dataclass(frozen=True)
class Candidate:
    """One candidate threshold before disposition."""

    name: str
    budget_flops: float
    category: str
    parameter_dependent: bool
    derivation: str


def candidate_thresholds(law: Any, kappa: float, box: AllocationBox) -> tuple[Candidate, ...]:
    """Return C_min, C_box and all four stationary-path bound crossings."""
    output = [
        Candidate("C_min", box.c_min_flops, CATEGORY_FEASIBILITY_ONSET, False,
                  "kappa * N_min * D_min (box geometry and receipt kappa only)"),
        Candidate("C_box", box.c_box_flops, CATEGORY_SLACK_ONSET, False,
                  "kappa * N_max * D_max (box geometry and receipt kappa only)"),
    ]
    for coordinate, label, bound in (("N", "N_min", box.n_min), ("N", "N_max", box.n_max),
                                     ("D", "D_min", box.d_min), ("D", "D_max", box.d_max)):
        output.append(Candidate(
            "stationary_reaches_" + label,
            stationary_threshold(law.params, kappa, coordinate, bound),
            CATEGORY_ACTIVE_SET, True,
            "kappa * N_s * D_s where the equality-slice stationary point has " + label,
        ))
    return tuple(sorted(output, key=lambda candidate: candidate.budget_flops))


def _record(result: AllocationResult | None) -> dict[str, Any]:
    if result is None:
        return {"status": "INFEASIBLE_BELOW_C_MIN", "regime": "INFEASIBLE"}
    return {
        "status": "VALID_ALLOCATION",
        "budget_flops": result.compute.budget_flops,
        "budget_role": result.compute.budget_role,
        "n_parameters_raw": result.n_parameters,
        "d_tokens_raw": result.d_tokens,
        "predicted_loss": result.predicted_loss,
        "regime": result.regime,
        "saturation": result.saturation,
        "active_bounds": list(result.active_bounds),
        "budget_geometry": result.budget_geometry,
        "spent_flops": result.spent_flops,
        "unused_budget_flops": result.unused_budget_flops,
        "compute_utilization": result.compute_utilization,
    }


def _solve(law: Any, receipt: SourceReceipt, context: int, budget: float) -> AllocationResult | None:
    try:
        return solve_baseline(law, BaselineCompute.continuation(receipt, budget, context))
    except NoValidityBoxAllocation:
        return None


@dataclass(frozen=True)
class ThresholdDisposition:
    """A candidate threshold, where it lies, and what the probes showed."""

    name: str
    budget_flops: float
    category: str
    parameter_dependent: bool
    derivation: str
    span_status: str
    disposition: str
    below: Mapping[str, Any] | None
    at: Mapping[str, Any] | None
    above: Mapping[str, Any] | None


@dataclass(frozen=True)
class RegimeInterval:
    """One budget interval of constant regime inside the declared span."""

    lower_flops: float
    upper_flops: float
    lower_kind: str
    upper_kind: str
    regime: str
    saturation: str
    active_bounds: tuple[str, ...]
    analytic_n_elasticity: float | None
    analytic_d_elasticity: float | None
    numeric_n_elasticity: float | None
    numeric_d_elasticity: float | None


@dataclass(frozen=True)
class RegimeThresholdAnalysis:
    """Regime map and threshold dispositions at one observed context."""

    context_tokens: int
    kappa: float
    c_min_flops: float
    c_box_flops: float
    span_flops: tuple[float, float]
    thresholds: tuple[ThresholdDisposition, ...]
    regime_map: tuple[RegimeInterval, ...]

    @property
    def retained(self) -> tuple[ThresholdDisposition, ...]:
        return tuple(item for item in self.thresholds if item.disposition == "RETAINED_REGIME_TRANSITION")


def _span_status(budget: float, span: tuple[float, float]) -> str:
    if budget < span[0]:
        return "below_declared_span"
    if budget > span[1]:
        return "above_declared_span"
    return "inside_declared_span"


def probe_budget(
    law: Any, receipt: SourceReceipt, context: int, budget: float,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bool]:
    """Classify just below, at and just above ``budget``; report whether R(C) changes."""
    below = _record(_solve(law, receipt, context, budget * (1.0 - PROBE_OFFSET)))
    at = _record(_solve(law, receipt, context, budget))
    above = _record(_solve(law, receipt, context, budget * (1.0 + PROBE_OFFSET)))
    return below, at, above, below["regime"] != above["regime"]


def _elasticity(law: Any, receipt: SourceReceipt, context: int, budget: float) -> tuple[float, float]:
    low = _solve(law, receipt, context, budget * (1.0 - ELASTICITY_STEP))
    high = _solve(law, receipt, context, budget * (1.0 + ELASTICITY_STEP))
    if low is None or high is None:
        raise RuntimeError("elasticity probe left the feasible range")
    step = math.log1p(ELASTICITY_STEP) - math.log1p(-ELASTICITY_STEP)
    return (
        (math.log(high.n_parameters) - math.log(low.n_parameters)) / step,
        (math.log(high.d_tokens) - math.log(low.d_tokens)) / step,
    )


def _geometry(law: Any, kappa: float) -> AllocationBox:
    """Box geometry at one kappa, independent of any budget's feasibility."""
    (n_min, n_max), (d_min, d_max) = law.validity_box["N"], law.validity_box["D"]
    c_min, c_box = kappa * n_min * d_min, kappa * n_max * d_max
    return AllocationBox(c_box, kappa, n_min, n_max, d_min, d_max, c_min, c_box, n_min, n_max)


def analyze_regime_thresholds(law: Any, receipt: SourceReceipt, context_tokens: int) -> RegimeThresholdAnalysis:
    """Identify and verify every budget regime transition inside the declared span."""
    context = receipt.require_context(context_tokens)
    span = receipt.budget_span
    box = _geometry(law, receipt.kappa(context))
    dispositions: list[ThresholdDisposition] = []
    for candidate in candidate_thresholds(law, box.kappa, box):
        status = _span_status(candidate.budget_flops, span)
        base = dict(name=candidate.name, budget_flops=candidate.budget_flops, category=candidate.category,
                    parameter_dependent=candidate.parameter_dependent, derivation=candidate.derivation,
                    span_status=status)
        if candidate.category == CATEGORY_ACTIVE_SET and not (
            box.c_min_flops < candidate.budget_flops < box.c_box_flops
        ):
            dispositions.append(ThresholdDisposition(
                **base, disposition="NOT_A_TRANSITION_OUTSIDE_C_MIN_C_BOX", below=None, at=None, above=None))
            continue
        if status != "inside_declared_span":
            dispositions.append(ThresholdDisposition(
                **base, disposition="OUTSIDE_DECLARED_SPAN_NOT_ANALYSED", below=None, at=None, above=None))
            continue
        below_budget = candidate.budget_flops * (1.0 - PROBE_OFFSET)
        above_budget = candidate.budget_flops * (1.0 + PROBE_OFFSET)
        if below_budget < span[0] or above_budget > span[1]:
            dispositions.append(ThresholdDisposition(
                **base, disposition="AT_DECLARED_SPAN_EDGE_NOT_VERIFIABLE", below=None, at=None, above=None))
            continue
        below, at, above, changed = probe_budget(law, receipt, context, candidate.budget_flops)
        dispositions.append(ThresholdDisposition(
            **base, disposition="RETAINED_REGIME_TRANSITION" if changed else "REJECTED_NO_REGIME_CHANGE",
            below=below, at=at, above=above))

    retained = sorted((item for item in dispositions if item.disposition == "RETAINED_REGIME_TRANSITION"),
                      key=lambda item: item.budget_flops)
    edges = [(span[0], CATEGORY_SUPPORT_BOUNDARY)]
    edges += [(item.budget_flops, item.category) for item in retained]
    edges += [(span[1], CATEGORY_SUPPORT_BOUNDARY)]
    for (left, _), (right, _) in zip(edges, edges[1:]):
        if not right > left * (1.0 + 100.0 * max(PROBE_OFFSET, ELASTICITY_STEP)):
            raise RuntimeError("regime thresholds are too close to probe and verify separately")
    intervals: list[RegimeInterval] = []
    for (left, left_kind), (right, right_kind) in zip(edges, edges[1:]):
        middle = math.sqrt(left * right)
        result = _solve(law, receipt, context, middle)
        if result is None:
            intervals.append(RegimeInterval(left, right, left_kind, right_kind, "INFEASIBLE", "INFEASIBLE", (),
                                            None, None, None, None))
            continue
        n_analytic, d_analytic = analytic_elasticities(law.params, result.saturation, result.active_bounds)
        n_numeric, d_numeric = _elasticity(law, receipt, context, middle)
        intervals.append(RegimeInterval(
            left, right, left_kind, right_kind, result.regime, result.saturation, result.active_bounds,
            n_analytic, d_analytic, n_numeric, d_numeric,
        ))
    return RegimeThresholdAnalysis(
        context_tokens=context,
        kappa=box.kappa,
        c_min_flops=box.c_min_flops,
        c_box_flops=box.c_box_flops,
        span_flops=span,
        thresholds=tuple(dispositions),
        regime_map=tuple(intervals),
    )


__all__ = [
    "CATEGORY_ACTIVE_SET",
    "CATEGORY_FEASIBILITY_ONSET",
    "CATEGORY_SLACK_ONSET",
    "CATEGORY_SUPPORT_BOUNDARY",
    "Candidate",
    "ELASTICITY_STEP",
    "EMPIRICAL_TRANSITION",
    "PROBE_OFFSET",
    "RegimeInterval",
    "RegimeThresholdAnalysis",
    "ThresholdDisposition",
    "analytic_elasticities",
    "analyze_regime_thresholds",
    "candidate_thresholds",
    "probe_budget",
    "stationary_threshold",
]
