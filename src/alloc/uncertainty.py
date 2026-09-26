"""Descriptive bootstrap evidence for receipt-bound baseline allocation.

The accepted IF3 serialization releases marginal model-clustered bootstrap
intervals, not complete bootstrap parameter vectors.  Marginal intervals cannot
be combined into joint parameter vectors without inventing a dependence
structure, so this module records them and their limits and propagates nothing.
Allocation robustness is propagated separately from the complete published
leave-one-trajectory-out vectors (:mod:`src.alloc.robustness`); the two kinds of
evidence answer different questions and are never merged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class AllocationUncertaintyEvidence:
    """Released bootstrap evidence and its permitted allocation use."""

    representation: str
    source_unit: str | None
    replicates: int | None
    n_clusters: int | None
    seed: int | None
    parameter_intervals: Mapping[str, tuple[float, float]]
    complete_bootstrap_vectors_released: bool
    bootstrap_allocation_propagation: str
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


def describe_allocation_uncertainty(classic: Any) -> AllocationUncertaintyEvidence:
    """Describe the released IF3 bootstrap evidence without fabricating draws."""
    bootstrap = classic.payload.get("bootstrap")
    if not isinstance(bootstrap, dict):
        bootstrap = {}
    return AllocationUncertaintyEvidence(
        representation="accepted_classic_if3_bootstrap_marginal_intervals",
        source_unit=bootstrap.get("unit") if isinstance(bootstrap.get("unit"), str) else None,
        replicates=_optional_nonnegative_int(bootstrap.get("replicates")),
        n_clusters=_optional_nonnegative_int(bootstrap.get("n_clusters")),
        seed=_optional_nonnegative_int(bootstrap.get("seed")),
        parameter_intervals=_intervals(bootstrap),
        complete_bootstrap_vectors_released=False,
        bootstrap_allocation_propagation="NOT_PERFORMED",
        limitation=(
            "The accepted IF3 releases marginal model-clustered bootstrap intervals only, not joint "
            "bootstrap parameter vectors, so no bootstrap allocation band is computed and no joint draw "
            "is synthesized from marginals. Profile-identifiability ratios are not converted into "
            "allocation limits. Allocation robustness is reported separately from the eight complete "
            "published leave-one-trajectory-out vectors. The IF3 fit recovers a deterministic generator "
            "on B1, so its narrow intervals do not measure how precisely real model scaling is known."
        ),
    )


__all__ = ["AllocationUncertaintyEvidence", "describe_allocation_uncertainty"]
