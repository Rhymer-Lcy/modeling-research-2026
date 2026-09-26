"""Inequality-feasible validity geometry for receipt-bound baseline allocation.

The accepted IF3 law is evaluated only inside its raw parameter/token validity
box.  Q3's source constraint is ``kappa * N * D <= C``; budget saturation is a
property of some optima, not a feasibility definition.  With

    C_min = kappa * N_min * D_min        C_box = kappa * N_max * D_max

the feasible set is empty for ``C < C_min``, is the single lower corner at
``C = C_min``, and for ``C > C_box`` contains the whole box, so the accepted-box
optimum is the upper corner ``(N_max, D_max)`` with unused budget ``C - C_box``.
Because the loss is strictly decreasing in N and in D for the accepted positive
parameters, the best feasible D at a given N is

    D_best(N) = min(D_max, C / (kappa * N)),   N in [N_min, min(N_max, C/(kappa*D_min))].
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from .constraint import BaselineCompute

BOUND_LABELS = ("N_min", "N_max", "D_min", "D_max")


class NoValidityBoxAllocation(ValueError):
    """No point in the accepted raw N/D box satisfies the compute inequality."""


def _positive_finite(value: object, label: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise NoValidityBoxAllocation(label + " must be numeric") from exc
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise NoValidityBoxAllocation(label + " must be finite and strictly positive")
    return numeric


def _raw_bounds(law: Any, coordinate: str) -> tuple[float, float]:
    values = law.validity_box.get(coordinate)
    if values is None or len(values) != 2:
        raise NoValidityBoxAllocation("classic law has no usable " + coordinate + " validity bounds")
    lower = _positive_finite(values[0], coordinate + " validity lower bound")
    upper = _positive_finite(values[1], coordinate + " validity upper bound")
    if lower > upper:
        raise NoValidityBoxAllocation(coordinate + " validity bounds are reversed")
    return lower, upper


def is_close(left: float, right: float) -> bool:
    """Scale-aware equality used for bounds, corners and budget saturation."""
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=0.0)


@dataclass(frozen=True)
class AllocationBox:
    """The accepted N/D box intersected with ``kappa*N*D <= budget``."""

    budget_flops: float
    kappa: float
    n_min: float
    n_max: float
    d_min: float
    d_max: float
    c_min_flops: float
    c_box_flops: float
    n_lower: float
    n_upper: float

    @classmethod
    def derive(cls, law: Any, compute: BaselineCompute) -> "AllocationBox":
        """Construct the inequality-feasible N interval, or fail below ``C_min``."""
        n_min, n_max = _raw_bounds(law, "N")
        d_min, d_max = _raw_bounds(law, "D")
        budget = _positive_finite(compute.budget_flops, "compute budget")
        kappa = _positive_finite(compute.kappa, "kappa")
        c_min = kappa * n_min * d_min
        c_box = kappa * n_max * d_max
        if budget < c_min and not is_close(budget, c_min):
            raise NoValidityBoxAllocation(
                "compute budget is below C_min: no point of the accepted raw N/D validity box is affordable"
            )
        n_upper = min(n_max, budget / (kappa * d_min))
        if n_upper < n_min:
            n_upper = n_min  # only reachable within the C_min rounding tolerance above
        return cls(budget, kappa, n_min, n_max, d_min, d_max, c_min, c_box, n_min, n_upper)

    @property
    def budget_geometry(self) -> str:
        """Classify the budget against the box geometry alone."""
        if is_close(self.budget_flops, self.c_min_flops):
            return "AT_C_MIN"
        if is_close(self.budget_flops, self.c_box_flops):
            return "AT_C_BOX"
        if self.budget_flops > self.c_box_flops:
            return "ABOVE_C_BOX"
        return "BETWEEN_C_MIN_AND_C_BOX"

    @property
    def saturation_kink_n(self) -> float:
        """N where ``D_best`` changes from ``D_max`` to budget saturation."""
        return self.budget_flops / (self.kappa * self.d_max)

    def contains_n(self, n_parameters: object) -> bool:
        """Return whether N has at least one D in the accepted feasible set."""
        n_value = _positive_finite(n_parameters, "N")
        return (self.n_lower <= n_value <= self.n_upper
                or is_close(n_value, self.n_lower) or is_close(n_value, self.n_upper))

    def d_best_for_n(self, n_parameters: object) -> float:
        """Return the loss-minimising feasible D at one feasible raw N value."""
        n_value = _positive_finite(n_parameters, "N")
        if not self.contains_n(n_value):
            raise NoValidityBoxAllocation("N lies outside the inequality-feasible allocation interval")
        return float(min(self.d_max, self.budget_flops / (self.kappa * n_value)))

    def contains_point(self, n_parameters: object, d_tokens: object) -> bool:
        """Return whether one raw N/D point obeys both the box and the budget."""
        n_value = _positive_finite(n_parameters, "N")
        d_value = _positive_finite(d_tokens, "D")
        spent = self.kappa * n_value * d_value
        return (
            (self.n_min <= n_value <= self.n_max or is_close(n_value, self.n_min) or is_close(n_value, self.n_max))
            and (self.d_min <= d_value <= self.d_max or is_close(d_value, self.d_min) or is_close(d_value, self.d_max))
            and (spent <= self.budget_flops or is_close(spent, self.budget_flops))
        )

    def active_bounds(self, n_parameters: object, d_tokens: object) -> tuple[str, ...]:
        """Return every simultaneous raw-box bound active at a feasible point."""
        n_value = _positive_finite(n_parameters, "N")
        d_value = _positive_finite(d_tokens, "D")
        if not self.contains_point(n_value, d_value):
            raise NoValidityBoxAllocation("point lies outside the accepted inequality-feasible box")
        values = {"N_min": (n_value, self.n_min), "N_max": (n_value, self.n_max),
                  "D_min": (d_value, self.d_min), "D_max": (d_value, self.d_max)}
        return tuple(label for label in BOUND_LABELS if is_close(*values[label]))

    def point_labels(self, n_parameters: object, d_tokens: object) -> Mapping[str, object]:
        """Return full validity and slack provenance for one feasible point."""
        n_value = _positive_finite(n_parameters, "N")
        d_value = _positive_finite(d_tokens, "D")
        spent = self.kappa * n_value * d_value
        return {
            "in_validity_box": self.contains_point(n_value, d_value),
            "active_bounds": list(self.active_bounds(n_value, d_value)),
            "budget_saturated": is_close(spent, self.budget_flops),
            "c_min_flops": self.c_min_flops,
            "c_box_flops": self.c_box_flops,
            "budget_geometry": self.budget_geometry,
        }


__all__ = ["AllocationBox", "BOUND_LABELS", "NoValidityBoxAllocation", "is_close"]
