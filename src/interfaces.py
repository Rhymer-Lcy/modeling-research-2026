"""Interface contracts between the four Problem-F questions.

The four questions form a chain: Q1 characterises the data, Q2 folds the data
factors into a scaling law, Q3 allocates a compute budget under that law, and
Q4 tests the law against historical evaluations and forecasts the frontier. The
output of one question is the input of the next, and the objects that cross
those boundaries are defined here rather than being re-derived on each side.

Each contract carries its own provenance and validity limits, because most of
the ways these objects can be misused are not type errors. A domain quality
score that covers only part of the corpus, a coefficient vector that is only
meaningful relative to a declared reference, and a fitted law whose quality
term comes from semi-synthetic data are all perfectly well-formed numbers that
mean less than they appear to. The fields below force those limits to travel
with the value.

Serialisation is JSON so that an interface can be inspected, diffed and
reviewed without importing the code that produced it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

SCHEMA_VERSION = "1.0"


class InterfaceError(ValueError):
    """Raised when an interface object violates its own contract."""


@dataclass
class Provenance:
    """Where a number came from and what it may therefore support.

    ``trust`` uses the organizer's own vocabulary so that a claim can never be
    upgraded by passing through a stage: ``observed``, ``subset``,
    ``interpolated``, ``semi_synthetic``, ``estimated``, ``mixed`` or
    ``reference``.
    """

    trust: str
    sources: List[str] = field(default_factory=list)
    notes: str = ""

    ALLOWED = (
        "observed",
        "subset",
        "interpolated",
        "semi_synthetic",
        "estimated",
        "mixed",
        "reference",
    )

    def validate(self) -> None:
        if self.trust not in self.ALLOWED:
            raise InterfaceError(
                f"unknown trust class {self.trust!r}; allowed: {self.ALLOWED}"
            )
        if not self.sources:
            raise InterfaceError("provenance must name at least one source")


@dataclass
class IF1DomainQuality:
    """Q1a -> Q2/Q3. Domain-level quality scores with their coverage limits.

    ``coverage_fraction`` is the load-bearing field. The quality signals cover
    seven domains while the mixture experiments use seventeen, and the
    organizer's reference mapping relates only a minority of them. A consumer
    that treats a partial-coverage score as a corpus-wide score is making a
    claim the data does not support, so the fraction of mixture mass the
    mapping actually reaches travels with the scores.
    """

    schema_version: str
    quality_domains: List[str]
    q_by_domain: Dict[str, float]
    q_ci_by_domain: Dict[str, Sequence[float]]
    n_by_domain: Dict[str, int]
    mixture_to_quality: Dict[str, Optional[str]]
    mapping_type: Dict[str, str]
    coverage_fraction: float
    indicator_directions: Dict[str, str]
    provenance: Provenance

    def validate(self) -> None:
        self.provenance.validate()
        for d, q in self.q_by_domain.items():
            if not 0.0 <= q <= 1.0:
                raise InterfaceError(f"domain quality out of [0,1]: {d}={q}")
            if d not in self.q_ci_by_domain:
                raise InterfaceError(f"domain {d} has no interval")
            if d not in self.n_by_domain:
                raise InterfaceError(f"domain {d} has no sample size")
        if not 0.0 <= self.coverage_fraction <= 1.0:
            raise InterfaceError("coverage_fraction must lie in [0,1]")
        bad = {k: v for k, v in self.indicator_directions.items()
               if v not in ("higher_better", "lower_better", "non_monotone")}
        if bad:
            raise InterfaceError(f"unknown indicator directions: {sorted(bad)}")


@dataclass
class IF2MixtureResponse:
    """Q1b -> Q2/Q3. The mixture-to-loss response surface.

    Under a sum-to-one constraint the per-domain coefficients are identified
    only up to an additive constant, so ``contrast_basis`` must name the
    reference that makes them readable. Reading a single coefficient as the
    absolute value of a domain, without that reference, is meaningless.

    ``zero_policy`` is recorded for the same reason: a large share of the
    mixture cells are exactly zero, log-ratio transforms are undefined there,
    and the treatment chosen changes what the coefficients mean.
    """

    schema_version: str
    mixture_domains: List[str]
    loss_columns: List[str]
    contrast_basis: str
    zero_policy: str
    renormalisation: str
    coefficients: Dict[str, Dict[str, float]]
    fit_scale: str
    validation: Dict[str, Any]
    domains_without_loss: List[str]
    provenance: Provenance

    def validate(self) -> None:
        self.provenance.validate()
        if not self.contrast_basis:
            raise InterfaceError("contrast_basis must be declared")
        if not self.zero_policy:
            raise InterfaceError("zero_policy must be declared")
        for target, coef in self.coefficients.items():
            missing = set(self.mixture_domains) - set(coef)
            if missing and self.contrast_basis not in ("none",):
                # A dropped reference domain is expected; anything else is not.
                if missing != {self.contrast_basis}:
                    raise InterfaceError(
                        f"target {target} is missing coefficients for {sorted(missing)}"
                    )


@dataclass
class IF3ScalingLaw:
    """Q2 -> Q3/Q4. The fitted generalised scaling law.

    ``validity_box`` states the region of (N, D, Q) the fit was identified in.
    Any consumer evaluating outside it is extrapolating and must say so.

    ``q_term_provenance`` is separate from the overall provenance because the
    quality dependence is identified only from semi-synthetic data: the law can
    be well determined in N and D while its Q behaviour is largely a recovery
    of whatever generated those points.
    """

    schema_version: str
    functional_form: str
    params: Dict[str, float]
    param_cov: Optional[List[List[float]]]
    bootstrap: Dict[str, Any]
    validity_box: Dict[str, Sequence[float]]
    validation: Dict[str, Any]
    q_term_provenance: Provenance
    provenance: Provenance

    def validate(self) -> None:
        self.provenance.validate()
        self.q_term_provenance.validate()
        if self.bootstrap.get("unit") != "model":
            raise InterfaceError(
                "bootstrap unit must be 'model': the principal fit data is a "
                "small number of long training trajectories, so resampling "
                "rows would treat correlated checkpoints as independent and "
                "overstate precision"
            )
        for key in ("N", "D", "Q"):
            if key not in self.validity_box:
                raise InterfaceError(f"validity_box is missing {key}")


@dataclass
class IF4LossBenchmarkBridge:
    """Q2/Q4 <-> Q4. The mapping from cross-entropy loss to benchmark score.

    The bridge is stratified by comparability and the homogeneous stratum is
    small, so ``prediction_error`` is mandatory: with few anchor models the
    mapping error can dominate a downstream forecast, and a forecast that hides
    it reports a precision it does not have.
    """

    schema_version: str
    strata: Dict[str, int]
    primary_stratum: str
    form: str
    params: Dict[str, float]
    prediction_error: Dict[str, float]
    n_anchor_models: int
    score_scale: str
    provenance: Provenance

    def validate(self) -> None:
        self.provenance.validate()
        if self.primary_stratum not in self.strata:
            raise InterfaceError("primary_stratum is not one of the declared strata")
        if not self.prediction_error:
            raise InterfaceError("prediction_error is mandatory for the bridge")
        if self.n_anchor_models <= 0:
            raise InterfaceError("n_anchor_models must be positive")


def _encode(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"not JSON-serialisable: {type(obj)!r}")


def save(interface: Any, path: Path) -> Path:
    """Validate then write an interface object as JSON."""
    interface.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(interface)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=_encode)
        handle.write("\n")
    return path


def load(path: Path) -> Dict[str, Any]:
    """Read an interface JSON document.

    Returns the raw mapping rather than a dataclass so that a consumer written
    against one schema version can inspect ``schema_version`` before deciding
    how to interpret the rest.
    """
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


__all__ = [
    "SCHEMA_VERSION",
    "InterfaceError",
    "Provenance",
    "IF1DomainQuality",
    "IF2MixtureResponse",
    "IF3ScalingLaw",
    "IF4LossBenchmarkBridge",
    "save",
    "load",
]
