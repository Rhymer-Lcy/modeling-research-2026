"""Validity-box reduction for receipt-bound baseline allocation.

The accepted IF3 law is valid only inside its raw-parameter/raw-token box.  At a
receipt-supported baseline operating point, budget saturation eliminates ``D``
and turns that box into one explicit interval in ``N``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from .classic import AcceptedClassicIF3
from .constraint import BaselineCompute


class NoValidityBoxAllocation(ValueError):
    """No budget-saturating point lies in the accepted raw N/D validity box."""


def _positive_finite(value: object, label: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise NoValidityBoxAllocation(label + " must be numeric") from exc
    if not math.isfinite(numeric) or numeric <= 0.0:
        raise NoValidityBoxAllocation(label + " must be finite and strictly positive")
    return numeric


def _raw_bounds(classic: AcceptedClassicIF3, coordinate: str) -> tuple[float, float]:
    values = classic.validity_box.get(coordinate)
    if values is None or len(values) != 2:
        raise NoValidityBoxAllocation("classic IF3 has no usable " + coordinate + " validity bounds")
    lower = _positive_finite(values[0], coordinate + " validity lower bound")
    upper = _positive_finite(values[1], coordinate + " validity upper bound")
    if lower > upper:
        raise NoValidityBoxAllocation(coordinate + " validity bounds are reversed")
    return lower, upper


def _is_close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-9)


@dataclass(frozen=True)
class AllocationBox:
    """The valid budget-saturating interval and its source constraints."""

    budget_flops: float
    kappa: float
    n_min: float
    n_max: float
    d_min: float
    d_max: float
    n_lower: float
    n_upper: float
    lower_constraints: tuple[str, ...]
    upper_constraints: tuple[str, ...]

    @classmethod
    def derive(cls, classic: AcceptedClassicIF3, compute: BaselineCompute) -> "AllocationBox":
        """Eliminate D under saturation and reject an empty accepted IF3 box."""
        n_min, n_max = _raw_bounds(classic, "N")
        d_min, d_max = _raw_bounds(classic, "D")
        budget = _positive_finite(compute.budget_flops, "compute budget")
        kappa = _positive_finite(compute.kappa, "kappa")
        lower_from_d_max = budget / (kappa * d_max)
        upper_from_d_min = budget / (kappa * d_min)
        n_lower = max(n_min, lower_from_d_max)
        n_upper = min(n_max, upper_from_d_min)
        if n_lower > n_upper and not _is_close(n_lower, n_upper):
            raise NoValidityBoxAllocation(
                "no budget-saturating allocation lies in the accepted raw N/D validity box"
            )
        if _is_close(n_lower, n_upper):
            n_lower = n_upper = (n_lower + n_upper) / 2.0
        lower_constraints = tuple(
            label
            for label, value in (("N_min", n_min), ("D_max", lower_from_d_max))
            if _is_close(n_lower, value)
        )
        upper_constraints = tuple(
            label
            for label, value in (("N_max", n_max), ("D_min", upper_from_d_min))
            if _is_close(n_upper, value)
        )
        return cls(
            budget_flops=budget,
            kappa=kappa,
            n_min=n_min,
            n_max=n_max,
            d_min=d_min,
            d_max=d_max,
            n_lower=n_lower,
            n_upper=n_upper,
            lower_constraints=lower_constraints,
            upper_constraints=upper_constraints,
        )

    def d_for_n(self, n_parameters: object) -> float:
        """Recover the exactly budget-saturating raw token count for ``N``."""
        n_value = _positive_finite(n_parameters, "N")
        return float(self.budget_flops / (self.kappa * n_value))

    def contains_n(self, n_parameters: object) -> bool:
        """Return whether an N value belongs to the derived closed interval."""
        n_value = _positive_finite(n_parameters, "N")
        return self.n_lower <= n_value <= self.n_upper

    def active_boundary(self, n_parameters: object) -> str:
        """Classify a valid point with stable precedence at coincident bounds."""
        n_value = _positive_finite(n_parameters, "N")
        if not self.contains_n(n_value):
            raise NoValidityBoxAllocation("N lies outside the derived allocation interval")
        if _is_close(n_value, self.n_lower):
            if "N_min" in self.lower_constraints:
                return "N_min"
            return "D_max"
        if _is_close(n_value, self.n_upper):
            if "N_max" in self.upper_constraints:
                return "N_max"
            return "D_min"
        return "none"

    def point_labels(self, n_parameters: object) -> Mapping[str, object]:
        """Return boundary provenance without reducing coincident constraints."""
        n_value = _positive_finite(n_parameters, "N")
        if not self.contains_n(n_value):
            raise NoValidityBoxAllocation("N lies outside the derived allocation interval")
        d_value = self.d_for_n(n_value)
        lower_active = _is_close(n_value, self.n_lower)
        upper_active = _is_close(n_value, self.n_upper)
        return {
            "in_validity_box": True,
            "active_boundary": self.active_boundary(n_value),
            "lower_constraints": self.lower_constraints if lower_active else (),
            "upper_constraints": self.upper_constraints if upper_active else (),
            "n_parameters": n_value,
            "d_tokens": d_value,
        }


__all__ = ["AllocationBox", "NoValidityBoxAllocation"]
