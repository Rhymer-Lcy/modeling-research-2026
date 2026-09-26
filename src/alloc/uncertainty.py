"""Descriptive uncertainty evidence for receipt-bound baseline allocation.

The accepted IF3 serialization releases marginal bootstrap confidence intervals,
not complete bootstrap parameter vectors.  This module records that limitation
rather than synthesizing joint parameter draws or allocation uncertainty bands.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .classic import AcceptedClassicIF3


@dataclass(frozen=True)
class AllocationUncertaintyEvidence:
    """Released uncertainty evidence and its permitted allocation use."""

    representation: str
    source_unit: str | None
    replicates: int | None
    n_clusters: int | None
    seed: int | None
    parameter_intervals: Mapping[str, tuple[float, float]]
    complete_parameter_vectors_released: bool
    allocation_propagation_available: bool
    limitation: str


def _optional_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None
    if numeric < 0 or numeric != value:
        return None
    return numeric


def _intervals(bootstrap: Mapping[str, Any]) -> Mapping[str, tuple[float, float]]:
    raw_intervals = bootstrap.get("ci")
    if not isinstance(raw_intervals, dict):
        return {}
    output: dict[str, tuple[float, float]] = {}
    for parameter, bounds in raw_intervals.items():
        if not isinstance(parameter, str) or not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            continue
        try:
            lower, upper = float(bounds[0]), float(bounds[1])
        except (TypeError, ValueError):
            continue
        output[parameter] = (lower, upper)
    return output


def describe_allocation_uncertainty(classic: AcceptedClassicIF3) -> AllocationUncertaintyEvidence:
    """Describe released IF3 evidence without fabricating an allocation interval."""
    bootstrap = classic.payload.get("bootstrap")
    if not isinstance(bootstrap, dict):
        bootstrap = {}
    intervals = _intervals(bootstrap)
    return AllocationUncertaintyEvidence(
        representation="accepted_classic_if3_bootstrap_marginal_intervals",
        source_unit=bootstrap.get("unit") if isinstance(bootstrap.get("unit"), str) else None,
        replicates=_optional_nonnegative_int(bootstrap.get("replicates")),
        n_clusters=_optional_nonnegative_int(bootstrap.get("n_clusters")),
        seed=_optional_nonnegative_int(bootstrap.get("seed")),
        parameter_intervals=intervals,
        complete_parameter_vectors_released=False,
        allocation_propagation_available=False,
        limitation=(
            "The accepted IF3 serialization supplies marginal bootstrap parameter intervals only; "
            "it does not release complete joint bootstrap parameter vectors. Allocation uncertainty "
            "bands are therefore not computed, and no joint samples are synthesized from marginals."
        ),
    )


__all__ = ["AllocationUncertaintyEvidence", "describe_allocation_uncertainty"]
